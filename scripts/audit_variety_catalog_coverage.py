"""Repeatable published-corpus/catalog reconciliation; no writes to data or inbox.

Run with --output <report.json>. Does not acquire sources, approve identities,
or claim completeness against the internet. Only explicit stored names count.
"""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.services.variety_universe.corpus_discovery import build_discovered_candidates


def audit(data_dir):
    def records(folder):
        return [json.loads(path.read_text(encoding="utf-8")) for path in sorted((data_dir / folder).rglob("*.json"))]
    entities, evidence, facts = records("entities"), records("evidence"), records("facts")
    varieties = [row for row in entities if row.get("entity_type") == "variety"]
    evidence = [row for row in evidence if row.get("status") == "published"]
    report = build_discovered_candidates(varieties=varieties, entities=entities, published_evidence=evidence, facts=facts)
    source_rows = []
    for source in evidence:
        mentions = [row for row in report["mentions"] if source["id"] in row["evidence_ids"]]
        if mentions:
            source_rows.append({"id": source["id"], "title": source.get("title"), "url": source.get("source_url"),
                "captured_date": source.get("captured_date"), "names": [{"name": row["candidate_name"],
                "berry_id": row["berry_id"], "catalog_id": row.get("canonical_variety_id"),
                "disposition": row["disposition"], "selection_code": row.get("breeder_code")} for row in mentions]})
    return {"scope": "Published stored sources only; exact identity strings, explicit declarations; not internet completeness",
            "catalog_count": len(varieties), "reviewed_sources_scanned": len(evidence), "source_named_identities": report["mention_count"],
            "catalog_matches": len(report["already_canonical"]), "names_awaiting_review": len(report["candidates"]),
            "per_berry": {berry: {"catalog": sum(berry in row.get("berry_ids", []) for row in varieties),
                "source_named": sum(row.get("berry_id") == berry for row in report["mentions"]),
                "awaiting_review": sum(row.get("berry_id") == berry for row in report["candidates"])}
                for berry in ["berry-blueberry", "berry-strawberry", "berry-raspberry", "berry-blackberry"]},
            "sources": source_rows, "exclusions": report["exclusions"]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.data_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in result.items() if key not in {"sources", "exclusions"}}))
