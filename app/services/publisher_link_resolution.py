"""Exact-headline links from the recorded publisher; never guess article URLs."""
import re
import unicodedata
from urllib.parse import urljoin, urlsplit

from lxml import etree, html as html_parser


def _title_key(text):
    return " ".join(re.findall(r"\w+", unicodedata.normalize("NFKC", str(text or "")).casefold()))


def _headline_key(headline, source_name):
    title = str(headline or "").strip()
    suffix = " - " + str(source_name or "").strip()
    if source_name and title.casefold().endswith(suffix.casefold()):
        title = title[:-len(suffix)]
    return _title_key(title)


def publisher_headlines_match(expected, actual, source_name="", *, min_words=5):
    target = _headline_key(expected, source_name)
    return len(target.split()) >= min_words and target == _headline_key(actual, source_name)


def publisher_article_link(html, home_url, headline, source_name=""):
    from app.services.feed_first_reader import is_public_http_url
    if not is_public_http_url(home_url):
        return ""
    target = _headline_key(headline, source_name)
    if len(target.split()) < 5:
        return ""  # Short/generic headings do not establish article identity.
    try:
        tree = html_parser.fromstring(html)
    except (etree.ParserError, TypeError, ValueError):
        return ""
    publisher = (urlsplit(home_url).hostname or "").casefold().removeprefix("www.")
    matches = {}
    for anchor in tree.xpath("//a[@href]"):
        labels = [anchor.text_content(), anchor.get("aria-label"), anchor.get("title")]
        labels.extend(node.text_content() for node in anchor.xpath(".//h1 | .//h2 | .//h3 | .//h4"))
        labels.extend(anchor.xpath(".//img/@alt"))
        if not any(_title_key(label) == target for label in labels if label):
            continue
        url = urljoin(home_url, anchor.get("href"))
        if not is_public_http_url(url):
            continue
        parsed = urlsplit(url)
        if ((parsed.hostname or "").casefold().removeprefix("www.") != publisher
                or parsed.path in {"", "/"} or url.split("#", 1)[0] == home_url.split("#", 1)[0]):
            continue
        from app.services.article_dedup import normalize_canonical_url
        matches.setdefault(normalize_canonical_url(url), url)
    return next(iter(matches.values())) if len(matches) == 1 else ""


def declared_publisher_feed(html, home_url):
    """At most one publisher-declared news feed; never guess an endpoint."""
    from app.services.feed_first_reader import is_public_http_url
    try:
        tree = html_parser.fromstring(html)
    except (etree.ParserError, TypeError, ValueError):
        return ""
    host = (urlsplit(home_url).hostname or "").casefold().removeprefix("www.")
    for node in tree.xpath("//link[@href]"):
        if "alternate" not in (node.get("rel") or "").casefold().split():
            continue
        if (node.get("type") or "").casefold() not in {"application/rss+xml", "application/atom+xml"}:
            continue
        if "comment" in (node.get("title") or "").casefold():
            continue
        url = urljoin(home_url, node.get("href"))
        if (is_public_http_url(url) and (urlsplit(url).hostname or "").casefold().removeprefix("www.") == host
                and "comments" not in urlsplit(url).path.casefold().split("/")):
            return url
    return ""


def publisher_feed_article_link(raw, home_url, headline, source_name=""):
    """Require one exact title and publisher-domain link in a declared feed."""
    from app.services.feed_first_reader import is_public_http_url
    target = _headline_key(headline, source_name)
    if len(target.split()) < 5:
        return ""
    try:
        tree = etree.fromstring(raw, parser=etree.XMLParser(resolve_entities=False, no_network=True))
    except (etree.XMLSyntaxError, TypeError, ValueError):
        return ""
    host = (urlsplit(home_url).hostname or "").casefold().removeprefix("www.")
    matches = {}
    for item in tree.xpath("//*[local-name()='item' or local-name()='entry']"):
        titles = item.xpath("./*[local-name()='title']")
        if not titles or _title_key("".join(titles[0].itertext())) != target:
            continue
        for link in item.xpath("./*[local-name()='link']"):
            if link.get("rel") not in {None, "alternate"}:
                continue
            url = urljoin(home_url, link.get("href") or link.text or "")
            if (is_public_http_url(url) and (urlsplit(url).hostname or "").casefold().removeprefix("www.") == host
                    and urlsplit(url).path not in {"", "/"}):
                from app.services.article_dedup import normalize_canonical_url
                matches.setdefault(normalize_canonical_url(url), url)
    return next(iter(matches.values())) if len(matches) == 1 else ""
