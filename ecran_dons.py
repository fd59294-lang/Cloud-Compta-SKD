"""Dons et reçus fiscaux (modèle Cerfa 11580, numérotation sans trou, duplicata)."""
from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

import documents as D
import metier
from commun import (backend, categorie_par_code, charger, club, enregistrer_document, eur, journaliser,
                    lecture_seule, libelle_exercice, logo, mois_debut, peut_saisir, prochain_numero, rafraichir,
                    ranger_fichier, utilisateur)
from referentiel import MODES_PAIEMENT, NATURES_DON


def _pdf(r, numero: str, duplicata: bool) -> bytes:
    return D.recu_fiscal(club(), logo(), numero, r["nom"], r["adresse"], float(r["montant"]),
                         metier.lire_date(r["date"]) or date.today(), r["nature"], r["mode"],
                         r.get("description", ""), duplicata=duplicata)


def page_dons():
    st.header("Dons et reçus fiscaux")
    st.caption("Le reçu fiscal permet au donateur de déduire 66 % de son don de ses impôts. Il ne s'émet que pour "
               "un don sans contrepartie (jamais pour une cotisation).")
    onglets = st.tabs(["➕ Nouveau don", "📜 Dons enregistrés"])
    with onglets[0]:
        _nouveau_don()
    with onglets[1]:
        _liste()


def _nouveau_don():
    if lecture_seule():
        return
    nature = st.radio("Nature du don", NATURES_DON, horizontal=True)
    with st.form("don", clear_on_submit=True):
        c1, c2 = st.columns(2)
        nom = c1.text_input("Nom et prénom du donateur (ou raison sociale)")
        email = c2.text_input("E-mail (facultatif)")
        adresse = st.text_input("Adresse complète (obligatoire pour le reçu fiscal)")
        c3, c4, c5 = st.columns(3)
        montant = c3.number_input("Montant ou valeur (€)", min_value=0.0, step=1.0, format="%.2f")
        jour = c4.date_input("Date du don", value=date.today(), format="DD/MM/YYYY")
        mode = c5.selectbox("Mode de versement", MODES_PAIEMENT if nature == "Numéraire" else ["—"])
        description = st.text_input("Description du don en nature", disabled=nature == "Numéraire")
        c6, c7 = st.columns(2)
        compta = c6.checkbox("Ajouter l'écriture en comptabilité", value=nature == "Numéraire",
                             disabled=nature != "Numéraire")
        recu = c7.checkbox("Émettre le reçu fiscal maintenant", value=True)
        valide = st.form_submit_button("Enregistrer le don", type="primary")
    if not valide:
        return
    if not nom.strip() or montant <= 0:
        st.error("Le nom du donateur et le montant sont obligatoires.")
        return
    if recu and not adresse.strip():
        st.error("L'adresse du donateur est obligatoire pour émettre un reçu fiscal.")
        return
    don = {"id": metier.nouvel_id(), "date": jour.isoformat(), "nom": nom.strip(), "adresse": adresse.strip(),
           "email": email.strip(), "montant": round(montant, 2), "nature": nature,
           "mode": mode if nature == "Numéraire" else "—", "description": description.strip(), "numero_recu": "",
           "operation_id": "", "saisi_par": utilisateur(), "saisi_le": metier.maintenant()}
    pdf = None
    if recu:
        don["numero_recu"] = prochain_numero("DON", jour.year)
        pdf = _pdf(don, don["numero_recu"], False)
        lieu = ranger_fichier("Reçus fiscaux", f"{don['numero_recu']}_{nom.strip()}.pdf".replace(" ", "_"), pdf,
                              "application/pdf")
        enregistrer_document("Reçu fiscal", don["numero_recu"], nom.strip(), f"Don ({nature.lower()})", montant, lieu)
    if compta and nature == "Numéraire":
        op = metier.nouvelle_operation(jour, "Recette", categorie_par_code("754"), f"Don – {nom.strip()}", montant,
                                       "Espèces" if mode == "Espèces" else "Banque", mode, nom.strip(),
                                       don["numero_recu"], "", utilisateur(), mois_debut(), origine=f"don:{don['id']}")
        don["operation_id"] = op["id"]
        backend().ajouter("operations", [op])
    backend().ajouter("dons", [don])
    journaliser("don", f"{nom.strip()} : {montant} €" + (f" – reçu {don['numero_recu']}" if recu else ""))
    rafraichir()
    st.success(f"Don de {eur(montant)} enregistré." + (f" Reçu fiscal {don['numero_recu']}." if recu else ""))
    if pdf:
        st.download_button(f"Télécharger le reçu {don['numero_recu']}", pdf, file_name=f"{don['numero_recu']}.pdf",
                           mime="application/pdf", type="primary")


def _liste():
    dons = charger("dons")
    if dons.empty:
        st.info("Aucun don enregistré.")
        return
    dons = dons.copy()
    dons["montant"] = metier.nombres(dons["montant"]).fillna(0)
    dons["d"] = pd.to_datetime(dons["date"], errors="coerce")
    dons["saison"] = dons["d"].map(lambda d: metier.exercice_de(d.date(), mois_debut()) if pd.notna(d) else 0)
    st.dataframe(dons.sort_values("d", ascending=False)[["date", "nom", "nature", "mode", "montant", "numero_recu"]],
                 hide_index=True, width="stretch",
                 column_config={"date": "Date", "nom": "Donateur", "nature": "Nature", "mode": "Mode",
                                "montant": st.column_config.NumberColumn("Montant", format="%.2f €"),
                                "numero_recu": "Reçu n°"})
    par_saison = dons.groupby("saison")["montant"].agg(["count", "sum"]).reset_index()
    st.caption(" · ".join(f"{libelle_exercice(int(r.saison))} : {int(r['count'])} don(s), {eur(r['sum'])}"
                          for _, r in par_saison.iterrows() if r.saison))
    st.caption("Rappel : chaque année, l'association déclare aux impôts le montant total des dons ayant donné lieu à "
               "un reçu et le nombre de reçus émis (art. 222 bis du CGI).")
    if not peut_saisir():
        return
    choix = st.selectbox("Don", dons["id"].tolist(),
                         format_func=lambda i: f"{dons[dons['id'] == i].iloc[0]['date']} – "
                                               f"{dons[dons['id'] == i].iloc[0]['nom']} – "
                                               f"{eur(dons[dons['id'] == i].iloc[0]['montant'])}")
    r = dons[dons["id"] == choix].iloc[0].to_dict()
    deja = bool(str(r["numero_recu"]).strip())
    if st.button("Éditer un duplicata du reçu" if deja else "Émettre le reçu fiscal", type="primary"):
        if not str(r["adresse"]).strip():
            st.error("L'adresse du donateur manque : complétez-la dans le Google Sheets (onglet « dons »).")
            return
        numero = r["numero_recu"] if deja else prochain_numero("DON", metier.lire_date(r["date"]).year)
        pdf = _pdf(r, numero, deja)
        if not deja:
            brut = charger("dons").copy()
            brut.loc[brut["id"] == choix, "numero_recu"] = numero
            backend().remplacer("dons", brut)
            lieu = ranger_fichier("Reçus fiscaux", f"{numero}_{r['nom']}.pdf".replace(" ", "_"), pdf, "application/pdf")
            enregistrer_document("Reçu fiscal", numero, r["nom"], "Don", r["montant"], lieu)
            journaliser("don", f"reçu {numero} émis")
            rafraichir()
        st.download_button(f"Télécharger {numero}" + (" (duplicata)" if deja else ""), pdf, file_name=f"{numero}.pdf",
                           mime="application/pdf")
