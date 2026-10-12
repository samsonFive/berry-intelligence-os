"""Audit supplied GDR CSV or read-only GRIN XLSX values, without trust writes.

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
from app.services.variety_external_coverage import analyze_gdr_csv, analyze_grin_values, compare_baseline
from app.services.variety_portfolio_coverage import load_portfolio_observations, reconcile_portfolios
from app.services.variety_universe.corpus_discovery import build_discovered_candidates


def audit(csv_path, data_dir, checked_on, reported_stocks, query_organisms=None):
    baseline = analyze_gdr_csv(csv_path, checked_on=checked_on, reported_stocks=reported_stocks, query_organisms=query_organisms)
    return baseline, compare_with_stored(baseline, data_dir)


def compare_with_stored(baseline, data_dir):
    def records(folder):
        return [json.loads(path.read_text(encoding="utf-8")) for path in sorted((data_dir / folder).rglob("*.json"))]
    entities = records("entities")
    varieties = [row for row in entities if row.get("entity_type") == "variety"]
    corpus = build_discovered_candidates(varieties=varieties, entities=entities,
        published_evidence=[row for row in records("evidence") if row.get("status") == "published"], facts=records("facts"))
    _, candidates = reconcile_portfolios(sources=load_portfolio_observations(data_dir), varieties=varieties,
        entities=entities, candidates=corpus["candidates"])
    return compare_baseline(baseline, varieties=varieties, candidates=candidates)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--csv", type=Path)
    source.add_argument("--grin-values", type=Path, help="Private matrix from read-only Artifact Tool XLSX import")
    parser.add_argument("--workbook", type=Path, help="Original GRIN workbook retained unchanged for SHA")
    parser.add_argument("--checked-on", required=True)
    parser.add_argument("--reported-stocks", required=True, type=int)
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data")
    parser.add_argument("--output", type=Path, default=ROOT / "inbox/external-variety-coverage/report.json")
    parser.add_argument("--snapshot-output", type=Path)
    parser.add_argument("--query-manifest", type=Path, help="Private JSON retaining the native query's selected_organisms")
    args = parser.parse_args()
    query = json.loads(args.query_manifest.read_text(encoding="utf-8")) if args.query_manifest else {}
    if args.grin_values:
        if not args.workbook:
            parser.error("--grin-values requires --workbook")
        native_query = query.get("query", {})
        if args.snapshot_output and not (native_query.get("scientific_name") == "Vaccinium"
                and native_query.get("accession_scope") == "All accessions including historical"
                and native_query.get("limit") == 10000 and query.get("native_reported_count") == args.reported_stocks
                and query.get("checked_on") == args.checked_on):
            parser.error("GRIN snapshot requires the retained native query and accession count")
        baseline = analyze_grin_values(json.loads(args.grin_values.read_text(encoding="utf-8")), workbook_path=args.workbook,
                                      checked_on=args.checked_on, reported_accessions=args.reported_stocks)
        if args.snapshot_output and baseline["input_sha256"] != query.get("raw_file_sha256"):
            parser.error("GRIN original workbook does not match its retained query manifest SHA")
        report = compare_with_stored(baseline, args.data_dir)
    else:
        if args.snapshot_output and not query.get("selected_organisms"):
            parser.error("--snapshot-output requires --query-manifest with the native selected organisms")
        baseline, report = audit(args.csv, args.data_dir, args.checked_on, args.reported_stocks, query.get("selected_organisms"))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.snapshot_output:
        args.snapshot_output.parent.mkdir(parents=True, exist_ok=True)
        args.snapshot_output.write_text(json.dumps(baseline, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"source": baseline["source_title"], "totals": baseline["totals"], "comparison": report["comparison_counts"]}))
