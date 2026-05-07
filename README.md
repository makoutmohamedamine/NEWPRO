# - Plateforme RH intelligente

Application full-stack pour la gestion de candidatures, l'analyse de CV (ML + IA), le suivi du workflow RH et la gestion des entretiens.

## Fonctionnalites principales

- Gestion des postes, candidats, CV et candidatures
- Workflow RH par statuts et domaines
- Tableau de bord RH
- Analyse de CV par Machine Learning
- Analyse de CV par IA (Groq)
- Synchronisation des emails (Gmail et Outlook legacy)
- Authentification JWT et gestion des utilisateurs
- Espace chat RH pour consultation de l'historique

## Stack technique

### Backend

- Python
- Django
- Django REST Framework
- JWT (`djangorestframework-simplejwt`)
- NLP/ML: `scikit-learn`, `nltk`, `xgboost`

### Frontend

- React
- React Router
- Axios
- Recharts
- React Big Calendar

## Structure du projet

```text
NEWPRO/
|- backend/      # API Django + logique metier RH/IA
|- frontend/     # Interface React
`- README.md
```

## Prerequis

- Python 3.10+ (recommande)
- Node.js 18+ et npm
- Git

## Installation et lancement local

## 1) Cloner le projet

```bash
git clone https://github.com/makoutmohamedamine/NEWPRO.git
cd NEWPRO
```

## 2) Backend (Django)

```bash
cd backend
python -m venv .venv
```

### Activer l'environnement virtuel

- Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

- Linux/Mac:

```bash
source .venv/bin/activate
```

### Installer les dependances

```bash
pip install -r backend/requirements.txt
```

### Variables d'environnement

Configurer `backend/.env` avec vos cles/API et vos parametres locaux avant de lancer le serveur.

### Migrer la base et lancer le serveur

```bash
python manage.py migrate
python manage.py runserver
```

Backend disponible sur: `http://127.0.0.1:8000`

## 3) Frontend (React)

Dans un nouveau terminal:

```bash
cd frontend
npm install
npm start
```

Frontend disponible sur: `http://localhost:3000`

Le frontend est configure avec un proxy vers `http://127.0.0.1:8000`.

## Endpoints API utiles (exemples)

- `POST /api/auth/login/`
- `GET /api/dashboard/`
- `GET /api/candidates/`
- `POST /api/candidates/upload/`
- `GET /api/dossiers/`
- `POST /api/ml/analyse/`
- `POST /api/ai/analyse/`
- `POST /api/gmail/sync/`

> Le prefixe exact (`/api/` ou autre) depend de la configuration des urls globales Django.

## Scripts frontend

Dans `frontend/`:

- `npm start` : mode developpement
- `npm run build` : build de production
- `npm test` : tests

## Securite

- Ne pas versionner les secrets (`.env`, tokens, cles API)
- Regenerer toute cle exposee accidentellement
- Utiliser des comptes de service avec permissions minimales

## Auteur

Projet: [makoutmohamedamine/NEWPRO](https://github.com/makoutmohamedamine/NEWPRO)
