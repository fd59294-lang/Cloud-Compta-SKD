"""Rapports : compte financier, bilan financier, rapport d'AG, comparaison, synthèse des opérations."""
from __future__ import annotations

import io
from datetime import datetime

import pandas as pd
import streamlit as st

import adherents as A
import metier
import rapports as R
from commun import (charger, club, ecrire_parametre, exercices_disponibles, journaliser, libelle_exercice, logo,
                    mois_debut, operations, parametre, peut_saisir, ranger_fichier)


def _livrer(pdf: bytes, nom: str):
    if peut_saisir():
        lieu = ranger_fichier("Rapports", nom, pdf, "application/pdf")
        if lieu:
            journaliser("rapport", nom)
            st.success(f"Rapport rangé dans le dossier « Rapports » du Drive : {lieu}")
    st.download_button(f"Télécharger {nom}", pdf, file_name=nom, mime="application/pdf", type="primary")


def page_rapports():
    st.header("Rapports et assemblée générale")
    ops = operations()
    if ops.empty:
        st.info("Aucune opération enregistrée : reprenez d'abord l'historique ou saisissez des opérations.")
        return
    md = mois_debut()
    exs = exercices_disponibles()
    ex = st.selectbox("Exercice / saison", exs, format_func=libelle_exercice, key="rapport_exercice")
    c = club()
    signataires = {k: v for k, v in (("Le/la président(e)", c.get("president")),
                                      ("Le/la trésorier(ère)", c.get("tresorier"))) if v}

    def donnees(**kw) -> R.DonneesRapport:
        return R.DonneesRapport(club=c, logo=logo(), exercice=int(ex), mois_debut=md, operations=ops,
                                budget=charger("budget"), signataires=signataires, **kw)

    onglets = st.tabs(["🏆 Rapport d'AG", "📗 Compte financier", "📈 Bilan financier", "📉 Comparaison",
                       "🗓️ Synthèse des opérations"])
    with onglets[0]:
        st.caption("Dossier complet à présenter en assemblée générale. Les textes sont conservés d'une génération à "
                   "l'autre.")
        colonnes = st.columns(3)
        choisies = [cle for i, (cle, titre) in enumerate(R.SECTIONS_AG.items())
                    if colonnes[i % 3].checkbox(titre, value=True, key=f"section_{cle}")]
        moral = st.text_area("Rapport moral et d'activité (un paragraphe par ligne)", value=parametre(f"moral_{ex}"),
                             height=140, placeholder="Cours, stages, passages de grades, compétitions, résultats…")
        perspectives = st.text_area("Perspectives", value=parametre(f"perspectives_{ex}"), height=100)
        resolutions = st.text_area("Résolutions soumises au vote (une par ligne)",
                                   value=parametre("resolutions_ag", R.DonneesRapport.__dataclass_fields__[
                                       "resolutions"].default), height=120)
        if st.button("Générer le rapport d'AG", type="primary", disabled=not choisies):
            etat = A.etat_saison(charger("adherents"), charger("inscriptions"), charger("paiements"), ex)
            dons = charger("dons").copy()
            if not dons.empty:
                dons["montant"] = metier.nombres(dons["montant"]).fillna(0)
                debut, fin = metier.bornes_exercice(ex, md)
                d = pd.to_datetime(dons["date"], errors="coerce")
                dons = dons[(d >= pd.Timestamp(debut)) & (d <= pd.Timestamp(fin))]
            if peut_saisir():
                for cle, val in ((f"moral_{ex}", moral), (f"perspectives_{ex}", perspectives),
                                 ("resolutions_ag", resolutions)):
                    if parametre(cle) != val:
                        ecrire_parametre(cle, val)
            with st.spinner("Préparation du rapport…"):
                pdf = R.rapport_ag(donnees(etat_adherents=A.statistiques_saison(etat, charger("inscriptions"), ex),
                                           dons=dons, texte_moral=moral, texte_perspectives=perspectives,
                                           resolutions=resolutions, sections=choisies))
            _livrer(pdf, f"rapport_AG_{libelle_exercice(ex)}_{datetime.now():%Y-%m-%d_%Hh%M}.pdf")
    with onglets[1]:
        st.caption("Récapitulatif des recettes et dépenses de la période, avec les soldes banque et caisse "
                   "(feuille « Compte financier » de l'Excel).")
        if st.button("Générer le compte financier", type="primary"):
            _livrer(R.compte_financier(donnees()), f"compte_financier_{libelle_exercice(ex)}.pdf")
    with onglets[2]:
        st.caption("Synthèse, trésorerie, graphique mensuel, détail par catégorie et budget prévu / réalisé.")
        if st.button("Générer le bilan financier", type="primary"):
            _livrer(R.bilan_financier(donnees()), f"bilan_financier_{libelle_exercice(ex)}.pdf")
    with onglets[3]:
        autres = [e for e in exs if e != ex] or [ex - 1]
        ex1 = st.selectbox("Comparer avec", autres, format_func=libelle_exercice)
        if st.button("Générer la comparaison", type="primary"):
            a, b = sorted([int(ex1), int(ex)])
            _livrer(R.comparatif(donnees(), a, b), f"comparaison_{libelle_exercice(a)}_{libelle_exercice(b)}.pdf")
    with onglets[4]:
        s = metier.synthese_mensuelle(ops, ex, md)
        st.dataframe(s, hide_index=True, width="stretch",
                     column_config={c: st.column_config.NumberColumn(c, format="%.2f") for c in s.columns[2:]})
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as w:
            s.to_excel(w, sheet_name="Synthèse", index=False)
            metier.mettre_en_forme(w)
        st.download_button("Télécharger la synthèse (Excel)", buf.getvalue(),
                           file_name=f"synthese_operations_{libelle_exercice(ex)}.xlsx")

