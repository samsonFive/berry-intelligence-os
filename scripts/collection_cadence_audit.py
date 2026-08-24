"""Audit per-Source collection cadence/yield from retained runtime records.

Read-only and offline: no Source fetches, model calls, trust changes, or
runtime writes are performed.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.composition import get_repositories
from app.repositories.paths import SCHEMAS_DIR
from app.runtime_config import resolve_data_dir, resolve_inbox_dir
from app.services.collection_runner import CollectionRunner, OperationalStateStore
from app.services.media_discovery import read_source_discovery_state
from app.services.source_cadence import build_cadence_audit, load_cadence_policy, load_json_objects


SPOKEN_ADAPTERS = {"podcast_rss", "youtube_feed"}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--data-dir", type=Path)
    parser.add_argument("--inbox-dir", type=Path)
    parser.add_argument("--schemas-dir", type=Path, default=SCHEMAS_DIR)
    parser.add_argument("--policy", type=Path)
    return parser


def _legacy_attempts_per_day(sources: list[dict], pipeline_config: dict) -> float:
    cadences = {
        row.get("id"): row.get("cadence_seconds")
        for row in pipeline_config.get("pipelines") or []
        if isinstance(row, dict)
    }
    attempts = 0.0
    for source in sources:
        adapter = (source.get("discovery") or {}).get("adapter")
        pipeline = "spoken_media" if adapter in SPOKEN_ADAPTERS else "article_news"
        seconds = cadences.get(pipeline)
        if not isinstance(seconds, int) or seconds <= 0:
            continue
        discovery = source.get("discovery") or {}
        requests = len(discovery.get("feed_urls") or []) or (1 if discovery.get("feed_url") else 0)
        attempts += requests * 86400 / seconds
    return attempts


def _human(payload: dict) -> str:
    before = payload["estimated_requests_per_day_before"]
    after = payload["estimated_requests_per_day_after"]
    reduction = payload["estimated_request_reduction_percent"]
    lines = [
        "COLLECTION CADENCE + YIELD AUDIT",
        f"Discoverable Sources: {payload['sources_discoverable']}",
        f"Repeat-run evidence: {payload['sources_with_repeat_run_evidence']}",
        f"Cadences changed / unchanged: {payload['cadences_changed']} / {payload['cadences_unchanged']}",
        f"Estimated collection requests/day: {before} -> {after} ({reduction}% reduction)",
        f"Berry coverage guard: {payload['berry_coverage']}",
        "",
        "Per Source:",
    ]
    for row in payload["sources"]:
        rate = row["duplicate_only_repeat_run_rate"]
        lines.append(
            f"  {row['source']} [{row['source_id']}]: {row['current_cadence']} -> "
            f"{row['cadence_class']} ({row['recommended_cadence_seconds']}s); "
            f"runs={row['recent_runs']}, ok={row['successful_runs']}, observed={row['items_observed']}, "
            f"new_after_initial={row['new_items_excluding_initial_run']}, duplicate_items={row['duplicate_items']}, "
            f"duplicate_only_rate={rate if rate is not None else 'unknown'}, "
            f"relevant_drafts={row['relevant_publication_drafts']}, rich={row['rich_body']}, "
            f"failures={row['failures']}, health={row['source_health']}, due={row['due']}, "
            f"next={row['next_due'] or 'operator/manual'}; {row['recommendation_reason']}"
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    data_dir = args.data_dir or resolve_data_dir(ROOT)
    inbox_dir = args.inbox_dir or resolve_inbox_dir(ROOT)
    policy_path = args.policy or data_dir / "configuration" / "source_collection_cadence.json"
    policy = load_cadence_policy(policy_path)
    repositories = get_repositories(data_dir, args.schemas_dir)
    eligibility = CollectionRunner(
        repositories=repositories,
        inbox_dir=inbox_dir,
        operations=OperationalStateStore(inbox_dir / "operations"),
        discover=lambda _source_id: None,
        orchestrate=lambda *_args: None,
        transcript_cache_ready=lambda _item: False,
    )
    discoverable = set(eligibility.eligible_source_ids())
    sources = [source for source in repositories.sources.list() if source.get("id") in discoverable]
    states = {source["id"]: read_source_discovery_state(inbox_dir, source["id"]) for source in sources}
    payload = build_cadence_audit(
        sources=sources,
        run_records=load_json_objects(inbox_dir / "operations" / "runs"),
        drafts=load_json_objects(inbox_dir / "evidence"),
        discovery_states=states,
        policy=policy,
    )
    pipeline_path = data_dir / "configuration" / "collection_pipelines.json"
    pipeline_config = json.loads(pipeline_path.read_text(encoding="utf-8"))
    before = round(_legacy_attempts_per_day(sources, pipeline_config), 2)
    after = payload["estimated_requests_per_day_after"]
    pipeline_cadences = {
        row.get("id"): row.get("cadence_seconds")
        for row in pipeline_config.get("pipelines") or []
        if isinstance(row, dict)
    }
    for row in payload["sources"]:
        row["current_operational_cadence_seconds"] = pipeline_cadences.get(
            "spoken_media" if row["discovery_mechanism"] in SPOKEN_ADAPTERS else "article_news"
        )
    avoided_duplicate_only = 0.0
    for row in payload["sources"]:
        old_seconds = row["current_operational_cadence_seconds"]
        new_seconds = row["recommended_cadence_seconds"]
        duplicate_rate = row["duplicate_only_repeat_run_rate"]
        if not all(isinstance(value, (int, float)) and value > 0 for value in (old_seconds, new_seconds)):
            continue
        if not isinstance(duplicate_rate, (int, float)):
            continue
        avoided_duplicate_only += max(0.0, 86400 / old_seconds - 86400 / new_seconds) * duplicate_rate
    payload["estimated_requests_per_day_before"] = before
    payload["estimated_request_reduction_percent"] = round((before - after) / before * 100, 1) if before else 0.0
    payload["estimated_duplicate_only_source_scans_avoided_per_day"] = round(avoided_duplicate_only, 2)
    print(json.dumps(payload, indent=2, ensure_ascii=False) if args.json else _human(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
