"""Socle partagé par tous les écrans : accès aux données, cache, droits, formatage, numérotation."""
from __future__ import annotations

import json
import threading
from datetime import date, datetime

import pandas as pd
import streamlit as st

import metier
from referentiel import (CATEGORIES_DEFAUT, DOSSIERS_DRIVE, PARAMETRES_CLUB, REDUCTION_FAMILLE_DEFAUT,
                         ROLES_ADMIN, ROLES_SAISIE, TARIF_BENEVOLE, TARIFS_DEFAUT, FRAIS_ADHESION_DEFAUT)
from stockage import creer_backend, lire_config

_VERROU_NUMEROS = threading.Lock()


# ====================================================================== socle
@st.cache_resource
def backend():
    b = creer_backend(lire_config())
    # Identifiants des dossiers Drive enregistrés par « Préparer les dossiers » (Paramètres)
    try:
        p = b.lire("parametres")
        brut = p.loc[p["cle"] == "dossiers_drive", "valeur"]
        if len(brut) and str(brut.iloc[0]).strip().startswith("{") and hasattr(b, "dossiers"):
            for k, v in json.loads(brut.iloc[0]).items():
                b.dossiers.setdefault(k, v)
    except Exception:
        pass
    return b


@st.cache_data(ttl=120, show_spinner=False)
def charger(table: str) -> pd.DataFrame:
    return backend().lire(table)


def rafraichir():
    charger.clear()


def eur(x: float, signe: bool = False) -> str:
    return metier.eur(x, signe)


def parametre(cle: str, defaut: str = "") -> str:
    p = charger("parametres")
    v = p.loc[p["cle"] == cle, "valeur"]
    return str(v.iloc[0]) if len(v) and str(v.iloc[0]) != "" else defaut


def ecrire_parametres(valeurs: dict) -> None:
    p = charger("parametres").copy()
    for cle, valeur in valeurs.items():
        if (p["cle"] == cle).any():
            p.loc[p["cle"] == cle, "valeur"] = str(valeur)
        else:
            p = pd.concat([p, pd.DataFrame([{"cle": cle, "valeur": str(valeur)}])], ignore_index=True)
    backend().remplacer("parametres", p)
    rafraichir()


def ecrire_parametre(cle: str, valeur) -> None:
    ecrire_parametres({cle: valeur})


def club() -> dict:
    """Coordonnées du club pour les documents (en-tête, mentions légales)."""
    return {cle: parametre(cle, defaut) for cle, (_, defaut) in PARAMETRES_CLUB.items()}


def journaliser(action: str, detail: str = "") -> None:
    backend().ajouter("journal", [{"horodatage": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                   "utilisateur": st.session_state.get("email", "?"),
                                   "action": action, "detail": detail}])


def utilisateur() -> str:
    return st.session_state.get("email", "?")


def initialiser_si_vide() -> None:
    """Premier lancement : catégories, tarifs de la saison et paramètres par défaut."""
    modifie = False
    if charger("categories").empty:
        backend().ajouter("categories", [{"code": c, "nom": n, "sens": s, "actif": "oui"}
                                         for c, n, s in CATEGORIES_DEFAUT])
        modifie = True
    if charger("tarifs").empty:
        saison = metier.exercice_de(date.today(), mois_debut())
        backend().ajouter("tarifs", [{"saison": saison, "nom": n, "age_min": a, "age_max": b, "cotisation": c,
                                      "dont_licence": l} for n, a, b, c, l in TARIFS_DEFAUT])
        modifie = True
    # Mises à jour du programme : nouvelles catégories par défaut (ex. 6238) et tarif bénévole
    cats = charger("categories")
    manquantes = [(c, n, s) for c, n, s in CATEGORIES_DEFAUT if c not in set(cats["code"].astype(str))]
    if not cats.empty and manquantes:
        backend().ajouter("categories", [{"code": c, "nom": n, "sens": s, "actif": "oui"} for c, n, s in manquantes])
        modifie = True
    tarifs = charger("tarifs")
    if not tarifs.empty and TARIF_BENEVOLE not in set(tarifs["nom"]):
        saison = int(metier.nombres(tarifs["saison"]).max())
        backend().ajouter("tarifs", [{"saison": saison, "nom": n, "age_min": a, "age_max": b, "cotisation": c,
                                      "dont_licence": l} for n, a, b, c, l in TARIFS_DEFAUT if n == TARIF_BENEVOLE])
        modifie = True
    if parametre("mois_debut_exercice") == "":
        ecrire_parametres({"mois_debut_exercice": 9, "reduction_famille": REDUCTION_FAMILLE_DEFAUT,
                           "frais_adhesion": FRAIS_ADHESION_DEFAUT})
        modifie = True
    if modifie:
        rafraichir()


# ====================================================================== données typées
def operations() -> pd.DataFrame:
    return metier.typer_operations(charger("operations"))


def mois_debut() -> int:
    p = charger("parametres")
    v = p.loc[p["cle"] == "mois_debut_exercice", "valeur"]
    try:
        return int(float(v.iloc[0])) if len(v) and str(v.iloc[0]) else 9
    except ValueError:
        return 9


def exercice_courant() -> int:
    return metier.exercice_de(date.today(), mois_debut())


def libelle_exercice(ex: int) -> str:
    return metier.libelle_exercice(int(ex), mois_debut())


def categories(sens: str | None = None, actives: bool = True) -> list[str]:
    """Libellés « code — nom » des catégories (pour les listes déroulantes)."""
    c = charger("categories")
    if c.empty:
        c = pd.DataFrame(CATEGORIES_DEFAUT, columns=["code", "nom", "sens"]).assign(actif="oui")
    if actives:
        c = c[c["actif"].astype(str).str.lower() != "non"]
    if sens:
        c = c[c["sens"] == sens]
    return [metier.libelle_categorie(r.code, r.nom) for r in c.itertuples()]


def categorie_par_code(code: str) -> str:
    for lib in categories(actives=False):
        if lib.split(" — ")[0] == str(code):
            return lib
    return str(code)


def exercices_disponibles() -> list[int]:
    ops = operations()
    ex = set(ops["exercice"].unique().tolist()) if not ops.empty else set()
    ex.add(exercice_courant())
    return sorted((int(e) for e in ex if e), reverse=True)


# ====================================================================== droits
def peut_saisir() -> bool:
    return st.session_state.get("role") in ROLES_SAISIE


def est_admin() -> bool:
    return st.session_state.get("role") in ROLES_ADMIN


def lecture_seule() -> bool:
    if not peut_saisir():
        st.warning("Votre profil est en lecture seule.")
        return True
    return False


# ====================================================================== fichiers et numérotation
def prochain_numero(prefixe: str, annee: int | None = None) -> str:
    """Numéro chronologique sans trou, par type de document et par année : FAC-2026-001…"""
    annee = annee or date.today().year
    cle = f"compteur_{prefixe}_{annee}"
    with _VERROU_NUMEROS:
        rafraichir()
        n = int(float(parametre(cle, "0") or 0)) + 1
        ecrire_parametre(cle, n)
    return f"{prefixe}-{annee}-{n:03d}"


def ranger_fichier(dossier: str, nom: str, contenu: bytes, mime: str) -> str:
    """Range un fichier dans le Drive du club. Renvoie le lien, ou "" en cas d'échec (signalé)."""
    try:
        return backend().enregistrer_fichier(dossier, nom, contenu, mime)
    except Exception as e:
        st.warning(f"Le fichier n'a pas pu être rangé dans le dossier « {dossier} » du Drive ({e}). "
                   "Téléchargez-le avec le bouton ci-dessous.")
        return ""


def enregistrer_document(type_doc: str, numero: str, destinataire: str, objet: str, montant: float,
                         fichier: str) -> None:
    backend().ajouter("documents", [{"id": metier.nouvel_id(), "type": type_doc, "numero": numero,
                                     "date": date.today().isoformat(), "destinataire": destinataire,
                                     "objet": objet, "montant": round(float(montant or 0), 2), "fichier": fichier,
                                     "cree_par": utilisateur(),
                                     "cree_le": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}])


@st.cache_data(ttl=600, show_spinner=False)
def logo() -> bytes | None:
    ref = parametre("logo_fichier")
    if not ref:
        return None
    try:
        return backend().lire_fichier(ref)
    except Exception:
        return None


def preparer_dossiers() -> dict:
    ids = backend().preparer_dossiers(DOSSIERS_DRIVE)
    ecrire_parametre("dossiers_drive", json.dumps(ids))
    return ids


# ====================================================================== messages
def flash(message: str) -> None:
    """Message de confirmation conservé jusqu'à l'affichage suivant (survit à st.rerun)."""
    st.session_state["flash"] = message


def afficher_flash() -> None:
    if "flash" in st.session_state:
        st.success(st.session_state.pop("flash"))
