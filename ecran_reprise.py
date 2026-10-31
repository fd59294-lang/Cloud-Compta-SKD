"""Reprise des données existantes et imports contrôlés (rien n'est écrit sans validation).

1. Excel d'origine (« Compte SKD .xlsm ») : livre de comptes depuis 2023 et opérations en attente.
2. Version Google Sheets / Apps Script (export .xlsx) : opérations, adhérents, dons, budget, paramètres.
3. Liste d'adhérents (export de l'extranet fédéral ou tableau maison).
4. Modèle d'import générique.
"""
from __future__ import annotations

from datetime import datetime

import pandas as pd
import streamlit as st

import adherents as A
import metier
from commun import (backend, charger, ecrire_parametres, eur, flash, journaliser, lecture_seule, mois_debut,
                    operations, rafraichir, ranger_fichier, utilisateur)

COLS_APERCU = {"date": st.column_config.TextColumn("Date"), "sens": "Sens", "categorie": "Catégorie",
               "libelle": "Libellé", "montant": st.column_config.NumberColumn("Montant", format="%.2f €"),
               "source": "Source", "tiers": "Tiers", "rapproche": "Rapprochée", "statut": "Statut", "notes": "Notes"}


def page_reprise():
    st.header("Reprise des données et import")
    if lecture_seule():
        return
    onglets = st.tabs(["📗 Excel d'origine (.xlsm)", "🟩 Version Google Sheets", "🥋 Liste d'adhérents",
                       "📥 Modèle d'import"])
    with onglets[0]:
        _excel_origine()
    with onglets[1]:
        _apps_script()
    with onglets[2]:
        _liste_adherents()
    with onglets[3]:
        st.download_button("Télécharger le modèle d'import", metier.modele_import_excel(),
                           file_name="modele_import_sensei.xlsx")
        fichier = st.file_uploader("Fichier rempli (.xlsx)", type=["xlsx"], key="modele")
        if fichier:
            ops, erreurs = metier.convertir_modele(fichier.getvalue(), charger("categories"), utilisateur(),
                                                   mois_debut(), metier.empreintes_existantes(operations()))
            for e in erreurs:
                st.warning(e)
            _apercu_et_import(ops, fichier, "modele")


def _apercu_et_import(ops: pd.DataFrame, fichier, cle: str, attente: pd.DataFrame | None = None) -> bool:
    if ops.empty:
        st.warning("Aucune opération exploitable dans ce fichier.")
        return False
    # Une ligne déjà reprise mais pointée depuis dans le fichier : on reporte seulement le pointage.
    existantes = operations()
    non_pointees = {metier.empreinte(r.date, r.montant, r.sens, r.libelle): r.id
                    for r in existantes.itertuples() if pd.notna(r.date) and not r.rapproche_b}
    a_pointer = {non_pointees[metier.empreinte(r["date"], r["montant"], r["sens"], r["libelle"])]: r.get("releve", "")
                 for r in ops.to_dict("records")
                 if r["statut"] == "Doublon" and r["rapproche"] == "oui"
                 and metier.empreinte(r["date"], r["montant"], r["sens"], r["libelle"]) in non_pointees}
    compte = ops["statut"].value_counts()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Nouvelles", int(compte.get("OK", 0)))
    c2.metric("À classer (catégorie inconnue)", int(compte.get("À classer", 0)))
    c3.metric("Déjà présentes", int(compte.get("Doublon", 0)))
    c4.metric("Pointages à reporter", len(a_pointer),
              help="Lignes déjà reprises, pointées depuis dans le fichier : seul le pointage est mis à jour.")
    t = metier.typer_operations(ops.drop(columns=["statut"]))
    s = metier.soldes(t)
    st.info(f"Après import de ces lignes seules : solde banque **{eur(s['banque'])}**, solde pointé "
            f"**{eur(s['pointe'])}**, caisse espèces **{eur(s['caisse'])}**. Comparez avec le fichier d'origine.")
    st.dataframe(ops[list(COLS_APERCU)], hide_index=True, width="stretch", column_config=COLS_APERCU)
    doublons = st.checkbox("Importer quand même les doublons", key=f"doublons_{cle}")
    a_importer = ops if doublons else ops[ops["statut"] != "Doublon"]
    if attente is not None and not attente.empty:
        # Une opération en attente déjà passée au livre (même date, même sens) n'est pas reprise une 2e fois.
        livre = {(str(d), sens) for d, sens in zip(ops["date"], ops["sens"])}
        garder = [(r["date"].isoformat(), "Recette" if r["montant"] > 0 else "Dépense") not in livre
                  for r in attente.to_dict("records")]
        ignorees = len(attente) - sum(garder)
        if ignorees:
            st.caption(f"{ignorees} opération(s) en attente figurent déjà au livre de comptes (même date) : "
                       "elles sont ignorées.")
        attente = attente[garder]
    avec_attente = attente is not None and not attente.empty and st.checkbox(
        f"Importer aussi les {len(attente)} opération(s) en attente", value=True, key=f"attente_{cle}")
    libelle_bouton = f"Importer {len(a_importer)} opération(s)" + (
        f" et reporter {len(a_pointer)} pointage(s)" if a_pointer else "")
    if not st.button(libelle_bouton, type="primary", disabled=a_importer.empty and not a_pointer,
                     key=f"importer_{cle}"):
        return False
    if a_pointer:
        brut = charger("operations").copy()
        if "releve" not in brut:
            brut["releve"] = ""
        for i, rel in a_pointer.items():
            brut.loc[brut["id"] == i, ["rapproche", "releve"]] = ["oui", rel or ""]
        backend().remplacer("operations", brut)
    if not a_importer.empty:
        backend().ajouter("operations", a_importer.drop(columns=["statut"]).to_dict("records"))
    if avec_attente:
        backend().ajouter("attente", [{
            "id": metier.nouvel_id(), "date": r["date"].isoformat(), "sens": "Recette" if r["montant"] > 0 else "Dépense",
            "categorie": metier.trouver_categorie(r["categorie"], "Recette" if r["montant"] > 0 else "Dépense",
                                                  charger("categories"))[0],
            "libelle": r["notes"] or r["categorie"], "montant": abs(r["montant"]),
            "source": "Espèces" if r["especes"] else "Banque", "mode_paiement": "", "tiers": r["tiers"], "notes": "",
            "cree_par": utilisateur(), "cree_le": metier.maintenant()} for r in attente.to_dict("records")])
    ranger_fichier("Imports", f"{datetime.now():%Y-%m-%d_%Hh%M}_{fichier.name}", fichier.getvalue(),
                   fichier.type or "application/octet-stream")
    journaliser("import", f"{len(a_importer)} opérations, {len(a_pointer)} pointages depuis {fichier.name}")
    rafraichir()
    flash(f"{len(a_importer)} opération(s) importée(s), {len(a_pointer)} pointage(s) reporté(s). "
          "Les lignes « à classer » sont à reprendre dans « Opérations ».")
    st.rerun()
    return True


# ------------------------------------------------------------------ 1. Excel d'origine
def _excel_origine():
    st.caption("Le classeur Excel utilisé depuis 2023 : la feuille « Livre de comptes » est reprise ligne par ligne. "
               "La colonne R devient « rapprochée », la colonne E devient « espèces » (hors compte bancaire).")
    fichier = st.file_uploader("Classeur Excel (.xlsm ou .xlsx)", type=["xlsm", "xlsx"], key="xlsm")
    if not fichier:
        return
    with st.spinner("Lecture du classeur…"):
        livre, attente, messages = metier.lire_livre_excel(fichier.getvalue())
    for m in messages:
        st.caption(m)
    if livre.empty:
        return
    ops = metier.convertir_livre(livre, charger("categories"), utilisateur(), mois_debut(),
                                 metier.empreintes_existantes(operations()))
    _apercu_et_import(ops, fichier, "xlsm", attente)


# ------------------------------------------------------------------ 2. version Apps Script
def _apps_script():
    st.caption("Si des données ont été saisies dans la version Google Sheets (Apps Script) : dans ce Google Sheets, "
               "Fichier → Télécharger → Microsoft Excel (.xlsx), puis déposez le fichier ici.")
    fichier = st.file_uploader("Export Excel du Google Sheets", type=["xlsx"], key="apps_script")
    if not fichier:
        return
    feuilles = metier.lire_export_apps_script(fichier.getvalue())
    st.caption("Onglets trouvés : " + ", ".join(feuilles))
    if "Operations_Historique" in feuilles:
        st.subheader("Opérations")
        ops = metier.convertir_operations_apps_script(feuilles["Operations_Historique"], charger("categories"),
                                                      utilisateur(), mois_debut(),
                                                      metier.empreintes_existantes(operations()))
        _apercu_et_import(ops, fichier, "apps_ops")
    if "Membres_Cotisations" in feuilles:
        st.subheader("Adhérents")
        _import_membres_apps_script(feuilles["Membres_Cotisations"])
    if "Dons_Recus" in feuilles:
        st.subheader("Dons")
        _import_dons_apps_script(feuilles["Dons_Recus"])
    if "Configuration" in feuilles:
        st.subheader("Coordonnées du club")
        _import_configuration(feuilles["Configuration"])
    if "Budget" in feuilles:
        st.subheader("Budget")
        b = feuilles["Budget"].dropna(how="all")
        st.dataframe(b, hide_index=True)
        if st.button("Importer le budget", key="imp_budget"):
            lignes = []
            for r in b.to_dict("records"):
                sens = "Recette" if str(r.get("Type", "")).lower().startswith("rec") else "Dépense"
                lignes.append({"exercice": int(metier.nombre(r.get("Exercice"), 0)),
                               "categorie": metier.trouver_categorie(r.get("Categorie"), sens, charger("categories"))[0],
                               "sens": sens, "prevu": metier.nombre(r.get("Montant_Prevu"), 0), "commentaire": "",
                               "maj_le": metier.maintenant()})
            backend().ajouter("budget", lignes)
            journaliser("import", f"budget : {len(lignes)} lignes")
            rafraichir()
            st.success("Budget importé.")


def _cle(c) -> str:
    return metier.sans_accent(c).replace(" ", "_")


def _import_membres_apps_script(df: pd.DataFrame):
    df = df.dropna(how="all")
    df.columns = [_cle(c) for c in df.columns]
    existants = charger("adherents")
    lignes, ins, pai = [], [], []
    for r in df.to_dict("records"):
        licence = A.normaliser_licence(r.get("numero_licence_ffkarate", ""))
        nom_prenom = str(r.get("nom_prenom") or "").strip()
        if not nom_prenom or nom_prenom.lower() == "nan":
            continue
        if licence and A.trouver_par_licence(existants, licence):
            continue
        morceaux = nom_prenom.split(" ", 1)
        aid = metier.nouvel_id()
        d_adh = metier.lire_date(r.get("date_adhesion")) or datetime.now().date()
        saison = metier.exercice_de(d_adh, mois_debut())
        lignes.append({"id": aid, "licence": licence, "nom": morceaux[0].upper(),
                       "prenom": morceaux[1] if len(morceaux) > 1 else "", "date_naissance": "", "responsable_legal": "",
                       "famille": morceaux[0].upper(), "email": str(r.get("email") or ""),
                       "telephone": str(r.get("telephone") or ""), "adresse": str(r.get("adresse") or ""),
                       "premiere_saison": saison, "notes": str(r.get("notes_membre") or ""), "actif": "oui",
                       "cree_le": metier.maintenant()})
        cot = metier.nombre(r.get("cotisation_annuelle"), 0.0)
        frais = metier.nombre(r.get("frais_adhesion"), 0.0)
        iid = metier.nouvel_id()
        ins.append({"id": iid, "adherent_id": aid, "saison": saison, "tarif": "Repris de l'ancienne version",
                    "cotisation": cot, "frais_adhesion": frais, "reduction": 0, "total_du": cot + frais,
                    "date_inscription": d_adh.isoformat(), "notes": "", "cree_par": utilisateur()})
        paye = metier.nombre(r.get("montant_paye"), 0.0) + (frais if str(r.get("statut_adhesion", "")).lower()
                                                              .startswith("pay") else 0.0)
        if paye:
            d_pai = metier.lire_date(r.get("date_paiement")) or d_adh
            pai.append({"id": metier.nouvel_id(), "inscription_id": iid, "adherent_id": aid, "saison": saison,
                        "date": d_pai.isoformat(), "montant": paye, "mode": "Autre", "payeur": "", "operation_id": "",
                        "recu": "", "saisi_par": f"reprise ({utilisateur()})", "saisi_le": metier.maintenant()})
    st.caption(f"{len(lignes)} nouvel(s) adhérent(s), {len(pai)} paiement(s) repris (sans nouvelle écriture "
               "comptable : elles sont déjà dans les opérations).")
    if lignes and st.button(f"Importer {len(lignes)} adhérent(s)", key="imp_membres"):
        backend().ajouter("adherents", lignes)
        backend().ajouter("inscriptions", ins)
        if pai:
            backend().ajouter("paiements", pai)
        journaliser("import", f"{len(lignes)} adhérents (version Google Sheets)")
        rafraichir()
        st.success("Adhérents importés.")


def _import_dons_apps_script(df: pd.DataFrame):
    df = df.dropna(how="all")
    df.columns = [_cle(c) for c in df.columns]
    dons = []
    for r in df.to_dict("records"):
        m = metier.nombre(r.get("montant"))
        if not m or not str(r.get("nom_donateur") or "").strip():
            continue
        dons.append({"id": metier.nouvel_id(), "date": (metier.lire_date(r.get("date_don")) or datetime.now().date()).isoformat(),
                     "nom": str(r.get("nom_donateur")), "adresse": str(r.get("adresse_complete") or ""),
                     "email": str(r.get("email") or ""), "montant": m,
                     "nature": "Don en nature" if "nature" in str(r.get("nature_don", "")).lower() else "Numéraire",
                     "mode": str(r.get("mode_versement") or "Chèque"), "description": "",
                     "numero_recu": str(r.get("numero_recu") or "").replace("nan", ""), "operation_id": "",
                     "saisi_par": f"reprise ({utilisateur()})", "saisi_le": metier.maintenant()})
    st.caption(f"{len(dons)} don(s) trouvés (les numéros de reçus déjà émis sont conservés).")
    if dons and st.button(f"Importer {len(dons)} don(s)", key="imp_dons"):
        backend().ajouter("dons", dons)
        journaliser("import", f"{len(dons)} dons (version Google Sheets)")
        rafraichir()
        st.success("Dons importés.")


CORRESP_CONFIG = {"nom_association": "nom_association", "objet_association": "objet_association", "adresse": "adresse",
                  "code_postal_ville": "code_postal_ville", "ville_signature": "ville_signature", "email": "email",
                  "telephone": "telephone", "iban": "iban", "rna": "rna", "siret": "siret",
                  "affiliation_ffkda": "affiliation", "president": "president", "tresorier": "tresorier",
                  "tarif_adhesion": "frais_adhesion", "mois_debut_exercice": "mois_debut_exercice"}


def _import_configuration(df: pd.DataFrame):
    valeurs = {}
    for r in df.dropna(how="all").itertuples(index=False):
        cle = CORRESP_CONFIG.get(_cle(r[0]).lower())
        if cle and str(r[1]).strip() and str(r[1]) != "nan":
            valeurs[cle] = str(r[1]).strip()
    st.json(valeurs)
    if valeurs and st.button("Reprendre ces coordonnées", key="imp_config"):
        ecrire_parametres(valeurs)
        journaliser("import", "coordonnées du club (version Google Sheets)")
        st.success("Coordonnées reprises (modifiables dans Paramètres).")


# ------------------------------------------------------------------ 3. liste d'adhérents
SYNONYMES_ADH = {"licence": ("licence", "n_licence", "numero_licence", "no_licence", "num_licence", "numero_de_licence",
                             "n°_licence", "numero_licence_ffkarate"),
                 "nom": ("nom", "nom_de_naissance"), "prenom": ("prenom",),
                 "date_naissance": ("date_de_naissance", "naissance", "date_naissance", "ne_le"),
                 "email": ("email", "e-mail", "mail", "courriel", "adresse_mail"),
                 "telephone": ("telephone", "tel", "portable", "mobile"), "adresse": ("adresse",),
                 "responsable_legal": ("responsable_legal", "representant_legal", "parent")}


def _liste_adherents():
    st.caption("Fichier Excel ou CSV avec au moins les colonnes Licence, Nom, Prénom (export de l'extranet fédéral "
               "ou tableau maison). Les licences déjà connues sont ignorées ; aucune inscription n'est créée "
               "(elle se fait saison par saison).")
    fichier = st.file_uploader("Liste d'adhérents", type=["xlsx", "xls", "csv"], key="liste_adh")
    if not fichier:
        return
    try:
        if fichier.name.lower().endswith(".csv"):
            brut = fichier.getvalue()
            texte = brut.decode("utf-8-sig", errors="replace")
            df = pd.read_csv(fichier, sep=";" if texte.count(";") > texte.count(",") else ",", dtype=str,
                             encoding="utf-8-sig", encoding_errors="replace")
        else:
            df = pd.read_excel(fichier, dtype=str)
    except Exception as e:
        st.error(f"Fichier illisible : {e}")
        return
    colonnes = {}
    for cle, syn in SYNONYMES_ADH.items():
        for c in df.columns:
            if _cle(c).lower().replace("°", "") in [s.replace("°", "") for s in syn]:
                colonnes[cle] = c
                break
    if not {"licence", "nom"} <= set(colonnes):
        st.error("Colonnes « Licence » et « Nom » introuvables. Colonnes du fichier : " + ", ".join(df.columns))
        return
    existants = charger("adherents")
    nouveaux = []
    for r in df.to_dict("records"):
        lic = A.normaliser_licence(r.get(colonnes["licence"]))
        nom = str(r.get(colonnes["nom"]) or "").strip()
        if not lic or not nom or nom.lower() == "nan" or A.trouver_par_licence(existants, lic) or \
                lic in {n["licence"] for n in nouveaux}:
            continue
        val = {k: str(r.get(c) or "").strip().replace("nan", "") for k, c in colonnes.items()}
        naissance = metier.lire_date(val.get("date_naissance"))
        nouveaux.append({"id": metier.nouvel_id(), "licence": lic, "nom": nom.upper(), "prenom": val.get("prenom", ""),
                         "date_naissance": naissance.isoformat() if naissance else "",
                         "responsable_legal": val.get("responsable_legal", ""), "famille": nom.upper(),
                         "email": val.get("email", ""), "telephone": val.get("telephone", ""),
                         "adresse": val.get("adresse", ""), "premiere_saison": "", "notes": "", "actif": "oui",
                         "cree_le": metier.maintenant()})
    st.dataframe(pd.DataFrame(nouveaux)[["licence", "nom", "prenom", "date_naissance", "email"]]
                 if nouveaux else pd.DataFrame(), hide_index=True, width="stretch")
    if nouveaux and st.button(f"Importer {len(nouveaux)} adhérent(s)", type="primary", key="imp_liste"):
        backend().ajouter("adherents", nouveaux)
        journaliser("import", f"{len(nouveaux)} adhérents depuis {fichier.name}")
        rafraichir()
        st.success(f"{len(nouveaux)} adhérent(s) importé(s). Inscrivez-les pour la saison dans « Adhérents ».")
