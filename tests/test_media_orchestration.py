"""Offline trust-boundary tests for discovered-media orchestration."""

from __future__ import annotations

from copy import deepcopy
from datetime import date
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import main
from app.main import app
from scripts import process_discovered_media
from app.services.media_orchestration import (
    MediaOrchestrationError,
    MediaOrchestrationService,
    publication_draft_id,
)
from app.services.transcript_evidence import StructuredCandidateProvider, TranscriptEvidenceExtractionService


SOURCE_ID = "source-orchestration-fixture"


class CountingTranscriptAdapter:
    def __init__(self, payload: dict | None) -> None:
        self.payload = payload
        self.calls = 0

    def load(self, discovered_item: dict) -> dict | None:
        self.calls += 1
        return deepcopy(self.payload)


def _item(item_id: str = "media-fixture-one", **changes) -> dict:
    record = {
        "id": item_id,
        "record_type": "discovered_media_item",
        "staging_schema_version": 1,
        "source_id": SOURCE_ID,
        "external_id": "episode-1",
        "dedupe_strategy": "external_id",
        "dedupe_key": "episode-1",
        "title": "Fixture episode",
        "description": "Publisher-supplied fixture description.",
        "canonical_url": "https://example.invalid/episode-1",
        "published_date": "2026-08-01",
        "media_format": "podcast",
        "transcript_availability": {"status": "unknown"},
        "possible_evidence_matches": [],
        "first_seen_at": "2026-08-15T10:00:00+00:00",
        "last_seen_at": "2026-08-15T10:00:00+00:00",
        "raw_metadata": {},
    }
    record.update(changes)
    return record


def _transcript(**changes) -> dict:
    payload = {
        "transcript_id": "transcript-orchestration-fixture",
        "discovered_item_id": "media-fixture-one",
        "language": "en",
        "provenance": {
            "method": "auto_generated",
            "created_by": "fixture transcript provider",
            "created_at": "2026-08-15",
        },
        "segments": [
            {"text": "Welcome.", "start_seconds": 0, "end_seconds": 2},
            {"text": "The trial may expand.", "start_seconds": 20, "end_seconds": 24},
        ],
    }
    payload.update(changes)
    return payload


def _parent(item: dict, evidence_id: str | None = None) -> dict:
    return {
        "id": evidence_id or publication_draft_id(item),
        "record_type": "evidence",
        "status": "published",
        "review_state": "published",
        "source_type": "industry_podcast",
        "title": item["title"],
        "source_name": "Fixture Publisher",
        "source_url": item["canonical_url"],
        "published_date": item["published_date"],
        "captured_date": "2026-08-15",
        "summary": "Human-reviewed publication fixture.",
        "submitted_by": "fixture reviewer",
        "source_id": item["source_id"],
        "media_format": item["media_format"],
        "evidence_role": "publication_artifact",
        "priority": {
            dimension: {"level": "none", "rationale": ""}
            for dimension in ("reading", "testing", "commercial_position", "monitoring")
        },
    }


def _write_item(inbox: Path, item: dict) -> None:
    folder = inbox / "discovered_media"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{item['id']}.json").write_text(json.dumps(item), encoding="utf-8")


def _setup(tmp_path: Path, *, transcript: dict | None = None, extraction: bool = False, candidates=None):
    data_dir = tmp_path / "data"
    inbox = tmp_path / "inbox"
    repos = main.get_repositories(data_dir, main.SCHEMAS_DIR)
    repos.sources.create({"id": SOURCE_ID, "name": "Fixture Publisher"})
    adapter = CountingTranscriptAdapter(transcript)
    validator = main.get_validator("evidence.schema.json")
    errors = lambda record: [error.message for error in validator.iter_errors(record)]
    extractor = None
    if extraction:
        extractor = TranscriptEvidenceExtractionService(
            repositories=repos,
            inbox_dir=inbox,
            evidence_errors=errors,
            provider=StructuredCandidateProvider(
                candidates if candidates is not None else [], name="fixture extractor", method="ai_assisted"
            ),
            today=lambda: date(2026, 8, 15),
        )
    service = MediaOrchestrationService(
        repositories=repos,
        inbox_dir=inbox,
        evidence_errors=errors,
        transcript_adapter=adapter,
        extraction_service=extractor,
        today=lambda: date(2026, 8, 15),
    )
    return service, repos, inbox, adapter


def test_discovered_item_creates_one_untrusted_publication_draft_and_dry_run_writes_nothing(tmp_path: Path) -> None:
    service, repos, inbox, _ = _setup(tmp_path)
    item = _item()
    _write_item(inbox, item)

    planned = service.process(item["id"], dry_run=True)
    assert planned.state == "discovered"
    assert planned.parent_resolution.status == "would_create_draft"
    assert not (inbox / "evidence").exists()

    created = service.process(item["id"])
    drafts = list((inbox / "evidence").glob("*.json"))
    assert created.state == "awaiting_publication_review"
    assert len(drafts) == 1
    draft = json.loads(drafts[0].read_text(encoding="utf-8"))
    assert draft["id"] == publication_draft_id(item)
    assert draft["evidence_role"] == "publication_artifact"
    assert draft["status"] == "draft" and draft["review_state"] == "in_review"
    assert draft["source_id"] == SOURCE_ID and draft["media_format"] == "podcast"
    assert draft["entity_ids"] == draft["geography_ids"] == draft["berry_ids"] == []
    assert repos.evidence.list() == []


def test_repeated_orchestration_does_not_duplicate_pending_or_rejected_draft(tmp_path: Path) -> None:
    service, _, inbox, _ = _setup(tmp_path)
    item = _item()
    _write_item(inbox, item)
    first = service.process(item["id"])
    second = service.process(item["id"])
    assert first.publication_draft_id == second.publication_draft_id
    assert second.parent_resolution.status == "pending_draft"
    assert len(list((inbox / "evidence").glob("*.json"))) == 1

    path = inbox / "evidence" / f"{first.publication_draft_id}.json"
    rejected = json.loads(path.read_text(encoding="utf-8"))
    rejected.update(status="rejected", review_state="rejected")
    path.write_text(json.dumps(rejected), encoding="utf-8")
    third = service.process(item["id"])
    assert third.state == "publication_rejected"
    assert len(list((inbox / "evidence").glob("*.json"))) == 1


def test_existing_trusted_publication_suppresses_duplicate_draft(tmp_path: Path) -> None:
    service, repos, inbox, _ = _setup(tmp_path)
    item = _item()
    _write_item(inbox, item)
    repos.evidence.create(_parent(item))
    result = service.process(item["id"])
    assert result.parent_resolution.status == "trusted"
    assert result.state == "publication_approved"
    assert result.transcript_status == "missing"
    assert not (inbox / "evidence").exists()


def test_ambiguous_trusted_matches_block_resolution_and_writes(tmp_path: Path) -> None:
    service, repos, inbox, _ = _setup(tmp_path)
    item = _item(
        canonical_url="https://example.invalid/not-an-exact-match",
        possible_evidence_matches=[{"evidence_id": "ev-match-one"}, {"evidence_id": "ev-match-two"}],
    )
    _write_item(inbox, item)
    repos.evidence.create(_parent(item, "ev-match-one"))
    repos.evidence.create(_parent(item, "ev-match-two"))
    result = service.process(item["id"])
    assert result.parent_resolution.status == "ambiguous"
    assert result.errors
    assert not (inbox / "evidence").exists()


def test_transcript_can_exist_before_approval_without_extraction_or_retranscription(tmp_path: Path) -> None:
    service, repos, inbox, adapter = _setup(
        tmp_path,
        transcript=_transcript(),
        extraction=True,
        candidates=[{"normalized_statement": "The trial may expand.", "segment_indexes": [1]}],
    )
    item = _item()
    _write_item(inbox, item)
    result = service.process(item["id"])
    assert result.state == "awaiting_publication_review"
    assert result.transcript_status == "ready"
    assert adapter.calls == 1
    assert repos.evidence.list() == []
    assert len(list((inbox / "evidence").glob("*.json"))) == 1


def test_parent_binding_changes_only_metadata_and_preserves_content_hash(tmp_path: Path) -> None:
    service, repos, _, _ = _setup(tmp_path)
    item = _item()
    parent = _parent(item)
    repos.evidence.create(parent)
    payload = _transcript()
    before = deepcopy(payload)
    bound = service.bind_transcript(payload, parent["id"])
    assert payload == before
    assert bound.parent_evidence_id == parent["id"]
    rebound = service.bind_transcript(payload, parent["id"])
    assert rebound.content_sha256() == bound.content_sha256()


def test_existing_human_review_publishes_draft_then_parent_resolution_unlocks_extraction(
    tmp_path: Path, monkeypatch
) -> None:
    service, repos, inbox, _ = _setup(tmp_path, transcript=_transcript())
    item = _item()
    _write_item(inbox, item)
    created = service.process(item["id"])
    monkeypatch.setattr(main, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(main, "INBOX_DIR", inbox)
    response = TestClient(app).post(
        f"/review/{created.publication_draft_id}/publish",
        data={
            "title": item["title"],
            "source_type": "industry_podcast",
            "source_name": "Fixture Publisher",
            "source_url": item["canonical_url"],
            "published_date": item["published_date"],
            "captured_date": "2026-08-15",
            "summary": "Human-approved fixture publication.",
            "reviewer": "fixture reviewer",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    trusted = repos.evidence.get(created.publication_draft_id)
    assert trusted["status"] == trusted["review_state"] == "published"
    assert trusted["evidence_role"] == "publication_artifact"
    assert trusted["discovered_item_id"] == item["id"]
    assert trusted["discovery_provenance"]["dedupe_key"] == item["dedupe_key"]
    assert not (inbox / "evidence" / f"{created.publication_draft_id}.json").exists()

    resumed = service.process(item["id"])
    assert resumed.state == "ready_for_extraction"
    assert resumed.parent_resolution.evidence_id == trusted["id"]


def test_approved_publication_and_valid_transcript_are_extraction_eligible(tmp_path: Path) -> None:
    service, repos, inbox, _ = _setup(tmp_path, transcript=_transcript())
    item = _item()
    _write_item(inbox, item)
    repos.evidence.create(_parent(item))
    result = service.process(item["id"])
    assert result.state == "ready_for_extraction"
    assert result.transcript_status == "ready"
    assert result.transcript_id == "transcript-orchestration-fixture"
    assert len(result.transcript_sha256 or "") == 64
    assert not (inbox / "evidence").exists()


def test_valid_parent_invokes_existing_extractor_and_creates_only_untrusted_proposal(tmp_path: Path) -> None:
    service, repos, inbox, _ = _setup(
        tmp_path,
        transcript=_transcript(),
        extraction=True,
        candidates=[{"normalized_statement": "The trial may expand.", "segment_indexes": [1]}],
    )
    item = _item()
    _write_item(inbox, item)
    parent = repos.evidence.create(_parent(item))
    before_evidence = deepcopy(repos.evidence.list())
    result = service.process(item["id"])
    assert result.state == "extraction_complete"
    assert result.extraction["accepted"] == 1
    proposals = [json.loads(path.read_text(encoding="utf-8")) for path in (inbox / "evidence").glob("*.json")]
    assert len(proposals) == 1
    assert proposals[0]["parent_evidence_id"] == parent["id"]
    assert proposals[0]["status"] == "draft" and proposals[0]["review_state"] == "in_review"
    assert repos.evidence.list() == before_evidence
    assert repos.facts.list() == []
    assert repos.assessments.list() == []
    assert repos.recommendations.list() == []


def test_repeated_extraction_and_rejected_proposal_remain_idempotent(tmp_path: Path) -> None:
    service, repos, inbox, _ = _setup(
        tmp_path,
        transcript=_transcript(),
        extraction=True,
        candidates=[{"normalized_statement": "The trial may expand.", "segment_indexes": [1]}],
    )
    item = _item()
    _write_item(inbox, item)
    repos.evidence.create(_parent(item))
    first = service.process(item["id"])
    second = service.process(item["id"])
    assert first.extraction["accepted"] == 1
    assert second.extraction["accepted"] == 0 and second.extraction["duplicates"] == 1
    path = next((inbox / "evidence").glob("*.json"))
    rejected = json.loads(path.read_text(encoding="utf-8"))
    rejected.update(status="rejected", review_state="rejected")
    path.write_text(json.dumps(rejected), encoding="utf-8")
    third = service.process(item["id"])
    assert third.extraction["duplicates"] == 1
    assert len(list((inbox / "evidence").glob("*.json"))) == 1


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        (None, "missing"),
        ({"transcript_id": "bad"}, "malformed"),
    ],
)
def test_missing_or_malformed_transcript_is_explicitly_blocked(tmp_path: Path, payload, expected: str) -> None:
    service, repos, inbox, _ = _setup(tmp_path, transcript=payload, extraction=True)
    item = _item()
    _write_item(inbox, item)
    repos.evidence.create(_parent(item))
    result = service.process(item["id"])
    assert result.state == "publication_approved"
    assert result.transcript_status == expected
    assert not (inbox / "evidence").exists()


def test_transcript_parent_mismatch_blocks_extraction(tmp_path: Path) -> None:
    service, repos, inbox, _ = _setup(
        tmp_path,
        transcript=_transcript(parent_evidence_id="ev-some-other-parent"),
        extraction=True,
    )
    item = _item()
    _write_item(inbox, item)
    repos.evidence.create(_parent(item))
    result = service.process(item["id"])
    assert result.transcript_status == "malformed"
    assert "parent mismatch" in result.errors[0]
    assert not (inbox / "evidence").exists()


def test_unresolved_source_and_malformed_staged_item_report_operator_action(tmp_path: Path) -> None:
    service, _, inbox, _ = _setup(tmp_path)
    missing_source = _item(source_id="source-missing")
    _write_item(inbox, missing_source)
    result = service.process(missing_source["id"])
    assert "Source ID does not resolve" in result.errors[0]

    malformed = _item(item_id="media-malformed")
    malformed.pop("dedupe_key")
    _write_item(inbox, malformed)
    with pytest.raises(MediaOrchestrationError, match="dedupe_key"):
        service.process(malformed["id"])


def test_real_lucentlands_match_resolves_existing_publication_without_writes(tmp_path: Path) -> None:
    live_repos = main.get_repositories(main.DATA_DIR, main.SCHEMAS_DIR)
    parent_id = "ev-lucentlands-scaling-blueberry-industry-2025"
    assert live_repos.evidence.get(parent_id)["evidence_role"] == "publication_artifact"
    item = _item(
        item_id="media-real-lucentlands-fixture",
        source_id="source-lucentlands-podcast",
        possible_evidence_matches=[{"evidence_id": parent_id, "reasons": ["title_match"]}],
        canonical_url="https://example.invalid/feed-link-can-differ",
    )
    inbox = tmp_path / "inbox"
    _write_item(inbox, item)
    validator = main.get_validator("evidence.schema.json")
    service = MediaOrchestrationService(
        repositories=live_repos,
        inbox_dir=inbox,
        evidence_errors=lambda record: [error.message for error in validator.iter_errors(record)],
        transcript_adapter=CountingTranscriptAdapter(None),
    )
    result = service.process(item["id"])
    assert result.parent_resolution.evidence_id == parent_id
    assert result.state == "publication_approved"
    assert not (inbox / "evidence").exists()


def test_generic_mapping_is_source_and_company_symmetric(tmp_path: Path) -> None:
    service, repos, _, _ = _setup(tmp_path)
    repos.sources.create({"id": "source-unrelated", "name": "Unrelated Publisher"})
    first = _item()
    second = _item(
        item_id="media-unrelated",
        source_id="source-unrelated",
        dedupe_key="unrelated-episode",
        external_id="unrelated-episode",
        title="Unrelated episode",
        canonical_url="https://unrelated.invalid/episode",
    )
    draft_a = service._draft_from_item(first, repos.sources.get(SOURCE_ID))
    draft_b = service._draft_from_item(second, repos.sources.get("source-unrelated"))
    for draft in (draft_a, draft_b):
        assert draft["entity_ids"] == []
        assert draft["berry_ids"] == []
        assert draft["geography_ids"] == []
        assert "company" not in draft


def test_operator_cli_dry_run_reports_plan_without_writing(tmp_path: Path, monkeypatch, capsys) -> None:
    data_dir = tmp_path / "data"
    inbox = tmp_path / "inbox"
    repos = main.get_repositories(data_dir, main.SCHEMAS_DIR)
    repos.sources.create({"id": SOURCE_ID, "name": "Fixture Publisher"})
    item = _item()
    _write_item(inbox, item)
    monkeypatch.setattr(
        "sys.argv",
        [
            "process_discovered_media.py",
            "--item",
            item["id"],
            "--dry-run",
            "--data-dir",
            str(data_dir),
            "--inbox-dir",
            str(inbox),
        ],
    )
    assert process_discovered_media.main() == 0
    output = json.loads(capsys.readouterr().out)
    assert output["dry_run"] is True
    assert output["parent_resolution"]["status"] == "would_create_draft"
    assert not (inbox / "evidence").exists()
