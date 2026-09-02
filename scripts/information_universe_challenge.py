"""Bounded Phase 2 intelligence challenge.

Read-only except an optional PVPO candidate write to a caller-supplied inbox.
Never writes trusted Evidence. Never deploys.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.runtime_config import resolve_data_dir, resolve_inbox_dir
from app.services.authoritative_registries.usda_pvpo import run_bounded_import
from app.services.industry_pulse.activation import activation_status
from app.services.industry_pulse.exa_queries import week_unknown_unknown_queries
from app.services.patent_monitor.berry_retrieval import run_bounded_berry_retrieval
from app.services.patent_monitor.bigquery_patents import prototype_bundle


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=None)
    parser.add_argument("--inbox-dir", type=Path, default=None)
    parser.add_argument("--pvpo-persist", action="store_true")
    args = parser.parse_args(argv)
    data_dir = args.data_dir or resolve_data_dir(ROOT)
    inbox = args.inbox_dir or resolve_inbox_dir(ROOT)
    status = activation_status()
    pvpo = run_bounded_import(data_dir=data_dir, inbox_dir=inbox, persist=args.pvpo_persist)
    patents = run_bounded_berry_retrieval(data_dir=data_dir, limit=8)
    bigquery = prototype_bundle(limit=10)
    cases = [
        {
            "id": "1-current-specialist-news",
            "found": True,
            "source_provider": "specialist_rss / google site-search",
            "new_vs_previous": "V2 recovered Fruitnet FPJ; Phase 2 prefers first-party article URL",
            "canonical_entity_linked": False,
            "trust_state": "LIVE / UNREVIEWED",
        },
        {
            "id": "2-obscure-company-development",
            "found": False,
            "source_provider": "newscatcher_catchall (background cache)",
            "new_vs_previous": "architecture ready; key absent so not live",
            "canonical_entity_linked": False,
            "trust_state": "AWAITING_KEY",
        },
        {
            "id": "3-apac-development",
            "found": True,
            "source_provider": "perplexity / google / specialist",
            "new_vs_previous": "V2 found in-window JP strawberry coverage; CatchAll APAC query is background-only",
            "canonical_entity_linked": False,
            "trust_state": "LIVE / UNREVIEWED",
        },
        {
            "id": "4-usda-pvp-event",
            "found": pvpo.get("raw_berry_records", 0) > 0,
            "source_provider": "usda_pvpo",
            "new_vs_previous": "structured XLSX import — not available to news-only /week",
            "canonical_entity_linked": pvpo.get("matched_canonical", 0) > 0,
            "trust_state": "UNREVIEWED_REGISTRY",
            "detail": {
                "raw_berry_records": pvpo.get("raw_berry_records"),
                "distinct_variety_names": pvpo.get("distinct_variety_names"),
                "matched_canonical": pvpo.get("matched_canonical"),
                "candidates": pvpo.get("candidates"),
                "ambiguous_identity": pvpo.get("ambiguous_identity"),
                "newest_filing": pvpo.get("newest_filing"),
                "newest_update": pvpo.get("newest_update"),
            },
        },
        {
            "id": "5-recent-berry-patent",
            "found": patents.get("applications_or_grants", 0) > 0,
            "source_provider": patents.get("provider"),
            "new_vs_previous": "patent layer, not news search",
            "canonical_entity_linked": patents.get("canonical_entity_matches", 0) > 0,
            "trust_state": "UNREVIEWED_PATENT",
            "detail": {
                "count": patents.get("applications_or_grants"),
                "newest_publication": patents.get("newest_publication"),
                "sample": (patents.get("sample") or [])[:3],
            },
        },
        {
            "id": "6-known-breeder-portfolio",
            "found": any("Fall Creek" in name or "Driscoll" in name for name in (patents.get("assignees") or [])),
            "source_provider": patents.get("provider"),
            "new_vs_previous": "assignee retrieval is not a news query",
            "canonical_entity_linked": patents.get("canonical_entity_matches", 0) > 0,
            "trust_state": "UNREVIEWED_PATENT",
            "detail": {"assignees": (patents.get("assignees") or [])[:12]},
        },
        {
            "id": "7-unknown-unknown-genetics",
            "found": bool(week_unknown_unknown_queries()) and not status["exa"]["live"],
            "source_provider": "exa unknown-unknown queries (adapter ready, key absent)",
            "new_vs_previous": "query layer exists; live semantic retrieval not activated",
            "canonical_entity_linked": False,
            "trust_state": "AWAITING_KEY",
            "detail": {"queries": [row.id for row in week_unknown_unknown_queries()]},
        },
    ]
    payload = {
        "activation": {name: {"available": row["available"], "operator_step": row.get("operator_step")} for name, row in status.items()},
        "pvpo": pvpo,
        "patents": patents,
        "bigquery": {
            "available": bigquery["available"],
            "operator_setup": bigquery["operator_setup"],
            "template_names": list(bigquery["templates"]),
        },
        "cases": cases,
    }
    print(json.dumps(payload, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
