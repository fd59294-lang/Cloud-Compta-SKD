"""Installation sur le compte Google du club — à lancer UNE SEULE FOIS sur un ordinateur.

Ce script :
  1. ouvre le navigateur pour que vous vous connectiez avec le compte Google du club
     (senseikaratedo59@gmail.com) et que vous autorisiez l'application ;
  2. crée dans le Drive du club le classeur Google Sheets « Sensei Karaté Do — Données » et le dossier
     « Sensei Karaté Do — Gestion » avec ses sous-dossiers ;
  3. affiche le bloc [club] à coller dans les secrets de l'application (voir GUIDE_MISE_EN_LIGNE.md).

Prérequis : Python 3.11+ et   pip install google-auth-oauthlib gspread google-api-python-client
Usage      : python outils/installer_google.py chemin/vers/client_secret.json

client_secret.json = identifiant OAuth de type « Application de bureau » créé dans Google Cloud
(le même projet Google Cloud que le Comité des Fêtes peut servir).
"""
from __future__ import annotations

import json
import sys

SCOPES = ["https://www.googleapis.com/auth/drive.file"]
DOSSIERS = ["Sauvegardes", "Factures et reçus", "Reçus fiscaux", "Rapports", "Relevés bancaires", "Justificatifs",
            "Imports", "Logo"]


def main() -> None:
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    import gspread

    flow = InstalledAppFlow.from_client_secrets_file(sys.argv[1], SCOPES)
    print("Une page Google va s'ouvrir : connectez-vous avec le compte DU CLUB, puis acceptez.")
    creds = flow.run_local_server(port=0, prompt="consent", access_type="offline")
    drive = build("drive", "v3", credentials=creds, cache_discovery=False)
    compte = drive.about().get(fields="user(emailAddress)").execute()["user"]["emailAddress"]
    print(f"Compte connecté : {compte}")

    racine = drive.files().create(body={"name": "Sensei Karaté Do — Gestion",
                                        "mimeType": "application/vnd.google-apps.folder"}, fields="id").execute()["id"]
    dossiers = {"_racine": racine}
    for nom in DOSSIERS:
        dossiers[nom] = drive.files().create(body={"name": nom, "mimeType": "application/vnd.google-apps.folder",
                                                   "parents": [racine]}, fields="id").execute()["id"]
    gc = gspread.authorize(creds)
    classeur = gc.create("Sensei Karaté Do — Données", folder_id=racine)
    jeton = json.loads(creds.to_json())
    print("\n" + "=" * 70)
    print("Copiez tout le bloc ci-dessous dans les secrets de l'application :\n")
    print("[club]")
    print('backend = "google"')
    print(f'spreadsheet_id = "{classeur.id}"')
    print(f'admins = "{compte}"')
    print(f"dossiers = '''{json.dumps(dossiers)}'''")
    print(f"google_credentials = '''{json.dumps(jeton)}'''")
    print("=" * 70)
    print("\nNe partagez jamais ce bloc : il donne accès aux fichiers créés par l'application dans le Drive du club.")


if __name__ == "__main__":
    main()
