#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")"/.. && pwd)"
cd "$PROJECT_DIR"

if [ -d .venv ]; then
  source .venv/bin/activate || true
fi

export FLASK_ENV=development
export FLASK_DEBUG=1

python app.py --port "${PORT:-5050}"


