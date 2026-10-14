import httpx

from app.services.feed_first_reader import capture_item
from app.services.publisher_link_resolution import declared_publisher_feed, publisher_article_link, publisher_feed_article_link


TITLE = "New Chilean blueberry varieties to score huge 39 percent export uptick"
HOME = "https://www.freshfruitportal.com"
ARTICLE = HOME + "/news/2026/10/13/blueberry-export-growth/"


def test_only_unique_exact_publisher_headline_links_are_accepted():
    html = f'<a href="{ARTICLE}"><h2>{TITLE}</h2></a><a href="/about">About</a>'
    assert publisher_article_link(html, HOME, TITLE + " - FreshFruitPortal.com", "FreshFruitPortal.com") == ARTICLE
    assert publisher_article_link(html, HOME, "Other berry production news") == ""
    assert publisher_article_link(html + f'<a href="/other-story">{TITLE}</a>', HOME, TITLE) == ""
    assert publisher_article_link(f'<a href="https://another-publisher.example/story">{TITLE}</a>', HOME, TITLE) == ""
    assert publisher_article_link(f'<a href="http://127.0.0.1/story">{TITLE}</a>', HOME, TITLE) == ""
    assert publisher_article_link('<a href="/story">Berry news</a>', HOME, "Berry news") == ""


def test_undecodable_wrapper_recovers_exact_publisher_link_and_keeps_original_identity(tmp_path):
    wrapper = "https://news.google.com/rss/articles/undecodable"
    prose = "Chilean growers announced new blueberry varieties and forecast a larger export harvest for the season."
    requests = []
    def response(request):
        requests.append(str(request.url))
        return httpx.Response(200, text=(f'<a href="{ARTICLE}">{TITLE}</a>' if str(request.url) == HOME else f'<article><p>{prose}</p></article>'))
    record = {"id": "wrapper-story", "source_url": wrapper, "origin_publisher_url": HOME, "title": TITLE, "source_name": "FreshFruitPortal.com"}
    with httpx.Client(transport=httpx.MockTransport(response)) as client:
        captured = capture_item(tmp_path, record, client=client)
    assert requests == [HOME, ARTICLE]
    assert captured["ok"] and captured["url"] == ARTICLE and captured["requested_url"] == wrapper
    assert captured["passages"] == [prose] and record["source_url"] == wrapper


def test_unresolved_wrapper_does_not_fetch_google_consent_or_guess_an_article(tmp_path):
    requests = []
    def response(request):
        requests.append(str(request.url))
        return httpx.Response(200, text=f'<a href="/different-article">Blueberry production update from another region</a>')
    record = {"id": "wrapper-story", "source_url": "https://news.google.com/rss/articles/undecodable", "origin_publisher_url": HOME, "title": TITLE}
    with httpx.Client(transport=httpx.MockTransport(response)) as client:
        capture = capture_item(tmp_path, record, client=client)
    assert requests == [HOME] and not capture["ok"] and capture["passages"] == []


def test_publisher_declared_feed_can_resolve_an_article_no_longer_on_home_page(tmp_path):
    rss = f'<rss><channel><item><title>{TITLE}</title><link>{ARTICLE}</link></item></channel></rss>'.encode()
    html = '<link rel="alternate" type="application/rss+xml" title="News" href="/feed/">'
    assert declared_publisher_feed(html, HOME) == HOME + "/feed/"
    assert publisher_feed_article_link(rss, HOME, TITLE) == ARTICLE
    assert publisher_feed_article_link(rss, HOME, "Different berry harvest expansion news today") == ""
    assert declared_publisher_feed('<link rel="alternate" type="application/rss+xml" href="https://other.example/feed">', HOME) == ""
    assert publisher_feed_article_link(rss.replace(ARTICLE.encode(), b"http://127.0.0.1/private"), HOME, TITLE) == ""
    def response(request):
        if str(request.url) == HOME:
            return httpx.Response(200, text=html)
        if str(request.url) == HOME + "/feed/":
            return httpx.Response(200, content=rss)
        return httpx.Response(200, text="<p>Chilean blueberry growers described new varieties and a larger expected export harvest for this season.</p>")
    record = {"id":"feed-story", "source_url":"https://news.google.com/rss/articles/undecodable", "origin_publisher_url":HOME,"title":TITLE}
    with httpx.Client(transport=httpx.MockTransport(response)) as client:
        capture = capture_item(tmp_path, record, client=client)
    assert capture["ok"] and capture["url"] == ARTICLE
