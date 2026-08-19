"""Additive sync of the full trusted data/ tree into a deployed runtime.

Real gap found while validating the Intelligence Acquisition mission's
Phase B company-coverage map (2026-08-19): comparing canonical data/ to
the VPS's demo-runtime/data/ showed the runtime was missing exactly the
two entity records added in canonical's most recent commit before this
mission started (company-sanlucar.json, company-ushbc.json) -- the same
seed-runs-once staleness bug that scripts/sync_source_config.py already
fixes for data/configuration/sources.json, just for the rest of data/
too. docker-entrypoint.sh's seed step only ever populates an empty
volume, so any file added to canonical after a runtime's first deploy
never reaches it without an explicit resync mechanism.

This module is deliberately additive-only, file-level: a file already
present at the runtime path is never touched, so any record an operator
has published live on that runtime (review/publish writes directly into
data/) is always preserved untouched. Only a file that exists in the
seed bundle but is missing from the runtime gets copied over.

data/configuration/sources.json is handled separately by
sync_source_config.sync_source_config(), which merges individual source
ids within that one shared array file rather than copying the whole
file -- every other file under data/ is a one-record-per-file JSON
document, so file-level additive copy is the correct granularity there.
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path
from typing import Any

from scripts.sync_source_config import sync_source_config

SOURCES_RELATIVE_PATH = Path("configuration") / "sources.json"


def sync_trusted_data(seed_data_dir: Path, runtime_data_dir: Path) -> dict[str, Any]:
    """Additively sync every file under seed_data_dir into runtime_data_dir.

    Returns a summary with the sources.json merge result plus the list of
    other files newly copied in (paths relative to the data/ root).
    """
    if not seed_data_dir.is_dir():
        return {"skipped_missing_seed": True, "sources": None, "files_added": []}

    sources_result = sync_source_config(
        seed_data_dir / SOURCES_RELATIVE_PATH, runtime_data_dir / SOURCES_RELATIVE_PATH
    )

    files_added: list[str] = []
    for seed_file in seed_data_dir.rglob("*"):
        if not seed_file.is_file():
            continue
        relative = seed_file.relative_to(seed_data_dir)
        if relative == SOURCES_RELATIVE_PATH:
            continue
        runtime_file = runtime_data_dir / relative
        if runtime_file.exists():
            continue
        runtime_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(seed_file, runtime_file)
        files_added.append(str(relative).replace("\\", "/"))

    return {
        "skipped_missing_seed": False,
        "sources": sources_result,
        "files_added": sorted(files_added),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", required=True, type=Path, help="Image/canonical seed data/ directory")
    parser.add_argument("--runtime", required=True, type=Path, help="Deployed runtime's data/ directory")
    args = parser.parse_args(argv)
    result = sync_trusted_data(args.seed, args.runtime)
    if result["skipped_missing_seed"]:
        print(f"No seed data directory at {args.seed}; nothing to sync.")
        return 0
    sources = result["sources"] or {}
    if sources.get("added"):
        print(f"sources.json: added {len(sources['added'])} source(s): {', '.join(sources['added'])}")
    else:
        print("sources.json: already up to date.")
    if result["files_added"]:
        print(f"Added {len(result['files_added'])} other trusted data file(s):")
        for path in result["files_added"]:
            print(f"  - {path}")
    else:
        print("No other trusted data files needed syncing.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
