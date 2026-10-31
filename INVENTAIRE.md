# Inventaire des fonctions — rien ne doit être perdu

Sources : l'Excel d'origine (`Compte SKD .xlsm`, 20 feuilles) et la version Apps Script
(`Code.gs` + `interface.html`, oct. 2026). Chaque ligne indique où la fonction se retrouve
dans le programme Python.

## Comptabilité
| Fonction d'origine | Origine | Programme Python |
|---|---|---|
| Livre de comptes : date, montant, catégorie, tiers, notes | Excel + Apps Script | Saisir / Opérations |
| Colonne E (espèces) distincte de la banque, solde bancaire hors espèces | Excel + Apps Script | champ « Source » Banque / Espèces, soldes séparés |
| Colonne R (rapproché) | Excel + Apps Script | case « Rapproché » + écran Banque |
| N° de pièce, justificatif PDF/photo lié à l'écriture | Apps Script | Opérations → justificatif rangé dans le Drive |
| Historique 2023+ filtrable (exercice, catégorie, source, rapprochement, texte) | Apps Script | Opérations |
| Export CSV/Excel des écritures | Apps Script | Opérations → export Excel |
| Correction / suppression d'une écriture | Excel | Opérations (correction tracée au journal) |
| Opérations en attente (prélèvements mensuels prévus) transférées au livre | Excel | Opérations en attente |
| Catégories du club | Excel | plan de catégories modifiable (Paramètres) |
| Exercice septembre → août | Excel (compte financier) | paramètre « mois de début » = septembre |

## Banque
| Import du relevé CSV, rapprochement automatique (montant ± 10 jours) | Apps Script | Banque → import |
| Catégorie devinée d'après les habitudes | Apps Script | Banque → import |
| Archivage des relevés (CSV et PDF) | Apps Script | Banque → archive Drive |
| Rapprochement : solde du relevé / solde pointé / écart | Excel (feuille Rappr) | Banque → contrôle du relevé |

## Adhérents
| Numéro de licence FFKaraté unique, réinscription sans ressaisie | Apps Script | Adhérents |
| Frais d'adhésion (1re année) distincts de la cotisation | Apps Script | Tarifs + inscription |
| Paiements en plusieurs fois, statut payé / partiel / en attente | Apps Script | Paiements |
| Modes : chèque, virement, espèces, Pass'Sport, carte | Apps Script | Paiements |
| Écriture comptable créée avec le paiement | Apps Script | Paiements |
| Facture d'adhérent PDF numérotée | Apps Script | Adhérents → facture |
| Attestation / reçu de paiement de cotisation, responsable légal de l'enfant | Excel (Reçu de cotisation) + Apps Script | Paiements → reçu |
| Recherche par licence ou nom | Apps Script | Adhérents |
| Historique multi-saisons | (exigence) | inscriptions par saison |

## Dons
| Saisie du don (numéraire / nature, mode) | Apps Script | Dons |
| Reçu fiscal Cerfa 11580 : montant en lettres, numérotation sans trou, duplicata | Apps Script (+ Excel « Reçu de don ») | Dons |
| Écriture comptable du don | Apps Script | Dons |

## Autres documents
| Facture libre (destinataire, lignes, IBAN) | Excel (Facture) | Documents → facture |
| Fiche de remboursement de frais (bénévole, lignes) | Excel (Remb. frais) | Documents → remboursement de frais |
| Logo, nom, adresse, contact, SIRET, RNA, affiliation, IBAN, trésorier, président | Excel (Prise en main) + Apps Script | Paramètres |

## Budget, rapports, tableau de bord
| Budget prévisionnel par catégorie, comparé à l'exercice précédent | Excel + Apps Script | Budget prévisionnel |
| Proposition du budget à partir du réalisé précédent | Apps Script | Budget prévisionnel |
| Prévu / réalisé avec barres | Apps Script | Budget + Tableau de bord |
| Compte financier (compte de résultat, soldes banque et caisse début/fin) | Excel | Rapports → compte financier PDF |
| Synthèse des opérations (mois × catégories) | Excel | Rapports → synthèse (écran + Excel) |
| Graphiques | Excel + Apps Script | Tableau de bord + rapports |
| Bilan financier PDF avec graphique mensuel | Apps Script | Rapports |
| Rapport d'AG (activité, finances, adhérents, dons, budget N+1, résolutions, signatures) | Apps Script | Rapports → AG |
| Comparaison de deux exercices | Apps Script | Rapports |
| Tableau de bord : banque, caisse, résultat, reste à encaisser, adhérents | Apps Script | Tableau de bord |

## Sécurité et données
| Données dans le Google Drive du club, jamais sur GitHub | décision | stockage Sheets + Drive (compte du club) |
| Sauvegarde quotidienne horodatée | Apps Script | sauvegarde Excel automatique dans le Drive |
| Connexion | Apps Script (compte unique) | connexion Google + liste d'utilisateurs et rôles (comme le Comité) |
| Journal des actions | (Comité) | Sauvegarde → journal |
| Reprise de l'existant | — | Reprise : Excel d'origine (.xlsm) + export de la version Apps Script |
