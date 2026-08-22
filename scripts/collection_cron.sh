#!/usr/bin/env bash
# Production collection-operations dispatcher for a scheduled systemd
# invocation against the deployed container. Cadence and runner commands are
# owned by collection_pipelines.json; this remains one scheduler framework.
#
# Bounded and safe to schedule frequently:
#   - The spoken-media registry command carries --skip-transcription, so this
#     dispatcher never launches Whisper implicitly.
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
#   BIOS_COLLECTION_OPERATIONS_ARGS  Optional dispatcher arguments (normally empty)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# Logs are mutable collection provenance and must survive a worktree replacement.
# The default matches docker-compose's default host-side bind mount.
LOG_DIR="${BIOS_COLLECTION_LOG_DIR:-$ROOT/demo-runtime/inbox/operations/cron-logs}"
mkdir -p "$LOG_DIR"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
LOG_FILE="$LOG_DIR/operations-$STAMP.json"

# shellcheck disable=SC2086
if docker compose --env-file deploy/.env -f deploy/docker-compose.yml exec -T --user 1000:1000 app \
    python scripts/run_due_pipelines.py ${BIOS_COLLECTION_OPERATIONS_ARGS:-} \
    > "$LOG_FILE" 2> "$LOG_FILE.stderr"; then
  echo "Collection operations complete: $LOG_FILE"
  exit 0
else
  status=$?
  echo "Collection operations failed (exit $status); see $LOG_FILE and $LOG_FILE.stderr" >&2
  exit "$status"
fi
