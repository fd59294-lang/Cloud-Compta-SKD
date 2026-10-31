/**
 * ============================================================================
 *  GESTION DU CLUB — Google Apps Script (fichier Code.gs complet)
 *  Version 2.0 — 28/10/2026
 *
 *  Ce fichier ne contient AUCUNE donnée du club : nom, adresse, IBAN, SIRET,
 *  tarifs… sont lus dans l'onglet "Configuration" du Google Sheets.
 *  Il peut donc être versionné sur GitHub sans risque.
 *
 *  Onglets utilisés : Operations_Historique, Membres_Cotisations,
 *                     Dons_Recus (créé si absent), Configuration, Dashboard
 *  Dossiers Drive    : 01_Données_Principales (logo), 02_Factures_PDF,
 *                     06_Sauvegardes
 * ============================================================================
 */

// ---------------------------------------------------------------------------
// 1. CONSTANTES
// ---------------------------------------------------------------------------

const TZ = 'Europe/Paris';

const ONGLET = {
  OPERATIONS: 'Operations_Historique',
  MEMBRES: 'Membres_Cotisations',
  DONS: 'Dons_Recus',
  CONFIG: 'Configuration',
  CATEGORIES: 'Categories',
  DASHBOARD: 'Dashboard',
  BUDGET: 'Budget'
};

const DOSSIER = {
  DONNEES: '01_Données_Principales',
  DOCUMENTS: '02_Factures_PDF',
  RELEVES: '03_Relevés_Bancaires',
  JUSTIFS: '04_Justificatifs',
  ARCHIVES: '05_Archives_Annuelles',
  SAUVEGARDES: '06_Sauvegardes'
};

// Identifiant de chaque dossier, enregistré dans l'onglet Configuration par « Installer les dossiers »
const CLE_DOSSIER = {
  '01_Données_Principales': 'Dossier_Donnees_ID',
  '02_Factures_PDF': 'Dossier_Documents_ID',
  '03_Relevés_Bancaires': 'Dossier_Releves_ID',
  '04_Justificatifs': 'Dossier_Justificatifs_ID',
  '05_Archives_Annuelles': 'Dossier_Archives_ID',
  '06_Sauvegardes': 'Dossier_Sauvegardes_ID'
};
const NOM_DOSSIER_RACINE = 'Comptabilité Association';

// Colonnes (index à partir de 0)
const OP = { DATE: 0, LIBELLE: 1, MONTANT: 2, TYPE: 3, CATEGORIE: 4, TIERS: 5, NOTES: 6,
             PIECE: 7, SOURCE: 8, RAPPROCHE: 9, SOLDE: 10, NB: 11, JUSTIF: 11 };

const M = { ID: 0, LICENCE: 1, NOM: 2, EMAIL: 3, TEL: 4, ADRESSE: 5, COTISATION: 6,
            DATE_ADHESION: 7, STATUT: 8, DATE_PAIEMENT: 9, MONTANT_PAYE: 10, NOTES: 11,
            FRAIS_ADHESION: 12, STATUT_ADHESION: 13, DATE_PAIEMENT_ADHESION: 14, TOTAL_DU: 15, NB: 16 };

const D = { ID: 0, DATE: 1, NOM: 2, ADRESSE: 3, EMAIL: 4, MONTANT: 5, NATURE: 6, MODE: 7, NUMERO: 8, NB: 9 };

const ENTETES = {
  OPERATIONS: ['Date', 'Libelle', 'Montant', 'Type', 'Categorie', 'Tiers', 'Notes', 'Numero_Piece',
               'Source', 'Rapproche', 'Solde_Cumule', 'Justificatif'],
  BUDGET: ['Exercice', 'Categorie', 'Type', 'Montant_Prevu'],
  MEMBRES: ['ID_Membre', 'Numero_Licence_FFKarate', 'Nom_Prenom', 'Email', 'Telephone', 'Adresse',
            'Cotisation_Annuelle', 'Date_Adhesion', 'Statut_Saison', 'Date_Paiement', 'Montant_Paye',
            'Notes_Membre', 'Frais_Adhesion', 'Statut_Adhesion', 'Date_Paiement_Adhesion', 'Total_Du'],
  DONS: ['ID_Don', 'Date_Don', 'Nom_Donateur', 'Adresse_Complete', 'Email', 'Montant', 'Nature_Don',
         'Mode_Versement', 'Numero_Recu']
};

// Clés de l'onglet Configuration et valeur par défaut
const CONFIG_CLES = [
  ['Nom_Association', ''],
  ['Objet_Association', ''],
  ['Adresse', ''],
  ['Code_Postal_Ville', ''],
  ['Ville_Signature', ''],
  ['Email', ''],
  ['Telephone', ''],
  ['IBAN', ''],
  ['RNA', ''],
  ['SIRET', ''],
  ['Affiliation_FFKda', ''],
  ['President', ''],
  ['Tresorier', ''],
  ['Logo_Fichier', 'Logo_Sensei_Karate_Do.png'],
  ['Tarif_Adhesion', '20'],
  ['Tarif_Cotisation', '50'],
  ['Mois_Debut_Exercice', '9'],
  ['Dernier_Numero_Recu', '0'],
  ['Dernier_Numero_Facture', '0'],
  ['Dernier_Numero_Recu_Fiscal', '0']
];

const MODES_PAIEMENT = ['Chèque', 'Virement', 'Espèces', "Pass'Sport", 'Carte bancaire'];

const COULEUR = { ROUGE: '#c8102e', NOIR: '#1a1a1a', VERT: '#2e7d32', GRIS: '#9e9e9e' };

// ---------------------------------------------------------------------------
// 2. MENU
// ---------------------------------------------------------------------------

function onOpen() {
  const ui = SpreadsheetApp.getUi();
  ui.createMenu('🏛️ Association')
    .addItem('➕ Nouvelle opération', 'nouvelleOperation')
    .addSeparator()
    .addSubMenu(ui.createMenu('👥 Adhérents')
      .addItem('➕ Nouvel adhérent / Réinscription', 'nouvelAdherent')
      .addItem('🔍 Rechercher (licence ou ID)', 'rechercherAdherent')
      .addItem('💰 Enregistrer un paiement', 'paiementAdherent')
      .addItem('🧾 Générer une facture', 'factureAdherent'))
    .addSubMenu(ui.createMenu('🎁 Dons & reçus fiscaux')
      .addItem('➕ Saisir un don', 'saisirDon')
      .addItem('📜 (Re)générer un reçu fiscal', 'recuFiscalDon'))
    .addSubMenu(ui.createMenu('📊 Rapports')
      .addItem('📈 Bilan financier (PDF)', 'bilanFinancier')
      .addItem('🏆 Rapport AGO (Google Doc modifiable)', 'rapportAGO')
      .addItem('📉 Comparaison de deux exercices (PDF)', 'analyseComparative'))
    .addSeparator()
    .addItem('📊 Tableau de bord', 'tableauDeBord')
    .addItem('💾 Sauvegarde maintenant', 'sauvegardeManuelle')
    .addSeparator()
    .addSubMenu(ui.createMenu('🔧 Maintenance')
      .addItem('Installer les dossiers Drive', 'installerDossiers')
      .addItem('Compléter l\'onglet Configuration', 'completerConfiguration')
      .addItem('Vérifier la structure des onglets', 'verifierStructure'))
    .addToUi();
}

// ---------------------------------------------------------------------------
// 3. OUTILS GÉNÉRAUX (fonctions privées : nom terminé par "_")
// ---------------------------------------------------------------------------

function feuille_(nom) {
  const sh = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(nom);
  if (!sh) throw new Error('Onglet "' + nom + '" introuvable');
  return sh;
}

/**
 * Retrouve un dossier du club : d'abord par son identifiant (onglet Configuration),
 * sinon à côté du Google Sheets, sinon par son nom dans tout le Drive.
 */
function dossier_(nom) {
  const cle = CLE_DOSSIER[nom];
  if (cle) {
    const id = texte_(lireConfiguration()[cle]);
    if (id) {
      try { return DriveApp.getFolderById(id); } catch (e) { /* identifiant périmé : on cherche autrement */ }
    }
  }
  try {
    const racine = racineClub_();
    if (racine) {
      const local = racine.getFoldersByName(nom);
      if (local.hasNext()) return local.next();
    }
  } catch (e) { /* on continue */ }
  const it = DriveApp.getFoldersByName(nom);
  if (!it.hasNext()) throw new Error('Dossier "' + nom + '" introuvable : lancez 🔧 Maintenance → Installer les dossiers');
  return it.next();
}

/** Dossier racine du club = parent du dossier qui contient le Google Sheets. */
function racineClub_() {
  const fichier = DriveApp.getFileById(SpreadsheetApp.getActiveSpreadsheet().getId());
  const parents = fichier.getParents();
  if (!parents.hasNext()) return null;
  const p = parents.next();
  if (p.getName() === '01_Données_Principales') {
    const gp = p.getParents();
    return gp.hasNext() ? gp.next() : p;
  }
  return p.getName() === NOM_DOSSIER_RACINE ? p : null;
}

function ecrireConfig_(cle, valeur) {
  const sh = feuille_(ONGLET.CONFIG);
  const vals = sh.getDataRange().getValues();
  for (let i = 1; i < vals.length; i++) {
    if (texte_(vals[i][0]) === cle) { sh.getRange(i + 1, 2).setValue(valeur); return; }
  }
  sh.appendRow([cle, valeur]);
}

function texte_(v) {
  return v === null || v === undefined ? '' : String(v).trim();
}

function nombre_(v) {
  if (typeof v === 'number') return v;
  const s = texte_(v).replace(/\s/g, '').replace('€', '').replace(',', '.');
  if (s === '') return NaN;
  const n = parseFloat(s);
  return isNaN(n) ? NaN : n;
}

function nombreOu_(v, defaut) {
  const n = nombre_(v);
  return isNaN(n) ? defaut : n;
}

function arrondi_(n) {
  return Math.round((Number(n) || 0) * 100) / 100;
}

function euros_(n) {
  const v = arrondi_(n);
  const parts = Math.abs(v).toFixed(2).split('.');
  const entier = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, ' ');
  return (v < 0 ? '-' : '') + entier + ',' + parts[1] + ' €';
}

function dateFr_(d) {
  const x = versDate_(d);
  return x ? Utilities.formatDate(x, TZ, 'dd/MM/yyyy') : '';
}

function versDate_(v) {
  if (v instanceof Date) return isNaN(v) ? null : v;
  const s = texte_(v);
  if (!s) return null;
  let m = s.match(/^(\d{1,2})[\/.-](\d{1,2})[\/.-](\d{2}|\d{4})$/);
  if (m) {
    const a = m[3].length === 2 ? 2000 + Number(m[3]) : Number(m[3]);
    return new Date(a, Number(m[2]) - 1, Number(m[1]));
  }
  m = s.match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (m) return new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]));
  return null;
}

function normaliserLicence_(v) {
  return texte_(v).replace(/\s/g, '').toUpperCase();
}

function memeId_(a, b) {
  const sa = texte_(a), sb = texte_(b);
  if (!sa || !sb) return false;
  const na = Number(sa), nb = Number(sb);
  if (!isNaN(na) && !isNaN(nb)) return na === nb;
  return sa === sb;
}

function sourceDepuisMode_(mode) {
  return mode === 'Espèces' ? 'Especes' : 'Banque';
}

/** Boîte de saisie. Renvoie null si l'utilisateur annule. */
function demander_(message, defaut) {
  const ui = SpreadsheetApp.getUi();
  const aDefaut = defaut !== undefined && defaut !== null && String(defaut) !== '';
  const txt = aDefaut ? message + '\n\n(Laisser vide = ' + defaut + ')' : message;
  const r = ui.prompt('Gestion du club', txt, ui.ButtonSet.OK_CANCEL);
  if (r.getSelectedButton() !== ui.Button.OK) return null;
  const v = r.getResponseText().trim();
  return v === '' && aDefaut ? String(defaut) : v;
}

function confirmer_(message) {
  const ui = SpreadsheetApp.getUi();
  return ui.alert('Gestion du club', message, ui.ButtonSet.YES_NO) === ui.Button.YES;
}

function info_(message) {
  SpreadsheetApp.getUi().alert('Gestion du club', message, SpreadsheetApp.getUi().ButtonSet.OK);
}

/** Exécute une action du menu en affichant proprement les erreurs. */
function proteger_(fn) {
  try {
    return fn();
  } catch (e) {
    info_('❌ ' + (e && e.message ? e.message : e));
  }
}

// ---------------------------------------------------------------------------
// 4. CONFIGURATION
// ---------------------------------------------------------------------------

function lireConfiguration() {
  const cfg = {};
  CONFIG_CLES.forEach(function (c) { cfg[c[0]] = c[1]; });
  const vals = feuille_(ONGLET.CONFIG).getDataRange().getValues();
  for (let i = 1; i < vals.length; i++) {
    const cle = texte_(vals[i][0]);
    if (!cle) continue;
    const v = vals[i][1];
    if (texte_(v) !== '') cfg[cle] = v;
    else if (!(cle in cfg)) cfg[cle] = '';
  }
  return cfg;
}

/** Valeur affichable ; signale clairement un champ non renseigné. */
function champ_(cfg, cle) {
  const v = texte_(cfg[cle]);
  return v || '[' + cle + ' à renseigner]';
}

/** Ajoute dans l'onglet Configuration les clés manquantes (n'écrase rien). */
function completerConfiguration() {
  proteger_(function () {
    const sh = feuille_(ONGLET.CONFIG);
    const vals = sh.getDataRange().getValues();
    const existantes = {};
    for (let i = 1; i < vals.length; i++) existantes[texte_(vals[i][0])] = true;
    if (texte_(vals[0][0]) === '') sh.getRange(1, 1, 1, 2).setValues([['Parametre', 'Valeur']]);
    const ajouts = CONFIG_CLES.filter(function (c) { return !existantes[c[0]]; });
    if (ajouts.length) {
      sh.getRange(sh.getLastRow() + 1, 1, ajouts.length, 2).setValues(ajouts);
    }
    info_(ajouts.length
      ? '✅ ' + ajouts.length + ' paramètre(s) ajouté(s) :\n\n' + ajouts.map(function (c) { return '• ' + c[0]; }).join('\n') +
        '\n\nRenseignez-les dans l\'onglet Configuration (colonne B).'
      : '✅ L\'onglet Configuration est complet.');
  });
}

/** Numérotation chronologique sans trou (verrouillée). */
function prochainNumero_(cle) {
  const lock = LockService.getScriptLock();
  lock.waitLock(15000);
  try {
    const sh = feuille_(ONGLET.CONFIG);
    const vals = sh.getDataRange().getValues();
    let n = 0, ligne = -1;
    for (let i = 1; i < vals.length; i++) {
      if (texte_(vals[i][0]) === cle) { n = Number(vals[i][1]) || 0; ligne = i + 1; break; }
    }
    n++;
    if (ligne > 0) sh.getRange(ligne, 2).setValue(n);
    else sh.appendRow([cle, n]);
    SpreadsheetApp.flush();
    return n;
  } finally {
    lock.releaseLock();
  }
}

// ---------------------------------------------------------------------------
// 5. EXERCICE / SAISON
// ---------------------------------------------------------------------------

function moisDebut_(cfg) {
  const m = Number(cfg.Mois_Debut_Exercice) || 1;
  return Math.min(12, Math.max(1, m));
}

function periodeExercice_(annee, cfg) {
  const m = moisDebut_(cfg);
  const a = Number(annee);
  return {
    annee: a,
    debut: new Date(a, m - 1, 1),
    fin: new Date(a + 1, m - 1, 1),
    moisDebut: m,
    libelle: m === 1 ? 'Exercice ' + a : 'Saison ' + a + '-' + (a + 1)
  };
}

function exerciceCourant_(cfg) {
  const now = new Date();
  return (now.getMonth() + 1) >= moisDebut_(cfg) ? now.getFullYear() : now.getFullYear() - 1;
}

function dansPeriode_(v, p) {
  const d = versDate_(v);
  return !!d && d >= p.debut && d < p.fin;
}

// ---------------------------------------------------------------------------
// 6. COMPTABILITÉ
// ---------------------------------------------------------------------------

/**
 * Ajoute une écriture. op = { date, libelle, montant (positif), type 'Recette'|'Depense',
 * categorie, tiers, notes, piece, source 'Banque'|'Especes' }
 * Le montant est signé automatiquement (dépense = négatif), comme dans l'historique.
 */
function ajouterLigneOperation_(op) {
  const sh = feuille_(ONGLET.OPERATIONS);
  const date = versDate_(op.date);
  const montant = Math.abs(nombre_(op.montant));
  if (!date) throw new Error('Date invalide');
  if (!texte_(op.libelle)) throw new Error('Le libellé est obligatoire');
  if (!(montant > 0)) throw new Error('Montant invalide');
  const type = op.type === 'Depense' ? 'Depense' : 'Recette';
  const source = op.source === 'Especes' ? 'Especes' : 'Banque';
  const ligne = sh.getLastRow() + 1;
  sh.getRange(ligne, 1, 1, OP.NB - 1).setValues([[
    date, texte_(op.libelle), type === 'Depense' ? -montant : montant, type,
    texte_(op.categorie) || 'Autres', texte_(op.tiers), texte_(op.notes), texte_(op.piece),
    source, !!op.rapproche
  ]]);
  const formule = ligne === 2
    ? '=IF(I2="Banque",C2,0)'
    : '=K' + (ligne - 1) + '+IF(I' + ligne + '="Banque",C' + ligne + ',0)';
  sh.getRange(ligne, OP.SOLDE + 1).setFormula(formule);
  return ligne;
}

function nouvelleOperation() {
  proteger_(function () {
    const d = demander_('Date (JJ/MM/AAAA)', dateFr_(new Date())); if (d === null) return;
    const date = versDate_(d); if (!date) throw new Error('Date invalide : ' + d);
    const libelle = demander_('Libellé'); if (!libelle) return;
    const montant = demander_('Montant en € (toujours positif, ex : 25,60)'); if (montant === null) return;
    const t = demander_('Type :\n1 = Recette\n2 = Dépense', '2'); if (t === null) return;
    const categorie = demander_('Catégorie', 'Autres'); if (categorie === null) return;
    const s = demander_('Source :\n1 = Banque\n2 = Espèces', '1'); if (s === null) return;
    const tiers = demander_('Tiers (optionnel)', ''); if (tiers === null) return;
    const notes = demander_('Notes (optionnel)', ''); if (notes === null) return;
    ajouterLigneOperation_({
      date: date, libelle: libelle, montant: montant, type: t === '1' ? 'Recette' : 'Depense',
      categorie: categorie, tiers: tiers, notes: notes, source: s === '2' ? 'Especes' : 'Banque'
    });
    info_('✅ Opération enregistrée : ' + libelle + ' (' + euros_(nombre_(montant)) + ')');
  });
}

function listerCategories_() {
  const set = {};
  try {
    const cat = feuille_(ONGLET.CATEGORIES).getDataRange().getValues();
    for (let i = 1; i < cat.length; i++) if (texte_(cat[i][1])) set[texte_(cat[i][1])] = true;
  } catch (e) { /* onglet absent : on continue */ }
  const ops = feuille_(ONGLET.OPERATIONS).getDataRange().getValues();
  for (let i = 1; i < ops.length; i++) if (texte_(ops[i][OP.CATEGORIE])) set[texte_(ops[i][OP.CATEGORIE])] = true;
  set['Cotisations'] = true; set['Dons'] = true; set['Autres'] = true;
  return Object.keys(set).sort(function (a, b) { return a.localeCompare(b, 'fr'); });
}

// ---------------------------------------------------------------------------
// 7. ADHÉRENTS
// ---------------------------------------------------------------------------

function lireMembres_() {
  const sh = feuille_(ONGLET.MEMBRES);
  return { sh: sh, vals: sh.getDataRange().getValues() };
}

function completerLigne_(r) {
  const x = r.slice(0, M.NB);
  while (x.length < M.NB) x.push('');
  return x;
}

/** Cherche par numéro de licence, puis par ID interne. */
function trouverMembre_(cle) {
  const lm = lireMembres_();
  const lic = normaliserLicence_(cle);
  if (!lic) return null;
  for (let i = 1; i < lm.vals.length; i++) {
    if (normaliserLicence_(lm.vals[i][M.LICENCE]) === lic) return { sh: lm.sh, ligne: i + 1, r: completerLigne_(lm.vals[i]) };
  }
  for (let i = 1; i < lm.vals.length; i++) {
    if (memeId_(lm.vals[i][M.ID], cle)) return { sh: lm.sh, ligne: i + 1, r: completerLigne_(lm.vals[i]) };
  }
  return null;
}

function trouverParLicence_(licence) {
  const lm = lireMembres_();
  const lic = normaliserLicence_(licence);
  if (!lic) return null;
  for (let i = 1; i < lm.vals.length; i++) {
    if (normaliserLicence_(lm.vals[i][M.LICENCE]) === lic) return { sh: lm.sh, ligne: i + 1, r: completerLigne_(lm.vals[i]) };
  }
  return null;
}

function prochainIdMembre_(vals) {
  let max = 0;
  for (let i = 1; i < vals.length; i++) {
    const n = Number(vals[i][M.ID]);
    if (!isNaN(n) && n > max) max = n;
  }
  return String(max + 1).padStart(3, '0');
}

function etatMembre_(r) {
  const frais = nombreOu_(r[M.FRAIS_ADHESION], 0);
  const cotisation = nombreOu_(r[M.COTISATION], 0);
  const paye = nombreOu_(r[M.MONTANT_PAYE], 0);
  const adhesionDue = texte_(r[M.STATUT_ADHESION]) === 'Impayée' && frais > 0;
  const cotisationRestante = Math.max(0, arrondi_(cotisation - paye));
  return {
    id: texte_(r[M.ID]),
    licence: texte_(r[M.LICENCE]),
    nom: texte_(r[M.NOM]),
    email: texte_(r[M.EMAIL]),
    tel: texte_(r[M.TEL]),
    adresse: texte_(r[M.ADRESSE]),
    statut: texte_(r[M.STATUT]),
    statutAdhesion: texte_(r[M.STATUT_ADHESION]),
    frais: frais,
    cotisation: cotisation,
    paye: paye,
    adhesionDue: adhesionDue,
    cotisationRestante: cotisationRestante,
    resteDu: arrondi_((adhesionDue ? frais : 0) + cotisationRestante)
  };
}

function ecrireMembre_(t, r) {
  const e = etatMembre_(r);
  r[M.TOTAL_DU] = e.resteDu;
  t.sh.getRange(t.ligne, M.ID + 1, 1, 2).setNumberFormat('@');
  t.sh.getRange(t.ligne, 1, 1, M.NB).setValues([r]);
}

/**
 * Crée un adhérent ou, si la licence existe déjà, le réinscrit pour la saison.
 * a = { licence, nom, email, tel, adresse, cotisation, fraisAdhesion, notes, forcer }
 */
function enregistrerAdherent_(a) {
  const cfg = lireConfiguration();
  const licence = texte_(a.licence);
  if (!licence) throw new Error('Le numéro de licence FFKaraté est obligatoire');
  const t = trouverParLicence_(licence);
  return t ? reinscrire_(t, a, cfg) : creerAdherent_(a, cfg);
}

function creerAdherent_(a, cfg) {
  const nom = texte_(a.nom);
  if (!nom) throw new Error('Le nom est obligatoire');
  const lm = lireMembres_();
  const frais = nombreOu_(a.fraisAdhesion, nombreOu_(cfg.Tarif_Adhesion, 0));
  const cotisation = nombreOu_(a.cotisation, nombreOu_(cfg.Tarif_Cotisation, 0));
  const id = prochainIdMembre_(lm.vals);
  const ligne = lm.sh.getLastRow() + 1;
  const r = completerLigne_([]);
  r[M.ID] = id;
  r[M.LICENCE] = normaliserLicence_(a.licence);
  r[M.NOM] = nom;
  r[M.EMAIL] = texte_(a.email);
  r[M.TEL] = texte_(a.tel);
  r[M.ADRESSE] = texte_(a.adresse);
  r[M.COTISATION] = cotisation;
  r[M.DATE_ADHESION] = new Date();
  r[M.STATUT] = 'Nouveau';
  r[M.MONTANT_PAYE] = 0;
  r[M.NOTES] = texte_(a.notes);
  r[M.FRAIS_ADHESION] = frais;
  r[M.STATUT_ADHESION] = frais > 0 ? 'Impayée' : 'Payée';
  ecrireMembre_({ sh: lm.sh, ligne: ligne }, r);
  const e = etatMembre_(r);
  return {
    type: 'creation',
    message: '✅ Nouvel adhérent : ' + nom + ' (licence ' + r[M.LICENCE] + ')\nÀ régler : ' + euros_(e.resteDu) +
             ' (adhésion ' + euros_(frais) + ' + cotisation ' + euros_(cotisation) + ')'
  };
}

function reinscrire_(t, a, cfg) {
  const r = t.r;
  const p = periodeExercice_(exerciceCourant_(cfg), cfg);
  const dejaPaye = nombreOu_(r[M.MONTANT_PAYE], 0) > 0 && dansPeriode_(r[M.DATE_PAIEMENT], p);
  if (dejaPaye && !a.forcer) {
    throw new Error('DEJA_A_JOUR: ' + texte_(r[M.NOM]) + ' a déjà réglé ' + euros_(r[M.MONTANT_PAYE]) +
                    ' pour la ' + p.libelle + '. Réinscrire quand même remettrait ce paiement à zéro.');
  }
  if (texte_(a.nom)) r[M.NOM] = texte_(a.nom);
  if (texte_(a.email)) r[M.EMAIL] = texte_(a.email);
  if (texte_(a.tel)) r[M.TEL] = texte_(a.tel);
  if (texte_(a.adresse)) r[M.ADRESSE] = texte_(a.adresse);
  if (texte_(a.notes)) r[M.NOTES] = texte_(a.notes);
  r[M.COTISATION] = nombreOu_(a.cotisation, nombreOu_(cfg.Tarif_Cotisation, nombreOu_(r[M.COTISATION], 0)));
  r[M.STATUT] = 'Réinscription';
  r[M.DATE_PAIEMENT] = '';
  r[M.MONTANT_PAYE] = 0;
  if (texte_(r[M.STATUT_ADHESION]) === '') r[M.STATUT_ADHESION] = 'Payée';
  ecrireMembre_(t, r);
  const e = etatMembre_(r);
  return {
    type: 'reinscription',
    message: '🔁 Réinscription de ' + e.nom + ' pour la ' + p.libelle + '\nÀ régler : ' + euros_(e.resteDu) +
             (e.adhesionDue ? ' (dont adhésion ' + euros_(e.frais) + ' encore due)' : ' (pas de frais d\'adhésion)')
  };
}

function nouvelAdherent() {
  proteger_(function () {
    const cfg = lireConfiguration();
    const licence = demander_('Numéro de licence FFKaraté'); if (!licence) return;
    const t = trouverParLicence_(licence);
    if (t) {
      const e = etatMembre_(t.r);
      if (!confirmer_('Licence connue : ' + e.nom + '\n' + e.email + ' – ' + e.tel + '\n' + e.adresse +
                      '\n\nRéinscrire pour la ' + periodeExercice_(exerciceCourant_(cfg), cfg).libelle + ' ?')) return;
      const email = demander_('Email', e.email); if (email === null) return;
      const tel = demander_('Téléphone', e.tel); if (tel === null) return;
      const adresse = demander_('Adresse', e.adresse); if (adresse === null) return;
      const cot = demander_('Cotisation de la saison (€)', texte_(cfg.Tarif_Cotisation)); if (cot === null) return;
      const a = { licence: licence, email: email, tel: tel, adresse: adresse, cotisation: cot };
      let res;
      try {
        res = enregistrerAdherent_(a);
      } catch (err) {
        if (String(err.message).indexOf('DEJA_A_JOUR') !== 0) throw err;
        if (!confirmer_(String(err.message).replace('DEJA_A_JOUR: ', '') + '\n\nContinuer ?')) return;
        a.forcer = true;
        res = enregistrerAdherent_(a);
      }
      return info_(res.message);
    }
    const nom = demander_('Nouvelle licence.\n\nNom et prénom'); if (!nom) return;
    const email = demander_('Email', ''); if (email === null) return;
    const tel = demander_('Téléphone', ''); if (tel === null) return;
    const adresse = demander_('Adresse complète', ''); if (adresse === null) return;
    const frais = demander_('Frais d\'adhésion (€)', texte_(cfg.Tarif_Adhesion)); if (frais === null) return;
    const cot = demander_('Cotisation annuelle (€)', texte_(cfg.Tarif_Cotisation)); if (cot === null) return;
    const notes = demander_('Notes (optionnel)', ''); if (notes === null) return;
    const res = enregistrerAdherent_({ licence: licence, nom: nom, email: email, tel: tel, adresse: adresse,
                                       fraisAdhesion: frais, cotisation: cot, notes: notes });
    info_(res.message);
  });
}

function rechercherAdherent() {
  proteger_(function () {
    const cle = demander_('Numéro de licence (ou ID interne)'); if (!cle) return;
    const t = trouverMembre_(cle);
    if (!t) throw new Error('Aucun adhérent pour : ' + cle);
    const e = etatMembre_(t.r);
    info_('🔢 Licence : ' + (e.licence || '—') + '   (ID ' + e.id + ')\n👤 ' + e.nom + '\n📧 ' + e.email +
          '\n📱 ' + e.tel + '\n🏠 ' + e.adresse + '\n\nSaison : ' + e.statut + ' – payé ' + euros_(e.paye) +
          ' / ' + euros_(e.cotisation) + '\nAdhésion : ' + (e.statutAdhesion || '—') + '\nReste dû : ' + euros_(e.resteDu));
  });
}

/**
 * Enregistre un paiement.
 * p = { cle, nature 'adhesion'|'cotisation'|'les_deux', montant, mode, date, compta (bool), recu (bool) }
 */
function enregistrerPaiement_(p) {
  const cfg = lireConfiguration();
  const t = trouverMembre_(p.cle);
  if (!t) throw new Error('Adhérent introuvable : ' + p.cle);
  const r = t.r;
  const e = etatMembre_(r);
  const montant = arrondi_(nombre_(p.montant));
  if (!(montant > 0)) throw new Error('Montant invalide');
  const date = versDate_(p.date) || new Date();
  const mode = MODES_PAIEMENT.indexOf(p.mode) >= 0 ? p.mode : 'Chèque';
  const saison = periodeExercice_(exerciceCourant_(cfg), cfg).libelle;

  let partAdh = 0, partCot = 0;
  if (p.nature === 'adhesion') {
    if (e.frais > 0 && montant < e.frais) throw new Error('Le montant ne couvre pas les frais d\'adhésion (' + euros_(e.frais) + ')');
    partAdh = montant;
  } else if (p.nature === 'cotisation') {
    partCot = montant;
  } else if (p.nature === 'les_deux') {
    if (montant < e.frais) throw new Error('Le montant ne couvre pas les frais d\'adhésion (' + euros_(e.frais) + ')');
    partAdh = e.frais;
    partCot = arrondi_(montant - e.frais);
  } else {
    throw new Error('Nature de paiement inconnue');
  }

  if (partAdh > 0) {
    r[M.STATUT_ADHESION] = 'Payée';
    r[M.DATE_PAIEMENT_ADHESION] = date;
  }
  if (partCot > 0) {
    const paye = arrondi_(nombreOu_(r[M.MONTANT_PAYE], 0) + partCot);
    r[M.MONTANT_PAYE] = paye;
    r[M.DATE_PAIEMENT] = date;
    r[M.STATUT] = paye >= e.cotisation ? 'À jour' : 'Paiement partiel';
  }
  ecrireMembre_(t, r);

  const objet = partAdh > 0 && partCot > 0 ? 'Adhésion + cotisation ' + saison
              : partAdh > 0 ? 'Frais d\'adhésion (première inscription)'
              : 'Cotisation ' + saison;

  let doc = null;
  if (p.recu) doc = creerRecuPaiement_(cfg, etatMembre_(r), objet, montant, mode, date);

  if (p.compta) {
    ajouterLigneOperation_({
      date: date, libelle: objet + ' – ' + e.nom, montant: montant, type: 'Recette',
      categorie: 'Cotisations', tiers: e.nom, notes: 'Mode : ' + mode + (e.licence ? ' – licence ' + e.licence : ''),
      piece: doc ? doc.numero : '', source: sourceDepuisMode_(mode)
    });
  }

  const apres = etatMembre_(r);
  return {
    message: '✅ Paiement de ' + euros_(montant) + ' enregistré pour ' + e.nom +
             (p.compta ? '\n📒 Écriture ajoutée en comptabilité' : '') +
             (doc ? '\n🧾 Reçu ' + doc.numero : '') +
             '\nReste dû : ' + euros_(apres.resteDu),
    url: doc ? doc.url : ''
  };
}

function paiementAdherent() {
  proteger_(function () {
    const cle = demander_('Numéro de licence (ou ID interne)'); if (!cle) return;
    const t = trouverMembre_(cle);
    if (!t) throw new Error('Aucun adhérent pour : ' + cle);
    const e = etatMembre_(t.r);
    if (e.resteDu <= 0 && !confirmer_(e.nom + ' est à jour. Enregistrer quand même un paiement ?')) return;
    const defautChoix = e.adhesionDue && e.cotisationRestante > 0 ? '3' : (e.adhesionDue ? '1' : '2');
    const choix = demander_(e.nom + '\nAdhésion : ' + (e.adhesionDue ? euros_(e.frais) + ' à payer' : 'réglée') +
                            '\nCotisation : reste ' + euros_(e.cotisationRestante) +
                            '\n\n1 = Adhésion\n2 = Cotisation\n3 = Adhésion + cotisation', defautChoix);
    if (choix === null) return;
    const nature = { '1': 'adhesion', '2': 'cotisation', '3': 'les_deux' }[choix];
    if (!nature) throw new Error('Choix invalide');
    const defautMontant = nature === 'adhesion' ? e.frais : nature === 'cotisation' ? e.cotisationRestante : e.resteDu;
    const montant = demander_('Montant reçu (€)', String(defautMontant).replace('.', ',')); if (montant === null) return;
    const m = demander_('Mode de paiement :\n' + MODES_PAIEMENT.map(function (x, i) { return (i + 1) + ' = ' + x; }).join('\n'), '1');
    if (m === null) return;
    const mode = MODES_PAIEMENT[Number(m) - 1];
    if (!mode) throw new Error('Mode invalide');
    const d = demander_('Date du paiement (JJ/MM/AAAA)', dateFr_(new Date())); if (d === null) return;
    const compta = confirmer_('Ajouter aussi l\'écriture en comptabilité ?');
    const recu = confirmer_('Générer le reçu PDF ?');
    const res = enregistrerPaiement_({ cle: cle, nature: nature, montant: montant, mode: mode, date: versDate_(d),
                                       compta: compta, recu: recu });
    info_(res.message + (res.url ? '\n\n📁 Dossier ' + DOSSIER.DOCUMENTS : ''));
  });
}

function factureAdherent() {
  proteger_(function () {
    const cle = demander_('Numéro de licence (ou ID interne)'); if (!cle) return;
    const doc = genererFacture_(cle);
    info_('🧾 Facture ' + doc.numero + ' créée (' + euros_(doc.total) + ')\n📁 Dossier ' + DOSSIER.DOCUMENTS);
  });
}

// ---------------------------------------------------------------------------
// 8. DOCUMENTS PDF (en-tête club, tableaux, logo)
// ---------------------------------------------------------------------------

function logoBlob_(cfg) {
  const nom = texte_(cfg.Logo_Fichier);
  if (!nom) return null;
  try {
    const it = dossier_(DOSSIER.DONNEES).getFilesByName(nom);
    if (it.hasNext()) return it.next().getBlob();
    const it2 = DriveApp.getFilesByName(nom);
    if (it2.hasNext()) return it2.next().getBlob();
  } catch (e) { /* pas de logo */ }
  return null;
}

function para_(body, txt, o) {
  o = o || {};
  const p = body.appendParagraph(txt === undefined || txt === null ? '' : String(txt));
  p.setSpacingBefore(o.avant || 0).setSpacingAfter(o.apres === undefined ? 4 : o.apres);
  if (o.align === 'centre') p.setAlignment(DocumentApp.HorizontalAlignment.CENTER);
  if (o.align === 'droite') p.setAlignment(DocumentApp.HorizontalAlignment.RIGHT);
  if (p.getText().length) {
    const t = p.editAsText();
    t.setFontFamily('Arial').setFontSize(o.taille || 10).setBold(!!o.gras).setItalic(!!o.italique)
     .setForegroundColor(o.couleur || COULEUR.NOIR);
  }
  return p;
}

function titre_(body, txt, o) {
  o = o || {};
  return para_(body, txt, { taille: o.taille || 13, gras: true, align: o.align || 'centre',
                            couleur: o.couleur || COULEUR.ROUGE, avant: o.avant || 6, apres: o.apres || 6 });
}

function tableau_(body, lignes, o) {
  o = o || {};
  const t = body.appendTable(lignes.map(function (l) { return l.map(function (c) { return String(c); }); }));
  t.setBorderColor('#bdbdbd');
  t.editAsText().setFontFamily('Arial').setFontSize(o.taille || 9);
  for (let i = 0; i < t.getNumRows(); i++) {
    const row = t.getRow(i);
    for (let j = 0; j < row.getNumCells(); j++) {
      const cell = row.getCell(j);
      cell.setPaddingTop(2).setPaddingBottom(2).setPaddingLeft(4).setPaddingRight(4);
      if (i === 0) {
        cell.setBackgroundColor(o.couleur || COULEUR.NOIR);
        cell.editAsText().setForegroundColor('#ffffff').setBold(true);
      }
      if ((o.droite || []).indexOf(j) >= 0 && cell.getNumChildren() > 0) {
        cell.getChild(0).asParagraph().setAlignment(DocumentApp.HorizontalAlignment.RIGHT);
      }
    }
  }
  if (o.totalDerniere) {
    const der = t.getRow(t.getNumRows() - 1);
    der.editAsText().setBold(true);
    for (let j = 0; j < der.getNumCells(); j++) der.getCell(j).setBackgroundColor('#f2f2f2');
  }
  return t;
}

function enTeteClub_(body, cfg) {
  const p0 = body.getParagraphs()[0];
  p0.setAlignment(DocumentApp.HorizontalAlignment.CENTER).setSpacingAfter(2);
  const logo = logoBlob_(cfg);
  if (logo) {
    const img = p0.appendInlineImage(logo);
    const ratio = img.getHeight() / img.getWidth();
    img.setWidth(70).setHeight(Math.round(70 * ratio));
  }
  para_(body, champ_(cfg, 'Nom_Association').toUpperCase(), { taille: 15, gras: true, align: 'centre', apres: 0 });
  para_(body, [texte_(cfg.Adresse), texte_(cfg.Code_Postal_Ville)].filter(String).join(' – '), { taille: 9, align: 'centre', apres: 0 });
  para_(body, [texte_(cfg.Email), texte_(cfg.Telephone)].filter(String).join(' – '), { taille: 9, align: 'centre', apres: 2 });
  body.appendHorizontalRule();
}

function piedLegal_(body, cfg) {
  body.appendHorizontalRule();
  const elements = ['Association loi 1901'];
  if (texte_(cfg.RNA)) elements.push('RNA ' + texte_(cfg.RNA));
  if (texte_(cfg.SIRET)) elements.push('SIRET ' + texte_(cfg.SIRET));
  if (texte_(cfg.Affiliation_FFKda)) elements.push('Affiliation FFKDA ' + texte_(cfg.Affiliation_FFKda));
  para_(body, elements.join(' – '), { taille: 7, align: 'centre', couleur: '#616161', apres: 0 });
}

function signature_(body, cfg, qualite, nom) {
  para_(body, 'Fait à ' + (texte_(cfg.Ville_Signature) || '……………') + ', le ' + dateFr_(new Date()),
        { align: 'droite', avant: 10, apres: 2 });
  para_(body, qualite + (texte_(nom) ? ' : ' + texte_(nom) : ''), { align: 'droite', gras: true, apres: 30 });
}

/**
 * Crée un document, l'exporte en PDF dans 02_Factures_PDF et supprime le brouillon.
 * Si garderDoc = true, le Google Doc modifiable est conservé dans le dossier (pas de PDF).
 */
function creerDocument_(nomFichier, construire, garderDoc) {
  const cfg = lireConfiguration();
  const doc = DocumentApp.create(nomFichier);
  const body = doc.getBody();
  body.setMarginTop(28).setMarginBottom(28).setMarginLeft(42).setMarginRight(42);
  enTeteClub_(body, cfg);
  construire(body, cfg);
  piedLegal_(body, cfg);
  doc.saveAndClose();
  const fichier = DriveApp.getFileById(doc.getId());
  const dossier = dossier_(DOSSIER.DOCUMENTS);
  if (garderDoc) {
    fichier.moveTo(dossier);
    return { nom: nomFichier, url: fichier.getUrl(), id: fichier.getId() };
  }
  const pdf = dossier.createFile(fichier.getAs(MimeType.PDF).setName(nomFichier + '.pdf'));
  fichier.setTrashed(true);
  return { nom: nomFichier + '.pdf', url: pdf.getUrl(), id: pdf.getId() };
}

function nomFichierPropre_(s) {
  return texte_(s).replace(/[\\\/:*?"<>|]/g, '').replace(/\s+/g, '_');
}

// ---------- Reçu de paiement ----------

function creerRecuPaiement_(cfg, e, objet, montant, mode, date) {
  const annee = new Date().getFullYear();
  const numero = 'REC-' + annee + '-' + String(prochainNumero_('Dernier_Numero_Recu')).padStart(3, '0');
  const res = creerDocument_(numero + '_' + nomFichierPropre_(e.nom), function (body) {
    titre_(body, 'REÇU DE PAIEMENT');
    para_(body, 'N° ' + numero + '     Date du paiement : ' + dateFr_(date), { gras: true, align: 'centre', apres: 8 });
    para_(body, 'Reçu de :', { gras: true, apres: 0 });
    para_(body, e.nom + (e.licence ? '  –  licence FFKaraté ' + e.licence : ''), { apres: 0 });
    para_(body, e.adresse || '', { apres: 8 });
    tableau_(body, [
      ['Objet', 'Mode de paiement', 'Montant'],
      [objet, mode, euros_(montant)]
    ], { droite: [2] });
    para_(body, 'Somme reçue : ' + euros_(montant), { taille: 12, gras: true, align: 'droite', avant: 8 });
    para_(body, 'Ce reçu atteste du paiement. Il n\'ouvre pas droit à réduction d\'impôt.',
          { taille: 8, italique: true, couleur: '#616161' });
    signature_(body, cfg, 'Le Trésorier', cfg.Tresorier);
  });
  res.numero = numero;
  return res;
}

// ---------- Facture ----------

function genererFacture_(cle) {
  const cfg = lireConfiguration();
  const t = trouverMembre_(cle);
  if (!t) throw new Error('Adhérent introuvable : ' + cle);
  const e = etatMembre_(t.r);
  const saison = periodeExercice_(exerciceCourant_(cfg), cfg).libelle;
  const lignes = [['Désignation', 'Montant']];
  if (e.adhesionDue) lignes.push(['Frais d\'adhésion (première inscription)', euros_(e.frais)]);
  lignes.push(['Cotisation annuelle – ' + saison, euros_(e.cotisation)]);
  if (e.paye > 0) lignes.push(['Déjà réglé', '-' + euros_(e.paye)]);
  lignes.push(['RESTE À PAYER', euros_(e.resteDu)]);

  const annee = new Date().getFullYear();
  const numero = 'FAC-' + annee + '-' + String(prochainNumero_('Dernier_Numero_Facture')).padStart(3, '0');
  const res = creerDocument_(numero + '_' + nomFichierPropre_(e.nom), function (body) {
    titre_(body, 'FACTURE');
    para_(body, 'N° ' + numero + '     Date : ' + dateFr_(new Date()), { gras: true, align: 'centre', apres: 8 });
    para_(body, 'Adressée à :', { gras: true, apres: 0 });
    para_(body, e.nom + (e.licence ? '  –  licence FFKaraté ' + e.licence : ''), { apres: 0 });
    para_(body, e.adresse || '', { apres: 0 });
    para_(body, e.email || '', { apres: 8 });
    tableau_(body, lignes, { droite: [1], totalDerniere: true });
    para_(body, 'Modalités de règlement', { gras: true, avant: 10, apres: 2 });
    para_(body, '• Chèque à l\'ordre de « ' + champ_(cfg, 'Nom_Association') + ' »', { apres: 0 });
    para_(body, '• Virement : ' + champ_(cfg, 'IBAN'), { apres: 0 });
    para_(body, '• Espèces (contre reçu) – Pass\'Sport accepté – paiement en plusieurs fois possible', { apres: 6 });
  });
  res.numero = numero;
  res.total = e.resteDu;
  return res;
}

// ---------------------------------------------------------------------------
// 9. DONS ET REÇUS FISCAUX
// ---------------------------------------------------------------------------

function feuilleDons_() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let sh = ss.getSheetByName(ONGLET.DONS);
  if (!sh) {
    sh = ss.insertSheet(ONGLET.DONS);
    sh.getRange(1, 1, 1, D.NB).setValues([ENTETES.DONS]).setFontWeight('bold').setBackground('#eeeeee');
    return sh;
  }
  // Ajoute les colonnes manquantes en fin de tableau (sans toucher aux données)
  const largeur = Math.max(sh.getLastColumn(), 1);
  const entetes = sh.getRange(1, 1, 1, largeur).getValues()[0];
  for (let j = 0; j < D.NB; j++) {
    if (texte_(entetes[j]) === '') sh.getRange(1, j + 1).setValue(ENTETES.DONS[j]).setFontWeight('bold').setBackground('#eeeeee');
  }
  return sh;
}

function enLettres_(n) {
  const u = ['zéro', 'un', 'deux', 'trois', 'quatre', 'cinq', 'six', 'sept', 'huit', 'neuf', 'dix', 'onze', 'douze',
             'treize', 'quatorze', 'quinze', 'seize', 'dix-sept', 'dix-huit', 'dix-neuf'];
  const d = ['', '', 'vingt', 'trente', 'quarante', 'cinquante', 'soixante', 'soixante', 'quatre-vingt', 'quatre-vingt'];
  function moinsDeCent(x) {
    if (x < 20) return u[x];
    const dz = Math.floor(x / 10), un = x % 10;
    if (dz === 7 || dz === 9) return d[dz] + (dz === 7 && un === 1 ? ' et ' : '-') + u[10 + un];
    if (un === 0) return d[dz] + (dz === 8 ? 's' : '');
    return d[dz] + (un === 1 && dz !== 8 ? ' et ' : '-') + u[un];
  }
  function moinsDeMille(x) {
    const c = Math.floor(x / 100), r = x % 100;
    let s = '';
    if (c > 0) s = (c > 1 ? u[c] + ' cent' : 'cent') + (c > 1 && r === 0 ? 's' : '');
    if (r > 0) s += (s ? ' ' : '') + moinsDeCent(r);
    return s;
  }
  function entier(x) {
    if (x === 0) return 'zéro';
    const mil = Math.floor(x / 1000000), mille = Math.floor((x % 1000000) / 1000), r = x % 1000;
    let s = '';
    if (mil) s += moinsDeMille(mil) + (mil > 1 ? ' millions' : ' million');
    if (mille) s += (s ? ' ' : '') + (mille === 1 ? 'mille' : moinsDeMille(mille).replace(/cents$/, 'cent') + ' mille');
    if (r) s += (s ? ' ' : '') + moinsDeMille(r);
    return s;
  }
  const total = Math.round(Math.abs(n) * 100);
  const e = Math.floor(total / 100), c = total % 100;
  let s = entier(e) + (e > 1 ? ' euros' : ' euro');
  if (c) s += ' et ' + entier(c) + (c > 1 ? ' centimes' : ' centime');
  return s;
}

/** d = { nom, adresse, email, montant, nature 'Numéraire'|'Don en nature', mode, date, compta, recu } */
function enregistrerDon_(d) {
  const nom = texte_(d.nom), adresse = texte_(d.adresse);
  if (!nom) throw new Error('Le nom du donateur est obligatoire');
  if (!adresse) throw new Error('L\'adresse du donateur est obligatoire pour un reçu fiscal');
  const montant = arrondi_(nombre_(d.montant));
  if (!(montant > 0)) throw new Error('Montant invalide');
  const nature = d.nature === 'Don en nature' ? 'Don en nature' : 'Numéraire';
  const mode = nature === 'Don en nature' ? '—' : (MODES_PAIEMENT.indexOf(d.mode) >= 0 ? d.mode : 'Chèque');
  const date = versDate_(d.date) || new Date();

  const sh = feuilleDons_();
  const vals = sh.getDataRange().getValues();
  let max = 0;
  for (let i = 1; i < vals.length; i++) { const n = Number(vals[i][D.ID]); if (!isNaN(n) && n > max) max = n; }
  const id = String(max + 1).padStart(3, '0');
  const ligne = sh.getLastRow() + 1;
  sh.getRange(ligne, 1).setNumberFormat('@');
  sh.getRange(ligne, 1, 1, D.NB).setValues([[id, date, nom, adresse, texte_(d.email), montant, nature, mode, '']]);

  let doc = null;
  if (d.recu) doc = recuFiscal_(ligne);
  if (d.compta && nature === 'Numéraire') {
    ajouterLigneOperation_({ date: date, libelle: 'Don – ' + nom, montant: montant, type: 'Recette',
                             categorie: 'Dons', tiers: nom, notes: 'Mode : ' + mode,
                             piece: doc ? doc.numero : '', source: sourceDepuisMode_(mode) });
  }
  return {
    message: '🎁 Don de ' + euros_(montant) + ' enregistré (' + nom + ')' +
             (doc ? '\n📜 Reçu fiscal ' + doc.numero : '') +
             (d.compta && nature === 'Numéraire' ? '\n📒 Écriture ajoutée en comptabilité' : ''),
    url: doc ? doc.url : ''
  };
}

/** Génère le reçu fiscal du don situé à la ligne "ligne" (numéro conservé en cas de réédition). */
function recuFiscal_(ligne) {
  const cfg = lireConfiguration();
  const sh = feuilleDons_();
  const r = sh.getRange(ligne, 1, 1, D.NB).getValues()[0];
  let numero = texte_(r[D.NUMERO]);
  const duplicata = !!numero;
  if (!numero) {
    numero = 'DON-' + new Date().getFullYear() + '-' + String(prochainNumero_('Dernier_Numero_Recu_Fiscal')).padStart(3, '0');
    sh.getRange(ligne, D.NUMERO + 1).setValue(numero);
  }
  const montant = nombreOu_(r[D.MONTANT], 0);
  const nature = texte_(r[D.NATURE]) || 'Numéraire';
  const mode = texte_(r[D.MODE]) || '—';
  const modeCerfa = { 'Espèces': 'Remise d\'espèces', 'Chèque': 'Chèque', 'Virement': 'Virement, prélèvement, carte bancaire',
                      'Carte bancaire': 'Virement, prélèvement, carte bancaire' }[mode] || mode;

  const res = creerDocument_(numero + (duplicata ? '_DUPLICATA' : '') + '_' + nomFichierPropre_(r[D.NOM]), function (body) {
    titre_(body, 'REÇU AU TITRE DES DONS À CERTAINS ORGANISMES D\'INTÉRÊT GÉNÉRAL', { taille: 11, apres: 0 });
    para_(body, 'Articles 200, 238 bis et 978 du code général des impôts', { taille: 8, italique: true, align: 'centre', apres: 4 });
    para_(body, 'Reçu n° ' + numero + (duplicata ? '   –   DUPLICATA' : ''), { gras: true, align: 'centre', apres: 8,
                                                                            couleur: duplicata ? COULEUR.ROUGE : COULEUR.NOIR });
    para_(body, 'Bénéficiaire des versements', { gras: true, apres: 0 });
    para_(body, champ_(cfg, 'Nom_Association') + ' – ' + [texte_(cfg.Adresse), texte_(cfg.Code_Postal_Ville)].filter(String).join(' '), { apres: 0 });
    para_(body, 'Objet : ' + champ_(cfg, 'Objet_Association'), { apres: 0 });
    para_(body, 'Association loi 1901' + (texte_(cfg.RNA) ? ' – RNA ' + texte_(cfg.RNA) : ''), { apres: 8 });
    para_(body, 'Donateur', { gras: true, apres: 0 });
    para_(body, texte_(r[D.NOM]), { apres: 0 });
    para_(body, texte_(r[D.ADRESSE]), { apres: 8 });
    para_(body, 'Le bénéficiaire reconnaît avoir reçu, au titre des dons et versements ouvrant droit à réduction d\'impôt, la somme de :',
          { apres: 2 });
    para_(body, euros_(montant) + '  (' + enLettres_(montant) + ')', { taille: 12, gras: true, align: 'centre', apres: 6 });
    tableau_(body, [
      ['Date du versement', 'Forme du don', 'Nature du don', 'Mode de versement'],
      [dateFr_(r[D.DATE]), 'Déclaration de don manuel', nature, nature === 'Don en nature' ? '—' : modeCerfa]
    ]);
    para_(body, 'Le bénéficiaire certifie sur l\'honneur que les dons et versements qu\'il reçoit ouvrent droit à la réduction d\'impôt prévue à l\'article 200 du CGI.',
          { taille: 9, avant: 8 });
    para_(body, 'Pour un particulier, la réduction d\'impôt est égale à 66 % des sommes versées, dans la limite de 20 % du revenu imposable (soit ici ' +
          euros_(montant * 0.66) + ' maximum).', { taille: 8, italique: true, couleur: '#616161' });
    signature_(body, cfg, 'Le Président', cfg.President);
  });
  res.numero = numero;
  return res;
}

function saisirDon() {
  proteger_(function () {
    const nom = demander_('Nom complet du donateur'); if (!nom) return;
    const adresse = demander_('Adresse complète du donateur (obligatoire)'); if (!adresse) return;
    const email = demander_('Email (optionnel)', ''); if (email === null) return;
    const montant = demander_('Montant du don (€)'); if (montant === null) return;
    const n = demander_('Nature :\n1 = Numéraire (argent)\n2 = Don en nature', '1'); if (n === null) return;
    const nature = n === '2' ? 'Don en nature' : 'Numéraire';
    let mode = '—';
    if (nature === 'Numéraire') {
      const m = demander_('Mode de versement :\n' + MODES_PAIEMENT.map(function (x, i) { return (i + 1) + ' = ' + x; }).join('\n'), '1');
      if (m === null) return;
      mode = MODES_PAIEMENT[Number(m) - 1];
      if (!mode) throw new Error('Mode invalide');
    }
    const d = demander_('Date du don (JJ/MM/AAAA)', dateFr_(new Date())); if (d === null) return;
    const compta = nature === 'Numéraire' ? confirmer_('Ajouter aussi l\'écriture en comptabilité ?') : false;
    const recu = confirmer_('Générer le reçu fiscal maintenant ?');
    const res = enregistrerDon_({ nom: nom, adresse: adresse, email: email, montant: montant, nature: nature,
                                  mode: mode, date: versDate_(d), compta: compta, recu: recu });
    info_(res.message);
  });
}

function recuFiscalDon() {
  proteger_(function () {
    const sh = feuilleDons_();
    const vals = sh.getDataRange().getValues();
    if (vals.length < 2) throw new Error('Aucun don enregistré');
    const liste = [];
    for (let i = Math.max(1, vals.length - 15); i < vals.length; i++) {
      liste.push(texte_(vals[i][D.ID]) + ' – ' + texte_(vals[i][D.NOM]) + ' – ' + euros_(vals[i][D.MONTANT]) + ' – ' +
                 dateFr_(vals[i][D.DATE]) + (texte_(vals[i][D.NUMERO]) ? ' (déjà émis : ' + texte_(vals[i][D.NUMERO]) + ')' : ''));
    }
    const id = demander_('Derniers dons :\n\n' + liste.join('\n') + '\n\nID du don :'); if (!id) return;
    for (let i = 1; i < vals.length; i++) {
      if (memeId_(vals[i][D.ID], id)) {
        const doc = recuFiscal_(i + 1);
        return info_('📜 Reçu fiscal ' + doc.numero + ' créé\n📁 Dossier ' + DOSSIER.DOCUMENTS);
      }
    }
    throw new Error('Don introuvable : ' + id);
  });
}

// ---------------------------------------------------------------------------
// 10. ANALYSES ET RAPPORTS
// ---------------------------------------------------------------------------

const NOMS_MOIS = ['Janv.', 'Févr.', 'Mars', 'Avr.', 'Mai', 'Juin', 'Juil.', 'Août', 'Sept.', 'Oct.', 'Nov.', 'Déc.'];

function analyserFinances_(p) {
  const ops = feuille_(ONGLET.OPERATIONS).getDataRange().getValues();
  const a = { recettes: {}, depenses: {}, totalR: 0, totalD: 0, nb: 0, mois: [],
              banqueDebut: 0, banqueFin: 0, caisseDebut: 0, caisseFin: 0 };
  for (let k = 0; k < 12; k++) {
    a.mois.push({ libelle: NOMS_MOIS[(p.moisDebut - 1 + k) % 12], r: 0, d: 0 });
  }
  for (let i = 1; i < ops.length; i++) {
    const d = versDate_(ops[i][OP.DATE]);
    const mt = nombre_(ops[i][OP.MONTANT]);
    if (!d || isNaN(mt)) continue;
    const src = texte_(ops[i][OP.SOURCE]);
    if (d < p.debut) { if (src === 'Banque') a.banqueDebut += mt; if (src === 'Especes') a.caisseDebut += mt; }
    if (d < p.fin) { if (src === 'Banque') a.banqueFin += mt; if (src === 'Especes') a.caisseFin += mt; }
    if (d < p.debut || d >= p.fin) continue;
    a.nb++;
    const cat = texte_(ops[i][OP.CATEGORIE]) || 'Autres';
    const idx = (d.getFullYear() * 12 + d.getMonth()) - (p.debut.getFullYear() * 12 + p.debut.getMonth());
    if (mt >= 0) {
      a.totalR += mt; a.recettes[cat] = (a.recettes[cat] || 0) + mt;
      if (idx >= 0 && idx < 12) a.mois[idx].r += mt;
    } else {
      a.totalD += -mt; a.depenses[cat] = (a.depenses[cat] || 0) - mt;
      if (idx >= 0 && idx < 12) a.mois[idx].d += -mt;
    }
  }
  a.resultat = a.totalR - a.totalD;
  return a;
}

function analyserMembres_(p) {
  const vals = lireMembres_().vals;
  const a = { total: 0, nouveaux: 0, aJour: 0, partiels: 0, attente: 0, encaisse: 0, resteDu: 0 };
  for (let i = 1; i < vals.length; i++) {
    if (!texte_(vals[i][M.NOM])) continue;
    const e = etatMembre_(completerLigne_(vals[i]));
    a.total++;
    if (dansPeriode_(vals[i][M.DATE_ADHESION], p)) a.nouveaux++;
    if (e.statut === 'À jour') a.aJour++;
    else if (e.statut === 'Paiement partiel') a.partiels++;
    else a.attente++;
    a.encaisse += e.paye;
    a.resteDu += e.resteDu;
  }
  return a;
}

function analyserDons_(p) {
  const a = { nb: 0, total: 0 };
  const sh = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(ONGLET.DONS);
  if (!sh) return a;
  const vals = sh.getDataRange().getValues();
  for (let i = 1; i < vals.length; i++) {
    if (!dansPeriode_(vals[i][D.DATE], p)) continue;
    a.nb++;
    a.total += nombreOu_(vals[i][D.MONTANT], 0);
  }
  return a;
}

function lignesCategories_(obj, total) {
  const lignes = [['Catégorie', 'Montant', 'Part']];
  Object.keys(obj).sort(function (x, y) { return obj[y] - obj[x]; }).forEach(function (k) {
    lignes.push([k, euros_(obj[k]), total ? Math.round(obj[k] / total * 100) + ' %' : '—']);
  });
  lignes.push(['TOTAL', euros_(total), total ? '100 %' : '—']);
  return lignes;
}

function graphiqueMensuel_(a) {
  try {
    const dt = Charts.newDataTable()
      .addColumn(Charts.ColumnType.STRING, 'Mois')
      .addColumn(Charts.ColumnType.NUMBER, 'Recettes')
      .addColumn(Charts.ColumnType.NUMBER, 'Dépenses');
    a.mois.forEach(function (m) { dt.addRow([m.libelle, arrondi_(m.r), arrondi_(m.d)]); });
    return Charts.newColumnChart()
      .setDataTable(dt.build())
      .setColors([COULEUR.VERT, COULEUR.ROUGE])
      .setDimensions(640, 260)
      .setLegendPosition(Charts.Position.BOTTOM)
      .build()
      .getAs('image/png');
  } catch (e) {
    return null;
  }
}

function insererGraphique_(body, blob) {
  if (!blob) return;
  const img = body.appendImage(blob);
  const ratio = img.getHeight() / img.getWidth();
  img.setWidth(460).setHeight(Math.round(460 * ratio));
  img.getParent().asParagraph().setAlignment(DocumentApp.HorizontalAlignment.CENTER);
}

function genererBilan_(annee) {
  const cfg = lireConfiguration();
  const p = periodeExercice_(annee, cfg);
  const a = analyserFinances_(p);
  return creerDocument_('Bilan_financier_' + nomFichierPropre_(p.libelle), function (body) {
    titre_(body, 'BILAN FINANCIER – ' + p.libelle.toUpperCase());
    para_(body, 'Du ' + dateFr_(p.debut) + ' au ' + dateFr_(new Date(p.fin.getTime() - 86400000)) + ' – ' + a.nb + ' écritures',
          { align: 'centre', taille: 9, italique: true, apres: 6 });
    tableau_(body, [
      ['Synthèse', 'Montant'],
      ['Recettes', euros_(a.totalR)],
      ['Dépenses', euros_(a.totalD)],
      ['RÉSULTAT', euros_(a.resultat)]
    ], { droite: [1], totalDerniere: true });
    para_(body, '', { apres: 2 });
    tableau_(body, [
      ['Trésorerie', 'Début', 'Fin'],
      ['Banque', euros_(a.banqueDebut), euros_(a.banqueFin)],
      ['Caisse (espèces)', euros_(a.caisseDebut), euros_(a.caisseFin)],
      ['TOTAL', euros_(a.banqueDebut + a.caisseDebut), euros_(a.banqueFin + a.caisseFin)]
    ], { droite: [1, 2], totalDerniere: true });
    insererGraphique_(body, graphiqueMensuel_(a));
    para_(body, 'Recettes par catégorie', { gras: true, avant: 6, apres: 2 });
    tableau_(body, lignesCategories_(a.recettes, a.totalR), { droite: [1, 2], couleur: COULEUR.VERT, totalDerniere: true });
    para_(body, 'Dépenses par catégorie', { gras: true, avant: 6, apres: 2 });
    tableau_(body, lignesCategories_(a.depenses, a.totalD), { droite: [1, 2], couleur: COULEUR.ROUGE, totalDerniere: true });
    const b = comparerBudget_(annee);
    if (b.lignes.length) {
      para_(body, 'Budget prévisionnel et réalisé', { gras: true, avant: 6, apres: 2 });
      tableau_(body, lignesBudgetDoc_(b, true), { droite: [2, 3, 4] });
    }
    signature_(body, cfg, 'Le Trésorier', cfg.Tresorier);
  });
}

function genererRapportAGO_(annee) {
  const cfg = lireConfiguration();
  const p = periodeExercice_(annee, cfg);
  const f = analyserFinances_(p);
  const m = analyserMembres_(p);
  const dn = analyserDons_(p);
  return creerDocument_('Rapport_AGO_' + nomFichierPropre_(p.libelle), function (body) {
    titre_(body, 'ASSEMBLÉE GÉNÉRALE ORDINAIRE', { apres: 0 });
    para_(body, 'Rapport d\'activité et rapport financier – ' + p.libelle, { align: 'centre', gras: true, apres: 8 });

    para_(body, '1. Vie du club', { gras: true, taille: 11, couleur: COULEUR.ROUGE, avant: 6 });
    tableau_(body, [
      ['Adhérents', 'Nombre'],
      ['Adhérents inscrits', String(m.total)],
      ['dont nouveaux sur la période', String(m.nouveaux)],
      ['Cotisation réglée', String(m.aJour)],
      ['Paiement partiel', String(m.partiels)],
      ['En attente de paiement', String(m.attente)]
    ], { droite: [1] });
    para_(body, '[À compléter par le bureau : cours, stages, passages de grades, compétitions, résultats…]',
          { italique: true, couleur: '#616161', avant: 4 });

    para_(body, '2. Rapport financier', { gras: true, taille: 11, couleur: COULEUR.ROUGE, avant: 8 });
    tableau_(body, [
      ['Compte de résultat', 'Montant'],
      ['Recettes', euros_(f.totalR)],
      ['Dépenses', euros_(f.totalD)],
      ['RÉSULTAT DE L\'EXERCICE', euros_(f.resultat)]
    ], { droite: [1], totalDerniere: true });
    para_(body, '', { apres: 2 });
    tableau_(body, [
      ['Trésorerie', 'Début', 'Fin'],
      ['Banque', euros_(f.banqueDebut), euros_(f.banqueFin)],
      ['Caisse (espèces)', euros_(f.caisseDebut), euros_(f.caisseFin)]
    ], { droite: [1, 2] });
    insererGraphique_(body, graphiqueMensuel_(f));
    para_(body, 'Recettes par catégorie', { gras: true, avant: 6, apres: 2 });
    tableau_(body, lignesCategories_(f.recettes, f.totalR), { droite: [1, 2], couleur: COULEUR.VERT, totalDerniere: true });
    para_(body, 'Dépenses par catégorie', { gras: true, avant: 6, apres: 2 });
    tableau_(body, lignesCategories_(f.depenses, f.totalD), { droite: [1, 2], couleur: COULEUR.ROUGE, totalDerniere: true });

    para_(body, '3. Dons', { gras: true, taille: 11, couleur: COULEUR.ROUGE, avant: 8 });
    para_(body, dn.nb ? dn.nb + ' don(s) reçu(s) pour un total de ' + euros_(dn.total) + '.' : 'Aucun don enregistré sur la période.');

    para_(body, '4. Perspectives et budget prévisionnel', { gras: true, taille: 11, couleur: COULEUR.ROUGE, avant: 8 });
    para_(body, '[À compléter par le bureau]', { italique: true, couleur: '#616161' });
    const bud = comparerBudget_(annee + 1);
    if (bud.lignes.some(function (l) { return l.prevu > 0; })) {
      para_(body, 'Budget prévisionnel – ' + periodeExercice_(annee + 1, cfg).libelle, { gras: true, avant: 4, apres: 2 });
      tableau_(body, lignesBudgetDoc_(bud, false), { droite: [2] });
    } else {
      para_(body, '(Aucun budget saisi pour ' + periodeExercice_(annee + 1, cfg).libelle + ' – à préparer dans l\'onglet Budget de l\'interface.)',
            { italique: true, taille: 9, couleur: '#616161' });
    }

    para_(body, '5. Résolutions soumises au vote', { gras: true, taille: 11, couleur: COULEUR.ROUGE, avant: 8 });
    para_(body, '• Approbation du rapport moral\n• Approbation des comptes de l\'exercice et quitus au trésorier\n• Affectation du résultat\n• Vote du budget prévisionnel');
    signature_(body, cfg, 'Le Président', cfg.President);
  }, true);
}

function genererComparatif_(annee1, annee2) {
  const cfg = lireConfiguration();
  const p1 = periodeExercice_(annee1, cfg), p2 = periodeExercice_(annee2, cfg);
  const a1 = analyserFinances_(p1), a2 = analyserFinances_(p2);
  function evol(x, y) { return x ? (y - x >= 0 ? '+' : '') + Math.round((y - x) / Math.abs(x) * 100) + ' %' : '—'; }
  const cats = {};
  Object.keys(a1.recettes).concat(Object.keys(a2.recettes)).forEach(function (k) { cats['R|' + k] = true; });
  Object.keys(a1.depenses).concat(Object.keys(a2.depenses)).forEach(function (k) { cats['D|' + k] = true; });
  const lignesCat = [['Catégorie', p1.libelle, p2.libelle, 'Évolution']];
  Object.keys(cats).sort().forEach(function (k) {
    const type = k.charAt(0), nom = k.slice(2);
    const x = type === 'R' ? (a1.recettes[nom] || 0) : (a1.depenses[nom] || 0);
    const y = type === 'R' ? (a2.recettes[nom] || 0) : (a2.depenses[nom] || 0);
    lignesCat.push([(type === 'R' ? '▲ ' : '▼ ') + nom, euros_(x), euros_(y), evol(x, y)]);
  });
  return creerDocument_('Comparatif_' + nomFichierPropre_(p1.libelle) + '_' + nomFichierPropre_(p2.libelle), function (body) {
    titre_(body, 'COMPARAISON ' + p1.libelle.toUpperCase() + ' / ' + p2.libelle.toUpperCase());
    tableau_(body, [
      ['Indicateur', p1.libelle, p2.libelle, 'Évolution'],
      ['Recettes', euros_(a1.totalR), euros_(a2.totalR), evol(a1.totalR, a2.totalR)],
      ['Dépenses', euros_(a1.totalD), euros_(a2.totalD), evol(a1.totalD, a2.totalD)],
      ['Résultat', euros_(a1.resultat), euros_(a2.resultat), euros_(a2.resultat - a1.resultat)],
      ['Trésorerie fin (banque + caisse)', euros_(a1.banqueFin + a1.caisseFin), euros_(a2.banqueFin + a2.caisseFin),
       euros_(a2.banqueFin + a2.caisseFin - a1.banqueFin - a1.caisseFin)]
    ], { droite: [1, 2, 3] });
    para_(body, 'Détail par catégorie (▲ recettes, ▼ dépenses)', { gras: true, avant: 8, apres: 2 });
    tableau_(body, lignesCat, { droite: [1, 2, 3] });
  });
}

function demanderAnnee_(message) {
  const cfg = lireConfiguration();
  const courant = exerciceCourant_(cfg);
  const v = demander_(message + '\n(' + periodeExercice_(courant, cfg).libelle + ' = ' + courant + ')', String(courant));
  if (v === null) return null;
  const n = Number(v);
  if (!(n > 2000 && n < 2100)) throw new Error('Année invalide : ' + v);
  return n;
}

function bilanFinancier() {
  proteger_(function () {
    const a = demanderAnnee_('Année de début de l\'exercice'); if (a === null) return;
    const doc = genererBilan_(a);
    info_('📈 ' + doc.nom + ' créé\n📁 Dossier ' + DOSSIER.DOCUMENTS);
  });
}

function rapportAGO() {
  proteger_(function () {
    const a = demanderAnnee_('Année de début de l\'exercice'); if (a === null) return;
    const doc = genererRapportAGO_(a);
    info_('🏆 ' + doc.nom + ' créé (Google Doc modifiable : complétez les parties entre crochets)\n📁 Dossier ' + DOSSIER.DOCUMENTS);
  });
}

function analyseComparative() {
  proteger_(function () {
    const a1 = demanderAnnee_('Premier exercice'); if (a1 === null) return;
    const a2 = demanderAnnee_('Second exercice'); if (a2 === null) return;
    const doc = genererComparatif_(a1, a2);
    info_('📉 ' + doc.nom + ' créé\n📁 Dossier ' + DOSSIER.DOCUMENTS);
  });
}

// ---------------------------------------------------------------------------
// 11. TABLEAU DE BORD
// ---------------------------------------------------------------------------

function obtenirStatistiquesCompletes() {
  const cfg = lireConfiguration();
  const p = periodeExercice_(exerciceCourant_(cfg), cfg);
  const f = analyserFinances_(p);
  const m = analyserMembres_(p);
  const dn = analyserDons_(p);
  const now = new Date();
  let opsMois = 0;
  const ops = feuille_(ONGLET.OPERATIONS).getDataRange().getValues();
  for (let i = 1; i < ops.length; i++) {
    const d = versDate_(ops[i][OP.DATE]);
    if (d && d.getFullYear() === now.getFullYear() && d.getMonth() === now.getMonth()) opsMois++;
  }
  // Soldes à aujourd'hui (toutes écritures)
  let banque = 0, caisse = 0;
  for (let i = 1; i < ops.length; i++) {
    const mt = nombre_(ops[i][OP.MONTANT]);
    if (isNaN(mt)) continue;
    const src = texte_(ops[i][OP.SOURCE]);
    if (src === 'Banque') banque += mt;
    if (src === 'Especes') caisse += mt;
  }
  return {
    exercice: p.libelle,
    soldeBanque: arrondi_(banque),
    soldeCaisse: arrondi_(caisse),
    recettes: arrondi_(f.totalR),
    depenses: arrondi_(f.totalD),
    resultat: arrondi_(f.resultat),
    operationsMois: opsMois,
    totalAdherents: m.total,
    adherentsAJour: m.aJour,
    adherentsPartiels: m.partiels,
    adherentsAttente: m.attente,
    cotisationsRecues: arrondi_(m.encaisse),
    resteAEncaisser: arrondi_(m.resteDu),
    nombreDons: dn.nb,
    totalDons: arrondi_(dn.total),
    // Compatibilité avec l'ancienne interface
    solde: arrondi_(banque).toFixed(2)
  };
}

function obtenirStatistiques() {
  return obtenirStatistiquesCompletes();
}

function tableauDeBord() {
  proteger_(function () {
    const s = obtenirStatistiquesCompletes();
    const lignes = [
      ['TABLEAU DE BORD', s.exercice],
      ['Mis à jour le', Utilities.formatDate(new Date(), TZ, 'dd/MM/yyyy HH:mm')],
      ['', ''],
      ['Solde banque', s.soldeBanque],
      ['Solde caisse (espèces)', s.soldeCaisse],
      ['Recettes de l\'exercice', s.recettes],
      ['Dépenses de l\'exercice', s.depenses],
      ['Résultat de l\'exercice', s.resultat],
      ['', ''],
      ['Adhérents inscrits', s.totalAdherents],
      ['Cotisation réglée', s.adherentsAJour],
      ['Paiement partiel', s.adherentsPartiels],
      ['En attente', s.adherentsAttente],
      ['Reste à encaisser', s.resteAEncaisser],
      ['', ''],
      ['Dons (nombre)', s.nombreDons],
      ['Dons (montant)', s.totalDons]
    ];
    const ss = SpreadsheetApp.getActiveSpreadsheet();
    const sh = ss.getSheetByName(ONGLET.DASHBOARD) || ss.insertSheet(ONGLET.DASHBOARD);
    sh.clear();
    sh.getRange(1, 1, lignes.length, 2).setValues(lignes);
    sh.getRange(1, 1, 1, 2).setFontWeight('bold').setFontSize(13);
    [4, 5, 6, 7, 8, 14, 17].forEach(function (r) { sh.getRange(r, 2).setNumberFormat('#,##0.00 "€"'); });
    sh.autoResizeColumns(1, 2);
    info_('📊 ' + s.exercice + '\n\n🏦 Banque : ' + euros_(s.soldeBanque) + '\n💶 Caisse : ' + euros_(s.soldeCaisse) +
          '\n📈 Résultat : ' + euros_(s.resultat) + '\n\n👥 ' + s.adherentsAJour + '/' + s.totalAdherents +
          ' adhérents à jour\n⏳ Reste à encaisser : ' + euros_(s.resteAEncaisser) +
          '\n🎁 Dons : ' + s.nombreDons + ' (' + euros_(s.totalDons) + ')\n\nDétail dans l\'onglet Dashboard.');
  });
}

// ---------------------------------------------------------------------------
// 12. SAUVEGARDE
// ---------------------------------------------------------------------------

/** Depuis le menu (affiche un message). Fonctionne aussi si appelée par un déclencheur. */
function sauvegardeManuelle() {
  const nom = sauvegarderDonnees_();
  try { info_('✅ Sauvegarde créée dans ' + DOSSIER.SAUVEGARDES + ' :\n' + nom); } catch (e) { /* exécution sans écran */ }
  return nom;
}

/** À utiliser dans le déclencheur de nuit. */
function sauvegardeAutomatique() {
  sauvegarderDonnees_();
}

function sauvegarderDonnees_() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const nom = 'Sauvegarde_' + Utilities.formatDate(new Date(), TZ, 'yyyy-MM-dd_HH-mm');
  const dossier = dossier_(DOSSIER.SAUVEGARDES);
  // 1. Copie complète (restaurable en un clic)
  DriveApp.getFileById(ss.getId()).makeCopy(nom, dossier);
  // 2. Export Excel lisible sans Google
  const url = 'https://docs.google.com/spreadsheets/d/' + ss.getId() + '/export?format=xlsx';
  const blob = UrlFetchApp.fetch(url, { headers: { Authorization: 'Bearer ' + ScriptApp.getOAuthToken() } })
    .getBlob().setName(nom + '.xlsx');
  dossier.createFile(blob);
  // 3. Corbeille pour les sauvegardes de plus de 30 jours
  const limite = new Date(Date.now() - 30 * 24 * 3600 * 1000);
  const fichiers = dossier.getFiles();
  while (fichiers.hasNext()) {
    const f = fichiers.next();
    if (f.getName().indexOf('Sauvegarde_') === 0 && f.getDateCreated() < limite) f.setTrashed(true);
  }
  return nom;
}

// ---------------------------------------------------------------------------
// 13. MAINTENANCE
// ---------------------------------------------------------------------------

function verifierStructure() {
  proteger_(function () {
    const controles = [[ONGLET.OPERATIONS, ENTETES.OPERATIONS], [ONGLET.MEMBRES, ENTETES.MEMBRES]];
    const ecarts = [];
    const ss = SpreadsheetApp.getActiveSpreadsheet();
    controles.forEach(function (c) {
      const sh = ss.getSheetByName(c[0]);
      if (!sh) { ecarts.push({ onglet: c[0], texte: 'onglet absent' }); return; }
      const lus = sh.getRange(1, 1, 1, c[1].length).getValues()[0];
      c[1].forEach(function (att, j) {
        if (texte_(lus[j]) !== att) {
          ecarts.push({ onglet: c[0], sh: sh, col: j + 1, attendu: att,
                        texte: 'colonne ' + String.fromCharCode(65 + j) + ' : « ' + (texte_(lus[j]) || 'vide') + ' » au lieu de « ' + att + ' »' });
        }
      });
    });
    feuilleDons_();
    if (!ecarts.length) return info_('✅ Structure conforme (Opérations, Adhérents, Dons).');
    const message = ecarts.map(function (e) { return '• ' + e.onglet + ' – ' + e.texte; }).join('\n');
    const renommables = ecarts.filter(function (e) { return e.sh; });
    if (renommables.length && confirmer_('Écarts trouvés :\n\n' + message +
        '\n\nVérifiez d\'abord que les DONNÉES sont bien dans le bon ordre.\nRenommer uniquement les en-têtes (ligne 1) ?')) {
      renommables.forEach(function (e) { e.sh.getRange(1, e.col).setValue(e.attendu); });
      info_('✅ En-têtes corrigés.');
    } else if (!renommables.length) {
      info_('Écarts trouvés :\n\n' + message);
    }
  });
}

// ---------------------------------------------------------------------------
// 14. INTERFACE WEB (fonctions appelées par interface.html)
// ---------------------------------------------------------------------------

function doGet() {
  return HtmlService.createHtmlOutputFromFile('interface')
    .setTitle('Gestion du club')
    .addMetaTag('viewport', 'width=device-width, initial-scale=1.0');
}

function getContexteWeb() {
  const cfg = lireConfiguration();
  const courant = exerciceCourant_(cfg);
  let logo = '';
  const blob = logoBlob_(cfg);
  if (blob) logo = 'data:' + blob.getContentType() + ';base64,' + Utilities.base64Encode(blob.getBytes());
  return {
    club: texte_(cfg.Nom_Association) || 'Gestion du club',
    ville: texte_(cfg.Code_Postal_Ville),
    exercice: periodeExercice_(courant, cfg).libelle,
    anneeCourante: courant,
    tarifAdhesion: nombreOu_(cfg.Tarif_Adhesion, 0),
    tarifCotisation: nombreOu_(cfg.Tarif_Cotisation, 0),
    categories: listerCategories_(),
    modes: MODES_PAIEMENT,
    logo: logo
  };
}

function ajouterOperationWeb(data) {
  const ligne = ajouterLigneOperation_({
    date: versDate_(data.date), libelle: data.libelle, montant: data.montant,
    type: data.type === 'Depense' ? 'Depense' : 'Recette', categorie: data.categorie,
    tiers: data.tiers, notes: data.notes, source: data.source === 'Especes' ? 'Especes' : 'Banque'
  });
  return { message: '✅ Opération enregistrée', ligne: ligne };
}

function dernieresOperationsWeb(n) {
  const vals = feuille_(ONGLET.OPERATIONS).getDataRange().getValues();
  const res = [];
  for (let i = vals.length - 1; i >= 1 && res.length < (n || 15); i--) {
    if (!texte_(vals[i][OP.LIBELLE]) && !texte_(vals[i][OP.MONTANT])) continue;
    res.push({
      date: dateFr_(vals[i][OP.DATE]), libelle: texte_(vals[i][OP.LIBELLE]), montant: arrondi_(nombreOu_(vals[i][OP.MONTANT], 0)),
      categorie: texte_(vals[i][OP.CATEGORIE]), source: texte_(vals[i][OP.SOURCE])
    });
  }
  return res;
}

function chercherLicenceWeb(licence) {
  const t = trouverParLicence_(licence);
  if (!t) return null;
  const e = etatMembre_(t.r);
  return { licence: e.licence, nom: e.nom, email: e.email, tel: e.tel, adresse: e.adresse,
           statut: e.statut, resteDu: e.resteDu, cotisation: e.cotisation };
}

function enregistrerAdherentWeb(data) {
  return enregistrerAdherent_(data);
}

function ajouterAdherentWeb(data) {
  return enregistrerAdherent_(data);
}

function listerAdherentsWeb() {
  const vals = lireMembres_().vals;
  const res = [];
  for (let i = 1; i < vals.length; i++) {
    if (!texte_(vals[i][M.NOM])) continue;
    const e = etatMembre_(completerLigne_(vals[i]));
    res.push({ id: e.id, licence: e.licence, nom: e.nom, email: e.email, statut: e.statut,
               statutAdhesion: e.statutAdhesion, frais: e.frais, adhesionDue: e.adhesionDue,
               cotisationRestante: e.cotisationRestante, resteDu: e.resteDu });
  }
  return res.sort(function (a, b) { return a.nom.localeCompare(b.nom, 'fr'); });
}

function enregistrerPaiementWeb(data) {
  return enregistrerPaiement_({
    cle: data.cle, nature: data.nature, montant: data.montant, mode: data.mode,
    date: versDate_(data.date), compta: !!data.compta, recu: !!data.recu
  });
}

function genererFactureWeb(cle) {
  const doc = genererFacture_(cle);
  return { message: '🧾 Facture ' + doc.numero + ' créée', url: doc.url };
}

function ajouterDonWeb(data) {
  return enregistrerDon_({
    nom: data.nom, adresse: data.adresse, email: data.email, montant: data.montant,
    nature: data.nature, mode: data.mode, date: versDate_(data.date), compta: !!data.compta, recu: !!data.recu
  });
}

function listerDonsWeb() {
  const sh = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(ONGLET.DONS);
  if (!sh) return [];
  const vals = sh.getDataRange().getValues();
  const res = [];
  for (let i = vals.length - 1; i >= 1; i--) {
    if (!texte_(vals[i][D.NOM])) continue;
    res.push({ id: texte_(vals[i][D.ID]), date: dateFr_(vals[i][D.DATE]), nom: texte_(vals[i][D.NOM]),
               montant: arrondi_(nombreOu_(vals[i][D.MONTANT], 0)), nature: texte_(vals[i][D.NATURE]),
               numero: texte_(vals[i][D.NUMERO]) });
  }
  return res;
}

function genererRecuDonWeb(id) {
  const sh = feuilleDons_();
  const vals = sh.getDataRange().getValues();
  for (let i = 1; i < vals.length; i++) {
    if (memeId_(vals[i][D.ID], id)) {
      const doc = recuFiscal_(i + 1);
      return { message: '📜 Reçu fiscal ' + doc.numero, url: doc.url };
    }
  }
  throw new Error('Don introuvable : ' + id);
}

function genererBilanWeb(annee) {
  const doc = genererBilan_(Number(annee));
  return { message: '📈 ' + doc.nom, url: doc.url };
}

function genererRapportAGOWeb(annee) {
  const doc = genererRapportAGO_(Number(annee));
  return { message: '🏆 ' + doc.nom + ' (Google Doc modifiable)', url: doc.url };
}

function genererComparatifWeb(annee1, annee2) {
  const doc = genererComparatif_(Number(annee1), Number(annee2));
  return { message: '📉 ' + doc.nom, url: doc.url };
}

function sauvegardeWeb() {
  return { message: '💾 Sauvegarde créée : ' + sauvegarderDonnees_() };
}

function obtenirUrlGoogleSheets() {
  return SpreadsheetApp.getActiveSpreadsheet().getUrl();
}

// ---------------------------------------------------------------------------
// 15. HISTORIQUE, RAPPROCHEMENT ET JUSTIFICATIFS
// ---------------------------------------------------------------------------

function estRapproche_(v) {
  if (v === true || v === 1) return true;
  return ['1', 'TRUE', 'VRAI', 'X', 'R', 'OUI'].indexOf(texte_(v).toUpperCase()) >= 0;
}

function sousDossier_(parent, nom) {
  const it = parent.getFoldersByName(nom);
  return it.hasNext() ? it.next() : parent.createFolder(nom);
}

function feuilleOperationsLarge_() {
  const sh = feuille_(ONGLET.OPERATIONS);
  if (sh.getMaxColumns() < OP.JUSTIF + 1) sh.insertColumnsAfter(sh.getMaxColumns(), OP.JUSTIF + 1 - sh.getMaxColumns());
  if (texte_(sh.getRange(1, OP.JUSTIF + 1).getValue()) === '') {
    sh.getRange(1, OP.JUSTIF + 1).setValue('Justificatif').setFontWeight('bold');
  }
  return sh;
}

function lireOperations_() {
  const sh = feuilleOperationsLarge_();
  const n = sh.getLastRow() - 1;
  if (n < 1) return { sh: sh, vals: [], liens: [] };
  const vals = sh.getRange(2, 1, n, OP.JUSTIF + 1).getValues();
  const rich = sh.getRange(2, OP.JUSTIF + 1, n, 1).getRichTextValues();
  const liens = rich.map(function (r, i) {
    const url = r[0] ? r[0].getLinkUrl() : null;
    if (url) return url;
    const brut = texte_(vals[i][OP.JUSTIF]);
    return /^https?:\/\//.test(brut) ? brut : '';
  });
  return { sh: sh, vals: vals, liens: liens };
}

/** f = { annee ('tout' ou année), categorie, source, rapproche ('oui'|'non'|''), texte } */
function filtrerOperations_(f) {
  f = f || {};
  const cfg = lireConfiguration();
  const p = f.annee && f.annee !== 'tout' ? periodeExercice_(Number(f.annee), cfg) : null;
  const t = lireOperations_();
  const txt = texte_(f.texte).toLowerCase();
  const res = [];
  let totR = 0, totD = 0;
  for (let i = 0; i < t.vals.length; i++) {
    const r = t.vals[i];
    const d = versDate_(r[OP.DATE]);
    const mt = nombre_(r[OP.MONTANT]);
    if (!d || isNaN(mt)) continue;
    if (p && (d < p.debut || d >= p.fin)) continue;
    if (f.categorie && texte_(r[OP.CATEGORIE]) !== f.categorie) continue;
    if (f.source && texte_(r[OP.SOURCE]) !== f.source) continue;
    const rap = estRapproche_(r[OP.RAPPROCHE]);
    if (f.rapproche === 'oui' && !rap) continue;
    if (f.rapproche === 'non' && rap) continue;
    if (txt && (texte_(r[OP.LIBELLE]) + ' ' + texte_(r[OP.TIERS]) + ' ' + texte_(r[OP.NOTES]) + ' ' + texte_(r[OP.PIECE]))
                 .toLowerCase().indexOf(txt) < 0) continue;
    if (mt >= 0) totR += mt; else totD += -mt;
    res.push({ ligne: i + 2, tri: d.getTime(), date: dateFr_(d), libelle: texte_(r[OP.LIBELLE]), montant: arrondi_(mt),
               categorie: texte_(r[OP.CATEGORIE]), source: texte_(r[OP.SOURCE]), tiers: texte_(r[OP.TIERS]),
               notes: texte_(r[OP.NOTES]), piece: texte_(r[OP.PIECE]), rapproche: rap, justif: t.liens[i] });
  }
  res.sort(function (a, b) { return b.tri - a.tri || b.ligne - a.ligne; });
  return { lignes: res, recettes: arrondi_(totR), depenses: arrondi_(totD) };
}

function rechercherOperationsWeb(f) {
  const r = filtrerOperations_(f);
  return { lignes: r.lignes.slice(0, 500), total: r.lignes.length, recettes: r.recettes, depenses: r.depenses };
}

function exporterOperationsWeb(f) {
  const r = filtrerOperations_(f);
  const q = function (v) { return '"' + String(v === null || v === undefined ? '' : v).replace(/"/g, '""') + '"'; };
  const lignes = [['Date', 'Libellé', 'Montant', 'Catégorie', 'Source', 'Tiers', 'Notes', 'N° pièce', 'Rapproché', 'Justificatif'].map(q).join(';')];
  r.lignes.slice().reverse().forEach(function (o) {
    lignes.push([o.date, o.libelle, String(o.montant.toFixed(2)).replace('.', ','), o.categorie, o.source, o.tiers, o.notes,
                 o.piece, o.rapproche ? 'Oui' : 'Non', o.justif].map(q).join(';'));
  });
  const nom = 'Export_operations_' + (f && f.annee && f.annee !== 'tout' ? f.annee + '_' : '') +
              Utilities.formatDate(new Date(), TZ, 'yyyy-MM-dd_HH-mm') + '.csv';
  const fichier = dossier_(DOSSIER.ARCHIVES).createFile(Utilities.newBlob('﻿' + lignes.join('\r\n'), 'text/csv', nom));
  return { message: '📤 ' + r.lignes.length + ' lignes exportées (' + nom + ')', url: fichier.getUrl() };
}

function basculerRapprochementWeb(ligne) {
  const sh = feuille_(ONGLET.OPERATIONS);
  const l = Number(ligne);
  if (!(l >= 2 && l <= sh.getLastRow())) throw new Error('Ligne invalide');
  const cell = sh.getRange(l, OP.RAPPROCHE + 1);
  const nouveau = !estRapproche_(cell.getValue());
  cell.setValue(nouveau);
  return { rapproche: nouveau };
}

const TYPES_JUSTIF = ['application/pdf', 'image/jpeg', 'image/png', 'image/webp', 'image/heic', 'image/heif'];

/** f = { base64, nom, mime, ligne (optionnel : ligne de l'opération à lier) } */
function televerserJustificatifWeb(f) {
  if (!f || !f.base64) throw new Error('Aucun fichier reçu');
  if (TYPES_JUSTIF.indexOf(f.mime) < 0) throw new Error('Format accepté : PDF, JPG, PNG, WEBP, HEIC');
  const octets = Utilities.base64Decode(f.base64);
  if (octets.length > 15 * 1024 * 1024) throw new Error('Fichier trop volumineux (15 Mo maximum)');
  const sh = feuilleOperationsLarge_();
  let date = new Date(), libelle = '';
  const ligne = Number(f.ligne) || 0;
  if (ligne) {
    if (!(ligne >= 2 && ligne <= sh.getLastRow())) throw new Error('Ligne d\'opération invalide');
    const r = sh.getRange(ligne, 1, 1, OP.NB).getValues()[0];
    date = versDate_(r[OP.DATE]) || date;
    libelle = texte_(r[OP.LIBELLE]);
  }
  const dossier = sousDossier_(dossier_(DOSSIER.JUSTIFS), String(date.getFullYear()));
  const nom = Utilities.formatDate(date, TZ, 'yyyy-MM-dd') + '_' + (libelle ? nomFichierPropre_(libelle).slice(0, 40) + '_' : '') +
              nomFichierPropre_(f.nom);
  const fichier = dossier.createFile(Utilities.newBlob(octets, f.mime, nom));
  if (ligne) {
    sh.getRange(ligne, OP.JUSTIF + 1).setRichTextValue(
      SpreadsheetApp.newRichTextValue().setText('📎 ' + texte_(f.nom)).setLinkUrl(fichier.getUrl()).build());
  }
  return { message: '📎 Justificatif enregistré' + (ligne ? ' et lié à l\'opération' : ''), url: fichier.getUrl() };
}

// ---------------------------------------------------------------------------
// 16. IMPORT DE RELEVÉ BANCAIRE (CSV) ET RAPPROCHEMENT AUTOMATIQUE
// ---------------------------------------------------------------------------

function decoderTexte_(octets) {
  const utf = Utilities.newBlob(octets).getDataAsString('UTF-8');
  if (utf.indexOf('�') >= 0) return Utilities.newBlob(octets).getDataAsString('ISO-8859-1');
  return utf.replace(/^﻿/, '');
}

function sansAccent_(s) {
  return texte_(s).toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '');
}

/** Lit un CSV de banque : en-tête avec Date + Libellé + (Débit/Crédit ou Montant). */
function lireReleveCsv_(texte) {
  const debut = texte.split(/\r?\n/).slice(0, 15).join('\n');
  const sep = (debut.match(/;/g) || []).length >= (debut.match(/,/g) || []).length ? ';'
            : ((debut.match(/\t/g) || []).length > 0 ? '\t' : ',');
  const rows = Utilities.parseCsv(texte, sep);
  let h = -1, iDate = -1, iLib = -1, iDeb = -1, iCre = -1, iMt = -1;
  for (let k = 0; k < Math.min(rows.length, 25); k++) {
    const c = rows[k].map(sansAccent_);
    const d = c.findIndex(function (x) { return x.indexOf('date') === 0 && x.indexOf('valeur') < 0; });
    const deb = c.findIndex(function (x) { return x.indexOf('debit') >= 0; });
    const cre = c.findIndex(function (x) { return x.indexOf('credit') >= 0; });
    const mt = c.findIndex(function (x) { return x.indexOf('montant') >= 0; });
    if (d >= 0 && (mt >= 0 || deb >= 0 || cre >= 0)) {
      h = k; iDate = d; iDeb = deb; iCre = cre; iMt = mt;
      iLib = c.findIndex(function (x) { return /libelle|operation|intitule|description|detail/.test(x); });
      break;
    }
  }
  if (h < 0) throw new Error('Format non reconnu : le fichier doit contenir une ligne d\'en-tête avec Date, Libellé et Débit/Crédit (ou Montant). Exportez le relevé en CSV depuis votre banque en ligne.');
  const res = [];
  for (let k = h + 1; k < rows.length; k++) {
    const r = rows[k];
    const date = versDate_(r[iDate]);
    if (!date) continue;
    let montant = NaN;
    if (iMt >= 0 && texte_(r[iMt]) !== '') montant = nombre_(r[iMt]);
    else {
      const cr = iCre >= 0 ? nombre_(r[iCre]) : NaN;
      const db = iDeb >= 0 ? nombre_(r[iDeb]) : NaN;
      if (!isNaN(cr) && cr !== 0) montant = Math.abs(cr);
      else if (!isNaN(db) && db !== 0) montant = -Math.abs(db);
    }
    if (isNaN(montant) || montant === 0) continue;
    res.push({ date: date, libelle: iLib >= 0 ? texte_(r[iLib]).replace(/\s+/g, ' ') : '', montant: arrondi_(montant) });
  }
  return res;
}

function motsCles_(s) {
  const vides = ['prlv', 'prelevement', 'vir', 'virement', 'sepa', 'carte', 'chq', 'cheque', 'remise', 'des', 'les', 'pour',
                 'par', 'ref', 'inst', 'recu', 'emis', 'facture', 'frais', 'paiement', 'achat', 'date', 'association'];
  return sansAccent_(s).replace(/[^a-z ]/g, ' ').split(/\s+/)
    .filter(function (w) { return w.length > 2 && vides.indexOf(w) < 0; });
}

/** Étape 1 : analyse le fichier et propose, ligne par ligne, rapprochement ou création. */
function analyserReleveWeb(f) {
  if (!f || !f.base64) throw new Error('Aucun fichier reçu');
  const bq = lireReleveCsv_(decoderTexte_(Utilities.base64Decode(f.base64)));
  if (!bq.length) throw new Error('Aucune opération lue dans le fichier');
  const t = lireOperations_();
  // Catégorie habituelle par libellé (la plus récente l'emporte)
  const habitudes = {};
  t.vals.forEach(function (r) {
    const cat = texte_(r[OP.CATEGORIE]);
    if (!cat) return;
    motsCles_(texte_(r[OP.LIBELLE]) + ' ' + texte_(r[OP.TIERS])).forEach(function (w) { habitudes[w] = cat; });
  });
  const pris = {};
  const lignes = bq.map(function (b) {
    let meilleur = -1, ecartMin = 999, meilleurRap = -1, ecartRap = 999;
    for (let i = 0; i < t.vals.length; i++) {
      if (pris[i]) continue;
      const r = t.vals[i];
      if (texte_(r[OP.SOURCE]) !== 'Banque') continue;
      if (arrondi_(nombre_(r[OP.MONTANT])) !== b.montant) continue;
      const d = versDate_(r[OP.DATE]);
      if (!d) continue;
      const ecart = Math.abs(d.getTime() - b.date.getTime()) / 86400000;
      if (ecart > 10) continue;
      if (estRapproche_(r[OP.RAPPROCHE])) { if (ecart < ecartRap) { ecartRap = ecart; meilleurRap = i; } }
      else if (ecart < ecartMin) { ecartMin = ecart; meilleur = i; }
    }
    let statut = 'nouveau', ligneCompta = 0, libelleCompta = '';
    const idx = meilleur >= 0 ? meilleur : meilleurRap;
    if (idx >= 0) {
      pris[idx] = true;
      statut = meilleur >= 0 ? 'rapprocher' : 'deja';
      ligneCompta = idx + 2;
      libelleCompta = texte_(t.vals[idx][OP.LIBELLE]);
    }
    let categorie = '';
    motsCles_(b.libelle).some(function (w) { if (habitudes[w]) { categorie = habitudes[w]; return true; } return false; });
    if (!categorie) categorie = b.montant < 0 && /frais|commission|cotisation carte|tenue de compte|abonnement/i.test(sansAccent_(b.libelle))
      ? 'Frais bancaires' : 'Autres';
    return { date: dateFr_(b.date), iso: Utilities.formatDate(b.date, TZ, 'yyyy-MM-dd'), libelle: b.libelle, montant: b.montant,
             statut: statut, ligneCompta: ligneCompta, libelleCompta: libelleCompta, categorie: categorie };
  });
  const compte = function (s) { return lignes.filter(function (l) { return l.statut === s; }).length; };
  return { lignes: lignes, nouveaux: compte('nouveau'), aRapprocher: compte('rapprocher'), deja: compte('deja') };
}

/** Étape 2 : applique les choix (coche les rapprochements, crée les nouvelles lignes, archive le relevé). */
function importerReleveWeb(f) {
  if (!f || !f.lignes) throw new Error('Rien à importer');
  const sh = feuille_(ONGLET.OPERATIONS);
  let nbRap = 0, nbNouv = 0;
  f.lignes.forEach(function (l) {
    if (!l.importer || l.statut !== 'rapprocher') return;
    const ligne = Number(l.ligneCompta);
    if (!(ligne >= 2 && ligne <= sh.getLastRow())) return;
    const mt = arrondi_(nombre_(sh.getRange(ligne, OP.MONTANT + 1).getValue()));
    if (mt !== arrondi_(l.montant)) return; // sécurité : la ligne a changé entre-temps
    sh.getRange(ligne, OP.RAPPROCHE + 1).setValue(true);
    nbRap++;
  });
  f.lignes.filter(function (l) { return l.importer && l.statut === 'nouveau'; })
    .sort(function (a, b) { return a.iso < b.iso ? -1 : a.iso > b.iso ? 1 : 0; })
    .forEach(function (l) {
      ajouterLigneOperation_({
        date: versDate_(l.iso), libelle: texte_(l.libelle) || 'Opération bancaire', montant: Math.abs(nombre_(l.montant)),
        type: nombre_(l.montant) < 0 ? 'Depense' : 'Recette', categorie: l.categorie, source: 'Banque',
        notes: 'Import relevé ' + texte_(f.nom), rapproche: true
      });
      nbNouv++;
    });
  let url = '';
  if (f.base64) {
    const octets = Utilities.base64Decode(f.base64);
    const dossier = sousDossier_(dossier_(DOSSIER.RELEVES), String(new Date().getFullYear()));
    url = dossier.createFile(Utilities.newBlob(octets, 'text/csv',
      Utilities.formatDate(new Date(), TZ, 'yyyy-MM-dd') + '_' + nomFichierPropre_(f.nom || 'releve.csv'))).getUrl();
  }
  return { message: '🏦 Relevé traité : ' + nbRap + ' écriture(s) rapprochée(s), ' + nbNouv + ' ajoutée(s)' +
                    (url ? '\n📁 Relevé archivé dans ' + DOSSIER.RELEVES : ''), url: url };
}

/** Archive un relevé PDF (consultation uniquement, pas de lecture automatique). */
function archiverRelevePdfWeb(f) {
  if (!f || !f.base64) throw new Error('Aucun fichier reçu');
  if (f.mime !== 'application/pdf') throw new Error('Seuls les PDF sont archivés ici');
  const octets = Utilities.base64Decode(f.base64);
  const dossier = sousDossier_(dossier_(DOSSIER.RELEVES), String(new Date().getFullYear()));
  const fichier = dossier.createFile(Utilities.newBlob(octets, 'application/pdf',
    Utilities.formatDate(new Date(), TZ, 'yyyy-MM-dd') + '_' + nomFichierPropre_(f.nom)));
  return { message: '📁 Relevé PDF archivé dans ' + DOSSIER.RELEVES, url: fichier.getUrl() };
}

// ---------------------------------------------------------------------------
// 17. BUDGET PRÉVISIONNEL
// ---------------------------------------------------------------------------

function feuilleBudget_() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let sh = ss.getSheetByName(ONGLET.BUDGET);
  if (!sh) {
    sh = ss.insertSheet(ONGLET.BUDGET);
    sh.getRange(1, 1, 1, ENTETES.BUDGET.length).setValues([ENTETES.BUDGET]).setFontWeight('bold').setBackground('#eeeeee');
  }
  return sh;
}

function lireBudget_(annee) {
  const vals = feuilleBudget_().getDataRange().getValues();
  const res = {};
  for (let i = 1; i < vals.length; i++) {
    if (Number(vals[i][0]) !== Number(annee)) continue;
    const type = texte_(vals[i][2]) === 'Recette' ? 'Recette' : 'Depense';
    res[type + '|' + texte_(vals[i][1])] = { categorie: texte_(vals[i][1]), type: type, prevu: nombreOu_(vals[i][3], 0) };
  }
  return res;
}

function comparerBudget_(annee) {
  const cfg = lireConfiguration();
  const p = periodeExercice_(annee, cfg);
  const f = analyserFinances_(p);
  const b = lireBudget_(annee);
  const map = {};
  Object.keys(b).forEach(function (k) { map[k] = { categorie: b[k].categorie, type: b[k].type, prevu: b[k].prevu, realise: 0 }; });
  Object.keys(f.recettes).forEach(function (c) {
    const k = 'Recette|' + c; map[k] = map[k] || { categorie: c, type: 'Recette', prevu: 0, realise: 0 }; map[k].realise = arrondi_(f.recettes[c]);
  });
  Object.keys(f.depenses).forEach(function (c) {
    const k = 'Depense|' + c; map[k] = map[k] || { categorie: c, type: 'Depense', prevu: 0, realise: 0 }; map[k].realise = arrondi_(f.depenses[c]);
  });
  const lignes = Object.keys(map).map(function (k) { return map[k]; }).sort(function (a, c) {
    return a.type === c.type ? a.categorie.localeCompare(c.categorie, 'fr') : (a.type === 'Recette' ? -1 : 1);
  });
  const somme = function (type, champ) {
    return arrondi_(lignes.filter(function (l) { return l.type === type; }).reduce(function (s, l) { return s + l[champ]; }, 0));
  };
  return { annee: Number(annee), libelle: p.libelle, lignes: lignes,
           prevuR: somme('Recette', 'prevu'), prevuD: somme('Depense', 'prevu'),
           realiseR: somme('Recette', 'realise'), realiseD: somme('Depense', 'realise') };
}

function lignesBudgetDoc_(b, avecRealise) {
  const t = avecRealise ? [['Type', 'Catégorie', 'Prévu', 'Réalisé', 'Écart']] : [['Type', 'Catégorie', 'Prévu']];
  b.lignes.forEach(function (l) {
    if (!l.prevu && !(avecRealise && l.realise)) return;
    const base = [l.type === 'Recette' ? 'Recette' : 'Dépense', l.categorie, euros_(l.prevu)];
    t.push(avecRealise ? base.concat([euros_(l.realise), euros_(l.realise - l.prevu)]) : base);
  });
  const totR = avecRealise ? ['TOTAL', 'Recettes', euros_(b.prevuR), euros_(b.realiseR), euros_(b.realiseR - b.prevuR)]
                           : ['TOTAL', 'Recettes', euros_(b.prevuR)];
  const totD = avecRealise ? ['TOTAL', 'Dépenses', euros_(b.prevuD), euros_(b.realiseD), euros_(b.realiseD - b.prevuD)]
                           : ['TOTAL', 'Dépenses', euros_(b.prevuD)];
  t.push(totR, totD);
  return t;
}

function budgetWeb(annee) {
  return comparerBudget_(Number(annee));
}

/** lignes = [{ categorie, type, prevu }] — remplace le budget de l'exercice. */
function enregistrerBudgetWeb(annee, lignes) {
  const a = Number(annee);
  if (!(a > 2000 && a < 2100)) throw new Error('Exercice invalide');
  const sh = feuilleBudget_();
  const vals = sh.getDataRange().getValues();
  for (let i = vals.length - 1; i >= 1; i--) if (Number(vals[i][0]) === a) sh.deleteRow(i + 1);
  const aEcrire = (lignes || []).filter(function (l) { return texte_(l.categorie) && nombreOu_(l.prevu, 0) > 0; })
    .map(function (l) { return [a, texte_(l.categorie), l.type === 'Recette' ? 'Recette' : 'Depense', arrondi_(nombre_(l.prevu))]; });
  if (aEcrire.length) sh.getRange(sh.getLastRow() + 1, 1, aEcrire.length, 4).setValues(aEcrire);
  return { message: '📒 Budget enregistré (' + aEcrire.length + ' ligne(s))' };
}

/** Propose un budget à partir du réalisé de l'exercice précédent (arrondi à la dizaine). */
function proposerBudgetWeb(annee) {
  const prec = comparerBudget_(Number(annee) - 1);
  return prec.lignes.filter(function (l) { return l.realise > 0; }).map(function (l) {
    return { categorie: l.categorie, type: l.type, prevu: Math.ceil(l.realise / 10) * 10 };
  });
}

// ---------------------------------------------------------------------------
// 18. INSTALLATION SUR UN NOUVEAU COMPTE GOOGLE
// ---------------------------------------------------------------------------

/**
 * Crée (ou retrouve) l'arborescence du club à côté du Google Sheets, range le Sheets
 * dans 01_Données_Principales et enregistre l'identifiant de chaque dossier dans Configuration.
 * Sans danger si on la relance : rien n'est supprimé ni dupliqué.
 */
function installerDossiers() {
  proteger_(function () {
    const ss = SpreadsheetApp.getActiveSpreadsheet();
    const fichier = DriveApp.getFileById(ss.getId());
    let racine = racineClub_();
    if (!racine) {
      const parents = fichier.getParents();
      const parent = parents.hasNext() ? parents.next() : DriveApp.getRootFolder();
      const existe = parent.getFoldersByName(NOM_DOSSIER_RACINE);
      racine = existe.hasNext() ? existe.next() : parent.createFolder(NOM_DOSSIER_RACINE);
    }
    const crees = [], trouves = [];
    Object.keys(CLE_DOSSIER).forEach(function (nom) {
      const it = racine.getFoldersByName(nom);
      let d;
      if (it.hasNext()) { d = it.next(); trouves.push(nom); }
      else { d = racine.createFolder(nom); crees.push(nom); }
      ecrireConfig_(CLE_DOSSIER[nom], d.getId());
    });
    const donnees = DriveApp.getFolderById(lireConfiguration()[CLE_DOSSIER['01_Données_Principales']]);
    const dejaRange = fichier.getParents().hasNext() && fichier.getParents().next().getId() === donnees.getId();
    if (!dejaRange) fichier.moveTo(donnees);
    completerConfigurationSilencieuse_();
    const logo = logoBlob_(lireConfiguration());
    info_('✅ Dossiers prêts dans « ' + racine.getName() + ' » (compte ' + Session.getEffectiveUser().getEmail() + ')\n\n' +
          (crees.length ? 'Créés : ' + crees.join(', ') + '\n' : '') +
          (trouves.length ? 'Déjà présents : ' + trouves.join(', ') + '\n' : '') +
          (dejaRange ? '' : 'Le Google Sheets a été rangé dans 01_Données_Principales.\n') +
          (logo ? '' : '\n⚠️ Logo introuvable : déposez-le dans 01_Données_Principales sous le nom indiqué en Configuration (Logo_Fichier).'));
  });
}

function completerConfigurationSilencieuse_() {
  const sh = feuille_(ONGLET.CONFIG);
  const vals = sh.getDataRange().getValues();
  const existantes = {};
  for (let i = 1; i < vals.length; i++) existantes[texte_(vals[i][0])] = true;
  const ajouts = CONFIG_CLES.filter(function (c) { return !existantes[c[0]]; });
  if (ajouts.length) sh.getRange(sh.getLastRow() + 1, 1, ajouts.length, 2).setValues(ajouts);
}
