"""One bounded official Tochigi listing; native originals, no archive claim."""
from datetime import date
import re
import unicodedata
from urllib.parse import urljoin, urlsplit

from lxml import html

from app.services.industry_pulse.models import DiscoveryHit
from app.services.industry_pulse.official_listings import _fetch
from app.services.industry_pulse.regional_news import regional_crop_ids

FEED = dict(id='feed:priority:tochigi:pest-notices', label='Tochigi Prefecture',
            host='pref.tochigi.lg.jp', geography='apac', hl='ja-JP', gl='JP', ceid='JP:ja',
            feed_url='https://www.pref.tochigi.lg.jp/g59/boujo/yosatsu.html',
            adapter='japanese_notices', route='direct_listing', source_type='government_document',
            access_note='One official pest-notice page, at most 300 anchors and 30 crop-headline PDF links. Only explicit full listing dates; unknown dates retained. PDF bodies require separate bounded acquisition and remain partial. No complete archive or first-public timestamp claim.')


def listing_day(text):
    """No filename, month-only, page update, or HTTP-modified date inference."""
    text = unicodedata.normalize('NFKC', text)
    years = set(re.findall(r'(?<!\d)((?:19|20)\d{2})\)?年', text))
    days = set(re.findall(r'(?<!\d)(\d{1,2})月(\d{1,2})日', text))
    if len(years) == 1 and len(days) == 1:
        month, day = next(iter(days))
        try:
            return date(int(next(iter(years))), int(month), int(day)).isoformat()
        except ValueError:
            pass
    return None


def listing_rows(raw):
    if len(raw) > 2_000_000:
        raise ValueError('japanese-listing-response-limit')
    root = html.fromstring(raw, parser=html.HTMLParser(encoding='utf-8', no_network=True))
    content = root.xpath('//div[@id="tmp_contents"]')
    if not content or not any('病害虫' in h.text_content() for h in content[0].xpath('.//h1')):
        raise ValueError('japanese-listing-record-structure-missing')
    rows = {}
    structure = False
    for anchor in content[0].xpath('.//a[@href]')[:300]:
        title = ' '.join(anchor.text_content().split())
        target = urljoin(FEED['feed_url'], anchor.get('href', ''))
        parsed = urlsplit(target)
        if (parsed.scheme != 'https' or parsed.netloc != 'www.pref.tochigi.lg.jp'
                or parsed.query or parsed.fragment
                or not re.fullmatch(r'/g59/boujo/documents/[A-Za-z0-9_-]+\.pdf', parsed.path)):
            continue
        structure = True
        if not regional_crop_ids(title):
            continue
        containers = anchor.xpath('ancestor::li[1]')
        snippet = ' '.join(containers[0].text_content().split()) if containers else title
        published = listing_day(snippet)
        previous = rows.get(target)
        if previous and (previous['published_date'] or not published):
            continue
        rows[target] = dict(url=target, title=title[:2000], snippet=snippet[:4000], published_date=published)
    if not structure:
        raise ValueError('japanese-listing-record-structure-missing')
    return list(rows.values())[:30]


def listing_hits(query, *, fetch=None):
    rows = listing_rows((fetch or _fetch)(FEED['feed_url']))
    return [DiscoveryHit(**row, source_domain=FEED['host'], query_id=query.id,
        query_text=query.text, geography=query.geography, berry=None, topic='specialist_feed',
        provider='specialist_rss', origin_publisher_name=FEED['label'], origin_publisher_url=row['url'],
        provider_metadata={'publisher_route': 'direct_listing', 'publisher_source_type': 'government_document',
            'query_edition': query.ceid, 'listing_url': FEED['feed_url'], 'listing_page_limit': 1,
            'date_basis': 'publisher_listing_day' if row['published_date'] else 'unknown',
            'first_public_visibility': 'unknown'}) for row in rows]
