"""Report deterministic operational freshness without fetching Sources."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.composition import get_repositories
from app.runtime_config import resolve_data_dir, resolve_inbox_dir
from app.services.freshness_assurance import build_runtime_freshness
from app.services.source_freshness import is_discoverable


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Print the complete body-free machine contract")
    parser.add_argument("--data-dir", type=Path)
    parser.add_argument("--inbox-dir", type=Path)
    parser.add_argument("--schemas-dir", type=Path, default=ROOT / "schemas")
    parser.add_argument("--policy", type=Path)
    parser.add_argument("--history-limit", type=int, default=500, help="Newest collection run summaries to inspect")
    return parser


def _human(payload: dict[str, Any], elapsed: float) -> str:
    counts = payload["counts"]
    lines = [
        "FRESHNESS ASSURANCE",
        f"SYSTEM: {payload['system_state']} ({payload['status_label']})",
        f"CURRENT THROUGH: {payload['current_through'] or 'not established'}",
        f"LAST SUCCESSFUL COLLECTION: {payload['last_successful_collection'] or 'not established'}",
        f"LAST NEW INTELLIGENCE: {payload['last_new_intelligence'] or 'not established'}",
        f"LAST NEW RICH DRAFT: {payload['last_new_rich_draft'] or 'not established'}",
        "",
        "SOURCES",
        f"Scheduled: {counts['scheduled_sources']}",
        f"Current: {counts['current']} (active {counts['current_active']}, quiet {counts['current_quiet']})",
        f"Due: {counts['due']}",
        f"Overdue: {counts['overdue']}",
        f"Retrying: {counts['retrying']}",
        f"Failing: {counts['failing']}",
        f"Blocked: {counts['blocked']}",
        f"Never run: {counts['never_run']}",
        f"Insufficient history: {counts['insufficient_history']}",
        "",
        "BERRY COVERAGE",
    ]
    for berry, summary in payload["berry_coverage"].items():
        lines.append(
            f"{berry}: scheduled {summary['scheduled_sources']}, current {summary['current']}, "
            f"due {summary['due']}, overdue {summary['overdue']}, failing {summary['failing']}, blocked {summary['blocked']}"
        )
    alert_counts: dict[str, int] = {}
    for alert in payload["alerts"]:
        code = str(alert.get("code"))
        alert_counts[code] = alert_counts.get(code, 0) + 1
    lines.extend(("", "ALERT CONDITIONS"))
    if alert_counts:
        lines.extend(f"{code}: {count}" for code, count in sorted(alert_counts.items()))
    else:
        lines.append("None")
    lines.append(f"Computed in {elapsed:.3f}s; read-only/offline.")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    started = time.perf_counter()
    data_dir = args.data_dir or resolve_data_dir(ROOT)
    inbox_dir = args.inbox_dir or resolve_inbox_dir(ROOT)
    policy_path = args.policy or data_dir / "configuration" / "source_collection_cadence.json"
    repositories = get_repositories(data_dir, args.schemas_dir)
    sources = [source for source in repositories.sources.list() if is_discoverable(source)]
    payload = build_runtime_freshness(
        data_dir=data_dir,
        inbox_dir=inbox_dir,
        sources=sources,
        policy_path=policy_path,
        history_limit=args.history_limit,
    )
    elapsed = time.perf_counter() - started
    payload["performance"] = {
        "elapsed_seconds": round(elapsed, 3),
        "history_limit": args.history_limit,
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False) if args.json else _human(payload, elapsed))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
