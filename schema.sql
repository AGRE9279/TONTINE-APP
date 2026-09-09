-- ============================================================
-- Script à exécuter dans Supabase : SQL Editor > New query
-- ============================================================

create table if not exists users (
    id bigint generated always as identity primary key,
    nom text not null,
    telephone text unique not null,
    password_hash text not null,
    created_at timestamptz not null default now()
);

create table if not exists tontines (
    id bigint generated always as identity primary key,
    nom text not null,
    code_invitation text unique not null,
    montant_cotisation numeric not null,
    frequence text not null,               -- 'hebdomadaire' | 'mensuelle'
    admin_id bigint not null references users(id),
    cycle_actuel int not null default 1,
    statut text not null default 'en_attente', -- 'en_attente' | 'active' | 'terminee'
    created_at timestamptz not null default now()
);

create table if not exists membres (
    id bigint generated always as identity primary key,
    tontine_id bigint not null references tontines(id),
    user_id bigint not null references users(id),
    ordre_tour int not null,
    a_recu_tour boolean not null default false,
    joined_at timestamptz not null default now(),
    unique(tontine_id, user_id)
);

create table if not exists cotisations (
    id bigint generated always as identity primary key,
    tontine_id bigint not null references tontines(id),
    user_id bigint not null references users(id),
    cycle_numero int not null,
    montant numeric not null,
    statut text not null default 'en_attente', -- 'en_attente' | 'declaree' | 'validee'
    date_declaration timestamptz,
    date_validation timestamptz,
    unique(tontine_id, user_id, cycle_numero)
);

-- Index utiles pour les requêtes fréquentes
create index if not exists idx_membres_tontine on membres(tontine_id);
create index if not exists idx_cotisations_tontine_cycle on cotisations(tontine_id, cycle_numero);

-- ============================================================
-- Sécurité : on désactive RLS pour ce prototype (authentification
-- maison gérée côté appli, pas via Supabase Auth). À revoir plus
-- tard si tu veux renforcer la sécurité (voir note en bas du README).
-- ============================================================
alter table users disable row level security;
alter table tontines disable row level security;
alter table membres disable row level security;
alter table cotisations disable row level security;
