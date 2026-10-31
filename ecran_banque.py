"""Banque : pointage relevé par relevé (validation à écart nul, verrouillage), import des relevés CSV."""
from __future__ import annotations

from datetime import date, datetime

import pandas as pd
import streamlit as st

import metier
from commun import (backend, categories, charger, est_admin, eur, flash, journaliser, lecture_seule, mois_debut,
                    operations, rafraichir, ranger_fichier, utilisateur)


def page_banque():
    st.header("Banque")
    onglets = st.tabs(["✅ Pointage relevé par relevé", "📥 Importer un relevé (CSV / Excel)", "🗂️ Relevés validés"])
    with onglets[0]:
        _pointage()
    with onglets[1]:
        _import_releve()
    with onglets[2]:
        _releves_valides()


def _import_releve():
    st.caption("Relevé **CSV ou Excel** (export « Télécharger les opérations » du Crédit Mutuel) : chaque ligne est comparée à la comptabilité (même montant, date à ±10 jours). "
               "Relevé **PDF** : simplement archivé dans le Drive. Dans l'espace en ligne de la banque, choisissez "
               "« Télécharger les opérations » au format CSV.")
    if lecture_seule():
        return
    fichier = st.file_uploader("Relevé bancaire", type=["csv", "xlsx", "xls", "pdf"], key="releve")
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
        releve = metier.lire_releve(fichier.getvalue(), fichier.name)
    except ValueError as e:
        st.error(str(e))
        return
    if releve.empty:
        st.warning("Aucune opération lue dans ce fichier.")
        return
    solde_fin = releve.attrs.get("solde_fin")
    st.caption(f"{len(releve)} opération(s) du {releve['date'].min():%d/%m/%Y} au {releve['date'].max():%d/%m/%Y}"
               + (f" · solde indiqué par la banque : **{eur(solde_fin[1])}** au {solde_fin[0]:%d/%m/%Y} "
                  "(il sera proposé dans l'onglet Pointage)" if solde_fin else ""))
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
    d0, _ = metier.dernier_releve_valide(charger("releves"))
    if d0:
        anciennes = a_traiter[(a_traiter["resultat"] == "Nouvelle") & (a_traiter["date"].map(metier.lire_date) <= d0)]
        if not anciennes.empty:
            st.warning(f"{len(anciennes)} ligne(s) datée(s) avant le dernier relevé validé ({d0:%d/%m/%Y}) ne sont "
                       "pas dans la comptabilité : elles sont ignorées. Si elles sont réelles, annulez la validation "
                       "de ce relevé (onglet « Relevés validés ») avant de les reprendre.")
            a_traiter = a_traiter.drop(anciennes.index)
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
                          fichier.type or "application/octet-stream")
    journaliser("banque", f"relevé {fichier.name} : {n_rap} rapprochée(s), {len(nouvelles)} ajoutée(s)")
    if solde_fin:
        st.session_state["releve_prefill"] = solde_fin
    rafraichir()
    flash(f"Relevé traité : {n_rap} écriture(s) rapprochée(s), {len(nouvelles)} ajoutée(s)."
          + (" Relevé archivé dans le Drive." if lieu else "")
          + (" Terminez dans l'onglet « Pointage » : la date et le solde du relevé y sont déjà remplis." if solde_fin else ""))
    st.rerun()


def _pointage():
    """Rapprochement bancaire rigoureux : un relevé à la fois, validé seulement quand l'écart est nul.

    Solde pointé = somme des écritures bancaires cochées « rapprochées » jusqu'à la date du relevé.
    Il doit être égal au solde imprimé sur le relevé. Une fois validé, le relevé verrouille ses écritures."""
    releves = charger("releves")
    d0, s0 = metier.dernier_releve_valide(releves)
    if "releve_prefill" in st.session_state:          # date et solde lus dans le dernier relevé importé
        st.session_state["pointage_date"], st.session_state["pointage_solde"] = st.session_state.pop("releve_prefill")
    ops = operations()
    st.markdown(
        "**Méthode** : prenez les relevés dans l'ordre chronologique. Pour chacun : date et solde de fin du relevé "
        "→ cochez les écritures qui y figurent → saisissez celles qui manquent → validez quand l'écart est à **0,00 €**.")
    if d0:
        st.info(f"Dernier relevé validé : **{d0:%d/%m/%Y}**, solde **{eur(s0)}**. Les écritures pointées jusqu'à "
                "cette date sont verrouillées.")
    else:
        st.info("Aucun relevé validé : commencez par le premier relevé du compte (ouverture en 2023).")
    if lecture_seule():
        return
    c1, c2, c3 = st.columns(3)
    jour = c1.date_input("Date de fin du relevé", value=None, format="DD/MM/YYYY", key="pointage_date",
                         min_value=d0 or None)
    solde_releve = c2.number_input("Solde de fin imprimé sur le relevé (€)", step=0.01, format="%.2f",
                                   value=None, key="pointage_solde")
    pdf = c3.file_uploader("Relevé PDF (facultatif, archivé)", type=["pdf"], key="pointage_pdf")
    if jour is None or solde_releve is None:
        st.caption("Indiquez la date et le solde du relevé pour afficher les écritures à pointer.")
        return
    if d0 and jour <= d0:
        st.error("Ce relevé est antérieur ou égal au dernier relevé validé.")
        return

    banque = ops[ops["source"] != "Espèces"]
    deja = float(banque.loc[banque["rapproche_b"] & (banque["releve_d"] <= pd.Timestamp(jour)), "signe"].sum())
    # Écritures non pointées datées jusqu'à la fin du relevé (+ 5 jours : chèque saisi après son encaissement)
    candidats = banque[~banque["rapproche_b"] & (banque["date"] <= pd.Timestamp(jour) + pd.Timedelta(days=5))]
    candidats = candidats.sort_values("date")
    vue = candidats[["id", "date", "libelle", "tiers", "signe"]].assign(pointer=False)
    edite = st.data_editor(
        vue[["pointer", "id", "date", "libelle", "tiers", "signe"]], hide_index=True, width="stretch",
        key=f"pointage_{jour}", disabled=["id", "date", "libelle", "tiers", "signe"],
        column_config={"pointer": st.column_config.CheckboxColumn("Sur le relevé"), "id": None,
                       "date": st.column_config.DateColumn("Date", format="DD/MM/YYYY"), "libelle": "Libellé",
                       "tiers": "Tiers", "signe": st.column_config.NumberColumn("Montant", format="%.2f €")})
    coches = edite[edite["pointer"]]
    pointe = round(deja + float(coches["signe"].sum()), 2)
    ecart = round(float(solde_releve) - pointe, 2)
    m1, m2, m3 = st.columns(3)
    m1.metric("Solde du relevé", eur(solde_releve))
    m2.metric("Solde pointé", eur(pointe))
    m3.metric("Écart", eur(ecart), delta="équilibré" if abs(ecart) < 0.005 else "à expliquer",
              delta_color="normal" if abs(ecart) < 0.005 else "inverse")
    if candidats.empty and abs(ecart) >= 0.005:
        st.warning("Toutes les écritures sont pointées mais l'écart persiste : il manque des écritures. "
                   "Saisissez-les ci-dessous.")

    with st.expander("➕ Saisir une écriture qui figure sur le relevé mais pas dans la comptabilité",
                     expanded=abs(ecart) >= 0.005 and candidats.empty):
        sens = st.radio("Sens", ["Dépense", "Recette"], horizontal=True, key="pointage_sens")
        with st.form("pointage_manquante", clear_on_submit=True):
            a, b_, c = st.columns(3)
            d = a.date_input("Date", value=jour, max_value=jour, format="DD/MM/YYYY")
            montant = b_.number_input("Montant (€)", min_value=0.0, step=1.0, format="%.2f")
            cat = c.selectbox("Catégorie", categories(sens))
            libelle = st.text_input("Libellé (tel que sur le relevé)")
            tiers = st.text_input("Tiers")
            if st.form_submit_button("Ajouter, déjà pointée"):
                if montant <= 0 or not libelle.strip():
                    st.error("Le montant et le libellé sont obligatoires.")
                else:
                    backend().ajouter("operations", [metier.nouvelle_operation(
                        d, sens, cat, libelle, montant, "Banque", "", tiers, "", f"Saisie au pointage du relevé du "
                        f"{jour:%d/%m/%Y}", utilisateur(), mois_debut(), rapproche=True, origine="pointage",
                        releve=jour)])
                    journaliser("pointage", f"écriture ajoutée : {libelle} {montant} €")
                    rafraichir()
                    st.rerun()

    b1, b2 = st.columns(2)
    if b1.button(f"Enregistrer le pointage ({len(coches)} écriture(s))", disabled=coches.empty):
        _pointer(coches["id"].tolist(), jour)
        flash(f"{len(coches)} écriture(s) pointée(s). Écart restant : {eur(ecart)}.")
        st.rerun()
    if b2.button("Valider le relevé", type="primary", disabled=abs(ecart) >= 0.005,
                 help="Possible seulement quand l'écart est nul."):
        if not coches.empty:
            _pointer(coches["id"].tolist(), jour)
        lien = ranger_fichier("Relevés bancaires", f"releve_{jour:%Y-%m-%d}.pdf", pdf.getvalue(),
                              "application/pdf") if pdf else ""
        backend().ajouter("releves", [{"id": metier.nouvel_id(), "date_releve": jour.isoformat(),
                                       "solde_releve": round(float(solde_releve), 2), "solde_pointe": pointe,
                                       "ecart": 0, "fichier": lien, "cree_par": utilisateur(),
                                       "cree_le": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "valide": "oui"}])
        journaliser("pointage", f"relevé du {jour:%d/%m/%Y} validé ({eur(solde_releve)})")
        rafraichir()
        flash(f"Relevé du {jour:%d/%m/%Y} validé : {eur(solde_releve)}. Passez au relevé suivant.")
        st.rerun()


def _pointer(ids: list[str], jour) -> None:
    brut = charger("operations").copy()
    if "releve" not in brut:
        brut["releve"] = ""
    brut.loc[brut["id"].isin(ids), "rapproche"] = "oui"
    brut.loc[brut["id"].isin(ids), "releve"] = jour.isoformat()
    backend().remplacer("operations", brut)
    journaliser("pointage", f"{len(ids)} écriture(s) pointée(s)")
    rafraichir()


def _releves_valides():
    r = charger("releves")
    r = r[r["valide"].map(metier.oui)] if not r.empty and "valide" in r else r.iloc[0:0]
    if r.empty:
        st.info("Aucun relevé validé.")
        return
    vue = r.assign(d=r["date_releve"].map(metier.lire_date)).sort_values("d", ascending=False)
    vue["solde_releve"] = metier.nombres(vue["solde_releve"])
    vue["fichier"] = vue["fichier"].where(vue["fichier"].astype(str).str.startswith("http"), None)
    st.dataframe(vue[["d", "solde_releve", "fichier", "cree_par", "cree_le"]], hide_index=True, width="stretch",
                 column_config={"d": st.column_config.DateColumn("Relevé du", format="DD/MM/YYYY"),
                                "solde_releve": st.column_config.NumberColumn("Solde", format="%.2f €"),
                                "fichier": st.column_config.LinkColumn("Relevé", display_text="📄 ouvrir"),
                                "cree_par": "Validé par", "cree_le": "Le"})
    if est_admin():
        st.caption("Une erreur découverte après validation ? Annulez le dernier relevé validé : ses écritures sont "
                   "déverrouillées, le pointage reste coché.")
        dernier = vue.iloc[0]
        if st.checkbox(f"Je confirme l'annulation de la validation du relevé du {dernier['d']:%d/%m/%Y}"):
            if st.button("Annuler cette validation"):
                brut = charger("releves").copy()
                brut.loc[brut["id"] == dernier["id"], "valide"] = "annulé"
                backend().remplacer("releves", brut)
                journaliser("pointage", f"validation du relevé du {dernier['d']:%d/%m/%Y} annulée")
                rafraichir()
                st.rerun()
