"""Isolated, zero-spend pilot. Provider claims never contribute to verified scores.

Successful reads are cached privately. No retries, scheduler, paid models, proxies,
credentials in URLs, or automatic account creation. Metered launches fail closed
until fresh balance, billing and all-in price verification are available.
"""
from datetime import datetime, timezone, timedelta
import hashlib
import json
import math
from pathlib import Path
import httpx
from .adapters import common, bsky_post, AccessBlocked
from .model import validate_intake
from .store import Store

WEIGHTS = {'discovery':25, 'multilingual':20, 'media':20,
           'fidelity':15, 'repeat':10, 'cost':10}

def verified_score(dimensions):
    points = coverage = 0
    for name, weight in WEIGHTS.items():
        d = dimensions.get(name, {})
        if d.get('state') != 'live-tested':
            continue
        if not d.get('n') or not isinstance(d.get('score'), (int, float)) or not 0 <= d['score'] <= 5:
            raise ValueError('Live score requires a measured sample and a 0–5 rating')
        coverage += weight
        points += weight * d['score'] / 5
    return {'verified_points_out_of_100':points, 'tested_weight_percent':coverage,
            'renormalized':False, 'recommendation':'no proven winner yet'}

def proportion(correct, total):
    if not 0 <= correct <= total:
        raise ValueError('Invalid counts')
    if not total:
        return {'numerator':0,'denominator':0,'estimate':None,'wilson95':None}
    p = correct / total; z = 1.959964
    center = (p + z*z/(2*total))/(1+z*z/total)
    half = z*math.sqrt(p*(1-p)/total+z*z/(4*total*total))/(1+z*z/total)
    return {'numerator':correct,'denominator':total,'estimate':p,
            'wilson95':[max(0,center-half),min(1,center+half)]}

def require_free_budget(verification, *, all_in_upper_bound, spent, ceiling, now=None):
    """Use before EVERY metered launch; sample docs or an API token prove no balance.

    Verification is a private operator record, not a credential, and must refer
    to actual current account/API evidence. Unsupported bounding is a blocker.
    """
    current = now or datetime.now(timezone.utc)
    checked = datetime.fromisoformat(verification['checked_at'])
    if checked.tzinfo is None or not timedelta(0) <= current-checked <= timedelta(minutes=15):
        raise AccessBlocked('Refresh actual balance and billing verification before this run')
    if verification.get('evidence_state') != 'actual-account' or not verification.get('evidence_reference'):
        raise AccessBlocked('Documentation/sample balances cannot authorize metered calls')
    if not verification.get('free_only') or verification.get('payment_method') or verification.get('auto_recharge'):
        raise AccessBlocked('Only verified free-only, no-card, no-recharge accounts are eligible')
    if not verification.get('enforceable_no_charge_cap') or not verification.get('ancillary_costs_included'):
        raise AccessBlocked('All-in charges and hard no-charge cap must be verified')
    balance = verification['balance']; initial = verification['initial_verified_balance']
    if not all(isinstance(v,(int,float)) and math.isfinite(v) and v>=0 for v in (balance,initial,spent,ceiling,all_in_upper_bound)):
        raise ValueError('Finite nonnegative budgets required')
    if not initial or balance > initial or balance-all_in_upper_bound < initial*.2 or spent+all_in_upper_bound > min(ceiling,initial*.8):
        raise AccessBlocked('Run exceeds ceiling or the 20% free-credit reserve')

class BoundedRead:
    """Allowlisted, single-attempt public transport; cache replay is not a repeat test."""
    HOSTS = {'public.api.bsky.app', 'news.google.com', 'www.googleapis.com'}
    def __init__(self, folder, *, enabled=False, max_requests=20, client=None):
        if not 1 <= max_requests <= 20:
            raise ValueError('Evaluation request ceiling is 1–20')
        self.folder = Path(folder); self.enabled = enabled
        self.max_requests = max_requests; self.requests = 0; self.cache_hits = 0
        self.client = client or httpx.Client(timeout=15, follow_redirects=False)
    def get(self, url, params):
        from urllib.parse import urlsplit
        if urlsplit(url).hostname not in self.HOSTS or urlsplit(url).scheme != 'https':
            raise AccessBlocked('Evaluation host not allowlisted')
        # YouTube keys never participate in stored cache names or provenance.
        public_params = {k:v for k,v in params.items() if k!='key'}
        digest = hashlib.sha256(json.dumps([url,public_params],sort_keys=True).encode()).hexdigest()
        cache = self.folder / (digest+'.bin')
        if cache.exists():
            self.cache_hits += 1
            return cache.read_bytes()
        if not self.enabled or self.requests >= self.max_requests:
            raise AccessBlocked('Explicit live opt-in and remaining request budget required')
        self.requests += 1
        try:
            with self.client.stream('GET',url,params=params) as response:
                if response.status_code != 200:
                    raise AccessBlocked(f'HTTP {response.status_code}; not zero volume')
                body = bytearray()
                for chunk in response.iter_bytes():
                    body.extend(chunk)
                    if len(body)>2_000_000:
                        raise AccessBlocked('2 MB response ceiling reached')
        except httpx.HTTPError as exc:
            raise AccessBlocked('Public transport failed; no retry') from exc
        self.folder.mkdir(parents=True,exist_ok=True)
        cache.write_bytes(body)
        return bytes(body)

def bluesky_search(transport, query, manifest):
    body = transport.get('https://public.api.bsky.app/xrpc/app.bsky.feed.searchPosts',
        {'q':query['query'],'lang':query['language'],'limit':10,'sort':'latest',
         'since':manifest['start_utc'],'until':manifest['end_utc']})
    data = json.loads(body)
    if not isinstance(data.get('posts'),list):
        raise AccessBlocked('Search response lacks posts')
    rows = [bsky_post(p) for p in data['posts'][:10]]
    for row in rows:
        row['query_version'] = manifest['version']
    return rows

def news_feed(transport, query, manifest):
    """Supplementary TITLE-only news discovery, never social/comment collection.

    RSS GUID and publisher reference retained. No feed HTML, redirects, arbitrary
    article fetching, location inference, or invented original publication date.
    """
    import email.utils
    import xml.etree.ElementTree as ET
    body = transport.get('https://news.google.com/rss/search',
        {'q':query['query']+' when:30d','hl':query['feed_locale'],'gl':query['market'],
         'ceid':query['market']+':'+query['language']})
    try:
        root = ET.fromstring(body)
    except ET.ParseError as exc:
        raise AccessBlocked('Malformed RSS') from exc
    rows = []
    for item in root.findall('./channel/item'):
        published = item.findtext('pubDate'); guid = item.findtext('guid'); url = item.findtext('link')
        if not guid or not url or not published:
            continue
        try:
            date = email.utils.parsedate_to_datetime(published).astimezone(timezone.utc)
        except (ValueError,TypeError):
            continue
        if not datetime.fromisoformat(manifest['start_utc']) <= date <= datetime.fromisoformat(manifest['end_utc']):
            continue
        # RSS opaque GUIDs can exceed the shared native-ID limit. A deterministic
        # digest preserves replay identity; canonical URL retains the feed link.
        feed_id = 'google-news-guid-sha256:'+hashlib.sha256(guid.encode()).hexdigest()
        publisher = item.findtext('source') or ''
        title = (item.findtext('title') or '').removesuffix(' - '+publisher) if publisher else item.findtext('title') or ''
        # Exact RSS publisher suffix is attribution, not a consumer observation.
        # Original XML remains private; no semantic rewriting of title words.
        row = common('forums-retail',feed_id,url,title,query['language'],date.isoformat())
        row.update(discovery_method='supplementary-news-rss-title-only',query_version=manifest['version'],
            language_basis='feed locale; original language unverified',content_role='news_repost',
            attribution='Google News RSS title (publisher suffix separated) / '+(publisher or 'publisher unknown'),
            permission_basis='Public feed title/reference only; no article body or media redistribution established')
        rows.append(validate_intake(row))
        if len(rows)>=10:
            break
    return rows

def jetstream_rows(result, manifest):
    rows = []
    for event in result.get('matched_events',[])[:10]:
        if event.get('operation') not in ('create','update') or event.get('collection')!='app.bsky.feed.post':
            continue
        uri = f"at://{event['did']}/{event['collection']}/{event['rkey']}"
        record = event['record']
        row = common('bluesky',uri,f"https://bsky.app/profile/{event['did']}/post/{event['rkey']}",
            record.get('text',''),(record.get('langs') or ['und'])[0],record.get('createdAt'),
            record.get('reply',{}).get('parent',{}).get('uri'))
        row.update(discovery_method='official-jetstream-live-tail',query_version=manifest['version'],
                   permission_basis='Public protocol reference; operator terms review required; no media bytes retained')
        # Blob CIDs are not working media URLs. Keep this absence measurable;
        # future hydration must use an approved host/rights path.
        images = record.get('embed',{}).get('images',[])
        for i, _image in enumerate(images[:30]):
            row['media'].append({'id':event['rkey']+f'-blob-{i}','parent_native_id':uri,
                'kind':'image','mime':'image/reference','source_url':None,'state':'unsupported',
                'storage_permission':'reference_only','attribution':'Original Bluesky blob',
                'retention':'CID received; hydration/availability/retention permission unverified'})
        rows.append(validate_intake(row))
    return rows

def ingest_isolated(rows, private_dir, entities):
    """Same validation, extraction, identity and restart path as the app."""
    store = Store(Path(private_dir)/'evaluation-inbox')
    ids = store.ingest(rows,entities)
    return {'ingested':len(ids),'unique':len(set(ids)), 'store':store}

def raw_metrics(rows, queries):
    unique = {(r['source'],r['native_id']):r for r in rows}
    values = list(unique.values())
    return {'returned':len(rows),'unique':len(values),'duplicates':len(rows)-len(values),
      'executed_queries':queries,'posts':sum(not r.get('parent_native_id') for r in values),
      'comments':sum(bool(r.get('parent_native_id')) for r in values),
      'human_reviewed_precision':proportion(0,0),
      'field_presence_not_correctness':{field:proportion(sum(bool(r.get(field)) for r in values),len(values))
          for field in ('native_id','canonical_url','published_at','text','language')},
      'media_references':sum(bool(m.get('source_url')) for r in values for m in r.get('media',[])),
      'downloaded_media_bytes':0, 'retention_permission_verified':False,
      'languages':{lang:sum(r['language']==lang for r in values) for lang in sorted({r['language'] for r in values})}}
