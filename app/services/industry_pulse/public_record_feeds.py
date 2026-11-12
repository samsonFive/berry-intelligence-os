"""Public primary-record routes and the free FSA structured-alert adapter.

Discovery metadata only: no source approval, trust promotion or model calls.
"""
from datetime import date
import json
from urllib.parse import urlsplit

import httpx

from app.services.industry_pulse.models import DiscoveryHit

FSA_FEED = {
    'id': 'feed:priority:uk-food-alerts:json', 'label': 'UK Food Standards Agency',
    'host': 'food.gov.uk', 'geography': 'europe', 'hl': 'en-GB', 'gl': 'GB', 'ceid': 'GB:en',
    'adapter': 'food_alerts_json', 'route': 'direct_json', 'source_type': 'government_document',
    'feed_url': 'https://data.food.gov.uk/food-alerts/id.json?_limit=100&_sort=-created',
    'access_note': 'Free official API, latest 100 notices. Created day is publisher metadata, not verified first-public visibility; older records require archive review.',
}


def _fetch(url):
    with httpx.stream('GET', url, timeout=12, follow_redirects=False,
                      headers={'User-Agent': 'BerryIntelligenceOS-Discovery/1.0'}) as response:
        response.raise_for_status()
        raw = bytearray()
        for chunk in response.iter_bytes(chunk_size=65536):
            raw.extend(chunk)
            if len(raw) > 2_000_000:
                raise ValueError('official-alert-response-limit')
    return json.loads(raw), bytes(raw)


def food_alert_hits(query, *, fetch=None):
    payload, _raw = (fetch or _fetch)(FSA_FEED['feed_url'])
    if not isinstance(payload, dict) or not isinstance(payload.get('items'), list):
        raise ValueError('official-alert-response-shape')
    hits = []
    for row in payload['items'][:100]:
        if not isinstance(row, dict) or not isinstance(row.get('status'), dict) or row['status'].get('label') != 'Published':
            continue
        title, url = row.get('title'), row.get('alertURL')
        if not isinstance(title, str) or not title.strip() or not isinstance(url, str):
            continue
        try:
            parsed = urlsplit(url)
            port = parsed.port
        except ValueError:
            continue
        if (parsed.scheme != 'https' or parsed.hostname not in {'www.food.gov.uk', 'alerts.food.gov.uk'}
                or parsed.username or parsed.password or port not in {None, 443}
                or not parsed.path.startswith('/news-alerts/alert/')):
            continue
        try:
            published = date.fromisoformat(str(row.get('created') or '')).isoformat()
        except ValueError:
            continue  # Modified time is not a substitute for publication.
        products = [str(p.get('productName') or '') for p in (row.get('productDetails') or []) if isinstance(p, dict)]
        risks = [str(p.get('riskStatement') or '') for p in (row.get('problem') or []) if isinstance(p, dict)]
        # Preserve publisher wording and product names when the title says only
        # "fruit products". Do not infer crop identity from an authority domain.
        snippet = '\n'.join([*products, *risks])[:4000]
        hits.append(DiscoveryHit(title=title.strip(), snippet=snippet, url=url,
            source_domain=parsed.hostname.removeprefix('www.'), published_date=published,
            query_id=query.id, query_text=query.text, geography=query.geography,
            berry=None, topic='specialist_feed', provider='specialist_rss',
            origin_publisher_name=FSA_FEED['label'], origin_publisher_url=url,
            provider_metadata={'publisher_route': 'direct_json', 'publisher_source_type': 'government_document',
                'query_edition': query.ceid, 'date_basis': 'publisher_created_day',
                'official_record_id': str(row.get('notation') or ''), 'official_record_url': str(row.get('@id') or '')}))
    return hits
