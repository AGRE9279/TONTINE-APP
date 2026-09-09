# Tontine App — Version Supabase (déployable)

## 1. Créer le projet Supabase

1. Va sur https://supabase.com et connecte-toi (ou crée un compte)
2. Clique sur "New project", donne-lui un nom (ex: `tontine-app`)
3. Choisis un mot de passe pour la base (note-le bien, tu n'en auras
   normalement pas besoin ici mais mieux vaut le garder)
4. Attends 1-2 minutes que le projet soit prêt

## 2. Créer les tables

1. Dans le menu de gauche, clique sur **SQL Editor**
2. Clique sur **New query**
3. Colle tout le contenu du fichier `schema.sql` fourni ici
4. Clique sur **Run** (ou Ctrl+Entrée)
5. Vérifie dans **Table Editor** que les 4 tables sont bien créées :
   `users`, `tontines`, `membres`, `cotisations`

## 3. Récupérer les clés d'API

1. Dans le menu de gauche, va dans **Project Settings** (icône
   engrenage) > **API**
2. Copie l'**URL du projet** (ex: `https://xxxxx.supabase.co`)
3. Copie la clé **anon public** (une longue chaîne commençant par
   `eyJ...`)

## 4. Tester en local avant de déployer

1. Renomme `.streamlit/secrets.toml.example` en
   `.streamlit/secrets.toml`
2. Ouvre ce fichier et colle ton URL et ta clé à la place des
   valeurs d'exemple
3. Installe les dépendances : `pip install -r requirements.txt`
4. Lance : `streamlit run app.py`
5. Crée un compte, une tontine — vérifie dans Supabase (Table
   Editor > users) que la ligne apparaît bien

## 5. Déployer sur Streamlit Cloud (accessible à tous)

1. Crée un nouveau dépôt GitHub (ex: `tontine-app`), et pousse-y
   tous ces fichiers **sauf** `.streamlit/secrets.toml` (il est
   dans le `.gitignore`, donc il ne sera pas envoyé — c'est normal
   et voulu, ne le pousse jamais)
2. Va sur https://share.streamlit.io et connecte-toi avec GitHub
3. Clique sur "New app", choisis ton dépôt, la branche `main`, et
   le fichier `app.py`
4. Avant de déployer, ouvre "Advanced settings" et colle le contenu
   de ton `secrets.toml` local dans le champ Secrets (même format
   TOML)
5. Clique sur "Deploy"

Une fois déployé, tu as une URL publique (ex:
`https://tontine-app-xxxx.streamlit.app`) que tu peux partager avec
n'importe qui — chacun peut créer un compte et rejoindre des
tontines depuis son propre téléphone ou ordinateur.

## Note sur la sécurité

Ce prototype désactive Row Level Security (RLS) sur les tables, car
l'authentification est gérée par l'appli elle-même (mot de passe
haché en SHA-256, comme pour AcademieIA) plutôt que par Supabase
Auth. C'est correct pour un prototype ou un usage restreint entre
personnes de confiance, mais si tu veux ouvrir l'appli à un large
public plus tard, il vaudra la peine de migrer vers Supabase Auth
et d'activer RLS avec des politiques adaptées.
