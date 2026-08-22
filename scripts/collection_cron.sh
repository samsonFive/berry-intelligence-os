#!/usr/bin/env bash
# Recurring collection entry point for a scheduled (systemd timer / cron)
# invocation against the deployed remote-demo container. Wraps the existing
# scripts/run_collection.py --all through docker compose exec -- no second
# acquisition architecture, no new mechanism inside the app itself.
#
# Bounded and safe to schedule frequently:
#   - --skip-transcription: never launches Whisper on the VPS; spoken-media
#     items are discovered (cheap RSS/Atom) but stay "transcript needed"
#     until an operator explicitly runs transcription elsewhere.
#   - CollectionRunner's own file lock (inbox/operations/collection.lock)
#     makes an overlapping invocation a fast, safe no-op rather than two
#     concurrent runs; systemd's own oneshot semantics add a second layer
#     of protection against overlap at the scheduler level.
#   - Per-source discovery failure isolation and the bounded initial-
#     discovery backlog policy (app/services/media_discovery.py) are
#     unchanged from the interactive path -- this script adds no new
#     resource-bounding logic of its own, it only invokes the existing one.
#
# Usage (from the repo root on the VPS, e.g. /opt/berry-intelligence-os):
#   ./scripts/collection_cron.sh
#
# Environment:
#   BIOS_COLLECTION_LOG_DIR   Where to write timestamped run logs (default: deployed demo-runtime/inbox/operations/cron-logs)
#   BIOS_COLLECTION_EXTRA_ARGS  Extra args appended to run_collection.py (e.g. --allow-historical-backfill for a one-time deliberate backfill)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# Logs are mutable collection provenance and must survive a worktree replacement.
# The default matches docker-compose's default host-side bind mount.
LOG_DIR="${BIOS_COLLECTION_LOG_DIR:-$ROOT/demo-runtime/inbox/operations/cron-logs}"
mkdir -p "$LOG_DIR"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
LOG_FILE="$LOG_DIR/collection-$STAMP.json"

# shellcheck disable=SC2086
if docker compose --env-file deploy/.env -f deploy/docker-compose.yml exec -T app \
    python scripts/run_collection.py --all --skip-transcription --json ${BIOS_COLLECTION_EXTRA_ARGS:-} \
    > "$LOG_FILE" 2> "$LOG_FILE.stderr"; then
  echo "Collection run complete: $LOG_FILE"
  exit 0
else
  status=$?
  echo "Collection run failed (exit $status); see $LOG_FILE and $LOG_FILE.stderr" >&2
  exit "$status"
fi
