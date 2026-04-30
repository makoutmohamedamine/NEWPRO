# Architecture du projet

## 1. Vue d'ensemble

Ce projet est une plateforme RH de gestion de candidatures avec:

- un frontend React pour les écrans métier
- un backend Django + Django REST Framework pour l'API et la logique métier
- une base PostgreSQL obligatoire
- un pipeline d'import de CV depuis Outlook et Gmail
- un moteur de classification/scoring de CV par heuristiques et ML
- une gestion d'authentification JWT avec initialisation du premier administrateur

Objectif principal:

1. créer et gérer des fiches de poste
2. importer ou synchroniser des CV
3. analyser les CV
4. créer les candidats, CV et candidatures en base
5. scorer les candidats contre un poste
6. suivre le workflow RH dans le dashboard et les dossiers

---

## 2. Structure racine

```text
NEWPRO/
├── backend/
├── frontend/
├── QUICKSTART.md
├── QUICKSTART_ML.md
├── CONFIGURATION.md
├── TECHNICAL_GUIDE.md
├── CHANGELIST.md
├── MIGRATION_CLAUDE_TO_ML.md
└── ARCHITECTURE_PROJET.md
```

Rôle des documents racine:

- `QUICKSTART.md`: démarrage global
- `QUICKSTART_ML.md`: démarrage orienté moteur ML
- `CONFIGURATION.md`: configuration technique
- `TECHNICAL_GUIDE.md`: guide technique détaillé
- `CHANGELIST.md`: historique des changements
- `MIGRATION_CLAUDE_TO_ML.md`: transition du moteur IA/Claude vers le moteur ML

---

## 3. Architecture technique globale

```text
React UI
   |
   v
Axios / fetch + JWT
   |
   v
Django REST API
   |
   +--> Auth / utilisateurs
   +--> CRUD postes / candidats / CV / candidatures
   +--> Dashboard / dossiers
   +--> Upload manuel CV
   +--> Sync Outlook / Gmail
   +--> Analyse ML / scoring IA
   |
   v
Services métier / pipelines / moteurs de scoring
   |
   +--> Extraction texte PDF/DOCX
   +--> Classification profil
   +--> Scoring poste <-> CV
   +--> Journalisation sync
   |
   v
PostgreSQL + fichiers media/cvs
```

---

## 4. Backend

### 4.1 Organisation

```text
backend/
├── manage.py
├── create_db.py
├── setup_test_user.py
├── gmail_service.py
├── train_models.py
├── backend/
│   ├── settings.py
│   ├── urls.py
│   ├── asgi.py
│   ├── wsgi.py
│   ├── __init__.py
│   ├── requirements.txt
│   └── import psycopg2.py
└── recruitment/
    ├── admin.py
    ├── apps.py
    ├── models.py
    ├── serializers.py
    ├── views.py
    ├── urls.py
    ├── tests.py
    ├── services.py
    ├── ai_engine.py
    ├── ai_claude.py
    ├── ml_classifier.py
    ├── ml_scoring_engine.py
    ├── scoring_api.py
    ├── outlook_connector.py
    ├── gmail_connector.py
    ├── pipeline.py
    ├── gmail_pipeline.py
    ├── management/
    │   └── commands/
    └── migrations/
```

### 4.2 Backend Django principal

Fichiers clés:

- `backend/manage.py`: point d'entrée Django
- `backend/backend/settings.py`: configuration globale
- `backend/backend/urls.py`: routes racine Django

Configuration notable dans `settings.py`:

- base PostgreSQL obligatoire via variables d'environnement
- `AUTH_USER_MODEL = recruitment.CustomUser`
- DRF configuré avec JWT par défaut
- CORS ouvert à toutes les origines
- `MEDIA_ROOT` pour stocker les CV
- timezone `Africa/Casablanca`

### 4.3 Application métier `recruitment`

Cette app concentre quasiment toute la logique métier:

- modèles RH
- endpoints REST
- login/register/setup
- imports email
- scoring et analyse CV

---

## 5. Modèle de données

Défini dans `backend/recruitment/models.py`.

### 5.1 `CustomUser`

Extension de `AbstractUser`.

Champs métier:

- `role`: `admin`, `rh`, `recruteur`, `manager`

Usage:

- permissions simples par rôle
- isolation des données par propriétaire

### 5.2 `Poste`

Représente une fiche de poste.

Champs principaux:

- `titre`, `description`
- `competences_requises`
- `competences_optionnelles`
- `langues_requises`
- `departement`, `localisation`, `type_contrat`
- `experience_min_annees`
- `niveau_etudes_requis`
- `quota_cible`
- `workflow_actif`
- `score_qualification`
- pondérations de scoring:
  `poids_competences`, `poids_experience`, `poids_formation`, `poids_langues`, `poids_localisation`, `poids_soft_skills`
- `niveau_priorite`
- `created_by`, `created_at`

### 5.3 `Candidat`

Représente la personne candidate.

Champs principaux:

- identité: `nom`, `prenom`, `email`, `telephone`
- provenance: `source`, `source_detail`
- profil: `current_title`, `niveau_etudes`, `annees_experience`
- contenu enrichi: `competences`, `langues`, `soft_skills`, `resume_profil`
- conformité: `consentement_rgpd`
- ownership: `created_by`, `created_at`

### 5.4 `CV`

Fichier de CV associé à un candidat.

Champs:

- `candidat`
- `fichier`
- `format_fichier`
- `texte_extrait`
- `email_source`
- `created_at`

### 5.5 `Candidature`

Association `Candidat` <-> `Poste`.

Champs principaux:

- `candidat`, `poste`, `cv`
- `statut`
- `score`
- `recommandation`
- `workflow_step`
- `source_channel`
- `explication_score`
- `score_details_json`
- `decision_comment`
- `sla_due_at`
- `assigned_to`
- `created_by`
- `created_at`, `updated_at`

Statuts gérés:

- `nouveau`
- `prequalifie`
- `shortlist`
- `entretien`
- `finaliste`
- `offre`
- `en_cours`
- `accepte`
- `refuse`
- `archive`

### 5.6 `EmailLog`

Journal technique des emails traités.

Utilisé pour:

- éviter les doublons par `message_id`
- tracer les erreurs d'import
- relier un email traité à un candidat

### 5.7 `SyncHistory`

Historique d'exécution des synchronisations.

Métriques stockées:

- `emails_scanned`
- `cvs_found`
- `cvs_created`
- `cvs_duplicate`
- `cvs_error`
- `triggered_by`
- `errors_json`

---

## 6. Couche API

### 6.1 Routage

Deux niveaux:

- `backend/backend/urls.py`
- `backend/recruitment/urls.py`

Le préfixe principal est `/api/`.

### 6.2 Authentification et comptes

Endpoints:

- `GET /api/auth/check-setup/`
- `POST /api/auth/setup/`
- `POST /api/auth/login/`
- `POST /api/auth/register/`
- `POST /api/auth/logout/`
- `GET /api/auth/me/`
- `POST /api/auth/refresh/`

Fonctionnement:

1. si aucun utilisateur n'existe, le frontend affiche l'écran `Setup`
2. le premier compte créé est administrateur
3. ensuite la plateforme repasse sur l'écran de login normal
4. la session applicative repose sur JWT access + refresh token

### 6.3 Gestion des utilisateurs

Endpoints admin:

- `GET /api/users/`
- `POST /api/users/create/`
- `GET|PUT|PATCH /api/users/<id>/`
- `DELETE /api/users/<id>/delete/`
- `PATCH /api/users/<id>/toggle/`

### 6.4 Entités RH

ViewSets REST:

- `/api/postes/`
- `/api/candidats/`
- `/api/cvs/`
- `/api/candidatures/`

Endpoints métier complémentaires:

- `GET /api/dashboard/`
- `GET /api/candidates/`
- `GET /api/candidates/<id>/`
- `POST /api/candidates/upload/`
- `PATCH /api/candidates/<id>/update/`
- `GET /api/dossiers/`

### 6.5 Synchronisation emails

Outlook:

- `POST /api/outlook/sync/`
- `GET /api/outlook/status/`

Gmail:

- `POST /api/gmail/sync/`
- `GET /api/gmail/status/`
- `GET /api/gmail/debug/`

### 6.6 Analyse et scoring IA/ML

- `POST /api/ml/analyse/`
- `POST /api/ai/analyse/`
- `POST /api/ai/score/`
- `POST /api/scoring/candidature/`
- `POST /api/scoring/job/`
- `POST /api/scoring/all/`

---

## 7. Logique métier dans `views.py`

`backend/recruitment/views.py` est le centre applicatif principal.

Il contient:

- l'authentification custom
- les endpoints dashboard
- les listes candidates/dossiers
- l'upload manuel
- la mise à jour du statut d'une candidature
- le calcul de payload enrichi envoyé au frontend
- le déclenchement des pipelines Outlook/Gmail
- les endpoints d'analyse ML/IA

Fonctions internes importantes:

- `scope_owned_queryset()`: isole les données par utilisateur
- `recommendation_for_score()`: calcule la recommandation RH
- `workflow_step_for_status()`: traduit un statut en étape métier
- `sla_due_for_status()`: calcule la date limite SLA
- `score_candidate_against_job()`: score heuristique contre un poste
- `pick_target_job()`: choisit le poste cible
- `candidature_payload()`: payload frontend riche
- `candidate_summary_payload()`: fallback quand il n'y a pas encore de candidature

Remarque d'architecture:

- certaines routes sont encore en `AllowAny`, même si l'application s'appuie aussi sur JWT et sur du scoping de données
- la sécurité réelle repose donc à la fois sur le token côté frontend et sur le filtrage applicatif côté backend

---

## 8. Pipelines d'import de CV

### 8.1 Pipeline Outlook

Fichier: `backend/recruitment/pipeline.py`

Rôle:

1. se connecter à Outlook via `outlook_connector.py`
2. récupérer les emails avec CV
3. éviter les doublons via `EmailLog.message_id`
4. lancer l'analyse via `ml_classifier.py`
5. créer ou enrichir `Candidat`
6. enregistrer le fichier dans `CV`
7. créer ou mettre à jour `Candidature`
8. écrire un `EmailLog`
9. produire un `PipelineReport`

Variables d'environnement attendues:

- `AZURE_TENANT_ID`
- `AZURE_CLIENT_ID`
- `AZURE_CLIENT_SECRET`
- `OUTLOOK_MAILBOX`
- `OUTLOOK_MAX_MESSAGES` optionnelle

### 8.2 Pipeline Gmail

Fichier: `backend/recruitment/gmail_pipeline.py`

Même logique générale que le pipeline Outlook, mais avec:

- `gmail_connector.py`
- authentification Gmail/Google
- token local

Variables et fichiers importants:

- `GMAIL_CLIENT_SECRET_FILE`
- `GMAIL_TOKEN_FILE`
- `GMAIL_MAX_MESSAGES`

### 8.3 Historisation

Après chaque sync:

- un `PipelineReport` est converti en `SyncHistory`
- les logs individuels sont stockés dans `EmailLog`

---

## 9. Moteurs d'analyse CV

Le projet possède plusieurs couches d'analyse, ce qui est important architecturalement.

### 9.1 `ai_engine.py`

Rôle:

- extraction texte PDF/DOCX
- heuristiques simples
- scoring avancé par critères

Fonctions clés:

- `extraire_texte_pdf()`
- `extraire_texte_docx()`
- `extraire_texte()`
- `extraire_email()`
- `extraire_telephone()`
- `extraire_competences()`
- `calculer_score()`
- `calculer_score_avance()`

### 9.2 `ml_classifier.py`

Rôle:

- classifier un CV par profil métier
- produire un score composite
- servir les imports Outlook/Gmail et l'upload manuel

Architecture interne:

```text
CV bytes
-> extraction texte PDF/DOCX
-> normalisation NLP
-> extraction email/téléphone/nom/compétences/études/expérience
-> scoring multi-profils
-> sélection du meilleur profil
```

Profils par défaut intégrés:

- Développeur Full Stack
- Data Analyst
- Ingénieur IA/NLP
- Marketing Digital
- Développeur Backend
- DevOps / Cloud

Le classifieur peut aussi charger dynamiquement les profils depuis la table `Poste`.

### 9.3 `ml_scoring_engine.py`

Rôle:

- analyse plus avancée avec `TF-IDF + Word2Vec + XGBoost`
- scoring CV contre une fiche poste
- exploitation de modèles persistés sous `backend/recruitment/models/`

Composants:

- `XGBoostScoringManager`
- `analyze_cv_ml()`
- `score_cv_against_job()`
- catalogue de compétences
- extraction d'indices sémantiques

Remarque:

- si `gensim` n'est pas disponible, le moteur passe en fallback sans Word2Vec

### 9.4 `train_models.py`

Script d'entraînement offline:

- entraîne TF-IDF
- entraîne Word2Vec
- entraîne XGBoost sur données synthétiques
- sauvegarde les artefacts dans `backend/recruitment/models/`

### 9.5 `ai_claude.py`

Présence héritée/migration:

- le projet contient encore une trace de l'ancienne approche Claude
- la documentation `MIGRATION_CLAUDE_TO_ML.md` montre que l'orientation actuelle est centrée sur ML local

---

## 10. Scripts et commandes d'administration

### 10.1 Scripts Python

- `backend/create_db.py`: création interactive d'une base PostgreSQL
- `backend/setup_test_user.py`: probablement pour générer un compte de test
- `backend/train_models.py`: entraînement des modèles ML
- `backend/gmail_service.py`: script/service annexe Gmail

### 10.2 Management commands Django

Dans `backend/recruitment/management/commands/`:

- `create_admin.py`
- `gmail_auth.py`
- `gmail_sync_test.py`

Usage architectural:

- automatiser la préparation du système
- autoriser des opérations de maintenance sans passer par l'UI

---

## 11. Frontend

### 11.1 Stack

Le frontend utilise:

- React 19
- React Router DOM 7
- Axios
- Recharts
- React Scripts

Configuration:

- proxy CRA vers `http://127.0.0.1:8000`

### 11.2 Organisation

```text
frontend/
├── public/
├── package.json
└── src/
    ├── api/
    │   └── api.js
    ├── components/
    │   ├── CVUpload.jsx
    │   ├── GmailSync.jsx
    │   ├── Navbar.jsx
    │   ├── OutlookSync.jsx
    │   └── Sidebar.jsx
    ├── page/
    │   ├── AnalyseIA.jsx
    │   ├── Candidats.jsx
    │   ├── Dashboard.jsx
    │   ├── Dossiers.jsx
    │   ├── GestionUsers.jsx
    │   ├── Postes.jsx
    │   ├── Setup.jsx
    │   └── login.jsx
    ├── App.jsx
    ├── App.js
    ├── App.css
    ├── index.js
    └── index.css
```

### 11.3 Point d'entrée UI

`frontend/src/App.jsx`:

- lit le token JWT depuis `localStorage`
- vérifie si le setup initial est nécessaire
- recharge l'utilisateur courant via `/auth/me/`
- route les pages privées
- cache la page utilisateurs pour les non-admins

### 11.4 Client API

`frontend/src/api/api.js` centralise:

- `axios.create({ baseURL: 'http://127.0.0.1:8000/api' })`
- injection automatique du bearer token
- refresh automatique du token sur `401`
- wrappers de toutes les routes backend

### 11.5 Pages principales

#### `Dashboard.jsx`

Vue cockpit:

- KPIs
- entonnoir de workflow
- distribution des profils
- distribution des scores
- alertes SLA
- top candidats
- vue postes/couverture
- widgets `CVUpload` et `OutlookSync`

#### `Dossiers.jsx`

Vue kanban/colonnes par poste:

- un poste = une colonne
- chaque colonne contient les candidatures rattachées
- recherche par titre de poste

#### `Candidats.jsx`

Vue détaillée candidats:

- filtrage texte + statut
- lecture des compétences
- visualisation du score
- changement de statut
- preview du CV

#### `Postes.jsx`

Gestion des fiches de poste:

- création
- modification
- suppression
- consultation des candidats classés par score pour un poste

#### `AnalyseIA.jsx`

Analyse ponctuelle d'un CV:

- upload PDF/DOCX
- choix optionnel d'un poste cible
- restitution détaillée du scoring

#### `GestionUsers.jsx`

Administration:

- liste des utilisateurs
- création/modification
- activation/désactivation
- suppression

#### `login.jsx`

Écran de connexion et d'inscription:

- login custom vers `/api/auth/login/`
- sign up vers `/api/auth/register/`

#### `Setup.jsx`

Écran d'initialisation:

- création du premier administrateur
- utilisé seulement si aucun compte n'existe

### 11.6 Composants

#### `Sidebar.jsx`

- navigation latérale
- rôle affiché
- logout

#### `CVUpload.jsx`

- import manuel de CV
- choix optionnel du poste cible
- déclenchement du scoring à l'upload

#### `OutlookSync.jsx`

- affichage de l'état de connexion Outlook
- déclenchement manuel de la synchronisation
- restitution du rapport de sync

#### `GmailSync.jsx`

- présent dans l'arborescence mais actuellement vide dans le dépôt

#### `Navbar.jsx`

- présent dans l'arborescence mais non utilisé dans `App.jsx`

---

## 12. Flux métier principaux

### 12.1 Premier démarrage

```text
Frontend App
-> GET /api/auth/check-setup/
-> si aucun user: afficher Setup
-> POST /api/auth/setup/
-> création admin + JWT
-> accès à l'application
```

### 12.2 Connexion utilisateur

```text
Login form
-> POST /api/auth/login/
-> access + refresh + user
-> stockage localStorage
-> GET /api/auth/me/
-> ouverture de l'espace connecté
```

### 12.3 Import manuel d'un CV

```text
Dashboard / CVUpload
-> upload PDF/DOCX
-> POST /api/candidates/upload/
-> extraction texte
-> classification ML
-> création candidat + CV
-> choix ou détection du poste
-> création/mise à jour candidature
-> retour payload candidat enrichi
```

### 12.4 Sync Outlook

```text
OutlookSync button
-> POST /api/outlook/sync/
-> Outlook connector
-> fetch attachments
-> EmailLog duplicate check
-> ml_classifier
-> Candidat + CV + Candidature
-> SyncHistory
-> dashboard refresh
```

### 12.5 Sync Gmail

Même logique que Outlook, mais avec authentification Google/Gmail.

### 12.6 Analyse IA d'un CV

```text
AnalyseIA page
-> POST /api/ai/analyse/
-> extraction texte
-> analyze_cv_ml()
-> score détaillé
-> restitution frontend
```

---

## 13. Sécurité et contrôle d'accès

Mécanismes présents:

- JWT access/refresh
- `me` pour recharger l'identité serveur
- rôle `admin` pour la gestion utilisateurs
- scoping des données par `created_by`

Points à noter:

- plusieurs endpoints métier sont en `AllowAny`
- le projet n'est donc pas strictement verrouillé au niveau DRF pour toutes les routes
- la séparation des données s'appuie en partie sur `scope_owned_queryset()`

En pratique, l'intention architecturale semble être:

- expérience simple en local/démo
- contrôle plus léger sur certains endpoints métier

---

## 14. Stockage

### 14.1 Base de données

PostgreSQL est obligatoire.

Tables métier principales:

- `users`
- `job_positions`
- `candidates`
- `resumes`
- `applications`
- `email_logs`
- `sync_history`

### 14.2 Fichiers

Les CV sont stockés sous:

- `MEDIA_ROOT / cvs/`

Ils sont servis par Django en développement via:

- `static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)`

---

## 15. Dépendances externes

### Backend

- Django
- Django REST Framework
- SimpleJWT
- corsheaders
- psycopg2
- python-dotenv
- PyMuPDF
- python-docx
- nltk
- scikit-learn
- xgboost
- gensim

### Frontend

- react
- react-dom
- react-router-dom
- axios
- recharts

### Services externes

- PostgreSQL
- Microsoft Graph / Azure AD pour Outlook
- Gmail API / OAuth Google pour Gmail

---

## 16. Points d'attention architecturels

### Forces

- architecture claire séparée frontend/backend
- modèle métier RH assez complet
- pipelines email déjà branchés
- scoring à plusieurs niveaux
- UX de setup initial bien pensée

### Particularités

- coexistence de plusieurs moteurs d'analyse: heuristique, ML composite, traces de Claude
- `views.py` est très centralisé et volumineux
- sécurité DRF partiellement ouverte sur plusieurs routes
- `services.py` semble hérité d'une ancienne version et référence des modèles non actuels (`Candidate`, `JobProfile`)
- certains fichiers semblent hérités ou peu utilisés:
  `App.js`, `Navbar.jsx`, `GmailSync.jsx`, `ai_claude.py`

### Pistes d'évolution

- découper `views.py` en modules par domaine
- séparer clairement les services de scoring
- unifier le pipeline d'analyse pour éviter les doublons heuristique/ML
- durcir les permissions DRF route par route
- documenter explicitement les variables d'environnement Outlook/Gmail/ML

---

## 17. Résumé exécutif

Le projet est une suite de recrutement intelligente construite sur une architecture web classique:

1. React gère l'interface RH
2. Django expose une API REST métier
3. PostgreSQL stocke utilisateurs, postes, candidats, CV et candidatures
4. des pipelines Outlook/Gmail alimentent automatiquement la base
5. un moteur ML/heuristique classe et score les CV
6. le frontend restitue le workflow de recrutement via dashboard, dossiers, candidats et postes

En bref, l'architecture est celle d'un ATS léger enrichi par import email et scoring automatisé de CV.
