# Cloud Compta SKD — gestion du club Sensei Karaté Do

Logiciel de gestion du club, construit **sur le même modèle que le logiciel du Comité des Fêtes** :

```
GitHub (ce dépôt) ──► hébergement en ligne ──► lien d'accès (connexion Google + liste d'utilisateurs)
                                                   │
                                                   ▼
                          Google Sheets + Google Drive du compte du club (toutes les données)
```

Ce dépôt ne contient **que le programme**. Aucune donnée du club (adhérents, écritures, coordonnées,
IBAN…) n'y figure : tout reste dans le Drive du club.

## Ce que fait le logiciel

| Pilotage | Comptabilité | Adhérents | Dons et documents |
|---|---|---|---|
| Tableau de bord (banque, caisse, résultat, reste à encaisser, graphiques) | Saisie avec justificatif PDF/photo | Fiche unique par n° de licence FFKaraté | Dons et reçus fiscaux Cerfa 11580 |
| Budget prévisionnel prévu / réalisé / N-1 | Historique filtrable depuis 2023, export Excel | Inscription par saison, tarif selon l'âge, réduction famille, frais d'adhésion | Factures libres |
| Rapport d'AG, compte financier, bilan, comparaison, synthèse mensuelle | Banque / espèces séparées, rapprochement | Paiements en plusieurs fois (chèque, virement, espèces, Pass'Sport…) | Fiches de remboursement de frais |
| | Import des relevés CSV, contrôle du relevé | Reçus de paiement, factures de cotisation | Registre des documents émis |
| | Opérations en attente (prélèvements prévus) | Restes à encaisser | Sauvegarde quotidienne, journal |

La liste détaillée, fonction par fonction, avec son origine (Excel d'origine ou version Apps Script)
est dans [INVENTAIRE.md](INVENTAIRE.md).

## Fichiers

| Fichier | Rôle |
|---|---|
| `app.py` | Lancement, connexion, tableau de bord, paramètres, utilisateurs, sauvegarde |
| `ecran_*.py` | Écrans : comptabilité, banque, adhérents, dons, documents, budget, rapports, reprise |
| `metier.py`, `adherents.py` | Règles de gestion (testées sans interface) |
| `documents.py`, `rapports.py` | PDF : factures, reçus, reçus fiscaux, remboursements, rapports d'AG |
| `stockage.py` | Google Sheets + Drive (production) ou fichier Excel local (essai) — identique au Comité |
| `outils/installer_google.py` | Installation unique sur le compte Google du club |
| `tests/` | Tests automatiques (`python -m pytest`) |

## Essai sur un ordinateur

```bash
pip install -r requirements.txt
streamlit run app.py          # mode essai : données dans ./donnees_locales, sans connexion
```

## Mise en ligne

Voir [GUIDE_MISE_EN_LIGNE.md](GUIDE_MISE_EN_LIGNE.md).
