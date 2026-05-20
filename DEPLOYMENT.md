# Déploiement NEWPRO (production)

Guide pour déployer la plateforme RH sur un **serveur Linux** (Ubuntu 22.04 recommandé), accessible via **SSH** (MobaXterm, PuTTY, etc.).

## Architecture cible

```text
Navigateur
    |
    v
Nginx (port 80/443)
    |-- /          --> React build (frontend/build)
    |-- /api/      --> Gunicorn (Django)
    |-- /admin/    --> Gunicorn
    |-- /media/    --> Fichiers CV uploades
    |-- /static/   --> Fichiers admin Django
    |
PostgreSQL (local)
```

## Prérequis serveur

| Composant | Version min. |
|-----------|--------------|
| OS | Ubuntu 22.04 LTS (ou Debian 12) |
| RAM | 2 Go (4 Go recommande avec ML) |
| Disque | 10 Go libres |
| Python | 3.10+ |
| Node.js | 18+ (pour build frontend sur le serveur) |
| PostgreSQL | 14+ |

## Étape 1 — Connexion SSH (MobaXterm)

1. Ouvrez MobaXterm → **Session** → **SSH**.
2. Renseignez l’**IP** ou le hostname du serveur, l’utilisateur (ex. `ubuntu`) et la clé/mot de passe.
3. Connectez-vous.

## Étape 2 — Transférer le projet sur le serveur

**Option A — Git (recommandé)**

```bash
sudo mkdir -p /var/www/newpro
sudo chown $USER:$USER /var/www/newpro
cd /var/www/newpro
git clone https://github.com/makoutmohamedamine/NEWPRO.git .
```

**Option B — Copie depuis Windows (MobaXterm SFTP)**

1. Panneau gauche SFTP → glissez le dossier `NEWPRO` vers `/var/www/newpro`.
2. Excluez `node_modules`, `.venv`, `frontend/build` pour accélérer le transfert.

## Étape 3 — Préparer le build frontend (sur votre PC Windows)

Sur votre machine, avant ou après transfert :

```powershell
cd "C:\Users\STG IT2\Desktop\NEWPRO\frontend"
npm install
$env:REACT_APP_API_URL="http://VOTRE_IP_OU_DOMAINE/api"
npm run build
```

Copiez ensuite `frontend/build/` sur le serveur si vous ne compilez pas sur le serveur.

## Étape 4 — Variables d’environnement backend

Sur le serveur :

```bash
cp /var/www/newpro/deploy/env.example /var/www/newpro/backend/.env
nano /var/www/newpro/backend/.env
```

Variables **obligatoires** :

- `SECRET_KEY` — clé aléatoire longue
- `DEBUG=False`
- `ALLOWED_HOSTS` — domaine et/ou IP du serveur
- `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`

Variables **optionnelles** : `GROQ_API_KEY`, Azure/Outlook, Gmail (`client_secret.json`, `token.json`).

Générer une clé secrète :

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(50))"
```

## Étape 5 — Installation automatique (Ubuntu)

```bash
cd /var/www/newpro/deploy
chmod +x install-server.sh
sudo DB_PASS='MotDePasseFort123' DOMAIN='192.168.1.50' bash install-server.sh
```

Remplacez `DOMAIN` par votre IP ou nom de domaine.

## Étape 5 bis — Installation manuelle

### PostgreSQL

```bash
sudo -u postgres createuser newpro
sudo -u postgres createdb -O newpro newpro
sudo -u postgres psql -c "ALTER USER newpro WITH PASSWORD 'votre_mdp';"
```

### Backend

```bash
cd /var/www/newpro/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py createsuperuser
mkdir -p media/cvs
```

### Service Gunicorn

```bash
sudo cp /var/www/newpro/deploy/newpro-backend.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now newpro-backend
sudo systemctl status newpro-backend
```

### Nginx

```bash
# Editez deploy/nginx-newpro.conf : remplacez VOTRE_DOMAINE
sudo cp /var/www/newpro/deploy/nginx-newpro.conf /etc/nginx/sites-available/newpro
sudo ln -s /etc/nginx/sites-available/newpro /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl reload nginx
```

Permissions :

```bash
sudo chown -R www-data:www-data /var/www/newpro/backend/media
sudo chown -R www-data:www-data /var/www/newpro/backend/staticfiles
```

## Étape 6 — HTTPS (Let's Encrypt, optionnel)

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d votre-domaine.com
```

Puis dans `.env` :

```env
CORS_ALLOW_ALL_ORIGINS=False
CORS_ALLOWED_ORIGINS=https://votre-domaine.com
```

Rebuild frontend avec `REACT_APP_API_URL=https://votre-domaine.com/api`.

## Vérifications

| Test | Commande / URL |
|------|----------------|
| API | `curl http://IP/api/auth/check-setup/` |
| Frontend | Navigateur → `http://IP/` |
| Admin Django | `http://IP/admin/` |
| Logs backend | `sudo journalctl -u newpro-backend -f` |
| Logs Nginx | `sudo tail -f /var/log/nginx/error.log` |

## Mise à jour après modification du code

```bash
cd /var/www/newpro
git pull   # ou recopiez les fichiers

cd backend
source .venv/bin/activate
pip install -r backend/requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
sudo systemctl restart newpro-backend

cd ../frontend
npm ci
REACT_APP_API_URL=https://votre-domaine.com/api npm run build
sudo systemctl reload nginx
```

## Sécurité production

- Ne jamais versionner `.env`, `token.json`, `client_secret.json`.
- `DEBUG=False` obligatoire.
- Restreindre `ALLOWED_HOSTS` et `CORS_ALLOWED_ORIGINS`.
- Pare-feu : ouvrir seulement 22 (SSH), 80, 443.
- Sauvegardes régulières de PostgreSQL et du dossier `backend/media/`.

## Dépannage

**502 Bad Gateway** — Gunicorn arrêté ou socket incorrect :

```bash
sudo systemctl restart newpro-backend
ls -la /run/newpro/gunicorn.sock
```

**Erreur PostgreSQL au démarrage** — Vérifiez `.env` et que PostgreSQL tourne : `sudo systemctl status postgresql`.

**CORS / login échoue** — `REACT_APP_API_URL` au build doit pointer vers la même origine que le site (ex. `https://domaine.com/api`).

**Analyse IA indisponible** — Ajoutez `GROQ_API_KEY` dans `.env` et redémarrez le service.
