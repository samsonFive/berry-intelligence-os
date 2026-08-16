"""Media acquisition + local speech-to-text tests
(app/services/media_transcription.py) -- upstream of the Evidence trust
boundary, downstream of media_discovery.py's staging layer.

Entirely offline: every network call is mocked via
`monkeypatch.setattr(media_transcription.httpx, "get", ...)`, mirroring
tests/test_media_discovery.py's own established convention. Every
TranscriptionProvider is a deterministic fake (`_FakeProvider` below) -- no
real Whisper model is ever loaded or downloaded by this file. No test
touches the live `data/` dataset; repositories are built via
get_repositories() pointed at tmp_path, per this project's "no fictional
intelligence in the live dataset" discipline.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pytest

from app.composition import get_repositories
from app.repositories.paths import SCHEMAS_DIR
from app.services import media_discovery, media_transcription as mt
from app.services.transcript_evidence import TranscriptArtifact, TranscriptContractError

SOURCE_ID = "source-media-transcription-test-podcast"
PARENT_EVIDENCE_ID = "ev-media-transcription-test-parent"


# ---------------------------------------------------------------------------
# fixtures / fakes
# ---------------------------------------------------------------------------


class _FakeHttpResponse:
    def __init__(self, content: bytes, status: int = 200, content_type: str = "audio/mpeg") -> None:
        self.content = content
        self.text = content.decode("utf-8", errors="replace")
        self.status_code = status
        self.headers = {"content-type": content_type}

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("error", request=None, response=self)  # type: ignore[arg-type]


def _discovered_item(
    suffix: str = "ep1",
    *,
    status: str = media_discovery.TRANSCRIPT_NOT_DETECTED,
    transcript_url: str | None = None,
    declared_type: str | None = None,
    transcript_language: str | None = None,
    enclosure_url: str | None = "https://example.invalid/audio-ep1.mp3",
    enclosure_type: str = "audio/mpeg",
    duration_seconds: int | None = 300,
) -> dict[str, Any]:
    availability: dict[str, Any] = {
        "status": status,
        "checked_at": "2026-08-15T00:00:00+00:00",
        "url": transcript_url,
        "language": transcript_language,
    }
    if declared_type:
        availability["declared_type"] = declared_type
    enclosures = [{"url": enclosure_url, "type": enclosure_type, "length_bytes": 12345}] if enclosure_url else []
    return {
        "id": f"discovered-test-{suffix}",
        "record_type": "discovered_media_item",
        "source_id": SOURCE_ID,
        "title": f"Test Episode {suffix}",
        "canonical_url": f"https://example.invalid/{suffix}",
        "external_id": f"guid-{suffix}",
        "published_date": "2025-10-28",
        "duration_seconds": duration_seconds,
        "transcript_availability": availability,
        "raw_metadata": {"enclosures": enclosures},
    }


class _FakeProvider:
    """A deterministic TranscriptionProvider stand-in. Never loads a real
    model, never touches the network or filesystem beyond recording which
    media_path it was called with."""

    name = "fake-engine"

    def __init__(
        self,
        *,
        model_name: str = "fake-model",
        segments: list[mt.RawSegment] | None = None,
        language: str = "en",
        raises: Exception | None = None,
        calls: list[Path] | None = None,
    ) -> None:
        self.model_name = model_name
        self._segments = segments if segments is not None else [
            mt.RawSegment(text="Hello and welcome to the show.", start_seconds=0.0, end_seconds=2.5),
            mt.RawSegment(text="Today we discuss blueberries.", start_seconds=2.5, end_seconds=5.0),
        ]
        self._language = language
        self._raises = raises
        self.calls = calls if calls is not None else []

    def transcribe(self, media_path: Path, *, language: str | None = None) -> mt.RawTranscription:
        self.calls.append(media_path)
        if self._raises is not None:
            raise self._raises
        return mt.RawTranscription(
            segments=tuple(self._segments),
            detected_language=self._language,
            engine=self.name,
            engine_version="0.0-test",
            model=self.model_name,
            device="cpu",
            duration_seconds=5.0,
        )


@pytest.fixture
def repos(tmp_path: Path):
    return get_repositories(tmp_path, SCHEMAS_DIR)


def _mock_audio_get(monkeypatch, content: bytes = b"FAKE-MP3-BYTES", status: int = 200, content_type: str = "audio/mpeg") -> None:
    monkeypatch.setattr(mt.httpx, "get", lambda *a, **k: _FakeHttpResponse(content, status=status, content_type=content_type))


# ---------------------------------------------------------------------------
# 1: publisher transcript preferred when available (Tier 1)
# ---------------------------------------------------------------------------


def test_publisher_transcript_preferred_when_available(tmp_path: Path, monkeypatch) -> None:
    item = _discovered_item(status=media_discovery.TRANSCRIPT_PUBLISHER, transcript_url="https://example.invalid/ep1.vtt", transcript_language="en")
    vtt = "WEBVTT\n\n00:00:00.000 --> 00:00:02.000\nHello and welcome.\n\n00:00:02.000 --> 00:00:04.500\nThis is the publisher transcript.\n"
    monkeypatch.setattr(media_discovery.httpx, "get", lambda *a, **k: _FakeHttpResponse(vtt.encode("utf-8"), content_type="text/vtt"))
    provider = _FakeProvider()

    outcome = mt.transcribe_discovered_item(tmp_path / "inbox", item, provider_factory=lambda: provider, parent_evidence_id=PARENT_EVIDENCE_ID)

    assert outcome.status == "ok"
    assert outcome.tier == "tier_1_publisher_transcript"
    assert outcome.segment_count == 2
    assert provider.calls == []  # local STT never invoked when Tier 1 succeeds


# ---------------------------------------------------------------------------
# 2: platform captions preferred over local transcription when appropriate
# ---------------------------------------------------------------------------


def test_platform_captions_normalization_never_invokes_local_transcription(tmp_path: Path) -> None:
    vtt = "WEBVTT\n\n00:00:00.000 --> 00:00:03.000\nMachine generated caption text.\n"
    segments, method = mt.normalize_platform_captions(vtt, human_created=False)
    assert method == "auto_generated"
    assert segments[0]["text"] == "Machine generated caption text."
    # normalize_platform_captions() is a pure function -- no provider, no
    # network, no filesystem write -- structurally cannot fall back to Tier 3.


def test_human_authored_platform_captions_map_to_publisher_provided(tmp_path: Path) -> None:
    vtt = "WEBVTT\n\n00:00:00.000 --> 00:00:03.000\nHuman-authored caption text.\n"
    segments, method = mt.normalize_platform_captions(vtt, human_created=True)
    assert method == "publisher_provided"


def test_platform_captions_status_without_supplied_document_falls_through_to_local(tmp_path: Path, monkeypatch) -> None:
    """This phase does not auto-discover platform captions (would require
    credentials or scraping -- see module docstring); an item flagged
    platform_captions but with no already-obtained document falls through
    to Tier 3 exactly like not_detected, and this is recorded, not silent."""
    item = _discovered_item(status=media_discovery.TRANSCRIPT_PLATFORM_CAPTIONS)
    _mock_audio_get(monkeypatch)
    provider = _FakeProvider()

    outcome = mt.transcribe_discovered_item(tmp_path / "inbox", item, provider_factory=lambda: provider)

    assert outcome.status == "ok"
    assert outcome.tier == "tier_3_local_speech_to_text"
    assert len(provider.calls) == 1


# ---------------------------------------------------------------------------
# 3: local transcription used when no transcript/captions exist (Tier 3)
# ---------------------------------------------------------------------------


def test_local_transcription_used_when_no_transcript_or_captions_exist(tmp_path: Path, monkeypatch) -> None:
    item = _discovered_item(status=media_discovery.TRANSCRIPT_NOT_DETECTED)
    _mock_audio_get(monkeypatch)
    provider = _FakeProvider()

    outcome = mt.transcribe_discovered_item(tmp_path / "inbox", item, provider_factory=lambda: provider)

    assert outcome.status == "ok"
    assert outcome.tier == "tier_3_local_speech_to_text"
    assert len(provider.calls) == 1


# ---------------------------------------------------------------------------
# 4: raw media stored outside trusted data/
# ---------------------------------------------------------------------------


def test_raw_media_stored_outside_trusted_data_dir(tmp_path: Path, monkeypatch) -> None:
    item = _discovered_item()
    _mock_audio_get(monkeypatch)
    inbox_dir = tmp_path / "inbox"
    data_dir = tmp_path / "data"

    acquired = mt.acquire_media(inbox_dir, item)

    assert str(acquired.path).startswith(str(inbox_dir))
    assert not str(acquired.path).startswith(str(data_dir))
    assert acquired.path.exists()
    assert not (data_dir).exists()


# ---------------------------------------------------------------------------
# 5: normalized timestamped segments produced correctly
# ---------------------------------------------------------------------------


def test_normalized_timestamped_segments_produced_correctly(tmp_path: Path, monkeypatch) -> None:
    item = _discovered_item()
    _mock_audio_get(monkeypatch)
    segments = [
        mt.RawSegment(text="First segment text.", start_seconds=0.0, end_seconds=1.2),
        mt.RawSegment(text="Second segment text.", start_seconds=1.2, end_seconds=3.4),
    ]
    provider = _FakeProvider(segments=segments)

    outcome = mt.transcribe_discovered_item(tmp_path / "inbox", item, provider_factory=lambda: provider)

    payload = json.loads(outcome.output_path.read_text(encoding="utf-8"))
    assert [s["text"] for s in payload["segments"]] == ["First segment text.", "Second segment text."]
    assert [s["start_seconds"] for s in payload["segments"]] == [0.0, 1.2]
    assert [s["end_seconds"] for s in payload["segments"]] == [1.2, 3.4]


# ---------------------------------------------------------------------------
# 6: speaker labels never invented
# ---------------------------------------------------------------------------


def test_speaker_labels_never_invented_from_local_transcription(tmp_path: Path, monkeypatch) -> None:
    item = _discovered_item()
    _mock_audio_get(monkeypatch)
    provider = _FakeProvider()

    outcome = mt.transcribe_discovered_item(tmp_path / "inbox", item, provider_factory=lambda: provider)

    payload = json.loads(outcome.output_path.read_text(encoding="utf-8"))
    assert all(segment["speaker_label"] is None for segment in payload["segments"])


# ---------------------------------------------------------------------------
# 7: language retained
# ---------------------------------------------------------------------------


def test_detected_language_is_retained(tmp_path: Path, monkeypatch) -> None:
    item = _discovered_item()
    _mock_audio_get(monkeypatch)
    provider = _FakeProvider(language="af")

    outcome = mt.transcribe_discovered_item(tmp_path / "inbox", item, provider_factory=lambda: provider)

    assert outcome.detected_language == "af"
    payload = json.loads(outcome.output_path.read_text(encoding="utf-8"))
    assert payload["language"] == "af"


# ---------------------------------------------------------------------------
# 8: transcription provenance retained
# ---------------------------------------------------------------------------


def test_transcription_provenance_is_retained(tmp_path: Path, monkeypatch) -> None:
    item = _discovered_item()
    _mock_audio_get(monkeypatch)
    provider = _FakeProvider(model_name="small")

    outcome = mt.transcribe_discovered_item(tmp_path / "inbox", item, provider_factory=lambda: provider)

    payload = json.loads(outcome.output_path.read_text(encoding="utf-8"))
    assert payload["provenance"]["method"] == "auto_generated"
    assert payload["provenance"]["created_by"]
    assert payload["provenance"]["created_at"]
    acquisition = payload["acquisition"]
    assert acquisition["engine"] == "fake-engine"
    assert acquisition["model"] == "small"
    assert acquisition["device"] == "cpu"
    assert acquisition["media_url"] == item["raw_metadata"]["enclosures"][0]["url"]
    assert acquisition["media_checksum_sha256"]


# ---------------------------------------------------------------------------
# 9: media acquisition failure does not produce a valid-looking artifact
# ---------------------------------------------------------------------------


def test_media_acquisition_failure_produces_no_transcript_file(tmp_path: Path, monkeypatch) -> None:
    item = _discovered_item()

    def _raise(*args, **kwargs):
        raise httpx.ConnectError("simulated network failure")

    monkeypatch.setattr(mt.httpx, "get", _raise)
    provider = _FakeProvider()

    outcome = mt.transcribe_discovered_item(tmp_path / "inbox", item, provider_factory=lambda: provider)

    assert outcome.status == "error"
    assert "simulated network failure" in outcome.error
    assert provider.calls == []
    assert not mt.transcripts_dir(tmp_path / "inbox").exists()


def test_missing_enclosure_url_fails_cleanly(tmp_path: Path) -> None:
    item = _discovered_item(enclosure_url=None)
    with pytest.raises(mt.MediaAcquisitionError):
        mt.acquire_media(tmp_path / "inbox", item)


# ---------------------------------------------------------------------------
# 10: malformed transcript/captions input fails cleanly
# ---------------------------------------------------------------------------


def test_malformed_publisher_transcript_fails_cleanly(tmp_path: Path, monkeypatch) -> None:
    item = _discovered_item(status=media_discovery.TRANSCRIPT_PUBLISHER, transcript_url="https://example.invalid/ep1.vtt")
    garbage = "This is just prose with no timestamps or cue markers at all."
    monkeypatch.setattr(media_discovery.httpx, "get", lambda *a, **k: _FakeHttpResponse(garbage.encode("utf-8"), content_type="text/plain"))
    provider = _FakeProvider()

    outcome = mt.transcribe_discovered_item(tmp_path / "inbox", item, provider_factory=lambda: provider)

    assert outcome.status == "error"
    assert outcome.tier == "tier_1_publisher_transcript"
    assert provider.calls == []
    assert not mt.transcripts_dir(tmp_path / "inbox").exists()


def test_parse_timed_text_captions_rejects_empty_body() -> None:
    with pytest.raises(mt.RawTranscriptParseError):
        mt.parse_timed_text_captions("")


def test_parse_timed_text_captions_supports_srt_format() -> None:
    srt = "1\n00:00:00,000 --> 00:00:02,000\nHello from SRT.\n\n2\n00:00:02,000 --> 00:00:04,000\nSecond SRT cue.\n"
    segments = mt.parse_timed_text_captions(srt)
    assert [s["text"] for s in segments] == ["Hello from SRT.", "Second SRT cue."]
    assert segments[0]["start_seconds"] == 0.0
    assert segments[1]["end_seconds"] == 4.0


# ---------------------------------------------------------------------------
# 11-14: idempotency / cache behavior
# ---------------------------------------------------------------------------


def test_repeated_identical_transcription_reuses_cache(tmp_path: Path) -> None:
    calls: list[Path] = []
    provider = _FakeProvider(calls=calls)
    media_path = tmp_path / "audio.mp3"
    media_path.write_bytes(b"fake audio bytes")
    item = _discovered_item()

    _, hit1 = mt.transcribe_media(tmp_path / "inbox", media_path, item=item, provider=provider, media_checksum_sha256="checksum-a")
    _, hit2 = mt.transcribe_media(tmp_path / "inbox", media_path, item=item, provider=provider, media_checksum_sha256="checksum-a")

    assert hit1 is False
    assert hit2 is True
    assert len(calls) == 1


def test_media_checksum_change_invalidates_cache(tmp_path: Path) -> None:
    calls: list[Path] = []
    provider = _FakeProvider(calls=calls)
    media_path = tmp_path / "audio.mp3"
    media_path.write_bytes(b"fake audio bytes")
    item = _discovered_item()

    mt.transcribe_media(tmp_path / "inbox", media_path, item=item, provider=provider, media_checksum_sha256="checksum-a")
    _, hit2 = mt.transcribe_media(tmp_path / "inbox", media_path, item=item, provider=provider, media_checksum_sha256="checksum-b")

    assert hit2 is False
    assert len(calls) == 2


def test_model_change_invalidates_cache(tmp_path: Path) -> None:
    calls: list[Path] = []
    media_path = tmp_path / "audio.mp3"
    media_path.write_bytes(b"fake audio bytes")
    item = _discovered_item()

    provider_small = _FakeProvider(model_name="small", calls=calls)
    mt.transcribe_media(tmp_path / "inbox", media_path, item=item, provider=provider_small, media_checksum_sha256="checksum-a")

    provider_medium = _FakeProvider(model_name="medium", calls=calls)
    _, hit2 = mt.transcribe_media(tmp_path / "inbox", media_path, item=item, provider=provider_medium, media_checksum_sha256="checksum-a")

    assert hit2 is False
    assert len(calls) == 2


def test_force_bypasses_cache(tmp_path: Path) -> None:
    calls: list[Path] = []
    provider = _FakeProvider(calls=calls)
    media_path = tmp_path / "audio.mp3"
    media_path.write_bytes(b"fake audio bytes")
    item = _discovered_item()

    mt.transcribe_media(tmp_path / "inbox", media_path, item=item, provider=provider, media_checksum_sha256="checksum-a")
    _, hit2 = mt.transcribe_media(tmp_path / "inbox", media_path, item=item, provider=provider, media_checksum_sha256="checksum-a", force=True)

    assert hit2 is False
    assert len(calls) == 2


def test_media_download_is_reused_when_url_unchanged(tmp_path: Path, monkeypatch) -> None:
    item = _discovered_item()
    calls = {"n": 0}

    def _get(*args, **kwargs):
        calls["n"] += 1
        return _FakeHttpResponse(b"fake audio bytes")

    monkeypatch.setattr(mt.httpx, "get", _get)
    first = mt.acquire_media(tmp_path / "inbox", item)
    second = mt.acquire_media(tmp_path / "inbox", item)

    assert calls["n"] == 1
    assert first.reused_cache is False
    assert second.reused_cache is True
    assert second.checksum_sha256 == first.checksum_sha256


# ---------------------------------------------------------------------------
# 15-16: parent Evidence resolution (Phase 12)
# ---------------------------------------------------------------------------


def test_item_can_be_transcribed_before_permanent_evidence_parent_exists(tmp_path: Path, monkeypatch) -> None:
    item = _discovered_item()
    _mock_audio_get(monkeypatch)
    provider = _FakeProvider()

    outcome = mt.transcribe_discovered_item(tmp_path / "inbox", item, provider_factory=lambda: provider, parent_evidence_id=None)

    assert outcome.status == "ok"
    payload = json.loads(outcome.output_path.read_text(encoding="utf-8"))
    assert payload["record_type"] == "staged_transcript"
    assert payload["parent_evidence_id"] is None
    # A staged transcript deliberately does NOT satisfy TranscriptArtifact.from_dict() yet.
    with pytest.raises(TranscriptContractError):
        TranscriptArtifact.from_dict(payload)


def test_resolved_transcript_matches_transcript_artifact_contract(tmp_path: Path, monkeypatch) -> None:
    item = _discovered_item()
    _mock_audio_get(monkeypatch)
    provider = _FakeProvider()
    inbox_dir = tmp_path / "inbox"

    mt.transcribe_discovered_item(inbox_dir, item, provider_factory=lambda: provider, parent_evidence_id=None)
    resolved = mt.resolve_parent_evidence(inbox_dir, item["id"], PARENT_EVIDENCE_ID)

    assert resolved["record_type"] == "transcript_artifact"
    artifact = TranscriptArtifact.from_dict(resolved)
    assert artifact.parent_evidence_id == PARENT_EVIDENCE_ID
    assert len(artifact.segments) == 2


def test_resolving_parent_evidence_does_not_retranscribe(tmp_path: Path, monkeypatch) -> None:
    """Phase 21 item 14: binding a staged transcript to a real parent
    Evidence id is a pure metadata promotion -- it must never re-invoke the
    transcription provider or change the already-produced segments/cache
    key. `resolve_parent_evidence()` only reads and rewrites the normalized
    JSON file; it never touches `transcribe_media()`'s raw STT cache at
    all, so the provider call count staying at exactly 1 (from the original
    transcription) proves no retranscription occurred."""
    item = _discovered_item()
    _mock_audio_get(monkeypatch)
    provider = _FakeProvider()
    inbox_dir = tmp_path / "inbox"

    first_outcome = mt.transcribe_discovered_item(inbox_dir, item, provider_factory=lambda: provider, parent_evidence_id=None)
    assert len(provider.calls) == 1
    raw_cache_key_before = json.loads((mt.raw_transcripts_dir(inbox_dir) / f"stt-{item['id']}.json").read_text(encoding="utf-8"))["cache_key"]

    resolved = mt.resolve_parent_evidence(inbox_dir, item["id"], PARENT_EVIDENCE_ID)

    assert len(provider.calls) == 1  # provider never called a second time
    raw_cache_key_after = json.loads((mt.raw_transcripts_dir(inbox_dir) / f"stt-{item['id']}.json").read_text(encoding="utf-8"))["cache_key"]
    assert raw_cache_key_after == raw_cache_key_before  # raw STT cache entirely untouched
    assert first_outcome.status == "ok"
    assert len(resolved["segments"]) == 2  # same segments the original (only) transcription produced


def test_transcribe_discovered_item_with_parent_upfront_matches_contract_immediately(tmp_path: Path, monkeypatch) -> None:
    item = _discovered_item()
    _mock_audio_get(monkeypatch)
    provider = _FakeProvider()

    outcome = mt.transcribe_discovered_item(tmp_path / "inbox", item, provider_factory=lambda: provider, parent_evidence_id=PARENT_EVIDENCE_ID)

    payload = json.loads(outcome.output_path.read_text(encoding="utf-8"))
    assert payload["record_type"] == "transcript_artifact"
    artifact = TranscriptArtifact.from_dict(payload)
    assert artifact.parent_evidence_id == PARENT_EVIDENCE_ID


# ---------------------------------------------------------------------------
# 17-19: this module never touches Evidence/Fact/Assessment/Recommendation
# ---------------------------------------------------------------------------


def test_no_atomic_evidence_is_automatically_proposed(tmp_path: Path, monkeypatch, repos) -> None:
    item = _discovered_item()
    _mock_audio_get(monkeypatch)
    provider = _FakeProvider()
    inbox_dir = tmp_path / "inbox"

    mt.transcribe_discovered_item(inbox_dir, item, provider_factory=lambda: provider, parent_evidence_id=PARENT_EVIDENCE_ID)

    assert not (inbox_dir / "evidence").exists()


def test_no_trusted_evidence_is_created(tmp_path: Path, monkeypatch, repos) -> None:
    item = _discovered_item()
    _mock_audio_get(monkeypatch)
    provider = _FakeProvider()
    inbox_dir = tmp_path / "inbox"

    mt.transcribe_discovered_item(inbox_dir, item, provider_factory=lambda: provider, parent_evidence_id=PARENT_EVIDENCE_ID)

    assert repos.evidence.list() == []


def test_no_fact_assessment_or_recommendation_is_created(tmp_path: Path, monkeypatch, repos) -> None:
    item = _discovered_item()
    _mock_audio_get(monkeypatch)
    provider = _FakeProvider()
    inbox_dir = tmp_path / "inbox"

    mt.transcribe_discovered_item(inbox_dir, item, provider_factory=lambda: provider, parent_evidence_id=PARENT_EVIDENCE_ID)

    assert repos.facts.list() == []
    assert repos.assessments.list() == []
    assert repos.recommendations.list() == []


# ---------------------------------------------------------------------------
# extra coverage: dependency/process failures, zero segments, diagnostics
# ---------------------------------------------------------------------------


def test_transcription_dependency_unavailable_fails_cleanly(tmp_path: Path, monkeypatch) -> None:
    item = _discovered_item()
    _mock_audio_get(monkeypatch)

    class _MissingDependencyProvider:
        name = "faster-whisper"
        model_name = "small"

        def transcribe(self, media_path: Path, *, language: str | None = None) -> mt.RawTranscription:
            raise mt.TranscriptionDependencyError("faster-whisper is not installed")

    outcome = mt.transcribe_discovered_item(tmp_path / "inbox", item, provider_factory=_MissingDependencyProvider)

    assert outcome.status == "error"
    assert "not installed" in outcome.error


def test_zero_segments_returned_is_treated_as_failure(tmp_path: Path, monkeypatch) -> None:
    item = _discovered_item()
    _mock_audio_get(monkeypatch)
    provider = _FakeProvider(raises=mt.TranscriptionError("transcription produced zero segments"))

    outcome = mt.transcribe_discovered_item(tmp_path / "inbox", item, provider_factory=lambda: provider)

    assert outcome.status == "error"
    assert not mt.transcripts_dir(tmp_path / "inbox").exists()


def test_corrupt_media_process_failure_fails_cleanly(tmp_path: Path, monkeypatch) -> None:
    item = _discovered_item()
    _mock_audio_get(monkeypatch)
    provider = _FakeProvider(raises=mt.TranscriptionError("local transcription failed: corrupt media"))

    outcome = mt.transcribe_discovered_item(tmp_path / "inbox", item, provider_factory=lambda: provider)

    assert outcome.status == "error"
    assert "corrupt media" in outcome.error


def test_diagnostics_report_segment_count_and_monotonicity(tmp_path: Path, monkeypatch) -> None:
    item = _discovered_item(duration_seconds=10)
    _mock_audio_get(monkeypatch)
    provider = _FakeProvider()

    outcome = mt.transcribe_discovered_item(tmp_path / "inbox", item, provider_factory=lambda: provider)

    assert outcome.diagnostics["segment_count"] == 2
    assert outcome.diagnostics["timestamps_monotonic"] is True
    assert outcome.diagnostics["media_duration_seconds"] == 10
    assert outcome.diagnostics["coverage_ratio"] == pytest.approx(0.5)


def test_select_enclosure_url_returns_none_without_recorded_enclosure(tmp_path: Path) -> None:
    item = _discovered_item(enclosure_url=None)
    assert mt.select_enclosure_url(item) is None


def test_select_enclosure_url_prefers_audio_or_video_typed_enclosure(tmp_path: Path) -> None:
    item = _discovered_item(enclosure_url="https://example.invalid/audio.mp3", enclosure_type="audio/mpeg")
    assert mt.select_enclosure_url(item) == "https://example.invalid/audio.mp3"


def test_resolve_parent_evidence_rejects_invalid_evidence_id(tmp_path: Path, monkeypatch) -> None:
    item = _discovered_item()
    _mock_audio_get(monkeypatch)
    provider = _FakeProvider()
    inbox_dir = tmp_path / "inbox"
    mt.transcribe_discovered_item(inbox_dir, item, provider_factory=lambda: provider)

    with pytest.raises(ValueError):
        mt.resolve_parent_evidence(inbox_dir, item["id"], "not-an-evidence-id")


def test_resolve_parent_evidence_requires_a_staged_transcript_to_exist(tmp_path: Path) -> None:
    with pytest.raises(mt.TranscriptionError):
        mt.resolve_parent_evidence(tmp_path / "inbox", "discovered-test-does-not-exist", PARENT_EVIDENCE_ID)
