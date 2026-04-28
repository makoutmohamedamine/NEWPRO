# Configuration Complète - Colorado RH Platform

## 📋 Table des matières
1. [Sign Up / Inscription](#sign-up--inscription)
2. [Upload de CV Manuel](#upload-de-cv-manuel)
3. [Configuration Outlook](#configuration-outlook)
4. [Démarrage du Projet](#démarrage-du-projet)

---

## Sign Up / Inscription

### ✅ Implémenté
L'endpoint d'inscription a été ajouté et le formulaire frontend est actif.

### Détails de l'API

**Endpoint:** `POST /api/auth/register/`

**Body JSON:**
```json
{
  "username": "jdupont",
  "email": "jean.dupont@example.com",
  "first_name": "Jean",
  "last_name": "Dupont",
  "password": "MotDePasse123"
}
```

**Réponse (201 Created):**
```json
{
  "message": "Compte \"jdupont\" créé avec succès. Bienvenue!",
  "access": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "user": {
    "id": 1,
    "username": "jdupont",
    "email": "jean.dupont@example.com",
    "first_name": "Jean",
    "last_name": "Dupont",
    "role": "recruteur",
    "is_active": true,
    "date_joined": "2026-04-20T10:30:00Z"
  }
}
```

### Frontend
La page de login a été mise à jour avec:
- Un bouton "Créer un compte" pour basculer vers le formulaire d'inscription
- Formulaire complet avec validation client
- Les données sont stockées dans la base de données Django automatiquement

---

## Upload de CV Manuel

### ✅ Implémenté
L'endpoint d'upload de CV existe déjà et fonctionne.

### Détails de l'API

**Endpoint:** `POST /api/candidates/upload/`

**Content-Type:** `multipart/form-data`

**Paramètres:**
```
- cv: <fichier PDF ou DOCX> [REQUIS]
- sourceEmail: email@example.com [OPTIONNEL]
- source: "manual" [OPTIONNEL, défaut: "manual"]
- targetJobId: 1 [OPTIONNEL - ID du poste pour matcher le CV]
```

**Exemple avec cURL:**
```bash
curl -X POST http://127.0.0.1:8000/api/candidates/upload/ \
  -F "cv=@mon_cv.pdf" \
  -F "sourceEmail=candidat@example.com" \
  -F "targetJobId=1"
```

**Réponse (200 OK):**
```json
{
  "candidate": {
    "id": 42,
    "fullName": "Candidat Inconnu",
    "email": "candidat@example.com",
    "phone": "0612345678",
    "profileLabel": "Ingénieur Python",
    "matchScore": 87.5,
    "status": "nouveau",
    "summary": "Expérience 5 ans en développement Python...",
    "cvUrl": "/media/cvs/mon_cv.pdf",
    "createdAt": "2026-04-20T10:30:00Z"
  }
}
```

### Flux de traitement
1. Le fichier est sauvegardé dans `/media/cvs/`
2. Le texte est extrait (PDF ou DOCX)
3. Le candidat est créé automatiquement
4. Les infos sont mises à jour (email, téléphone)
5. Si un poste cible est fourni, une candidature est créée avec scoring

---

## Configuration Outlook

### 📌 Étapes de Configuration Azure/Outlook

Avant de pouvoir récupérer les CVs depuis Outlook, vous devez configurer Microsoft Azure:

#### 1️⃣ Créer une Application Azure AD

1. Allez sur https://portal.azure.com
2. Cliquez sur **Azure Active Directory** → **App Registrations**
3. Cliquez sur **+ New Registration**
4. Remplissez:
   - **Name:** `Colorado RH CV Extractor` (ou votre choix)
   - **Supported account types:** `Accounts in this organizational directory only`
   - Cliquez **Register**

#### 2️⃣ Générer les Secrets

1. Dans votre app registration, allez à **Certificates & secrets**
2. Cliquez **+ New client secret**
3. Décrivez: `CV Extractor Secret`
4. Cliquez **Add**
5. **Copiez la valeur du secret** (vous ne pourrez plus la voir après)

#### 3️⃣ Configurer les Permissions

1. Allez à **API permissions**
2. Cliquez **+ Add a permission**
3. Sélectionnez **Microsoft Graph**
4. Choisissez **Application permissions** (pas Delegated)
5. Recherchez et sélectionnez:
   - `Mail.Read` - Lire les emails
   - `User.Read.All` - Lire les utilisateurs
6. Cliquez **Add permissions**
7. Cliquez **Grant admin consent for [votre organisation]**

#### 4️⃣ Récupérer les Identifiants

Dans votre app registration overview, notez:
- **Application (client) ID** → `AZURE_CLIENT_ID`
- **Directory (tenant) ID** → `AZURE_TENANT_ID`
- Client Secret (de l'étape 2) → `AZURE_CLIENT_SECRET`

#### 5️⃣ Configurer le Fichier .env

Modifiez `.env` dans `/backend/`:

```env
# Microsoft Azure / Outlook Office 365
AZURE_TENANT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
AZURE_CLIENT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
AZURE_CLIENT_SECRET=votre_secret_ici_xxx~xxxxxxx

# Boite mail Outlook à surveiller
OUTLOOK_MAILBOX=khaoula.fsttetouane@outlook.com

# Nombre maximum d'emails à traiter par cycle
OUTLOOK_MAX_MESSAGES=50
```

#### 6️⃣ Donner l'Accès à la Boite Mail

L'application Azure a besoin d'un accès délégué à la boite mail de khaoula.

**Option A:** Utiliser le compte khaoula (Plus facile)
- Se connecter à https://login.microsoftonline.com avec khaoula.fsttetouane@outlook.com
- Accepter les permissions de l'app Colorado RH

**Option B:** Admin delegation (Pour les orgs)
- Demander à l'admin Azure de configurer les permissions d'application

### Endpoint de Synchronisation

Une fois configurée, vous pouvez déclencher la synchronisation Outlook:

**Endpoint:** `POST /api/outlook/sync/`

**Response:**
```json
{
  "startedAt": "2026-04-20T10:30:00Z",
  "finishedAt": "2026-04-20T10:35:00Z",
  "emailsScanned": 15,
  "cvsFound": 8,
  "cvsCreated": 7,
  "cvsDuplicate": 1,
  "cvsError": 0,
  "success": true,
  "errors": []
}
```

**Statut de la connexion:**

`GET /api/outlook/status/` - Voir le statut de la connexion et l'historique

---

## Démarrage du Projet

### Backend Setup

```bash
# Entrer dans le répertoire backend
cd backend

# Activer l'environnement virtuel
env\Scripts\activate  # Sur Windows
# ou
source env/bin/activate  # Sur Linux/Mac

# Installer les dépendances
pip install -r backend/requirements.txt

# Appliquer les migrations
python manage.py migrate

# Créer le premier administrateur
python manage.py createsuperuser

# Démarrer le serveur
python manage.py runserver
```

### Frontend Setup

```bash
# Entrer dans le répertoire frontend
cd frontend

# Installer les dépendances
npm install

# Démarrer le serveur de développement
npm start
```

### Accès à l'Application

- **Frontend:** http://127.0.0.1:3000
- **Backend API:** http://127.0.0.1:8000/api/
- **Admin Django:** http://127.0.0.1:8000/admin/

---

## 🔄 Workflows Principaux

### 1. Inscription d'un nouvel utilisateur
```
Frontend Login Page → "Créer un compte" 
→ Remplir formulaire (nom, email, username, mot de passe)
→ POST /api/auth/register/
→ Utilisateur créé avec rôle "recruteur"
→ Tokens JWT retournés
→ Redirection vers Dashboard
```

### 2. Ajouter un CV manuellement
```
Frontend Sidebar → "Upload CV" ou "Ajouter candidat"
→ Sélectionner fichier PDF/DOCX
→ POST /api/candidates/upload/
→ Extraction du texte
→ Candidat créé automatiquement
→ Analyse ML
→ Affichage dans le Dashboard
```

### 3. Récupérer les CVs depuis Outlook
```
Frontend Dashboard → "Sync Outlook" (bouton)
→ POST /api/outlook/sync/
→ Connexion à khaoula.fsttetouane@outlook.com
→ Récupération des emails avec pièces jointes
→ Filtrage des CVs (PDF/DOCX)
→ Extraction du texte
→ Création des candidats
→ Analyse ML et scoring
→ Affichage du rapport
```

---

## 📝 Notes Importantes

### Sécurité
- ✅ Les mots de passe sont hachés avec Django
- ✅ Les tokens JWT expiration est configurée
- ✅ CORS est activé pour localhost
- ⚠️ À changer en production: `DEBUG=False`, `ALLOWED_HOSTS`, variables d'environnement sécurisées

### Base de Données
- Actuellement SQLite pour développement
- PostgreSQL configurée mais à activer en prodduction
- Les migrations sont appliquées avec `python manage.py migrate`

### Fichiers
- Les CVs sont stockés dans `/backend/media/cvs/`
- Les fichiers uploadés ont des noms uniques pour éviter les collisions

---

## ❓ Dépannage

### Erreur "Variables d'environnement manquantes"
- Vérifiez que le fichier `.env` existe dans `/backend/`
- Vérifiez les valeurs `AZURE_*` et `OUTLOOK_MAILBOX`

### Erreur "Authentification Microsoft Graph échouée"
- Vérifiez que les credentials Azure sont corrects
- Vérifiez que les permissions "Mail.Read" et "User.Read.All" sont accordées
- Vérifiez que le consentement administrateur a été accordé

### Registration échoue avec "Email already exists"
- L'email est déjà utilisé, choisissez un autre

### Upload de CV échoue
- Vérifiez que c'est un PDF ou DOCX
- Vérifiez que le fichier n'est pas corrompu
- Vérifiez les permissions sur `/backend/media/`

---

## 📚 Architecture

### Backend (Django + DRF)
- `/recruitment/views.py` - Tous les endpoints
- `/recruitment/models.py` - Schéma DB (CustomUser, Candidat, CV, Candidature)
- `/recruitment/serializers.py` - Sérialisation JSON
- `/recruitment/pipeline.py` - Pipeline Outlook → ML → DB
- `/recruitment/outlook_connector.py` - Connecteur Microsoft Graph

### Frontend (React)
- `/src/page/login.jsx` - Page d'authentification + inscription
- `/src/components/` - Composants réutilisables
- `/src/api/api.js` - Client HTTP

---

**Créé le:** 2026-04-20
**Dernière mise à jour:** 2026-04-20
