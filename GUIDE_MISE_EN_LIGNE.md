# Mise en ligne — compte Google du club (senseikaratedo59)

Même procédure que pour le Comité des Fêtes. Durée : environ 30 minutes, une seule fois.

```
① Google Cloud        ② Installation Drive        ③ Hébergement          ④ Premier lancement
identifiants OAuth ──► script installer_google ──► depuis GitHub + ──► reprise de l'Excel
(projet du Comité)     (crée Sheets + dossiers)    secrets              (le solde doit égaler l'Excel)
```

## ① Identifiants Google (projet Google Cloud du Comité)

Dans https://console.cloud.google.com, ouvrez le **même projet** que celui du Comité des Fêtes.

1. **API et services → Bibliothèque** : vérifiez que *Google Drive API* et *Google Sheets API* sont activées.
2. **Écran de consentement OAuth → Utilisateurs test** : ajoutez `senseikaratedo59@gmail.com` et l'adresse
   Google de chaque membre du bureau qui utilisera le logiciel.
3. **Identifiants → Créer → ID client OAuth** :
   - un client **« Application de bureau »** (pour l'installation, étape ②) → téléchargez le JSON ;
   - un client **« Application Web »** (pour la connexion au logiciel). Dans *URI de redirection autorisés*,
     ajoutez l'adresse du logiciel suivie de `/oauth2callback` (vous la connaîtrez à l'étape ③ ; revenez
     la compléter).

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

## ③ Hébergement depuis GitHub

Déployez le dépôt `fd59294-lang/Cloud-Compta-SKD` (fichier principal `app.py`) de la même façon que
`comite-fetes`, puis collez dans les **secrets** de l'application :

```toml
[auth]
redirect_uri = "https://ADRESSE-DU-LOGICIEL/oauth2callback"
cookie_secret = "une longue phrase aléatoire"
client_id = "… (client « Application Web »)"
client_secret = "…"
server_metadata_url = "https://accounts.google.com/.well-known/openid-configuration"

# + le bloc [club] affiché par le script de l'étape ②
```

Ajoutez dans `admins` (bloc `[club]`) votre adresse Google personnelle si vous voulez vous connecter avec :
toute adresse listée dans `admins` est créée automatiquement comme président(e) à sa première connexion.

## ④ Premier lancement

1. Ouvrez le lien, connectez-vous avec un compte listé dans `admins`.
2. **Administration → Paramètres** : coordonnées du club, IBAN, RNA, SIRET, affiliation, président,
   trésorier, logo. Vérifiez « Début de la saison » = **Septembre**.
3. **Adhérents → Tarifs** : vérifiez les tarifs de la saison.
4. **Association → Reprise et import** :
   - onglet *Excel d'origine* : déposez le classeur `.xlsm` → contrôlez que les soldes affichés (banque et
     pointé) sont ceux de l'Excel au moment de l'import, puis importez. Le pointage et les écritures
     manquantes se terminent ensuite dans le logiciel, relevé par relevé (page **Banque → Pointage**, méthode dans
     [POINTAGE.md](POINTAGE.md)). Si vous
     préférez finir dans l'Excel, réimportez-le : seules les nouvelles lignes sont ajoutées et les
     pointages faits entre-temps sont reportés ;
   - onglet *Version Google Sheets* : seulement si des données ont été saisies dans la version Apps Script
     (Fichier → Télécharger → .xlsx depuis ce Google Sheets).
5. **Administration → Utilisateurs** : ajoutez le trésorier, la secrétaire… avec leur rôle.

## Adresse personnalisée (facultatif)

Si le domaine `senseikaratedo.fr` est géré chez Cloudflare, une règle de redirection
(`compta.senseikaratedo.fr` → adresse du logiciel) donne une adresse plus simple à retenir.

## Sécurité

- L'application ne voit que les fichiers qu'elle a créés dans le Drive (autorisation `drive.file`).
- Seules les adresses de la page **Utilisateurs** peuvent entrer ; rôle « Lecture seule » possible.
- Une sauvegarde Excel complète est rangée chaque jour dans *Sauvegardes* ; le bouton
  « Télécharger toutes les données » donne une copie à tout moment.
- La page publique `?page=confidentialite` sert à l'écran de consentement Google.
