#!/usr/bin/env python3
"""Derive manifest.json, source-coverage.csv and the QA report body from the package contents.

Everything this script emits is computed from the staged records, so it can be re-run after any
change to the package and will stay in sync. Run from the repository root or anywhere:

    python data/imports/blueberry-public-pilot-<date>/scripts/build_reports.py
"""
from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent
PKG_NAME = PKG.name
TODAY = date.today().isoformat()

TIER_TAGS = ("tier-1", "tier-2", "tier-3")


def load(folder: str) -> list[dict]:
    out = []
    for p in sorted((PKG / folder).rglob("*.json")):
        out.append(json.loads(p.read_text()))
    return out


def sha256_of_tree() -> str:
    h = hashlib.sha256()
    for p in sorted(PKG.rglob("*.json")):
        h.update(p.relative_to(PKG).as_posix().encode())
        h.update(p.read_bytes())
    return h.hexdigest()


def tier_of(ev: dict) -> str:
    for t in ev.get("tags", []):
        if t in TIER_TAGS:
            return t
    return "untagged"


def main() -> None:
    entities = load("entities")
    evidence = load("evidence")
    facts = load("facts")
    rels = load("relationships")
    sqs = load("strategic-questions")

    by_type = Counter(e["entity_type"] for e in entities)
    ev_by_tier = Counter(tier_of(e) for e in evidence)
    ev_by_source_type = Counter(e.get("source_type", "unknown") for e in evidence)
    ev_by_status = Counter(e["status"] for e in evidence)
    f_by_class = Counter(f["classification"] for f in facts)
    f_by_conf = Counter(f["confidence"] for f in facts)
    f_by_status = Counter(f["status"] for f in facts)
    r_by_pred = Counter(r["predicate"] for r in rels)
    r_by_status = Counter(r["status"] for r in rels)

    # ---------------------------------------------------------------- manifest
    manifest = {
        "package": PKG_NAME,
        "berry_scope": ["berry-blueberry"],
        "generated_on": TODAY,
        "generated_by": "research-agent/blueberry-public-pilot-2026-08-03",
        "repo_commit": None,
        "repo_commit_note": (
            "The repository was supplied as a zip archive with no .git directory, so no commit "
            "hash is available. Schema conformance was verified against the schema files present "
            "in that archive."
        ),
        "schemas_validated_against": sorted(
            p.name for p in (PKG.parent.parent.parent / "schemas").glob("*.json")
        ),
        "target_import_root": "data/",
        "write_mode": "additive only; no existing record is modified or deleted",
        "evidence_status_on_import": "in_review",
        "counts": {
            "files_total": len(list(PKG.rglob("*.json"))),
            "entity": len(entities),
            "entity_by_type": dict(sorted(by_type.items())),
            "evidence": len(evidence),
            "evidence_by_tier": dict(sorted(ev_by_tier.items())),
            "evidence_by_status": dict(sorted(ev_by_status.items())),
            "evidence_by_source_type": dict(sorted(ev_by_source_type.items())),
            "fact": len(facts),
            "fact_by_classification": dict(sorted(f_by_class.items())),
            "fact_by_confidence": dict(sorted(f_by_conf.items())),
            "fact_by_status": dict(sorted(f_by_status.items())),
            "relationship": len(rels),
            "relationship_by_predicate": dict(sorted(r_by_pred.items())),
            "relationship_by_status": dict(sorted(r_by_status.items())),
            "strategic_question": len(sqs),
            "distinct_source_urls": len({e.get("source_url") for e in evidence if e.get("source_url")}),
        },
        "content_sha256": sha256_of_tree(),
    }
    (PKG / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")

    # --------------------------------------------------------- source coverage
    ent_name = {e["id"]: e["name"] for e in entities}
    fact_by_ev = defaultdict(int)
    for f in facts:
        for e in f.get("evidence_ids", []):
            fact_by_ev[e] += 1
    rel_by_ev = defaultdict(int)
    for r in rels:
        for e in r.get("evidence_ids", []):
            rel_by_ev[e] += 1

    rows = []
    for e in sorted(evidence, key=lambda x: (tier_of(x), x["id"])):
        ents = e.get("entity_ids", [])
        rows.append(
            {
                "evidence_id": e["id"],
                "tier": tier_of(e),
                "source_name": e.get("source_name", ""),
                "source_type": e.get("source_type", ""),
                "title": e.get("title", ""),
                "source_url": e.get("source_url", ""),
                "published_date": e.get("published_date") or "",
                "captured_date": e.get("captured_date", ""),
                "entity_count": len(ents),
                "entities": "; ".join(ent_name.get(i, i) for i in ents),
                "facts_supported": fact_by_ev.get(e["id"], 0),
                "relationships_supported": rel_by_ev.get(e["id"], 0),
                "strategic_questions": "; ".join(e.get("strategic_question_ids", [])),
            }
        )
    with (PKG / "source-coverage.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    # ------------------------------------------------------------- stats dump
    # Consumed by the QA report so the narrative and the numbers cannot drift apart.
    stats = {
        "entity_by_type": dict(sorted(by_type.items())),
        "evidence_by_tier": dict(sorted(ev_by_tier.items())),
        "evidence_by_source_type": dict(sorted(ev_by_source_type.items())),
        "fact_by_classification": dict(sorted(f_by_class.items())),
        "fact_by_confidence": dict(sorted(f_by_conf.items())),
        "fact_by_status": dict(sorted(f_by_status.items())),
        "relationship_by_predicate": dict(sorted(r_by_pred.items())),
        "relationship_by_status": dict(sorted(r_by_status.items())),
        "totals": {
            "entity": len(entities),
            "evidence": len(evidence),
            "fact": len(facts),
            "relationship": len(rels),
            "strategic_question": len(sqs),
            "files": len(list(PKG.rglob("*.json"))),
        },
        "disputed_facts": [
            {"id": f["id"], "statement": f["statement"]} for f in facts if f["status"] == "disputed"
        ],
        "unverified_entities": [
            {"id": e["id"], "name": e["name"], "type": e["entity_type"]}
            for e in entities
            if e["status"] == "unverified"
        ],
        "geography_entities": sorted(
            e["name"] for e in entities if e["entity_type"] == "geography"
        ),
        "evidence_without_published_date": sorted(
            e["id"] for e in evidence if not e.get("published_date")
        ),
    }
    (PKG / "scripts" / "_stats.json").write_text(json.dumps(stats, indent=2) + "\n")

    print(f"manifest.json        {manifest['counts']['files_total']} json files indexed")
    print(f"source-coverage.csv  {len(rows)} rows")
    print(f"_stats.json          written")


if __name__ == "__main__":
    main()
