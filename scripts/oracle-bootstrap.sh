#!/usr/bin/env bash
# Run on a fresh Ubuntu 22.04/24.04 Oracle Cloud (or any VPS) VM as ubuntu/root.
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/anuragrawat121/MandiSync/main/scripts/oracle-bootstrap.sh | bash
# Or after cloning:
#   bash scripts/oracle-bootstrap.sh

set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/anuragrawat121/MandiSync.git}"
APP_DIR="${APP_DIR:-$HOME/MandiSync}"

echo "==> Installing Docker…"
if ! command -v docker >/dev/null 2>&1; then
  sudo apt-get update -y
  sudo apt-get install -y ca-certificates curl git
  sudo install -m 0755 -d /etc/apt/keyrings
  sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  sudo chmod a+r /etc/apt/keyrings/docker.asc
  echo \
    "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
    $(. /etc/os-release && echo "${VERSION_CODENAME}") stable" | \
    sudo tee /etc/apt/sources.list.d/docker.list >/dev/null
  sudo apt-get update -y
  sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
  sudo usermod -aG docker "$USER" || true
fi

echo "==> Opening firewall ports 22, 80, 3000, 8000…"
if command -v firewall-cmd >/dev/null 2>&1; then
  sudo firewall-cmd --permanent --add-port=22/tcp || true
  sudo firewall-cmd --permanent --add-port=80/tcp || true
  sudo firewall-cmd --permanent --add-port=3000/tcp || true
  sudo firewall-cmd --permanent --add-port=8000/tcp || true
  sudo firewall-cmd --reload || true
fi
if command -v ufw >/dev/null 2>&1; then
  sudo ufw allow 22/tcp || true
  sudo ufw allow 80/tcp || true
  sudo ufw allow 3000/tcp || true
  sudo ufw allow 8000/tcp || true
fi

echo "==> Cloning MandiSync…"
if [ ! -d "$APP_DIR/.git" ]; then
  git clone "$REPO_URL" "$APP_DIR"
else
  git -C "$APP_DIR" pull --ff-only || true
fi
cd "$APP_DIR"

PUBLIC_IP="$(curl -fsSL https://ifconfig.me || curl -fsSL https://api.ipify.org || hostname -I | awk '{print $1}')"
echo "==> Detected public IP: ${PUBLIC_IP}"

if [ ! -f .env.production ]; then
  cp .env.production.example .env.production
  DB_PASS="$(openssl rand -hex 16)"
  API_KEY="$(openssl rand -hex 24)"
  sed -i "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=${DB_PASS}|" .env.production
  sed -i "s|^API_KEY=.*|API_KEY=${API_KEY}|" .env.production
  sed -i "s|^ALLOWED_ORIGINS=.*|ALLOWED_ORIGINS=http://${PUBLIC_IP}:3000|" .env.production
  sed -i "s|^NEXT_PUBLIC_API_BASE_URL=.*|NEXT_PUBLIC_API_BASE_URL=http://${PUBLIC_IP}:8000|" .env.production
  echo
  echo "Created .env.production"
  echo "  NEXT_PUBLIC_API_BASE_URL=http://${PUBLIC_IP}:8000"
  echo "  ALLOWED_ORIGINS=http://${PUBLIC_IP}:3000"
  echo
  echo "EDIT these two keys before starting:"
  echo "  nano $APP_DIR/.env.production"
  echo "    AGMARKNET_API_KEY=...   (required for live prices)"
  echo "    GEMINI_API_KEY=...      (optional, for voice briefings)"
  echo
  echo "Then run:"
  echo "  cd $APP_DIR"
  echo "  sudo docker compose -f docker-compose.prod.yml --env-file .env.production up -d --build"
  echo
  echo "After it starts:"
  echo "  Farmer UI: http://${PUBLIC_IP}:3000"
  echo "  Admin:     http://${PUBLIC_IP}:3000/admin"
  echo "  API:       http://${PUBLIC_IP}:8000/health"
  exit 0
fi

echo "==> .env.production already exists — starting stack…"
sudo docker compose -f docker-compose.prod.yml --env-file .env.production up -d --build
echo
echo "Farmer UI: http://${PUBLIC_IP}:3000"
echo "Admin:     http://${PUBLIC_IP}:3000/admin"
echo "API:       http://${PUBLIC_IP}:8000/health"
