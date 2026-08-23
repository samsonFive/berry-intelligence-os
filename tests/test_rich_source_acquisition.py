from __future__ import annotations

import httpx
import pytest

from app.services import article_acquisition
from app.services.article_acquisition import (
    ArticleAcquisitionError, ArticleBody, ArticleParagraph, fetch_article,
    repeated_body_conflict,
)
from app.services.source_completeness import source_completeness


def _body(url: str = "https://publisher.test/a", digest: str = "a" * 64) -> ArticleBody:
    return ArticleBody(
        source_url=url,
        paragraphs=(ArticleParagraph(0, "Real source paragraph " * 30),),
        word_count=90,
        content_sha256=digest,
        fetched_at="2026-08-23T00:00:00+00:00",
        extractor="trafilatura",
        extractor_version="1",
    )


def test_source_completeness_distinguishes_article_transcript_registry_and_thin() -> None:
    article = {"summary": "summary", "article": _body().as_dict()}
    transcript = {"summary": "summary", "transcript": {"status": "available", "text": "full transcript"}}
    registry = {"summary": "structured", "source_type": "patent_record", "patent_filing": {"number": "1"}}
    thin = {"summary": "description only", "publisher_description": "description only"}
    empty = {}
    assert source_completeness(article)["class"] == "FULL_ARTICLE"
    assert source_completeness(transcript)["class"] == "FULL_TRANSCRIPT"
    assert source_completeness(registry)["class"] == "STRUCTURED_REGISTRY"
    assert source_completeness(thin)["class"] == "THIN_DESCRIPTION"
    assert source_completeness(empty)["class"] == "NO_CONTENT"


def test_google_news_wrapper_is_never_preserved_as_full_article(monkeypatch) -> None:
    request = httpx.Request("GET", "https://news.google.com/rss/articles/wrapper")
    response = httpx.Response(200, request=request, text="<html><body>" + ("shared wrapper chrome " * 100) + "</body></html>")
    monkeypatch.setattr(article_acquisition.httpx, "get", lambda *args, **kwargs: response)
    with pytest.raises(ArticleAcquisitionError) as exc:
        fetch_article(str(request.url))
    assert exc.value.category == "script_rendered"


def test_google_news_consent_redirect_is_explicit_interstitial(monkeypatch) -> None:
    request = httpx.Request("GET", "https://news.google.com/rss/articles/wrapper")
    response = httpx.Response(
        200,
        request=httpx.Request("GET", "https://consent.google.com/ml?continue=https://news.google.com/rss/articles/wrapper"),
        text="<html><body>Before you continue to Google, we use cookies and data to provide services.</body></html>",
        extensions={},
    )
    monkeypatch.setattr(article_acquisition.httpx, "get", lambda *args, **kwargs: response)
    with pytest.raises(ArticleAcquisitionError) as exc:
        fetch_article(str(request.url))
    assert exc.value.category == "interstitial"


def test_repeated_body_detection_allows_reprint_pair_but_blocks_third_url() -> None:
    body = _body(digest="b" * 64)
    existing = [
        {"source_url": "https://one.test/story", "article": {"content_sha256": "b" * 64}},
    ]
    assert repeated_body_conflict(body, existing) is False
    existing.append({"source_url": "https://two.test/reprint", "article": {"content_sha256": "b" * 64}})
    assert repeated_body_conflict(body, existing) is True


def test_failure_metadata_is_specific_and_retry_semantics_are_derived() -> None:
    paywall = source_completeness({"summary": "thin"}, failure_category="paywall")
    timeout = source_completeness({"summary": "thin"}, failure_category="timeout")
    assert paywall["failure_category"] == "PAYWALL" and paywall["retryable"] is False
    assert timeout["failure_category"] == "TIMEOUT" and timeout["retryable"] is True
