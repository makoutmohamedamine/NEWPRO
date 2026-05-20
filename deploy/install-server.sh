#!/usr/bin/env bash
# Installation NEWPRO sur Ubuntu 22.04+ (executer en root: sudo bash install-server.sh)
set -euo pipefail

APP_DIR="/var/www/newpro"
DOMAIN="${DOMAIN:-localhost}"
DB_NAME="${DB_NAME:-newpro}"
DB_USER="${DB_USER:-newpro}"
DB_PASS="${DB_PASS:-}"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Lancez ce script avec sudo."
  exit 1
fi

if [[ -z "$DB_PASS" ]]; then
  echo "Definissez le mot de passe PostgreSQL: DB_PASS='votre_mdp' sudo -E bash install-server.sh"
  exit 1
fi

echo "==> Paquets systeme"
apt-get update
apt-get install -y python3 python3-venv python3-pip nginx postgresql postgresql-contrib \
  build-essential libpq-dev curl git

echo "==> PostgreSQL"
sudo -u postgres psql -tc "SELECT 1 FROM pg_roles WHERE rolname='$DB_USER'" | grep -q 1 \
  || sudo -u postgres createuser "$DB_USER"
sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname='$DB_NAME'" | grep -q 1 \
  || sudo -u postgres createdb -O "$DB_USER" "$DB_NAME"
sudo -u postgres psql -c "ALTER USER $DB_USER WITH PASSWORD '$DB_PASS';"

echo "==> Repertoire application"
mkdir -p "$APP_DIR"
if [[ ! -d "$APP_DIR/backend" ]]; then
  echo "Copiez d'abord le projet dans $APP_DIR (git clone ou scp)."
  exit 1
fi

echo "==> Backend Python"
cd "$APP_DIR/backend"
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r backend/requirements.txt

if [[ ! -f .env ]]; then
  cp "$APP_DIR/deploy/env.example" .env
  SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(50))")
  sed -i "s|^SECRET_KEY=.*|SECRET_KEY=$SECRET|" .env
  sed -i "s|^DEBUG=.*|DEBUG=False|" .env
  sed -i "s|^ALLOWED_HOSTS=.*|ALLOWED_HOSTS=$DOMAIN|" .env
  sed -i "s|^CORS_ALLOWED_ORIGINS=.*|CORS_ALLOWED_ORIGINS=http://$DOMAIN,https://$DOMAIN|" .env
  sed -i "s|^DB_NAME=.*|DB_NAME=$DB_NAME|" .env
  sed -i "s|^DB_USER=.*|DB_USER=$DB_USER|" .env
  sed -i "s|^DB_PASSWORD=.*|DB_PASSWORD=$DB_PASS|" .env
  echo "Fichier .env cree — verifiez-le avant de continuer."
fi

.venv/bin/python manage.py migrate --noinput
.venv/bin/python manage.py collectstatic --noinput
mkdir -p media/cvs
chown -R www-data:www-data "$APP_DIR/backend/media" "$APP_DIR/backend/staticfiles" 2>/dev/null || true

echo "==> Frontend (Node requis sur le serveur ou build local puis copie du dossier build/)"
if command -v npm >/dev/null 2>&1 && [[ -d "$APP_DIR/frontend" ]]; then
  cd "$APP_DIR/frontend"
  npm ci
  REACT_APP_API_URL="http://$DOMAIN/api" npm run build
fi

echo "==> Nginx + systemd"
sed "s/VOTRE_DOMAINE/$DOMAIN/g" "$APP_DIR/deploy/nginx-newpro.conf" > /etc/nginx/sites-available/newpro
ln -sf /etc/nginx/sites-available/newpro /etc/nginx/sites-enabled/newpro
rm -f /etc/nginx/sites-enabled/default 2>/dev/null || true
cp "$APP_DIR/deploy/newpro-backend.service" /etc/systemd/system/newpro-backend.service
chown -R www-data:www-data "$APP_DIR"
nginx -t
systemctl daemon-reload
systemctl enable --now newpro-backend
systemctl reload nginx

echo "==> Termine. Ouvrez http://$DOMAIN"
echo "Creez l'admin: cd $APP_DIR/backend && .venv/bin/python manage.py createsuperuser"
