# 🚀 Démarrage Rapide - Colorado RH Platform

## ⚡ Setup Rapide (5 minutes)

### 1. Démarrer le Backend

```bash
# Ouvrir un terminal PowerShell
cd C:\Users\STG IT2\Desktop\NEWPRO\backend

# Activer l'environnement virtuel
env\Scripts\activate

# Démarrer Django
python manage.py runserver

# ✓ Vous devriez voir: "Starting development server at http://127.0.0.1:8000/"
```

### 2. Démarrer le Frontend

```bash
# Ouvrir un AUTRE terminal PowerShell
cd C:\Users\STG IT2\Desktop\NEWPRO\frontend

# Installer les dépendances (si première fois)
npm install

# Démarrer React
npm start

# ✓ Vous devriez voir: "Compiled successfully!"
# ✓ Le navigateur ouvrira automatiquement http://127.0.0.1:3000
```

### 3. Accéder à l'Application

- **Frontend:** http://127.0.0.1:3000
- **API:** http://127.0.0.1:8000/api/
- **Admin:** http://127.0.0.1:8000/admin/

---

## 📋 Les 3 Nouvelles Fonctionnalités

### 1️⃣ S'inscrire (Sign Up)

**Dans l'app:**
1. Allez à http://127.0.0.1:3000
2. Cliquez "Créer un compte"
3. Remplissez:
   - Prénom
   - Nom
   - Email
   - Nom d'utilisateur
   - Mot de passe (min 6 caractères)
4. Cliquez "S'inscrire"

**Résultat:**
- ✓ Utilisateur créé avec rôle "recruteur"
- ✓ Connexion automatique
- ✓ Accès au Dashboard

---

### 2️⃣ Uploader un CV Manuellement

**Option A: Via l'API (Curl)**

```bash
curl -X POST http://127.0.0.1:8000/api/candidates/upload/ \
  -F "cv=@C:\chemin\vers\mon_cv.pdf" \
  -F "sourceEmail=candidat@example.com" \
  -F "targetJobId=1"
```

**Option B: Via le Composant Frontend**

```javascript
// Utiliser le composant CVUpload (disponible bientôt au Dashboard)
// Pour le tester maintenant:

import CVUpload from './components/CVUpload';

// Dans votre composant:
<CVUpload />
```

**Formats acceptés:**
- ✓ PDF (.pdf)
- ✓ Word (.docx)
- ✓ Taille max: 20 MB

**Résultat:**
- ✓ Candidat créé automatiquement
- ✓ Texte extrait et analysé
- ✓ Score calculé si poste fourni
- ✓ Affiché dans le Dashboard

---

### 3️⃣ Récupérer les CVs depuis Outlook

**Prérequis:** Configurer Azure (voir section ci-dessous)

**Dans l'app:**
1. Cliquez "Synchronisation Outlook" (déjà dans l'app)
2. Cliquez "Lancer la synchro"
3. Attendez le résultat

**Via l'API:**
```bash
curl -X POST http://127.0.0.1:8000/api/outlook/sync/ \
  -H "Content-Type: application/json"
```

**Résultat:**
- ✓ Emails récupérés de khaoula.fsttetouane@outlook.com
- ✓ CVs détectés automatiquement
- ✓ Candidats créés
- ✓ Scores calculés

---

## 🔧 Configuration Outlook (Etapes Importantes)

### ÉTAPE 1: Créer une Application Azure

1. Allez sur https://portal.azure.com
2. Cliquez **Azure Active Directory**
3. Cliquez **App Registrations**
4. Cliquez **+ New Registration**
5. Nom: `Colorado RH CV Extractor`
6. Cliquez **Register**

### ÉTAPE 2: Créer un Secret

1. Dans votre app, cliquez **Certificates & secrets**
2. Cliquez **+ New client secret**
3. Description: `CV Extractor Secret`
4. Cliquez **Add**
5. **COPIEZ la valeur** (dernière chance de la voir!)

### ÉTAPE 3: Ajouter les Permissions

1. Cliquez **API permissions**
2. Cliquez **+ Add a permission**
3. Sélectionnez **Microsoft Graph**
4. Cliquez **Application permissions**
5. Cherchez et cochez:
   - `Mail.Read`
   - `User.Read.All`
6. Cliquez **Add permissions**
7. Cliquez **Grant admin consent** ⚠️ Important!

### ÉTAPE 4: Récupérer les Identifiants

Dans la page **Overview**, copiez:
- **Application (client) ID** → `AZURE_CLIENT_ID`
- **Directory (tenant) ID** → `AZURE_TENANT_ID`
- Votre Secret → `AZURE_CLIENT_SECRET`

### ÉTAPE 5: Remplir le Fichier .env

Ouvrez `backend\.env`:

```env
AZURE_TENANT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
AZURE_CLIENT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
AZURE_CLIENT_SECRET=xxx~xxxxxxx_xxxxxxxxxxxxxx

OUTLOOK_MAILBOX=khaoula.fsttetouane@outlook.com
OUTLOOK_MAX_MESSAGES=50
```

### ÉTAPE 6: Tester

```bash
# Terminal Python
python manage.py shell
>>> from recruitment.outlook_connector import OutlookCVExtractor
>>> extractor = OutlookCVExtractor.from_env()
>>> print("✓ Configuration OK!")
```

---

## 🧪 Tester Rapidement

### Créer un Admin (si première utilisation)

```bash
# Terminal
python manage.py createsuperuser

# Entrez:
# Username: admin
# Email: admin@example.com
# Password: AdminPassword123
```

Puis connectez-vous avec:
- **Username:** admin
- **Password:** AdminPassword123

### Tester le Sign Up

```bash
# Cliquez "Créer un compte"
# Remplissez avec un nouveau compte
# Vérifiez que vous êtes connecté
```

### Tester l'Upload CV

```bash
# Terminal (avec admin loggé)
curl -X POST http://127.0.0.1:8000/api/candidates/upload/ \
  -F "cv=@C:\chemin\vers\test.pdf" \
  -F "sourceEmail=test@example.com"

# Ou utiliser le formulaire frontend
```

### Tester Outlook Sync

```bash
# Terminal (avec config Azure remplie)
curl -X POST http://127.0.0.1:8000/api/outlook/sync/

# Ou cliquer le bouton dans l'app
```

---

## ⚠️ Problèmes Courants

### "ModuleNotFoundError"
```bash
# Vérifier que l'env venv est activé
env\Scripts\activate

# Réinstaller les dépendances
pip install -r backend/requirements.txt
```

### "CORS Error"
```bash
# Normal en développement
# Le frontend http://3000 appelle le backend http://8000
# C'est configuré dans Django
```

### "Variables d'environnement manquantes"
```bash
# Vérifier que backend/.env existe
# Vérifier que toutes les valeurs AZURE_* sont remplies
cat backend\.env | findstr AZURE_
```

### "Connection refused (Outlook)"
```bash
# Vérifier les credentials Azure
# Vérifier que les permissions sont accordées
# Vérifier que OUTLOOK_MAILBOX est correct
```

---

## 📚 Documentation Complète

Pour une documentation détaillée, consultez:

- **CONFIGURATION.md** - Configuration complète et workflows
- **TECHNICAL_GUIDE.md** - Documentation technique détaillée
- **CHANGELIST.md** - Liste de tous les changements

---

## 💡 Astuces

### Accélérer le Développement

```bash
# Utiliser 2-3 terminaux PowerShell:
# Terminal 1: Backend Django
cd backend && env\Scripts\activate && python manage.py runserver

# Terminal 2: Frontend React
cd frontend && npm start

# Terminal 3: Test/Debug
python manage.py shell
```

### Voir les Logs

```bash
# Django debug
# Vérifier dans le terminal backend

# Frontend debug
# Ouvrir la console du navigateur (F12)

# Base de données
python manage.py shell
>>> from recruitment.models import *
>>> Candidat.objects.all()
>>> CV.objects.all()
```

### Réinitialiser la Base de Données

```bash
# ⚠️ Attention: cela supprimera tous les candidats!
python manage.py flush

# Puis recréer un admin:
python manage.py createsuperuser
```

---

## 🎉 Vous Êtes Prêt!

Commandes à lancer dans 2 terminaux séparés:

**Terminal 1 - Backend:**
```bash
cd backend && env\Scripts\activate && python manage.py runserver
```

**Terminal 2 - Frontend:**
```bash
cd frontend && npm start
```

Puis accédez à: **http://127.0.0.1:3000**

---

## 📞 Questions?

1. Consultez **CONFIGURATION.md** pour la configuration
2. Consultez **TECHNICAL_GUIDE.md** pour les détails techniques
3. Consultez **CHANGELIST.md** pour la liste des changements
4. Vérifiez les logs du terminal pour les erreurs
5. Utilisez `python manage.py shell` pour déboguer

---

**Setup créé:** 20 Avril 2026
**Platform:** Colorado RH - Recruitment Intelligence Suite
