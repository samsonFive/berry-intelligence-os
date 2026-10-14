"""Exact-headline links from the recorded publisher; never guess article URLs."""
import re
import unicodedata
from urllib.parse import urljoin, urlsplit

from lxml import etree, html as html_parser


def _title_key(text):
    return " ".join(re.findall(r"\w+", unicodedata.normalize("NFKC", str(text or "")).casefold()))


def publisher_article_link(html, home_url, headline, source_name=""):
    from app.services.feed_first_reader import is_public_http_url
    if not is_public_http_url(home_url):
        return ""
    title = str(headline or "").strip()
    suffix = " - " + str(source_name or "").strip()
    if source_name and title.casefold().endswith(suffix.casefold()):
        title = title[:-len(suffix)]
    target = _title_key(title)
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
