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

if [ "$(id -u)" = "0" ]; then
    chown -R berry:berry "$RUNTIME_DIR" || true
    exec gosu berry "$@"
fi

exec "$@"
