"""Additive sync of trusted source configuration into a deployed runtime.

Continuous Intelligence Acquisition mission (2026-08-18): a deployed
runtime's data/configuration/sources.json is seeded exactly once (see
docker-entrypoint.sh's "seed only if the volume is empty, and only if it
has never been seeded before" contract) -- so new sources added to
canonical after that first deploy never reach the running app. This is
the real, confirmed cause of a real production VPS's recurring collector
having zero web_article sources despite three (Fresh Fruit Portal, Fresh
Plaza, Produce Report) being live in canonical for days: nothing ever
re-synced sources.json into the already-seeded runtime volume.

This module is deliberately additive-only, never destructive: a source
id already present in the runtime -- whether from the original seed or
added live via the authoring UI's "Add source" form -- is never modified
or removed, even if the seed bundle's copy of that same id differs. Only
source ids present in the seed bundle (deployed with the code) but
missing from the runtime get appended.

This is the mechanism that keeps TRUSTED SOURCE CONFIGURATION (this
file) in sync with what canonical ships on every deploy, while RUNTIME
DISCOVERY STATE (inbox/discovered_media/_state/*.json -- last_checked_at,
last_success_at, per-run history) remains untouched, environment-local,
and is never written by this script or read from the seed bundle at all.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def sync_source_config(seed_path: Path, runtime_path: Path) -> dict[str, Any]:
    """Append seed-only source ids into the runtime's source registry.
    Never modifies or removes an id already present at runtime_path."""
    if not seed_path.is_file():
        return {"added": [], "skipped_missing_seed": True}
    seed_sources = json.loads(seed_path.read_text(encoding="utf-8"))
    if not isinstance(seed_sources, list):
        raise ValueError(f"seed source config must be a JSON array: {seed_path}")

    if runtime_path.is_file():
        runtime_sources = json.loads(runtime_path.read_text(encoding="utf-8"))
        if not isinstance(runtime_sources, list):
            raise ValueError(f"runtime source config must be a JSON array: {runtime_path}")
    else:
        runtime_sources = []

    existing_ids = {source.get("id") for source in runtime_sources if isinstance(source, dict)}
    added: list[str] = []
    for source in seed_sources:
        if not isinstance(source, dict):
            continue
        source_id = source.get("id")
        if not source_id or source_id in existing_ids:
            continue
        runtime_sources.append(source)
        existing_ids.add(source_id)
        added.append(source_id)

    if added:
        runtime_path.parent.mkdir(parents=True, exist_ok=True)
        runtime_path.write_text(
            json.dumps(runtime_sources, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )

    return {"added": added, "skipped_missing_seed": False}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", required=True, type=Path, help="Image/canonical seed sources.json")
    parser.add_argument("--runtime", required=True, type=Path, help="Deployed runtime's sources.json")
    args = parser.parse_args(argv)
    result = sync_source_config(args.seed, args.runtime)
    if result["skipped_missing_seed"]:
        print(f"No seed source config at {args.seed}; nothing to sync.")
    elif result["added"]:
        print(f"Added {len(result['added'])} new source(s): {', '.join(result['added'])}")
    else:
        print("Runtime source configuration already up to date.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
