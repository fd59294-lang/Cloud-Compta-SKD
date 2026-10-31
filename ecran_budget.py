"""Budget prévisionnel par catégorie : proposé d'après le réalisé précédent, comparé au réalisé."""
from __future__ import annotations

from datetime import datetime

import altair as alt
import pandas as pd
import streamlit as st

import metier
from commun import (backend, categories, charger, eur, est_admin, exercice_courant, journaliser, libelle_exercice,
                    operations, rafraichir)


def page_budget():
    st.header("Budget prévisionnel")
    ops = operations()
    saisons = sorted({exercice_courant() - 1, exercice_courant(), exercice_courant() + 1}
                     | set(metier.nombres(charger("budget")["exercice"]).dropna().astype(int).tolist()), reverse=True)
    ex = st.selectbox("Exercice", saisons, index=saisons.index(exercice_courant()), format_func=libelle_exercice)
    comp = metier.budget_compare(ops, charger("budget"), ex)
    if comp["prevu"].sum() == 0:
        c1, c2 = st.columns([2, 1])
        hausse = c1.slider("Proposition : réalisé de l'exercice précédent + hausse de (%)", -20, 30, 0)
        prop = metier.proposer_budget(ops, ex, hausse)
        if not prop.empty:
            st.info(f"Aucun budget enregistré pour {libelle_exercice(ex)} : les montants ci-dessous sont proposés "
                    f"d'après le réalisé {libelle_exercice(ex - 1)} (arrondis à la dizaine). Ajustez puis enregistrez.")
            comp = comp.drop(columns=["prevu"]).merge(prop, on=["sens", "categorie"], how="outer")
            comp["prevu"] = comp["prevu"].fillna(0.0)
            comp[["realise", "realise_n1"]] = comp[["realise", "realise_n1"]].fillna(0.0)
            comp["commentaire"] = comp["commentaire"].fillna("")
    vue = comp[["sens", "categorie", "prevu", "realise_n1", "realise", "commentaire"]].copy()
    edite = st.data_editor(
        vue, num_rows="dynamic", hide_index=True, width="stretch", key=f"budget_{ex}",
        disabled=["realise_n1", "realise"] if est_admin() else True,
        column_config={"sens": st.column_config.SelectboxColumn("Sens", options=["Recette", "Dépense"], required=True),
                       "categorie": st.column_config.SelectboxColumn("Catégorie", options=categories(actives=False),
                                                                     required=True),
                       "prevu": st.column_config.NumberColumn("Prévu", format="%.2f €", min_value=0.0),
                       "realise_n1": st.column_config.NumberColumn(f"Réalisé {libelle_exercice(ex - 1)}", format="%.2f €"),
                       "realise": st.column_config.NumberColumn(f"Réalisé {libelle_exercice(ex)}", format="%.2f €"),
                       "commentaire": "Commentaire"})
    edite["prevu"] = pd.to_numeric(edite["prevu"], errors="coerce").fillna(0.0)
    pr = edite.loc[edite["sens"] == "Recette", "prevu"].sum()
    pdp = edite.loc[edite["sens"] == "Dépense", "prevu"].sum()
    rr = edite.loc[edite["sens"] == "Recette", "realise"].fillna(0).sum()
    rd = edite.loc[edite["sens"] == "Dépense", "realise"].fillna(0).sum()
    c1, c2, c3 = st.columns(3)
    c1.metric("Recettes prévues / réalisées", f"{eur(pr)} / {eur(rr)}")
    c2.metric("Dépenses prévues / réalisées", f"{eur(pdp)} / {eur(rd)}")
    c3.metric("Résultat prévu", eur(pr - pdp))
    graphe = edite[edite["prevu"] > 0].copy()
    if not graphe.empty:
        graphe["cat"] = graphe["categorie"].map(metier.nom_categorie)
        graphe["avancement"] = (graphe["realise"].fillna(0) / graphe["prevu"] * 100).round(0)
        graphe["depasse"] = (graphe["sens"] == "Dépense") & (graphe["avancement"] > 100)
        st.altair_chart(alt.Chart(graphe).mark_bar().encode(
            y=alt.Y("cat:N", title=None, axis=alt.Axis(labelLimit=260), sort="-x"),
            x=alt.X("avancement:Q", title="Réalisé en % du prévu", scale=alt.Scale(domainMax=150, clamp=True)),
            color=alt.condition(alt.datum.depasse, alt.value("#C8102E"), alt.value("#2E7D32")),
            row=alt.Row("sens:N", title=None),
            tooltip=["cat", alt.Tooltip("prevu:Q", format=",.2f", title="Prévu"),
                     alt.Tooltip("realise:Q", format=",.2f", title="Réalisé"),
                     alt.Tooltip("avancement:Q", title="%")]).properties(width=520), width="content")
        st.caption("En rouge : dépense qui dépasse son budget.")
    if est_admin() and st.button("Enregistrer ce budget", type="primary"):
        edite = edite.dropna(subset=["categorie"])
        if edite.duplicated(subset=["sens", "categorie"]).any():
            st.error("Une même catégorie apparaît deux fois.")
            return
        autres = charger("budget")
        autres = autres[metier.nombres(autres["exercice"]) != ex] if not autres.empty else autres
        neuf = edite[edite["prevu"] > 0].assign(exercice=ex, maj_le=datetime.now().strftime("%Y-%m-%d %H:%M"))
        neuf = neuf[["exercice", "categorie", "sens", "prevu", "commentaire", "maj_le"]].fillna("")
        backend().remplacer("budget", pd.concat([autres, neuf.astype(str)], ignore_index=True))
        journaliser("budget", f"exercice {ex} enregistré ({len(neuf)} lignes)")
        rafraichir()
        st.success("Budget enregistré. Il apparaît dans le tableau de bord, le bilan et le rapport d'AG.")
