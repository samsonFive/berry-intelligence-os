"""Persist corpus-discovered Variety candidates into the inbox universe.

Never writes data/entities. GET of any page does not run this script.
Identity is resolved but never auto-confirmed.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.composition import get_repositories
from app.runtime_config import resolve_data_dir, resolve_inbox_dir
from app.services.variety_universe.candidates import load_variety_candidates, persist_variety_candidates
from app.services.variety_universe.corpus_discovery import build_discovered_candidates


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inbox", type=Path, default=None)
    parser.add_argument("--data-dir", type=Path, default=None)
    args = parser.parse_args()
    data_dir = args.data_dir or resolve_data_dir(ROOT)
    inbox_dir = args.inbox or resolve_inbox_dir(ROOT)
    repos = get_repositories(data_dir, ROOT / "schemas")
    entities = repos.entities.list()
    varieties = [entity for entity in entities if entity.get("entity_type") == "variety"]
    evidence = [row for row in repos.evidence.list() if row.get("status") == "published"]
    facts = repos.facts.list()
    existing = load_variety_candidates(inbox_dir)
    report = build_discovered_candidates(
        varieties=varieties,
        entities=entities,
        published_evidence=evidence,
        facts=facts,
        existing_candidates=existing,
    )
    written = persist_variety_candidates(report["candidates"], inbox_dir=inbox_dir)
    print(
        "variety-corpus discovery: "
        f"mentions={report['mention_count']} "
        f"already_canonical={len(report['already_canonical'])} "
        f"already_candidate={len(report['already_candidate'])} "
        f"new_candidates={len(report['candidates'])} "
        f"written={len(written)} "
        f"possible_alias={len(report['possible_aliases'])} "
        f"unresolved={len(report['unresolved'])} "
        f"exclusions={len(report['exclusions'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
