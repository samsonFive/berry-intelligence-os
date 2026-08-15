"""Audio/Video Intelligence data-model foundation tests.

Proves the schema/query-layer changes for `evidence.media_format` and
`evidence.transcript` (schemas/evidence.schema.json) hold, without touching
the live `data/evidence/` dataset -- per this project's standing "no
fictional intelligence in the live dataset" principle, every fixture here
is built through `get_repositories()` (app/composition.py) against a
`tmp_path`, mirroring tests/queries/test_query_services.py's own pattern.

Six things this file proves:
1. Existing (pre-this-phase) text evidence -- no `media_format`, no
   `transcript` -- still validates, since both fields are optional/additive.
2. Podcast evidence (`media_format: "podcast"`, with a `transcript` object)
   validates against the schema.
3. Video and conference_video evidence validate the same way.
4. One Source can own many audio/video Evidence records (`source_id`).
5. One Evidence record can link multiple existing entities and geographies
   via the pre-existing `entity_ids`/`geography_ids` relationship arrays --
   no new relationship mechanism was introduced for this phase.
6. `media_format` participates in `filter_evidence()` (app/main.py)
   alongside the pre-existing `source`/`berry`/`geography` filters, and
   `filter_options()` surfaces the distinct formats present in a record set.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from app.composition import get_repositories
from app.main import filter_evidence, filter_options
from app.repositories.paths import SCHEMAS_DIR


def _evidence(suffix: str, **overrides: Any) -> dict[str, Any]:
    record = {
        "id": f"ev-media-test-{suffix}",
        "record_type": "evidence",
        "status": "published",
        "source_type": "trade_press",
        "title": f"Media test evidence {suffix}",
        "captured_date": "2026-08-14",
        "summary": "Summary.",
        "submitted_by": "media-test",
        "priority": {
            dim: {"level": "none", "rationale": ""}
            for dim in ("reading", "testing", "commercial_position", "monitoring")
        },
    }
    record.update(overrides)
    return record


@pytest.fixture
def repos(tmp_path: Path):
    return get_repositories(tmp_path, SCHEMAS_DIR)


# ---------------------------------------------------------------------------
# 1-3: schema validation across formats
# ---------------------------------------------------------------------------

def test_existing_text_evidence_without_media_fields_remains_valid(repos) -> None:
    created = repos.evidence.create(_evidence("text-legacy"))
    assert "media_format" not in created
    assert "transcript" not in created


def test_podcast_evidence_with_transcript_validates(repos) -> None:
    created = repos.evidence.create(
        _evidence(
            "podcast",
            media_format="podcast",
            transcript={
                "status": "available",
                "language": "en",
                "source": "publisher_provided",
                "text": "Full transcript text.",
                "url": None,
            },
        )
    )
    assert created["media_format"] == "podcast"
    assert created["transcript"]["status"] == "available"


def test_video_evidence_validates(repos) -> None:
    created = repos.evidence.create(_evidence("video", media_format="video"))
    assert created["media_format"] == "video"


def test_conference_video_evidence_validates(repos) -> None:
    created = repos.evidence.create(_evidence("conf-video", media_format="conference_video"))
    assert created["media_format"] == "conference_video"


def test_transcript_not_available_is_distinct_from_absent_transcript(repos) -> None:
    considered = repos.evidence.create(
        _evidence("transcript-checked", media_format="podcast", transcript={"status": "not_available"})
    )
    never_considered = repos.evidence.create(_evidence("transcript-unconsidered", media_format="podcast"))
    assert considered["transcript"]["status"] == "not_available"
    assert "transcript" not in never_considered


def test_invalid_media_format_is_rejected(repos) -> None:
    from app.repositories.base import InvalidRecord

    with pytest.raises(InvalidRecord):
        repos.evidence.create(_evidence("bad-format", media_format="tiktok_clip"))


# ---------------------------------------------------------------------------
# 4: one Source owns many audio/video Evidence records
# ---------------------------------------------------------------------------

def test_one_source_owns_many_audio_video_evidence_records(repos) -> None:
    repos.sources.create({"id": "src-media-test-1", "name": "Test Berry Podcast Network"})
    repos.evidence.create(_evidence("src-ep1", media_format="podcast", source_id="src-media-test-1"))
    repos.evidence.create(_evidence("src-ep2", media_format="podcast", source_id="src-media-test-1"))
    repos.evidence.create(_evidence("src-vid1", media_format="video", source_id="src-media-test-1"))
    repos.evidence.create(_evidence("src-other", media_format="podcast", source_id="src-media-test-other"))

    owned = repos.evidence.list(source_id="src-media-test-1")
    assert {r["id"] for r in owned} == {
        "ev-media-test-src-ep1",
        "ev-media-test-src-ep2",
        "ev-media-test-src-vid1",
    }


# ---------------------------------------------------------------------------
# 5: one Evidence record links multiple entities and geographies
# ---------------------------------------------------------------------------

def test_evidence_links_multiple_entities_and_geographies(repos) -> None:
    repos.entities.create(
        {"id": "company-media-a", "record_type": "entity", "entity_type": "company", "name": "A Co", "status": "active"}
    )
    repos.entities.create(
        {"id": "company-media-b", "record_type": "entity", "entity_type": "company", "name": "B Co", "status": "active"}
    )
    repos.entities.create(
        {"id": "geography-media-x", "record_type": "entity", "entity_type": "geography", "name": "Region X", "status": "active"}
    )

    created = repos.evidence.create(
        _evidence(
            "multi-link",
            media_format="video",
            entity_ids=["company-media-a", "company-media-b"],
            geography_ids=["geography-media-x"],
        )
    )
    assert created["entity_ids"] == ["company-media-a", "company-media-b"]
    assert created["geography_ids"] == ["geography-media-x"]


# ---------------------------------------------------------------------------
# 6: media_format participates in filtering
# ---------------------------------------------------------------------------

def test_filter_evidence_by_media_format() -> None:
    records = [
        _evidence("filter-podcast", media_format="podcast"),
        _evidence("filter-video", media_format="video"),
        _evidence("filter-text"),
    ]
    result = filter_evidence(records, media_format="podcast")
    assert [r["id"] for r in result] == ["ev-media-test-filter-podcast"]


def test_filter_evidence_by_media_format_combines_with_existing_filters() -> None:
    records = [
        _evidence("combo-match", media_format="podcast", berry_ids=["blueberry"]),
        _evidence("combo-wrong-berry", media_format="podcast", berry_ids=["raspberry"]),
        _evidence("combo-wrong-format", media_format="video", berry_ids=["blueberry"]),
    ]
    result = filter_evidence(records, berry="blueberry", media_format="podcast")
    assert [r["id"] for r in result] == ["ev-media-test-combo-match"]


def test_filter_options_surfaces_distinct_media_formats_present() -> None:
    records = [
        _evidence("opt-podcast", media_format="podcast"),
        _evidence("opt-video", media_format="video"),
        _evidence("opt-video-2", media_format="video"),
        _evidence("opt-text"),
    ]
    options = filter_options(records, entities={})
    assert options["media_formats"] == ["podcast", "video"]


def test_filter_options_media_formats_empty_when_none_present() -> None:
    records = [_evidence("opt-none-a"), _evidence("opt-none-b")]
    options = filter_options(records, entities={})
    assert options["media_formats"] == []
