"""scripts/monitor_plant_patents.py's CLI default resolution for
--watchlist/--data-dir/--inbox-dir.

Real bug caught running the deployed VPS container for the first time
(not caught by any unit test, since every existing test passes explicit
paths): --watchlist defaulted to ROOT / "data" / "configuration" /
patent_watchlist.json, where ROOT is the code checkout (/app in the
container) -- but /app/data/... never exists there, only
/app/seed/data/... (the image's build-time copy) and the real runtime
data dir (kept in sync by scripts/sync_trusted_data.py). This is the same
class of bug tests/test_run_collection_cli.py already documents for
run_collection.py's data_dir/inbox_dir -- a scheduled/deployed run
"succeeding" while silently writing to (or here, reading from) a path the
running app never sees.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts import monitor_plant_patents


def test_watchlist_data_and_inbox_dir_default_to_none_before_resolution() -> None:
    """The argparse default itself must not be a concrete repo-relative
    path -- that was the bug. main() resolves the real default afterward."""
    args = monitor_plant_patents._parser().parse_args(["--dry-run"])
    assert args.watchlist is None
    assert args.data_dir is None
    assert args.inbox_dir is None


def test_main_resolves_watchlist_under_the_runtime_data_dir_not_the_repo_root(
    monkeypatch, tmp_path: Path
) -> None:
    runtime = tmp_path / "runtime"
    monkeypatch.setenv("BIOS_RUNTIME_DIR", str(runtime))
    monkeypatch.delenv("BIOS_DATA_DIR", raising=False)
    monkeypatch.delenv("BIOS_INBOX_DIR", raising=False)
    monkeypatch.delenv("BIOS_USPTO_ODP_API_KEY", raising=False)

    watchlist_path = runtime / "data" / "configuration" / "patent_watchlist.json"
    watchlist_path.parent.mkdir(parents=True)
    watchlist_path.write_text(
        json.dumps(
            {
                "kind": "berry-intelligence-os-patent-watchlist",
                "provider_preference": ["google_patents_json"],
                "max_candidates_per_run": 5,
                "queries": [],
            }
        ),
        encoding="utf-8",
    )

    # No queries configured -- discover() returns immediately with zero
    # filings, no network call, but still exercises the full path
    # resolution (load_watchlist(args.watchlist) must find the real file).
    exit_code = monitor_plant_patents.main(["--dry-run", "--json"])
    assert exit_code == 0


def test_explicit_watchlist_flag_still_overrides_the_default(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("BIOS_RUNTIME_DIR", str(tmp_path / "runtime"))
    explicit_watchlist = tmp_path / "custom-watchlist.json"
    args = monitor_plant_patents._parser().parse_args(["--watchlist", str(explicit_watchlist)])
    assert args.watchlist == explicit_watchlist
