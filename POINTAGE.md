# Méthode pour des comptes carrés

Objectif : chaque relevé bancaire est **validé à 0,00 € d'écart**, dans l'ordre chronologique, depuis
l'ouverture du compte en 2023. Une fois validé, un relevé **verrouille** ses écritures : on ne peut plus
les modifier par erreur.

```
Reprise de l'Excel (une fois)
        │
        ▼
┌─ Pour chaque relevé, du plus ancien au plus récent ───────────────────────┐
│  Banque → Pointage                                                        │
│   1. date de fin + solde imprimé sur le relevé (+ le PDF, archivé)        │
│   2. cocher les écritures qui figurent sur le relevé                      │
│   3. écart ≠ 0 ? → saisir les écritures manquantes (bouton ➕)            │
│                  → ou corriger un montant dans Opérations                 │
│   4. écart = 0,00 € → « Valider le relevé »  🔒                            │
└───────────────────────────────────────────────────────────────────────────┘
        │
        ▼
Caisse espèces : chaque sortie d'espèces doit avoir son entrée en face
        │
        ▼
Rapports → Compte financier de chaque saison (2023-2024, 2024-2025…)
```

## Les cas qui créent un écart

| Sur le relevé, pas dans la compta | → bouton « ➕ Saisir une écriture » (créée déjà pointée) |
|---|---|
| Dans la compta, pas sur ce relevé | normal (chèque pas encore encaissé) : ne pas cocher, il sera pointé sur un relevé suivant |
| Montant différent | Opérations → corriger l'écriture (avant validation) |
| Écriture en double | Opérations → supprimer le doublon |
| Écriture passée par le compte mais saisie « Espèces » | Opérations → changer la source en « Banque » |

## Les espèces

Les espèces ne passent pas par la banque : elles ne se pointent pas sur un relevé. Pour que la caisse soit
juste, chaque dépense payée en espèces doit avoir une origine :
- argent reçu en espèces (cotisation, buvette) → recette, source « Espèces » ;
- dépôt d'espèces à la banque → une dépense « Espèces » et une recette « Banque » du même montant ;
- dépense avancée par un membre → fiche de remboursement de frais, ou don si le membre renonce au remboursement.

Le solde de caisse affiché doit correspondre à l'argent réellement dans la caisse (0 € s'il n'y a pas de caisse).

## Une erreur découverte après validation

Banque → Relevés validés → annuler la validation du **dernier** relevé (président ou trésorier). Les écritures
se déverrouillent, on corrige, on revalide. L'opération est tracée dans le journal.
