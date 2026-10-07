"""Export body-free portfolio reconciliation; never writes data or private state."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.services.variety_portfolio_coverage import load_portfolio_observations, portfolio_coverage, source_content_coverage
from app.services.variety_universe.corpus_discovery import build_discovered_candidates, merge_visible_candidates


def audit(data_dir):
    def records(folder):
        return [json.loads(path.read_text(encoding="utf-8")) for path in sorted((data_dir / folder).rglob("*.json"))]
    entities = records("entities")
    varieties = [row for row in entities if row.get("entity_type") == "variety"]
    published = [row for row in records("evidence") if row.get("status") == "published"]
    report = build_discovered_candidates(varieties=varieties, entities=entities,
        published_evidence=published, facts=records("facts"))
    corpus_candidates = merge_visible_candidates([], report["candidates"])
    coverage = portfolio_coverage(data_dir=data_dir, sources=load_portfolio_observations(data_dir), varieties=varieties,
        entities=entities, candidates=corpus_candidates)
    visible = coverage.pop("visible_candidates")
    coverage["source_content"] = source_content_coverage(published)
    coverage["candidate_counts"] = {"stored_source_candidates": len(corpus_candidates), "combined_candidates": len(visible),
                                    "additional_primary_portfolio_candidates": len(visible) - len(corpus_candidates)}
    coverage["subjects"] = [{**row, "sources": [source["id"] for source in row["sources"]]} for row in coverage["subjects"]]
    coverage["scope"] = "Stored primary-page name observations only. No private inbox or human review notes. No global completeness score."
    return coverage


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.data_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"]))
