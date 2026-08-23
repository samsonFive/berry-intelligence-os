from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from app.services.draft_delivery import (
    ALREADY_PRESENT_IDENTICAL,
    CONFLICT_DIFFERENT_CONTENT,
    DraftDeliveryError,
    NEW_DRAFT,
    SKIP_ALREADY_TRUSTED,
    SKIP_NOT_OPERATIONAL,
    SKIP_TEST_ARTIFACT,
    deliver_drafts,
    inventory,
    payload_hash,
)
from scripts.deliver_drafts import main as deliver_main


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _draft(draft_id: str, **overrides) -> dict:
    record = {
        "id": draft_id,
        "status": "draft",
        "review_state": "in_review",
        "source_url": f"https://example.test/{draft_id}",
        "submitted_by": "media-orchestration",
        "summary": "body text that must not appear in logs",
        "article": {"paragraphs": [{"index": 0, "text": "secret body"}]},
        "relevance_tier": "direct",
        "does_not_prove": [],
        "berry_ids": ["berry-raspberry"],
        "entity_ids": ["company-planasa"],
        "language": "en",
        "title": "Example title",
        "publisher_description": "publisher blurb",
        "published_date": "2026-08-20",
        "captured_date": "2026-08-20",
        "source_id": "source-example",
        "discovery_provenance": {"external_id": "https://example.test/p"},
        "ai_enrichment": {
            "suggested_berry_ids": ["berry-raspberry"],
            "suggested_entity_ids": ["company-planasa"],
            "suggested_geography_ids": [],
        },
    }
    record.update(overrides)
    return record


def test_dry_run_does_not_write(tmp_path: Path) -> None:
    source = tmp_path / "src" / "inbox"
    dest = tmp_path / "dst" / "inbox"
    _write(source / "evidence" / "ev-a.json", _draft("ev-a"))
    report = deliver_drafts(
        source_inbox=source,
        destination_inbox=dest,
        source_identity="acquisition-local",
        destination_identity="local-test",
        expected_identity="local-test",
        apply=False,
        dry_run=True,
    )
    assert report.decisions[0].outcome == NEW_DRAFT
    assert not (dest / "evidence" / "ev-a.json").exists()
    assert report.dry_run is True


def test_apply_adds_missing_draft_and_is_idempotent(tmp_path: Path) -> None:
    source = tmp_path / "src" / "inbox"
    dest = tmp_path / "dst" / "inbox"
    _write(source / "evidence" / "ev-a.json", _draft("ev-a"))
    first = deliver_drafts(
        source_inbox=source,
        destination_inbox=dest,
        source_identity="acquisition-local",
        destination_identity="local-test",
        expected_identity="local-test",
        apply=True,
        dry_run=False,
    )
    assert first.decisions[0].written is True
    copied = json.loads((dest / "evidence" / "ev-a.json").read_text(encoding="utf-8"))
    assert copied["article"]["paragraphs"][0]["text"] == "secret body"
    second = deliver_drafts(
        source_inbox=source,
        destination_inbox=dest,
        source_identity="acquisition-local",
        destination_identity="local-test",
        expected_identity="local-test",
        apply=True,
        dry_run=False,
    )
    assert second.decisions[0].outcome == ALREADY_PRESENT_IDENTICAL
    assert second.decisions[0].written is False


def test_conflict_does_not_overwrite_analyst_edits(tmp_path: Path) -> None:
    source = tmp_path / "src" / "inbox"
    dest = tmp_path / "dst" / "inbox"
    _write(source / "evidence" / "ev-a.json", _draft("ev-a", summary="new"))
    dest_record = _draft("ev-a", summary="analyst kept this", review_state="saved")
    _write(dest / "evidence" / "ev-a.json", dest_record)
    before = (dest / "evidence" / "ev-a.json").read_text(encoding="utf-8")
    report = deliver_drafts(
        source_inbox=source,
        destination_inbox=dest,
        source_identity="acquisition-local",
        destination_identity="local-test",
        expected_identity="local-test",
        apply=True,
        dry_run=False,
    )
    assert report.decisions[0].outcome == CONFLICT_DIFFERENT_CONTENT
    after = json.loads((dest / "evidence" / "ev-a.json").read_text(encoding="utf-8"))
    assert after["summary"] == "analyst kept this"
    assert after["review_state"] == "saved"
    assert (dest / "evidence" / "ev-a.json").read_text(encoding="utf-8") == before


def test_skip_already_trusted_by_id_and_url(tmp_path: Path) -> None:
    source = tmp_path / "src" / "inbox"
    dest = tmp_path / "dst" / "inbox"
    data = tmp_path / "dst" / "data"
    _write(source / "evidence" / "ev-trusted.json", _draft("ev-trusted"))
    _write(source / "evidence" / "ev-url.json", _draft("ev-url", source_url="https://example.test/same"))
    _write(data / "evidence" / "ev-trusted.json", {"id": "ev-trusted", "status": "published"})
    _write(data / "evidence" / "other.json", {"id": "other", "source_url": "https://example.test/same"})
    _write(
        source / "evidence" / "ev-canonical-url.json",
        _draft("ev-canonical-url", source_url="https://example.test/same"),
    )
    report = deliver_drafts(
        source_inbox=source,
        destination_inbox=dest,
        destination_data=data,
        source_identity="acquisition-local",
        destination_identity="local-test",
        expected_identity="local-test",
        apply=True,
        dry_run=False,
    )
    outcomes = {row.draft_id: row.outcome for row in report.decisions}
    assert outcomes["ev-trusted"] == SKIP_ALREADY_TRUSTED
    assert outcomes["ev-url"] == SKIP_ALREADY_TRUSTED
    assert outcomes["ev-canonical-url"] == SKIP_ALREADY_TRUSTED
    assert not (dest / "evidence" / "ev-trusted.json").exists()


def test_skip_test_artifact(tmp_path: Path) -> None:
    source = tmp_path / "src" / "inbox"
    dest = tmp_path / "dst" / "inbox"
    _write(source / "evidence" / "ev-test-1.json", _draft("ev-test-1"))
    report = deliver_drafts(
        source_inbox=source,
        destination_inbox=dest,
        source_identity="acquisition-local",
        destination_identity="local-test",
        expected_identity="local-test",
        apply=True,
        dry_run=False,
    )
    assert report.decisions[0].outcome == SKIP_TEST_ARTIFACT
    assert not (dest / "evidence").exists() or not (dest / "evidence" / "ev-test-1.json").exists()


def test_identity_mismatch_fails_closed(tmp_path: Path) -> None:
    source = tmp_path / "src" / "inbox"
    dest = tmp_path / "dst" / "inbox"
    _write(source / "evidence" / "ev-a.json", _draft("ev-a"))
    with pytest.raises(DraftDeliveryError):
        deliver_drafts(
            source_inbox=source,
            destination_inbox=dest,
            source_identity="acquisition-local",
            destination_identity="production-vps",
            expected_identity="other-box",
            apply=True,
            dry_run=False,
        )
    assert not (dest / "evidence" / "ev-a.json").exists()


def test_production_requires_allowlist(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "src" / "inbox"
    dest = tmp_path / "dst" / "inbox"
    _write(source / "evidence" / "ev-a.json", _draft("ev-a"))
    monkeypatch.delenv("BIOS_DRAFT_DELIVERY_ALLOWED_DESTINATIONS", raising=False)
    with pytest.raises(DraftDeliveryError):
        deliver_drafts(
            source_inbox=source,
            destination_inbox=dest,
            source_identity="acquisition-local",
            destination_identity="production-vps",
            expected_identity="production-vps",
            apply=True,
            dry_run=False,
        )


def test_audit_omits_article_body(tmp_path: Path) -> None:
    source = tmp_path / "src" / "inbox"
    dest = tmp_path / "dst" / "inbox"
    _write(source / "evidence" / "ev-a.json", _draft("ev-a"))
    deliver_drafts(
        source_inbox=source,
        destination_inbox=dest,
        source_identity="acquisition-local",
        destination_identity="local-test",
        expected_identity="local-test",
        apply=True,
        dry_run=False,
    )
    audit = (dest / "operations" / "draft-deliveries" / "latest.json").read_text(encoding="utf-8")
    assert "secret body" not in audit
    assert "body text that must not appear" not in audit
    assert "ev-a" in audit
    assert "NEW_DRAFT" in audit


def test_payload_hash_ignores_analyst_owned_fields() -> None:
    a = _draft("ev-a", review_state="in_review")
    b = _draft("ev-a", review_state="saved", reviewed_by="analyst")
    assert payload_hash(a) == payload_hash(b)


def test_cli_dry_run_and_apply(tmp_path: Path) -> None:
    source = tmp_path / "src" / "inbox"
    dest = tmp_path / "dst" / "inbox"
    _write(source / "evidence" / "ev-cli.json", _draft("ev-cli"))
    rc = deliver_main(
        [
            "--source-inbox",
            str(source),
            "--destination-inbox",
            str(dest),
            "--source-identity",
            "acquisition-local",
            "--destination-identity",
            "local-test",
            "--expected-destination-identity",
            "local-test",
        ]
    )
    assert rc == 0
    assert not (dest / "evidence" / "ev-cli.json").exists()
    rc = deliver_main(
        [
            "--source-inbox",
            str(source),
            "--destination-inbox",
            str(dest),
            "--source-identity",
            "acquisition-local",
            "--destination-identity",
            "local-test",
            "--expected-destination-identity",
            "local-test",
            "--apply",
        ]
    )
    assert rc == 0
    assert (dest / "evidence" / "ev-cli.json").exists()


def test_copies_missing_transcript_artifact(tmp_path: Path) -> None:
    source = tmp_path / "src" / "inbox"
    dest = tmp_path / "dst" / "inbox"
    rel = "discovered_media/_normalized_transcripts/t1.json"
    _write(source / rel, {"id": "t1", "text": "spoken"})
    _write(
        source / "evidence" / "ev-spoken.json",
        _draft("ev-spoken", transcript_path=rel),
    )
    deliver_drafts(
        source_inbox=source,
        destination_inbox=dest,
        source_identity="acquisition-local",
        destination_identity="local-test",
        expected_identity="local-test",
        apply=True,
        dry_run=False,
    )
    assert (dest / rel).is_file()


def test_inventory_compare_counts(tmp_path: Path) -> None:
    a = tmp_path / "a" / "inbox"
    b = tmp_path / "b" / "inbox"
    _write(a / "evidence" / "ev-1.json", _draft("ev-1"))
    _write(b / "evidence" / "ev-1.json", _draft("ev-1"))
    assert inventory(a)["ev-1"] == inventory(b)["ev-1"]


def test_dry_run_writes_zero_destination_files(tmp_path: Path) -> None:
    source = tmp_path / "src" / "inbox"
    dest = tmp_path / "dst" / "inbox"
    dest.mkdir(parents=True)
    before = {path.relative_to(tmp_path) for path in dest.rglob("*")}
    _write(source / "evidence" / "ev-a.json", _draft("ev-a"))
    deliver_drafts(
        source_inbox=source,
        destination_inbox=dest,
        source_identity="acquisition-local",
        destination_identity="local-test",
        expected_identity="local-test",
        apply=False,
        dry_run=True,
        write_audit=True,
    )
    after = {path.relative_to(tmp_path) for path in dest.rglob("*")}
    assert after == before


def test_full_source_fidelity_survives_copy(tmp_path: Path) -> None:
    source = tmp_path / "src" / "inbox"
    dest = tmp_path / "dst" / "inbox"
    record = _draft(
        "ev-rich",
        article={
            "paragraphs": [{"index": 0, "text": "para one"}, {"index": 1, "text": "para two"}],
            "word_count": 4,
            "content_sha256": "abc",
            "acquisition": {"extractor": "trafilatura", "version": "article-acquisition-v1"},
        },
        transcript_path="discovered_media/_normalized_transcripts/t1.json",
    )
    _write(source / "discovered_media/_normalized_transcripts/t1.json", {"id": "t1"})
    _write(source / "evidence" / "ev-rich.json", record)
    deliver_drafts(
        source_inbox=source,
        destination_inbox=dest,
        source_identity="acquisition-local",
        destination_identity="local-test",
        expected_identity="local-test",
        apply=True,
        dry_run=False,
    )
    copied = json.loads((dest / "evidence" / "ev-rich.json").read_text(encoding="utf-8"))
    fidelity_keys = [
        "article",
        "source_url",
        "publisher_description",
        "summary",
        "language",
        "discovery_provenance",
        "relevance_tier",
        "does_not_prove",
        "berry_ids",
        "entity_ids",
        "published_date",
        "title",
        "source_id",
        "ai_enrichment",
        "transcript_path",
    ]
    for key in fidelity_keys:
        assert copied[key] == record[key]
    assert copied["article"]["paragraphs"] == record["article"]["paragraphs"]
    assert (dest / "discovered_media/_normalized_transcripts/t1.json").is_file()


def test_skip_published_source_is_not_operational(tmp_path: Path) -> None:
    source = tmp_path / "src" / "inbox"
    dest = tmp_path / "dst" / "inbox"
    _write(source / "evidence" / "ev-pub.json", _draft("ev-pub", status="published"))
    report = deliver_drafts(
        source_inbox=source,
        destination_inbox=dest,
        source_identity="acquisition-local",
        destination_identity="local-test",
        expected_identity="local-test",
        apply=True,
        dry_run=False,
    )
    assert report.decisions[0].outcome == SKIP_NOT_OPERATIONAL
    assert not (dest / "evidence" / "ev-pub.json").exists()


def test_cli_summary_labels(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    source = tmp_path / "src" / "inbox"
    dest = tmp_path / "dst" / "inbox"
    _write(source / "evidence" / "ev-a.json", _draft("ev-a"))
    deliver_main(
        [
            "--source-inbox",
            str(source),
            "--destination-inbox",
            str(dest),
            "--source-identity",
            "acquisition-local",
            "--destination-identity",
            "local-test",
            "--expected-destination-identity",
            "local-test",
        ]
    )
    out = capsys.readouterr().out
    assert "SOURCE acquisition-local" in out
    assert "DESTINATION local-test" in out
    assert "NEW 1" in out
    assert "IDENTICAL 0" in out
    assert "CONFLICT 0" in out
    assert "SKIPPED 0" in out
    assert "TOTAL 1" in out
    assert "secret body" not in out
