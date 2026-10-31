# Mise en ligne — compte Google du club (senseikaratedo59)

Même méthode que pour le Comité des Fêtes, mais tout est propre au club (projet Google Cloud, Drive, hébergement). Durée : environ 30 minutes, une seule fois.

```
① Google Cloud        ② Installation Drive        ③ Streamlit Cloud       ④ Premier lancement
identifiants OAuth ──► script installer_google ──► depuis GitHub + ──► import de la reprise
(projet du club)       (crée Sheets + dossiers)    secrets              (banque = 213,46 €)
```

## ① Projet Google Cloud du club (propre à Sensei Karaté Do)

Aucun élément partagé avec le Comité des Fêtes : projet, identifiants, Drive et données sont ceux du club.
Connectez-vous à https://console.cloud.google.com avec **senseikaratedo59@gmail.com**.

1. En haut, sélecteur de projet → **Nouveau projet** → nom `Sensei Karate Do Gestion` → Créer, puis
   sélectionnez-le.
2. **API et services → Bibliothèque** : activez *Google Drive API* puis *Google Sheets API*.
3. **API et services → Écran de consentement OAuth** (ou *Google Auth Platform*) :
   type **Externe** ; nom de l'application `Sensei Karaté Do — Gestion` ; e-mail d'assistance et contact :
   `senseikaratedo59@gmail.com`. Dans **Audience → Utilisateurs test**, ajoutez `senseikaratedo59@gmail.com`
   et l'adresse Google de chaque membre du bureau qui utilisera le logiciel.
4. **Identifiants (ou Clients) → Créer un ID client OAuth**, deux fois :
   - type **Application de bureau**, nom `installation` → téléchargez le JSON ;
   - type **Application Web**, nom `logiciel`, *URI de redirection autorisés* :
     `https://sensei-karate-do-haussy.streamlit.app/oauth2callback` → notez l'ID client et le code secret.

## ② Installation dans le Drive du club (une seule fois)

Sur n'importe quel ordinateur avec Python :

```bash
pip install google-auth-oauthlib gspread google-api-python-client
python outils/installer_google.py client_secret_bureau.json
```

Connectez-vous avec **le compte du club**. Le script crée dans son Drive :
- le classeur **« Sensei Karaté Do — Données »** (une page par table : opérations, adhérents…) ;
- le dossier **« Sensei Karaté Do — Gestion »** et ses sous-dossiers (Sauvegardes, Factures et reçus,
  Reçus fiscaux, Rapports, Relevés bancaires, Justificatifs, Imports, Logo).

Il affiche ensuite un bloc `[club]` : copiez-le, il sert à l'étape ③. Ne le partagez pas et ne le mettez
jamais dans GitHub. Supprimez ensuite le fichier `client_secret_bureau.json` de l'ordinateur.

## ③ Hébergement sur Streamlit Community Cloud (comme `comite-fetes-haussy.streamlit.app`)

1. Ouvrez https://share.streamlit.io (connexion avec le compte GitHub `fd59294-lang`, propriétaire du dépôt)
   → **Create app** →
   **Deploy a public app from GitHub**.
2. Renseignez :
   - *Repository* : `fd59294-lang/Cloud-Compta-SKD` — *Branch* : `main` — *Main file path* : `app.py`
   - *App URL* : `sensei-karate-do-haussy` → adresse **https://sensei-karate-do-haussy.streamlit.app**
3. **Advanced settings** : *Python version* **3.12**, puis collez dans *Secrets* :

```toml
[auth]
redirect_uri = "https://sensei-karate-do-haussy.streamlit.app/oauth2callback"
cookie_secret = "une longue phrase aléatoire"
client_id = "… (client « Application Web »)"
client_secret = "…"
server_metadata_url = "https://accounts.google.com/.well-known/openid-configuration"

# + le bloc [club] affiché par le script de l'étape ②
```

4. **Deploy**. Dans Google Cloud (projet du club), *Écran de consentement → Lien vers la page d'accueil / règles de confidentialité*, mettez
   `https://sensei-karate-do-haussy.streamlit.app/?page=confidentialite`.

Ajoutez dans `admins` (bloc `[club]`) votre adresse Google personnelle si vous voulez vous connecter avec :
toute adresse listée dans `admins` est créée automatiquement comme président(e) à sa première connexion.
Les secrets se modifient ensuite dans *Manage app → Settings → Secrets* (jamais dans GitHub).

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
