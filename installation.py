"""Installation dans le Drive du club, directement depuis l'application en ligne (aucun PC nécessaire).

Secrets de départ (Streamlit → Settings → Secrets) :

    [auth]  ... (client Google « Application Web » du projet du club)
    [club]
    backend = "installation"
    admins = "senseikaratedo59@gmail.com"

Un administrateur connecté clique « Autoriser l'accès au Drive du club » ; l'application crée le classeur
« Sensei Karaté Do — Données » et le dossier « Sensei Karaté Do — Gestion », puis affiche le bloc [club]
définitif à coller à la place du bloc de départ.

L'adresse de l'application (ex. https://sensei-karate-do-haussy.streamlit.app/) doit figurer dans les
« URI de redirection autorisés » du client « Application Web », en plus de …/oauth2callback.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

SCOPES = ["https://www.googleapis.com/auth/drive.file"]
AUTH_URI = "https://accounts.google.com/o/oauth2/auth"
TOKEN_URI = "https://oauth2.googleapis.com/token"
DOSSIERS = ["Sauvegardes", "Factures et reçus", "Reçus fiscaux", "Rapports", "Relevés bancaires", "Justificatifs",
            "Imports", "Logo"]


# ------------------------------------------------------------------ création dans le Drive (commun au script)
def creer_espace(creds) -> dict:
    """Crée le dossier racine, ses sous-dossiers et le classeur. Renvoie les éléments du bloc [club]."""
    from googleapiclient.discovery import build
    import gspread

    drive = build("drive", "v3", credentials=creds, cache_discovery=False)
    compte = drive.about().get(fields="user(emailAddress)").execute()["user"]["emailAddress"]
    racine = drive.files().create(body={"name": "Sensei Karaté Do — Gestion",
                                        "mimeType": "application/vnd.google-apps.folder"}, fields="id").execute()["id"]
    dossiers = {"_racine": racine}
    for nom in DOSSIERS:
        dossiers[nom] = drive.files().create(body={"name": nom, "mimeType": "application/vnd.google-apps.folder",
                                                   "parents": [racine]}, fields="id").execute()["id"]
    classeur = gspread.authorize(creds).create("Sensei Karaté Do — Données", folder_id=racine)
    return {"compte": compte, "spreadsheet_id": classeur.id, "dossiers": dossiers,
            "google_credentials": json.loads(creds.to_json())}


def bloc_club(res: dict, admins: list[str]) -> str:
    tous = list(dict.fromkeys([res["compte"].lower()] + [a.lower() for a in admins]))
    return "\n".join([
        "[club]",
        'backend = "google"',
        f'spreadsheet_id = "{res["spreadsheet_id"]}"',
        f'admins = "{", ".join(tous)}"',
        f"dossiers = '''{json.dumps(res['dossiers'])}'''",
        f"google_credentials = '''{json.dumps(res['google_credentials'])}'''",
    ])


# ------------------------------------------------------------------ OAuth « Application Web »
def _base(redirect_uri: str) -> str:
    return redirect_uri.rsplit("/oauth2callback", 1)[0].rstrip("/") + "/"


def _etat(secret: str, horodatage: int | None = None) -> str:
    h = int(horodatage if horodatage is not None else time.time())
    sig = hmac.new(secret.encode(), f"installation|{h}".encode(), hashlib.sha256).hexdigest()[:32]
    return f"inst.{h}.{sig}"


def etat_valide(etat: str, secret: str, delai: int = 900) -> bool:
    try:
        prefixe, h, _ = etat.split(".")
        h = int(h)
    except ValueError:
        return False
    return prefixe == "inst" and 0 <= time.time() - h <= delai and hmac.compare_digest(etat, _etat(secret, h))


def url_autorisation(auth: dict, login_hint: str = "") -> str:
    params = {"client_id": auth["client_id"], "redirect_uri": _base(auth["redirect_uri"]),
              "response_type": "code", "scope": " ".join(SCOPES), "access_type": "offline",
              "prompt": "consent", "include_granted_scopes": "true", "state": _etat(auth["cookie_secret"])}
    if login_hint:
        params["login_hint"] = login_hint
    return f"{AUTH_URI}?{urlencode(params)}"


def echanger_code(auth: dict, code: str):
    import httpx
    from google.oauth2.credentials import Credentials

    r = httpx.post(TOKEN_URI, data={"code": code, "client_id": auth["client_id"],
                                    "client_secret": auth["client_secret"],
                                    "redirect_uri": _base(auth["redirect_uri"]),
                                    "grant_type": "authorization_code"}, timeout=30)
    r.raise_for_status()
    t = r.json()
    if not t.get("refresh_token"):
        raise RuntimeError("Google n'a pas fourni de jeton permanent. Recommencez en acceptant toutes les "
                           "autorisations demandées.")
    return Credentials(token=t["access_token"], refresh_token=t["refresh_token"], token_uri=TOKEN_URI,
                       client_id=auth["client_id"], client_secret=auth["client_secret"], scopes=SCOPES)


# ------------------------------------------------------------------ page
def page_installation(conf: dict) -> None:
    import streamlit as st

    auth = {k: st.secrets["auth"][k] for k in ("client_id", "client_secret", "redirect_uri", "cookie_secret")}
    admins = conf.get("admins") or []
    st.title("🥋 Installation dans le Drive du club")

    if "installation" in st.session_state:
        res = st.session_state["installation"]
        st.success(f"Installation terminée dans le Drive de **{res['compte']}** : classeur « Sensei Karaté Do — "
                   "Données » et dossier « Sensei Karaté Do — Gestion » créés.")
        st.markdown(
            "**Dernière étape** : Streamlit → *Manage app* → *Settings* → *Secrets*. Remplacez **tout le bloc "
            "`[club]`** actuel par le bloc ci-dessous (gardez le bloc `[auth]`), puis *Save*. L'application "
            "redémarre et s'ouvre normalement.")
        st.code(bloc_club(res, admins), language="toml")
        st.warning("Ce bloc donne accès aux fichiers du logiciel dans le Drive du club : ne le copiez nulle part "
                   "ailleurs que dans les secrets Streamlit (jamais dans GitHub, ni par e-mail).")
        return

    q = st.query_params
    if q.get("error"):
        st.error(f"Autorisation refusée par Google : {q.get('error')}.")
    elif q.get("code"):
        if not etat_valide(q.get("state", ""), auth["cookie_secret"]):
            st.error("Lien d'autorisation expiré ou invalide : recommencez.")
        else:
            with st.spinner("Création du classeur et des dossiers dans le Drive du club…"):
                try:
                    res = creer_espace(echanger_code(auth, q["code"]))
                except Exception as e:  # noqa: BLE001
                    st.error(f"L'installation a échoué : {e}")
                    st.query_params.clear()
                    return
            st.session_state["installation"] = res
            st.query_params.clear()
            st.rerun()

    st.markdown(
        "Le logiciel n'est pas encore relié au Drive du club. Cliquez ci-dessous, **connectez-vous avec le "
        "compte du club** et acceptez : l'application crée son classeur de données et ses dossiers. Elle ne "
        "pourra voir que les fichiers qu'elle a elle-même créés.")
    st.link_button("Autoriser l'accès au Drive du club", url_autorisation(auth, admins[0] if admins else ""),
                   type="primary")
    st.caption("Si Google affiche « Application non validée » : Paramètres avancés → Accéder à l'application "
               "(normal pour une application privée en mode test).")
