# Mise en ligne — compte Google du club (senseikaratedo59)

Même méthode que pour le Comité des Fêtes, mais tout est propre au club (projet Google Cloud, Drive, hébergement). Durée : environ 30 minutes, une seule fois.

```
① Google Cloud        ② Streamlit Cloud          ③ Installation Drive         ④ Premier lancement
projet du club   ──►  depuis GitHub +       ──►  bouton dans l'application ──► import de la reprise
client « Web »        secrets de départ          (crée Sheets + dossiers)     (banque = 213,46 €)
```

## ① Projet Google Cloud du club (propre à Sensei Karaté Do)

Aucun élément partagé avec le Comité des Fêtes : projet, identifiants, Drive et données sont ceux du club.
Connectez-vous à https://console.cloud.google.com avec **senseikaratedo59@gmail.com**.

1. Projet `Sensei Karate Do Gestion`.
2. **API et services → Bibliothèque** : activez *Google Drive API* et *Google Sheets API*.
3. **Écran de consentement OAuth** : type **Externe**, nom `Sensei Karaté Do — Gestion`, e-mail
   `senseikaratedo59@gmail.com` ; **Utilisateurs test** : `senseikaratedo59@gmail.com` + l'adresse Google de
   chaque membre du bureau qui utilisera le logiciel.
4. **Client OAuth « Application Web »** avec **deux** *URI de redirection autorisés* :
   - `https://sensei-karate-do-haussy.streamlit.app/oauth2callback` (connexion au logiciel)
   - `https://sensei-karate-do-haussy.streamlit.app/` (installation dans le Drive, étape ③)

## ② Hébergement sur Streamlit Community Cloud (comme `comite-fetes-haussy.streamlit.app`)

1. https://share.streamlit.io (compte GitHub `fd59294-lang`, propriétaire du dépôt) → **Create app** →
   **Deploy a public app from GitHub**.
2. *Repository* `fd59294-lang/Cloud-Compta-SKD` — *Branch* `main` — *Main file path* `app.py` —
   *App URL* `sensei-karate-do-haussy`.
3. **Advanced settings** : *Python version* **3.12** ; *Secrets* (secrets **de départ**) :

```toml
[auth]
redirect_uri = "https://sensei-karate-do-haussy.streamlit.app/oauth2callback"
cookie_secret = "une longue phrase aléatoire"
client_id = "… (client « Application Web »)"
client_secret = "…"
server_metadata_url = "https://accounts.google.com/.well-known/openid-configuration"

[club]
backend = "installation"
admins = "senseikaratedo59@gmail.com"
```

4. **Deploy**. Dans Google Cloud (projet du club), *Écran de consentement → page d'accueil / règles de
   confidentialité* : `https://sensei-karate-do-haussy.streamlit.app/?page=confidentialite`.

## ③ Installation dans le Drive du club (depuis l'application, aucun PC nécessaire)

1. Ouvrez https://sensei-karate-do-haussy.streamlit.app → **Se connecter avec Google** (compte du club).
2. Page « Installation dans le Drive du club » → **Autoriser l'accès au Drive du club** → compte du club →
   accepter (si « Application non validée » : *Paramètres avancés → Accéder à l'application*).
3. L'application crée le classeur **« Sensei Karaté Do — Données »** et le dossier **« Sensei Karaté Do —
   Gestion »** (Sauvegardes, Factures et reçus, Reçus fiscaux, Rapports, Relevés bancaires, Justificatifs,
   Imports, Logo), puis affiche le **bloc `[club]` définitif**.
4. Streamlit → *Manage app → Settings → Secrets* : remplacez le bloc `[club]` de départ par ce bloc (gardez
   `[auth]`), *Save*. L'application redémarre reliée au Drive. Pour vous connecter aussi avec votre adresse
   personnelle, ajoutez-la dans `admins` (séparée par une virgule).

Variante sans l'application : `python outils/installer_google.py client_bureau.json` sur un ordinateur avec
Python (client OAuth « Application de bureau »).

## ④ Premier lancement

1. Ouvrez le lien, connectez-vous avec un compte listé dans `admins`.
2. **Administration → Paramètres** : coordonnées du club, IBAN, RNA, SIRET, affiliation, président,
   trésorier, logo. Vérifiez « Début de la saison » = **Septembre**.
3. **Adhérents → Tarifs** : vérifiez les tarifs de la saison.
4. **Association → Reprise et import → Modèle d'import Excel** : déposez le fichier de reprise
   `SKD_reprise_2023-2026.xlsx` (déjà rapproché avec tous les relevés). L'aperçu doit afficher
   **banque 213,46 €, pointé 213,46 €, caisse 0,00 €**. Importez. N'importez pas en plus le `.xlsm` d'origine :
   ses écritures sont déjà dans le fichier de reprise.
5. **Banque → Pointage** : validez les relevés un par un, du 02/05/2023 au 31/10/2026 (écart 0,00 € à
   chaque fois ; joignez le PDF du relevé pour l'archiver dans le Drive). Méthode : [POINTAGE.md](POINTAGE.md).
6. **Administration → Utilisateurs** : ajoutez le trésorier, la secrétaire… avec leur rôle.

## Adresse personnalisée (facultatif)

Si le domaine `senseikaratedo.fr` est géré chez Cloudflare, une règle de redirection
(`compta.senseikaratedo.fr` → adresse du logiciel) donne une adresse plus simple à retenir.

## Sécurité

- L'application ne voit que les fichiers qu'elle a créés dans le Drive (autorisation `drive.file`).
- Seules les adresses de la page **Utilisateurs** peuvent entrer ; rôle « Lecture seule » possible.
- Une sauvegarde Excel complète est rangée chaque jour dans *Sauvegardes* ; le bouton
  « Télécharger toutes les données » donne une copie à tout moment.
- La page publique `?page=confidentialite` sert à l'écran de consentement Google.
