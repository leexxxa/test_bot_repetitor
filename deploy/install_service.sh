#!/usr/bin/env bash
set -e
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PY=python3
if ! command -v "$PY" >/dev/null 2>&1; then
  echo "python3 not found"
  exit 1
fi
VENV="$PROJECT_DIR/.venv"
if [ ! -d "$VENV" ]; then
  "$PY" -m venv "$VENV"
fi
. "$VENV/bin/activate"
python -m pip install -U pip
pip install -r "$PROJECT_DIR/requirements.txt"
ENV_FILE="$PROJECT_DIR/.env"
if [ ! -f "$ENV_FILE" ]; then
  read -r -p "BOT_TOKEN: " BOT_TOKEN
  read -r -p "ADMIN_ID (digits): " ADMIN_ID
  read -r -p "CHANNEL_USERNAME (e.g. @telergambots): " CHANNEL_USERNAME
  read -r -p "CHANNEL_LINK (e.g. https://t.me/...): " CHANNEL_LINK
  read -r -p "SCHEDULE_DAYS_AHEAD (default 30): " SCHEDULE_DAYS_AHEAD
  [ -z "$SCHEDULE_DAYS_AHEAD" ] && SCHEDULE_DAYS_AHEAD=30
  cat > "$ENV_FILE" <<EOF
BOT_TOKEN=$BOT_TOKEN
ADMIN_ID=$ADMIN_ID
CHANNEL_USERNAME=$CHANNEL_USERNAME
CHANNEL_LINK=$CHANNEL_LINK
SCHEDULE_DAYS_AHEAD=$SCHEDULE_DAYS_AHEAD
EOF
fi
SERVICE_NAME="repetitor_bot.service"
SERVICE_FILE="/etc/systemd/system/$SERVICE_NAME"
sudo bash -c "cat > '$SERVICE_FILE' <<EOF
[Unit]
Description=Repetitor Telegram Bot
After=network.target

[Service]
WorkingDirectory=$PROJECT_DIR
Environment=PYTHONUNBUFFERED=1
ExecStart=$PROJECT_DIR/.venv/bin/python $PROJECT_DIR/bot.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
"
sudo systemctl daemon-reload
sudo systemctl enable --now "$SERVICE_NAME"
sleep 2
sudo systemctl status "$SERVICE_NAME" --no-pager || true
sudo journalctl -u "$SERVICE_NAME" -n 50 --no-pager || true
