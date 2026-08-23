from __future__ import annotations

from copy import deepcopy
import json

import pytest
from fastapi.testclient import TestClient

from app import main
from app.main import app
from app.services.review_events import load_review_events
from app.services.extraction_backlog import classify_record
from app.services.source_fidelity_recovery import (
    build_recovery_artifact, candidate_from_record, decide_recovery_artifact,
    effective_record_for_extraction, match_recoveries, priority_key,
    recovery_manifest, write_recovery_artifact,
)


def _trusted(record_id="ev-media-c8cdb7133db1cae0bf66", **overrides):
    record = {
        "id": record_id, "record_type": "evidence", "status": "published",
        "title": "Pink Hudson raspberry awarded the Superior Taste Award",
        "source_type": "company_website", "source_name": "Planasa Newsroom",
        "source_id": "source-planasa", "source_url": "https://planasa.com/pink-hudson/",
        "published_date": "2026-06-01", "captured_date": "2026-08-01",
        "summary": "Pink Hudson received an award.", "submitted_by": "analyst",
        "berry_ids": ["berry-raspberry"], "entity_ids": ["company-planasa"],
        "priority": {
            dimension: {"level": "none", "rationale": ""}
            for dimension in ("reading", "testing", "commercial_position", "monitoring")
        },
    }
    record.update(overrides)
    return record


def _rich(record_id="ev-media-c8cdb7133db1cae0bf66", **overrides):
    record = {
        **_trusted(record_id), "status": "draft", "review_state": "in_review",
        "article": {
            "paragraphs": [{"index": index, "text": f"{record_id} paragraph {index}. " * 12} for index in range(5)],
            "word_count": 120, "content_sha256": "a" * 64,
            "acquisition": {"method": "readable_text_extraction", "extractor": "test", "extractor_version": "1", "fetched_at": "2026-08-01T00:00:00Z"},
        },
    }
    record.update(overrides)
    return record


def _candidate(record, source="historic_inbox"):
    locator_id = record.get("id") or record.get("transcript_id") or "artifact"
    value = candidate_from_record(record, recovery_source=source, locator=f"private/{locator_id}.json")
    assert value is not None
    return value


def test_exact_id_recovery_and_pink_hudson_not_confused_with_other_article():
    trusted = _trusted()
    pink = _candidate(_rich())
    other = _candidate(_rich("ev-media-d2406f3e7a6de96c4fa1", source_url="https://planasa.com/breeding-awards/"))
    result = match_recoveries([trusted], [other, pink])[0]
    assert result["match_class"] == "EXACT_IDENTITY_MATCH"
    assert result["candidate"]["candidate_id"] == trusted["id"]
    assert result["candidate"]["artifact"]["article"]["paragraphs"] == pink["artifact"]["article"]["paragraphs"]


def test_exact_url_recovery_without_title_fuzziness():
    trusted = _trusted("ev-trusted")
    rich = _candidate(_rich("ev-old-draft", source_url=trusted["source_url"]))
    result = match_recoveries([trusted], [rich])[0]
    assert result["match_class"] == "EXACT_URL_MATCH"


def test_same_id_conflicting_url_is_conflict():
    trusted = _trusted()
    rich = _candidate(_rich(source_url="https://planasa.com/different-article/"))
    assert match_recoveries([trusted], [rich])[0]["match_class"] == "CONFLICT"


def test_reused_body_across_three_distinct_publications_is_conflict():
    shared = [{"index": index, "text": f"Shared acquisition payload {index}. " * 20} for index in range(3)]
    trusted = [
        _trusted(f"ev-{index}", source_url=f"https://example.com/article-{index}")
        for index in range(3)
    ]
    candidates = [
        _candidate(_rich(f"draft-{index}", source_url=row["source_url"], article={
            "paragraphs": shared,
            "word_count": 180,
            "content_sha256": "b" * 64,
            "acquisition": {"method": "historic_cache"},
        }))
        for index, row in enumerate(trusted)
    ]
    results = match_recoveries(trusted, candidates)
    assert {row["match_class"] for row in results} == {"CONFLICT"}
    assert {row["conflict_count"] for row in results} == {3}
    assert all(row["candidate"] is None for row in results)
    manifest = recovery_manifest(results)
    assert manifest["counts"] == {"CONFLICT": 3}
    assert manifest["recoverable_articles"] == 0
    assert {row["conflict_reason"] for row in manifest["entries"]} == {
        "REUSED_BODY_HASH_ACROSS_DISTINCT_PUBLICATIONS"
    }


def test_similar_title_wrong_article_is_only_ambiguous():
    trusted = _trusted("ev-trusted", source_url="https://example.com/trusted")
    rich = _candidate(_rich("ev-other", source_url="https://example.com/other"))
    result = match_recoveries([trusted], [rich])[0]
    assert result["match_class"] == "AMBIGUOUS"
    assert result["candidate"] is None


def test_recovery_preserves_body_paragraph_indexes_and_semantic_trust():
    trusted = _trusted()
    original = deepcopy(trusted)
    result = match_recoveries([trusted], [_candidate(_rich())])[0]
    artifact = build_recovery_artifact(result, trusted)
    assert [row["index"] for row in artifact["artifact"]["article"]["paragraphs"]] == list(range(5))
    assert artifact["review"]["status"] == "pending"
    assert trusted == original
    assert classify_record(trusted, artifact)["readiness"] == "THIN_DESCRIPTION_ONLY"


def test_affirmation_alone_makes_recovered_body_eligible_without_semantic_overwrite():
    trusted = _trusted()
    artifact = build_recovery_artifact(match_recoveries([trusted], [_candidate(_rich())])[0], trusted)
    affirmed = decide_recovery_artifact(artifact, trusted, decision="affirmed", reviewer="analyst", reviewed_at="2026-08-23T00:00:00+00:00")
    effective = effective_record_for_extraction(trusted, affirmed)
    assert classify_record(trusted, affirmed)["readiness"] == "READY_FULL_ARTICLE"
    for field in ("status", "summary", "berry_ids", "entity_ids"):
        assert effective[field] == trusted[field]


@pytest.mark.parametrize("decision", ["rejected", "needs_investigation"])
def test_nonaffirming_decisions_remain_ineligible(decision):
    trusted = _trusted()
    artifact = build_recovery_artifact(match_recoveries([trusted], [_candidate(_rich())])[0], trusted)
    decided = decide_recovery_artifact(artifact, trusted, decision=decision, reviewer="analyst")
    assert classify_record(trusted, decided)["readiness"] == "THIN_DESCRIPTION_ONLY"


def test_transcript_artifact_is_preserved_and_requires_affirmation():
    trusted = _trusted("ev-spoken", media_format="podcast", source_type="industry_podcast")
    rich = _rich("ev-spoken", media_format="podcast", source_type="industry_podcast")
    rich.pop("article")
    rich["transcript"] = {"status": "available", "language": "en", "source": "publisher_provided", "segments": [{"index": 0, "start_seconds": 1.0, "end_seconds": 4.0, "speaker": "Host", "text": "Exact transcript segment."}]}
    artifact = build_recovery_artifact(match_recoveries([trusted], [_candidate(rich)])[0], trusted)
    assert artifact["artifact_type"] == "transcript"
    assert classify_record(trusted, artifact)["readiness"] != "READY_TRANSCRIPT"
    affirmed = decide_recovery_artifact(artifact, trusted, decision="affirmed", reviewer="analyst")
    assert classify_record(trusted, affirmed)["readiness"] == "READY_TRANSCRIPT"
    assert affirmed["artifact"]["transcript"]["segments"][0]["start_seconds"] == 1.0


def test_normalized_transcript_artifact_matches_explicit_parent_lineage():
    trusted = _trusted("ev-spoken", media_format="podcast", source_type="industry_podcast")
    normalized = {
        "record_type": "transcript_artifact",
        "transcript_id": "transcript-spoken",
        "item_id": "media-spoken",
        "parent_evidence_id": trusted["id"],
        "language": "en",
        "transcription_method": "publisher_caption",
        "segments": [{"index": 0, "start_seconds": 2.0, "end_seconds": 5.0, "speaker": "Guest", "text": "Historic exact transcript text."}],
    }
    candidate = _candidate(normalized, source="normalized_transcript")
    result = match_recoveries([trusted], [candidate])[0]
    artifact = build_recovery_artifact(result, trusted)
    assert result["match_class"] == "LINEAGE_MATCH"
    assert artifact["artifact"]["transcript"]["transcription_method"] == "publisher_caption"
    assert artifact["artifact"]["transcript"]["segments"][0]["speaker"] == "Guest"
    assert classify_record(trusted, artifact)["readiness"] != "READY_TRANSCRIPT"


def test_apply_is_additive_idempotent_and_conflict_stops(tmp_path):
    trusted = _trusted()
    artifact = build_recovery_artifact(match_recoveries([trusted], [_candidate(_rich())])[0], trusted)
    path = tmp_path / "artifact.json"
    assert write_recovery_artifact(path, artifact) == "created"
    assert write_recovery_artifact(path, artifact) == "unchanged"
    changed = deepcopy(artifact); changed["source_chars"] += 1
    with pytest.raises(ValueError, match="conflict"):
        write_recovery_artifact(path, changed)


def test_private_manifest_has_no_body_and_caneberry_priority():
    raspberry = _trusted("ev-r", berry_ids=["berry-raspberry"])
    blueberry = _trusted("ev-b", berry_ids=["berry-blueberry"])
    results = match_recoveries([blueberry, raspberry], [_candidate(_rich("ev-r")), _candidate(_rich("ev-b"))])
    manifest = recovery_manifest(results)
    assert manifest["entries"][0]["evidence_id"] == "ev-r"
    encoded = json.dumps(manifest)
    assert "Paragraph 0" not in encoded and "artifact" not in manifest["entries"][0]
    assert sorted(results, key=priority_key)[0]["evidence_id"] == "ev-r"


def test_private_source_fidelity_queue_and_decision_are_separate_and_audited(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path / "inbox")
    trusted = _trusted(review_state="published", reviewed_by="original-analyst", reviewed_at="2026-08-01")
    main.get_repositories(main.DATA_DIR, main.SCHEMAS_DIR).evidence.create(trusted)
    artifact = build_recovery_artifact(match_recoveries([trusted], [_candidate(_rich())])[0], trusted)
    path = main.INBOX_DIR / "source_fidelity" / "artifacts" / f"{trusted['id']}.json"
    write_recovery_artifact(path, artifact)
    before = deepcopy(main.get_repositories(main.DATA_DIR, main.SCHEMAS_DIR).evidence.get(trusted["id"]))
    client = TestClient(app)

    queue = client.get("/source-fidelity")
    detail = client.get(f"/source-fidelity/{trusted['id']}")
    assert queue.status_code == 200 and "PRIVATE OPERATIONAL REVIEW" in queue.text
    assert detail.status_code == 200 and "NOT PUBLICATION REVIEW" in detail.text
    assert "Paragraph 0" in detail.text and "historic_inbox" in detail.text

    response = client.post(
        f"/source-fidelity/{trusted['id']}/decision",
        data={"decision": "affirmed", "reviewer": "source-reviewer"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    after = json.loads(path.read_text(encoding="utf-8"))
    assert after["review"]["status"] == "affirmed"
    assert main.get_repositories(main.DATA_DIR, main.SCHEMAS_DIR).evidence.get(trusted["id"]) == before
    events = load_review_events(main.INBOX_DIR, workflow="source_fidelity_review")
    assert [(row["action"], row["prior_state"], row["new_state"]) for row in events] == [
        ("affirmed", "pending", "affirmed")
    ]
