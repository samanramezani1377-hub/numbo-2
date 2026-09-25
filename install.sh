#!/usr/bin/env bash
set -euo pipefail

SRC_DIR="$(cd "$(dirname "$0")" && pwd)"
INSTALL_DIR="${NUMBO_DIR:-/opt/numbo}"
PORT="${NUMBO_PORT:-8080}"

echo "=== Numbo-2 install ==="

if ! command -v python3 >/dev/null 2>&1; then
  echo "Installing python3..."
  if command -v apt-get >/dev/null 2>&1; then
    apt-get update -y
    DEBIAN_FRONTEND=noninteractive apt-get install -y python3 python3-venv python3-pip unzip rsync
  elif command -v yum >/dev/null 2>&1; then
    yum install -y python3 python3-pip unzip rsync
  else
    echo "Please install python3 first."
    exit 1
  fi
fi

if [ "$(id -u)" -eq 0 ]; then
  mkdir -p "$INSTALL_DIR"
  if [ "$SRC_DIR" != "$INSTALL_DIR" ]; then
    if command -v rsync >/dev/null 2>&1; then
      rsync -a --exclude venv --exclude data --exclude .git "$SRC_DIR"/ "$INSTALL_DIR"/
    else
      cp -a "$SRC_DIR"/. "$INSTALL_DIR"/
    fi
  fi
  APP="$INSTALL_DIR"
else
  APP="$SRC_DIR"
  echo "No root: installing in $APP"
fi

cd "$APP"
chmod +x install.sh start_ui.py run.py export.py 2>/dev/null || true

python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

mkdir -p data

if [ ! -f .env ]; then
  PASS="${NUMBO_PANEL_PASSWORD:-$(python3 -c 'import secrets; print(secrets.token_urlsafe(10))')}"
  SECRET="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
  cat > .env <<EOF
NUMBO_PANEL_PASSWORD=$PASS
NUMBO_SECRET=$SECRET
NUMBO_PORT=$PORT
EOF
  python3 - "$PORT" "$PASS" "$SECRET" <<'PY'
import json, sys
from pathlib import Path
port, password, secret = sys.argv[1], sys.argv[2], sys.argv[3]
p = Path("config.json")
data = {}
if p.exists():
    try:
        data = json.loads(p.read_text())
    except Exception:
        data = {}
data["panel_port"] = int(port)
data["panel_password"] = password
data["secret"] = secret
data.setdefault("allowed_tlds", [".ir"])
data.setdefault("cycle_delay", 300)
p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
PY
  echo "$PASS" > data/panel-password.txt
  chmod 600 data/panel-password.txt .env
else
  PASS=$(grep NUMBO_PANEL_PASSWORD .env | cut -d= -f2-)
fi

HOST_IP=$(hostname -I 2>/dev/null | awk '{print $1}')
HOST_IP=${HOST_IP:-YOUR_SERVER_IP}

if [ "$(id -u)" -eq 0 ] && command -v systemctl >/dev/null 2>&1; then
  cat > /etc/systemd/system/numbo.service <<EOF
[Unit]
Description=Numbo-2 Web Panel
After=network.target

[Service]
Type=simple
WorkingDirectory=$APP
EnvironmentFile=$APP/.env
ExecStart=$APP/venv/bin/python $APP/start_ui.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
  systemctl daemon-reload
  systemctl enable --now numbo.service
  echo
  echo "Installed."
  echo "Panel:    http://$HOST_IP:$PORT"
  echo "Password: $PASS"
  echo "Do everything from the web panel."
else
  echo
  echo "Start panel:"
  echo "  cd $APP && source venv/bin/activate && python start_ui.py"
  echo "Panel:    http://$HOST_IP:$PORT"
  echo "Password: $PASS"
fi
