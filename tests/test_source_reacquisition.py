from __future__ import annotations

from collections import Counter
import json

from app.services.article_acquisition import ArticleBody, ArticleParagraph
from app.services.source_fidelity_recovery import decide_recovery_artifact
from app.services.source_reacquisition import (
    build_inventory, build_reacquired_artifact, compare_current_artifact,
    classify_acquisition_failure, pilot_manifest, preflight_reacquisition_url,
    prioritize_record, stage_reacquired_artifact, write_pilot_audit,
)


def _trusted(evidence_id: str = "ev-one", berries=None) -> dict:
    return {
        "id": evidence_id, "status": "published", "title": "Berry strategy expands",
        "source_url": "https://publisher.test/story", "source_name": "Publisher",
        "published_date": "2026-07-01", "summary": "Berry strategy expands into raspberries.",
        "source_type": "company_press_release", "berry_ids": berries or ["berry-raspberry"],
        "entity_ids": ["company-one", "variety-one"],
    }


def _article() -> ArticleBody:
    return ArticleBody(
        source_url="https://publisher.test/story", final_url=None,
        paragraphs=(ArticleParagraph(0, "Berry strategy expands into raspberries with a detailed source account."),),
        word_count=10, content_sha256="c" * 64,
        fetched_at="2026-08-23T00:00:00+00:00", extractor="trafilatura",
        extractor_version="1", title="Berry strategy expands", published_date="2026-07-01",
        language="en", author="Reporter",
    )


def test_priority_reasons_are_deterministic_and_caneberry_visible() -> None:
    entities = {
        "company-one": {"id": "company-one", "entity_type": "company"},
        "variety-one": {"id": "variety-one", "entity_type": "variety"},
    }
    row = prioritize_record(
        _trusted(), entities=entities, signal_refs=Counter({"ev-one": 2}),
        assessment_refs=Counter({"ev-one": 1}),
    )
    components = {reason["component"] for reason in row["priority_reasons"]}
    assert row["priority"] == "HIGH"
    assert {"signal_support", "assessment_support", "raspberry_gap", "linked_varieties"} <= components
    assert row["priority_points"] == sum(reason["points"] for reason in row["priority_reasons"])


def test_pilot_manifest_is_bounded_body_free_and_diverse() -> None:
    records = [
        _trusted(f"ev-{index}", [berry])
        for index, berry in enumerate(
            ["berry-blackberry", "berry-raspberry", "berry-strawberry", "berry-blueberry"] * 7
        )
    ]
    report = build_inventory(
        records,
        entities=[
            {"id": "company-one", "entity_type": "company"},
            {"id": "variety-one", "entity_type": "variety"},
        ],
        signals=[], assessments=[],
    )
    manifest = pilot_manifest(report["items"], 10)
    assert len(manifest["entries"]) == 10
    assert {row["berry"] for row in manifest["entries"]} >= {"Blackberry", "Raspberry", "Strawberry", "Blueberry"}
    assert all("article" not in row and "transcript" not in row and "body" not in row for row in manifest["entries"])
    assert all(row["expected_review_path"] == "SOURCE_FIDELITY_REVIEW" for row in manifest["entries"])


def test_reacquired_current_page_stays_separate_pending_source_fidelity_review() -> None:
    trusted = _trusted()
    before = dict(trusted)
    comparison = compare_current_artifact(trusted, _article())
    assert comparison["outcome"] == "LIKELY_SAME_ARTICLE_CHANGED_FORMATTING"
    artifact = build_reacquired_artifact(trusted, _article())
    assert artifact["match_class"] == "REACQUIRED_CURRENT_SOURCE"
    assert artifact["review"]["status"] == "pending"
    assert artifact["artifact"]["article"]["paragraphs"]
    assert trusted == before
    decided = decide_recovery_artifact(artifact, trusted, decision="needs_investigation", reviewer="analyst")
    assert decided["review"]["status"] == "needs_investigation"
    assert trusted == before


def test_reacquisition_failure_outcomes_are_operator_meaningful() -> None:
    assert classify_acquisition_failure("paywall") == "PAYWALLED"
    assert classify_acquisition_failure("http_error", "HTTP 404") == "REMOVED"
    assert classify_acquisition_failure("interstitial") == "INTERSTITIAL_OR_CONSENT"
    assert classify_acquisition_failure("blocked") == "ROBOTS_OR_ACCESS_BLOCKED"
    assert classify_acquisition_failure("script_rendered") == "SCRIPT_RENDERED_UNAVAILABLE"
    assert classify_acquisition_failure("timeout") == "NETWORK_FAILURE"
    assert classify_acquisition_failure("empty_body") == "THIN_BODY"


def test_preflight_excludes_unsafe_and_non_article_urls() -> None:
    assert preflight_reacquisition_url("https://publisher.test/article") == (True, None)
    assert preflight_reacquisition_url("https://news.google.com/articles/one") == (
        False, "GOOGLE_NEWS_WRAPPER",
    )
    assert preflight_reacquisition_url("https://consent.google.com/ml") == (
        False, "INTERSTITIAL_OR_CONSENT",
    )
    assert preflight_reacquisition_url("https://www.google.com/search?q=berries") == (
        False, "SEARCH_RESULT_PAGE",
    )
    assert preflight_reacquisition_url("not-a-url") == (False, "INVALID_URL")


def test_exact_stable_source_classification_uses_historic_body_hash() -> None:
    trusted = _trusted()
    trusted["article"] = {"content_sha256": "c" * 64}
    comparison = compare_current_artifact(trusted, _article())
    assert comparison["outcome"] == "EXACT_STABLE_SOURCE"
    assert comparison["historic_body_hash_match"] is True


def test_unrelated_redirect_is_ambiguous_not_a_success() -> None:
    article = ArticleBody(
        source_url="https://publisher.test/story",
        final_url="https://publisher.test/unrelated",
        paragraphs=(ArticleParagraph(0, "Completely unrelated generic publisher content without the historic claim."),),
        word_count=8, content_sha256="d" * 64,
        fetched_at="2026-08-23T00:00:00+00:00", extractor="trafilatura",
        extractor_version="1", title="Unrelated home page", published_date="2026-08-23",
    )
    assert compare_current_artifact(_trusted(), article)["outcome"] == "AMBIGUOUS"


def test_idempotent_staging_preserves_matching_artifact_and_refuses_conflict(tmp_path) -> None:
    path = tmp_path / "source_fidelity" / "artifacts" / "ev-one.json"
    first = build_reacquired_artifact(_trusted(), _article())
    assert stage_reacquired_artifact(path, first) == "created"
    persisted = json.loads(path.read_text(encoding="utf-8"))

    later_article = ArticleBody(
        **{**_article().__dict__, "fetched_at": "2026-08-24T00:00:00+00:00"}
    )
    later = build_reacquired_artifact(_trusted(), later_article)
    assert stage_reacquired_artifact(path, later) == "unchanged"
    assert json.loads(path.read_text(encoding="utf-8")) == persisted

    changed_article = ArticleBody(
        **{**_article().__dict__, "content_sha256": "e" * 64}
    )
    changed = build_reacquired_artifact(_trusted(), changed_article)
    try:
        stage_reacquired_artifact(path, changed)
    except ValueError as exc:
        assert "conflict" in str(exc)
    else:
        raise AssertionError("conflicting reacquisition must not overwrite the staged artifact")


def test_private_body_free_pilot_audit_is_created_atomically(tmp_path) -> None:
    audit = {
        "manifest": "REACQUISITION-PILOT-10",
        "canonical": "abc123",
        "evidence_ids": ["ev-one"],
        "outcomes": [{"evidence_id": "ev-one", "body_sha256": "c" * 64}],
        "assertions": {"trusted_evidence_mutated": False, "new_extraction_ready_ids": []},
    }
    path = write_pilot_audit(tmp_path / "private-runs", audit, stamp="20260823T000000000000Z")
    assert json.loads(path.read_text(encoding="utf-8")) == audit
    assert "paragraphs" not in path.read_text(encoding="utf-8")
