"""Deterministic, mocked-HTTP tests for app/services/article_acquisition.py."""

from __future__ import annotations

import httpx
import pytest

from app.services import article_acquisition as aa


class _FakeResponse:
    def __init__(self, text: str, *, status: int = 200, url: str = "https://example.invalid/article") -> None:
        self.text = text
        self.status_code = status
        self.url = url


_REAL_ARTICLE_HTML = """
<html><head><title>Blueberry acreage grows in Peru</title></head>
<body>
<nav>Home | About | Contact</nav>
<article>
<h1>Blueberry acreage grows in Peru</h1>
<p>Peru's blueberry acreage expanded by 12 percent this season, according to industry group Proarándanos.
Growers cited favorable pricing and strong export demand from the United States and China as key drivers
of the expansion. Several new plantings are expected to reach full production within three years.</p>
<p>Industry analysts expect the trend to continue as more growers convert land from other crops.
The shift reflects broader confidence in blueberries as a stable, high-value export commodity for the region.</p>
</article>
<footer>Copyright 2026. All rights reserved. Subscribe to our newsletter.</footer>
</body></html>
"""


def test_clean_article_extraction_produces_paragraphs_and_provenance(monkeypatch):
    monkeypatch.setattr(aa.httpx, "get", lambda *a, **k: _FakeResponse(_REAL_ARTICLE_HTML))
    body = aa.fetch_article("https://example.invalid/article")
    assert body.word_count > 20
    assert len(body.paragraphs) >= 2
    assert "Peru" in body.full_text
    assert body.extractor == "trafilatura"
    assert body.content_sha256 and len(body.content_sha256) == 64
    as_dict = body.as_dict()
    assert as_dict["acquisition"]["method"] == "readable_text_extraction"
    assert as_dict["acquisition"]["version"] == aa.ARTICLE_ACQUISITION_VERSION


def test_malformed_no_body_page_raises_empty_body_category(monkeypatch):
    monkeypatch.setattr(aa.httpx, "get", lambda *a, **k: _FakeResponse("<html><body><nav>Menu</nav></body></html>"))
    with pytest.raises(aa.ArticleAcquisitionError) as exc_info:
        aa.fetch_article("https://example.invalid/empty")
    assert exc_info.value.category == "empty_body"


def test_403_response_is_a_blocked_failure_not_a_crash(monkeypatch):
    monkeypatch.setattr(aa.httpx, "get", lambda *a, **k: _FakeResponse("blocked", status=403))
    with pytest.raises(aa.ArticleAcquisitionError) as exc_info:
        aa.fetch_article("https://example.invalid/blocked")
    assert exc_info.value.category == "blocked"


def test_paywall_signal_in_body_is_a_paywall_failure(monkeypatch):
    html = "<html><body><p>Subscribe to continue reading this premium content about berries.</p></body></html>"
    monkeypatch.setattr(aa.httpx, "get", lambda *a, **k: _FakeResponse(html))
    with pytest.raises(aa.ArticleAcquisitionError) as exc_info:
        aa.fetch_article("https://example.invalid/paywalled")
    assert exc_info.value.category == "paywall"


def test_recaptcha_script_tag_does_not_false_positive_as_blocked(monkeypatch):
    """Regression test for a real bug found during this feature's own pilot
    against freshplaza.com: a normal, unblocked article page that merely
    loads Google's reCAPTCHA script (for an unrelated form) must not be
    misclassified as a bot wall just because "captcha" appears inside a
    <script src="...recaptcha/api.js"> tag."""
    html = _REAL_ARTICLE_HTML.replace(
        "<nav>", '<script src="https://www.google.com/recaptcha/api.js?render=explicit"></script><nav>'
    )
    monkeypatch.setattr(aa.httpx, "get", lambda *a, **k: _FakeResponse(html))
    body = aa.fetch_article("https://example.invalid/article")
    assert "Peru" in body.full_text


def test_timeout_is_reported_as_timeout_category(monkeypatch):
    def _raise(*args, **kwargs):
        raise httpx.TimeoutException("timed out")

    monkeypatch.setattr(aa.httpx, "get", _raise)
    with pytest.raises(aa.ArticleAcquisitionError) as exc_info:
        aa.fetch_article("https://example.invalid/slow")
    assert exc_info.value.category == "timeout"


def test_navigation_and_photo_credit_lines_are_stripped_from_the_body(monkeypatch):
    """Regression test for real junk found during this feature's own pilot:
    a "You are here" / "Back to top" nav breadcrumb pair, a duplicated
    title line, and a bare "© Photographer Name" photo-credit line each
    appearing as their own paragraph on real, live pages."""
    html = """
    <html><head><title>Fresh figs in good supply</title></head>
    <body><article>
    <p>You are here</p>
    <p>Back to top</p>
    <h1>Fresh figs in good supply</h1>
    <p>Fresh figs continue to be in good supply from California and have been so for the past month,
    according to grower reports. Production is expected to remain steady through the end of the season.</p>
    <p>&copy; J. Marchini Farms</p>
    <p>Sizing is normal for this point in the season, with typical variation between early and late harvest.</p>
    </article></body></html>
    """
    monkeypatch.setattr(aa.httpx, "get", lambda *a, **k: _FakeResponse(html))
    body = aa.fetch_article("https://example.invalid/figs")
    assert "you are here" not in body.full_text.lower()
    assert "back to top" not in body.full_text.lower()
    assert "j. marchini farms" not in body.full_text.lower()
    assert "fresh figs continue to be in good supply" in body.full_text.lower()


def test_empty_url_is_a_malformed_html_failure_not_a_crash():
    with pytest.raises(aa.ArticleAcquisitionError) as exc_info:
        aa.fetch_article("")
    assert exc_info.value.category == "malformed_html"
