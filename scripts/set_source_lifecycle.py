"""Plan or explicitly apply one Source lifecycle transition.

This updates only the selected Source record inside ``sources.json``. It never
deletes the Source, touches discovery history/inbox, or mutates Evidence. The
default is a read-only plan; ``--apply`` is required to write runtime config.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.composition import get_repositories  # noqa: E402
from app.repositories.paths import SCHEMAS_DIR  # noqa: E402
from app.runtime_config import resolve_data_dir  # noqa: E402
from app.services.source_lifecycle import KNOWN_STATES, lifecycle_state, with_lifecycle  # noqa: E402


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, help="Existing Source id")
    parser.add_argument("--state", required=True, choices=sorted(KNOWN_STATES))
    parser.add_argument("--reason", required=True)
    parser.add_argument("--changed-at", help="Timezone-aware ISO-8601 timestamp; defaults to current UTC")
    parser.add_argument("--replacement-source", help="Optional existing replacement Source id")
    parser.add_argument("--source-url", help="Optional verified canonical publisher page URL")
    parser.add_argument("--apply", action="store_true", help="Persist the planned transition")
    parser.add_argument("--data-dir", type=Path)
    parser.add_argument("--schemas-dir", type=Path, default=SCHEMAS_DIR)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    data_dir = args.data_dir or resolve_data_dir(ROOT)
    repositories = get_repositories(data_dir, args.schemas_dir)
    source = repositories.sources.get(args.source)
    if source is None:
        raise SystemExit(f"unknown Source: {args.source}")
    if args.replacement_source and repositories.sources.get(args.replacement_source) is None:
        raise SystemExit(f"unknown replacement Source: {args.replacement_source}")
    changed_at = args.changed_at or datetime.now(timezone.utc).isoformat(timespec="seconds")
    updated = with_lifecycle(
        source,
        state=args.state,
        reason=args.reason,
        changed_at=changed_at,
        replacement_source_id=args.replacement_source,
    )
    if args.source_url:
        updated["url"] = args.source_url.strip()
    if args.apply:
        repositories.sources.update(args.source, updated)
    print(json.dumps({
        "source_id": args.source,
        "mode": "applied" if args.apply else "dry-run",
        "before_state": lifecycle_state(source),
        "after": updated["lifecycle"],
        "source_url": updated.get("url"),
        "source_id_preserved": updated.get("id") == source.get("id"),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
