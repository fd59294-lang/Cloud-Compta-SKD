"""Adhérents : fiche unique par licence FFKaraté, inscription par saison, paiements, reçus, factures, tarifs."""
from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

import adherents as A
import documents as D
import metier
from commun import (backend, categorie_par_code, charger, club, enregistrer_document, eur, exercice_courant,
                    exercices_disponibles, flash, journaliser, lecture_seule, libelle_exercice, logo, mois_debut,
                    parametre, ecrire_parametres, peut_saisir, prochain_numero, rafraichir, ranger_fichier,
                    utilisateur, est_admin)
from referentiel import MODES_PAIEMENT


def _choisir_saison(cle: str) -> int:
    saisons = sorted(set(exercices_disponibles()) | {exercice_courant(), exercice_courant() + 1}, reverse=True)
    return st.selectbox("Saison", saisons, index=saisons.index(exercice_courant()), format_func=libelle_exercice,
                        key=cle)


def _debut_saison(saison: int) -> date:
    return metier.bornes_exercice(saison, mois_debut())[0]


# ====================================================================== adhérents et inscriptions
def page_adherents():
    st.header("Adhérents et inscriptions")
    saison = _choisir_saison("saison_adherents")
    onglets = st.tabs(["➕ Inscrire / réinscrire", "📋 Inscrits de la saison", "👤 Fiche adhérent"])
    with onglets[0]:
        _inscription(saison)
    with onglets[1]:
        _liste_saison(saison)
    with onglets[2]:
        _fiche()


def _inscription(saison: int):
    if lecture_seule():
        return
    st.caption("Saisissez le numéro de licence FFKaraté : s'il est connu, la fiche est reprise telle quelle "
               "(réinscription sans ressaisie) ; sinon, une nouvelle fiche est créée.")
    c1, c2 = st.columns([2, 1])
    licence = c1.text_input("N° de licence FFKaraté", key="licence_recherchee")
    if c2.button("Rechercher", width="stretch"):
        st.session_state["licence_validee"] = licence
    lic = st.session_state.get("licence_validee", "")
    if not lic or A.normaliser_licence(lic) != A.normaliser_licence(licence):
        return
    adh = charger("adherents")
    fiche = A.trouver_par_licence(adh, lic)
    ins = charger("inscriptions")
    if fiche:
        st.success(f"🔁 Licence connue : **{A.nom_complet(fiche)}** — réinscription pour la saison "
                   f"{libelle_exercice(saison)}.")
        deja = ins[(ins["adherent_id"] == fiche["id"]) & (metier.nombres(ins["saison"]).fillna(0).astype(int) == saison)]
        if not deja.empty:
            st.info("Cet adhérent est déjà inscrit pour cette saison. Les paiements se saisissent dans « Paiements et reçus ».")
            return
    else:
        st.info("🆕 Nouvelle licence : complétez la fiche.")
        fiche = {"id": "", "licence": A.normaliser_licence(lic)}
    with st.form("inscription"):
        st.markdown("**Fiche**")
        c1, c2, c3 = st.columns(3)
        nom = c1.text_input("Nom", value=fiche.get("nom", ""))
        prenom = c2.text_input("Prénom", value=fiche.get("prenom", ""))
        naissance = c3.date_input("Date de naissance", value=metier.lire_date(fiche.get("date_naissance")),
                                  min_value=date(1930, 1, 1), max_value=date.today(), format="DD/MM/YYYY")
        c4, c5 = st.columns(2)
        responsable = c4.text_input("Responsable légal (si mineur)", value=fiche.get("responsable_legal", ""))
        famille = c5.text_input("Famille (même nom pour les membres d'une famille)",
                                value=fiche.get("famille", "") or fiche.get("nom", ""),
                                help="Sert à appliquer la réduction pour le 2e membre d'une même famille.")
        c6, c7 = st.columns(2)
        email = c6.text_input("E-mail", value=fiche.get("email", ""))
        tel = c7.text_input("Téléphone", value=fiche.get("telephone", ""))
        adresse = st.text_input("Adresse", value=fiche.get("adresse", ""))
        st.markdown("**Inscription de la saison**")
        tarifs = A.tarifs_saison(charger("tarifs"), saison)
        noms_tarifs = tarifs["nom"].tolist() or ["Cotisation"]
        suggere = A.tarif_suggere(charger("tarifs"), saison, naissance, _debut_saison(saison))
        c8, c9, c10 = st.columns(3)
        tarif = c8.selectbox("Tarif", noms_tarifs, index=noms_tarifs.index(suggere) if suggere in noms_tarifs else 0,
                             help="Proposé d'après l'âge au début de la saison.")
        premiere = not fiche.get("id") or not A.deja_inscrit_avant(ins, fiche["id"], saison)
        frais_def = float(parametre("frais_adhesion", "0") or 0) if premiere else 0.0
        frais = c9.number_input("Frais d'adhésion (1re saison)", min_value=0.0, step=1.0, value=frais_def,
                                format="%.2f")
        autre = A.membre_famille_deja_inscrit(adh, ins, fiche.get("id", ""), saison) if fiche.get("id") else None
        red_def = float(parametre("reduction_famille", "30") or 0) if autre else 0.0
        reduction = c10.number_input("Réduction famille", min_value=0.0, step=1.0, value=red_def, format="%.2f",
                                     help=f"Déjà inscrit dans la famille : {autre}" if autre else
                                     "À appliquer pour le 2e membre d'une même famille.")
        notes = st.text_input("Notes", value=fiche.get("notes", ""))
        valide = st.form_submit_button("Enregistrer l'inscription", type="primary")
    if not valide:
        return
    if not nom.strip() or not prenom.strip():
        st.error("Le nom et le prénom sont obligatoires.")
        return
    t = tarifs[tarifs["nom"] == tarif]
    cotisation = float(t.iloc[0]["cotisation"]) if not t.empty else 0.0
    valeurs = {"licence": A.normaliser_licence(lic), "nom": nom.strip().upper(), "prenom": prenom.strip(),
               "date_naissance": naissance.isoformat() if naissance else "", "responsable_legal": responsable.strip(),
               "famille": famille.strip().upper(), "email": email.strip(), "telephone": tel.strip(),
               "adresse": adresse.strip(), "notes": notes.strip(), "actif": "oui"}
    if fiche.get("id"):
        brut = charger("adherents").copy()
        for k, v in valeurs.items():
            brut.loc[brut["id"] == fiche["id"], k] = v
        backend().remplacer("adherents", brut)
        adherent_id = fiche["id"]
    else:
        adherent_id = metier.nouvel_id()
        backend().ajouter("adherents", [{**valeurs, "id": adherent_id, "premiere_saison": saison,
                                         "cree_le": metier.maintenant()}])
    total = round(cotisation + frais - reduction, 2)
    backend().ajouter("inscriptions", [{"id": metier.nouvel_id(), "adherent_id": adherent_id, "saison": saison,
                                        "tarif": tarif, "cotisation": cotisation, "frais_adhesion": frais,
                                        "reduction": reduction, "total_du": total,
                                        "date_inscription": date.today().isoformat(), "notes": notes.strip(),
                                        "cree_par": utilisateur()}])
    journaliser("inscription", f"{valeurs['nom']} {valeurs['prenom']} ({valeurs['licence']}) – saison {saison}")
    rafraichir()
    st.session_state.pop("licence_validee", None)
    flash(f"Inscription enregistrée : {valeurs['nom']} {valeurs['prenom']} — {eur(total)} à régler. "
          "Saisissez le règlement dans « Paiements et reçus ».")
    st.rerun()


def _liste_saison(saison: int):
    etat = A.etat_saison(charger("adherents"), charger("inscriptions"), charger("paiements"), saison)
    s = A.statistiques_saison(etat, charger("inscriptions"), saison)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Inscrits", s["inscrits"], help=f"dont {s['nouveaux']} nouveaux")
    c2.metric("À jour", s["a_jour"])
    c3.metric("Encaissé", eur(s["encaisse"]))
    c4.metric("Reste à encaisser", eur(s["reste"]))
    if etat.empty:
        st.info("Aucun inscrit pour cette saison.")
        return
    filtre = st.text_input("Filtrer (nom ou licence)", key="filtre_inscrits")
    v = etat
    if filtre:
        f = metier.sans_accent(filtre)
        v = v[v["nom"].map(metier.sans_accent).str.contains(f) | v["licence"].map(metier.sans_accent).str.contains(f)]
    st.dataframe(v[["licence", "nom", "tarif", "total_du", "paye", "reste", "statut"]], hide_index=True,
                 width="stretch",
                 column_config={"licence": "Licence", "nom": "Nom", "tarif": "Tarif",
                                "total_du": st.column_config.NumberColumn("Dû", format="%.2f €"),
                                "paye": st.column_config.NumberColumn("Payé", format="%.2f €"),
                                "reste": st.column_config.NumberColumn("Reste", format="%.2f €"), "statut": "Statut"})
    if est_admin():
        st.caption("Supprimer une inscription (erreur de saisie) n'est possible que si aucun paiement n'y est rattaché.")
        sans_paiement = etat[etat["paye"] == 0]
        if not sans_paiement.empty:
            c1, c2 = st.columns([3, 1])
            choix = c1.selectbox("Inscription à supprimer", sans_paiement["inscription_id"].tolist(),
                                 format_func=lambda i: sans_paiement[sans_paiement["inscription_id"] == i].iloc[0]["nom"])
            if c2.button("Supprimer l'inscription"):
                backend().supprimer_ids("inscriptions", [choix])
                journaliser("inscription", f"suppression {choix}")
                rafraichir()
                st.rerun()


def _fiche():
    adh = charger("adherents")
    if adh.empty:
        st.info("Aucun adhérent.")
        return
    adh = adh.assign(libelle=adh.apply(lambda r: f"{A.nom_complet(r)} – licence {r['licence']}", axis=1))
    choix = st.selectbox("Adhérent", adh.sort_values("libelle")["id"].tolist(),
                         format_func=lambda i: adh[adh["id"] == i].iloc[0]["libelle"], key="fiche_adherent")
    a = adh[adh["id"] == choix].iloc[0].to_dict()
    h = A.historique_adherent(choix, charger("inscriptions"), charger("paiements"))
    if not h.empty:
        h["saison"] = h["saison"].map(libelle_exercice)
        st.dataframe(h, hide_index=True, width="stretch",
                     column_config={"saison": "Saison", "tarif": "Tarif",
                                    "total_du": st.column_config.NumberColumn("Dû", format="%.2f €"),
                                    "paye": st.column_config.NumberColumn("Payé", format="%.2f €"),
                                    "reglements": "Règlements"})
    if not peut_saisir():
        st.json({k: a[k] for k in ("licence", "nom", "prenom", "email", "telephone", "adresse")})
        return
    with st.form(f"fiche_{choix}"):
        c1, c2, c3 = st.columns(3)
        licence = c1.text_input("Licence", value=a["licence"])
        nom = c2.text_input("Nom", value=a["nom"])
        prenom = c3.text_input("Prénom", value=a["prenom"])
        c4, c5, c6 = st.columns(3)
        naissance = c4.date_input("Date de naissance", value=metier.lire_date(a["date_naissance"]),
                                  min_value=date(1930, 1, 1), max_value=date.today(), format="DD/MM/YYYY")
        responsable = c5.text_input("Responsable légal", value=a["responsable_legal"])
        famille = c6.text_input("Famille", value=a["famille"])
        c7, c8 = st.columns(2)
        email = c7.text_input("E-mail", value=a["email"])
        tel = c8.text_input("Téléphone", value=a["telephone"])
        adresse = st.text_input("Adresse", value=a["adresse"])
        notes = st.text_input("Notes", value=a["notes"])
        actif = st.checkbox("Adhérent actif", value=str(a["actif"]).strip() == "" or metier.oui(a["actif"]))
        if st.form_submit_button("Enregistrer la fiche", type="primary"):
            autre = A.trouver_par_licence(charger("adherents"), licence)
            if autre and autre["id"] != choix:
                st.error(f"Cette licence appartient déjà à {A.nom_complet(autre)}.")
                return
            brut = charger("adherents").copy()
            for k, v in {"licence": A.normaliser_licence(licence), "nom": nom.strip().upper(), "prenom": prenom.strip(),
                         "date_naissance": naissance.isoformat() if naissance else "",
                         "responsable_legal": responsable.strip(), "famille": famille.strip().upper(),
                         "email": email.strip(), "telephone": tel.strip(), "adresse": adresse.strip(),
                         "notes": notes.strip(), "actif": "oui" if actif else "non"}.items():
                brut.loc[brut["id"] == choix, k] = v
            backend().remplacer("adherents", brut)
            journaliser("adhérent", f"fiche modifiée : {nom} {prenom}")
            rafraichir()
            flash("Fiche enregistrée.")
            st.rerun()


# ====================================================================== paiements et reçus
def page_paiements():
    st.header("Paiements et reçus")
    saison = _choisir_saison("saison_paiements")
    etat = A.etat_saison(charger("adherents"), charger("inscriptions"), charger("paiements"), saison)
    if etat.empty:
        st.info("Aucun inscrit pour cette saison : inscrivez d'abord l'adhérent (page « Adhérents et inscriptions »).")
        return
    onglets = st.tabs(["💰 Enregistrer un paiement", "🧾 Reçus et factures", "⏳ Restes à encaisser"])
    with onglets[0]:
        _enregistrer_paiement(etat, saison)
    with onglets[1]:
        _documents_adherent(etat, saison)
    with onglets[2]:
        reste = etat[etat["reste"] > 0]
        if reste.empty:
            st.success("Toutes les cotisations de la saison sont réglées.")
        else:
            st.dataframe(reste[["licence", "nom", "responsable_legal", "total_du", "paye", "reste", "statut"]],
                         hide_index=True, width="stretch",
                         column_config={"total_du": st.column_config.NumberColumn("Dû", format="%.2f €"),
                                        "paye": st.column_config.NumberColumn("Payé", format="%.2f €"),
                                        "reste": st.column_config.NumberColumn("Reste", format="%.2f €"),
                                        "licence": "Licence", "nom": "Nom", "responsable_legal": "Responsable",
                                        "statut": "Statut"})
            st.caption(f"Total restant : **{eur(reste['reste'].sum())}**")


def _etiquette(etat, i):
    r = etat[etat["inscription_id"] == i].iloc[0]
    return f"{r['nom']} – {r['licence']} – reste {eur(r['reste'])}"


def _enregistrer_paiement(etat: pd.DataFrame, saison: int):
    if lecture_seule():
        return
    ordre = etat.sort_values(["reste", "nom"], ascending=[False, True])
    choix = st.selectbox("Adhérent", ordre["inscription_id"].tolist(), format_func=lambda i: _etiquette(etat, i),
                         key="paiement_inscription")
    r = etat[etat["inscription_id"] == choix].iloc[0]
    c1, c2, c3 = st.columns(3)
    c1.metric("Dû", eur(r["total_du"]))
    c2.metric("Déjà payé", eur(r["paye"]))
    c3.metric("Reste", eur(r["reste"]))
    with st.form(f"paiement_{choix}", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        montant = c1.number_input("Montant reçu (€)", min_value=0.0, step=1.0, value=float(r["reste"]), format="%.2f")
        mode = c2.selectbox("Mode", MODES_PAIEMENT)
        jour = c3.date_input("Date du paiement", value=date.today(), format="DD/MM/YYYY")
        payeur = st.text_input("Payé par", value=r["responsable_legal"] or r["nom"])
        c4, c5 = st.columns(2)
        compta = c4.checkbox("Ajouter l'écriture en comptabilité", value=True)
        recu = c5.checkbox("Générer le reçu PDF", value=True)
        valide = st.form_submit_button("Enregistrer le paiement", type="primary")
    if not valide:
        return
    if montant <= 0:
        st.error("Montant invalide.")
        return
    paiement_id = metier.nouvel_id()
    numero, pdf, lieu, op_id = "", None, "", ""
    if recu:
        numero = prochain_numero("REC", jour.year)
        pdf = _pdf_recu(r, numero, payeur, montant, mode, jour, saison, deja_paye=r["paye"])
        lieu = ranger_fichier("Factures et reçus", f"{numero}_{r['nom']}.pdf".replace(" ", "_"), pdf, "application/pdf")
        enregistrer_document("Reçu de paiement", numero, r["nom"], f"Cotisation {libelle_exercice(saison)}", montant,
                             lieu)
    if compta:
        op = metier.nouvelle_operation(jour, "Recette", categorie_par_code("756"),
                                       f"Cotisation {libelle_exercice(saison)} – {r['nom']}", montant,
                                       "Espèces" if mode == "Espèces" else "Banque", mode, payeur, numero,
                                       f"Licence {r['licence']}", utilisateur(), mois_debut(),
                                       origine=f"paiement:{paiement_id}")
        op_id = op["id"]
        backend().ajouter("operations", [op])
    backend().ajouter("paiements", [{"id": paiement_id, "inscription_id": choix, "adherent_id": r["adherent_id"],
                                     "saison": saison, "date": jour.isoformat(), "montant": round(montant, 2),
                                     "mode": mode, "payeur": payeur.strip(), "operation_id": op_id, "recu": numero,
                                     "saisi_par": utilisateur(), "saisi_le": metier.maintenant()}])
    journaliser("paiement", f"{r['nom']} : {montant} € ({mode})" + (f" – reçu {numero}" if numero else ""))
    rafraichir()
    st.success(f"Paiement de {eur(montant)} enregistré pour {r['nom']}."
               + (" Écriture ajoutée en comptabilité." if compta else "") + (f" Reçu {numero}." if numero else ""))
    if pdf:
        st.download_button(f"Télécharger le reçu {numero}", pdf, file_name=f"{numero}.pdf", mime="application/pdf",
                           type="primary")


def _detail(r, deja_paye: float, montant: float) -> list:
    detail = [(f"Cotisation – {r['tarif']}", float(r["cotisation"]))]
    if float(r["frais_adhesion"]):
        detail.append(("Frais d'adhésion (1re saison)", float(r["frais_adhesion"])))
    if float(r["reduction"]):
        detail.append(("Réduction famille", -float(r["reduction"])))
    if deja_paye:
        detail.append(("Réglé auparavant", -float(deja_paye)))
    detail.append(("Présent règlement", -float(montant)))
    detail.append(("Reste à régler", round(float(r["total_du"]) - float(deja_paye) - float(montant), 2)))
    return detail


def _pdf_recu(r, numero, payeur, montant, mode, jour, saison, deja_paye, duplicata=False) -> bytes:
    return D.recu_paiement(club(), logo(), numero + (" (duplicata)" if duplicata else ""), payeur, r["nom"],
                           r["licence"], r["responsable_legal"], "la cotisation annuelle", montant, mode, jour,
                           _detail(r, deja_paye, montant), libelle_exercice(saison))


def _documents_adherent(etat: pd.DataFrame, saison: int):
    choix = st.selectbox("Adhérent", etat["inscription_id"].tolist(), format_func=lambda i: _etiquette(etat, i),
                         key="documents_inscription")
    r = etat[etat["inscription_id"] == choix].iloc[0]
    pai = charger("paiements")
    pai = pai[pai["inscription_id"] == choix].copy()
    if not pai.empty:
        pai["montant"] = metier.nombres(pai["montant"])
        st.dataframe(pai[["date", "montant", "mode", "payeur", "recu"]], hide_index=True, width="stretch",
                     column_config={"montant": st.column_config.NumberColumn("Montant", format="%.2f €"),
                                    "date": "Date", "mode": "Mode", "payeur": "Payé par", "recu": "Reçu n°"})
    if not peut_saisir():
        return
    c1, c2 = st.columns(2)
    if c1.button("🧾 Générer la facture de la saison", width="stretch"):
        numero = prochain_numero("FAC")
        lignes = [(f"Cotisation {libelle_exercice(saison)} – {r['tarif']}", 1, float(r["cotisation"]))]
        if float(r["frais_adhesion"]):
            lignes.append(("Frais d'adhésion (première saison)", 1, float(r["frais_adhesion"])))
        if float(r["reduction"]):
            lignes.append(("Réduction famille (2e membre)", 1, -float(r["reduction"])))
        a = charger("adherents")
        a = a[a["id"] == r["adherent_id"]].iloc[0]
        destinataire = r["responsable_legal"] or r["nom"]
        pdf = D.facture(club(), logo(), numero, destinataire, a["adresse"], a["email"], lignes,
                        deja_regle=float(r["paye"]),
                        objet=f"Inscription de {r['nom']} (licence {r['licence']}) – saison {libelle_exercice(saison)}")
        lieu = ranger_fichier("Factures et reçus", f"{numero}_{r['nom']}.pdf".replace(" ", "_"), pdf, "application/pdf")
        enregistrer_document("Facture", numero, destinataire, f"Cotisation {libelle_exercice(saison)}",
                             float(r["total_du"]), lieu)
        journaliser("facture", f"{numero} – {r['nom']}")
        st.download_button(f"Télécharger la facture {numero}", pdf, file_name=f"{numero}.pdf", mime="application/pdf",
                           type="primary")
    if not pai.empty:
        p = c2.selectbox("Reçu à rééditer", pai["id"].tolist(),
                         format_func=lambda i: f"{pai[pai['id'] == i].iloc[0]['date']} – "
                                               f"{eur(pai[pai['id'] == i].iloc[0]['montant'])} – "
                                               f"{pai[pai['id'] == i].iloc[0]['recu'] or 'sans reçu'}")
        if c2.button("Rééditer / émettre ce reçu", width="stretch"):
            ligne = pai[pai["id"] == p].iloc[0]
            avant = pai[(pd.to_datetime(pai["date"]) < pd.to_datetime(ligne["date"]))]["montant"].sum()
            numero = ligne["recu"] or prochain_numero("REC", pd.to_datetime(ligne["date"]).year)
            pdf = _pdf_recu(r, numero, ligne["payeur"], float(ligne["montant"]), ligne["mode"],
                            pd.to_datetime(ligne["date"]).date(), saison, avant, duplicata=bool(ligne["recu"]))
            if not ligne["recu"]:
                brut = charger("paiements").copy()
                brut.loc[brut["id"] == p, "recu"] = numero
                backend().remplacer("paiements", brut)
                lieu = ranger_fichier("Factures et reçus", f"{numero}_{r['nom']}.pdf".replace(" ", "_"), pdf,
                                      "application/pdf")
                enregistrer_document("Reçu de paiement", numero, r["nom"], f"Cotisation {libelle_exercice(saison)}",
                                     float(ligne["montant"]), lieu)
                rafraichir()
            st.download_button(f"Télécharger le reçu {numero}", pdf, file_name=f"{numero}.pdf", mime="application/pdf",
                               type="primary")


# ====================================================================== tarifs
def page_tarifs():
    st.header("Tarifs")
    saison = _choisir_saison("saison_tarifs")
    tous = charger("tarifs")
    propres = tous[metier.nombres(tous["saison"]).fillna(0).astype(int) == saison] if not tous.empty else tous
    if propres.empty:
        base = A.tarifs_saison(tous, saison)
        st.info("Pas encore de tarifs pour cette saison : ceux de la saison précédente sont proposés ci-dessous. "
                "Enregistrez-les (éventuellement modifiés) pour les fixer.")
        propres = base[["nom", "age_min", "age_max", "cotisation", "dont_licence"]].assign(saison=saison) \
            if not base.empty else pd.DataFrame(columns=["saison", "nom", "age_min", "age_max", "cotisation", "dont_licence"])
    vue = propres[["nom", "age_min", "age_max", "cotisation", "dont_licence"]].copy()
    for c in ("age_min", "age_max", "cotisation", "dont_licence"):
        vue[c] = metier.nombres(vue[c])
    edite = st.data_editor(vue, num_rows="dynamic", hide_index=True, width="stretch",
                           disabled=not est_admin(),
                           column_config={"nom": "Tarif", "age_min": st.column_config.NumberColumn("Âge mini", format="%d"),
                                          "age_max": st.column_config.NumberColumn("Âge maxi", format="%d"),
                                          "cotisation": st.column_config.NumberColumn("Cotisation totale", format="%.2f €"),
                                          "dont_licence": st.column_config.NumberColumn("dont licence FFK", format="%.2f €")})
    c1, c2 = st.columns(2)
    frais = c1.number_input("Frais d'adhésion pour une première inscription (€)", min_value=0.0, step=1.0,
                            value=float(parametre("frais_adhesion", "0") or 0), format="%.2f", disabled=not est_admin())
    red = c2.number_input("Réduction pour le 2e membre d'une même famille (€)", min_value=0.0, step=1.0,
                          value=float(parametre("reduction_famille", "30") or 0), format="%.2f", disabled=not est_admin())
    st.caption("L'âge pris en compte est celui au premier jour de la saison. Les inscriptions déjà enregistrées "
               "gardent le montant de leur saison.")
    if est_admin() and st.button("Enregistrer les tarifs de la saison", type="primary"):
        edite = edite.dropna(subset=["nom"])
        autres = tous[metier.nombres(tous["saison"]).fillna(0).astype(int) != saison] if not tous.empty else tous
        neuf = edite.assign(saison=saison)[["saison", "nom", "age_min", "age_max", "cotisation", "dont_licence"]]
        backend().remplacer("tarifs", pd.concat([autres, neuf.astype(str)], ignore_index=True))
        ecrire_parametres({"frais_adhesion": frais, "reduction_famille": red})
        journaliser("tarifs", f"saison {saison}")
        rafraichir()
        st.success("Tarifs enregistrés.")
