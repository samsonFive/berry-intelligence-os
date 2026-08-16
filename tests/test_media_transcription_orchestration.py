"""Offline integration tests for Claude transcription + Codex orchestration."""

from __future__ import annotations

from copy import deepcopy
from datetime import date
import json
from pathlib import Path

from app import main
from app.services import media_transcription
from app.services.media_orchestration import (
    MediaOrchestrationService,
    MediaTranscriptionAdapter,
    publication_draft_id,
)
from app.services.transcript_evidence import (
    StructuredCandidateProvider,
    TranscriptArtifact,
    TranscriptEvidenceExtractionService,
)


SOURCE_ID = "source-transcription-orchestration-fixture"


class _Response:
    content = b"synthetic audio bytes"
    headers = {"content-type": "audio/mpeg"}

    def raise_for_status(self) -> None:
        return None


class _Provider:
    name = "faster-whisper"

    def __init__(self, calls: list[Path], model: str = "small") -> None:
        self.calls = calls
        self.model_name = model

    def transcribe(self, media_path: Path, *, language: str | None = None):
        self.calls.append(media_path)
        return media_transcription.RawTranscription(
            segments=(
                media_transcription.RawSegment("Welcome.", 0.0, 2.0),
                media_transcription.RawSegment("The trial may expand.", 20.0, 24.0),
            ),
            detected_language=language or "en",
            engine=self.name,
            engine_version="fixture",
            model=self.model_name,
            device="cpu",
            duration_seconds=24.0,
        )


def _item(item_id: str = "discovered-transcription-orchestration") -> dict:
    return {
        "id": item_id,
        "record_type": "discovered_media_item",
        "source_id": SOURCE_ID,
        "external_id": "episode-fixture",
        "dedupe_strategy": "external_id",
        "dedupe_key": "episode-fixture",
        "title": "Transcription integration fixture",
        "description": "Synthetic publisher description.",
        "canonical_url": "https://example.invalid/episode",
        "published_date": "2026-08-01",
        "media_format": "podcast",
        "transcript_availability": {"status": "not_detected"},
        "possible_evidence_matches": [],
        "first_seen_at": "2026-08-15T10:00:00+00:00",
        "last_seen_at": "2026-08-15T10:00:00+00:00",
        "raw_metadata": {
            "enclosures": [{"url": "https://example.invalid/audio.mp3", "type": "audio/mpeg"}]
        },
    }


def _parent(item: dict) -> dict:
    return {
        "id": publication_draft_id(item),
        "record_type": "evidence",
        "status": "published",
        "review_state": "published",
        "source_type": "industry_podcast",
        "title": item["title"],
        "source_name": "Fixture Publisher",
        "source_url": item["canonical_url"],
        "published_date": item["published_date"],
        "captured_date": "2026-08-15",
        "summary": "Human-reviewed fixture.",
        "submitted_by": "fixture reviewer",
        "source_id": item["source_id"],
        "media_format": "podcast",
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


def _setup(tmp_path: Path):
    data_dir = tmp_path / "data"
    inbox = tmp_path / "inbox"
    repos = main.get_repositories(data_dir, main.SCHEMAS_DIR)
    repos.sources.create({"id": SOURCE_ID, "name": "Fixture Publisher"})
    validator = main.get_validator("evidence.schema.json")
    errors = lambda record: [error.message for error in validator.iter_errors(record)]
    return repos, inbox, errors


def _service(repos, inbox: Path, errors, adapter, extractor=None):
    return MediaOrchestrationService(
        repositories=repos,
        inbox_dir=inbox,
        evidence_errors=errors,
        transcript_adapter=adapter,
        extraction_service=extractor,
        today=lambda: date(2026, 8, 15),
    )


def test_adapter_uses_public_normalized_loader_without_invoking_transcription(monkeypatch, tmp_path: Path) -> None:
    item = _item()
    payload = media_transcription.normalize_transcript(
        item=item,
        segments=[{"text": "Cached.", "start_seconds": 0, "end_seconds": 1}],
        language="en",
        method="auto_generated",
        created_by="faster-whisper:small",
        created_at="2026-08-15",
        parent_evidence_id=None,
        acquisition={
            "tier": "tier_3_local_speech_to_text",
            "model": "small",
            "media_url": media_transcription.select_enclosure_url(item),
        },
    )
    loads = []
    monkeypatch.setattr(
        media_transcription,
        "load_transcript_artifact",
        lambda inbox, item_id: loads.append((inbox, item_id)) or deepcopy(payload),
    )
    monkeypatch.setattr(
        media_transcription,
        "transcribe_discovered_item",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("transcription should not run")),
    )
    loaded = MediaTranscriptionAdapter(tmp_path / "inbox").load(item)
    assert loaded["transcript_id"] == payload["transcript_id"]
    assert loads == [(tmp_path / "inbox", item["id"])]


def test_actual_service_transcribes_missing_item_once_then_reuses_normalized_cache(monkeypatch, tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    item = _item()
    calls: list[Path] = []
    monkeypatch.setattr(media_transcription.httpx, "get", lambda *args, **kwargs: _Response())
    adapter = MediaTranscriptionAdapter(inbox, provider_factory=lambda: _Provider(calls))

    first = adapter.load(item)
    second = adapter.load(item)
    assert len(calls) == 1
    assert first == second
    assert first["record_type"] == "staged_transcript"
    assert first["parent_evidence_id"] is None
    assert first["provenance"]["method"] == "auto_generated"
    assert len(first["segments"]) == 2


def test_parent_binding_is_lossless_and_never_retranscribes(monkeypatch, tmp_path: Path) -> None:
    repos, inbox, errors = _setup(tmp_path)
    item = _item()
    _write_item(inbox, item)
    repos.evidence.create(_parent(item))
    calls: list[Path] = []
    monkeypatch.setattr(media_transcription.httpx, "get", lambda *args, **kwargs: _Response())
    adapter = MediaTranscriptionAdapter(inbox, provider_factory=lambda: _Provider(calls))
    staged = adapter.load(item)
    before_segments = deepcopy(staged["segments"])
    service = _service(repos, inbox, errors, adapter)

    first = service.process(item["id"])
    second = service.process(item["id"])
    assert first.state == second.state == "ready_for_extraction"
    assert len(calls) == 1
    assert media_transcription.load_transcript_artifact(inbox, item["id"])["segments"] == before_segments
    bound_payload = deepcopy(staged)
    bound_payload["parent_evidence_id"] = repos.evidence.list()[0]["id"]
    artifact = TranscriptArtifact.from_dict(bound_payload)
    assert artifact.content_sha256() == first.transcript_sha256 == second.transcript_sha256


def test_force_and_model_change_delegate_to_claude_cache_semantics(monkeypatch, tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    item = _item()
    calls: list[Path] = []
    downloads = []

    def _get(*args, **kwargs):
        downloads.append(args[0])
        return _Response()

    monkeypatch.setattr(media_transcription.httpx, "get", _get)
    MediaTranscriptionAdapter(inbox, provider_factory=lambda: _Provider(calls)).load(item)
    MediaTranscriptionAdapter(
        inbox, model="medium", provider_factory=lambda: _Provider(calls, model="medium")
    ).load(item)
    MediaTranscriptionAdapter(inbox, provider_factory=lambda: _Provider(calls), force=True).load(item)
    assert len(calls) == 3
    assert len(downloads) == 2  # initial acquisition + explicit force; model change reuses media


def test_transcription_failure_is_operator_readable_and_creates_no_evidence(tmp_path: Path) -> None:
    repos, inbox, errors = _setup(tmp_path)
    item = _item()
    item["raw_metadata"] = {"enclosures": []}
    _write_item(inbox, item)
    repos.evidence.create(_parent(item))
    result = _service(repos, inbox, errors, MediaTranscriptionAdapter(inbox)).process(item["id"])
    assert result.state == "publication_approved"
    assert result.transcript_status == "acquisition_failed"
    assert "no playable media enclosure" in result.errors[0]
    assert not (inbox / "evidence").exists()


def test_cached_transcript_and_missing_extractor_stop_at_ready_for_extraction(monkeypatch, tmp_path: Path) -> None:
    repos, inbox, errors = _setup(tmp_path)
    item = _item()
    _write_item(inbox, item)
    repos.evidence.create(_parent(item))
    calls: list[Path] = []
    monkeypatch.setattr(media_transcription.httpx, "get", lambda *args, **kwargs: _Response())
    result = _service(
        repos,
        inbox,
        errors,
        MediaTranscriptionAdapter(inbox, provider_factory=lambda: _Provider(calls)),
    ).process(item["id"])
    assert result.state == "ready_for_extraction"
    assert result.next_action == "Run the configured atomic Evidence extractor."
    assert len(calls) == 1


def test_configured_extractor_creates_only_idempotent_untrusted_proposals(monkeypatch, tmp_path: Path) -> None:
    repos, inbox, errors = _setup(tmp_path)
    item = _item()
    _write_item(inbox, item)
    parent = repos.evidence.create(_parent(item))
    trusted_before = deepcopy(repos.evidence.list())
    calls: list[Path] = []
    monkeypatch.setattr(media_transcription.httpx, "get", lambda *args, **kwargs: _Response())
    adapter = MediaTranscriptionAdapter(inbox, provider_factory=lambda: _Provider(calls))
    extractor = TranscriptEvidenceExtractionService(
        repositories=repos,
        inbox_dir=inbox,
        evidence_errors=errors,
        provider=StructuredCandidateProvider(
            [{"normalized_statement": "The trial may expand.", "segment_indexes": [1]}],
            name="fixture extractor",
            method="ai_assisted",
        ),
        today=lambda: date(2026, 8, 15),
    )
    service = _service(repos, inbox, errors, adapter, extractor)
    first = service.process(item["id"])
    second = service.process(item["id"])
    assert first.extraction["accepted"] == 1
    assert second.extraction["accepted"] == 0 and second.extraction["duplicates"] == 1
    assert second.next_action == "No new proposals were created; existing proposals remain in the review workflow."
    assert len(calls) == 1
    proposals = [json.loads(path.read_text(encoding="utf-8")) for path in (inbox / "evidence").glob("*.json")]
    assert len(proposals) == 1
    assert proposals[0]["parent_evidence_id"] == parent["id"]
    assert proposals[0]["status"] == "draft" and proposals[0]["review_state"] == "in_review"
    assert repos.evidence.list() == trusted_before
    assert repos.facts.list() == []
    assert repos.assessments.list() == []
    assert repos.recommendations.list() == []


def test_dry_run_adapter_never_transcribes_missing_media(monkeypatch, tmp_path: Path) -> None:
    item = _item()
    monkeypatch.setattr(
        media_transcription,
        "transcribe_discovered_item",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("dry-run transcribed")),
    )
    assert MediaTranscriptionAdapter(tmp_path / "inbox", transcribe_missing=False).load(item) is None
