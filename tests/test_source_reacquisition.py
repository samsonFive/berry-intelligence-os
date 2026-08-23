from __future__ import annotations

from collections import Counter

from app.services.article_acquisition import ArticleBody, ArticleParagraph
from app.services.source_fidelity_recovery import decide_recovery_artifact
from app.services.source_reacquisition import (
    build_inventory, build_reacquired_artifact, compare_current_artifact,
    classify_acquisition_failure, pilot_manifest, prioritize_record,
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
    assert classify_acquisition_failure("interstitial") == "UNAVAILABLE"
