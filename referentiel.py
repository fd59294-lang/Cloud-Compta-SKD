"""Référentiels : catégories, tables, rôles, modes de paiement, tarifs par défaut.

Les catégories suivent le plan comptable associatif (règlement ANC 2018-06), simplifié pour un
club sportif. Elles sont copiées dans l'onglet « categories » au premier lancement et restent
ensuite modifiables dans les Paramètres.
"""

APP_NOM = "Sensei Karaté Do — Gestion"
NOM_ASSOCIATION_DEFAUT = "Sensei Karaté Do"

# ------------------------------------------------------------------ catégories par défaut
CATEGORIES_DEFAUT = [
    # (code, nom, sens)
    ("756", "Cotisations des adhérents", "Recette"),
    ("7562", "Frais d'adhésion", "Recette"),
    ("754", "Dons", "Recette"),
    ("74", "Subventions", "Recette"),
    ("706", "Stages, compétitions, manifestations", "Recette"),
    ("707", "Ventes (équipements, boutique)", "Recette"),
    ("7581", "Rétrocession de frais bancaires", "Recette"),
    ("768", "Produits financiers", "Recette"),
    ("1081", "Apports et dépôts d'espèces", "Recette"),
    ("758", "Recettes diverses", "Recette"),
    ("R99", "À classer (recette)", "Recette"),
    ("6281", "Licences FFKaraté", "Dépense"),
    ("6282", "Affiliation et cotisation fédérale", "Dépense"),
    ("616", "Assurances", "Dépense"),
    ("627", "Frais bancaires", "Dépense"),
    ("606", "Achat de matériel et d'équipement", "Dépense"),
    ("613", "Locations (salle, matériel)", "Dépense"),
    ("6251", "Déplacements, compétitions, stages", "Dépense"),
    ("6256", "Remboursements de frais aux bénévoles", "Dépense"),
    ("622", "Honoraires, arbitrage, intervenants", "Dépense"),
    ("623", "Communication, impression, site internet", "Dépense"),
    ("626", "Frais postaux et téléphone", "Dépense"),
    ("6257", "Réceptions, récompenses, cadeaux", "Dépense"),
    ("658", "Dépenses diverses", "Dépense"),
    ("D99", "À classer (dépense)", "Dépense"),
]

# Correspondance des catégories de l'Excel d'origine et de la version Apps Script
CORRESPONDANCE_CATEGORIES = {
    "cotisations des licenciés": "756", "cotisations des licenciés club skd": "756", "cotisations": "756",
    "cotisation": "756", "frais d'adhésion": "7562", "adhésion": "7562",
    "dons": "754", "don": "754", "subventions": "74", "subvention": "74",
    "evenements": "706", "événements": "706", "stages": "706",
    "retrocession frais bancaire": "7581", "rétrocession frais bancaire": "7581",
    "recettes diverses": "758", "autres": "758", "dépôt d'espèces": "1081", "depot d'especes": "1081",
    "licence adherent ffk": "6281", "licence adhérent ffk": "6281", "licences": "6281",
    "cotisation federation": "6282", "cotisation fédération": "6282",
    "assurance maif": "616", "assurances": "616", "assurance": "616",
    "frais bancaires": "627", "frais_bancaires": "627",
    "achat matériel / équipement": "606", "achat materiel / equipement": "606", "materiel": "606", "matériel": "606",
    "fonctionnement": "658", "dépenses diverses": "658", "depenses diverses": "658",
}

SENS = ["Recette", "Dépense"]
SOURCES = ["Banque", "Espèces"]
MODES_PAIEMENT = ["Chèque", "Virement", "Espèces", "Pass'Sport", "Carte bancaire", "Prélèvement", "Autre"]
NATURES_DON = ["Numéraire", "Don en nature"]

# ------------------------------------------------------------------ tarifs (modifiables, par saison)
TARIFS_DEFAUT = [
    # (nom, âge mini, âge maxi, cotisation totale, dont licence FFK)
    ("Enfant (jusqu'à 12 ans)", 0, 12, 129.0, 39.0),
    ("Ado / adulte (13 ans et plus)", 13, 120, 139.0, 39.0),
]
REDUCTION_FAMILLE_DEFAUT = 30.0
FRAIS_ADHESION_DEFAUT = 0.0

# ------------------------------------------------------------------ tables (un onglet chacune)
TABLES = {
    "operations": ["id", "date", "exercice", "sens", "categorie", "libelle", "montant", "source", "mode_paiement",
                   "tiers", "piece", "notes", "rapproche", "justificatif", "origine", "saisi_par", "saisi_le"],
    "attente": ["id", "date", "sens", "categorie", "libelle", "montant", "source", "mode_paiement", "tiers", "notes",
                "cree_par", "cree_le"],
    "categories": ["code", "nom", "sens", "actif"],
    "adherents": ["id", "licence", "nom", "prenom", "date_naissance", "responsable_legal", "famille", "email",
                  "telephone", "adresse", "premiere_saison", "notes", "actif", "cree_le"],
    "tarifs": ["saison", "nom", "age_min", "age_max", "cotisation", "dont_licence"],
    "inscriptions": ["id", "adherent_id", "saison", "tarif", "cotisation", "frais_adhesion", "reduction", "total_du",
                     "date_inscription", "notes", "cree_par"],
    "paiements": ["id", "inscription_id", "adherent_id", "saison", "date", "montant", "mode", "payeur",
                  "operation_id", "recu", "saisi_par", "saisi_le"],
    "dons": ["id", "date", "nom", "adresse", "email", "montant", "nature", "mode", "description", "numero_recu",
             "operation_id", "saisi_par", "saisi_le"],
    "documents": ["id", "type", "numero", "date", "destinataire", "objet", "montant", "fichier", "cree_par", "cree_le"],
    "budget": ["exercice", "categorie", "sens", "prevu", "commentaire", "maj_le"],
    "releves": ["id", "date_releve", "solde_releve", "solde_pointe", "ecart", "fichier", "cree_par", "cree_le",
                "valide"],
    "utilisateurs": ["email", "nom", "role"],
    "parametres": ["cle", "valeur"],
    "journal": ["horodatage", "utilisateur", "action", "detail"],
}

# Paramètres du club (onglet « parametres ») : clé -> (libellé, valeur par défaut)
PARAMETRES_CLUB = {
    "nom_association": ("Nom de l'association", NOM_ASSOCIATION_DEFAUT),
    "objet_association": ("Objet (pour le reçu fiscal)", "Enseignement et pratique du karaté"),
    "adresse": ("Adresse", ""),
    "code_postal_ville": ("Code postal et ville", ""),
    "ville_signature": ("Ville de signature des documents", ""),
    "email": ("E-mail", ""),
    "telephone": ("Téléphone", ""),
    "iban": ("IBAN", ""),
    "bic": ("BIC", ""),
    "rna": ("N° RNA", ""),
    "siret": ("N° SIRET", ""),
    "affiliation": ("N° d'affiliation FFKaraté", ""),
    "president": ("Président(e)", ""),
    "tresorier": ("Trésorier(e)", ""),
    "secretaire": ("Secrétaire", ""),
}

ROLES = ["president", "tresorier", "secretaire", "lecteur"]
ROLES_LIBELLES = {"president": "Président(e)", "tresorier": "Trésorier(e)",
                  "secretaire": "Secrétaire", "lecteur": "Lecture seule"}
ROLES_SAISIE = {"president", "tresorier", "secretaire"}
ROLES_ADMIN = {"president", "tresorier"}

MOIS = ["Toute l'année", "Janvier", "Février", "Mars", "Avril", "Mai", "Juin", "Juillet",
        "Août", "Septembre", "Octobre", "Novembre", "Décembre"]
MOIS_COURTS = ["Janv.", "Févr.", "Mars", "Avr.", "Mai", "Juin", "Juil.", "Août", "Sept.", "Oct.", "Nov.", "Déc."]

# Sous-dossiers du Drive du club (créés par l'application, voir Paramètres → Drive)
DOSSIERS_DRIVE = ["Sauvegardes", "Factures et reçus", "Reçus fiscaux", "Rapports", "Relevés bancaires",
                  "Justificatifs", "Imports", "Logo"]

# Modèle d'import Excel générique
COLONNES_IMPORT = ["Date", "Sens", "Catégorie", "Libellé", "Montant", "Source", "Mode de paiement", "Tiers",
                   "N° pièce", "Notes", "Rapproché"]
