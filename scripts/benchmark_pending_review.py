"""Reproducible, content-free Pending Review performance benchmark.

Creates production-shaped private drafts in a temporary directory and reports
only stage timings/counts.  No title, body, or source text is logged.
"""

from __future__ import annotations

import argparse
from datetime import date, timedelta
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from time import perf_counter
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.queries.pending_review import JsonPendingDraftSnapshotProvider, PendingReviewQueryService
from app import main as application
from app.repositories.json.entities import EntityRepository
from app.repositories.json.evidence import EvidenceRepository
from app.repositories.json.sources import JsonSourceRepository
from app.repositories.paths import SCHEMAS_DIR
from app.services.morning_brief import build_morning_brief


BERRIES = {
    "berry-strawberry": "Strawberry",
    "berry-blueberry": "Blueberry",
    "berry-raspberry": "Raspberry",
    "berry-blackberry": "Blackberry",
}


def _timed(call):
    started = perf_counter()
    value = call()
    return value, round(perf_counter() - started, 4)


def _record(index: int) -> dict:
    day = date.today() - timedelta(days=index % 80)
    event = index // 2 if index % 10 in {0, 1} else index
    return {
        "id": f"benchmark-pending-{index:05d}",
        "title": f"Berry company event {event:05d} production update",
        "evidence_role": "publication_artifact",
        "status": "draft",
        "review_state": "pending_review",
        "source_id": f"benchmark-source-{index % 24}",
        "source_name": f"Benchmark source {index % 24}",
        "source_url": f"https://benchmark.invalid/items/{index}",
        "published_date": day.isoformat(),
        "captured_date": f"{day.isoformat()}T12:00:00Z",
        "berry_ids": [list(BERRIES)[index % len(BERRIES)]],
        "entity_ids": [],
        "relevance_tier": "adjacent" if index % 11 == 0 else "direct",
        "priority": {"reading": {"level": "high" if index % 7 == 0 else "medium"}},
        "tags": ["tier-1"] if index % 5 == 0 else [],
        "summary": "Production-shaped benchmark metadata.",
        "article": {
            "final_url": f"https://benchmark.invalid/items/{index}",
            "paragraphs": [
                {"text": "A production-shaped article paragraph for deterministic attribution. " * 18}
                for _ in range(5)
            ],
        },
        "transcript": "A private transcript field that the pending list must omit. " * 80,
    }


def _run(size: int) -> dict:
    entities = {row["id"]: row for row in EntityRepository(data_dir=ROOT / "data", schemas_dir=SCHEMAS_DIR).list()}
    sources = {row["id"]: row for row in JsonSourceRepository(data_dir=ROOT / "data").list()}
    published = EvidenceRepository(data_dir=ROOT / "data", schemas_dir=SCHEMAS_DIR).list(status="published")
    with TemporaryDirectory(prefix="bios-pending-benchmark-") as raw:
        inbox = Path(raw)
        evidence = inbox / "evidence"
        evidence.mkdir(parents=True)
        for index in range(size):
            record = _record(index)
            (evidence / f"{record['id']}.json").write_text(json.dumps(record), encoding="utf-8")

        provider = JsonPendingDraftSnapshotProvider(inbox)
        service = PendingReviewQueryService(provider)
        bootstrap, bootstrap_seconds = _timed(lambda: service.list_pending(entities=entities, sources=sources))

        restart_service = PendingReviewQueryService(JsonPendingDraftSnapshotProvider(inbox))
        snapshot, inventory_seconds = _timed(
            lambda: restart_service.list_pending(entities=entities, sources=sources)
        )
        brief, rank_seconds = _timed(
            lambda: build_morning_brief(
                inbox_dir=inbox,
                published=published,
                drafts=snapshot.records,
                unvalidated=[],
                signals=[],
                entities=entities,
                sources=list(sources.values()),
                berry_labels=BERRIES,
                include_signal_candidates=False,
                mode="pending",
            )
        )
        def render(model):
            for bucket in (model.get("pending_triage") or {}).get("buckets") or []:
                application._attach_pending_decision_actions(bucket.get("entries") or [], "benchmark")
            return application.templates.get_template("pending_review.html").render(
                request=SimpleNamespace(
                    url=SimpleNamespace(path="/pending", query=""),
                    query_params={},
                ),
                brief=model,
                authoring_mode=True,
                static_build=False,
                reviewer="benchmark",
                return_to="/pending",
                ui_context={
                    "berry": "global",
                    "berry_label": "Global",
                    "feed_view": "grid",
                    "landscape_href": "/entities/berry",
                },
                nav_work_counts={
                    "brief_action": 0, "reading_action": 0, "review_now": 0,
                    "emerging_signals": 0, "monitoring_inventory": 0,
                    "signal_alerts": 0, "testing_action": 0,
                },
                pending_review_count=lambda: 0,
            )

        rendered, template_seconds = _timed(lambda: render(brief))
        _warm_snapshot, warm_inventory_seconds = _timed(
            lambda: restart_service.list_pending(entities=entities, sources=sources)
        )
        _warm_brief, warm_rank_seconds = _timed(
            lambda: build_morning_brief(
                inbox_dir=inbox,
                published=published,
                drafts=snapshot.records,
                unvalidated=[],
                signals=[],
                entities=entities,
                sources=list(sources.values()),
                berry_labels=BERRIES,
                include_signal_candidates=False,
                mode="pending",
            )
        )
        warm_rendered, warm_template_seconds = _timed(lambda: render(_warm_brief))
        detail, direct_detail_seconds = _timed(
            lambda: json.loads((evidence / "benchmark-pending-00000.json").read_text(encoding="utf-8"))
        )
        buckets = (brief.get("pending_triage") or {}).get("buckets") or []
        visible = sum(len(bucket.get("entries") or []) for bucket in buckets)
        return {
            "records": size,
            "bootstrap_index_seconds": bootstrap_seconds,
            "cold_restart": {
                "inventory_seconds": inventory_seconds,
                "rank_thread_model_seconds": rank_seconds,
                "actions_template_seconds": template_seconds,
                "total_seconds": round(inventory_seconds + rank_seconds + template_seconds, 4),
            },
            "warm": {
                "inventory_seconds": warm_inventory_seconds,
                "rank_thread_model_seconds": warm_rank_seconds,
                "actions_template_seconds": warm_template_seconds,
                "total_seconds": round(warm_inventory_seconds + warm_rank_seconds + warm_template_seconds, 4),
            },
            "direct_detail_seconds": direct_detail_seconds,
            "direct_detail_has_article": bool(detail.get("article")),
            "list_projection_has_rich_body": any(
                any(key in row for key in ("article", "transcript", "transcript_segments", "raw_content", "raw_html", "source_text"))
                for row in snapshot.records
            ),
            "bootstrap_parsed": bootstrap.parsed_records,
            "restart_reused": snapshot.reused_records,
            "exact_open_count": (brief.get("pending_triage") or {}).get("counts", {}).get("total", 0),
            "visible_cards": visible,
            "rendered_bytes": len(rendered.encode("utf-8")),
            "warm_rendered_bytes": len(warm_rendered.encode("utf-8")),
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sizes", nargs="+", type=int, default=[1500, 5000])
    args = parser.parse_args()
    print(json.dumps({"pending_review_benchmark_v2": [_run(size) for size in args.sizes]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
