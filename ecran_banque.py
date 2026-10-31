"""Banque : import des relevés (CSV) avec rapprochement automatique, contrôle du relevé, archives."""
from __future__ import annotations

from datetime import date, datetime

import pandas as pd
import streamlit as st

import metier
from commun import (backend, categories, charger, eur, flash, journaliser, lecture_seule, mois_debut, operations,
                    rafraichir, ranger_fichier, utilisateur)


def page_banque():
    st.header("Banque")
    onglets = st.tabs(["📥 Importer un relevé", "⚖️ Contrôle du relevé", "🗂️ Relevés contrôlés"])
    with onglets[0]:
        _import_releve()
    with onglets[1]:
        _controle()
    with onglets[2]:
        r = charger("releves")
        if r.empty:
            st.info("Aucun contrôle enregistré.")
        else:
            st.dataframe(r.iloc[::-1].drop(columns=["id"]), hide_index=True, width="stretch")


def _import_releve():
    st.caption("Relevé **CSV** : chaque ligne est comparée à la comptabilité (même montant, date à ±10 jours). "
               "Relevé **PDF** : simplement archivé dans le Drive. Dans l'espace en ligne de la banque, choisissez "
               "« Télécharger les opérations » au format CSV.")
    if lecture_seule():
        return
    fichier = st.file_uploader("Relevé bancaire", type=["csv", "pdf"], key="releve")
    if not fichier:
        return
    if fichier.name.lower().endswith(".pdf"):
        if st.button("Archiver ce relevé PDF", type="primary"):
            lieu = ranger_fichier("Relevés bancaires", f"{date.today():%Y-%m-%d}_{fichier.name}", fichier.getvalue(),
                                  "application/pdf")
            journaliser("banque", f"relevé PDF archivé : {fichier.name}")
            st.success(f"Relevé archivé : {lieu}")
        return
    try:
        releve = metier.lire_releve_csv(fichier.getvalue())
    except ValueError as e:
        st.error(str(e))
        return
    if releve.empty:
        st.warning("Aucune opération lue dans ce fichier.")
        return
    ops = operations()
    cats = categories()
    apercu = metier.analyser_releve(releve, ops, cats)
    compte = apercu["resultat"].value_counts()
    c1, c2, c3 = st.columns(3)
    c1.metric("🆕 Nouvelles", int(compte.get("Nouvelle", 0)))
    c2.metric("🔗 Déjà saisies, à rapprocher", int(compte.get("À rapprocher", 0)))
    c3.metric("✅ Déjà rapprochées", int(compte.get("Déjà rapprochée", 0)))
    st.caption("Décochez une ligne pour l'ignorer. Pour les nouvelles lignes, vérifiez la catégorie proposée "
               "(vide = « à classer »).")
    edite = st.data_editor(
        apercu, hide_index=True, width="stretch", key="apercu_releve",
        disabled=["date", "libelle", "montant", "resultat", "ecriture", "operation_id"],
        column_config={"importer": st.column_config.CheckboxColumn("Traiter"),
                       "date": st.column_config.DateColumn("Date", format="DD/MM/YYYY"), "libelle": "Libellé banque",
                       "montant": st.column_config.NumberColumn("Montant", format="%.2f €"),
                       "resultat": "Résultat", "operation_id": None, "ecriture": "Écriture correspondante",
                       "categorie": st.column_config.SelectboxColumn("Catégorie (nouvelles)", options=cats)})
    a_traiter = edite[edite["importer"] & (edite["resultat"] != "Déjà rapprochée")]
    if not st.button(f"Valider ({len(a_traiter)} ligne(s))", type="primary", disabled=a_traiter.empty):
        return
    brut = charger("operations").copy()
    n_rap = 0
    for r in a_traiter[a_traiter["resultat"] == "À rapprocher"].itertuples():
        brut.loc[brut["id"] == r.operation_id, "rapproche"] = "oui"
        n_rap += 1
    if n_rap:
        backend().remplacer("operations", brut)
    nouvelles = []
    for r in a_traiter[a_traiter["resultat"] == "Nouvelle"].sort_values("date").itertuples():
        sens = "Recette" if r.montant > 0 else "Dépense"
        cat = r.categorie if r.categorie and metier._sens_categorie(r.categorie) == sens else \
            metier.trouver_categorie("", sens, charger("categories"))[0]
        nouvelles.append(metier.nouvelle_operation(
            r.date, sens, cat, r.libelle or "Opération bancaire", abs(r.montant), "Banque", "", "", "",
            f"Import du relevé {fichier.name}", utilisateur(), mois_debut(), rapproche=True,
            origine="relevé bancaire"))
    if nouvelles:
        backend().ajouter("operations", nouvelles)
    lieu = ranger_fichier("Relevés bancaires", f"{date.today():%Y-%m-%d}_{fichier.name}", fichier.getvalue(),
                          "text/csv")
    journaliser("banque", f"relevé {fichier.name} : {n_rap} rapprochée(s), {len(nouvelles)} ajoutée(s)")
    rafraichir()
    flash(f"Relevé traité : {n_rap} écriture(s) rapprochée(s), {len(nouvelles)} ajoutée(s)."
          + (" Relevé archivé dans le Drive." if lieu else ""))
    st.rerun()


def _controle():
    st.caption("Comme la feuille « Rappr » de l'Excel : on compare le solde indiqué sur le relevé au solde des "
               "écritures cochées « rapprochées ». Un écart signale un oubli ou une erreur de saisie.")
    ops = operations()
    c1, c2 = st.columns(2)
    jour = c1.date_input("Date du relevé", value=date.today(), format="DD/MM/YYYY", key="date_releve")
    solde_releve = c2.number_input("Solde indiqué sur le relevé (€)", step=0.01, format="%.2f", key="solde_releve")
    s = metier.soldes(ops, jusqu_au=jour)
    ecart = round(solde_releve - s["pointe"], 2)
    m1, m2, m3 = st.columns(3)
    m1.metric("Solde pointé à cette date", eur(s["pointe"]))
    m2.metric("Solde comptable (tout compris)", eur(s["banque"]))
    m3.metric("Écart relevé − pointé", eur(ecart), delta="OK" if abs(ecart) < 0.005 else None)
    if abs(ecart) < 0.005:
        st.success("Le relevé et les écritures rapprochées concordent.")
    else:
        st.warning("Écart à expliquer. Écritures bancaires non rapprochées jusqu'à cette date :")
    non_rap = ops[(ops["source"] != "Espèces") & ~ops["rapproche_b"] & (ops["date"] <= pd.Timestamp(jour))]
    if not non_rap.empty:
        st.dataframe(non_rap.sort_values("date")[["date", "libelle", "signe", "tiers"]], hide_index=True,
                     width="stretch", column_config={"date": st.column_config.DateColumn("Date", format="DD/MM/YYYY"),
                                                     "signe": st.column_config.NumberColumn("Montant", format="%.2f €"),
                                                     "libelle": "Libellé", "tiers": "Tiers"})
        st.caption(f"Total non rapproché : {eur(non_rap['signe'].sum())}. Cochez-les dans « Opérations » quand elles "
                   "apparaissent sur un relevé.")
    if st.button("Enregistrer ce contrôle"):
        backend().ajouter("releves", [{"id": metier.nouvel_id(), "date_releve": jour.isoformat(),
                                       "solde_releve": round(solde_releve, 2), "solde_pointe": s["pointe"],
                                       "ecart": ecart, "fichier": "", "cree_par": utilisateur(),
                                       "cree_le": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}])
        journaliser("banque", f"contrôle du relevé au {jour:%d/%m/%Y} : écart {ecart}")
        rafraichir()
        st.success("Contrôle enregistré.")
