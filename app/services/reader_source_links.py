"""Display source destinations without rewriting the recorded source URL.

Only local wrapper decoding and an exact-source saved capture are used here.
Feed presentation must never fetch a publisher or hydrate a capture body.
"""
from urllib.parse import urlsplit

from app.services.feed_first_reader import is_public_http_url
from app.services.google_news_url import resolve_google_news_url
from app.services.source_body import google_access_page


def _public_url(value):
    return value if isinstance(value, str) and is_public_http_url(value) else ""


def _google_destination(url):
    return google_access_page(url) or (urlsplit(url).hostname or "").casefold().rstrip(".") in {
        "google.com", "www.google.com",
    }


def _article_url(url):
    return bool(url and not _google_destination(url) and urlsplit(url).path not in {"", "/"})


def source_links(record, *, capture=None, publisher_url="", resolved_url=""):
    """Return navigation fields; source/review records remain untouched.

    ``resolved_url`` is supplied only by the existing exact-title publisher
    discovery cache. A capture must belong to this item and original URL and
    have succeeded; a consent page or publisher homepage is never an article.
    """
    original = _public_url(record.get("source_url"))
    media = record.get('media_format')
    if media in {'podcast', 'video', 'conference_video'} or record.get('source_type') == 'industry_podcast':
        return {'source_link_url': _public_url(record.get('media_url')) or original,
                'source_link_label': 'Listen at source' if media == 'podcast' or record.get('source_type') == 'industry_podcast' else 'Watch at source',
                'publisher_home_url': original, 'source_link_unresolved': False}
    target = _public_url(resolve_google_news_url(original)) if original else ""
    if original and _google_destination(target):
        cached = _public_url(resolved_url)
        if _article_url(cached):
            target = cached
    if (original and isinstance(capture, dict) and capture.get("ok") is True
            and capture.get("availability") not in ("blocked", "error")
            and (capture.get("requested_url") or capture.get("url")) == original
            and capture.get("item_id", record.get("id")) == record.get("id")):
        final = _public_url(capture.get("url"))
        if _article_url(final):
            target = final
    unresolved = bool(target and _google_destination(target))
    home = ""
    if unresolved:
        home = next((candidate for value in (record.get("origin_publisher_url"), publisher_url)
                     if (candidate := _public_url(value)) and candidate != target
                     and not _google_destination(candidate)), "")
    return {
        "source_link_url": target,
        "source_link_label": ("Open Google News link" if unresolved else
                              "Read original at publisher" if _article_url(target) else "Open source website"),
        "publisher_home_url": home,
        "source_link_unresolved": unresolved,
    }
