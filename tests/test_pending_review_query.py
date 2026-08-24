"""Pending Review V2 read-model, bounded hydration, and mutation safety."""

from __future__ import annotations

from copy import deepcopy
from datetime import date
import json
from pathlib import Path

from fastapi.testclient import TestClient

from app import main
from app.queries.pending_review import JsonPendingDraftSnapshotProvider, PendingReviewQueryService
from app.services import morning_brief
from app.services.draft_attribution import (
    attribute_draft,
    build_attribution_match_index,
    indexed_title_matched_entity_ids,
)
from app.services.morning_brief import build_morning_brief, title_matched_entities


PRIORITY = {
    dimension: {"level": "none", "rationale": ""}
    for dimension in ("reading", "testing", "commercial_position", "monitoring")
}
ENTITIES = {
    "company-planasa": {
        "id": "company-planasa",
        "entity_type": "company",
        "name": "Plantas de Navarra, S.A.",
        "aliases": ["Planasa"],
    },
    "variety-blue-maldiva": {
        "id": "variety-blue-maldiva",
        "entity_type": "variety",
        "name": "Blue Maldiva",
        "aliases": ["Maldiva"],
    },
}
SOURCES = {
    "source-planasa": {
        "id": "source-planasa",
        "label": "Planasa Newsroom",
        "monitoring_priority": "high",
        "linked_competitor_ids": ["company-planasa"],
    }
}


def _draft(index: int, **overrides) -> dict:
    record = {
        "id": f"pending-{index:04d}",
        "record_type": "evidence",
        "evidence_role": "publication_artifact",
        "status": "pending",
        "review_state": "pending_review",
        "source_id": "source-planasa" if index % 2 == 0 else "source-other",
        "source_name": "Planasa Newsroom" if index % 2 == 0 else "Trade desk",
        "source_type": "rss",
        "source_url": f"https://example.invalid/{index}",
        "title": f"Planasa blueberry production update {index}",
        "published_date": date.today().isoformat(),
        "captured_date": date.today().isoformat(),
        "summary": "Untrusted pending summary.",
        "berry_ids": ["berry-blueberry" if index % 2 == 0 else "berry-raspberry"],
        "entity_ids": [],
        "relevance_tier": "direct",
        "media_format": "web_article",
        "priority": deepcopy(PRIORITY),
        "article": {
            "final_url": f"https://example.invalid/{index}",
            "paragraphs": [{"text": "Blue Maldiva appears in the full private article body."}],
        },
        "transcript": "Private full transcript.",
    }
    record.update(overrides)
    return record


def _write(folder: Path, record: dict) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{record['id']}.json"
    path.write_text(json.dumps(record), encoding="utf-8")
    return path


def test_indexed_attribution_is_identical_to_historical_matcher() -> None:
    records = [
        _draft(1),
        _draft(2, title="Blue Maldiva launch", source_name="Unrelated source"),
        _draft(3, title="Unrelated title", entity_ids=["company-planasa"]),
    ]
    index = build_attribution_match_index(ENTITIES)
    for record in records:
        assert attribute_draft(record, ENTITIES, sources=SOURCES, match_index=index) == attribute_draft(
            record, ENTITIES, sources=SOURCES
        )


def test_indexed_title_matches_preserve_legacy_substring_and_order() -> None:
    entities = {
        **ENTITIES,
        "company-blue": {
            "id": "company-blue",
            "entity_type": "company",
            "name": "Blue",
        },
    }
    record = _draft(7, title="Blueberry update from Planasa")
    index = build_attribution_match_index(entities)
    expected = [row["id"] for row in title_matched_entities(record, entities)]
    assert indexed_title_matched_entity_ids(record["title"], entities, index) == expected
    assert "company-blue" in expected


def _rich_article() -> dict:
    return {
        "final_url": "https://example.invalid/rich",
        "paragraphs": [{
            "text": (
                "Captured full article body for publication review completeness. "
                * 20
            )
        }],
    }


def test_private_read_model_omits_bodies_reuses_restart_and_preserves_detail(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    source = _draft(1, article=_rich_article())
    path = _write(inbox / "evidence", source)
    service = PendingReviewQueryService(JsonPendingDraftSnapshotProvider(inbox))

    first = service.list_pending(entities=ENTITIES, sources=SOURCES)
    assert first.parsed_records == 1
    assert first.body_records_omitted == 1
    assert first.records[0]["_pending_completeness"] == "FULL_ARTICLE"
    assert first.records[0]["_pending_paragraph_count"] >= 1
    assert "article" not in first.records[0]
    assert "transcript" not in first.records[0]
    assert first.records[0]["_pending_attribution"] == attribute_draft(source, ENTITIES, sources=SOURCES)
    assert (inbox / "indexes" / "pending-review-v2.json").is_file()

    restarted = PendingReviewQueryService(JsonPendingDraftSnapshotProvider(inbox)).list_pending(
        entities=ENTITIES, sources=SOURCES
    )
    assert restarted.parsed_records == 0
    assert restarted.reused_records == 1
    detail = json.loads(path.read_text(encoding="utf-8"))
    assert detail["article"]["paragraphs"]
    assert detail["transcript"] == "Private full transcript."


def test_filters_are_pushed_into_inventory_result(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    for index in range(4):
        _write(inbox / "evidence", _draft(index))
    service = PendingReviewQueryService(JsonPendingDraftSnapshotProvider(inbox))
    result = service.list_pending(
        entities=ENTITIES,
        sources=SOURCES,
        ids={"pending-0000", "pending-0001", "pending-0002"},
        berry_id="berry-blueberry",
        source="source-planasa",
    )
    assert [row["id"] for row in result.records] == ["pending-0000", "pending-0002"]
    assert result.inventory_count == 4


def test_draft_mutation_invalidates_sidecar(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    path = _write(inbox / "evidence", _draft(0, status="pending"))
    provider = JsonPendingDraftSnapshotProvider(inbox)
    first = provider.snapshot(entities=ENTITIES, sources=SOURCES)
    changed = _draft(0, source_id="source-changed")
    encoded = json.dumps(changed)
    old_encoded = path.read_text(encoding="utf-8")
    assert len(encoded) == len(old_encoded)
    path.write_text(encoded, encoding="utf-8")
    second = provider.snapshot(entities=ENTITIES, sources=SOURCES)
    assert first.records[0]["status"] == "pending"
    assert second.parsed_records == 1
    assert second.records[0]["source_id"] == "source-changed"


def test_pending_mode_hydrates_only_bounded_visible_single_cards(monkeypatch, tmp_path: Path) -> None:
    drafts = [_draft(index, article=None, transcript=None) for index in range(180)]
    calls = {"compact": 0, "full": 0}
    real = morning_brief.rank_item

    def counted(record, *, ctx, compact=False):
        calls["compact" if compact else "full"] += 1
        return real(record, ctx=ctx, compact=compact)

    monkeypatch.setattr(morning_brief, "rank_item", counted)
    brief = build_morning_brief(
        inbox_dir=tmp_path / "inbox",
        published=[],
        drafts=drafts,
        unvalidated=[],
        signals=[],
        entities=ENTITIES,
        sources=list(SOURCES.values()),
        berry_labels={"berry-blueberry": "Blueberry", "berry-raspberry": "Raspberry"},
        include_signal_candidates=False,
        mode="pending",
    )
    visible = sum(len(bucket["entries"]) for bucket in brief["pending_triage"]["buckets"])
    assert brief["pending_triage"]["counts"]["total"] == 180
    assert calls["compact"] == 180
    assert calls["full"] <= visible <= 100
    assert all(len(bucket["entries"]) <= 20 for bucket in brief["pending_triage"]["buckets"])


def test_pending_route_uses_private_projection_and_renders_filters(monkeypatch, tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    _write(inbox / "evidence", _draft(0, article=_rich_article()))
    _write(inbox / "evidence", _draft(1))
    monkeypatch.setattr(main, "INBOX_DIR", inbox)
    monkeypatch.setattr(main, "entity_index", lambda: ENTITIES)
    monkeypatch.setattr(main, "load_sources", lambda: list(SOURCES.values()))
    monkeypatch.setattr(main, "published_evidence", lambda: [])
    response = TestClient(main.app).get("/pending?berry=blueberry&source=source-planasa")
    assert response.status_code == 200
    assert "pending-0000" in response.text
    assert "pending-0001" not in response.text
    sidecar = json.loads((inbox / "indexes" / "pending-review-v2.json").read_text(encoding="utf-8"))
    encoded = json.dumps(sidecar)
    assert sidecar["version"] == 5
    assert "full private article body" not in encoded
    assert "Private full transcript" not in encoded
    assert "FULL ARTICLE" in response.text


def test_completeness_filter_does_not_hydrate_bodies(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    _write(inbox / "evidence", _draft(0, article=_rich_article()))
    _write(
        inbox / "evidence",
        _draft(1, article=None, transcript=None, publisher_description="Thin feed blurb."),
    )
    service = PendingReviewQueryService(JsonPendingDraftSnapshotProvider(inbox))
    result = service.list_pending(entities=ENTITIES, sources=SOURCES, completeness="FULL_ARTICLE")
    assert [row["id"] for row in result.records] == ["pending-0000"]
    assert "article" not in result.records[0]
    assert result.records[0]["_pending_completeness"] == "FULL_ARTICLE"
