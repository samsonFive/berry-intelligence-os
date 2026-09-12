"""Read-only inventory of configured Source execution capability and history."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.composition import get_repositories
from app.repositories.paths import SCHEMAS_DIR
from app.runtime_config import resolve_data_dir, resolve_inbox_dir
from app.services.media_discovery import read_source_discovery_state
from app.services.monitor_workspace import retry_hints_by_source
from app.services.source_freshness import aggregate_source_execution, source_execution_status


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path)
    parser.add_argument("--inbox-dir", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    data_dir = args.data_dir or resolve_data_dir(ROOT)
    inbox_dir = args.inbox_dir or resolve_inbox_dir(ROOT)
    sources = get_repositories(data_dir, SCHEMAS_DIR).sources.list()
    retries = retry_hints_by_source(inbox_dir)
    rows = []
    for source in sorted(sources, key=lambda row: str(row.get("id") or "")):
        source_id = str(source.get("id") or "")
        if not source_id:
            continue
        status = source_execution_status(
            source,
            discovery_state=read_source_discovery_state(inbox_dir, source_id),
            retry_hint=retries.get(source_id),
        )
        rows.append({"source_id": source_id, "label": source.get("label") or source_id, **status})
    payload = {
        "scope": "Configured Sources plus local per-source discovery state; no network calls or writes.",
        "counts": aggregate_source_execution({row["source_id"]: row for row in rows}),
        "sources": rows,
    }
    rendered = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
