import urllib.parse
from datetime import datetime

import streamlit as st
import db

st.set_page_config(page_title="Tontine App", page_icon="💰", layout="centered")


def format_phone_international(telephone: str) -> str:
    """Convertit un numéro local (ex: 0102939380) en format international
    sans le '+' pour les liens wa.me. Suppose la Côte d'Ivoire (225) si le
    numéro commence par 0."""
    digits = "".join(ch for ch in telephone if ch.isdigit())
    if digits.startswith("0"):
        return "225" + digits[1:]
    return digits


def format_datetime_fr(iso_str: str) -> str:
    """Convertit une date ISO (ex: 2026-09-10T14:23:05.123456) en format
    lisible français : '10/09/2026 à 14:23'."""
    if not iso_str:
        return ""
    try:
        dt = datetime.fromisoformat(iso_str)
        return dt.strftime("%d/%m/%Y à %H:%M")
    except (ValueError, TypeError):
        return iso_str


def whatsapp_reminder_url(telephone: str, nom: str, tontine_nom: str, montant: float, cycle: int) -> str:
    phone = format_phone_international(telephone)
    message = (
        f"Bonjour {nom}, petit rappel pour votre cotisation de {montant:.0f} FCFA "
        f"pour la tontine « {tontine_nom} » (cycle {cycle}). Merci de cotiser dès que possible 🙏"
    )
    return f"https://wa.me/{phone}?text={urllib.parse.quote(message)}"


def whatsapp_reminder_url_association(telephone: str, nom: str, association_nom: str, montant: float, periode: int) -> str:
    phone = format_phone_international(telephone)
    message = (
        f"Bonjour {nom}, petit rappel pour votre cotisation de {montant:.0f} FCFA "
        f"pour l'association « {association_nom} » (période {periode}). Merci de cotiser dès que possible 🙏"
    )
    return f"https://wa.me/{phone}?text={urllib.parse.quote(message)}"

if "user" not in st.session_state:
    st.session_state.user = None
if "tontine_id" not in st.session_state:
    st.session_state.tontine_id = None
if "association_id" not in st.session_state:
    st.session_state.association_id = None


# ---------------------------------------------------------------------------
# AUTH
# ---------------------------------------------------------------------------

def page_auth():
    st.title("💰 Tontine App")
    st.caption("Gérez vos tontines et cotisations d'association simplement, sans carnet ni confusion.")

    tab_login, tab_signup = st.tabs(["Connexion", "Inscription"])

    with tab_login:
        with st.form("login_form"):
            tel = st.text_input("Téléphone")
            pwd = st.text_input("Mot de passe", type="password")
            submitted = st.form_submit_button("Se connecter", use_container_width=True)
            if submitted:
                user = db.authenticate(tel, pwd)
                if user:
                    st.session_state.user = user
                    st.rerun()
                else:
                    st.error("Téléphone ou mot de passe incorrect.")

    with tab_signup:
        with st.form("signup_form"):
            nom = st.text_input("Nom complet")
            tel = st.text_input("Téléphone", key="signup_tel")
            pwd = st.text_input("Mot de passe", type="password", key="signup_pwd")
            submitted = st.form_submit_button("Créer mon compte", use_container_width=True)
            if submitted:
                if not nom or not tel or not pwd:
                    st.warning("Merci de remplir tous les champs.")
                else:
                    ok, msg = db.create_user(nom, tel, pwd)
                    if ok:
                        st.success(msg + " Connectez-vous maintenant.")
                    else:
                        st.error(msg)


# ---------------------------------------------------------------------------
# DASHBOARD — liste des tontines
# ---------------------------------------------------------------------------

def page_dashboard():
    user = st.session_state.user
    st.title(f"👋 Bonjour, {user['nom']}")

    tab_tontines, tab_associations = st.tabs(["💰 Tontines", "🤝 Associations"])

    with tab_tontines:
        page_dashboard_tontines(user)

    with tab_associations:
        page_dashboard_associations(user)


def page_dashboard_tontines(user):
    is_admin_or_more = user["role"] in ("admin", "super_admin")

    if is_admin_or_more:
        col1, col2 = st.columns(2)
    else:
        col1 = None
        col2 = st.container()
        st.caption("Seuls les administrateurs peuvent créer une tontine. Tu peux rejoindre une tontine existante avec un code.")

    if is_admin_or_more:
        with col1:
            with st.expander("➕ Créer une tontine"):
                with st.form("create_tontine_form"):
                    nom = st.text_input("Nom de la tontine")
                    montant = st.number_input("Montant de cotisation (FCFA)", min_value=500, step=500)
                    freq = st.selectbox("Fréquence", ["hebdomadaire", "mensuelle"])
                    submitted = st.form_submit_button("Créer")
                    if submitted and nom:
                        ok, result = db.create_tontine(nom, montant, freq, user["id"])
                        if ok:
                            st.success(f"Tontine créée ! Code d'invitation : **{result}**")
                        else:
                            st.warning(result)

    with col2:
        with st.expander("🔑 Rejoindre une tontine"):
            with st.form("join_tontine_form"):
                code = st.text_input("Code d'invitation")
                submitted = st.form_submit_button("Rejoindre")
                if submitted and code:
                    ok, msg = db.join_tontine(code.strip().upper(), user["id"])
                    if ok:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)

    st.divider()
    st.subheader("Mes tontines")

    tontines = db.get_user_tontines(user["id"])
    if not tontines:
        st.info("Vous ne faites partie d'aucune tontine pour le moment.")
        return

    for t in tontines:
        statut_emoji = {"en_attente": "🟡", "active": "🟢", "terminee": "✅"}.get(t["statut"], "")
        role_badge = "👑 Admin" if t["admin_id"] == user["id"] else "🙋 Adhérent"
        with st.container(border=True):
            c1, c2 = st.columns([3, 1])
            with c1:
                st.markdown(f"**{t['nom']}** {statut_emoji} · :blue-background[{role_badge}]")
                st.caption(
                    f"{t['montant_cotisation']:.0f} FCFA · {t['frequence']} · "
                    f"code `{t['code_invitation']}` · statut : {t['statut']}"
                )
            with c2:
                if st.button("Ouvrir", key=f"open_{t['id']}", use_container_width=True):
                    st.session_state.tontine_id = t["id"]
                    st.rerun()


def page_dashboard_associations(user):
    is_admin_or_more = user["role"] in ("admin", "super_admin")

    if is_admin_or_more:
        col1, col2 = st.columns(2)
    else:
        col1 = None
        col2 = st.container()
        st.caption("Seuls les administrateurs peuvent créer une association. Tu peux rejoindre une association existante avec un code.")

    if is_admin_or_more:
        with col1:
            with st.expander("➕ Créer une association"):
                with st.form("create_association_form"):
                    nom = st.text_input("Nom de l'association", key="assoc_nom")
                    montant = st.number_input("Montant de cotisation (FCFA)", min_value=500, step=500, key="assoc_montant")
                    freq = st.selectbox("Fréquence", ["hebdomadaire", "mensuelle"], key="assoc_freq")
                    submitted = st.form_submit_button("Créer")
                    if submitted and nom:
                        ok, result = db.create_association(nom, montant, freq, user["id"])
                        if ok:
                            st.success(f"Association créée ! Code d'invitation : **{result}**")
                        else:
                            st.warning(result)

    with col2:
        with st.expander("🔑 Rejoindre une association"):
            with st.form("join_association_form"):
                code = st.text_input("Code d'invitation", key="join_assoc_code")
                submitted = st.form_submit_button("Rejoindre")
                if submitted and code:
                    ok, msg = db.join_association(code.strip().upper(), user["id"])
                    if ok:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)

    st.divider()
    st.subheader("Mes associations")

    associations = db.get_user_associations(user["id"])
    if not associations:
        st.info("Vous ne faites partie d'aucune association pour le moment.")
        return

    for a in associations:
        role_badge = "👑 Admin" if a["admin_id"] == user["id"] else "🙋 Membre"
        with st.container(border=True):
            c1, c2 = st.columns([3, 1])
            with c1:
                st.markdown(f"**{a['nom']}** · :blue-background[{role_badge}]")
                st.caption(
                    f"{a['montant_cotisation']:.0f} FCFA · {a['frequence']} · "
                    f"code `{a['code_invitation']}` · période {a['periode_actuelle']}"
                )
            with c2:
                if st.button("Ouvrir", key=f"open_assoc_{a['id']}", use_container_width=True):
                    st.session_state.association_id = a["id"]
                    st.rerun()


# ---------------------------------------------------------------------------
# DETAIL D'UNE TONTINE
# ---------------------------------------------------------------------------

def page_tontine():
    user = st.session_state.user
    tontine = db.get_tontine(st.session_state.tontine_id)

    if st.button("← Retour à mes tontines"):
        st.session_state.tontine_id = None
        st.rerun()

    st.title(f"💰 {tontine['nom']}")
    is_admin = tontine["admin_id"] == user["id"]

    membres = db.get_membres(tontine["id"])
    admin_user = db.get_user(tontine["admin_id"])

    st.caption(
        f"{tontine['montant_cotisation']:.0f} FCFA · {tontine['frequence']} · "
        f"{len(membres)} adhérent(s) · code `{tontine['code_invitation']}`"
    )
    admin_label = admin_user["nom"] + (" (vous)" if is_admin else "")
    st.markdown(f"👑 **Administrateur :** {admin_label}")

    # --- Activation par l'admin ---
    if tontine["statut"] == "en_attente":
        st.warning("Cette tontine n'a pas encore démarré.")
        if is_admin:
            st.write("Adhérents inscrits :")
            if not membres:
                st.caption("Aucun adhérent pour l'instant — partage le code d'invitation.")
            for m in membres:
                st.write(f"- {m['nom']} (tour n°{m['ordre_tour']})")
            if membres and st.button("🚀 Démarrer la tontine", type="primary"):
                db.activer_tontine(tontine["id"])
                st.rerun()
        return

    if tontine["statut"] == "terminee":
        st.success("Cette tontine est terminée. Tous les membres ont reçu leur tour !")

    cycle = tontine["cycle_actuel"]
    beneficiaire = next((m for m in membres if m["ordre_tour"] == cycle), None)

    if beneficiaire:
        st.info(f"📅 Cycle {cycle} — Bénéficiaire de ce tour : **{beneficiaire['nom']}**")

    # --- Cotisations du cycle ---
    st.subheader(f"Cotisations — cycle {cycle}")
    cotisations = {c["user_id"]: c for c in db.get_cotisations_cycle(tontine["id"], cycle)}

    for m in membres:
        cot = cotisations.get(m["user_id"])
        statut = cot["statut"] if cot else "en_attente"
        emoji = {"en_attente": "⚪", "declaree": "🟠", "validee": "🟢"}[statut]
        label = {
            "en_attente": ":red[**En retard**]",
            "declaree": ":orange[En attente de validation]",
            "validee": ":green[**Payé ✓**]",
        }[statut]

        date_declaration = format_datetime_fr(cot.get("date_declaration")) if cot else ""
        date_validation = format_datetime_fr(cot.get("date_validation")) if cot else ""

        c1, c2, c3 = st.columns([3, 2, 2])
        with c1:
            st.write(f"{emoji} {m['nom']}")
        with c2:
            st.markdown(label)
            if statut == "declaree" and date_declaration:
                st.caption(f"Déclaré le {date_declaration}")
            elif statut == "validee":
                if date_validation:
                    st.caption(f"Validé le {date_validation}")
                if date_declaration:
                    st.caption(f"(déclaré le {date_declaration})")
        with c3:
            if m["user_id"] == user["id"] and statut == "en_attente":
                if st.button("Déclarer mon paiement", key=f"declare_{m['id']}"):
                    db.declarer_cotisation(
                        tontine["id"], user["id"], cycle, tontine["montant_cotisation"]
                    )
                    st.rerun()
            elif is_admin and statut == "declaree":
                if st.button("Valider", key=f"validate_{m['id']}"):
                    db.valider_cotisation(cot["id"])
                    st.rerun()
            elif is_admin and statut == "en_attente" and m.get("telephone"):
                url = whatsapp_reminder_url(
                    m["telephone"], m["nom"], tontine["nom"],
                    tontine["montant_cotisation"], cycle,
                )
                st.link_button("📲 Rappel WhatsApp", url, key=f"remind_{m['id']}")

    # --- Passage au tour suivant (admin) ---
    if is_admin and tontine["statut"] == "active":
        st.divider()
        nb_validees = sum(1 for c in cotisations.values() if c["statut"] == "validee")
        st.caption(f"{nb_validees}/{len(membres)} cotisations validées pour ce cycle.")
        if st.button("➡️ Clôturer ce cycle et passer au suivant", type="primary"):
            db.avancer_cycle(tontine["id"])
            st.rerun()


# ---------------------------------------------------------------------------
# DETAIL D'UNE ASSOCIATION
# ---------------------------------------------------------------------------

def page_association():
    user = st.session_state.user
    association = db.get_association(st.session_state.association_id)

    if st.button("← Retour à mes associations"):
        st.session_state.association_id = None
        st.rerun()

    st.title(f"🤝 {association['nom']}")
    is_admin = association["admin_id"] == user["id"]

    membres = db.get_membres_association(association["id"])
    admin_user = db.get_user(association["admin_id"])

    st.caption(
        f"{association['montant_cotisation']:.0f} FCFA · {association['frequence']} · "
        f"{len(membres)} membre(s) · code `{association['code_invitation']}`"
    )
    admin_label = admin_user["nom"] + (" (vous)" if is_admin else "")
    st.markdown(f"👑 **Administrateur :** {admin_label}")

    if not membres:
        st.info("Aucun membre pour l'instant — partage le code d'invitation.")
        return

    periode = association["periode_actuelle"]
    st.subheader(f"Cotisations — période {periode}")
    cotisations = {
        c["user_id"]: c for c in db.get_cotisations_periode_association(association["id"], periode)
    }

    for m in membres:
        cot = cotisations.get(m["user_id"])
        statut = cot["statut"] if cot else "en_attente"
        emoji = {"en_attente": "⚪", "declaree": "🟠", "validee": "🟢"}[statut]
        label = {
            "en_attente": ":red[**En retard**]",
            "declaree": ":orange[En attente de validation]",
            "validee": ":green[**Payé ✓**]",
        }[statut]

        date_declaration = format_datetime_fr(cot.get("date_declaration")) if cot else ""
        date_validation = format_datetime_fr(cot.get("date_validation")) if cot else ""

        c1, c2, c3 = st.columns([3, 2, 2])
        with c1:
            st.write(f"{emoji} {m['nom']}")
        with c2:
            st.markdown(label)
            if statut == "declaree" and date_declaration:
                st.caption(f"Déclaré le {date_declaration}")
            elif statut == "validee":
                if date_validation:
                    st.caption(f"Validé le {date_validation}")
                if date_declaration:
                    st.caption(f"(déclaré le {date_declaration})")
        with c3:
            if m["user_id"] == user["id"] and statut == "en_attente":
                if st.button("Déclarer mon paiement", key=f"declare_assoc_{m['id']}"):
                    db.declarer_cotisation_association(
                        association["id"], user["id"], periode, association["montant_cotisation"]
                    )
                    st.rerun()
            elif is_admin and statut == "declaree":
                if st.button("Valider", key=f"validate_assoc_{m['id']}"):
                    db.valider_cotisation_association(cot["id"])
                    st.rerun()
            elif is_admin and statut == "en_attente" and m.get("telephone"):
                url = whatsapp_reminder_url_association(
                    m["telephone"], m["nom"], association["nom"],
                    association["montant_cotisation"], periode,
                )
                st.link_button("📲 Rappel WhatsApp", url, key=f"remind_assoc_{m['id']}")

    # --- Passage à la période suivante (admin) ---
    if is_admin:
        st.divider()
        nb_validees = sum(1 for c in cotisations.values() if c["statut"] == "validee")
        st.caption(f"{nb_validees}/{len(membres)} cotisations validées pour cette période.")
        if st.button("➡️ Clôturer cette période et passer à la suivante", type="primary"):
            db.avancer_periode_association(association["id"])
            st.rerun()


# ---------------------------------------------------------------------------
# PANNEAU SUPER_ADMIN — création de comptes admin
# ---------------------------------------------------------------------------

def page_admin_panel():
    st.title("🛡️ Administration")
    st.caption("Réservé au super_admin — crée ici les comptes des administrateurs de tontines.")

    if st.button("← Retour au tableau de bord"):
        st.session_state.show_admin_panel = False
        st.rerun()

    with st.form("create_admin_form"):
        nom = st.text_input("Nom complet de l'admin")
        tel = st.text_input("Téléphone")
        pwd = st.text_input("Mot de passe à lui communiquer", type="password")
        submitted = st.form_submit_button("Créer le compte admin")
        if submitted:
            if not nom or not tel or not pwd:
                st.warning("Merci de remplir tous les champs.")
            else:
                ok, msg = db.create_admin_account(nom, tel, pwd)
                if ok:
                    st.success(msg + " Communique-lui son téléphone et son mot de passe.")
                else:
                    st.error(msg)

    st.divider()
    st.subheader("Comptes existants")
    users = db.get_all_users()
    for u in users:
        role_badge = {"super_admin": "🛡️ Super admin", "admin": "👑 Admin", "user": "🙋 Utilisateur"}.get(u["role"], u["role"])
        c1, c2 = st.columns([4, 1])
        with c1:
            st.write(f"- **{u['nom']}** ({u['telephone']}) — {role_badge}")
        with c2:
            if u["role"] in ("admin", "user"):
                if st.button("🗑️ Supprimer", key=f"del_{u['id']}"):
                    st.session_state[f"confirm_del_{u['id']}"] = True
                if st.session_state.get(f"confirm_del_{u['id']}"):
                    if u["role"] == "admin":
                        st.warning(f"Supprimer {u['nom']} et toutes ses tontines/cotisations ?")
                    else:
                        st.warning(f"Supprimer {u['nom']} et ses participations aux tontines ?")
                    cc1, cc2 = st.columns(2)
                    with cc1:
                        if st.button("Oui, supprimer", key=f"confirm_yes_{u['id']}", type="primary"):
                            if u["role"] == "admin":
                                db.delete_admin_account(u["id"])
                            else:
                                db.delete_user_account(u["id"])
                            st.session_state[f"confirm_del_{u['id']}"] = False
                            st.success(f"Compte {u['nom']} supprimé.")
                            st.rerun()
                    with cc2:
                        if st.button("Annuler", key=f"confirm_no_{u['id']}"):
                            st.session_state[f"confirm_del_{u['id']}"] = False
                            st.rerun()

    st.divider()
    st.subheader("Réinitialiser une tontine")
    st.caption("Efface les cotisations et remet le cycle à 1, pour retester une tontine sans la recréer.")
    tontines = db.get_all_tontines()
    if not tontines:
        st.caption("Aucune tontine pour l'instant.")
    for t in tontines:
        c1, c2 = st.columns([4, 1])
        with c1:
            st.write(f"- **{t['nom']}** (admin : {t['admin_nom']}) — statut : {t['statut']}, cycle {t['cycle_actuel']}")
        with c2:
            if st.button("🔄 Réinitialiser", key=f"reset_{t['id']}"):
                db.reset_tontine(t["id"])
                st.success(f"Tontine « {t['nom']} » réinitialisée.")
                st.rerun()

    st.divider()
    st.subheader("Réinitialiser une association")
    st.caption("Efface les cotisations et remet la période à 1, pour retester une association sans la recréer.")
    associations = db.get_all_associations()
    if not associations:
        st.caption("Aucune association pour l'instant.")
    for a in associations:
        c1, c2 = st.columns([4, 1])
        with c1:
            st.write(f"- **{a['nom']}** (admin : {a['admin_nom']}) — période {a['periode_actuelle']}")
        with c2:
            if st.button("🔄 Réinitialiser", key=f"reset_assoc_{a['id']}"):
                db.reset_association(a["id"])
                st.success(f"Association « {a['nom']} » réinitialisée.")
                st.rerun()

    st.divider()
    st.subheader("⚠️ Zone dangereuse")
    with st.expander("Tout effacer (toutes les tontines, associations, membres et cotisations)"):
        st.error("Action irréversible. Les comptes utilisateurs sont conservés, mais toutes les tontines, associations et cotisations seront définitivement supprimées.")
        confirm_text = st.text_input("Tape EFFACER pour confirmer")
        if st.button("Tout effacer définitivement", disabled=(confirm_text != "EFFACER")):
            db.wipe_all_data()
            st.success("Toutes les données de tontines et associations ont été effacées.")
            st.rerun()


# ---------------------------------------------------------------------------
# ROUTING
# ---------------------------------------------------------------------------

if "show_admin_panel" not in st.session_state:
    st.session_state.show_admin_panel = False

if st.session_state.user is None:
    page_auth()
else:
    with st.sidebar:
        st.write(f"Connecté : **{st.session_state.user['nom']}**")
        if st.session_state.user["role"] == "super_admin":
            if st.button("🛡️ Administration"):
                st.session_state.show_admin_panel = True
                st.rerun()
        if st.button("Déconnexion"):
            st.session_state.user = None
            st.session_state.tontine_id = None
            st.session_state.association_id = None
            st.session_state.show_admin_panel = False
            st.rerun()

    if st.session_state.show_admin_panel:
        page_admin_panel()
    elif st.session_state.tontine_id is not None:
        page_tontine()
    elif st.session_state.association_id is not None:
        page_association()
    else:
        page_dashboard()
