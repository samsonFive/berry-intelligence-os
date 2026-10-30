"""Publication dates must come from the article, never latest-news chrome."""
import json

import pytest

from app.services import article_acquisition as aa
from tests.test_article_acquisition import _FakeResponse, _REAL_ARTICLE_HTML

URL = "https://example.invalid/article"


def test_cms_article_date_wins_over_latest_news_and_extractor_guess(monkeypatch):
    # Structure observed during the Produce Report recovery pilot; body is synthetic.
    html = _REAL_ARTICLE_HTML.replace("<article>", "<article><div class='panel-pane pane-node-created'>June 08, 2026</div>")
    html = html.replace("</body>", "<aside><time datetime='2026-10-07'>October 07, 2026</time></aside></body>")
    monkeypatch.setattr(aa.httpx, "get", lambda *a, **kw: _FakeResponse(html, url=URL))
    body = aa.fetch_article(URL)
    assert body.published_date == "2026-06-08"
    assert body.published_date_basis == body.as_dict()["published_date_basis"] == "publisher_display_date"
    assert body.as_dict()["acquisition"]["version"] == "article-acquisition-v4"


@pytest.mark.parametrize("markup", [
    "<aside><time class='published' datetime='2026-10-07'>Latest news</time></aside>",
    "<footer>Copyright 2026</footer>",
    "<meta property='article:modified_time' content='2026-10-07T10:00:00Z'>",
    "<main><p>Trial measurements were recorded June 08, 2026.</p></main>",
    "<article><time class='modified' datetime='2026-10-07'>Updated</time></article>",
    "<script type='application/ld+json'>{\"@type\":\"WebSite\",\"datePublished\":\"2026-10-07\"}</script>",
    "<script type='application/ld+json'>{\"@type\":\"NewsArticle\",\"url\":\"https://example.invalid/other\",\"datePublished\":\"2026-10-07\"}</script>",
    "<script type='application/ld+json'>{not valid JSON}</script>",
    "<script type='application/ld+json'>{\"@type\":\"NewsArticle\",\"url\":\"https://[bad\",\"datePublished\":\"2026-10-07\"}</script>",
])
def test_unrelated_modified_or_malformed_dates_remain_unknown(markup):
    assert aa.publisher_publication_date(f"<html><body>{markup}</body></html>", URL) == (None, "unknown")


@pytest.mark.parametrize("value", ["2026", "2026-06", "2026-02-30", "2026-06-08Tgarbage", "June 08", "not a date"])
def test_incomplete_or_invalid_publication_metadata_is_not_a_date(value):
    markup = f'<meta property="article:published_time" content="{value}">'
    assert aa.publisher_publication_date(markup, URL) == (None, "unknown")


def test_explicit_metadata_keeps_original_date_and_ignores_modification():
    html = """<html><head>
    <meta property='article:published_time' content='2021-12-14T23:30:00-08:00'>
    <meta property='article:modified_time' content='2026-10-07T12:00:00Z'>
    </head><body><main><time class='published' datetime='2026-10-07'>Related story</time></main></body></html>"""
    assert aa.publisher_publication_date(html, URL) == ("2021-12-14", "publisher_metadata")


def test_conflicting_publication_metadata_is_unknown_instead_of_selecting_newest():
    html = """<meta property='article:published_time' content='2021-12-14'>
    <meta name='datePublished' content='2026-10-07'>"""
    assert aa.publisher_publication_date(html, URL) == (None, "unknown")


def test_structured_article_is_bound_to_current_url_and_not_other_articles():
    graph = {"@graph": [
        {"@type": "NewsArticle", "url": "https://example.invalid/other", "datePublished": "2026-10-07"},
        {"@type": ["https://schema.org/NewsArticle"], "mainEntityOfPage": {"@id": URL + "#article"}, "datePublished": "2026-06-08T10:00:00Z", "dateModified": "2026-10-07"},
    ]}
    html = '<script type="application/ld+json">' + json.dumps(graph) + '</script>'
    assert aa.publisher_publication_date(html, URL) == ("2026-06-08", "publisher_metadata")


def test_marked_article_time_is_supported_without_sidebar_dates():
    html = """<main><article><time itemprop='datePublished' datetime='2026-06-08'>June 8</time></article></main>
    <aside><time class='published' datetime='2026-10-07'>Latest story</time></aside>"""
    assert aa.publisher_publication_date(html, URL) == ("2026-06-08", "publisher_display_date")


def test_fetch_never_labels_page_wide_guess_as_publisher_metadata(monkeypatch):
    html = _REAL_ARTICLE_HTML.replace("</body>", "<aside><p>October 07, 2026</p></aside></body>")
    monkeypatch.setattr(aa.httpx, "get", lambda *a, **kw: _FakeResponse(html, url=URL))
    body = aa.fetch_article(URL)
    assert body.published_date is None and body.as_dict()["published_date_basis"] == "unknown"
    assert body.paragraphs and body.full_text


def embrapa_header(value):
    # Synthetic text in the verified Embrapa news-header DOM structure.
    return ("<div class='visualizacao visualizacao-noticias'><div class='data-categoria'>"
            f"<span class='data'>{value}</span><span class='categoria'>Research</span></div>"
            "<h1 class='titulo'>A crop research announcement</h1><p>Article body</p></div>")


@pytest.mark.parametrize('value,expected', [('05/09/25','2025-09-05'), ('27/08/26','2026-08-27'),
    ('05/09/2025','2025-09-05'), ('31/12/99','1999-12-31'), ('31/02/25',None), ('09/25',None), ('2025',None)])
def test_verified_portal_dd_mm_year_header(value, expected):
    # English portal URL still uses the verified Brazilian DD/MM/YY template.
    result = aa.publisher_publication_date(embrapa_header(value), 'https://www.embrapa.br/en/-/noticia/123/research')
    assert result == (expected, 'publisher_display_date' if expected else 'unknown')


def test_portal_profile_does_not_guess_from_other_sites_paths_or_chrome():
    markup = embrapa_header('05/09/25')
    for url in (URL, 'https://www.embrapa.br.evil.invalid/-/noticia/123', 'https://www.embrapa.br/search'):
        assert aa.publisher_publication_date(markup, url) == (None, 'unknown')
    url = 'https://www.embrapa.br/pt/-/noticia/123/research'
    for wrapper in ('aside', 'nav', 'footer'):
        assert aa.publisher_publication_date(f'<{wrapper}>{markup}</{wrapper}>', url) == (None, 'unknown')
    assert aa.publisher_publication_date(markup.replace("<h1 class='titulo'>", '<h2>'), url) == (None, 'unknown')
    assert aa.publisher_publication_date(markup + embrapa_header('06/09/25'), url) == (None, 'unknown')
    assert aa.publisher_publication_date(markup + '<footer>Copyright 2026</footer>', url) == ('2025-09-05','publisher_display_date')


def test_fetch_preserves_portal_original_date_instead_of_rss_or_crawl_date(monkeypatch):
    url = 'https://www.embrapa.br/en/-/noticia/123/research'
    html = _REAL_ARTICLE_HTML.replace('<article>', '<article>' + embrapa_header('05/09/25'))
    monkeypatch.setattr(aa.httpx, 'get', lambda *a, **kw: _FakeResponse(html, url=url))
    body = aa.fetch_article(url)
    assert body.published_date == '2025-09-05' and body.published_date_basis == 'publisher_display_date'
