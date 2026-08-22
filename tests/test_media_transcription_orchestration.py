"""Offline integration tests for Claude transcription + Codex orchestration."""

from __future__ import annotations

from copy import deepcopy
from datetime import date
import json
from pathlib import Path

import pytest

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


def _youtube_item(item_id: str = "discovered-youtube-orchestration") -> dict:
    video_id = "platform-video-123"
    return {
        **_item(item_id),
        "external_id": None,
        "platform_item_id": video_id,
        "dedupe_strategy": "platform_item_id",
        "dedupe_key": video_id,
        "canonical_url": f"https://video.example.invalid/watch?v={video_id}",
        "media_format": "video",
        "transcript_availability": {"status": "unknown"},
        "raw_metadata": {"yt_video_id": video_id},
    }


def _cached_payload(
    item: dict, *, tier: str, language: str = "en", language_requested: str | None = None
) -> dict:
    acquisition = {
        "tier": tier,
        "source_fingerprint": media_transcription.resolve_acquisition_fingerprint(item),
        "media_url": item.get("canonical_url") if tier == "tier_3_local_speech_to_text" else None,
        "media_checksum_sha256": "a" * 64 if tier == "tier_3_local_speech_to_text" else None,
        "model": "small" if tier == "tier_3_local_speech_to_text" else None,
        "language_requested": language_requested,
    }
    return media_transcription.normalize_transcript(
        item=item,
        segments=[{"text": "The trial may expand.", "start_seconds": 20, "end_seconds": 24}],
        language=language,
        method="auto_generated",
        created_by="fixture",
        created_at="2026-08-15",
        parent_evidence_id=None,
        acquisition=acquisition,
    )


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


@pytest.mark.parametrize(
    ("source_id", "enclosure"),
    [
        ("source-lucentlands", "https://anchor.invalid/episode.mp3"),
        ("source-business-of-blueberries", "https://captivate.invalid/episode.mp3"),
    ],
)
def test_rss_cache_fingerprint_is_host_neutral_and_invalidates_changed_enclosure(
    tmp_path: Path, source_id: str, enclosure: str
) -> None:
    item = _item(f"discovered-{source_id}")
    item["source_id"] = source_id
    item["raw_metadata"]["enclosures"] = [{"url": enclosure, "type": "audio/mpeg"}]
    payload = _cached_payload(item, tier="tier_3_local_speech_to_text")
    assert payload["acquisition"]["source_fingerprint"] == {
        "kind": "media_enclosure",
        "value": enclosure,
    }
    assert media_transcription.transcript_cache_matches_request(
        tmp_path / "inbox", payload, item, model="small", language=None
    )

    changed = deepcopy(item)
    changed["raw_metadata"]["enclosures"][0]["url"] = enclosure + "?revision=2"
    assert not media_transcription.transcript_cache_matches_request(
        tmp_path / "inbox", payload, changed, model="small", language=None
    )


def test_tier3_cache_invalidates_changed_local_checksum_language_model_and_force(
    tmp_path: Path,
) -> None:
    inbox = tmp_path / "inbox"
    item = _item()
    payload = _cached_payload(item, tier="tier_3_local_speech_to_text")
    media_folder = media_transcription.media_dir(inbox)
    media_folder.mkdir(parents=True)
    (media_folder / f"{item['id']}.meta.json").write_text(
        json.dumps({"checksum_sha256": "b" * 64}), encoding="utf-8"
    )

    assert not media_transcription.transcript_cache_matches_request(
        inbox, payload, item, model="small", language=None
    )
    assert not media_transcription.transcript_cache_matches_request(
        tmp_path / "without-sidecar", payload, item, model="medium", language=None
    )
    assert not media_transcription.transcript_cache_matches_request(
        tmp_path / "without-sidecar", payload, item, model="small", language="en"
    )
    assert not media_transcription.transcript_cache_matches_request(
        tmp_path / "without-sidecar", payload, item, model="small", language=None, force=True
    )

    explicitly_english = _cached_payload(
        item,
        tier="tier_3_local_speech_to_text",
        language_requested="en",
    )
    assert not media_transcription.transcript_cache_matches_request(
        tmp_path / "without-sidecar", explicitly_english, item, model="small", language=None
    )


@pytest.mark.parametrize(
    ("tier", "language"),
    [
        ("tier_2_youtube_auto_captions", "es"),
        ("tier_2_youtube_human_captions", "en"),
    ],
)
def test_youtube_caption_cache_reuses_platform_identity_without_acquisition(
    monkeypatch, tmp_path: Path, tier: str, language: str
) -> None:
    inbox = tmp_path / "inbox"
    item = _youtube_item()
    payload = _cached_payload(
        item, tier=tier, language=language, language_requested=language
    )
    media_transcription.write_transcript_artifact(inbox, payload)
    monkeypatch.setattr(
        media_transcription,
        "transcribe_discovered_item",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("valid caption cache must not be reacquired")
        ),
    )

    adapter = MediaTranscriptionAdapter(inbox, language=language)
    assert adapter.load(item) == payload
    assert adapter.load(item) == payload


def test_youtube_tier3_parent_binding_and_extraction_reruns_never_invoke_stt(
    monkeypatch, tmp_path: Path
) -> None:
    repos, inbox, errors = _setup(tmp_path)
    item = _youtube_item()
    _write_item(inbox, item)
    parent = _parent(item)
    parent["media_format"] = "video"
    parent["source_url"] = item["canonical_url"]
    repos.evidence.create(parent)
    payload = _cached_payload(item, tier="tier_3_local_speech_to_text")
    before_segments = deepcopy(payload["segments"])
    media_transcription.write_transcript_artifact(inbox, payload)
    monkeypatch.setattr(
        media_transcription,
        "transcribe_discovered_item",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("parent binding/extraction rerun must not invoke STT")
        ),
    )
    extractor = TranscriptEvidenceExtractionService(
        repositories=repos,
        inbox_dir=inbox,
        evidence_errors=errors,
        provider=StructuredCandidateProvider(
            [{"normalized_statement": "The trial may expand.", "segment_indexes": [0]}],
            name="fixture extractor",
            method="ai_assisted",
        ),
        today=lambda: date(2026, 8, 15),
    )
    service = _service(repos, inbox, errors, MediaTranscriptionAdapter(inbox), extractor)

    first = service.process(item["id"])
    second = service.process(item["id"])
    assert first.state == second.state == "extraction_complete"
    assert first.extraction["accepted"] == 1
    assert second.extraction["accepted"] == 0
    assert media_transcription.load_transcript_artifact(inbox, item["id"])["segments"] == before_segments


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
