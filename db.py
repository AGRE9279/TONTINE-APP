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


# ---------- Freemium / Abonnements ----------

LIMITE_FREE_TONTINES = 1
LIMITE_FREE_MEMBRES = 10
LIMITE_FREE_ASSOCIATIONS = 1
LIMITE_FREE_MEMBRES_ASSOCIATION = 10


def get_plan_actif(admin_id):
    """Retourne le plan actif de l'admin ('free' ou 'premium').
    Si aucun abonnement trouvé, considère 'free' par défaut."""
    sb = get_client()
    res = (
        sb.table("subscriptions")
        .select("plan")
        .eq("admin_id", admin_id)
        .eq("statut", "actif")
        .order("date_debut", desc=True)
        .limit(1)
        .execute()
    )
    if res.data:
        return res.data[0]["plan"]
    return "free"


def verifier_limite_tontines(admin_id):
    """Vérifie si l'admin peut créer une nouvelle tontine.
    Retourne (True, None) si autorisé, (False, message) sinon."""
    plan = get_plan_actif(admin_id)
    if plan == "premium":
        return True, None

    sb = get_client()
    res = sb.table("tontines").select("id").eq("admin_id", admin_id).execute()
    nb_tontines = len(res.data)

    if nb_tontines >= LIMITE_FREE_TONTINES:
        return False, (
            f"Le plan gratuit est limité à {LIMITE_FREE_TONTINES} tontine(s). "
            "Passez au plan Premium pour en créer davantage."
        )
    return True, None


def verifier_limite_membres(tontine_id):
    """Vérifie si une tontine peut accueillir un nouveau membre,
    selon le plan de son admin. Retourne (True, None) ou (False, message)."""
    sb = get_client()
    t_res = sb.table("tontines").select("admin_id").eq("id", tontine_id).execute()
    if not t_res.data:
        return False, "Tontine introuvable."

    admin_id = t_res.data[0]["admin_id"]
    plan = get_plan_actif(admin_id)
    if plan == "premium":
        return True, None

    membres_res = sb.table("membres").select("id").eq("tontine_id", tontine_id).execute()
    nb_membres = len(membres_res.data)

    if nb_membres >= LIMITE_FREE_MEMBRES:
        return False, (
            f"Cette tontine a atteint la limite de {LIMITE_FREE_MEMBRES} membres "
            "du plan gratuit. Contactez l'administrateur pour passer en Premium."
        )
    return True, None


def verifier_limite_associations(admin_id):
    """Vérifie si l'admin peut créer une nouvelle association.
    Retourne (True, None) si autorisé, (False, message) sinon."""
    plan = get_plan_actif(admin_id)
    if plan == "premium":
        return True, None

    sb = get_client()
    res = sb.table("associations").select("id").eq("admin_id", admin_id).execute()
    nb_associations = len(res.data)

    if nb_associations >= LIMITE_FREE_ASSOCIATIONS:
        return False, (
            f"Le plan gratuit est limité à {LIMITE_FREE_ASSOCIATIONS} association(s). "
            "Passez au plan Premium pour en créer davantage."
        )
    return True, None


def verifier_limite_membres_association(association_id):
    """Vérifie si une association peut accueillir un nouveau membre,
    selon le plan de son admin. Retourne (True, None) ou (False, message)."""
    sb = get_client()
    a_res = sb.table("associations").select("admin_id").eq("id", association_id).execute()
    if not a_res.data:
        return False, "Association introuvable."

    admin_id = a_res.data[0]["admin_id"]
    plan = get_plan_actif(admin_id)
    if plan == "premium":
        return True, None

    membres_res = (
        sb.table("membres_association")
        .select("id")
        .eq("association_id", association_id)
        .execute()
    )
    nb_membres = len(membres_res.data)

    if nb_membres >= LIMITE_FREE_MEMBRES_ASSOCIATION:
        return False, (
            f"Cette association a atteint la limite de {LIMITE_FREE_MEMBRES_ASSOCIATION} "
            "membres du plan gratuit. Contactez l'administrateur pour passer en Premium."
        )
    return True, None


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

    res = sb.table("users").insert({
        "nom": nom,
        "telephone": telephone,
        "password_hash": hash_password(password),
        "role": "admin",
    }).execute()

    # Initialise automatiquement un abonnement gratuit pour ce nouvel admin
    new_user_id = res.data[0]["id"]
    sb.table("subscriptions").insert({
        "admin_id": new_user_id,
        "plan": "free",
        "statut": "actif",
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


def get_all_tontines():
    sb = get_client()
    res = sb.table("tontines").select("*, users(nom)").order("created_at", desc=True).execute()
    tontines = []
    for t in res.data:
        t2 = dict(t)
        t2["admin_nom"] = t["users"]["nom"] if t.get("users") else "—"
        tontines.append(t2)
    return tontines


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
    """Crée une tontine si l'admin n'a pas dépassé la limite de son plan.
    Retourne (True, code) en cas de succès, (False, message) sinon."""
    ok, msg = verifier_limite_tontines(admin_id)
    if not ok:
        return False, msg

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

    # L'admin gère la tontine mais n'est plus ajouté automatiquement comme
    # adhérent — s'il veut aussi cotiser et recevoir un tour, il rejoint
    # avec le code comme n'importe qui d'autre.

    return True, code


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

    ok, msg = verifier_limite_membres(tontine["id"])
    if not ok:
        return False, msg

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


# ---------- Associations (cotisations simples, hors tontine) ----------

def create_association(nom, montant_cotisation, frequence, admin_id):
    """Crée une association si l'admin n'a pas dépassé la limite de son
    plan. Retourne (True, code) en cas de succès, (False, message) sinon."""
    ok, msg = verifier_limite_associations(admin_id)
    if not ok:
        return False, msg

    sb = get_client()
    code = generate_code()
    while sb.table("associations").select("id").eq("code_invitation", code).execute().data:
        code = generate_code()

    sb.table("associations").insert({
        "nom": nom,
        "code_invitation": code,
        "montant_cotisation": montant_cotisation,
        "frequence": frequence,
        "admin_id": admin_id,
    }).execute()

    return True, code


def join_association(code, user_id):
    sb = get_client()
    a_res = sb.table("associations").select("*").eq("code_invitation", code).execute()
    if not a_res.data:
        return False, "Code d'invitation invalide."
    association = a_res.data[0]

    already = (
        sb.table("membres_association")
        .select("id")
        .eq("association_id", association["id"])
        .eq("user_id", user_id)
        .execute()
    )
    if already.data:
        return False, "Vous êtes déjà membre de cette association."

    ok, msg = verifier_limite_membres_association(association["id"])
    if not ok:
        return False, msg

    sb.table("membres_association").insert({
        "association_id": association["id"],
        "user_id": user_id,
    }).execute()

    return True, f"Vous avez rejoint l'association « {association['nom']} »."


def get_user_associations(user_id):
    sb = get_client()
    membres = sb.table("membres_association").select("association_id").eq("user_id", user_id).execute()
    association_ids = set(m["association_id"] for m in membres.data)

    admin_res = sb.table("associations").select("id").eq("admin_id", user_id).execute()
    association_ids.update(a["id"] for a in admin_res.data)

    if not association_ids:
        return []
    res = (
        sb.table("associations")
        .select("*")
        .in_("id", list(association_ids))
        .order("created_at", desc=True)
        .execute()
    )
    return res.data


def get_association(association_id):
    sb = get_client()
    res = sb.table("associations").select("*").eq("id", association_id).execute()
    return res.data[0] if res.data else None


def get_membres_association(association_id):
    sb = get_client()
    res = (
        sb.table("membres_association")
        .select("*, users(nom, telephone)")
        .eq("association_id", association_id)
        .order("created_at")
        .execute()
    )
    membres = []
    for m in res.data:
        m2 = dict(m)
        m2["nom"] = m["users"]["nom"]
        m2["telephone"] = m["users"]["telephone"]
        membres.append(m2)
    return membres


def declarer_cotisation_association(association_id, user_id, periode_numero, montant):
    sb = get_client()
    existing = (
        sb.table("cotisations_association")
        .select("id")
        .eq("association_id", association_id)
        .eq("user_id", user_id)
        .eq("periode_numero", periode_numero)
        .execute()
    )
    if existing.data:
        sb.table("cotisations_association").update({
            "statut": "declaree",
            "date_declaration": datetime.now().isoformat(),
        }).eq("id", existing.data[0]["id"]).execute()
    else:
        sb.table("cotisations_association").insert({
            "association_id": association_id,
            "user_id": user_id,
            "periode_numero": periode_numero,
            "montant": montant,
            "statut": "declaree",
            "date_declaration": datetime.now().isoformat(),
        }).execute()


def valider_cotisation_association(cotisation_id):
    sb = get_client()
    sb.table("cotisations_association").update({
        "statut": "validee",
        "date_validation": datetime.now().isoformat(),
    }).eq("id", cotisation_id).execute()


def get_cotisations_periode_association(association_id, periode_numero):
    sb = get_client()
    res = (
        sb.table("cotisations_association")
        .select("*, users(nom)")
        .eq("association_id", association_id)
        .eq("periode_numero", periode_numero)
        .execute()
    )
    cotisations = []
    for c in res.data:
        c2 = dict(c)
        c2["nom"] = c["users"]["nom"]
        cotisations.append(c2)
    return cotisations


def avancer_periode_association(association_id):
    """Passe à la période suivante. Une association n'a pas de fin —
    les cotisations se répètent indéfiniment période après période."""
    sb = get_client()
    association = get_association(association_id)
    nouvelle_periode = association["periode_actuelle"] + 1
    sb.table("associations").update({"periode_actuelle": nouvelle_periode}).eq(
        "id", association_id
    ).execute()


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


# ---------- Administration (super_admin) ----------

def reset_tontine(tontine_id):
    """Remet une tontine à zéro : supprime toutes ses cotisations, remet
    le cycle à 1, le statut à 'en_attente', et 'a_recu_tour' à False pour
    tous les membres. Les membres eux-mêmes restent inscrits."""
    sb = get_client()
    sb.table("cotisations").delete().eq("tontine_id", tontine_id).execute()
    sb.table("membres").update({"a_recu_tour": False}).eq("tontine_id", tontine_id).execute()
    sb.table("tontines").update({
        "cycle_actuel": 1,
        "statut": "en_attente",
    }).eq("id", tontine_id).execute()


def get_all_associations():
    sb = get_client()
    res = sb.table("associations").select("*, users(nom)").order("created_at", desc=True).execute()
    associations = []
    for a in res.data:
        a2 = dict(a)
        a2["admin_nom"] = a["users"]["nom"] if a.get("users") else "—"
        associations.append(a2)
    return associations


def reset_association(association_id):
    """Remet une association à zéro : supprime toutes ses cotisations et
    remet la période à 1. Les membres restent inscrits."""
    sb = get_client()
    sb.table("cotisations_association").delete().eq("association_id", association_id).execute()
    sb.table("associations").update({"periode_actuelle": 1}).eq("id", association_id).execute()


def wipe_all_data():
    """Efface TOUTES les tontines, associations, membres et cotisations
    (garde les comptes utilisateurs). Irréversible."""
    sb = get_client()
    sb.table("cotisations").delete().neq("id", 0).execute()
    sb.table("membres").delete().neq("id", 0).execute()
    sb.table("tontines").delete().neq("id", 0).execute()
    sb.table("cotisations_association").delete().neq("id", 0).execute()
    sb.table("membres_association").delete().neq("id", 0).execute()
    sb.table("associations").delete().neq("id", 0).execute()


def delete_admin_account(user_id):
    """Supprime un compte admin ainsi que toutes les tontines et
    associations qu'il administre (et leurs membres/cotisations), plus
    ses propres participations ailleurs."""
    sb = get_client()

    # Tontines administrées par ce compte : supprimer en cascade
    admin_tontines = sb.table("tontines").select("id").eq("admin_id", user_id).execute()
    tontine_ids = [t["id"] for t in admin_tontines.data]
    if tontine_ids:
        sb.table("cotisations").delete().in_("tontine_id", tontine_ids).execute()
        sb.table("membres").delete().in_("tontine_id", tontine_ids).execute()
        sb.table("tontines").delete().in_("id", tontine_ids).execute()

    # Associations administrées par ce compte : supprimer en cascade
    admin_associations = sb.table("associations").select("id").eq("admin_id", user_id).execute()
    association_ids = [a["id"] for a in admin_associations.data]
    if association_ids:
        sb.table("cotisations_association").delete().in_("association_id", association_ids).execute()
        sb.table("membres_association").delete().in_("association_id", association_ids).execute()
        sb.table("associations").delete().in_("id", association_ids).execute()

    # Ses propres participations ailleurs (en tant qu'adhérent)
    sb.table("cotisations").delete().eq("user_id", user_id).execute()
    sb.table("membres").delete().eq("user_id", user_id).execute()
    sb.table("cotisations_association").delete().eq("user_id", user_id).execute()
    sb.table("membres_association").delete().eq("user_id", user_id).execute()

    # Abonnement associé (s'il en avait un)
    sb.table("subscriptions").delete().eq("admin_id", user_id).execute()

    # Le compte lui-même
    sb.table("users").delete().eq("id", user_id).execute()


def delete_user_account(user_id):
    """Supprime un compte utilisateur simple (role 'user') : ses
    cotisations et ses participations (membres) dans les tontines et
    associations qu'il a rejointes, puis le compte lui-même."""
    sb = get_client()

    sb.table("cotisations").delete().eq("user_id", user_id).execute()
    sb.table("membres").delete().eq("user_id", user_id).execute()
    sb.table("cotisations_association").delete().eq("user_id", user_id).execute()
    sb.table("membres_association").delete().eq("user_id", user_id).execute()
    sb.table("users").delete().eq("id", user_id).execute()
