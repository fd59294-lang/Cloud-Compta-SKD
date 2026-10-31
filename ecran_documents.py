"""Factures libres, fiches de remboursement de frais, registre des documents émis."""
from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

import documents as D
import metier
from commun import (backend, categorie_par_code, categories, charger, club, enregistrer_document, eur, journaliser,
                    lecture_seule, logo, mois_debut, prochain_numero, rafraichir, ranger_fichier, utilisateur)
from referentiel import MODES_PAIEMENT, SOURCES


def page_documents():
    st.header("Factures et remboursements")
    onglets = st.tabs(["🧾 Facture", "🚗 Remboursement de frais", "🗂️ Documents émis"])
    with onglets[0]:
        _facture()
    with onglets[1]:
        _remboursement()
    with onglets[2]:
        d = charger("documents")
        if d.empty:
            st.info("Aucun document émis.")
        else:
            d = d.copy()
            d["montant"] = metier.nombres(d["montant"])
            d["fichier"] = d["fichier"].where(d["fichier"].astype(str).str.startswith("http"), None)
            st.dataframe(d.iloc[::-1][["date", "type", "numero", "destinataire", "objet", "montant", "fichier"]],
                         hide_index=True, width="stretch",
                         column_config={"montant": st.column_config.NumberColumn("Montant", format="%.2f €"),
                                        "fichier": st.column_config.LinkColumn("Fichier", display_text="📄 ouvrir"),
                                        "date": "Date", "type": "Type", "numero": "Numéro",
                                        "destinataire": "Destinataire", "objet": "Objet"})


def _lignes_vides(colonnes: dict) -> pd.DataFrame:
    return pd.DataFrame([{k: v for k, v in colonnes.items()} for _ in range(3)])


def _facture():
    st.caption("Facture pour une prestation du club (stage, location, vente d'équipement…). Les factures de cotisation "
               "se font depuis « Paiements et reçus ».")
    if lecture_seule():
        return
    c1, c2 = st.columns(2)
    destinataire = c1.text_input("Destinataire", key="fac_dest")
    email = c2.text_input("E-mail", key="fac_mail")
    adresse = st.text_input("Adresse", key="fac_adr")
    c3, c4 = st.columns(2)
    objet = c3.text_input("Objet", key="fac_objet")
    echeance = c4.date_input("À régler avant le", value=None, format="DD/MM/YYYY", key="fac_ech")
    lignes = st.data_editor(_lignes_vides({"designation": "", "quantite": 1.0, "prix_unitaire": 0.0}),
                            num_rows="dynamic", hide_index=True, width="stretch", key="fac_lignes",
                            column_config={"designation": "Désignation",
                                           "quantite": st.column_config.NumberColumn("Quantité", min_value=0.0),
                                           "prix_unitaire": st.column_config.NumberColumn("Prix unitaire (€)",
                                                                                          format="%.2f")})
    lignes = lignes.dropna(subset=["designation"])
    lignes = lignes[lignes["designation"].astype(str).str.strip() != ""]
    total = float((lignes["quantite"].fillna(0) * lignes["prix_unitaire"].fillna(0)).sum())
    st.caption(f"Total : **{eur(total)}**")
    c5, c6 = st.columns(2)
    deja_payee = c5.checkbox("Déjà payée : enregistrer la recette en comptabilité", key="fac_payee")
    cat = c6.selectbox("Catégorie de la recette", categories("Recette"), key="fac_cat", disabled=not deja_payee)
    if not st.button("Générer la facture", type="primary", disabled=lignes.empty or not destinataire.strip()):
        return
    numero = prochain_numero("FAC")
    pdf = D.facture(club(), logo(), numero, destinataire.strip(), adresse.strip(), email.strip(),
                    [(str(r.designation), float(r.quantite or 0), float(r.prix_unitaire or 0))
                     for r in lignes.itertuples()], objet=objet.strip(),
                    echeance=f"{echeance:%d/%m/%Y}" if echeance else "")
    lieu = ranger_fichier("Factures et reçus", f"{numero}_{destinataire.strip()}.pdf".replace(" ", "_"), pdf,
                          "application/pdf")
    enregistrer_document("Facture", numero, destinataire.strip(), objet.strip(), total, lieu)
    if deja_payee:
        backend().ajouter("operations", [metier.nouvelle_operation(
            date.today(), "Recette", cat, f"Facture {numero} – {objet or destinataire}", total, "Banque", "",
            destinataire.strip(), numero, "", utilisateur(), mois_debut(), origine=f"facture:{numero}")])
    journaliser("facture", f"{numero} – {destinataire} – {total} €")
    rafraichir()
    st.success(f"Facture {numero} créée ({eur(total)}).")
    st.download_button(f"Télécharger la facture {numero}", pdf, file_name=f"{numero}.pdf", mime="application/pdf",
                       type="primary")


def _remboursement():
    st.caption("Fiche de remboursement des frais avancés par un bénévole (déplacements, achats…), à signer et à "
               "conserver avec les justificatifs.")
    if lecture_seule():
        return
    c1, c2 = st.columns(2)
    beneficiaire = c1.text_input("Bénéficiaire", key="rf_benef")
    adresse = c2.text_input("Adresse", key="rf_adr")
    objet = st.text_input("Objet", key="rf_objet", placeholder="ex. Déplacement championnat régional")
    lignes = st.data_editor(_lignes_vides({"date": date.today(), "descriptif": "", "montant": 0.0}),
                            num_rows="dynamic", hide_index=True, width="stretch", key="rf_lignes",
                            column_config={"date": st.column_config.DateColumn("Date", format="DD/MM/YYYY"),
                                           "descriptif": "Descriptif de la dépense",
                                           "montant": st.column_config.NumberColumn("Montant (€)", format="%.2f")})
    lignes = lignes.dropna(subset=["descriptif"])
    lignes = lignes[(lignes["descriptif"].astype(str).str.strip() != "") & (lignes["montant"].fillna(0) > 0)]
    total = float(lignes["montant"].sum())
    st.caption(f"Total à rembourser : **{eur(total)}**")
    c3, c4, c5 = st.columns(3)
    mode = c3.selectbox("Mode de remboursement", MODES_PAIEMENT, key="rf_mode")
    compta = c4.checkbox("Enregistrer la dépense en comptabilité", value=True, key="rf_compta")
    cat = c5.selectbox("Catégorie", categories("Dépense"), key="rf_cat",
                       index=categories("Dépense").index(categorie_par_code("6256"))
                       if categorie_par_code("6256") in categories("Dépense") else 0)
    if not st.button("Générer la fiche", type="primary", disabled=lignes.empty or not beneficiaire.strip()):
        return
    numero = prochain_numero("RF")
    pdf = D.remboursement_frais(club(), logo(), numero, beneficiaire.strip(), adresse.strip(), objet.strip(),
                                [(r.date if isinstance(r.date, date) else metier.lire_date(r.date), str(r.descriptif),
                                  float(r.montant)) for r in lignes.itertuples()], mode)
    lieu = ranger_fichier("Factures et reçus", f"{numero}_{beneficiaire.strip()}.pdf".replace(" ", "_"), pdf,
                          "application/pdf")
    enregistrer_document("Remboursement de frais", numero, beneficiaire.strip(), objet.strip(), total, lieu)
    if compta:
        backend().ajouter("operations", [metier.nouvelle_operation(
            date.today(), "Dépense", cat, f"Remboursement de frais {numero} – {beneficiaire.strip()}", total,
            "Espèces" if mode == "Espèces" else SOURCES[0], mode, beneficiaire.strip(), numero, objet.strip(),
            utilisateur(), mois_debut(), origine=f"remboursement:{numero}")])
    journaliser("remboursement", f"{numero} – {beneficiaire} – {total} €")
    rafraichir()
    st.success(f"Fiche {numero} créée ({eur(total)}).")
    st.download_button(f"Télécharger la fiche {numero}", pdf, file_name=f"{numero}.pdf", mime="application/pdf",
                       type="primary")
