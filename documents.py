"""Documents PDF du club : facture, reçu / attestation de paiement, reçu fiscal (Cerfa 11580),
fiche de remboursement de frais. Mise en page sur une page A4, avec le logo et les mentions du club."""
from __future__ import annotations

import io
import os
from datetime import date

import matplotlib
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from metier import en_lettres, eur

_POLICES = os.path.join(matplotlib.get_data_path(), "fonts", "ttf")
if "DejaVu" not in pdfmetrics.getRegisteredFontNames():
    pdfmetrics.registerFont(TTFont("DejaVu", os.path.join(_POLICES, "DejaVuSans.ttf")))
    pdfmetrics.registerFont(TTFont("DejaVu-Bold", os.path.join(_POLICES, "DejaVuSans-Bold.ttf")))
    pdfmetrics.registerFont(TTFont("DejaVu-Oblique", os.path.join(_POLICES, "DejaVuSans-Oblique.ttf")))
    pdfmetrics.registerFontFamily("DejaVu", normal="DejaVu", bold="DejaVu-Bold", italic="DejaVu-Oblique")

ROUGE = colors.HexColor("#C8102E")
NOIR = colors.HexColor("#1A1A1A")
GRIS = colors.HexColor("#F2F2F2")
GRIS_TEXTE = colors.HexColor("#616161")

S = {
    "club": ParagraphStyle("club", fontName="DejaVu-Bold", fontSize=15, leading=18, alignment=TA_CENTER),
    "entete": ParagraphStyle("entete", fontName="DejaVu", fontSize=8.5, leading=11, alignment=TA_CENTER,
                             textColor=GRIS_TEXTE),
    "titre": ParagraphStyle("titre", fontName="DejaVu-Bold", fontSize=14, leading=18, alignment=TA_CENTER,
                            textColor=ROUGE, spaceBefore=6, spaceAfter=2),
    "sous_titre": ParagraphStyle("sous_titre", fontName="DejaVu-Oblique", fontSize=8, leading=10,
                                 alignment=TA_CENTER, textColor=GRIS_TEXTE),
    "numero": ParagraphStyle("numero", fontName="DejaVu-Bold", fontSize=10, leading=13, alignment=TA_CENTER),
    "h": ParagraphStyle("h", fontName="DejaVu-Bold", fontSize=9.5, leading=13, spaceBefore=8, spaceAfter=2),
    "texte": ParagraphStyle("texte", fontName="DejaVu", fontSize=9.5, leading=13),
    "grand": ParagraphStyle("grand", fontName="DejaVu-Bold", fontSize=12, leading=16, alignment=TA_CENTER,
                            spaceBefore=4, spaceAfter=4),
    "droite": ParagraphStyle("droite", fontName="DejaVu", fontSize=9.5, leading=13, alignment=TA_RIGHT),
    "droite_g": ParagraphStyle("droite_g", fontName="DejaVu-Bold", fontSize=9.5, leading=13, alignment=TA_RIGHT),
    "note": ParagraphStyle("note", fontName="DejaVu", fontSize=7.5, leading=10, textColor=GRIS_TEXTE),
    "cel": ParagraphStyle("cel", fontName="DejaVu", fontSize=8.5, leading=11),
    "cel_d": ParagraphStyle("cel_d", fontName="DejaVu", fontSize=8.5, leading=11, alignment=TA_RIGHT),
    "pied": ParagraphStyle("pied", fontName="DejaVu", fontSize=7, leading=9, alignment=TA_CENTER,
                           textColor=GRIS_TEXTE),
}


def _p(texte, style="texte"):
    return Paragraph(str(texte or "").replace("\n", "<br/>"), S[style])


def _echapper(t) -> str:
    return str(t or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _entete(club: dict, logo: bytes | None) -> list:
    elements = []
    if logo:
        try:
            img = Image(io.BytesIO(logo))
            ratio = img.imageHeight / img.imageWidth
            img.drawWidth, img.drawHeight = 2.4 * cm, 2.4 * cm * ratio
            elements.append(img)
        except Exception:
            pass
    elements.append(_p(_echapper(club.get("nom_association", "")).upper(), "club"))
    lignes = [" – ".join(x for x in (club.get("adresse"), club.get("code_postal_ville")) if x),
              " – ".join(x for x in (club.get("email"), club.get("telephone")) if x)]
    elements.append(_p("<br/>".join(_echapper(x) for x in lignes if x), "entete"))
    return elements


def _pied(club: dict) -> list:
    morceaux = ["Association loi 1901"]
    for cle, lib in (("rna", "RNA"), ("siret", "SIRET"), ("affiliation", "Affiliation FFKaraté")):
        if club.get(cle):
            morceaux.append(f"{lib} {club[cle]}")
    return [Spacer(1, 0.4 * cm), _p(_echapper(" – ".join(morceaux)), "pied")]


def _tableau(lignes, largeurs, droite=(), total_derniere=False, couleur=NOIR):
    data = []
    for i, ligne in enumerate(lignes):
        rangee = []
        for j, v in enumerate(ligne):
            if isinstance(v, Paragraph):
                rangee.append(v)
                continue
            style = S["cel_d"] if j in droite else S["cel"]
            if i == 0:
                style = ParagraphStyle("entete_tableau", parent=style, textColor=colors.white)
            gras = i == 0 or (total_derniere and i == len(lignes) - 1)
            rangee.append(Paragraph(("<b>%s</b>" if gras else "%s") % _echapper(v), style))
        data.append(rangee)
    t = Table(data, colWidths=largeurs)
    style = [("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("BACKGROUND", (0, 0), (-1, 0), couleur),
             ("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.HexColor("#D0D0D0")),
             ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]
    if total_derniere:
        style.append(("BACKGROUND", (0, len(lignes) - 1), (-1, len(lignes) - 1), GRIS))
    t.setStyle(TableStyle(style))
    return t


def _signature(club: dict, qualite: str, nom: str) -> list:
    ville = club.get("ville_signature") or "……………"
    return [Spacer(1, 0.5 * cm), _p(f"Fait à {_echapper(ville)}, le {date.today():%d/%m/%Y}", "droite"),
            _p(f"<b>{qualite}</b>" + (f" : {_echapper(nom)}" if nom else ""), "droite"), Spacer(1, 1.6 * cm)]


def _construire(titre_doc: str, auteur: str, histoire: list) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=1.8 * cm, rightMargin=1.8 * cm, topMargin=1.2 * cm,
                            bottomMargin=1.2 * cm, title=titre_doc, author=auteur)
    doc.build(histoire)
    return buf.getvalue()


def _bloc_adresse(titre: str, nom: str, adresse: str = "", complement: str = "") -> list:
    contenu = f"<b>{_echapper(nom)}</b>"
    if complement:
        contenu += f"<br/>{_echapper(complement)}"
    if adresse:
        contenu += f"<br/>{_echapper(adresse)}"
    return [_p(titre, "h"), _p(contenu)]


# ------------------------------------------------------------------ facture
def facture(club: dict, logo: bytes | None, numero: str, destinataire: str, adresse: str, email: str,
            lignes: list[tuple[str, float, float]], deja_regle: float = 0.0, objet: str = "",
            echeance: str = "") -> bytes:
    """lignes = [(désignation, quantité, prix unitaire)]"""
    h = _entete(club, logo)
    h += [_p("FACTURE", "titre"), _p(f"N° {numero} – {date.today():%d/%m/%Y}", "numero")]
    h += _bloc_adresse("Adressée à", destinataire, adresse, email)
    if objet:
        h += [_p(f"<b>Objet :</b> {_echapper(objet)}")]
    total = sum(q * pu for _, q, pu in lignes)
    t = [["Désignation", "Quantité", "Prix unitaire", "Montant"]]
    t += [[d, f"{q:g}", eur(pu), eur(q * pu)] for d, q, pu in lignes]
    t.append(["TOTAL", "", "", eur(total)])
    if deja_regle:
        t.append(["Déjà réglé", "", "", "−" + eur(deja_regle)])
        t.append(["RESTE À PAYER", "", "", eur(total - deja_regle)])
    h += [Spacer(1, 0.3 * cm), _tableau(t, [9.4 * cm, 2 * cm, 3 * cm, 3 * cm], droite=(1, 2, 3), total_derniere=True)]
    h += [_p("Modalités de règlement", "h")]
    reglement = [f"• Chèque à l'ordre de « {_echapper(club.get('nom_association'))} »"]
    if club.get("iban"):
        reglement.append(f"• Virement : IBAN {_echapper(club['iban'])}" + (f" – BIC {_echapper(club['bic'])}"
                                                                              if club.get("bic") else ""))
    reglement.append("• Espèces contre reçu – Pass'Sport accepté – paiement en plusieurs fois possible")
    if echeance:
        reglement.append(f"• À régler avant le {_echapper(echeance)}")
    h += [_p("<br/>".join(reglement))]
    h += [Spacer(1, 0.2 * cm), _p("Association non assujettie à la TVA (article 261, 7-1° du code général des impôts).",
                                  "note")]
    h += _pied(club)
    return _construire(f"Facture {numero}", club.get("nom_association", ""), h)


# ------------------------------------------------------------------ reçu / attestation de paiement
def recu_paiement(club: dict, logo: bytes | None, numero: str, payeur: str, adherent: str, licence: str,
                  responsable_legal: str, objet: str, montant: float, mode: str, date_paiement: date,
                  detail: list[tuple[str, float]] | None = None, saison: str = "") -> bytes:
    """Attestation de paiement (reprend la formulation du « Reçu de cotisation » de l'Excel)."""
    h = _entete(club, logo)
    h += [_p("REÇU – ATTESTATION DE PAIEMENT", "titre"),
          _p(f"N° {numero} – paiement du {date_paiement:%d/%m/%Y}", "numero"), Spacer(1, 0.3 * cm)]
    tresorier = club.get("tresorier") or "le trésorier"
    qui = _echapper(payeur or responsable_legal or adherent)
    pour = ""
    if responsable_legal and responsable_legal.strip() and responsable_legal.strip() != adherent.strip():
        pour = f", responsable légal de <b>{_echapper(adherent)}</b>"
    elif payeur and payeur.strip() != adherent.strip():
        pour = f", pour <b>{_echapper(adherent)}</b>"
    licence_txt = f" (licence FFKaraté {_echapper(licence)})" if licence else ""
    texte = (f"Je soussigné(e), {_echapper(tresorier)}, trésorier(ère) de l'association "
             f"{_echapper(club.get('nom_association'))}, atteste que <b>{qui}</b>{pour}{licence_txt} a versé la somme "
             f"de <b>{eur(montant)}</b> ({en_lettres(montant)}) par {_echapper(mode.lower())} pour le règlement de : "
             f"{_echapper(objet)}{' – saison ' + _echapper(saison) if saison else ''}.")
    h += [_p(texte)]
    if detail:
        t = [["Détail de la saison", "Montant"]] + [[lib, eur(m)] for lib, m in detail]
        h += [Spacer(1, 0.3 * cm), _tableau(t, [13.4 * cm, 4 * cm], droite=(1,), total_derniere=True)]
    h += [Spacer(1, 0.2 * cm), _p("Ce reçu atteste du paiement. Une cotisation n'ouvre pas droit à réduction d'impôt.",
                                  "note")]
    h += _signature(club, "Le/la trésorier(ère)", club.get("tresorier", ""))
    h += _pied(club)
    return _construire(f"Reçu {numero}", club.get("nom_association", ""), h)


# ------------------------------------------------------------------ reçu fiscal (Cerfa 11580)
MODES_CERFA = {"Espèces": "Remise d'espèces", "Chèque": "Chèque",
               "Virement": "Virement, prélèvement, carte bancaire",
               "Carte bancaire": "Virement, prélèvement, carte bancaire",
               "Prélèvement": "Virement, prélèvement, carte bancaire"}


def recu_fiscal(club: dict, logo: bytes | None, numero: str, donateur: str, adresse: str, montant: float,
                date_don: date, nature: str, mode: str, description: str = "", duplicata: bool = False) -> bytes:
    h = _entete(club, logo)
    h += [_p("REÇU AU TITRE DES DONS À CERTAINS ORGANISMES D'INTÉRÊT GÉNÉRAL", "titre"),
          _p("Articles 200, 238 bis et 978 du code général des impôts – modèle Cerfa n° 11580", "sous_titre"),
          _p(f"Reçu n° {numero}" + ("  –  DUPLICATA" if duplicata else ""), "numero")]
    h += [_p("Bénéficiaire des versements", "h"),
          _p(f"<b>{_echapper(club.get('nom_association'))}</b><br/>"
             f"{_echapper(club.get('adresse'))} {_echapper(club.get('code_postal_ville'))}<br/>"
             f"Objet : {_echapper(club.get('objet_association'))}<br/>"
             f"Association loi 1901 d'intérêt général" + (f" – RNA {_echapper(club['rna'])}" if club.get("rna") else ""))]
    h += _bloc_adresse("Donateur", donateur, adresse)
    h += [Spacer(1, 0.2 * cm),
          _p("Le bénéficiaire reconnaît avoir reçu au titre des dons et versements ouvrant droit à réduction d'impôt, "
             "la somme de :"),
          _p(f"{eur(montant)}", "grand"), _p(f"<i>{_echapper(en_lettres(montant))}</i>", "numero"), Spacer(1, 0.2 * cm)]
    t = [["Date du versement", "Forme du don", "Nature du don", "Mode de versement"],
         [f"{date_don:%d/%m/%Y}", "Déclaration de don manuel", nature,
          "—" if nature != "Numéraire" else MODES_CERFA.get(mode, mode)]]
    h += [_tableau(t, [3.6 * cm, 4.6 * cm, 3.6 * cm, 5.6 * cm])]
    if description:
        h += [_p(f"<b>Description du don en nature :</b> {_echapper(description)}")]
    h += [Spacer(1, 0.2 * cm),
          _p("Le bénéficiaire certifie sur l'honneur que les dons et versements qu'il reçoit ouvrent droit à la "
             "réduction d'impôt prévue à l'article 200 du CGI.")]
    h += [_p(f"Pour un particulier, la réduction d'impôt est égale à 66 % des sommes versées, dans la limite de 20 % "
             f"du revenu imposable (soit ici {eur(montant * 0.66)} au maximum).", "note")]
    h += _signature(club, "Le/la président(e)", club.get("president", ""))
    h += _pied(club)
    return _construire(f"Reçu fiscal {numero}", club.get("nom_association", ""), h)


# ------------------------------------------------------------------ remboursement de frais
def remboursement_frais(club: dict, logo: bytes | None, numero: str, beneficiaire: str, adresse: str,
                        objet: str, lignes: list[tuple[date, str, float]], mode: str) -> bytes:
    h = _entete(club, logo)
    h += [_p("FICHE DE REMBOURSEMENT DE FRAIS", "titre"), _p(f"N° {numero} – {date.today():%d/%m/%Y}", "numero")]
    h += _bloc_adresse("Bénéficiaire", beneficiaire, adresse)
    if objet:
        h += [_p(f"<b>Objet :</b> {_echapper(objet)}")]
    total = sum(m for _, _, m in lignes)
    t = [["Date", "Descriptif de la dépense", "Montant"]]
    t += [[f"{d:%d/%m/%Y}" if d else "", lib, eur(m)] for d, lib, m in lignes]
    t.append(["", "TOTAL À REMBOURSER", eur(total)])
    h += [Spacer(1, 0.3 * cm), _tableau(t, [2.8 * cm, 11 * cm, 3.6 * cm], droite=(2,), total_derniere=True)]
    h += [_p(f"Remboursement par {_echapper(mode.lower())}, sur présentation des justificatifs joints.")]
    cellules = [[_p("<b>Le bénéficiaire</b><br/><br/><br/>Signature"),
                 _p(f"<b>Le/la trésorier(ère)</b><br/>{_echapper(club.get('tresorier'))}<br/><br/>Signature")]]
    sig = Table(cellules, colWidths=[8.7 * cm, 8.7 * cm])
    sig.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    h += [Spacer(1, 0.6 * cm), sig, Spacer(1, 1.2 * cm)]
    h += _pied(club)
    return _construire(f"Remboursement {numero}", club.get("nom_association", ""), h)
