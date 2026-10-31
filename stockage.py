"""Couche de stockage : Google Sheets + Google Drive en production, fichier Excel local pour les essais.

Même principe que le logiciel du Comité des Fêtes : toutes les tables sont des onglets d'un même
classeur Google Sheets appartenant au compte du club ; les fichiers produits (factures, reçus,
rapports, relevés, justificatifs, sauvegardes) vont dans les sous-dossiers Drive du club.
"""
from __future__ import annotations

import io
import json
import os
import threading
from pathlib import Path

import pandas as pd

from referentiel import TABLES, DOSSIERS_DRIVE

SCOPES = ["https://www.googleapis.com/auth/drive.file"]


# ------------------------------------------------------------------ configuration
def lire_config() -> dict:
    """Lit la configuration dans st.secrets (section [club]) puis dans les variables d'environnement."""
    conf = {}
    try:
        import streamlit as st
        if "club" in st.secrets:
            conf.update({k: st.secrets["club"][k] for k in st.secrets["club"]})
    except Exception:
        pass
    for cle in ("backend", "spreadsheet_id", "dossiers", "google_credentials", "admins", "dossier_local"):
        env = os.environ.get("CLUB_" + cle.upper())
        if env and cle not in conf:
            conf[cle] = env
    conf.setdefault("backend", "local")
    for cle in ("dossiers", "google_credentials"):
        if isinstance(conf.get(cle), str) and conf[cle].strip().startswith("{"):
            conf[cle] = json.loads(conf[cle])
    if isinstance(conf.get("admins"), str):
        conf["admins"] = [a.strip().lower() for a in conf["admins"].split(",") if a.strip()]
    return conf


def creer_backend(conf: dict) -> "Backend":
    if conf.get("backend") == "google":
        return BackendGoogle(conf)
    return BackendLocal(conf.get("dossier_local", "donnees_locales"))


def credentials_google(info: dict):
    """Jeton du compte Google de l'association (recommandé) ou compte de service."""
    if info.get("type") == "service_account":
        from google.oauth2.service_account import Credentials
        return Credentials.from_service_account_info(info, scopes=SCOPES)
    from google.oauth2.credentials import Credentials
    return Credentials.from_authorized_user_info(info, scopes=SCOPES)


# ------------------------------------------------------------------ interface commune
class Backend:
    nom = ""

    def lire(self, table: str) -> pd.DataFrame: ...
    def ajouter(self, table: str, lignes: list[dict]) -> None: ...
    def remplacer(self, table: str, df: pd.DataFrame) -> None: ...
    def supprimer_ids(self, table: str, ids: list[str]) -> int: ...
    def enregistrer_fichier(self, dossier: str, nom: str, contenu: bytes, mime: str) -> str: ...
    def lire_fichier(self, reference: str) -> bytes: ...
    def preparer_dossiers(self, noms: list[str]) -> dict[str, str]: ...

    @staticmethod
    def _vide(table: str) -> pd.DataFrame:
        return pd.DataFrame(columns=TABLES[table])

    @staticmethod
    def _ligne(table: str, d: dict) -> list:
        valeurs = []
        for col in TABLES[table]:
            v = d.get(col, "")
            if v is None or (isinstance(v, float) and pd.isna(v)):
                v = ""
            if hasattr(v, "item"):  # types numpy -> python
                v = v.item()
            valeurs.append(v)
        return valeurs


# ------------------------------------------------------------------ mode local (essais)
class BackendLocal(Backend):
    nom = "Fichier local (mode essai)"
    _verrou = threading.Lock()

    def __init__(self, dossier: str):
        self.racine = Path(dossier)
        self.racine.mkdir(parents=True, exist_ok=True)
        for d in DOSSIERS_DRIVE:
            (self.racine / d).mkdir(exist_ok=True)
        self.fichier = self.racine / "base_locale.xlsx"
        if not self.fichier.exists():
            with pd.ExcelWriter(self.fichier, engine="openpyxl") as w:
                for t in TABLES:
                    self._vide(t).to_excel(w, sheet_name=t, index=False)

    def _tout(self) -> dict[str, pd.DataFrame]:
        feuilles = pd.read_excel(self.fichier, sheet_name=None, dtype=str, keep_default_na=False)
        return {t: feuilles.get(t, self._vide(t)) for t in TABLES}

    def _ecrire(self, tout: dict[str, pd.DataFrame]) -> None:
        tmp = self.fichier.with_suffix(".tmp.xlsx")
        with pd.ExcelWriter(tmp, engine="openpyxl") as w:
            for t, df in tout.items():
                df.reindex(columns=TABLES[t]).to_excel(w, sheet_name=t, index=False)
        tmp.replace(self.fichier)

    def lire(self, table):
        with self._verrou:
            return self._tout()[table].reindex(columns=TABLES[table]).fillna("").astype(str)

    def ajouter(self, table, lignes):
        if not lignes:
            return
        with self._verrou:
            tout = self._tout()
            neuf = pd.DataFrame([self._ligne(table, l) for l in lignes], columns=TABLES[table])
            tout[table] = pd.concat([tout[table], neuf.astype(str)], ignore_index=True)
            self._ecrire(tout)

    def remplacer(self, table, df):
        with self._verrou:
            tout = self._tout()
            tout[table] = df.reindex(columns=TABLES[table]).fillna("").astype(str)
            self._ecrire(tout)

    def supprimer_ids(self, table, ids):
        with self._verrou:
            tout = self._tout()
            avant = len(tout[table])
            tout[table] = tout[table][~tout[table]["id"].isin(ids)]
            self._ecrire(tout)
            return avant - len(tout[table])

    def enregistrer_fichier(self, dossier, nom, contenu, mime):
        (self.racine / dossier).mkdir(exist_ok=True)
        chemin = self.racine / dossier / nom
        chemin.write_bytes(contenu)
        return str(chemin)

    def lire_fichier(self, reference):
        return Path(reference).read_bytes()

    def preparer_dossiers(self, noms):
        for n in noms:
            (self.racine / n).mkdir(exist_ok=True)
        return {n: str(self.racine / n) for n in noms}


# ------------------------------------------------------------------ mode Google
class BackendGoogle(Backend):
    nom = "Google Drive de l'association"

    def __init__(self, conf: dict):
        import gspread

        info = conf["google_credentials"]
        if isinstance(info, str):
            info = json.loads(info) if info.strip().startswith("{") else json.loads(Path(info).read_text())
        self.creds = credentials_google(dict(info))
        self.gc = gspread.authorize(self.creds)
        self.classeur = self.gc.open_by_key(conf["spreadsheet_id"])
        self.dossiers = dict(conf.get("dossiers") or {})
        self._onglets = {}

    @property
    def drive(self):
        """Client Drive neuf à chaque appel : la connexion HTTP (httplib2) ne se partage pas entre les sessions
        de l'application et se coupe après un temps d'inactivité (erreur SSL à l'envoi d'un fichier)."""
        from googleapiclient.discovery import build
        import google_auth_httplib2
        import httplib2
        http = google_auth_httplib2.AuthorizedHttp(self.creds, http=httplib2.Http(timeout=120))
        return build("drive", "v3", http=http, cache_discovery=False)

    def _onglet(self, table: str):
        if table not in self._onglets:
            import gspread
            try:
                ws = self.classeur.worksheet(table)
            except gspread.WorksheetNotFound:
                ws = self.classeur.add_worksheet(table, rows=1000, cols=len(TABLES[table]))
                ws.update([TABLES[table]], "A1")
            self._onglets[table] = ws
        return self._onglets[table]

    def lire(self, table):
        valeurs = self._onglet(table).get(value_render_option="UNFORMATTED_VALUE")
        if not valeurs:
            return self._vide(table)
        entete, lignes = valeurs[0], valeurs[1:]
        lignes = [l + [""] * (len(entete) - len(l)) for l in lignes]
        df = pd.DataFrame(lignes, columns=entete)
        return df.reindex(columns=TABLES[table]).fillna("").astype(str)

    def ajouter(self, table, lignes):
        if lignes:
            self._onglet(table).append_rows([self._ligne(table, l) for l in lignes],
                                            value_input_option="RAW", insert_data_option="INSERT_ROWS")

    def remplacer(self, table, df):
        ws = self._onglet(table)
        df = df.reindex(columns=TABLES[table]).fillna("")
        ws.clear()
        ws.update([TABLES[table]] + [self._ligne(table, r) for r in df.to_dict("records")],
                  "A1", value_input_option="RAW")

    def supprimer_ids(self, table, ids):
        ws = self._onglet(table)
        col_id = ws.col_values(TABLES[table].index("id") + 1)
        a_supprimer = [i + 1 for i, v in enumerate(col_id) if i > 0 and str(v) in set(ids)]
        for numero in sorted(a_supprimer, reverse=True):
            ws.delete_rows(numero)
        return len(a_supprimer)

    def enregistrer_fichier(self, dossier, nom, contenu, mime):
        from googleapiclient.http import MediaIoBaseUpload
        parent = self.dossiers.get(dossier)
        meta = {"name": nom, **({"parents": [parent]} if parent else {})}
        media = MediaIoBaseUpload(io.BytesIO(contenu), mimetype=mime, resumable=True, chunksize=5 * 1024 * 1024)
        f = self.drive.files().create(body=meta, media_body=media, fields="id,webViewLink").execute(num_retries=4)
        return f.get("webViewLink", f["id"])

    @staticmethod
    def _id_depuis(reference: str) -> str:
        """Accepte un identifiant Drive ou un lien https://drive.google.com/…/d/<id>/…"""
        ref = str(reference).strip()
        if "/d/" in ref:
            return ref.split("/d/")[1].split("/")[0]
        if "id=" in ref:
            return ref.split("id=")[1].split("&")[0]
        return ref

    def lire_fichier(self, reference):
        from googleapiclient.http import MediaIoBaseDownload
        buf = io.BytesIO()
        requete = self.drive.files().get_media(fileId=self._id_depuis(reference))
        telechargement = MediaIoBaseDownload(buf, requete)
        fini = False
        while not fini:
            _, fini = telechargement.next_chunk(num_retries=4)
        return buf.getvalue()

    def preparer_dossiers(self, noms):
        """Crée (ou retrouve) le dossier racine du club et ses sous-dossiers. Renvoie {nom: id}.

        Les dossiers sont créés par l'application : l'autorisation « drive.file » lui suffit
        pour y écrire, sans aucun accès au reste du Drive."""
        racine = self.dossiers.get("_racine")
        if not racine:
            nom_racine = "Sensei Karaté Do — Gestion"
            trouves = self.drive.files().list(
                q=f"name = '{nom_racine}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false",
                fields="files(id)").execute(num_retries=4).get("files", [])
            racine = trouves[0]["id"] if trouves else self.drive.files().create(
                body={"name": nom_racine, "mimeType": "application/vnd.google-apps.folder"}, fields="id").execute(num_retries=4)["id"]
        resultat = {"_racine": racine}
        for n in noms:
            if self.dossiers.get(n):
                resultat[n] = self.dossiers[n]
                continue
            trouves = self.drive.files().list(
                q=(f"name = '{n}' and '{racine}' in parents and mimeType = 'application/vnd.google-apps.folder' "
                   "and trashed = false"), fields="files(id)").execute(num_retries=4).get("files", [])
            resultat[n] = trouves[0]["id"] if trouves else self.drive.files().create(
                body={"name": n, "mimeType": "application/vnd.google-apps.folder", "parents": [racine]},
                fields="id").execute(num_retries=4)["id"]
        self.dossiers.update(resultat)
        return resultat
