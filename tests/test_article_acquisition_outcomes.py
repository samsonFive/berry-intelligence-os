from __future__ import annotations

from app.services.article_acquisition import ArticleAcquisitionError, ArticleBody, ArticleParagraph
from app.services.article_acquisition_outcomes import (
    aggregate_acquisition_summaries,
    build_outcome,
    persist_outcome,
    source_acquisition_summary,
)


ITEM = {
    "id": "item-1",
    "source_id": "source-1",
    "canonical_url": "https://example.invalid/story?token=secret&topic=berries",
}


def _body() -> ArticleBody:
    return ArticleBody(
        source_url=ITEM["canonical_url"],
        paragraphs=(ArticleParagraph(index=0, text="Readable berry article body."),),
        word_count=4,
        content_sha256="a" * 64,
        fetched_at="2026-09-15T12:00:00+00:00",
        extractor="trafilatura",
        extractor_version="2.0",
        published_date="2026-09-14",
    )


def test_outcome_categories_are_specific_and_do_not_preserve_secrets():
    cases = [
        (ArticleAcquisitionError("consent wall", category="interstitial"), "cookie_or_consent_page"),
        (ArticleAcquisitionError("403 bot blocked", category="blocked", http_status=403), "bot_wall"),
        (ArticleAcquisitionError("access denied", category="blocked"), "access_denied"),
        (ArticleAcquisitionError("no extractable body", category="empty_body"), "empty_page"),
        (ArticleAcquisitionError("body too short; likely not a real article", category="empty_body"), "navigation_only_shell"),
        (ArticleAcquisitionError("HTTP 503", category="http_error", http_status=503), "http_failure"),
        (ArticleAcquisitionError("timeout", category="timeout"), "network_failure"),
        (ArticleAcquisitionError("bad parser output", category="malformed_html"), "parser_failure"),
        (ArticleAcquisitionError("script-only wrapper", category="script_rendered"), "unsupported_source"),
        (ArticleAcquisitionError("login required", category="paywall"), "manual_acquisition_required"),
    ]
    for error, expected in cases:
        outcome = build_outcome(ITEM, error=error)
        assert outcome["outcome_category"] == expected
        assert "secret" not in outcome["attempted_url"]
        assert "secret" not in outcome["diagnostic"]


def test_invalid_url_port_is_not_persisted():
    invalid = dict(ITEM, canonical_url="https://example.invalid:not-a-port/story")

    outcome = build_outcome(invalid, error=ArticleAcquisitionError("failed", category="blocked"))

    assert outcome["attempted_url"] == "[invalid URL]"


def test_persisted_ledger_keeps_each_attempt_and_source_summary(tmp_path):
    first = persist_outcome(tmp_path, ITEM, build_outcome(ITEM, body=_body(), publication_id="draft-1"))
    second = persist_outcome(
        tmp_path,
        ITEM,
        build_outcome(ITEM, error=ArticleAcquisitionError("timed out", category="timeout")),
    )
    assert first["attempt_count"] == 1
    assert second["attempt_count"] == 2
    assert len(list((tmp_path / "operations" / "article_acquisition_outcomes").glob("*/*/*.json"))) == 2
    summary = source_acquisition_summary(tmp_path, "source-1")
    assert summary["attempts"] == 2
    assert summary["readable"] == 1
    assert summary["retryable"] == 1
    assert summary["state"] == "network_failure"
    assert summary["latest_readable_acquired_at"] == "2026-09-15T12:00:00+00:00"
    assert summary["most_recent_readable_article"] == "2026-09-14"
    totals = aggregate_acquisition_summaries({"source-1": summary})
    assert totals == {
        "attempts": 2,
        "readable": 1,
        "blocked_or_unusable": 0,
        "retryable": 1,
        "sources_with_attempts": 1,
    }


def test_operational_attempt_can_skip_creating_a_discovery_item(tmp_path):
    outcome = build_outcome(
        ITEM,
        body=_body(),
        publication_id="evidence-1",
        acquisition_stage="historical_reacquisition",
    )

    record = persist_outcome(tmp_path, ITEM, outcome, update_staged_item=False)

    assert record["acquisition_stage"] == "historical_reacquisition"
    assert not (tmp_path / "discovered_media" / "item-1.json").exists()
    assert len(list((tmp_path / "operations/article_acquisition_outcomes").glob("*/*/*.json"))) == 1
