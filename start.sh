#!/usr/bin/env bash
set -euo pipefail

# source venv/bin/a#ctivate

BASE_PATH="${BASE_PATH:-}"
if [ -n "${BASE_PATH}" ]; then
  python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload --root-path "${BASE_PATH}"
else
  python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload
fi
