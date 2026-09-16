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
    assert exc_info.value.http_status == 403


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


def test_cookie_consent_gate_is_an_interstitial_failure_not_a_readable_body(monkeypatch):
    """A GDPR-style cookie/consent gate that replaces the page's visible
    content must be reported as `interstitial`, never silently extracted
    and presented as a readable article -- the exact "cookie/consent text"
    class this project's failure taxonomy names distinctly from an
    ordinary bot wall (category `blocked`) or paywall."""
    html = """
    <html><head><title>We value your privacy</title></head>
    <body>
    <div class="consent-banner">
    <h1>We value your privacy</h1>
    <p>We use cookies and data to deliver and maintain our services, to measure audiences,
    and to show you personalized content depending on your settings. Please choose your
    cookie preferences below or accept all cookies to continue to the site.</p>
    <button>Accept all cookies</button>
    <button>Manage consent</button>
    <button>Reject all cookies</button>
    </div>
    </body></html>
    """
    monkeypatch.setattr(aa.httpx, "get", lambda *a, **k: _FakeResponse(html))
    with pytest.raises(aa.ArticleAcquisitionError) as exc_info:
        aa.fetch_article("https://example.invalid/consent-gate")
    assert exc_info.value.category == "interstitial"


def test_headline_only_press_template_with_no_body_element_is_empty_body(monkeypatch):
    """Regression fixture for a real, live pattern found auditing Wave 1
    Source Oishii Press Feed (source-20260915-oishii-press): the publisher's
    own "Press" page template renders a hero image, title, publish date, and
    social-share icons -- and literally no body-text element at all, for
    every item in that feed sampled during this mission. This is a genuine,
    permanent, external content-availability fact (confirmed: no hidden
    body div, no outbound link to original coverage), not a bot wall, not a
    JS-rendering gap this project's static fetcher could ever resolve, and
    not a bug in this project's own extraction code -- `empty_body` /
    `navigation_only_shell` is the correct, honest, non-retryable outcome."""
    html = """
    <html><head><title>Press headline with no article body</title></head>
    <body>
    <section class="recipe-hero">
    <h1 class="recipe-hero__title">Press headline with no article body</h1>
    <p class="recipe-hero__description"></p>
    </section>
    <section class="recipe-metadata">
    <p>Published on Jun 21, 2024</p>
    <p>Written by a staff writer</p>
    <div class="social-share">Share: Twitter Facebook Email</div>
    </section>
    </body></html>
    """
    monkeypatch.setattr(aa.httpx, "get", lambda *a, **k: _FakeResponse(html))
    with pytest.raises(aa.ArticleAcquisitionError) as exc_info:
        aa.fetch_article("https://example.invalid/headline-only-press")
    assert exc_info.value.category == "empty_body"
    assert "too short" in str(exc_info.value) or "not a real article" in str(exc_info.value)


def test_cms_bound_empty_rich_text_article_is_empty_body(monkeypatch):
    """Regression fixture for a real, live pattern found auditing Wave 1
    Source Fruitist Newsroom (source-20260915-fruitist-newsroom): roughly
    two-thirds of that publisher's own "news" CMS collection items render
    their rich-text body container completely empty (`w-dyn-bind-empty`,
    a real Webflow CMS marker meaning the bound field itself holds no
    content) while the surrounding chrome (title, date, share links) is
    otherwise identical to items that DO carry a real body -- a genuine,
    per-item, external content-population inconsistency on the publisher's
    own site, not an extraction bug. `empty_body` is the correct outcome;
    a future re-check of the same URL may legitimately succeed if the
    publisher later populates that field, which is why this failure stays
    outside the always-permanent `script_rendered`/paywall/blocked
    categories -- see `article_acquisition_outcomes._failure_outcome`."""
    html = """
    <html><head><title>Fruitist Secures Financing to Drive Global Expansion</title></head>
    <body>
    <h1>Fruitist Secures Financing to Drive Global Expansion</h1>
    <div class="p-sm">04 November 2026</div>
    <article class="news-text w-dyn-bind-empty w-richtext"></article>
    <div class="news_share">Share: LinkedIn Twitter Email</div>
    </body></html>
    """
    monkeypatch.setattr(aa.httpx, "get", lambda *a, **k: _FakeResponse(html))
    with pytest.raises(aa.ArticleAcquisitionError) as exc_info:
        aa.fetch_article("https://example.invalid/cms-bound-empty")
    assert exc_info.value.category == "empty_body"
