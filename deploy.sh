#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/root/ThinkBIG"
SERVICE="thinkbig"

cd "$APP_DIR"

echo "==> git pull"
git pull origin main

echo "==> install requirements"
source "$APP_DIR/venv/bin/activate"
pip install -r requirements.txt

echo "==> restart service"
sudo systemctl restart "$SERVICE"

echo "==> health check"
sleep 2
curl -fsS http://127.0.0.1:8000/docs >/dev/null

echo "✅ deploy done"
