#!/usr/bin/env bash
set -euo pipefail

# Setup script for Order Matching Engine
# - Creates virtual environment
# - Installs dependencies
# - Starts PostgreSQL via Docker (optional)
# - Runs initial DB migration (create tables)

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")"/.. && pwd)"
cd "$PROJECT_DIR"

python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo "If you don't have Postgres locally, starting a Dockerized instance..."
if ! docker ps >/dev/null 2>&1; then
  echo "Docker not available or not running; skipping Postgres container startup."
else
  docker compose up -d db || docker-compose up -d db || true
fi

# Create tables by importing the Flask app
python - <<'PY'
from app import app
from models import db
with app.app_context():
    db.create_all()
print("Database tables ensured.")
PY

echo "Setup complete. Use scripts/run.sh to start the server."


