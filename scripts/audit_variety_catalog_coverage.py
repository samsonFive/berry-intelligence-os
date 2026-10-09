"""Repeatable catalog reconciliation; no canonical or workflow-state writes.

Run with --output <report.json>. --inbox-dir additionally checks known,
already-captured articles and requires a private inbox output destination.
Does not acquire sources, approve identities or claim internet completeness.
"""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.services.variety_universe.corpus_discovery import build_discovered_candidates


def audit(data_dir, *, inbox_dir=None):
    def records(folder):
        return [json.loads(path.read_text(encoding="utf-8")) for path in sorted((data_dir / folder).rglob("*.json"))]
    entities, evidence, facts = records("entities"), records("evidence"), records("facts")
    varieties = [row for row in entities if row.get("entity_type") == "variety"]
    evidence = [row for row in evidence if row.get("status") == "published"]
    article_sources, article_counts = [], None
    if inbox_dir is not None:
        from app.services.variety_universe.article_sources import available_article_sources
        article_sources, article_counts = available_article_sources(evidence, inbox_dir)
    report = build_discovered_candidates(varieties=varieties, entities=entities, published_evidence=evidence,
        facts=facts, source_text_records=article_sources)
    source_rows = []
    sources = {row["id"]: row for row in [*article_sources, *evidence]}
    for source in sources.values():
        mentions = [row for row in report["mentions"] if source["id"] in row["evidence_ids"]]
        if mentions:
            source_rows.append({"id": source["id"], "title": source.get("title"), "url": source.get("source_url"),
                "captured_date": source.get("captured_date"), "names": [{"name": row["candidate_name"],
                "berry_id": row["berry_id"], "catalog_id": row.get("canonical_variety_id"),
                "disposition": row["disposition"], "selection_code": row.get("breeder_code"),
                **({"named_in_article": any(ref["evidence_id"] == source["id"]
                    for ref in row.get("article_text_sources") or [])} if inbox_dir is not None else {})} for row in mentions],
                **({"publication_reviewed": source.get("status") == "published"} if inbox_dir is not None else {})})
    return {"scope": ("Private: published summaries and known captured article text; before private identity decisions; not internet completeness"
                      if inbox_dir is not None else "Published stored sources only; exact identity strings, explicit declarations; not internet completeness"),
            **({"article_sources": article_counts} if article_counts is not None else {}),
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
    parser.add_argument("--inbox-dir", type=Path, help="Opt in to private captured article inputs; never fetches")
    args = parser.parse_args()
    output = args.output.resolve()
    if args.inbox_dir is not None and (any(output.is_relative_to((ROOT / folder).resolve())
            for folder in ("generated", "data", "artifacts")) or not any(output.is_relative_to(folder.resolve())
            for folder in (args.inbox_dir, ROOT / "inbox"))):
        parser.error("Captured-article reports must stay under the selected inbox or repository inbox.")
    result = audit(args.data_dir, inbox_dir=args.inbox_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in result.items() if key not in {"sources", "exclusions"}}))
