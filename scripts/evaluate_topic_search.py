"""Reproducible discovery benchmark; live calls are opt-in and never CI.

The held-out final six queries must not tune vocabulary/ranking. Relevance
metrics require source-inspected judgments; ranking labels are never reused
as their own gold standard. Full captures stay in private inbox/.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import statistics
import subprocess
import sys
import time
import types

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.services.topic_retrieval import plan_query, retrieve
from app.services.topic_discovery import discover_topic
from app.services.search_quality_evaluation import score_query, score_snapshot

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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--limit", type=int, default=24)
    parser.add_argument("--old-ref", default="origin/v2/intelligence-os")
    parser.add_argument("--google-baseline", type=Path)
    parser.add_argument("--judgments", type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / "inbox/search-quality-evaluation/live.json")
    args = parser.parse_args()
    entities_list = load_records(ROOT / "data/entities")
    entities = {r["id"]: r for r in entities_list if r.get("id")}
    records = load_records(ROOT / "data/evidence")
    old_sha = subprocess.check_output(["git", "rev-parse", args.old_ref], cwd=ROOT, text=True).strip()
    code = subprocess.check_output(["git", "show", f"{old_sha}:app/services/global_search.py"], cwd=ROOT, text=True, encoding="utf-8")
    old = types.ModuleType("benchmark_old_global_search")
    sys.modules[old.__name__] = old
    exec(compile(code, f"git:{old_sha}:global_search.py", "exec"), old.__dict__)
    pools = old.SearchPools(entities=entities_list, published_evidence=records)
    docs = old.build_search_documents(pools, include_private=False)
    old_records = {r["id"]: r for r in records}
    baseline = json.loads(args.google_baseline.read_text(encoding="utf-8")) if args.google_baseline else {}
    google = {r["query"]: r for r in baseline.get("queries", [])}
    judgments = json.loads(args.judgments.read_text(encoding="utf-8")) if args.judgments else {}
    run = {"version": 1, "started_at": datetime.now(timezone.utc).isoformat(), "old_ref": old_sha, "provider": "perplexity_search" if args.live else "local_only", "locale": "en-US", "fixed_depth": 10, "held_out_query_indices": list(range(18, 24)), "comparison_limitations": ["Old app comparison measures archive Global Search, not an unavailable historical production request trace.", "Google organic headings exclude ads, AI overviews, shopping and video modules; captured first and second result pages are pooled in displayed order.", "Source-inspected independent relevance and event judgments are required before parity can be asserted."], "queries": []}
    for i, query in enumerate(QUERIES[:args.limit]):
        started = time.monotonic()
        plan = plan_query(query)
        local = retrieve(records, plan, entities=entities, limit=20)
        names = [e["name"] for e in entities_list if e.get("entity_type") == "variety" and any("berry-" + crop in (e.get("berry_ids") or []) for crop in (set(plan.terms) & {"blackberry", "blueberry", "raspberry", "strawberry"}))]
        web = discover_topic(plan, inbox_dir=ROOT / "inbox", entities=entities, constraints={"public_variety_names": names}) if args.live else {"items": [], "status": "not_run", "queries_this_request": 0}
        ranked = retrieve([*local, *(web.get("items") or [])], plan, entities=entities, limit=20)
        cold = time.monotonic() - started
        warm_started = time.monotonic()
        warm = discover_topic(plan, inbox_dir=ROOT / "inbox", entities=entities, constraints={"public_variety_names": names}) if args.live else {}
        warm_latency = time.monotonic() - warm_started
        before = old.search_global(query, pools, documents=docs, limit_per_group=20, sort="relevance")
        before_rows = [old_records[r["id"]] for g in before["groups"] if g["id"] == "intelligence" for r in g["in_context"] + g["also_global"] if r["id"] in old_records][:20]
        judged = judgments.get(query) or {}
        evaluation = score_query({"query":query,"old_app":before_rows,"improved_app":ranked}, judged, google.get(query))
        result = {"query": query, "split": "held_out" if i >= 18 else "development", "plan": plan.as_dict(), "old_app": before_rows, "improved_app": ranked, "google": google.get(query, {}).get("results", []), "google_depth_complete": bool(google.get(query, {}).get("complete_depth")), "discovery": {k: v for k, v in web.items() if k != "items"}, "cold_seconds": round(cold, 3), "warm_seconds": round(warm_latency, 3), "warm_queries": warm.get("queries_this_request"), "metrics": evaluation["metrics"], "judged_pool_complete":evaluation["judged_pool_complete"], "google_comparable":evaluation["google_comparable"]}
        run["queries"].append(result)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(run, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"{i+1}/{min(args.limit,24)} old={len(before_rows)} improved={len(ranked)} web={web['status']} {cold:.2f}s {query}", flush=True)
    latencies = sorted(r["cold_seconds"] for r in run["queries"])
    run["summary"] = {"queries": len(latencies), "median_seconds": statistics.median(latencies), "p95_seconds": latencies[min(len(latencies)-1, math.ceil(len(latencies)*.95)-1)], "cost": None, "citation_support": "requires source inspection", "google_parity": "UNVERIFIED — source-inspected pooled judgments required", "all_warm_queries_zero": all(r.get("warm_queries") == 0 for r in run["queries"]) if args.live else None}
    run["quality_evaluation"] = score_snapshot(run, baseline, judgments)
    args.output.write_text(json.dumps(run, ensure_ascii=False, indent=2), encoding="utf-8")
    public = {**run, "queries": [{**r, "old_app": [{k: x.get(k) for k in ("id", "title", "source_url", "published_date")} for x in r["old_app"]], "improved_app": [{k: x.get(k) for k in ("id", "title", "source_url", "published_date", "capture_status", "relevance")} for x in r["improved_app"]]} for r in run["queries"]]}
    folder = ROOT / "artifacts/search-research-quality"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / ("live-results.json" if args.live else "local-results.json")).write_text(json.dumps(public, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(run["summary"], indent=2))


if __name__ == "__main__":
    main()
