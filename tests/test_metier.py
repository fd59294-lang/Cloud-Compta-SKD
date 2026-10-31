"""Tests des règles métier (sans Streamlit ni Google)."""
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

import adherents as A
import documents as D
import metier
import rapports as R

EXCEL = Path(__file__).resolve().parents[2] / "Compte SKDtest .xlsm"


@pytest.fixture(scope="module")
def ops_excel():
    if not EXCEL.exists():
        pytest.skip("classeur d'origine absent (données réelles hors du dépôt)")
    livre, attente, _ = metier.lire_livre_excel(EXCEL.read_bytes())
    ops = metier.convertir_livre(livre, pd.DataFrame(), "test", 9, set())
    return ops, attente


def test_reprise_excel_retrouve_les_soldes_de_l_excel(ops_excel):
    ops, attente = ops_excel
    assert len(ops) == 105 and (ops["statut"] == "OK").all()
    s = metier.soldes(metier.typer_operations(ops.drop(columns="statut")))
    assert s["banque"] == 251.84          # « Solde final » de l'Excel
    assert s["pointe"] == 361.81          # « Solde rapproché » de l'Excel
    assert len(attente) == 10


def test_reprise_excel_sans_doublon_au_second_passage(ops_excel):
    ops, _ = ops_excel
    t = metier.typer_operations(ops.drop(columns="statut"))
    livre, _, _ = metier.lire_livre_excel(EXCEL.read_bytes())
    deuxieme = metier.convertir_livre(livre, pd.DataFrame(), "test", 9, metier.empreintes_existantes(t))
    assert (deuxieme["statut"] == "Doublon").all()


def test_exercice_septembre_aout():
    assert metier.exercice_de(date(2025, 9, 1), 9) == 2025
    assert metier.exercice_de(date(2026, 8, 31), 9) == 2025
    assert metier.libelle_exercice(2025, 9) == "2025-2026"
    assert metier.bornes_exercice(2025, 9) == (date(2025, 9, 1), date(2026, 8, 31))


@pytest.mark.parametrize("montant,attendu", [
    (1, "un euro"), (21, "vingt et un euros"), (71, "soixante et onze euros"), (80, "quatre-vingts euros"),
    (81, "quatre-vingt-un euros"), (200, "deux cents euros"), (250, "deux cent cinquante euros"),
    (2000, "deux mille euros"), (129.5, "cent vingt-neuf euros et cinquante centimes")])
def test_montant_en_lettres(montant, attendu):
    assert metier.en_lettres(montant) == attendu


def test_releve_csv_et_rapprochement():
    csv = ("Date;Date de valeur;Débit;Crédit;Libellé;Solde\n"
           "09/10/2026;09/10/2026;3,88;;FRAIS PAQUET ASSOCIATION;100\n"
           "12/10/2026;12/10/2026;;139,00;VIR SEPA DUPONT COTISATION;239\n"
           "15/10/26;15/10/26;-45,00;;CB DECATHLON;194\n").encode("latin-1")
    rel = metier.lire_releve_csv(csv)
    assert rel["montant"].tolist() == [-3.88, 139.0, -45.0]
    ops = metier.typer_operations(pd.DataFrame([
        metier.nouvelle_operation(date(2026, 10, 10), "Recette", "756 — Cotisations des adhérents", "Cotisation DUPONT",
                                  139, "Banque", "Virement", "DUPONT", "", "", "t", 9),
        metier.nouvelle_operation(date(2026, 9, 9), "Dépense", "627 — Frais bancaires", "Frais tenue de compte",
                                  3.88, "Banque", "", "Crédit Mutuel", "", "", "t", 9, rapproche=True)]))
    cats = ["627 — Frais bancaires", "606 — Achat de matériel et d'équipement", "756 — Cotisations des adhérents"]
    a = metier.analyser_releve(rel, ops, cats)
    assert a["resultat"].tolist() == ["Nouvelle", "À rapprocher", "Nouvelle"]
    assert a.loc[0, "categorie"] == "627 — Frais bancaires"


def test_adherents_reste_du_et_statuts():
    adh = pd.DataFrame([{"id": "a1", "licence": "590 001", "nom": "DUPONT", "prenom": "Léo", "date_naissance": "2016-03-01",
                         "responsable_legal": "DUPONT Marie", "famille": "DUPONT", "email": "", "telephone": "",
                         "adresse": "", "premiere_saison": 2026, "notes": "", "actif": "oui", "cree_le": ""},
                        {"id": "a2", "licence": "590002", "nom": "DUPONT", "prenom": "Zoé", "date_naissance": "2010-03-01",
                         "responsable_legal": "", "famille": "DUPONT", "email": "", "telephone": "", "adresse": "",
                         "premiere_saison": 2026, "notes": "", "actif": "oui", "cree_le": ""}])
    ins = pd.DataFrame([{"id": "i1", "adherent_id": "a1", "saison": 2026, "tarif": "Enfant", "cotisation": 129,
                         "frais_adhesion": 0, "reduction": 0, "total_du": 129, "date_inscription": "", "notes": "",
                         "cree_par": ""}])
    pai = pd.DataFrame([{"id": "p1", "inscription_id": "i1", "adherent_id": "a1", "saison": 2026, "date": "2026-09-15",
                         "montant": 50, "mode": "Chèque", "payeur": "", "operation_id": "", "recu": "", "saisi_par": "",
                         "saisi_le": ""}])
    e = A.etat_saison(adh, ins, pai, 2026)
    assert e.loc[0, "reste"] == 79 and e.loc[0, "statut"] == "Partiel"
    assert A.trouver_par_licence(adh, "590001")["id"] == "a1"
    assert A.membre_famille_deja_inscrit(adh, ins, "a2", 2026) == "DUPONT Léo"
    tarifs = pd.DataFrame([{"saison": 2026, "nom": "Enfant", "age_min": 0, "age_max": 12, "cotisation": 129, "dont_licence": 39},
                           {"saison": 2026, "nom": "Adulte", "age_min": 13, "age_max": 120, "cotisation": 139, "dont_licence": 39}])
    assert A.tarif_suggere(tarifs, 2026, "2016-03-01", date(2026, 9, 1)) == "Enfant"
    assert A.tarif_suggere(tarifs, 2027, "2010-03-01", date(2027, 9, 1)) == "Adulte"   # tarifs repris de 2026


def test_documents_pdf_une_page(tmp_path):
    club = {"nom_association": "Club Exemple", "adresse": "1 rue X", "code_postal_ville": "59000 VILLE",
            "iban": "FR76 0000", "rna": "W000", "tresorier": "T. Exemple", "president": "P. Exemple"}
    for pdf in (D.facture(club, None, "FAC-2026-001", "A", "adr", "", [("Cotisation", 1, 129)], 50),
                D.recu_paiement(club, None, "REC-2026-001", "B", "C", "590001", "B", "cotisation", 50, "Chèque",
                                date(2026, 9, 15)),
                D.recu_fiscal(club, None, "DON-2026-001", "D", "adr", 100, date(2026, 10, 1), "Numéraire", "Chèque"),
                D.remboursement_frais(club, None, "RF-2026-001", "E", "adr", "obj", [(date(2026, 10, 1), "péage", 12)],
                                      "Virement")):
        assert pdf.startswith(b"%PDF") and pdf.count(b"/Type /Page\n") + pdf.count(b"/Type /Page ") <= 2


def test_rapports(ops_excel):
    ops, _ = ops_excel
    t = metier.typer_operations(ops.drop(columns="statut"))
    d = R.DonneesRapport(club={"nom_association": "Club"}, logo=None, exercice=2024, mois_debut=9, operations=t,
                         budget=pd.DataFrame(columns=["exercice", "categorie", "sens", "prevu", "commentaire", "maj_le"]))
    for pdf in (R.compte_financier(d), R.bilan_financier(d), R.rapport_ag(d), R.comparatif(d, 2023, 2024)):
        assert pdf.startswith(b"%PDF")
    s = metier.synthese_mensuelle(t, 2024, 9)
    assert s.iloc[-1]["Catégorie"] == "Total général"
    assert round(s.iloc[-1]["Total"], 2) == metier.totaux(t, 2024)["resultat"]


def test_reprise_version_apps_script():
    df = pd.DataFrame([
        {"Date": "2026-10-01", "Libelle": "Cotisation DUPONT", "Montant": 129, "Type": "Recette", "Categorie": "Cotisations",
         "Tiers": "DUPONT", "Notes": "", "Numero_Piece": "REC-2026-001", "Source": "Banque", "Rapproche": True,
         "Solde_Cumule": 129, "Justificatif": ""},
        {"Date": "2026-10-02", "Libelle": "Assurance", "Montant": -39.42, "Type": "Depense", "Categorie": "Assurances",
         "Tiers": "MAIF", "Notes": "", "Numero_Piece": "", "Source": "Especes", "Rapproche": False, "Solde_Cumule": 0,
         "Justificatif": ""}])
    ops = metier.convertir_operations_apps_script(df, pd.DataFrame(), "t", 9, set())
    assert ops["sens"].tolist() == ["Recette", "Dépense"]
    assert ops["montant"].tolist() == [129.0, 39.42]
    assert ops["source"].tolist() == ["Banque", "Espèces"]
    assert ops["rapproche"].tolist() == ["oui", "non"]
    assert ops["categorie"].tolist() == ["756 — Cotisations des adhérents", "616 — Assurances"]


def test_categorie_inconnue_a_classer():
    cat, reconnu = metier.trouver_categorie("Buvette du gala", "Recette")
    assert not reconnu and cat.startswith("R99")


def test_releve_valide_verrouille_les_ecritures_pointees():
    rel = pd.DataFrame([{"id": "r1", "date_releve": "2025-08-31", "solde_releve": 361.81, "solde_pointe": 361.81,
                         "ecart": 0, "fichier": "", "cree_par": "", "cree_le": "", "valide": "oui"},
                        {"id": "r2", "date_releve": "2025-09-30", "solde_releve": 300, "solde_pointe": 300,
                         "ecart": 0, "fichier": "", "cree_par": "", "cree_le": "", "valide": "annulé"}])
    assert metier.dernier_releve_valide(rel) == (date(2025, 8, 31), 361.81)
    ops = metier.typer_operations(pd.DataFrame([
        metier.nouvelle_operation(date(2025, 8, 9), "Dépense", "627 — Frais bancaires", "a", 3.97, "Banque", "", "",
                                  "", "", "t", 9, rapproche=True),
        metier.nouvelle_operation(date(2025, 8, 20), "Dépense", "606 — Achat", "chèque non débité", 40, "Banque", "",
                                  "", "", "", "t", 9),
        metier.nouvelle_operation(date(2025, 9, 9), "Dépense", "627 — Frais bancaires", "b", 3.97, "Banque", "", "",
                                  "", "", "t", 9, rapproche=True)]))
    assert metier.verrouillees(ops, date(2025, 8, 31)).tolist() == [True, False, False]
    assert not metier.verrouillees(ops, None).any()
