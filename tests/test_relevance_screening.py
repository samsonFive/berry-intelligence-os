"""Pre-transcription relevance screening is cheap, deterministic triage."""

from __future__ import annotations

from app.services.media_orchestration import MediaOrchestrationService
from app.services.relevance_screening import screen_discovered_item
from tests.test_media_orchestration import SOURCE_ID, _item, _setup, _write_item


def test_strong_blueberry_signal_processes() -> None:
    screen = screen_discovered_item(
        {
            "title": "Business of Blueberries: cultivar update",
            "description": "Breeding and genetics discussion.",
            "source_id": "source-business-of-blueberries-podcast",
            "published_date": "2026-08-10",
        }
    )
    assert screen.decision == "process"
    assert "berry-blueberry" in screen.likely_berry_ids
    assert screen.provenance["trust_state"] == "untrusted_triage"


def test_clearly_irrelevant_item_is_skipped() -> None:
    screen = screen_discovered_item(
        {
            "title": "Celebrity gossip roundup",
            "description": "Awards night fashion recap.",
            "source_id": "source-other",
            "published_date": "2026-08-10",
        }
    )
    assert screen.decision == "skip"
    assert screen.score <= 3


def test_relevance_gate_skips_transcription_and_draft(tmp_path) -> None:
    service, repos, inbox, adapter = _setup(tmp_path)
    item = _item(title="Celebrity gossip roundup", description="Awards night fashion recap.")
    _write_item(inbox, item)
    result = service.process(item["id"], relevance_gate=True)
    assert result.state == "skipped_irrelevant"
    assert adapter.calls == 0
    assert not (inbox / "evidence").exists()
    stored = service.load_item(item["id"])
    assert stored["relevance_screening"]["decision"] == "skip"


def test_relevance_gate_off_still_creates_draft_for_low_signal_item(tmp_path) -> None:
    service, _, inbox, adapter = _setup(tmp_path)
    item = _item(title="Celebrity gossip roundup", description="Awards night fashion recap.")
    _write_item(inbox, item)
    result = service.process(item["id"], relevance_gate=False)
    assert result.state == "awaiting_publication_review"
    assert adapter.calls == 1
    assert list((inbox / "evidence").glob("*.json"))
