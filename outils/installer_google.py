"""Installation sur le compte Google du club — à lancer UNE SEULE FOIS sur un ordinateur.

Ce script :
  1. ouvre le navigateur pour que vous vous connectiez avec le compte Google du club
     (senseikaratedo59@gmail.com) et que vous autorisiez l'application ;
  2. crée dans le Drive du club le classeur Google Sheets « Sensei Karaté Do — Données » et le dossier
     « Sensei Karaté Do — Gestion » avec ses sous-dossiers ;
  3. affiche le bloc [club] à coller dans les secrets de l'application (voir GUIDE_MISE_EN_LIGNE.md).

Prérequis : Python 3.11+ et   pip install google-auth-oauthlib gspread google-api-python-client
Usage      : python outils/installer_google.py chemin/vers/client_secret.json

client_secret.json = identifiant OAuth de type « Application de bureau » du projet Google Cloud du club.
Plus simple : l'installation peut se faire directement depuis l'application en ligne (installation.py).
"""
from __future__ import annotations

import os
import sys

SCOPES = ["https://www.googleapis.com/auth/drive.file"]


def main() -> None:
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)
    from google_auth_oauthlib.flow import InstalledAppFlow
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from installation import bloc_club, creer_espace

    flow = InstalledAppFlow.from_client_secrets_file(sys.argv[1], SCOPES)
    print("Une page Google va s'ouvrir : connectez-vous avec le compte DU CLUB, puis acceptez.")
    creds = flow.run_local_server(port=0, prompt="consent", access_type="offline")
    res = creer_espace(creds)
    print(f"Compte connecté : {res['compte']}")
    print("\n" + "=" * 70)
    print("Copiez tout le bloc ci-dessous dans les secrets de l'application :\n")
    print(bloc_club(res, []))
    print("=" * 70)
    print("\nNe partagez jamais ce bloc : il donne accès aux fichiers créés par l'application dans le Drive du club.")


if __name__ == "__main__":
    main()
