#!/usr/bin/env bash
# One-time setup for a fresh Ubuntu 24.04 server (built for an Azure B1s VM). Run with sudo:
#
#   sudo git clone https://github.com/Sukanth19/jamr.io.git /opt/jamr
#   sudo bash /opt/jamr/deploy/setup.sh jamr.<region>.cloudapp.azure.com
#
# Spotify only allows https redirect addresses (apart from 127.0.0.1), so a
# domain is required; Caddy gets the HTTPS certificate for it automatically.
# It asks for the Spotify client ID and secret the first time.
#
# Safe to re-run: secrets and the database are kept.
set -euo pipefail

APP_DIR=/opt/jamr
APP_USER=jamr
ENV_FILE=/etc/jamr.env
DOMAIN="${1:-}"

if [ "$(id -u)" -ne 0 ]; then echo "Run as root (or with sudo)." >&2; exit 1; fi
if [ -z "$DOMAIN" ]; then echo "Usage: sudo bash $0 <domain>   e.g. jamr.eastus.cloudapp.azure.com" >&2; exit 1; fi
if ! [[ "$DOMAIN" =~ ^[A-Za-z0-9.-]+$ ]]; then echo "That doesn't look like a domain: $DOMAIN" >&2; exit 1; fi
cd "$APP_DIR"

step() { echo; echo ">> $*"; }

# Read a setting from the env file (empty if missing)
setting() { grep -s "^$1=" "$ENV_FILE" | head -n1 | cut -d= -f2- || true; }

step "System packages"
export DEBIAN_FRONTEND=noninteractive
apt-get update -q
apt-get install -y -q sudo ca-certificates curl git python3 python3-venv postgresql caddy ufw

step "App user"
id "$APP_USER" >/dev/null 2>&1 || useradd --system --home "$APP_DIR" --shell /usr/sbin/nologin "$APP_USER"
chown -R "$APP_USER:$APP_USER" "$APP_DIR"

step "Database"
# Containers used for testing have no systemd to start PostgreSQL
if [ "${JAMR_NO_SYSTEMD:-0}" = 1 ]; then pg_ctlcluster "$(ls /etc/postgresql)" main start || true; fi
DB_PASSWORD=$(setting DATABASE_URL | sed -n 's|^postgresql://jamr:\([^@]*\)@.*|\1|p')
if [ -z "$DB_PASSWORD" ]; then DB_PASSWORD=$(python3 -c "import secrets; print(secrets.token_hex(24))"); fi
if sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname = 'jamr'" | grep -q 1; then
  sudo -u postgres psql -qc "ALTER ROLE jamr WITH LOGIN PASSWORD '$DB_PASSWORD'"
else
  sudo -u postgres psql -qc "CREATE ROLE jamr WITH LOGIN PASSWORD '$DB_PASSWORD'"
fi
sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname = 'jamr_io'" | grep -q 1 \
  || sudo -u postgres createdb -O jamr jamr_io
echo "jamr_io is ready"

step "Settings ($ENV_FILE)"
# Generated once and kept: a new ENCRYPTION_KEY would make stored Spotify tokens unreadable
ENCRYPTION_KEY=$(setting ENCRYPTION_KEY)
[ -n "$ENCRYPTION_KEY" ] || ENCRYPTION_KEY=$(python3 -c "import base64, os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())")
SESSION_SECRET=$(setting SESSION_SECRET)
[ -n "$SESSION_SECRET" ] || SESSION_SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")

SPOTIFY_CLIENT_ID=$(setting SPOTIFY_CLIENT_ID)
SPOTIFY_CLIENT_SECRET=$(setting SPOTIFY_CLIENT_SECRET)
if [ -z "$SPOTIFY_CLIENT_ID" ] || [ -z "$SPOTIFY_CLIENT_SECRET" ]; then
  if [ -t 0 ]; then
    echo "In your Spotify app's settings, add this Redirect URI: https://$DOMAIN/auth/callback"
    read -rp "Spotify client ID: " SPOTIFY_CLIENT_ID
    read -rsp "Spotify client secret (hidden): " SPOTIFY_CLIENT_SECRET; echo
  else
    echo "SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET are missing. Run this again in a terminal to enter them," >&2
    echo "or add them to $ENV_FILE." >&2
  fi
fi

# Keep settings added by hand when this runs again
KEEP=$(grep -sv -e '^DATABASE_URL=' -e '^ENCRYPTION_KEY=' -e '^SESSION_SECRET=' -e '^SPOTIFY_' \
  -e '^ENVIRONMENT=' -e '^CORS_ORIGINS=' "$ENV_FILE" || true)
umask 027
cat > "$ENV_FILE" <<EOF
ENVIRONMENT=production
DATABASE_URL=postgresql://jamr:$DB_PASSWORD@localhost:5432/jamr_io
ENCRYPTION_KEY=$ENCRYPTION_KEY
SESSION_SECRET=$SESSION_SECRET
SPOTIFY_CLIENT_ID=$SPOTIFY_CLIENT_ID
SPOTIFY_CLIENT_SECRET=$SPOTIFY_CLIENT_SECRET
SPOTIFY_REDIRECT_URI=https://$DOMAIN/auth/callback
CORS_ORIGINS=https://$DOMAIN
EOF
if [ -n "$KEEP" ]; then printf '%s\n' "$KEEP" >> "$ENV_FILE"; fi
umask 022
# Secrets: readable by root and the app user only
chown "root:$APP_USER" "$ENV_FILE"
chmod 640 "$ENV_FILE"

step "Install and migrate"
sudo -u "$APP_USER" -H bash -c "set -a; . $ENV_FILE; set +a; bash $APP_DIR/deploy/build.sh"

step "Services"
install -m 0644 "$APP_DIR/deploy/jamr.service" /etc/systemd/system/
sed "s|{\$SITE}|$DOMAIN|" "$APP_DIR/deploy/Caddyfile" > /etc/caddy/Caddyfile
install -m 0755 "$APP_DIR/deploy/backup.sh" /etc/cron.daily/jamr-backup

if [ "${JAMR_NO_SYSTEMD:-0}" = 1 ]; then
  echo "JAMR_NO_SYSTEMD=1: skipping firewall and service start (testing only)"
else
  step "Firewall: only SSH, HTTP and HTTPS"
  ufw allow OpenSSH >/dev/null
  ufw allow 80/tcp >/dev/null
  ufw allow 443/tcp >/dev/null
  ufw --force enable >/dev/null

  systemctl daemon-reload
  systemctl enable --now jamr
  systemctl restart jamr caddy
fi

echo
echo "Done. jamr.io is at: https://$DOMAIN"
echo
echo "Next:"
echo "  1. In the Spotify developer dashboard, make sure the Redirect URI https://$DOMAIN/auth/callback"
echo "     is added, and everyone who'll log in is under User Management."
echo "  2. Log in on the site once, then make yourself the Overseer:"
echo "       sudo bash $APP_DIR/deploy/run.sh create_overseer.py <your-spotify-display-name>"
