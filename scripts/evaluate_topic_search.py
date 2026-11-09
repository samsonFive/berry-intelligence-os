"""Reproducible discovery benchmark; live calls are opt-in and never CI.

The held-out final six queries must not tune vocabulary/ranking. Relevance
metrics require source-inspected judgments; ranking labels are never reused
as their own gold standard. Full captures stay in private inbox/.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from io import BytesIO
import json
import math
import os
from pathlib import Path
import statistics
import subprocess
import sys
import tarfile
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.services.topic_retrieval import plan_query, retrieve
from app.services.topic_discovery import discover_topic
from app.services.search_quality_evaluation import score_query, score_snapshot
from app.services.resilient_topic_search import credit_free_mode

QUERIES = [
    "Blackberry Floricans", "Floricane blackberry developments",
    "New blackberry varieties that fruit on second-year canes", "Ervin blackberry", "NC 740 blackberry",
    "Floricane blackberry licensing outside the United States",
    "Floricane blackberry developments 2026-01-01 through 2026-10-26",
    "Primocane blackberry developments",
    "Blackberry floricane crop trials involving a primocane-fruiting cultivar",
    "Strawberry gene editing heat tolerance Hudson River Plantik",
    "Blueberry breeding developments", "Raspberry developments Europe",
    "Blackberry fruit new varieties -software -security",
    "Sweet-Ark Immaculate blackberry release", "Fontana blackberry Pairwise",
    "Blueberry varieties Fall Creek Peru", "Strawberry Planasa licensing Spain", "Raspberry breeding Scotland",
    "Blueberry machine harvesting trials", "Nonexistent cultivar ZZZQX-991 blackberry",
    "Blackberry floricane pruning", "Raspberry primocane trials United Kingdom",
    "Strawberry robotic harvesting research", "Blueberry heat tolerance breeding",
]


def load_records(folder):
    return [json.loads(p.read_text(encoding="utf-8")) for p in folder.rglob("*.json")]


def archive_baseline(old_sha, queries, entities, records):
    """Run the old search and its imports against the same supplied corpus."""
    archive = subprocess.check_output(["git", "archive", old_sha, "app"], cwd=ROOT)
    code = """
import json
import sys

from app.services.global_search import SearchPools, build_search_documents, search_global

inputs = json.load(sys.stdin)
pools = SearchPools(entities=inputs["entities"], published_evidence=inputs["records"])
documents = build_search_documents(pools, include_private=False)
results = []
for query in inputs["queries"]:
    result = search_global(query, pools, documents=documents, limit_per_group=20, sort="relevance")
    results.append([row["id"] for group in result["groups"] if group["id"] == "intelligence"
                    for row in group["in_context"] + group["also_global"]][:20])
print(json.dumps(results))
"""
    with tempfile.TemporaryDirectory(prefix="archive-search-", dir=ROOT / "inbox") as work:
        with tarfile.open(fileobj=BytesIO(archive)) as source:
            source.extractall(work, filter="data")
        output = subprocess.check_output(
            [sys.executable, "-c", code], cwd=work,
            input=json.dumps({"queries": queries, "entities": entities, "records": records}).encode(),
        )
    by_id = {row["id"]: row for row in records}
    return [[by_id[record_id] for record_id in ids if record_id in by_id] for ids in json.loads(output)]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--allow-paid", action="store_true", help="Allow the configured paid provider during a live run")
    parser.add_argument("--limit", type=int, default=24)
    parser.add_argument("--old-ref", default="origin/v2/intelligence-os")
    parser.add_argument("--google-baseline", type=Path)
    parser.add_argument("--judgments", type=Path)
    parser.add_argument("--cohort", type=Path, help="JSON array of fresh held-out query strings")
    parser.add_argument("--public-output", type=Path, help="Path for the metadata-only snapshot")
    parser.add_argument("--output", type=Path, default=ROOT / "inbox/search-quality-evaluation/live.json")
    args = parser.parse_args()
    if args.allow_paid and not args.live:
        parser.error("--allow-paid requires --live")
    if args.live and not args.allow_paid:
        os.environ["BIOS_RESEARCH_CREDIT_FREE_ONLY"] = "1"
    queries = json.loads(args.cohort.read_text(encoding="utf-8")) if args.cohort else QUERIES
    if not isinstance(queries, list) or not queries or any(not isinstance(q, str) or not q.strip() for q in queries):
        parser.error("Cohort must be a nonempty JSON array of query strings")
    if args.limit < 1:
        parser.error("--limit must be positive")
    queries = queries[:args.limit]
    held_out = set(range(0 if args.cohort else 18, len(queries)))
    entities_list = load_records(ROOT / "data/entities")
    entities = {r["id"]: r for r in entities_list if r.get("id")}
    records = load_records(ROOT / "data/evidence")
    old_sha = subprocess.check_output(["git", "rev-parse", args.old_ref], cwd=ROOT, text=True).strip()
    (ROOT / "inbox").mkdir(exist_ok=True)
    old_results = archive_baseline(old_sha, queries, entities_list, records)
    baseline = json.loads(args.google_baseline.read_text(encoding="utf-8")) if args.google_baseline else {}
    google = {r["query"]: r for r in baseline.get("queries", [])}
    judgments = json.loads(args.judgments.read_text(encoding="utf-8")) if args.judgments else {}
    run = {"version": 1, "started_at": datetime.now(timezone.utc).isoformat(), "old_ref": old_sha, "provider": "perplexity_search" if args.live else "local_only", "locale": "en-US", "fixed_depth": 10, "held_out_query_indices": list(range(18, 24)), "comparison_limitations": ["Old app comparison measures archive Global Search, not an unavailable historical production request trace.", "Google organic headings exclude ads, AI overviews, shopping and video modules; captured first and second result pages are pooled in displayed order.", "Source-inspected independent relevance and event judgments are required before parity can be asserted."], "queries": []}
    run["held_out_query_indices"] = sorted(held_out)
    run["candidate_ref"] = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True,
    ).strip()
    run["candidate_tracked_changes"] = bool(subprocess.check_output(
        ["git", "status", "--porcelain", "--untracked-files=no"], cwd=ROOT, text=True,
    ).strip())
    if args.live and credit_free_mode():
        run["provider"] = "public_metadata_fallback"
    for i, query in enumerate(queries):
        started = time.monotonic()
        plan = plan_query(query)
        local = retrieve(records, plan, entities=entities, limit=20)
        local_seconds = time.monotonic() - started
        first_body_supported_seconds = None
        if any(row.get("support_status") == "body_supported" for row in local):
            first_body_supported_seconds = local_seconds

        def record_progress(event):
            nonlocal first_body_supported_seconds
            if first_body_supported_seconds is None and any(
                row.get("passage") and row.get("passage_locator")
                for row in event.get("items", [])
            ):
                first_body_supported_seconds = time.monotonic() - started
        names = [e["name"] for e in entities_list if e.get("entity_type") == "variety" and any("berry-" + crop in (e.get("berry_ids") or []) for crop in (set(plan.terms) & {"blackberry", "blueberry", "raspberry", "strawberry"}))]
        discovery_args = {
            "inbox_dir": ROOT / "inbox", "data_dir": ROOT / "data", "entities": entities,
            "constraints": {"public_variety_names": names},
        }
        capture_trace = []
        web = discover_topic(plan, progress=record_progress, capture_audit=capture_trace.extend, **discovery_args) if args.live else {"items": [], "status": "not_run", "queries_this_request": 0}
        ranked = retrieve([*local, *(web.get("items") or [])], plan, entities=entities, limit=20)
        cold = time.monotonic() - started
        if first_body_supported_seconds is None and any(
            row.get("support_status") == "body_supported" for row in ranked
        ):
            first_body_supported_seconds = cold
        warm_started = time.monotonic()
        warm = discover_topic(plan, **discovery_args) if args.live else {}
        warm_latency = time.monotonic() - warm_started
        before_rows = old_results[i]
        judged = judgments.get(query) or {}
        evaluation = score_query({"query":query,"old_app":before_rows,"improved_app":ranked,"discovery":web}, judged, google.get(query))
        result = {"query": query, "split": "held_out" if i >= 18 else "development", "plan": plan.as_dict(), "old_app": before_rows, "improved_app": ranked, "google": google.get(query, {}).get("results", []), "google_depth_complete": bool(google.get(query, {}).get("complete_depth")), "discovery": {k: v for k, v in web.items() if k != "items"}, "cold_seconds": round(cold, 3), "warm_seconds": round(warm_latency, 3), "warm_queries": warm.get("queries_this_request"), "metrics": evaluation["metrics"], "judged_pool_complete":evaluation["judged_pool_complete"], "google_comparable":evaluation["google_comparable"]}
        result["split"] = "held_out" if i in held_out else "development"
        if args.live and not web.get("cache_hit"):
            result["capture_trace"] = capture_trace
        result["local_retrieval_seconds"] = round(local_seconds, 3)
        result["first_body_supported_seconds"] = (
            round(first_body_supported_seconds, 3) if first_body_supported_seconds is not None else None
        )
        run["queries"].append(result)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(run, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"{i+1}/{len(queries)} old={len(before_rows)} improved={len(ranked)} web={web['status']} {cold:.2f}s {query}", flush=True)
    latencies = sorted(r["cold_seconds"] for r in run["queries"])
    run["summary"] = {"queries": len(latencies), "median_seconds": statistics.median(latencies), "p95_seconds": latencies[min(len(latencies)-1, math.ceil(len(latencies)*.95)-1)], "cost": None, "citation_support": "requires source inspection", "google_parity": "UNVERIFIED — source-inspected pooled judgments required", "all_warm_queries_zero": all(r.get("warm_queries") == 0 for r in run["queries"]) if args.live else None}
    run["quality_evaluation"] = score_snapshot(run, baseline, judgments)
    args.output.write_text(json.dumps(run, ensure_ascii=False, indent=2), encoding="utf-8")
    public = {**run, "queries": [{**r, "old_app": [{k: x.get(k) for k in ("id", "title", "source_url", "published_date")} for x in r["old_app"]], "improved_app": [{k: x.get(k) for k in ("id", "title", "source_url", "published_date", "capture_status", "relevance")} for x in r["improved_app"]]} for r in run["queries"]]}
    public_output = args.public_output or ROOT / "artifacts/search-research-quality" / (
        "live-results.json" if args.live else "local-results.json"
    )
    public_output.parent.mkdir(parents=True, exist_ok=True)
    public_output.write_text(json.dumps(public, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(run["summary"], indent=2))


if __name__ == "__main__":
    main()
