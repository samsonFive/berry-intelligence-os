"""Audit a supplied public GDR native CSV, without acquisition or trust writes.

Default output is private. --snapshot-output explicitly saves only literal
Cultivar labels and reference identifiers, never bodies, pedigree or image text.
This is an independent coverage comparison, not a monitor or Source onboarding.
"""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.services.variety_external_coverage import analyze_gdr_csv, compare_baseline
from app.services.variety_portfolio_coverage import load_portfolio_observations, reconcile_portfolios
from app.services.variety_universe.corpus_discovery import build_discovered_candidates


def audit(csv_path, data_dir, checked_on, reported_stocks, query_organisms=None):
    baseline = analyze_gdr_csv(csv_path, checked_on=checked_on, reported_stocks=reported_stocks, query_organisms=query_organisms)
    def records(folder):
        return [json.loads(path.read_text(encoding="utf-8")) for path in sorted((data_dir / folder).rglob("*.json"))]
    entities = records("entities")
    varieties = [row for row in entities if row.get("entity_type") == "variety"]
    corpus = build_discovered_candidates(varieties=varieties, entities=entities,
        published_evidence=[row for row in records("evidence") if row.get("status") == "published"], facts=records("facts"))
    _, candidates = reconcile_portfolios(sources=load_portfolio_observations(data_dir), varieties=varieties,
        entities=entities, candidates=corpus["candidates"])
    return baseline, compare_baseline(baseline, varieties=varieties, candidates=candidates)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", required=True, type=Path)
    parser.add_argument("--checked-on", required=True)
    parser.add_argument("--reported-stocks", required=True, type=int)
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data")
    parser.add_argument("--output", type=Path, default=ROOT / "inbox/external-variety-coverage/report.json")
    parser.add_argument("--snapshot-output", type=Path)
    parser.add_argument("--query-manifest", type=Path, help="Private JSON retaining the native query's selected_organisms")
    args = parser.parse_args()
    query = json.loads(args.query_manifest.read_text(encoding="utf-8")) if args.query_manifest else {}
    if args.snapshot_output and not query.get("selected_organisms"):
        parser.error("--snapshot-output requires --query-manifest with the native selected organisms")
    baseline, report = audit(args.csv, args.data_dir, args.checked_on, args.reported_stocks, query.get("selected_organisms"))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.snapshot_output:
        args.snapshot_output.parent.mkdir(parents=True, exist_ok=True)
        args.snapshot_output.write_text(json.dumps(baseline, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"source": baseline["source_title"], "totals": baseline["totals"], "comparison": report["comparison_counts"]}))
