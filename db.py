import hashlib
import secrets
import string
from datetime import datetime

import streamlit as st
from supabase import create_client, Client


@st.cache_resource
def get_client() -> Client:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)


# ---------- Auth ----------

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def create_user(nom, telephone, password):
    sb = get_client()
    existing = sb.table("users").select("id").eq("telephone", telephone).execute()
    if existing.data:
        return False, "Ce numéro de téléphone est déjà utilisé."

    sb.table("users").insert({
        "nom": nom,
        "telephone": telephone,
        "password_hash": hash_password(password),
        "role": "user",
    }).execute()
    return True, "Compte créé avec succès."


def create_admin_account(nom, telephone, password):
    """Réservé au super_admin : crée directement un compte avec le rôle
    'admin', sans passer par l'auto-inscription publique."""
    sb = get_client()
    existing = sb.table("users").select("id").eq("telephone", telephone).execute()
    if existing.data:
        return False, "Ce numéro de téléphone est déjà utilisé."

    sb.table("users").insert({
        "nom": nom,
        "telephone": telephone,
        "password_hash": hash_password(password),
        "role": "admin",
    }).execute()
    return True, "Compte admin créé avec succès."


def get_all_users():
    sb = get_client()
    res = (
        sb.table("users")
        .select("id, nom, telephone, role, created_at")
        .order("created_at", desc=True)
        .execute()
    )
    return res.data


def authenticate(telephone, password):
    sb = get_client()
    res = (
        sb.table("users")
        .select("*")
        .eq("telephone", telephone)
        .eq("password_hash", hash_password(password))
        .execute()
    )
    return res.data[0] if res.data else None


# ---------- Tontines ----------

def generate_code(length=6):
    return "".join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(length))


def create_tontine(nom, montant_cotisation, frequence, admin_id):
    sb = get_client()
    code = generate_code()
    while sb.table("tontines").select("id").eq("code_invitation", code).execute().data:
        code = generate_code()

    res = sb.table("tontines").insert({
        "nom": nom,
        "code_invitation": code,
        "montant_cotisation": montant_cotisation,
        "frequence": frequence,
        "admin_id": admin_id,
    }).execute()
    tontine_id = res.data[0]["id"]

    # L'admin gère la tontine mais n'est plus ajouté automatiquement comme
    # adhérent — s'il veut aussi cotiser et recevoir un tour, il rejoint
    # avec le code comme n'importe qui d'autre.

    return tontine_id, code


def join_tontine(code, user_id):
    sb = get_client()
    t_res = sb.table("tontines").select("*").eq("code_invitation", code).execute()
    if not t_res.data:
        return False, "Code d'invitation invalide."
    tontine = t_res.data[0]

    already = (
        sb.table("membres")
        .select("id")
        .eq("tontine_id", tontine["id"])
        .eq("user_id", user_id)
        .execute()
    )
    if already.data:
        return False, "Vous êtes déjà membre de cette tontine."

    membres = sb.table("membres").select("ordre_tour").eq("tontine_id", tontine["id"]).execute()
    max_ordre = max([m["ordre_tour"] for m in membres.data], default=0)

    sb.table("membres").insert({
        "tontine_id": tontine["id"],
        "user_id": user_id,
        "ordre_tour": max_ordre + 1,
    }).execute()

    return True, f"Vous avez rejoint la tontine « {tontine['nom']} »."


def get_user_tontines(user_id):
    sb = get_client()
    membres = sb.table("membres").select("tontine_id").eq("user_id", user_id).execute()
    tontine_ids = set(m["tontine_id"] for m in membres.data)

    # Inclure aussi les tontines que l'utilisateur administre, même s'il
    # n'en est pas adhérent.
    admin_res = sb.table("tontines").select("id").eq("admin_id", user_id).execute()
    tontine_ids.update(t["id"] for t in admin_res.data)

    if not tontine_ids:
        return []
    res = (
        sb.table("tontines")
        .select("*")
        .in_("id", list(tontine_ids))
        .order("created_at", desc=True)
        .execute()
    )
    return res.data


def get_user(user_id):
    sb = get_client()
    res = sb.table("users").select("id, nom, telephone").eq("id", user_id).execute()
    return res.data[0] if res.data else None


def get_tontine(tontine_id):
    sb = get_client()
    res = sb.table("tontines").select("*").eq("id", tontine_id).execute()
    return res.data[0] if res.data else None


def get_membres(tontine_id):
    sb = get_client()
    res = (
        sb.table("membres")
        .select("*, users(nom, telephone)")
        .eq("tontine_id", tontine_id)
        .order("ordre_tour")
        .execute()
    )
    membres = []
    for m in res.data:
        m2 = dict(m)
        m2["nom"] = m["users"]["nom"]
        m2["telephone"] = m["users"]["telephone"]
        membres.append(m2)
    return membres


def activer_tontine(tontine_id):
    sb = get_client()
    sb.table("tontines").update({"statut": "active", "cycle_actuel": 1}).eq("id", tontine_id).execute()


# ---------- Cotisations ----------

def declarer_cotisation(tontine_id, user_id, cycle_numero, montant):
    sb = get_client()
    existing = (
        sb.table("cotisations")
        .select("id")
        .eq("tontine_id", tontine_id)
        .eq("user_id", user_id)
        .eq("cycle_numero", cycle_numero)
        .execute()
    )
    if existing.data:
        sb.table("cotisations").update({
            "statut": "declaree",
            "date_declaration": datetime.now().isoformat(),
        }).eq("id", existing.data[0]["id"]).execute()
    else:
        sb.table("cotisations").insert({
            "tontine_id": tontine_id,
            "user_id": user_id,
            "cycle_numero": cycle_numero,
            "montant": montant,
            "statut": "declaree",
            "date_declaration": datetime.now().isoformat(),
        }).execute()


def valider_cotisation(cotisation_id):
    sb = get_client()
    sb.table("cotisations").update({
        "statut": "validee",
        "date_validation": datetime.now().isoformat(),
    }).eq("id", cotisation_id).execute()


def get_cotisations_cycle(tontine_id, cycle_numero):
    sb = get_client()
    res = (
        sb.table("cotisations")
        .select("*, users(nom)")
        .eq("tontine_id", tontine_id)
        .eq("cycle_numero", cycle_numero)
        .execute()
    )
    cotisations = []
    for c in res.data:
        c2 = dict(c)
        c2["nom"] = c["users"]["nom"]
        cotisations.append(c2)
    return cotisations


def avancer_cycle(tontine_id):
    sb = get_client()
    tontine = get_tontine(tontine_id)
    cycle = tontine["cycle_actuel"]

    sb.table("membres").update({"a_recu_tour": True}).eq("tontine_id", tontine_id).eq(
        "ordre_tour", cycle
    ).execute()

    sb.table("tontines").update({"cycle_actuel": cycle + 1}).eq("id", tontine_id).execute()

    membres = sb.table("membres").select("id").eq("tontine_id", tontine_id).execute()
    nb_membres = len(membres.data)

    if cycle >= nb_membres:
        sb.table("tontines").update({"statut": "terminee"}).eq("id", tontine_id).execute()
