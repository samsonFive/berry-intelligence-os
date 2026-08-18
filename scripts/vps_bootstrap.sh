#!/usr/bin/env bash
# Install the authenticated remote-interactive demo on a Linux VPS.
# Run on the VPS as root (or a user that can run docker).
#
#   curl -fsSL https://raw.githubusercontent.com/samsonFive/berry-intelligence-os/<ref>/scripts/vps_bootstrap.sh | sudo bash
#   # or, from a clone:
#   sudo BIOS_GIT_REF=<sha> ./scripts/vps_bootstrap.sh
set -euo pipefail

SITE="${BIOS_DEMO_SITE:-intel.johnnyaceii.com}"
REF="${BIOS_GIT_REF:-cursor/remote-interactive-demo-bd27}"
ROOT="${BIOS_INSTALL_DIR:-/opt/berry-intelligence-os}"
USER_NAME="${BIOS_REVIEW_USERNAME:-johnny}"
REPO_URL="${BIOS_REPO_URL:-https://github.com/samsonFive/berry-intelligence-os.git}"

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker Engine is required." >&2
  exit 1
fi
if ! docker compose version >/dev/null 2>&1; then
  echo "Docker Compose plugin is required." >&2
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive
if command -v apt-get >/dev/null 2>&1; then
  apt-get update -qq
  apt-get install -y -qq git ca-certificates openssl curl
fi

mkdir -p "$ROOT"
if [ ! -d "$ROOT/.git" ]; then
  git clone "$REPO_URL" "$ROOT"
fi
cd "$ROOT"
git fetch --all --tags --prune
if git rev-parse --verify "origin/$REF" >/dev/null 2>&1; then
  git checkout -B "$REF" "origin/$REF"
else
  git checkout --detach "$REF"
fi

mkdir -p demo-runtime/inbox/evidence demo-runtime/inbox/discovered_media
if [ ! -e demo-runtime/data/.seeded-from-repo ] && [ -d data ]; then
  rm -rf demo-runtime/data
  cp -a data demo-runtime/data
  touch demo-runtime/data/.seeded-from-repo
fi

ENV_FILE=deploy/.env
if [ ! -f "$ENV_FILE" ]; then
  PASS="$(openssl rand -hex 24)"
  SESSION_SECRET="$(openssl rand -hex 32)"
  umask 077
  cat > "$ENV_FILE" <<EOF
BIOS_REVIEW_USERNAME=$USER_NAME
BIOS_REVIEW_PASSWORD=$PASS
BIOS_SESSION_SECRET=$SESSION_SECRET
BIOS_DEMO_SITE=$SITE
BIOS_DEMO_RUNTIME=../demo-runtime
BIOS_APP_BIND=127.0.0.1
BIOS_APP_PORT=8000
BIOS_HTTP_PORT=80
BIOS_HTTPS_PORT=443
EOF
  echo "Wrote $ENV_FILE. Username is $USER_NAME. Secrets are not printed; read the username with: sudo grep BIOS_REVIEW_USERNAME $ROOT/$ENV_FILE"
else
  echo "Keeping existing $ENV_FILE"
  if ! grep -q '^BIOS_SESSION_SECRET=' "$ENV_FILE"; then
    umask 077
    printf '\nBIOS_SESSION_SECRET=%s\n' "$(openssl rand -hex 32)" >> "$ENV_FILE"
    echo "Added BIOS_SESSION_SECRET to $ENV_FILE (value not printed)"
  fi
fi

docker compose --env-file deploy/.env -f deploy/docker-compose.yml --profile tls up -d --build

echo "Waiting for loopback healthz..."
ok=0
for _ in $(seq 1 40); do
  if curl -fsS http://127.0.0.1:8000/healthz >/dev/null 2>&1; then
    ok=1
    break
  fi
  sleep 3
done
if [ "$ok" -ne 1 ]; then
  echo "App did not become healthy on 127.0.0.1:8000. Check: docker compose -f deploy/docker-compose.yml --profile tls ps" >&2
  docker compose --env-file deploy/.env -f deploy/docker-compose.yml --profile tls ps >&2 || true
  exit 1
fi

echo "Loopback healthz OK. Public URL: https://$SITE/login"
echo "App port 8000 is bound to 127.0.0.1 only."
