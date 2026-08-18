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
    docker compose --env-file deploy/.env -f deploy/docker-compose.yml up -d --build
    echo "App is on port ${BIOS_APP_PORT:-8000}. Optional TLS: docker compose --env-file deploy/.env -f deploy/docker-compose.yml --profile tls up -d"
    ;;
  down)
    docker compose --env-file deploy/.env -f deploy/docker-compose.yml --profile tls down
    ;;
  *)
    cat <<'EOF'
Remote interactive demo

1. python scripts/export_demo_runtime.py --output demo-runtime
2. Copy the repo plus demo-runtime/ to the VPS
3. cp deploy/.env.example deploy/.env && edit credentials and BIOS_DEMO_SITE
4. docker compose --env-file deploy/.env -f deploy/docker-compose.yml up -d --build
5. Point DNS A record for review.example.com at the VPS
6. docker compose --env-file deploy/.env -f deploy/docker-compose.yml --profile tls up -d
EOF
    ;;
esac
