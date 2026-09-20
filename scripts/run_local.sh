#!/usr/bin/env bash
# Start Berry OS locally for feed-first Today / thumbs-up publishing.
set -euo pipefail
cd "$(dirname "$0")/.."

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required (3.12+)." >&2
  exit 1
fi

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install -q -r requirements-dev.txt

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

host="${BIOS_APP_BIND:-127.0.0.1}"
port="${BIOS_APP_PORT:-8000}"
echo "Berry OS → http://${host}:${port}/today"
echo "Refresh live lanes on Today if the feed looks stale. Thumbs-up is the publish path."
exec python -m uvicorn app.main:app --reload --host "$host" --port "$port"
