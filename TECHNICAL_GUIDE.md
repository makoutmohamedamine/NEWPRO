# Guide Technique - Intégration Outlook et Upload de CV

## 📑 Table des matières
1. [Système d'Upload de CV](#système-dupload-de-cv)
2. [Connecteur Outlook](#connecteur-outlook)
3. [Pipeline de Synchronisation](#pipeline-de-synchronisation)
4. [Modèles de Données](#modèles-de-données)
5. [Gestion des Erreurs](#gestion-des-erreurs)

---

## Système d'Upload de CV

### Architecture

```
Frontend (React)
    ↓
HTML multipart/form-data
    ↓
POST /api/candidates/upload/
    ↓
Backend (Django)
    ├─ Validation du fichier
    ├─ Création du Candidat
    ├─ Sauvegarde du fichier
    ├─ Extraction du texte
    ├─ Analyse ML
    └─ Retour du candidat formaté
```

### Formats Acceptés
- **PDF** (.pdf) - Extracted avec PyPDF2 / PyMuPDF
- **DOCX** (.docx) - Extracted avec python-docx
- **DOC** (.doc) - Extracted avec python-docx

### Paramètres de l'Endpoint

#### Requis
- `cv`: Fichier multipart (PDF/DOCX) - Limite: 20MB

#### Optionnels
- `sourceEmail`: Email du candidat (string, max 254 chars)
- `targetJobId`: ID du poste à matcher (integer)
- `source`: Source de l'upload (string, défaut: "manual")
  - "manual" - Upload utilisateur
  - "outlook" - Email Outlook
  - "gmail" - Email Gmail

### Flux de Traitement

```python
# 1. Validation
if not cv_file:
    return 400 {"error": "Aucun fichier CV fourni"}

# 2. Détection du format
filename = cv_file.name.lower()
format_f = 'pdf' if filename.endswith('.pdf') else 'docx'

# 3. Création du candidat (infos temporaires)
candidat = Candidat.objects.create(
    nom='Inconnu',
    prenom='Candidat',
    email=source_email or f"candidat_{uuid}@unknown.com"
)

# 4. Sauvegarde du CV
cv = CV.objects.create(
    candidat=candidat,
    fichier=cv_file,
    format_fichier=format_f,
    email_source=source_email
)

# 5. Extraction du texte
texte = extract_text_from_upload(cv.fichier)
cv.texte_extrait = texte
cv.save()

# 6. Mise à jour des infos candidat
email, phone = extract_contact_info(texte)
candidat.email = email or candidat.email
candidat.telephone = phone or candidat.telephone
candidat.save()

# 7. Matching avec poste (optionnel)
if targetJobId:
    poste = Poste.objects.get(pk=targetJobId)
    score = ml_classifier.score(texte, poste.description)
    Candidature.objects.create(
        candidat=candidat,
        poste=poste,
        cv=cv,
        score=score,
        statut='nouveau'
    )

# 8. Retour formaté
return 201 {"candidate": format_candidate(candidat)}
```

### Exemple d'Utilisation (JavaScript)

```javascript
const formData = new FormData();
formData.append('cv', fileInput.files[0]);
formData.append('sourceEmail', 'candidat@example.com');
formData.append('targetJobId', 5);

const response = await fetch('http://127.0.0.1:8000/api/candidates/upload/', {
  method: 'POST',
  body: formData,
  // NE PAS définir Content-Type, le navigateur le fera automatiquement
});

const data = await response.json();
if (response.ok) {
  console.log('Candidat créé:', data.candidate);
  console.log('Score de match:', data.candidate.matchScore);
}
```

---

## Connecteur Outlook

### Architecture Générale

```
OutlookCVExtractor (orchestrateur)
    ├─ OutlookAuthenticator (OAuth2 MSAL)
    │   └─ Azure AD Token Service
    └─ GraphMailClient (API Microsoft Graph)
        ├─ GET /users/{mailbox}/mailFolders/inbox/messages
        ├─ GET /users/{mailbox}/messages/{id}/attachments
        └─ PATCH /users/{mailbox}/messages/{id}
```

### Authentification (OAuth2 Client Credentials)

```python
# Flow d'authentification
1. OutlookAuthenticator.get_token()
   ├─ Envoie client_id + client_secret à Azure AD
   ├─ Reçoit access_token JWT
   └─ Le cache pour réutilisation

2. Chaque requête Graph API
   ├─ Ajoute header: Authorization: Bearer {access_token}
   └─ Azure valide et autorise l'accès
```

### Configuration

#### Variables d'Environnement Requises

```env
# Microsoft Azure
AZURE_TENANT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
  # Format: UUID de l'organisation Azure
  # Récupération: Azure Portal → Directory (tenant) ID

AZURE_CLIENT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
  # Format: UUID de l'application
  # Récupération: Azure Portal → App Registration → Client ID

AZURE_CLIENT_SECRET=xxxxx_xxxxxxxxxxxxxxx~xxxxxxx
  # Format: Chaîne alphanumérique longue
  # Récupération: Azure Portal → Certificates & Secrets → Create → Copy Value
  # ⚠️ À ne partager avec personne, à stocker de manière sécurisée

OUTLOOK_MAILBOX=khaoula.fsttetouane@outlook.com
  # Format: Adresse email complète
  # Cette boite mail doit donner consentement à l'app pour lire ses emails

OUTLOOK_MAX_MESSAGES=50
  # Format: Integer (1-50)
  # Nombre max d'emails à scanner par cycle de sync
```

### Processus de Récupération des CVs

```
1. fetch_new_cvs()
   ├─ Récupère les message IDs déjà traités
   ├─ Appelle list_unread_messages_with_attachments()
   │   └─ Filtre: hasAttachments eq true AND isRead eq false
   ├─ Pour chaque message:
   │   ├─ list_attachments()
   │   │   └─ Récupère meta (nom, type, taille)
   │   ├─ Pour chaque attachment:
   │   │   ├─ _is_cv_attachment() → détection heuristique
   │   │   │   ├─ Extension valide (.pdf, .docx)?
   │   │   │   ├─ Content-type valide?
   │   │   │   └─ Mot-clé CV dans nom/sujet?
   │   │   ├─ get_attachment_bytes()
   │   │   │   └─ Télécharge le contenu binaire
   │   │   └─ Yield EmailAttachment
   │   └─ mark_as_read()
   │       └─ Marque le message comme lu
   └─ move_to_folder("CVs-Traités")
       └─ Archive les messages traités
```

### Exemple d'Utilisation

```python
from recruitment.outlook_connector import OutlookCVExtractor

# Instancier l'extracteur (charge les credentials .env)
extractor = OutlookCVExtractor.from_env()

# Récupérer les CVs
already_processed = set(EmailLog.objects.values_list('message_id', flat=True))

for cv_attachment in extractor.fetch_new_cvs(
    already_processed_ids=already_processed,
    max_messages=50,
    mark_as_read=True,
    move_to_processed=True
):
    print(f"Trouvé: {cv_attachment.filename}")
    print(f"  De: {cv_attachment.sender_email}")
    print(f"  Sujet: {cv_attachment.subject}")
    print(f"  Taille: {len(cv_attachment.content_bytes)} bytes")
    
    # Traiter le fichier
    # save_cv_to_db(cv_attachment)
```

---

## Pipeline de Synchronisation

### Étapes du Pipeline

```
OutlookCVPipeline.run()
├─ 1. Vérifier la configuration Azure
│   ├─ AZURE_TENANT_ID
│   ├─ AZURE_CLIENT_ID
│   ├─ AZURE_CLIENT_SECRET
│   └─ OUTLOOK_MAILBOX
│
├─ 2. Récupérer les IDs déjà traités
│   └─ SELECT message_id FROM EmailLog
│
├─ 3. Récupérer les nouveaux CVs
│   ├─ OutlookCVExtractor.fetch_new_cvs()
│   └─ Pour chaque CV:
│       ├─ 3a. Vérifier les doublons
│       │   ├─ Doublon message_id? → SKIP + log "duplicate"
│       │   ├─ Doublon email candidat? → SKIP + log "duplicate"
│       │   └─ Nouveau → PROCESS
│       │
│       ├─ 3b. Extraire et analyser le CV
│       │   ├─ extract_text_from_upload()
│       │   │   └─ PDF/DOCX → texte brut
│       │   ├─ extract_contact_info()
│       │   │   ├─ Regex email
│       │   │   ├─ Regex téléphone
│       │   │   └─ Regex nom
│       │   └─ ML Classifier
│       │       ├─ score = classifier.predict(texte, poste)
│       │       └─ skills = classifier.extract_skills(texte)
│       │
│       ├─ 3c. Sauvegarder en base de données
│       │   ├─ Créer/récupérer Candidat
│       │   ├─ Créer CV + fichier
│       │   ├─ Créer Candidature
│       │   └─ EmailLog(status='processed')
│       │
│       └─ 3d. Gestion d'erreurs
│           ├─ Si erreur → EmailLog(status='error')
│           ├─ Log détaillé
│           └─ Continuer avec le prochain
│
└─ 4. Retourner le rapport
    ├─ emails_scanned: nombre d'emails traités
    ├─ cvs_found: pièces jointes détectées comme CV
    ├─ cvs_created: nouveaux candidats créés
    ├─ cvs_duplicate: CVs déjà traités
    ├─ cvs_error: erreurs de traitement
    └─ errors: liste des messages d'erreur
```

### Déclenchement Manual (via API)

```bash
curl -X POST http://127.0.0.1:8000/api/outlook/sync/ \
  -H "Content-Type: application/json" \
  -d '{"triggeredBy": "manual"}'
```

**Response:**
```json
{
  "startedAt": "2026-04-20T10:30:00.123456Z",
  "finishedAt": "2026-04-20T10:35:45.654321Z",
  "emailsScanned": 15,
  "cvsFound": 8,
  "cvsCreated": 7,
  "cvsDuplicate": 1,
  "cvsError": 0,
  "success": true,
  "errors": []
}
```

### Code Source

**Fichier:** `/recruitment/pipeline.py`

Clés:
- `PipelineReport` - Dataclass du rapport
- `OutlookCVPipeline` - Classe principale
- `OutlookCVPipeline.run()` - Exécution du cycle complet

---

## Modèles de Données

### Modèle Candidat

```python
class Candidat(models.Model):
    nom              CharField(100)
    prenom           CharField(100)
    email            EmailField(unique=True)
    telephone        CharField(20, blank=True)
    created_at       DateTimeField(auto_now_add=True)
```

### Modèle CV

```python
class CV(models.Model):
    FORMAT_CHOICES = [('pdf', 'PDF'), ('docx', 'DOCX')]
    
    candidat         ForeignKey(Candidat, CASCADE)
    fichier          FileField(upload_to='cvs/')
    format_fichier   CharField(10, choices=FORMAT_CHOICES)
    texte_extrait    TextField(blank=True)           # Texte complet du CV
    email_source     EmailField(blank=True)          # Email d'où vient le CV
    created_at       DateTimeField(auto_now_add=True)
```

### Modèle EmailLog (Traçabilité)

```python
class EmailLog(models.Model):
    STATUS_CHOICES = [
        ('processed', 'Traité avec succès'),
        ('duplicate', 'Doublon ignoré'),
        ('error', 'Erreur de traitement'),
        ('no_cv', 'Pas de CV détecté'),
    ]
    
    message_id       CharField(512, unique=True, db_index=True)  # Graph API ID
    sender_email     EmailField(blank=True)
    sender_name      CharField(200, blank=True)
    subject          CharField(500, blank=True)
    received_at      CharField(50, blank=True)           # ISO datetime
    filename         CharField(300, blank=True)
    
    status           CharField(20, choices=STATUS_CHOICES)
    error_message    TextField(blank=True)
    candidat         ForeignKey(Candidat, SET_NULL, null=True)
    created_at       DateTimeField(auto_now_add=True)
```

### Modèle SyncHistory (Historique)

```python
class SyncHistory(models.Model):
    started_at       DateTimeField()
    finished_at      DateTimeField(null=True, blank=True)
    emails_scanned   IntegerField(default=0)
    cvs_found        IntegerField(default=0)
    cvs_created      IntegerField(default=0)
    cvs_duplicate    IntegerField(default=0)
    cvs_error        IntegerField(default=0)
    triggered_by     CharField(50, default='manual')    # manual / cron / api
    errors_json      TextField(blank=True, default='[]')
```

---

## Gestion des Erreurs

### Erreurs Courantes

#### 1. Configuration Azure Manquante
**Code:** 500 Internal Server Error
**Message:** "Variables d'environnement manquantes : AZURE_TENANT_ID, ..."

**Solution:**
```bash
# Vérifier le fichier .env
cat backend/.env | grep AZURE_

# Remplir les valeurs manquantes
# AZURE_TENANT_ID=votre_value
# AZURE_CLIENT_ID=votre_value
# AZURE_CLIENT_SECRET=votre_value
```

#### 2. Authentification Microsoft Graph Échouée
**Code:** 500 Internal Server Error
**Message:** "Authentification Microsoft Graph échouée : ..."

**Causes possibles:**
- Credentials incorrects
- Secret expiré
- Permissions insuffisantes

**Solution:**
```
1. Vérifier AZURE_CLIENT_SECRET (regénérer si nécessaire)
2. Vérifier permissions: Mail.Read, User.Read.All
3. Vérifier que le consentement administrateur est accordé
4. Vérifier que OUTLOOK_MAILBOX correspond à la bonne boite mail
```

#### 3. Fichier CV Corrompu
**Status:** "error"
**Message:** "Unable to extract text from PDF"

**Solution:**
- Le fichier PDF est corrompu ou protégé
- Télécharger le CV manuellement et vérifier son intégrité
- Essayer de le reconvertir

#### 4. Doublon Détecté
**Status:** "duplicate"
**Raison:** Le même email a déjà été traité

**Info stockée:**
```
EmailLog(
    status='duplicate',
    message_id=...,
    candidat=None  # Pas de nouveau candidat
)
```

### Logging et Debugging

#### Activer les logs Django

**Dans `settings.py`:**
```python
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'file': {
            'level': 'DEBUG',
            'class': 'logging.FileHandler',
            'filename': 'debug.log',
        },
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
        },
    },
    'root': {
        'handlers': ['file', 'console'],
        'level': 'DEBUG',
    },
}
```

#### Vérifier les logs

```bash
# Logs du pipeline
tail -f debug.log | grep -i outlook

# Logs via l'API
GET /api/outlook/status/ → voir les 20 derniers EmailLog

# Logs en base de données
python manage.py shell
>>> from recruitment.models import EmailLog, SyncHistory
>>> EmailLog.objects.order_by('-created_at')[:10]
>>> SyncHistory.objects.order_by('-started_at')[:5]
```

### Test de la Configuration

```bash
# Script de test de connexion
python manage.py shell

from recruitment.outlook_connector import OutlookCVExtractor

try:
    extractor = OutlookCVExtractor.from_env()
    print("✓ Configuration Azure OK")
    
    messages = extractor._client.list_unread_messages_with_attachments(max_results=5)
    print(f"✓ Connexion Outlook OK - {len(messages)} emails trouvés")
    
    for msg in messages[:1]:
        attachments = extractor._client.list_attachments(msg['id'])
        print(f"✓ Attachments: {len(attachments)} trouvés")
        
except Exception as e:
    print(f"✗ Erreur: {e}")
```

---

## Performance et Optimisations

### Limitations Microsoft Graph
- Maximum 50 emails par requête (default: 50)
- Rate limiting: 2000 requêtes/minute

### Optimisations Implémentées
- ✅ Cache du token d'accès
- ✅ Détection des doublons (message_id)
- ✅ Marquage des emails comme lus
- ✅ Archivage dans dossier "CVs-Traités"
- ✅ Extraction de texte optimisée (PyMuPDF rapide)
- ✅ Index DB sur message_id et email

### Recommandations
- Exécuter la sync pendant les heures creuses
- Limiter à 50 emails par sync
- Monitorer les erreurs et les doublons
- Nettoyer les vieux EmailLog après 30 jours

---

**Documentation Technique**
**Créée:** 2026-04-20
**Maintenue par:** Colorado RH Dev Team
