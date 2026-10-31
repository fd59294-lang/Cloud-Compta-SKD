"""Sensei Karaté Do — logiciel de gestion du club (Streamlit).

Même architecture que le logiciel du Comité des Fêtes : code sur GitHub, mise en ligne avec un lien
d'accès, connexion avec un compte Google autorisé, données dans le Google Sheets et le Drive du club.

Lancement local (mode essai, données dans ./donnees_locales) :  streamlit run app.py
"""
from __future__ import annotations

from datetime import date, datetime

import altair as alt
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Sensei Karaté Do — Gestion", page_icon="🥋", layout="wide")

import adherents as A  # noqa: E402
import metier  # noqa: E402
from commun import (afficher_flash, backend, charger, eur, est_admin, exercice_courant,  # noqa: E402
                    exercices_disponibles, initialiser_si_vide, journaliser, libelle_exercice, logo, mois_debut,
                    operations, parametre, ecrire_parametre, ecrire_parametres, peut_saisir, preparer_dossiers,
                    rafraichir)
from ecran_adherents import page_adherents, page_paiements, page_tarifs  # noqa: E402
from ecran_banque import page_banque  # noqa: E402
from ecran_budget import page_budget  # noqa: E402
from ecran_compta import page_attente, page_operations, page_saisie  # noqa: E402
from ecran_documents import page_documents  # noqa: E402
from ecran_dons import page_dons  # noqa: E402
from ecran_rapports import page_rapports  # noqa: E402
from ecran_reprise import page_reprise  # noqa: E402
from referentiel import APP_NOM, MOIS, PARAMETRES_CLUB, ROLES, ROLES_ADMIN, ROLES_LIBELLES, TABLES  # noqa: E402
from stockage import lire_config  # noqa: E402


# ====================================================================== accès (identique au Comité)
def auth_configuree() -> bool:
    try:
        return "auth" in st.secrets
    except Exception:
        return False


def controler_acces() -> bool:
    conf = lire_config()
    if not auth_configuree():
        if conf.get("backend") == "google":
            st.error("Connexion Google non configurée (section [auth] absente des secrets) : accès bloqué "
                     "pour protéger les données du club. Voir le guide de mise en ligne.")
            return False
        st.session_state.update(email="essai.local", nom="Mode essai", role="president")
        return True
    if not st.user.is_logged_in:
        st.title(f"🥋 {APP_NOM}")
        st.write("Connectez-vous avec votre compte Google pour accéder au logiciel.")
        st.button("Se connecter avec Google", type="primary", on_click=st.login)
        return False
    email = str(st.user.email).lower()
    if conf.get("backend") == "installation":       # premier lancement : relier le Drive du club
        if email in (conf.get("admins") or []):
            from installation import page_installation
            page_installation(conf)
        else:
            st.error(f"Installation en cours : seul un compte listé dans « admins » peut la faire ({email} ne l'est pas).")
            st.button("Se déconnecter", on_click=st.logout)
        return False
    users = charger("utilisateurs")
    ligne = users[users["email"].str.lower() == email]
    if ligne.empty and email in (conf.get("admins") or []):
        backend().ajouter("utilisateurs", [{"email": email, "nom": st.user.get("name", email), "role": "president"}])
        rafraichir()
        ligne = charger("utilisateurs")
        ligne = ligne[ligne["email"].str.lower() == email]
    if ligne.empty:
        st.error(f"Le compte {email} n'est pas autorisé. Demandez au président ou au trésorier de vous ajouter.")
        st.button("Se déconnecter", on_click=st.logout)
        return False
    st.session_state.update(email=email, nom=ligne.iloc[0]["nom"] or email, role=ligne.iloc[0]["role"])
    return True


# ====================================================================== sauvegarde
def sauvegarde_automatique() -> None:
    """Une sauvegarde Excel horodatée par jour, déclenchée à la première connexion."""
    aujourd_hui = date.today().isoformat()
    if st.session_state.get("sauvegarde_verifiee") == aujourd_hui:
        return
    st.session_state["sauvegarde_verifiee"] = aujourd_hui
    if parametre("derniere_sauvegarde") == aujourd_hui or charger("operations").empty:
        return
    try:
        faire_sauvegarde("automatique")
    except Exception as e:
        st.toast(f"Sauvegarde automatique impossible : {e}", icon="⚠️")


def faire_sauvegarde(origine: str) -> str:
    tables = {t: charger(t) for t in TABLES}
    contenu = metier.export_excel(tables, mois_debut())
    nom = f"sauvegarde_{datetime.now():%Y-%m-%d_%Hh%M}.xlsx"
    lieu = backend().enregistrer_fichier(
        "Sauvegardes", nom, contenu, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    ecrire_parametre("derniere_sauvegarde", date.today().isoformat())
    journaliser("sauvegarde", f"{origine} : {nom}")
    return lieu


# ====================================================================== tableau de bord
def page_tableau_de_bord():
    ops = operations()
    st.header("Tableau de bord")
    exs = exercices_disponibles()
    ex = st.selectbox("Saison / exercice", exs, format_func=libelle_exercice)
    s_auj = metier.soldes(ops)
    t, t1 = metier.totaux(ops, ex), metier.totaux(ops, ex - 1)
    comparer = t1["nb"] > 0
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🏦 Solde banque (aujourd'hui)", eur(s_auj["banque"]))
    c2.metric("💶 Caisse espèces", eur(s_auj["caisse"]))
    c3.metric("Recettes", eur(t["recettes"]), delta=eur(t["recettes"] - t1["recettes"]) if comparer else None)
    c4.metric("Résultat", eur(t["resultat"]), delta=eur(t["resultat"] - t1["resultat"]) if comparer else None)

    etat = A.etat_saison(charger("adherents"), charger("inscriptions"), charger("paiements"), ex)
    stats = A.statistiques_saison(etat, charger("inscriptions"), ex)
    _alertes(ops, etat)

    g, d = st.columns([3, 2])
    with g:
        st.subheader("Recettes et dépenses par mois")
        m = metier.mensuel(ops, ex, mois_debut()).melt(id_vars=["ordre", "mois"], var_name="Sens", value_name="€")
        st.altair_chart(alt.Chart(m).mark_bar().encode(
            x=alt.X("mois:N", sort=alt.SortField("ordre"), title=None), xOffset="Sens:N",
            y=alt.Y("€:Q", title="€"),
            color=alt.Color("Sens:N", scale=alt.Scale(domain=["Recettes", "Dépenses"], range=["#2E7D32", "#C8102E"]),
                            legend=alt.Legend(orient="top", title=None)),
            tooltip=["mois", "Sens", alt.Tooltip("€:Q", format=",.2f")]).properties(height=260), width="stretch")
    with d:
        st.subheader("Adhérents de la saison")
        if stats["inscrits"]:
            a = pd.DataFrame({"Statut": ["À jour", "Partiel", "En attente"],
                              "Nombre": [stats["a_jour"], stats["partiels"], stats["en_attente"]]})
            st.altair_chart(alt.Chart(a).mark_arc(innerRadius=50).encode(
                theta="Nombre:Q", color=alt.Color("Statut:N", scale=alt.Scale(
                    domain=["À jour", "Partiel", "En attente"], range=["#2E7D32", "#F0A020", "#C8102E"]),
                    legend=alt.Legend(orient="bottom", title=None)),
                tooltip=["Statut", "Nombre"]).properties(height=220), width="stretch")
            st.caption(f"{stats['inscrits']} inscrits dont {stats['nouveaux']} nouveaux · encaissé "
                       f"{eur(stats['encaisse'])} · reste à encaisser **{eur(stats['reste'])}**")
        else:
            st.info("Aucune inscription pour cette saison.")

    b = metier.budget_compare(ops, charger("budget"), ex)
    b = b[b["prevu"] > 0]
    if not b.empty:
        st.subheader("Budget prévu / réalisé")
        pr = b.assign(cat=b["categorie"].map(metier.nom_categorie)).melt(
            id_vars=["sens", "cat"], value_vars=["prevu", "realise"], var_name="Version", value_name="€")
        pr["Version"] = pr["Version"].map({"prevu": "Prévu", "realise": "Réalisé"})
        st.altair_chart(alt.Chart(pr).mark_bar().encode(
            y=alt.Y("cat:N", title=None, axis=alt.Axis(labelLimit=240)), x=alt.X("€:Q"), yOffset="Version:N",
            color=alt.Color("Version:N", scale=alt.Scale(range=["#BDBDBD", "#1A1A1A"]),
                            legend=alt.Legend(orient="top", title=None)),
            row=alt.Row("sens:N", title=None), tooltip=["cat", "Version", alt.Tooltip("€:Q", format=",.2f")]
        ).properties(width=520), width="content")


def _alertes(ops: pd.DataFrame, etat: pd.DataFrame) -> None:
    alertes = []
    a_classer = ops[ops["categorie"].str.startswith(("R99", "D99"))]
    if not a_classer.empty:
        alertes.append(f"{len(a_classer)} opération(s) « à classer » (page Opérations).")
    attente = charger("attente")
    if not attente.empty:
        echues = attente[pd.to_datetime(attente["date"], errors="coerce") <= pd.Timestamp(date.today())]
        if not echues.empty:
            alertes.append(f"{len(echues)} opération(s) en attente arrivée(s) à échéance.")
    if not etat.empty:
        retard = etat[etat["statut"] != "À jour"]
        if not retard.empty:
            alertes.append(f"{len(retard)} adhérent(s) n'ont pas fini de régler leur cotisation "
                           f"({eur(retard['reste'].sum())}).")
    if parametre("derniere_sauvegarde") and parametre("derniere_sauvegarde") < (
            date.today() - pd.Timedelta(days=7)).isoformat():
        alertes.append("Aucune sauvegarde depuis plus de 7 jours.")
    if alertes:
        with st.container(border=True):
            st.markdown("**⚠️ À traiter**")
            for a in alertes:
                st.markdown(f"- {a}")


# ====================================================================== administration
def page_sauvegarde():
    st.header("Sauvegarde et export")
    st.write(f"Dernière sauvegarde dans le Drive : **{parametre('derniere_sauvegarde', 'jamais')}**. "
             "Une sauvegarde Excel horodatée est faite chaque jour à la première connexion.")
    tables = {t: charger(t) for t in TABLES}
    st.download_button("Télécharger toutes les données (Excel)", metier.export_excel(tables, mois_debut()),
                       file_name=f"sensei_export_{date.today():%Y-%m-%d}.xlsx", type="primary")
    if peut_saisir() and st.button("Sauvegarder maintenant dans le Drive"):
        st.success(f"Sauvegarde enregistrée : {faire_sauvegarde('manuelle')}")
    with st.expander("Journal des actions"):
        st.dataframe(charger("journal").iloc[::-1], hide_index=True, width="stretch")


def page_utilisateurs():
    st.header("Utilisateurs")
    st.caption("Seules les adresses Google listées ici peuvent ouvrir le logiciel.")
    u = charger("utilisateurs")
    edite = st.data_editor(u, num_rows="dynamic", hide_index=True, width="stretch",
                           column_config={"email": "Adresse Google", "nom": "Nom",
                                          "role": st.column_config.SelectboxColumn("Rôle", options=ROLES,
                                                                                   required=True)})
    st.caption(" · ".join(f"{r} = {l}" for r, l in ROLES_LIBELLES.items()))
    if st.button("Enregistrer", type="primary"):
        edite = edite.dropna(subset=["email"])
        edite["email"] = edite["email"].str.strip().str.lower()
        if not edite["role"].isin(ROLES_ADMIN).any():
            st.error("Il faut au moins un président ou un trésorier.")
            return
        backend().remplacer("utilisateurs", edite)
        journaliser("utilisateurs", f"{len(edite)} compte(s)")
        rafraichir()
        st.success("Utilisateurs enregistrés.")


def page_parametres():
    st.header("Paramètres")
    st.subheader("Coordonnées du club")
    st.caption("Elles apparaissent sur les factures, reçus, reçus fiscaux et rapports.")
    with st.form("parametres_club"):
        valeurs = {}
        colonnes = st.columns(2)
        for i, (cle, (libelle, defaut)) in enumerate(PARAMETRES_CLUB.items()):
            valeurs[cle] = colonnes[i % 2].text_input(libelle, value=parametre(cle, defaut))
        mois = st.selectbox("Début de la saison / de l'exercice comptable", MOIS[1:], index=mois_debut() - 1,
                            help="Septembre pour une saison sportive septembre → août.")
        if st.form_submit_button("Enregistrer", type="primary"):
            valeurs["mois_debut_exercice"] = MOIS.index(mois)
            ecrire_parametres(valeurs)
            journaliser("paramètres", "coordonnées du club")
            st.success("Paramètres enregistrés.")

    st.subheader("Logo")
    c1, c2 = st.columns([1, 3])
    if logo():
        c1.image(logo(), width=110)
    fichier = c2.file_uploader("Nouveau logo (PNG ou JPG)", type=["png", "jpg", "jpeg"])
    if fichier and c2.button("Enregistrer ce logo"):
        lieu = backend().enregistrer_fichier("Logo", f"logo_{datetime.now():%Y%m%d%H%M}.{fichier.name.split('.')[-1]}",
                                             fichier.getvalue(), fichier.type or "image/png")
        ecrire_parametre("logo_fichier", lieu)
        logo.clear()
        journaliser("paramètres", "logo")
        st.success("Logo enregistré.")
        st.rerun()

    st.subheader("Catégories comptables")
    st.caption("Modifiez un nom, désactivez une catégorie inutilisée ou ajoutez-en une (code unique). "
               "Les écritures existantes gardent leur libellé.")
    cats = charger("categories").copy()
    cats["actif"] = cats["actif"].astype(str).str.lower() != "non"
    edite = st.data_editor(cats, num_rows="dynamic", hide_index=True, width="stretch",
                           column_config={"code": "Code", "nom": "Nom",
                                          "sens": st.column_config.SelectboxColumn("Sens", options=["Recette", "Dépense"],
                                                                                   required=True),
                                          "actif": st.column_config.CheckboxColumn("Active")})
    if st.button("Enregistrer les catégories"):
        edite = edite.dropna(subset=["code", "nom"])
        edite["code"] = edite["code"].astype(str).str.strip()
        if edite["code"].duplicated().any():
            st.error("Deux catégories ont le même code.")
        else:
            edite["actif"] = edite["actif"].map(lambda b: "oui" if b else "non")
            backend().remplacer("categories", edite)
            journaliser("paramètres", "catégories")
            rafraichir()
            st.success("Catégories enregistrées.")

    st.subheader("Dossiers du Drive")
    st.caption("Crée (ou retrouve) le dossier « Sensei Karaté Do — Gestion » et ses sous-dossiers dans le Drive du club. "
               "Sans danger si on le relance.")
    if st.button("Préparer les dossiers du Drive"):
        ids = preparer_dossiers()
        st.success(f"{len(ids) - 1} dossiers prêts.")
    st.caption(f"Stockage : {backend().nom}")


def page_confidentialite():
    """Page publique (sans connexion) exigée par Google pour l'écran de consentement."""
    nom = parametre("nom_association", "le club") if lire_config().get("backend") != "google" else "le club Sensei Karaté Do"
    st.title("Règles de confidentialité")
    st.markdown(f"""
Ce logiciel est l'outil interne de gestion de **{nom}** (comptabilité, adhérents, dons, documents).
Il est réservé aux membres du bureau de l'association.

**Données traitées.** Pour la connexion, seuls l'adresse e-mail et le nom du compte Google sont utilisés,
afin de vérifier que la personne est autorisée. Les données de gestion (opérations, adhérents, paiements,
dons) sont enregistrées dans le Google Drive de l'association, jamais ailleurs.

**Accès au Drive.** Le logiciel ne peut lire et modifier que les fichiers qu'il a lui-même créés
(autorisation Google « drive.file ») : il n'a aucun accès au reste du Drive.

**Partage.** Aucune donnée n'est vendue, cédée ni transmise à des tiers. Aucune publicité, aucun traçage.

**Durée et droits.** Les comptes d'accès sont supprimés dès qu'un membre quitte le bureau. Les données des
adhérents sont conservées le temps de leur adhésion puis le délai légal de conservation des pièces comptables.
Pour toute question ou demande : écrire au club.
""")


# ====================================================================== lancement
def main():
    if st.query_params.get("page") == "confidentialite":
        page_confidentialite()
        return
    if not controler_acces():
        return
    initialiser_si_vide()
    sauvegarde_automatique()
    with st.sidebar:
        if logo():
            st.image(logo(), width=90)
        st.markdown(f"### {parametre('nom_association', 'Sensei Karaté Do')}")
        st.caption(f"{st.session_state['nom']} · {ROLES_LIBELLES.get(st.session_state['role'], '')}")
        st.caption(f"Saison en cours : {libelle_exercice(exercice_courant())}")
        if auth_configuree():
            st.button("Se déconnecter", on_click=st.logout)
        else:
            st.warning("Mode essai : données locales, sans connexion.")
    pages = {
        "Pilotage": [st.Page(page_tableau_de_bord, title="Tableau de bord", icon="📊", default=True),
                     st.Page(page_budget, title="Budget prévisionnel", icon="📒", url_path="budget"),
                     st.Page(page_rapports, title="Rapports et AG", icon="📄", url_path="rapports")],
        "Comptabilité": [st.Page(page_saisie, title="Saisir une opération", icon="✏️", url_path="saisie"),
                         st.Page(page_operations, title="Opérations", icon="📜", url_path="operations"),
                         st.Page(page_attente, title="Opérations en attente", icon="⏳", url_path="attente"),
                         st.Page(page_banque, title="Banque", icon="🏦", url_path="banque")],
        "Adhérents": [st.Page(page_adherents, title="Adhérents et inscriptions", icon="🥋", url_path="adherents"),
                      st.Page(page_paiements, title="Paiements et reçus", icon="💰", url_path="paiements"),
                      st.Page(page_tarifs, title="Tarifs", icon="🏷️", url_path="tarifs")],
        "Dons et documents": [st.Page(page_dons, title="Dons et reçus fiscaux", icon="🎁", url_path="dons"),
                              st.Page(page_documents, title="Factures et remboursements", icon="🧾",
                                      url_path="documents")],
        "Association": [st.Page(page_reprise, title="Reprise et import", icon="📥", url_path="reprise"),
                        st.Page(page_sauvegarde, title="Sauvegarde et export", icon="💾", url_path="sauvegarde")],
    }
    if est_admin():
        pages["Administration"] = [st.Page(page_utilisateurs, title="Utilisateurs", icon="👥", url_path="utilisateurs"),
                                   st.Page(page_parametres, title="Paramètres", icon="⚙️", url_path="parametres")]
    navigation = st.navigation(pages, expanded=True)
    afficher_flash()
    navigation.run()


if __name__ == "__main__":
    main()
