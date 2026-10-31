"""Écrans de comptabilité : saisie, opérations (historique, rapprochement, justificatifs, correction),
opérations en attente."""
from __future__ import annotations

import io
from datetime import date

import pandas as pd
import streamlit as st

import metier
from commun import (backend, categories, charger, eur, est_admin, exercices_disponibles, flash, journaliser,
                    lecture_seule, libelle_exercice, mois_debut, operations, peut_saisir, rafraichir, ranger_fichier,
                    utilisateur)
from referentiel import MODES_PAIEMENT, SENS, SOURCES


def tiers_connus() -> list[str]:
    noms = set(charger("operations")["tiers"].dropna().astype(str).str.strip())
    adh = charger("adherents")
    if not adh.empty:
        noms |= {f"{str(r.nom).upper()} {r.prenom}".strip() for r in adh.itertuples()}
    return sorted(n for n in noms if n)


def ranger_justificatif(fichier, jour: date, libelle: str) -> str:
    nom = f"{jour:%Y-%m-%d}_{''.join(c for c in libelle if c.isalnum() or c in ' -_')[:40].strip()}_{fichier.name}"
    return ranger_fichier("Justificatifs", nom, fichier.getvalue(), fichier.type or "application/octet-stream")


def formulaire_operation(cle: str, defaut: dict | None = None) -> dict | None:
    d = defaut or {}
    sens = st.radio("Sens", SENS, horizontal=True, key=f"{cle}_sens",
                    index=SENS.index(d["sens"]) if d.get("sens") in SENS else 1)
    tiers_liste = tiers_connus()
    with st.form(cle, clear_on_submit=not defaut):
        c1, c2, c3 = st.columns(3)
        jour = c1.date_input("Date", value=d.get("date") or date.today(), format="DD/MM/YYYY")
        montant = c2.number_input("Montant (€)", min_value=0.0, step=1.0, format="%.2f",
                                  value=float(d.get("montant") or 0.0))
        source = c3.radio("Source", SOURCES, horizontal=True,
                          index=SOURCES.index(d["source"]) if d.get("source") in SOURCES else 0,
                          help="Banque = passe par le compte bancaire. Espèces = caisse, hors compte bancaire.")
        cats = categories(sens)
        if d.get("categorie") and d["categorie"] not in cats:
            cats.append(d["categorie"])
        c4, c5 = st.columns(2)
        cat = c4.selectbox("Catégorie", cats, index=cats.index(d["categorie"]) if d.get("categorie") in cats else 0)
        mode = c5.selectbox("Mode de paiement", [""] + MODES_PAIEMENT,
                            index=([""] + MODES_PAIEMENT).index(d["mode_paiement"])
                            if d.get("mode_paiement") in MODES_PAIEMENT else 0)
        libelle = st.text_input("Libellé", value=d.get("libelle", ""), placeholder="ex. Achat de tatamis")
        c6, c7, c8 = st.columns(3)
        options_tiers = tiers_liste + ([d["tiers"]] if d.get("tiers") and d["tiers"] not in tiers_liste else [])
        tiers = c6.selectbox("Tiers", options_tiers, index=options_tiers.index(d["tiers"]) if d.get("tiers") else None,
                             accept_new_options=True, placeholder="fournisseur, adhérent… (ou saisir un nouveau)")
        piece = c7.text_input("N° de pièce", value=d.get("piece", ""), placeholder="facture, ticket…")
        rapproche = c8.checkbox("Rapprochée (figure sur un relevé)", value=metier.oui(d.get("rapproche", "")))
        notes = st.text_input("Notes", value=d.get("notes", ""))
        justificatif = st.file_uploader("Justificatif (PDF ou photo, facultatif)",
                                        type=["pdf", "jpg", "jpeg", "png", "heic", "webp"])
        valide = st.form_submit_button("Enregistrer", type="primary")
    if not valide:
        return None
    if montant <= 0 or not libelle.strip():
        st.error("Le montant et le libellé sont obligatoires.")
        return None
    d0, _ = metier.dernier_releve_valide(charger("releves"))
    pointee_sur = metier.lire_date(d.get("releve", "")) or jour     # relevé sur lequel l'écriture est pointée
    if d0 and source == "Banque" and rapproche and pointee_sur <= d0:
        st.error(f"Le relevé du {d0:%d/%m/%Y} est validé : une écriture bancaire pointée ne peut plus être ajoutée ou "
                 "modifiée avant cette date (annulez d'abord la validation dans Banque → Relevés validés).")
        return None
    lien = d.get("justificatif", "")
    if justificatif is not None:
        lien = ranger_justificatif(justificatif, jour, libelle) or lien
    return metier.nouvelle_operation(jour, sens, cat, libelle, montant, source, mode, tiers or "", piece, notes,
                                     utilisateur(), mois_debut(), rapproche=rapproche, justificatif=lien,
                                     releve=metier.lire_date(d.get("releve", "")))


# ====================================================================== saisie
def page_saisie():
    st.header("Saisir une opération")
    if lecture_seule():
        return
    st.caption("Les cotisations et les dons se saisissent de préférence dans leurs pages : l'écriture comptable "
               "est alors créée automatiquement avec le reçu.")
    op = formulaire_operation("saisie")
    if op:
        backend().ajouter("operations", [op])
        journaliser("saisie", f"{op['sens']} {op['montant']} € — {op['libelle']}")
        rafraichir()
        st.success(f"Enregistré : {op['sens'].lower()} de {eur(op['montant'])} ({op['source'].lower()}).")


# ====================================================================== opérations
def page_operations():
    st.header("Opérations")
    ops = operations()
    if ops.empty:
        st.info("Aucune opération. Saisissez-en une ou reprenez l'historique (page « Reprise et import »).")
        return
    s = metier.soldes(ops)
    c1, c2, c3 = st.columns(3)
    c1.metric("Solde banque", eur(s["banque"]))
    c2.metric("Solde pointé (rapproché)", eur(s["pointe"]))
    c3.metric("Caisse espèces", eur(s["caisse"]))

    f1, f2, f3, f4, f5 = st.columns(5)
    ex = f1.selectbox("Exercice", ["Tous"] + exercices_disponibles(),
                      format_func=lambda e: e if e == "Tous" else libelle_exercice(e))
    cat = f2.selectbox("Catégorie", ["Toutes"] + sorted(ops["categorie"].unique()))
    source = f3.selectbox("Source", ["Toutes"] + SOURCES)
    rap = f4.selectbox("Rapprochement", ["Toutes", "Non rapprochées", "Rapprochées"])
    texte = f5.text_input("Recherche", placeholder="libellé, tiers, pièce…")
    v = ops
    if ex != "Tous":
        v = v[v["exercice"] == ex]
    if cat != "Toutes":
        v = v[v["categorie"] == cat]
    if source != "Toutes":
        v = v[v["source"] == source]
    if rap != "Toutes":
        v = v[v["rapproche_b"] == (rap == "Rapprochées")]
    if texte:
        t = texte.lower()
        v = v[v[["libelle", "tiers", "piece", "notes", "categorie"]].astype(str).apply(
            lambda col: col.str.lower().str.contains(t, regex=False)).any(axis=1)]
    v = v.sort_values(["date", "saisi_le"], ascending=False, kind="stable")
    st.caption(f"{len(v)} opération(s) — recettes {eur(v.loc[v['sens'] == 'Recette', 'montant'].sum())}, "
               f"dépenses {eur(v.loc[v['sens'] == 'Dépense', 'montant'].sum())}")

    vue = v[["id", "date", "sens", "categorie", "libelle", "signe", "source", "tiers", "piece", "rapproche_b",
             "justificatif"]].copy()
    vue["justificatif"] = vue["justificatif"].where(vue["justificatif"].astype(str).str.startswith("http"), None)
    edite = st.data_editor(
        vue, hide_index=True, width="stretch", key="table_operations",
        disabled=[c for c in vue.columns if c != "rapproche_b"] if peut_saisir() else True,
        column_config={"id": None, "date": st.column_config.DateColumn("Date", format="DD/MM/YYYY"),
                       "sens": "Sens", "categorie": "Catégorie", "libelle": "Libellé",
                       "signe": st.column_config.NumberColumn("Montant", format="%.2f €"), "source": "Source",
                       "tiers": "Tiers", "piece": "Pièce",
                       "rapproche_b": st.column_config.CheckboxColumn("Rapprochée"),
                       "justificatif": st.column_config.LinkColumn("Justificatif", display_text="📎 ouvrir")})
    c1, c2 = st.columns([1, 3])
    modif = edite[edite["rapproche_b"] != vue["rapproche_b"]]
    d0, _ = metier.dernier_releve_valide(charger("releves"))
    if d0 and not modif.empty:
        periode_validee = (modif["date"] <= pd.Timestamp(d0)) & (modif["source"] != "Espèces")
        if periode_validee.any():
            st.warning(f"{int(periode_validee.sum())} changement(s) de pointage concernent la période du relevé validé "
                       f"du {d0:%d/%m/%Y} : ils ne seront pas enregistrés.")
            modif = modif[~periode_validee]
    if peut_saisir() and c1.button(f"Enregistrer les rapprochements ({len(modif)})", disabled=modif.empty):
        brut = charger("operations").copy()
        for r in modif.itertuples():
            brut.loc[brut["id"] == r.id, "rapproche"] = "oui" if r.rapproche_b else "non"
            if not r.rapproche_b and "releve" in brut:
                brut.loc[brut["id"] == r.id, "releve"] = ""
        backend().remplacer("operations", brut)
        journaliser("rapprochement", f"{len(modif)} écriture(s) modifiée(s)")
        rafraichir()
        flash("Rapprochements enregistrés.")
        st.rerun()
    export = v.drop(columns=["signe", "rapproche_b", "releve_d"], errors="ignore").copy()
    export["date"] = export["date"].dt.date
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        export.to_excel(w, sheet_name="Opérations", index=False)
        metier.mettre_en_forme(w)
    c2.download_button("Exporter cette sélection (Excel)", buf.getvalue(),
                       file_name=f"operations_{date.today():%Y-%m-%d}.xlsx")

    if not peut_saisir() or v.empty:
        return
    st.divider()
    st.subheader("Corriger, compléter ou supprimer une opération")
    choix = st.selectbox("Opération", v["id"].tolist(), key="operation_a_corriger",
                         format_func=lambda i: _resume(v[v["id"] == i].iloc[0]))
    ligne = v[v["id"] == choix].iloc[0]
    if str(ligne["origine"]).startswith(("paiement:", "don:")):
        st.info("Cette écriture vient d'un paiement d'adhérent ou d'un don : corrigez de préférence depuis la page "
                "concernée pour garder le reçu cohérent.")
    d0, _ = metier.dernier_releve_valide(charger("releves"))
    if bool(metier.verrouillees(v[v["id"] == choix], d0).any()):
        _completer_verrouillee(ligne, d0)
        return
    defaut = {**ligne.to_dict(), "date": ligne["date"].date() if pd.notna(ligne["date"]) else date.today()}
    corrigee = formulaire_operation(f"edition_{choix}", defaut)
    if corrigee:
        brut = charger("operations").copy()
        corrigee.update(id=choix, saisi_par=ligne["saisi_par"], saisi_le=ligne["saisi_le"], origine=ligne["origine"])
        if corrigee.get("rapproche") == "oui" and not corrigee.get("releve"):
            corrigee["releve"] = ligne.get("releve", "") or ""      # garder le relevé de pointage
        for col, val in corrigee.items():
            brut.loc[brut["id"] == choix, col] = str(val)
        backend().remplacer("operations", brut)
        journaliser("correction", _resume(ligne))
        rafraichir()
        flash("Opération corrigée.")
        st.rerun()
    if est_admin():
        confirmer = st.checkbox("Je confirme la suppression définitive de cette opération")
        if st.button("Supprimer", disabled=not confirmer):
            backend().supprimer_ids("operations", [choix])
            journaliser("suppression", _resume(ligne))
            rafraichir()
            flash("Opération supprimée.")
            st.rerun()


def _completer_verrouillee(ligne, d0) -> None:
    """Écriture d'un relevé validé : date, montant, sens, source et pointage sont figés (ils font le solde du
    relevé) ; la catégorie, le libellé, le tiers, la pièce, les notes et le justificatif restent modifiables."""
    st.info(f"Écriture pointée sur un relevé validé (jusqu'au {d0:%d/%m/%Y}) : **date, montant, sens et pointage "
            "sont verrouillés**. Vous pouvez corriger la catégorie, le libellé, le tiers, la pièce, les notes et le "
            "justificatif. Pour changer le reste, annulez d'abord la validation du relevé (Banque → Relevés validés).")
    st.caption(f"{ligne['date']:%d/%m/%Y} · {ligne['sens']} · {eur(float(ligne['montant']))} · {ligne['source']}")
    choix = ligne["id"]
    cats = categories(ligne["sens"])
    if ligne["categorie"] and ligne["categorie"] not in cats:
        cats.append(ligne["categorie"])
    tiers_liste = tiers_connus()
    if ligne["tiers"] and ligne["tiers"] not in tiers_liste:
        tiers_liste.append(ligne["tiers"])
    with st.form(f"completer_{choix}"):
        c1, c2 = st.columns(2)
        cat = c1.selectbox("Catégorie", cats, index=cats.index(ligne["categorie"]) if ligne["categorie"] in cats else 0)
        modes = [""] + MODES_PAIEMENT
        mode = c2.selectbox("Mode de paiement", modes,
                            index=modes.index(ligne["mode_paiement"]) if ligne["mode_paiement"] in modes else 0)
        libelle = st.text_input("Libellé", value=ligne["libelle"])
        c3, c4 = st.columns(2)
        tiers = c3.selectbox("Tiers", tiers_liste, index=tiers_liste.index(ligne["tiers"]) if ligne["tiers"] else None,
                             accept_new_options=True, placeholder="adhérent, donateur, fournisseur…")
        piece = c4.text_input("N° de pièce", value=ligne["piece"])
        notes = st.text_input("Notes", value=ligne["notes"])
        justificatif = st.file_uploader("Justificatif (PDF ou photo, facultatif)",
                                        type=["pdf", "jpg", "jpeg", "png", "heic", "webp"])
        valide = st.form_submit_button("Enregistrer", type="primary")
    if not valide:
        return
    if not libelle.strip():
        st.error("Le libellé est obligatoire.")
        return
    lien = ligne["justificatif"]
    if justificatif is not None:
        lien = ranger_justificatif(justificatif, ligne["date"].date(), libelle) or lien
    brut = charger("operations").copy()
    for col, val in {"categorie": cat, "mode_paiement": mode, "libelle": libelle.strip(), "tiers": tiers or "",
                     "piece": piece, "notes": notes, "justificatif": lien}.items():
        brut.loc[brut["id"] == choix, col] = str(val)
    backend().remplacer("operations", brut)
    journaliser("correction", f"{_resume(ligne)} → {cat} / {tiers or ''}")
    rafraichir()
    flash("Opération complétée.")
    st.rerun()


def _resume(r) -> str:
    d = r["date"].strftime("%d/%m/%Y") if pd.notna(r["date"]) else "?"
    return f"{d} · {r['sens']} {eur(float(r['montant']))} · {r['libelle']} · {r['source']} · réf. {r['id'][:6]}"


# ====================================================================== opérations en attente
def page_attente():
    st.header("Opérations en attente")
    st.caption("Opérations prévues (prélèvements mensuels, chèques non encore débités…) : elles ne comptent pas "
               "dans les soldes tant qu'elles ne sont pas passées en comptabilité.")
    att = charger("attente").copy()
    if not att.empty:
        att["date"] = pd.to_datetime(att["date"], errors="coerce")
        att["montant"] = metier.nombres(att["montant"]).fillna(0)
        att = att.sort_values("date")
        att["choisir"] = att["date"] <= pd.Timestamp(date.today())
        edite = st.data_editor(
            att[["choisir", "id", "date", "sens", "categorie", "libelle", "montant", "source", "tiers", "notes"]],
            hide_index=True, width="stretch", disabled=["id", "date", "sens", "categorie", "libelle", "montant",
                                                         "source", "tiers", "notes"],
            column_config={"choisir": st.column_config.CheckboxColumn("Choisir"), "id": None,
                           "date": st.column_config.DateColumn("Échéance", format="DD/MM/YYYY"),
                           "montant": st.column_config.NumberColumn("Montant", format="%.2f €")})
        choisies = edite[edite["choisir"]]
        if peut_saisir():
            c1, c2 = st.columns(2)
            if c1.button(f"Passer en comptabilité ({len(choisies)})", type="primary", disabled=choisies.empty):
                ops = []
                for r in choisies.itertuples():
                    src = att[att["id"] == r.id].iloc[0]
                    ops.append(metier.nouvelle_operation(r.date.date(), r.sens, r.categorie, r.libelle, r.montant,
                                                         r.source, src["mode_paiement"], r.tiers, "", r.notes,
                                                         utilisateur(), mois_debut(), origine="attente"))
                backend().ajouter("operations", ops)
                backend().supprimer_ids("attente", choisies["id"].tolist())
                journaliser("attente", f"{len(ops)} opération(s) passée(s) en comptabilité")
                rafraichir()
                flash(f"{len(ops)} opération(s) passée(s) en comptabilité.")
                st.rerun()
            if c2.button(f"Supprimer ({len(choisies)})", disabled=choisies.empty):
                backend().supprimer_ids("attente", choisies["id"].tolist())
                journaliser("attente", f"{len(choisies)} supprimée(s)")
                rafraichir()
                st.rerun()
    else:
        st.info("Aucune opération en attente.")

    if not peut_saisir():
        return
    st.subheader("Ajouter une opération en attente")
    sens = st.radio("Sens", SENS, horizontal=True, index=1, key="attente_sens")
    with st.form("nouvelle_attente", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        jour = c1.date_input("Première échéance", value=date.today(), format="DD/MM/YYYY")
        montant = c2.number_input("Montant (€)", min_value=0.0, step=1.0, format="%.2f")
        repetitions = c3.number_input("Répéter chaque mois (nombre de mois)", min_value=1, max_value=36, value=1)
        c4, c5, c6 = st.columns(3)
        cat = c4.selectbox("Catégorie", categories(sens))
        source = c5.radio("Source", SOURCES, horizontal=True)
        mode = c6.selectbox("Mode", [""] + MODES_PAIEMENT)
        libelle = st.text_input("Libellé", placeholder="ex. Frais de tenue de compte")
        tiers = st.text_input("Tiers", placeholder="ex. Crédit Mutuel")
        notes = st.text_input("Notes")
        if st.form_submit_button("Ajouter", type="primary"):
            if montant <= 0 or not libelle.strip():
                st.error("Le montant et le libellé sont obligatoires.")
            else:
                lignes = [{"id": metier.nouvel_id(), "date": d.isoformat(), "sens": sens, "categorie": cat,
                           "libelle": libelle.strip(), "montant": round(montant, 2), "source": source,
                           "mode_paiement": mode, "tiers": tiers.strip(), "notes": notes.strip(),
                           "cree_par": utilisateur(), "cree_le": metier.maintenant()}
                          for d in metier.serie_mensuelle(jour, int(repetitions))]
                backend().ajouter("attente", lignes)
                journaliser("attente", f"{len(lignes)} ajoutée(s) : {libelle}")
                rafraichir()
                flash(f"{len(lignes)} opération(s) en attente ajoutée(s).")
                st.rerun()
