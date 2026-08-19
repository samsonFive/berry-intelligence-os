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

# Every start (not just the first): additively sync trusted source
# CONFIGURATION (data/configuration/sources.json) from the deployed image,
# so a source added to canonical actually reaches a runtime that was
# already seeded weeks ago -- the first-seed-only rule above intentionally
# never runs again, and nothing else used to keep this file current. Never
# modifies or removes an existing runtime source id (an operator's own
# "Add source" additions are preserved); never touches RUNTIME DISCOVERY
# STATE (inbox/discovered_media/_state/*.json), which stays
# environment-local. Non-fatal: a sync problem must never block app startup.
if [ -f /app/seed/data/configuration/sources.json ]; then
    python3 /app/scripts/sync_source_config.py \
        --seed /app/seed/data/configuration/sources.json \
        --runtime "$DATA_DIR/configuration/sources.json" \
        || echo "warning: source config sync failed; continuing with existing runtime sources" >&2
fi

if [ "$(id -u)" = "0" ]; then
    chown -R berry:berry "$RUNTIME_DIR" || true
    exec gosu berry "$@"
fi

exec "$@"
