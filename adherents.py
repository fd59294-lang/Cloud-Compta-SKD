"""Adhérents : fiche unique par licence FFKaraté, inscriptions par saison, paiements en plusieurs fois.

Une saison = un exercice (même mois de début). Le reste dû d'une inscription est
  cotisation + frais d'adhésion (première saison seulement) − réduction famille − paiements reçus.
"""
from __future__ import annotations

from datetime import date

import pandas as pd

from metier import lire_date, nombres, oui, sans_accent
from referentiel import TABLES


def normaliser_licence(v) -> str:
    return "".join(str(v or "").split()).upper()


def nom_complet(r) -> str:
    nom = str(r.get("nom", "") if isinstance(r, dict) else r["nom"]).strip().upper()
    prenom = str(r.get("prenom", "") if isinstance(r, dict) else r["prenom"]).strip()
    return f"{nom} {prenom}".strip()


def typer(df: pd.DataFrame, table: str, numeriques: tuple = ()) -> pd.DataFrame:
    df = df.copy()
    if df.empty:
        df = pd.DataFrame(columns=TABLES[table])
    for c in numeriques:
        df[c] = nombres(df[c]).fillna(0.0)
    return df


def trouver_par_licence(adherents: pd.DataFrame, licence: str) -> dict | None:
    lic = normaliser_licence(licence)
    if not lic or adherents.empty:
        return None
    x = adherents[adherents["licence"].map(normaliser_licence) == lic]
    return x.iloc[0].to_dict() if not x.empty else None


def age_au(naissance, jour: date) -> int | None:
    d = lire_date(naissance)
    if not d:
        return None
    return jour.year - d.year - ((jour.month, jour.day) < (d.month, d.day))


def tarifs_saison(tarifs: pd.DataFrame, saison: int) -> pd.DataFrame:
    t = typer(tarifs, "tarifs", ("age_min", "age_max", "cotisation", "dont_licence"))
    t["saison_n"] = nombres(t["saison"]).fillna(0).astype(int)
    propres = t[t["saison_n"] == int(saison)]
    if not propres.empty:
        return propres
    anterieures = t[t["saison_n"] < int(saison)]
    if anterieures.empty:
        return t[t["saison_n"] == t["saison_n"].min()] if not t.empty else t
    return anterieures[anterieures["saison_n"] == anterieures["saison_n"].max()]


def tarif_suggere(tarifs: pd.DataFrame, saison: int, naissance, debut_saison: date) -> str | None:
    t = tarifs_saison(tarifs, saison)
    if t.empty:
        return None
    age = age_au(naissance, debut_saison)
    if age is not None:
        for r in t.itertuples():
            if r.age_min <= age <= r.age_max:
                return r.nom
    return t.iloc[-1]["nom"]


def deja_inscrit_avant(inscriptions: pd.DataFrame, adherent_id: str, saison: int) -> bool:
    if inscriptions.empty:
        return False
    x = inscriptions[(inscriptions["adherent_id"] == adherent_id)
                     & (nombres(inscriptions["saison"]).fillna(0).astype(int) < int(saison))]
    return not x.empty


def membre_famille_deja_inscrit(adherents: pd.DataFrame, inscriptions: pd.DataFrame, adherent_id: str,
                                saison: int) -> str | None:
    """Nom d'un autre membre de la même famille déjà inscrit cette saison (réduction 2e membre)."""
    if adherents.empty or inscriptions.empty:
        return None
    moi = adherents[adherents["id"] == adherent_id]
    if moi.empty:
        return None
    famille = sans_accent(moi.iloc[0].get("famille") or "").strip()
    if not famille:
        return None
    ids = adherents.loc[(adherents["famille"].map(lambda f: sans_accent(f or "").strip()) == famille)
                        & (adherents["id"] != adherent_id), "id"]
    x = inscriptions[inscriptions["adherent_id"].isin(ids)
                     & (nombres(inscriptions["saison"]).fillna(0).astype(int) == int(saison))]
    if x.empty:
        return None
    autre = adherents[adherents["id"] == x.iloc[0]["adherent_id"]].iloc[0]
    return nom_complet(autre)


def etat_saison(adherents: pd.DataFrame, inscriptions: pd.DataFrame, paiements: pd.DataFrame,
                saison: int) -> pd.DataFrame:
    """Une ligne par inscription de la saison : dû, payé, reste, statut."""
    ins = typer(inscriptions, "inscriptions", ("cotisation", "frais_adhesion", "reduction", "total_du"))
    ins = ins[nombres(ins["saison"]).fillna(0).astype(int) == int(saison)]
    pai = typer(paiements, "paiements", ("montant",))
    payes = pai.groupby("inscription_id")["montant"].sum() if not pai.empty else pd.Series(dtype=float)
    adh = adherents.set_index("id") if not adherents.empty else pd.DataFrame(columns=TABLES["adherents"])
    lignes = []
    for r in ins.itertuples():
        a = adh.loc[r.adherent_id] if r.adherent_id in adh.index else None
        paye = float(payes.get(r.id, 0.0))
        reste = round(r.total_du - paye, 2)
        lignes.append({
            "inscription_id": r.id, "adherent_id": r.adherent_id,
            "licence": a["licence"] if a is not None else "", "nom": nom_complet(a) if a is not None else "?",
            "responsable_legal": a["responsable_legal"] if a is not None else "",
            "famille": a["famille"] if a is not None else "",
            "tarif": r.tarif, "cotisation": r.cotisation, "frais_adhesion": r.frais_adhesion,
            "reduction": r.reduction, "total_du": r.total_du, "paye": round(paye, 2), "reste": max(reste, 0.0),
            "trop_percu": max(-reste, 0.0),
            "statut": "À jour" if reste <= 0.004 else ("Partiel" if paye > 0 else "En attente"),
        })
    cols = ["inscription_id", "adherent_id", "licence", "nom", "responsable_legal", "famille", "tarif", "cotisation",
            "frais_adhesion", "reduction", "total_du", "paye", "reste", "trop_percu", "statut"]
    return pd.DataFrame(lignes, columns=cols).sort_values("nom").reset_index(drop=True)


def historique_adherent(adherent_id: str, inscriptions: pd.DataFrame, paiements: pd.DataFrame) -> pd.DataFrame:
    ins = typer(inscriptions, "inscriptions", ("total_du",))
    ins = ins[ins["adherent_id"] == adherent_id]
    pai = typer(paiements, "paiements", ("montant",))
    lignes = []
    for r in ins.itertuples():
        p = pai[pai["inscription_id"] == r.id]
        lignes.append({"saison": int(float(r.saison)), "tarif": r.tarif, "total_du": r.total_du,
                       "paye": float(p["montant"].sum()), "reglements": len(p)})
    return pd.DataFrame(lignes, columns=["saison", "tarif", "total_du", "paye", "reglements"]).sort_values(
        "saison", ascending=False)


def statistiques_saison(etat: pd.DataFrame, inscriptions: pd.DataFrame, saison: int) -> dict:
    nouveaux = 0
    if not inscriptions.empty:
        ins = inscriptions.copy()
        ins["s"] = nombres(ins["saison"]).fillna(0).astype(int)
        premieres = ins.groupby("adherent_id")["s"].min()
        nouveaux = int((premieres == int(saison)).sum())
    return {"inscrits": int(len(etat)), "nouveaux": nouveaux,
            "a_jour": int((etat["statut"] == "À jour").sum()), "partiels": int((etat["statut"] == "Partiel").sum()),
            "en_attente": int((etat["statut"] == "En attente").sum()),
            "encaisse": round(float(etat["paye"].sum()), 2), "reste": round(float(etat["reste"].sum()), 2)}


def adherents_actifs(adherents: pd.DataFrame) -> pd.DataFrame:
    if adherents.empty:
        return adherents
    return adherents[adherents["actif"].map(lambda v: str(v).strip() == "" or oui(v))]


# ------------------------------------------------------------------ import de l'export « licenciés » de l'extranet FFK
TARIF_PARTICULIER = "Tarif particulier (situation sociale)"


def lire_export_ffk(contenu: bytes) -> pd.DataFrame:
    """Export « LstExp_lstlic… .xls » de l'extranet FFKaraté : en réalité un texte tabulé (latin-1) dont les
    valeurs sont écrites ="…". Accepte aussi un vrai classeur Excel ou un CSV avec les mêmes colonnes."""
    import io
    df = None
    if contenu[:4] in (b"PK\x03\x04", b"\xd0\xcf\x11\xe0"):            # vrai .xlsx / .xls
        df = pd.read_excel(io.BytesIO(contenu), dtype=str)
    else:
        for enc in ("utf-8-sig", "cp1252", "latin-1"):
            try:
                texte = contenu.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        sep = "\t" if texte.count("\t") >= texte.count(";") else ";"
        df = pd.read_csv(io.StringIO(texte), sep=sep, dtype=str)
    df = df.fillna("").apply(lambda c: c.astype(str).str.strip().str.replace(r'^="(.*)"$', r"\1", regex=True))
    df.columns = [sans_accent(c).strip().lower().replace(".", "_").replace(" ", "_") for c in df.columns]
    return df


def _col(df: pd.DataFrame, *noms) -> str | None:
    for n in noms:
        if n in df.columns:
            return n
    return None


def preparer_import_ffk(ffk: pd.DataFrame, adherents: pd.DataFrame, inscriptions: pd.DataFrame,
                        tarifs: pd.DataFrame, mois_debut: int, utilisateur: str, maintenant: str,
                        nouvel_id, benevoles: set[str] | None = None) -> dict:
    """Fiches adhérents (une par licence) et inscriptions (une par saison) à partir d'exports FFK.

    Saison = celle de la fin de validité de la licence (31/08/2026 → saison 2025-2026).
    Aucun paiement ni aucune écriture comptable n'est créé : les cotisations sont déjà en comptabilité.
    benevoles = n° de licence des bénévoles : tarif « Bénévole », cotisation 0 (licence offerte par le club)."""
    from referentiel import TARIF_BENEVOLE
    benevoles = {normaliser_licence(x) for x in (benevoles or set())}
    from metier import bornes_exercice, exercice_de
    c_lic, c_nom, c_pre = _col(ffk, "code", "licence", "n_licence"), _col(ffk, "nom"), _col(ffk, "prenom")
    c_nai, c_vil = _col(ffk, "naissance", "date_de_naissance"), _col(ffk, "ville", "adresse")
    c_fin, c_deb = _col(ffk, "val_fin", "fin_validite"), _col(ffk, "val_debut", "debut_validite")
    c_etat, c_prod, c_cat = _col(ffk, "etat"), _col(ffk, "produit"), _col(ffk, "categorie")
    if not (c_lic and c_nom):
        raise ValueError("Colonnes « Code » (n° de licence) et « Nom » introuvables : ce n'est pas un export "
                         "des licenciés FFK. Colonnes lues : " + ", ".join(ffk.columns))
    adh = adherents.copy() if not adherents.empty else pd.DataFrame(columns=TABLES["adherents"])
    ins = inscriptions.copy() if not inscriptions.empty else pd.DataFrame(columns=TABLES["inscriptions"])
    par_licence = {normaliser_licence(r["licence"]): r["id"] for r in adh.to_dict("records") if r.get("licence")}
    deja = {(r["adherent_id"], int(float(r["saison"] or 0))) for r in ins.to_dict("records")}
    nouveaux, nouvelles, rapport = [], [], []
    for r in ffk.to_dict("records"):
        lic = normaliser_licence(r.get(c_lic))
        if not lic:
            continue
        if c_etat and r.get(c_etat) and sans_accent(r[c_etat]).lower() not in ("valide", "validee"):
            rapport.append({"licence": lic, "nom": r.get(c_nom, ""), "saison": "", "action": f"Ignoré ({r[c_etat]})"})
            continue
        fin = lire_date(str(r.get(c_fin, "")).split(" ")[0]) if c_fin else None
        deb = lire_date(str(r.get(c_deb, "")).split(" ")[0]) if c_deb else None
        if fin:
            saison = exercice_de(fin, mois_debut)          # fin de validité 31/08/2026 → saison 2025-2026
        elif deb:
            saison = exercice_de(deb, mois_debut)
        else:
            rapport.append({"licence": lic, "nom": r.get(c_nom, ""), "saison": "", "action": "Ignoré (pas de dates)"})
            continue
        naissance = lire_date(r.get(c_nai, "")) if c_nai else None
        nom, prenom = str(r.get(c_nom, "")).upper().strip(), str(r.get(c_pre, "")).strip().title()
        aid = par_licence.get(lic)
        action = []
        if not aid:
            aid = nouvel_id()
            par_licence[lic] = aid
            nouveaux.append({"id": aid, "licence": lic, "nom": nom, "prenom": prenom,
                             "date_naissance": naissance.isoformat() if naissance else "", "responsable_legal": "",
                             "famille": nom, "email": "", "telephone": "", "adresse": str(r.get(c_vil, "")).strip(),
                             "premiere_saison": str(saison), "notes": "Repris de l'export des licenciés FFK",
                             "actif": "oui", "cree_le": maintenant})
            action.append("nouvel adhérent")
        else:
            for n in nouveaux:          # 1re saison = la plus ancienne vue dans les exports
                if n["id"] == aid and int(n["premiere_saison"]) > saison:
                    n["premiere_saison"] = str(saison)
        if (aid, saison) in deja:
            action.append("déjà inscrit cette saison")
        else:
            deja.add((aid, saison))
            debut = bornes_exercice(saison, mois_debut)[0]
            t = tarifs_saison(tarifs, saison)
            if lic in benevoles:
                nom_tarif, cot = TARIF_BENEVOLE, 0.0
            else:
                nom_tarif = tarif_suggere(tarifs, saison, naissance, debut) if not t.empty else None
                ligne_t = t[t["nom"] == nom_tarif] if nom_tarif else t.iloc[0:0]
                cot = float(ligne_t.iloc[0]["cotisation"]) if not ligne_t.empty else 0.0
            nouvelles.append({"id": nouvel_id(), "adherent_id": aid, "saison": str(saison),
                              "tarif": nom_tarif or "À préciser", "cotisation": cot, "frais_adhesion": 0.0,
                              "reduction": 0.0, "total_du": cot,
                              "date_inscription": (deb or debut).isoformat(),
                              "notes": "Licence FFK " + " ".join(x for x in (r.get(c_prod, ""), r.get(c_cat, "")) if x),
                              "cree_par": utilisateur})
            action.append("inscription créée")
        age = age_au(naissance, bornes_exercice(saison, mois_debut)[0]) if naissance else None
        rapport.append({"licence": lic, "nom": f"{nom} {prenom}", "saison": saison, "age": age,
                        "tarif": nouvelles[-1]["tarif"] if "inscription créée" in action else "",
                        "cotisation": nouvelles[-1]["cotisation"] if "inscription créée" in action else None,
                        "action": ", ".join(action)})
    return {"adherents": nouveaux, "inscriptions": nouvelles, "rapport": pd.DataFrame(rapport)}


def benevoles_connus(adherents: pd.DataFrame, inscriptions: pd.DataFrame) -> set[str]:
    """Licences déjà inscrites au tarif bénévole une saison précédente (pré-cochées au prochain import)."""
    from referentiel import TARIF_BENEVOLE
    if adherents.empty or inscriptions.empty:
        return set()
    ids = set(inscriptions.loc[inscriptions["tarif"] == TARIF_BENEVOLE, "adherent_id"])
    return {normaliser_licence(l) for l in adherents.loc[adherents["id"].isin(ids), "licence"]}


# ------------------------------------------------------------------ reprise complète : adhérents + inscriptions + paiements
FEUILLES_REPRISE = {
    "Adhérents": ["Licence", "Nom", "Prénom", "Date de naissance", "Responsable légal", "Famille", "Adresse",
                  "E-mail", "Téléphone", "Notes"],
    "Inscriptions": ["Licence", "Saison", "Tarif", "Cotisation", "Frais d'adhésion", "Réduction", "Notes"],
    "Paiements": ["Licence", "Saison", "Date", "Montant", "Mode", "Payé par", "Écriture du", "Montant de l'écriture"],
}


def _saison_de(texte, mois_debut: int) -> int | None:
    """« 2025-2026 », « 2025 » ou une date → saison (année de début)."""
    from metier import exercice_de
    t = str(texte or "").strip()
    if len(t) >= 4 and t[:4].isdigit() and (len(t) == 4 or t[4] in "-/ "):
        return int(t[:4])
    d = lire_date(t)
    return exercice_de(d, mois_debut) if d else None


def preparer_reprise_adherents(contenu: bytes, adherents: pd.DataFrame, inscriptions: pd.DataFrame,
                               paiements: pd.DataFrame, operations: pd.DataFrame, mois_debut: int, utilisateur: str,
                               maintenant: str, nouvel_id) -> dict:
    """Classeur « Adhérents / Inscriptions / Paiements » → lignes à ajouter, sans aucune écriture comptable.

    Chaque paiement est rattaché à l'écriture de recette déjà en comptabilité (même date et même montant que
    « Écriture du » / « Montant de l'écriture », ex. la remise de chèques qui le contient). Déjà présents
    (licence, inscription de la saison, paiement identique) : ignorés, donc réimport sans doublon."""
    import io
    from metier import nombre
    feuilles = pd.read_excel(io.BytesIO(contenu), sheet_name=None, dtype=object)
    norm = {sans_accent(k).strip().lower(): v for k, v in feuilles.items()}

    def feuille(nom):
        df = norm.get(sans_accent(nom).lower())
        if df is None:
            return pd.DataFrame(columns=FEUILLES_REPRISE[nom])
        df = df.rename(columns={c: str(c).strip() for c in df.columns}).dropna(how="all")
        return df.where(pd.notna(df), "")

    adh = adherents.copy() if not adherents.empty else pd.DataFrame(columns=TABLES["adherents"])
    ins = inscriptions.copy() if not inscriptions.empty else pd.DataFrame(columns=TABLES["inscriptions"])
    pai = paiements.copy() if not paiements.empty else pd.DataFrame(columns=TABLES["paiements"])
    ops = operations.copy()
    par_lic = {normaliser_licence(r["licence"]): r["id"] for r in adh.to_dict("records") if r.get("licence")}
    insc = {(r["adherent_id"], int(float(r["saison"] or 0))): r["id"] for r in ins.to_dict("records")}
    from collections import Counter
    # paiements déjà en base (compteur : deux paiements identiques le même jour restent possibles)
    deja_pai = Counter((r["inscription_id"], str(lire_date(r["date"])),
                        round(float(nombres(pd.Series([r["montant"]]))[0] or 0), 2)) for r in pai.to_dict("records"))
    nv_adh, nv_ins, nv_pai, erreurs = [], [], [], []

    for k, r in enumerate(feuille("Adhérents").to_dict("records"), start=2):
        lic = normaliser_licence(r.get("Licence"))
        if not lic or not str(r.get("Nom", "")).strip():
            erreurs.append(f"Adhérents, ligne {k} : licence ou nom manquant.")
            continue
        if lic in par_lic:
            continue
        aid = nouvel_id()
        par_lic[lic] = aid
        nai = lire_date(r.get("Date de naissance"))
        nom = str(r["Nom"]).strip().upper()
        nv_adh.append({"id": aid, "licence": lic, "nom": nom, "prenom": str(r.get("Prénom", "")).strip(),
                       "date_naissance": nai.isoformat() if nai else "",
                       "responsable_legal": str(r.get("Responsable légal", "")).strip(),
                       "famille": str(r.get("Famille", "")).strip().upper() or nom,
                       "email": str(r.get("E-mail", "")).strip(), "telephone": str(r.get("Téléphone", "")).strip(),
                       "adresse": str(r.get("Adresse", "")).strip(), "premiere_saison": "",
                       "notes": str(r.get("Notes", "")).strip(), "actif": "oui", "cree_le": maintenant})

    for k, r in enumerate(feuille("Inscriptions").to_dict("records"), start=2):
        lic, saison = normaliser_licence(r.get("Licence")), _saison_de(r.get("Saison"), mois_debut)
        aid = par_lic.get(lic)
        if not aid or saison is None:
            erreurs.append(f"Inscriptions, ligne {k} : licence inconnue ou saison illisible ({lic} {r.get('Saison')}).")
            continue
        if (aid, saison) in insc:
            continue
        cot, frais = nombre(r.get("Cotisation"), 0.0), nombre(r.get("Frais d'adhésion"), 0.0)
        red = nombre(r.get("Réduction"), 0.0)
        iid = nouvel_id()
        insc[(aid, saison)] = iid
        nv_ins.append({"id": iid, "adherent_id": aid, "saison": str(saison), "tarif": str(r.get("Tarif", "")).strip(),
                       "cotisation": cot, "frais_adhesion": frais, "reduction": red,
                       "total_du": round(max(cot + frais - red, 0.0), 2), "date_inscription": f"{saison}-{mois_debut:02d}-01",
                       "notes": str(r.get("Notes", "")).strip(), "cree_par": utilisateur})
        for a in nv_adh:
            if a["id"] == aid and (not a["premiere_saison"] or int(a["premiere_saison"]) > saison):
                a["premiere_saison"] = str(saison)

    if not ops.empty:
        ops = ops.assign(_d=ops["date"].map(lambda x: str(lire_date(x))),
                         _m=nombres(ops["montant"]).fillna(0).round(2),
                         _t=(ops["libelle"].astype(str) + " " + ops["tiers"].astype(str) + " "
                             + ops.get("notes", "").astype(str)).map(lambda t: sans_accent(t).lower()))
    # Montant déjà rattaché à chaque écriture (une remise de chèques peut couvrir plusieurs paiements)
    rattache = {}
    for r in pai.to_dict("records"):
        if r.get("operation_id"):
            rattache[r["operation_id"]] = rattache.get(r["operation_id"], 0.0) + float(
                nombres(pd.Series([r["montant"]]))[0] or 0)
    for k, r in enumerate(feuille("Paiements").to_dict("records"), start=2):
        lic, saison = normaliser_licence(r.get("Licence")), _saison_de(r.get("Saison"), mois_debut)
        aid = par_lic.get(lic)
        iid = insc.get((aid, saison)) if aid and saison is not None else None
        jour, montant = lire_date(r.get("Date")), nombre(r.get("Montant"), 0.0)
        if not iid or not jour or montant <= 0:
            erreurs.append(f"Paiements, ligne {k} : inscription introuvable, date ou montant illisible ({lic}).")
            continue
        cle = (iid, str(jour), round(montant, 2))
        if deja_pai[cle] > 0:
            deja_pai[cle] -= 1
            continue
        op_id = ""
        d_op, m_op = lire_date(r.get("Écriture du")), nombre(r.get("Montant de l'écriture"), 0.0)
        if d_op and m_op:
            x = ops[(ops["_d"] == str(d_op)) & (ops["_m"] == round(m_op, 2)) & (ops["sens"] == "Recette")] \
                if not ops.empty else ops
            # écritures encore assez « libres » pour ce paiement, puis la plus proche du payeur / de l'adhérent
            x = x[[round(m - rattache.get(i, 0.0), 2) >= round(montant, 2) for i, m in zip(x["id"], x["_m"])]] \
                if not x.empty else x
            if not x.empty:
                mots = {m for m in sans_accent(f"{r.get('Payé par', '')} {r.get('Libellé de l écriture', '')} "
                                               f"{lic}").lower().replace("-", " ").split() if len(m) > 2}
                if aid:
                    mots |= {m for m in sans_accent(" ".join(
                        str(a.get("nom", "")) for a in nv_adh + adh.to_dict("records") if a.get("id") == aid
                    )).lower().replace("-", " ").split() if len(m) > 2}
                score = x["_t"].map(lambda t: sum(m in t for m in mots))
                x = x.assign(_s=score).sort_values("_s", ascending=False, kind="stable")
                op_id = x.iloc[0]["id"]
                rattache[op_id] = rattache.get(op_id, 0.0) + montant
            else:
                erreurs.append(f"Paiements, ligne {k} : aucune écriture de {m_op:.2f} € le {d_op:%d/%m/%Y} disponible "
                               "en comptabilité (paiement repris sans lien).")
        nv_pai.append({"id": nouvel_id(), "inscription_id": iid, "adherent_id": aid, "saison": str(saison),
                       "date": jour.isoformat(), "montant": round(montant, 2), "mode": str(r.get("Mode", "")).strip(),
                       "payeur": str(r.get("Payé par", "")).strip(), "operation_id": op_id, "recu": "",
                       "saisi_par": f"reprise ({utilisateur})", "saisi_le": maintenant})
    return {"adherents": nv_adh, "inscriptions": nv_ins, "paiements": nv_pai, "erreurs": erreurs}


def modele_reprise_adherents() -> bytes:
    import io
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        for nom, cols in FEUILLES_REPRISE.items():
            pd.DataFrame(columns=cols).to_excel(w, sheet_name=nom, index=False)
    return buf.getvalue()
