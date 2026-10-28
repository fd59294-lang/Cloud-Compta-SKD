# Cloud Compta SKD

Gestion d'une association sportive sur Google Sheets + Google Apps Script :
comptabilité (banque / espèces), adhérents par n° de licence FFKaraté, paiements
adhésion / cotisation, factures et reçus PDF, dons et reçus fiscaux, import de
relevés bancaires CSV avec rapprochement, justificatifs, budget prévisionnel,
rapports d'AG et sauvegarde quotidienne.

**Ce dépôt ne contient que le programme.** Toutes les données (adhérents, écritures,
coordonnées du club, IBAN…) restent dans le Google Sheets et le Google Drive du club.

## Fichiers

| Fichier | Rôle |
|---|---|
| `Code.js` | Script serveur (s'appelle `Code.gs` dans l'éditeur Apps Script) |
| `interface.html` | Interface web (8 onglets) |
| `appsscript.json` | Manifeste : fuseau Europe/Paris, moteur V8, accès « moi uniquement » |

## Installation dans un nouveau Google Sheets

1. Onglets attendus : `Operations_Historique`, `Membres_Cotisations`, `Configuration`
   (les onglets `Dons_Recus`, `Budget`, `Dashboard` sont créés automatiquement).
2. Dossiers Drive : `01_Données_Principales` (logo), `02_Factures_PDF`,
   `03_Relevés_Bancaires`, `04_Justificatifs`, `05_Archives_Annuelles`, `06_Sauvegardes`.
3. Extensions → Apps Script : coller `Code.js` dans `Code.gs` et créer le fichier HTML `interface`.
4. Dans le Sheets : menu 🏛️ Association → 🔧 Maintenance → *Compléter l'onglet Configuration*,
   puis renseigner les valeurs.
5. Déclencheur quotidien sur `sauvegardeAutomatique`.
6. Déployer → Application Web (exécuter en tant que moi, accès moi uniquement).

## Synchronisation avec clasp (optionnel)

```bash
npm install -g @google/clasp
clasp login
clasp clone <ID_DU_SCRIPT> --rootDir .
```
