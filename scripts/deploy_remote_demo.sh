#!/usr/bin/env bash
# Shortest operator path for a Linux VPS with Docker.
# Usage:
#   scripts/deploy_remote_demo.sh export
#   scripts/deploy_remote_demo.sh up
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

cmd="${1:-help}"

case "$cmd" in
  export)
    mkdir -p demo-runtime
    python scripts/export_demo_runtime.py --output demo-runtime
    echo "Exported to $ROOT/demo-runtime (gitignored). Copy this folder to the server."
    ;;
  up)
    if [ ! -f deploy/.env ]; then
      echo "Create deploy/.env from deploy/.env.example first." >&2
      exit 1
    fi
    # shellcheck disable=SC1091
    set -a
    . deploy/.env
    set +a
    if [ "${BIOS_REVIEW_USERNAME:-}" = "replace-me" ] || [ -z "${BIOS_REVIEW_PASSWORD:-}" ] || [ "${BIOS_REVIEW_PASSWORD:-}" = "replace-me-with-a-long-random-value" ]; then
      echo "Set real BIOS_REVIEW_USERNAME and BIOS_REVIEW_PASSWORD in deploy/.env" >&2
      exit 1
    fi
    if [ -z "${BIOS_SESSION_SECRET:-}" ] || [ "${BIOS_SESSION_SECRET:-}" = "replace-me-with-openssl-rand-hex-32" ]; then
      echo "Set a real BIOS_SESSION_SECRET in deploy/.env (openssl rand -hex 32). Do not reuse the review password." >&2
      exit 1
    fi
    docker compose --env-file deploy/.env -f deploy/docker-compose.yml --profile tls up -d --build
    echo "App is loopback-only (${BIOS_APP_BIND:-127.0.0.1}:${BIOS_APP_PORT:-8000}). Public HTTPS is Caddy on 80/443."
    ;;
  down)
    docker compose --env-file deploy/.env -f deploy/docker-compose.yml --profile tls down
    ;;
  *)
    cat <<'EOF'
Remote interactive demo

1. python scripts/export_demo_runtime.py --output demo-runtime
2. Copy the repo plus demo-runtime/ to the VPS
3. cp deploy/.env.example deploy/.env && edit credentials, BIOS_SESSION_SECRET, and BIOS_DEMO_SITE
4. docker compose --env-file deploy/.env -f deploy/docker-compose.yml --profile tls up -d --build
5. Point DNS A record at the VPS before enabling TLS
6. Open https://<BIOS_DEMO_SITE>/login
The app container is published on 127.0.0.1 only. Do not map host 8000 to 0.0.0.0.
EOF
    ;;
esac
