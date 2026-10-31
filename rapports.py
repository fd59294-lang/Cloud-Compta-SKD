"""Rapports PDF : compte financier, bilan financier, rapport d'assemblée générale, comparaison d'exercices.
(ReportLab + graphiques matplotlib, même procédé que le logiciel du Comité des Fêtes.)"""
from __future__ import annotations

import io
from dataclasses import dataclass, field
from datetime import date

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
from reportlab.lib.pagesizes import A4  # noqa: E402
from reportlab.lib.units import cm  # noqa: E402
from reportlab.platypus import (Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer,  # noqa: E402
                                Table, TableStyle)

import documents as D  # noqa: E402
from metier import (bornes_exercice, budget_compare, eur, libelle_exercice, mensuel, nom_categorie,  # noqa: E402
                    soldes, synthese_categories, totaux)

VERT, ROUGE_HEX, GRIS_HEX = "#2E7D32", "#C8102E", "#9E9E9E"

SECTIONS_AG = {
    "moral": "Rapport moral et d'activité",
    "adherents": "Adhérents",
    "finances": "Compte de résultat",
    "tresorerie": "Trésorerie",
    "graphique": "Recettes et dépenses par mois",
    "dons": "Dons",
    "budget_realise": "Budget prévu / réalisé",
    "budget_suivant": "Budget prévisionnel de l'exercice suivant",
    "perspectives": "Perspectives",
    "resolutions": "Résolutions soumises au vote",
}


@dataclass
class DonneesRapport:
    club: dict
    logo: bytes | None
    exercice: int
    mois_debut: int
    operations: pd.DataFrame            # typées (metier.typer_operations)
    budget: pd.DataFrame
    etat_adherents: dict = field(default_factory=dict)   # adherents.statistiques_saison
    dons: pd.DataFrame = field(default_factory=pd.DataFrame)
    texte_moral: str = ""
    texte_perspectives: str = ""
    resolutions: str = ("Approbation du rapport moral et d'activité\nApprobation des comptes de l'exercice et quitus "
                        "au trésorier\nAffectation du résultat\nVote du budget prévisionnel\nMontant des cotisations "
                        "de la saison suivante")
    signataires: dict = field(default_factory=dict)
    sections: list = field(default_factory=lambda: list(SECTIONS_AG))


# ------------------------------------------------------------------ éléments
def _h1(t):
    return Paragraph(D._echapper(t), D.ParagraphStyle("h1", parent=D.S["h"], fontSize=13, leading=17,
                                                      textColor=D.ROUGE, spaceBefore=10, spaceAfter=6))


def _texte_libre(t: str) -> list:
    return [D._p(D._echapper(ligne)) for ligne in str(t or "").splitlines() if ligne.strip()] or \
           [D._p("<i>(à compléter)</i>")]


def _image(fig, largeur_cm: float) -> Image:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=200, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    img = Image(buf)
    img.drawWidth = largeur_cm * cm
    img.drawHeight = largeur_cm * cm * img.imageHeight / img.imageWidth
    return img


def graphique_mensuel(ops: pd.DataFrame, exercice: int, mois_debut: int):
    m = mensuel(ops, exercice, mois_debut)
    fig, ax = plt.subplots(figsize=(8, 2.8))
    x = range(len(m))
    ax.bar([i - 0.2 for i in x], m["Recettes"], width=0.4, color=VERT, label="Recettes")
    ax.bar([i + 0.2 for i in x], m["Dépenses"], width=0.4, color=ROUGE_HEX, label="Dépenses")
    ax.set_xticks(list(x), m["mois"], fontsize=8)
    for cote in ("top", "right", "left"):
        ax.spines[cote].set_visible(False)
    ax.tick_params(axis="y", labelsize=8)
    ax.grid(axis="y", color="#E0E0E0", linewidth=0.6)
    ax.set_axisbelow(True)
    ax.legend(fontsize=8, frameon=False, loc="upper right")
    return fig


def _categories(ops, exercice, sens, couleur) -> list:
    s = synthese_categories(ops, exercice)
    s = s[s["sens"] == sens]
    total = float(s["montant"].sum())
    lignes = [["Catégorie", "Montant", "Part"]]
    lignes += [[nom_categorie(r.categorie), eur(r.montant), f"{r.montant / total * 100:.0f} %" if total else "—"]
               for r in s.itertuples()]
    lignes.append(["TOTAL", eur(total), "100 %" if total else "—"])
    return [D._tableau(lignes, [11 * cm, 3.6 * cm, 2.4 * cm], droite=(1, 2), total_derniere=True, couleur=couleur)]


def _tresorerie(d: DonneesRapport) -> list:
    debut, fin = bornes_exercice(d.exercice, d.mois_debut)
    a = soldes(d.operations, avant=debut)
    b = soldes(d.operations, jusqu_au=fin)
    lignes = [["Trésorerie", f"au {debut:%d/%m/%Y}", f"au {fin:%d/%m/%Y}"],
              ["Compte bancaire", eur(a["banque"]), eur(b["banque"])],
              ["Caisse (espèces)", eur(a["caisse"]), eur(b["caisse"])],
              ["TOTAL", eur(a["banque"] + a["caisse"]), eur(b["banque"] + b["caisse"])]]
    return [D._tableau(lignes, [8.6 * cm, 4.2 * cm, 4.2 * cm], droite=(1, 2), total_derniere=True)]


def _compte_resultat(d: DonneesRapport) -> list:
    t = totaux(d.operations, d.exercice)
    h = [D._p("Recettes", "h")] + _categories(d.operations, d.exercice, "Recette", D.colors.HexColor(VERT))
    h += [D._p("Dépenses", "h")] + _categories(d.operations, d.exercice, "Dépense", D.ROUGE)
    resultat = [["Résultat de l'exercice", eur(t["resultat"])]]
    tb = Table([[D._p(f"<b>{a}</b>"), D._p(f"<b>{b}</b>", "droite")] for a, b in resultat],
               colWidths=[13.4 * cm, 3.6 * cm])
    tb.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), D.GRIS), ("TOPPADDING", (0, 0), (-1, -1), 5),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
    return h + [Spacer(1, 0.2 * cm), tb]


def _budget(d: DonneesRapport, exercice: int, avec_realise: bool) -> list:
    b = budget_compare(d.operations, d.budget, exercice)
    if not avec_realise or b["prevu"].sum() == 0:
        b = b[b["prevu"] > 0]
    if b.empty:
        return [D._p("<i>Aucun budget saisi pour cet exercice.</i>")]
    if avec_realise:
        lignes = [["Sens", "Catégorie", "Prévu", "Réalisé", "Écart"]]
        lignes += [[r.sens, nom_categorie(r.categorie), eur(r.prevu), eur(r.realise), eur(r.ecart, signe=True)]
                   for r in b.itertuples()]
        largeurs, droite = [2 * cm, 7.4 * cm, 2.6 * cm, 2.6 * cm, 2.4 * cm], (2, 3, 4)
    else:
        lignes = [["Sens", "Catégorie", "Prévu", "Réalisé n-1"]]
        lignes += [[r.sens, nom_categorie(r.categorie), eur(r.prevu), eur(r.realise_n1)] for r in b.itertuples()]
        largeurs, droite = [2 * cm, 9.2 * cm, 2.9 * cm, 2.9 * cm], (2, 3)
    pr = b.loc[b["sens"] == "Recette", "prevu"].sum()
    pd_ = b.loc[b["sens"] == "Dépense", "prevu"].sum()
    lignes.append(["", "Résultat prévu", eur(pr - pd_)] + [""] * (len(lignes[0]) - 3))
    return [D._tableau(lignes, largeurs, droite=droite, total_derniere=True)]


def _signatures(d: DonneesRapport) -> list:
    if not d.signataires:
        return []
    cellules = [[D._p(f"<b>{D._echapper(r)}</b><br/>{D._echapper(n)}<br/><br/><br/>Signature")
                 for r, n in d.signataires.items()]]
    t = Table(cellules, colWidths=[17 * cm / len(d.signataires)] * len(d.signataires))
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    return [Spacer(1, 0.8 * cm), D._p(f"Fait le {date.today():%d/%m/%Y}"), Spacer(1, 0.3 * cm), KeepTogether([t])]


def _document(titre: str, d: DonneesRapport, histoire: list) -> bytes:
    buf = io.BytesIO()
    pied_txt = f"{d.club.get('nom_association', '')} — {titre}"

    def pied(canvas, doc):
        canvas.saveState()
        canvas.setFont("DejaVu", 7.5)
        canvas.setFillColor(D.GRIS_TEXTE)
        canvas.drawString(1.8 * cm, 1 * cm, pied_txt)
        canvas.drawRightString(A4[0] - 1.8 * cm, 1 * cm, f"Page {doc.page}")
        canvas.restoreState()

    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=1.8 * cm, rightMargin=1.8 * cm, topMargin=1.4 * cm,
                            bottomMargin=1.6 * cm, title=pied_txt, author=d.club.get("nom_association", ""))
    while histoire and isinstance(histoire[-1], PageBreak):
        histoire.pop()
    doc.build(histoire, onFirstPage=pied, onLaterPages=pied)
    return buf.getvalue()


# ------------------------------------------------------------------ compte financier (feuille Excel d'origine)
def compte_financier(d: DonneesRapport) -> bytes:
    lib = libelle_exercice(d.exercice, d.mois_debut)
    debut, fin = bornes_exercice(d.exercice, d.mois_debut)
    h = D._entete(d.club, d.logo)
    h += [D._p(f"COMPTE FINANCIER {lib}", "titre"),
          D._p(f"Récapitulatif des recettes et des dépenses du {debut:%d/%m/%Y} au {fin:%d/%m/%Y}", "sous_titre")]
    h += [D._p("Trésorerie", "h")] + _tresorerie(d)
    h += _compte_resultat(d)
    h += [D._p(f"Trésorier(ère) : {D._echapper(d.club.get('tresorier'))}", "note")] if d.club.get("tresorier") else []
    h += _signatures(d)
    return _document(f"Compte financier {lib}", d, h)


# ------------------------------------------------------------------ bilan financier
def bilan_financier(d: DonneesRapport) -> bytes:
    lib = libelle_exercice(d.exercice, d.mois_debut)
    t = totaux(d.operations, d.exercice)
    h = D._entete(d.club, d.logo)
    h += [D._p(f"BILAN FINANCIER {lib}", "titre"), D._p(f"{t['nb']} écritures", "sous_titre")]
    synth = [["Synthèse", "Montant"], ["Recettes", eur(t["recettes"])], ["Dépenses", eur(t["depenses"])],
             ["RÉSULTAT", eur(t["resultat"])]]
    h += [Spacer(1, 0.2 * cm), D._tableau(synth, [13.4 * cm, 3.6 * cm], droite=(1,), total_derniere=True)]
    h += [D._p("Trésorerie", "h")] + _tresorerie(d)
    h += [D._p("Recettes et dépenses par mois", "h"), _image(graphique_mensuel(d.operations, d.exercice,
                                                                               d.mois_debut), 17)]
    h += _compte_resultat(d)
    h += [D._p("Budget prévu / réalisé", "h")] + _budget(d, d.exercice, True)
    h += _signatures(d)
    return _document(f"Bilan financier {lib}", d, h)


# ------------------------------------------------------------------ rapport d'AG
def rapport_ag(d: DonneesRapport) -> bytes:
    lib = libelle_exercice(d.exercice, d.mois_debut)
    h = D._entete(d.club, d.logo)
    h += [Spacer(1, 0.6 * cm), D._p("ASSEMBLÉE GÉNÉRALE ORDINAIRE", "titre"),
          D._p(f"Rapport d'activité et rapport financier – saison {lib}", "numero"), Spacer(1, 0.4 * cm)]
    t = totaux(d.operations, d.exercice)
    e = d.etat_adherents or {}
    resume = [["Indicateur", "Valeur"],
              ["Adhérents inscrits", str(e.get("inscrits", "—"))],
              ["dont nouveaux", str(e.get("nouveaux", "—"))],
              ["Recettes", eur(t["recettes"])], ["Dépenses", eur(t["depenses"])],
              ["Résultat de l'exercice", eur(t["resultat"])]]
    h += [D._tableau(resume, [13.4 * cm, 3.6 * cm], droite=(1,))]
    n = 0
    for s in d.sections:
        n += 1
        titre = f"{n}. {SECTIONS_AG[s]}"
        if s == "moral":
            h += [_h1(titre)] + _texte_libre(d.texte_moral)
        elif s == "adherents":
            lignes = [["Adhérents", "Nombre"], ["Inscrits sur la saison", str(e.get("inscrits", 0))],
                      ["Nouveaux adhérents", str(e.get("nouveaux", 0))],
                      ["Cotisation réglée", str(e.get("a_jour", 0))], ["Paiement partiel", str(e.get("partiels", 0))],
                      ["En attente de paiement", str(e.get("en_attente", 0))],
                      ["Cotisations encaissées", eur(e.get("encaisse", 0))],
                      ["Reste à encaisser", eur(e.get("reste", 0))]]
            h += [_h1(titre), D._tableau(lignes, [13.4 * cm, 3.6 * cm], droite=(1,))]
        elif s == "finances":
            h += [_h1(titre)] + _compte_resultat(d)
        elif s == "tresorerie":
            h += [_h1(titre)] + _tresorerie(d)
        elif s == "graphique":
            h += [_h1(titre), _image(graphique_mensuel(d.operations, d.exercice, d.mois_debut), 17)]
        elif s == "dons":
            dn = d.dons
            if dn is None or dn.empty:
                h += [_h1(titre), D._p("Aucun don enregistré sur la saison.")]
            else:
                h += [_h1(titre), D._p(f"{len(dn)} don(s) reçu(s) pour un total de {eur(dn['montant'].sum())}. "
                                       "Merci à nos donateurs.")]
        elif s == "budget_realise":
            h += [_h1(titre)] + _budget(d, d.exercice, True)
        elif s == "budget_suivant":
            h += [_h1(f"{n}. Budget prévisionnel {libelle_exercice(d.exercice + 1, d.mois_debut)}")]
            h += _budget(d, d.exercice + 1, False)
        elif s == "perspectives":
            h += [_h1(titre)] + _texte_libre(d.texte_perspectives)
        elif s == "resolutions":
            h += [_h1(titre)] + [D._p("• " + D._echapper(r)) for r in d.resolutions.splitlines() if r.strip()]
    h += _signatures(d)
    return _document(f"Assemblée générale {lib}", d, h)


# ------------------------------------------------------------------ comparaison de deux exercices
def comparatif(d: DonneesRapport, ex1: int, ex2: int) -> bytes:
    l1, l2 = libelle_exercice(ex1, d.mois_debut), libelle_exercice(ex2, d.mois_debut)
    a, b = totaux(d.operations, ex1), totaux(d.operations, ex2)

    def evol(x, y):
        return f"{(y - x) / abs(x) * 100:+.0f} %" if x else "—"

    h = D._entete(d.club, d.logo)
    h += [D._p(f"COMPARAISON {l1} / {l2}", "titre"), Spacer(1, 0.2 * cm)]
    _, f1 = bornes_exercice(ex1, d.mois_debut)
    _, f2 = bornes_exercice(ex2, d.mois_debut)
    s1, s2 = soldes(d.operations, jusqu_au=f1), soldes(d.operations, jusqu_au=f2)
    t = [["Indicateur", l1, l2, "Évolution"],
         ["Recettes", eur(a["recettes"]), eur(b["recettes"]), evol(a["recettes"], b["recettes"])],
         ["Dépenses", eur(a["depenses"]), eur(b["depenses"]), evol(a["depenses"], b["depenses"])],
         ["Résultat", eur(a["resultat"]), eur(b["resultat"]), eur(b["resultat"] - a["resultat"], signe=True)],
         ["Trésorerie en fin d'exercice", eur(s1["banque"] + s1["caisse"]), eur(s2["banque"] + s2["caisse"]),
          eur(s2["banque"] + s2["caisse"] - s1["banque"] - s1["caisse"], signe=True)]]
    h += [D._tableau(t, [6.4 * cm, 3.6 * cm, 3.6 * cm, 3.4 * cm], droite=(1, 2, 3))]
    c1, c2 = synthese_categories(d.operations, ex1), synthese_categories(d.operations, ex2)
    cats = sorted(set(zip(c1["sens"], c1["categorie"])) | set(zip(c2["sens"], c2["categorie"])),
                  key=lambda x: (x[0] != "Recette", x[1]))
    lignes = [["Catégorie", l1, l2, "Évolution"]]
    for sens, cat in cats:
        x = float(c1.loc[(c1["sens"] == sens) & (c1["categorie"] == cat), "montant"].sum())
        y = float(c2.loc[(c2["sens"] == sens) & (c2["categorie"] == cat), "montant"].sum())
        lignes.append([("▲ " if sens == "Recette" else "▼ ") + nom_categorie(cat), eur(x), eur(y), evol(x, y)])
    h += [D._p("Détail par catégorie (▲ recettes, ▼ dépenses)", "h"),
          D._tableau(lignes, [8 * cm, 3.2 * cm, 3.2 * cm, 2.6 * cm], droite=(1, 2, 3))]
    return _document(f"Comparaison {l1} / {l2}", d, h)
