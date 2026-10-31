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
