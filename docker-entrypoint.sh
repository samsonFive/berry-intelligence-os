#!/bin/sh
set -eu

RUNTIME_DIR="${BIOS_RUNTIME_DIR:-/app/runtime}"
DATA_DIR="${BIOS_DATA_DIR:-$RUNTIME_DIR/data}"
INBOX_DIR="${BIOS_INBOX_DIR:-$RUNTIME_DIR/inbox}"

mkdir -p "$DATA_DIR" "$INBOX_DIR/evidence" "$INBOX_DIR/discovered_media"

# Seed trusted published data into an empty volume. Never seed inbox: that
# must come from `scripts/export_demo_runtime.py` (or stay empty).
if [ ! -e "$DATA_DIR/.seeded" ] && [ -d /app/seed/data ]; then
    if [ -z "$(ls -A "$DATA_DIR" 2>/dev/null || true)" ]; then
        cp -a /app/seed/data/. "$DATA_DIR/"
    fi
    touch "$DATA_DIR/.seeded"
fi

# Every start (not just the first): additively sync all of TRUSTED DATA
# CONFIGURATION (data/) from the deployed image, so anything added to
# canonical after a runtime's first seed -- new sources, new entity
# records, etc. -- actually reaches it. The first-seed-only rule above
# intentionally never runs again, and nothing else used to keep data/
# current. File-level additive only: a file (or, for sources.json, a
# source id) already present at the runtime path is never touched, so
# any record an operator has published live on this runtime is always
# preserved. Never touches RUNTIME DISCOVERY STATE
# (inbox/discovered_media/_state/*.json), which stays environment-local.
# Non-fatal: a sync problem must never block app startup.
if [ -d /app/seed/data ]; then
    python3 /app/scripts/sync_trusted_data.py \
        --seed /app/seed/data \
        --runtime "$DATA_DIR" \
        || echo "warning: trusted data sync failed; continuing with existing runtime data" >&2
fi

if [ "$(id -u)" = "0" ]; then
    chown -R berry:berry "$RUNTIME_DIR" || true
    exec gosu berry "$@"
fi

exec "$@"
