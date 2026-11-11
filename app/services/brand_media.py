"""Shared entity media references, separate from social/Evidence trust.

Social bytes and posts stay in their existing store. This private index keeps
only identity/classification/policy decisions; reading a gallery never collects.
"""
from contextlib import closing
from datetime import UTC, datetime, timedelta
import hashlib
from io import BytesIO
import json
from pathlib import Path
import re
import sqlite3
import warnings
from typing import Literal
from urllib.parse import quote, urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.services.analyst_state_io import atomic_json, serialized_write
from app.services.entity_logo_overrides import _image_type, MAX_LOGO_BYTES
from app.services.social_intelligence.model import safe_url
from app.services.social_intelligence.output_eligibility import deleted_sources
from app.services.social_intelligence.store import media_reference_key

VERSION = 1
KINDS = {
    'logo': 'Actual logo', 'profile_image': 'Other profile image',
    'pack_photo': 'Packaging photograph', 'pack_render': 'Official packaging rendering',
    'label_closeup': 'Label close-up', 'shelf_observation': 'Retail shelf / display',
    'campaign': 'Campaign / lifestyle', 'unclassified': 'Needs image inspection',
}
PACK_KINDS = {'pack_photo', 'pack_render', 'label_closeup'}
ASSET_ID = re.compile(r'^asset-[a-f0-9]{24}$')
SOCIAL_ID = re.compile(r'^ev-social-[a-f0-9]{24}$')


def stamp():
    return datetime.now(UTC)


def raster_info(content):
    """Verify raster structure and decoded bounds; SVG never enters delivery.

    Pillow is already installed by this application's reportlab dependency.
    No remote URL is opened and original branded pixels are never rewritten.
    """
    from PIL import Image, UnidentifiedImageError
    _, mime = _image_type(content)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(BytesIO(content)) as image:
                width, height = image.size
                if width < 1 or height < 1 or width > 12000 or height > 12000 or width * height > 20_000_000:
                    raise ValueError('Image dimensions exceed safe limits')
                if Image.MIME.get(image.format) != mime:
                    raise ValueError('Raster format and signature disagree')
                image.verify()
        return mime, width, height
    except (UnidentifiedImageError, OSError, SyntaxError, Image.DecompressionBombWarning, Image.DecompressionBombError) as exc:
        raise ValueError('A valid bounded raster image is required') from exc


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid')


class Policy(Strict):
    display: bool = False
    cache: bool = False
    export: bool = False
    basis: str = Field(default='Usage unresolved; references only', min_length=1, max_length=1000)
    source_url: str | None = None
    checked_at: datetime | None = None
    expires_at: datetime | None = None
    # This version serves permitted local raster bytes only. A source URL is
    # never silently turned into a hotlink or an arbitrary server-side fetch.
    _url = field_validator('source_url')(lambda v: safe_url(v) if v else v)

    @field_validator('checked_at', 'expires_at')
    @classmethod
    def aware(cls, value):
        if value and value.tzinfo is None:
            raise ValueError('Policy dates require a timezone')
        return value


class Asset(Strict):
    id: str = Field(pattern=r'^asset-[a-f0-9]{24}$')
    entity_id: str = Field(min_length=1, max_length=200)
    origin: Literal['social', 'authorized_upload', 'official_reference']
    observation_id: str | None = Field(default=None, pattern=r'^ev-social-[a-f0-9]{24}$')
    media_id: str | None = Field(default=None, max_length=200)
    original_image_url: str | None = None
    source_page_url: str | None = None
    publisher: str | None = Field(default=None, max_length=500)
    source_locator: str | None = Field(default=None, max_length=1500)
    width: int | None = Field(default=None, ge=1, le=100000)
    height: int | None = Field(default=None, ge=1, le=100000)
    published_at: datetime | None = None
    source_kind: Literal['official', 'retailer', 'consumer', 'unknown'] = 'unknown'
    kind: Literal['logo', 'profile_image', 'pack_photo', 'pack_render', 'label_closeup', 'shelf_observation', 'campaign', 'unclassified'] = 'unclassified'
    match_status: Literal['matched', 'review_needed'] = 'review_needed'
    match_basis: str = Field(min_length=1, max_length=1500)
    classification_basis: str | None = Field(default=None, max_length=1500)
    caption: str = Field(default='', max_length=500)
    attribution: str = Field(default='', max_length=500)
    historical_status: Literal['historical', 'date_unknown', 'dated_reference'] = 'date_unknown'
    policy: Policy = Field(default_factory=Policy)
    primary: bool = False
    rejected: bool = False
    analyst_selected: bool = False
    object_ref: str | None = Field(default=None, pattern=r'^[a-f0-9]{64}$')
    mime: Literal['image/png', 'image/jpeg', 'image/webp', 'image/gif'] | None = None
    evidence_ids: list[str] = Field(default_factory=list, max_length=30)
    # Existing observation/variant records own market, origin, supplier and
    # cultivar. None are guessed or duplicated from pixels in this index.
    retail_observation_ids: list[str] = Field(default_factory=list, max_length=30)
    updated_at: datetime
    _urls = field_validator('source_page_url', 'original_image_url')(lambda v: safe_url(v) if v else v)

    @field_validator('published_at', 'updated_at')
    @classmethod
    def aware(cls, value):
        if value and value.tzinfo is None:
            raise ValueError('Media dates require a timezone')
        return value


def index_path(inbox):
    return Path(inbox) / 'brand_media' / 'index.json'


def load(inbox):
    path = index_path(inbox)
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding='utf-8'))
    if value.get('version') != VERSION or not isinstance(value.get('assets'), dict):
        raise ValueError('Media index requires repair')
    return {key: Asset.model_validate(row).model_dump(mode='json') for key, row in value['assets'].items()
            if key == row.get('id')}


def _save(inbox, assets):
    atomic_json(index_path(inbox), {'version': VERSION, 'assets': assets})


def retained_records(inbox, *, ids=None):
    """No Store construction, schema migration, WAL write, or retention reset."""
    path = Path(inbox) / 'social' / 'observations.sqlite3'
    if not path.is_file():
        return []
    receipts = deleted_sources(inbox)
    blocked = {r['id'] for r in receipts}
    native_blocked = {(r['source'], r['native_id']) for r in receipts}
    with closing(sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True, timeout=5)) as db:
        if ids is None:
            values = db.execute('SELECT id,payload,analysis FROM observations WHERE removed=0').fetchall()
        elif not ids:
            return []
        else:
            marks = ','.join('?' for _ in ids)
            values = db.execute(f'SELECT id,payload,analysis FROM observations WHERE removed=0 AND id IN ({marks})', tuple(ids)).fetchall()
        tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        media_holds = {(key, mid): state for key, mid, state in db.execute('SELECT evidence_id,media_id,state FROM media_tombstones')} if 'media_tombstones' in tables else {}
        url_holds = {(key, digest): state for key, digest, state in db.execute('SELECT evidence_id,url_hash,state FROM media_url_tombstones')} if 'media_url_tombstones' in tables else {}
    rows = []
    for key, payload, analysis in values:
        row = json.loads(payload)
        if key in blocked or row.get('mode') == 'fixture' or (row.get('source'), row.get('native_id')) in native_blocked:
            continue
        for media in row.get('media', []):
            url = media.get('source_url')
            reference = media_reference_key(row['source'], url)
            digests = [hashlib.sha256(v.encode()).hexdigest() for v in (url, reference) if v]
            state = media_holds.get((key, media['id'])) or next((url_holds[(key, d)] for d in digests if (key, d) in url_holds), None)
            if state:
                media.update(state=state, source_url=None, object_ref=None, content_hash=None)
        rows.append({**row, 'id': key, 'analysis': json.loads(analysis)})
    return rows


def _account(platform, value):
    if not value:
        return None
    if not value.startswith('https://'):
        return (platform, value.strip('/@').casefold())
    parts = urlsplit(safe_url(value))
    hosts = {'facebook': {'facebook.com', 'www.facebook.com'}, 'instagram': {'instagram.com', 'www.instagram.com'},
             'linkedin': {'linkedin.com', 'www.linkedin.com'}, 'x': {'x.com', 'www.x.com', 'twitter.com', 'www.twitter.com'}}
    if parts.hostname not in hosts.get(platform, set()) or parts.query or parts.fragment:
        return None
    path = parts.path.strip('/')
    # A post URL, page name prefix or a co-mention is not an account identity.
    if platform == 'linkedin':
        if not re.fullmatch(r'company/[^/]+', path):
            return None
    elif '/' in path:
        return None
    return (platform, path.lstrip('@').casefold()) if path else None


def resolve_account(record, accounts, entities):
    """Exact preverified account mapping only, never a text/visual match."""
    author = _account(record['source'], record.get('author_handle'))
    if author is None and record['source'] == 'facebook':
        parts = urlsplit(safe_url(record['canonical_url']))
        match = re.fullmatch(r'/([^/]+)/posts/[^/]+/?', parts.path)
        if match and parts.hostname in {'facebook.com', 'www.facebook.com'}:
            author = ('facebook', match[1].casefold())
    matches = []
    for account in accounts:
        entity = entities.get(account.get('entity_id'))
        if (entity and entity.get('entity_type') in {'company', 'brand', 'retailer'}
                and account.get('platform') == record['source'] and account.get('supporting_url')
                and account.get('verification_basis') and author is not None
                and author == _account(account['platform'], account['account_url'])):
            safe_url(account['supporting_url'])
            matches.append(account)
    return matches[0] if len(matches) == 1 else None


@serialized_write
def reuse_social(inbox, entities, *, accounts=(), entity_ids=(), limit=500, now=None):
    """Register all retained attachments, without acquiring or copying media.

    Identity can be matched automatically from a verified account. Packaging
    classification and display policy remain independent, explicit decisions.
    """
    now = now or stamp()
    if not 1 <= limit <= 1000:
        raise ValueError('Reuse limit must be 1–1000')
    assets = load(inbox)
    counts = dict(posts_scanned=0, attachments_seen=0, created=0, reused=0, expired=0, unmatched=0)
    for record in retained_records(inbox)[:limit]:
        counts['posts_scanned'] += 1
        expiry = datetime.fromisoformat(record['collected_at'].replace('Z', '+00:00')) + timedelta(days=record['retention_days'])
        if expiry <= now:
            counts['expired'] += 1
            continue
        account = resolve_account(record, accounts, entities)
        links = [l.get('entity_id') for l in record.get('analysis', {}).get('entity_links', [])
                 if l.get('entity_id') in entities and entities[l['entity_id']].get('entity_type') in {'company', 'brand', 'retailer'}]
        target = account['entity_id'] if account else (links[0] if len(set(links)) == 1 else None)
        if not target or (entity_ids and target not in entity_ids):
            counts['unmatched'] += 1
            continue
        for media in record['media']:
            counts['attachments_seen'] += 1
            if media['state'] != 'available' or media['kind'] not in {'image', 'thumbnail'}:
                continue
            reference = media_reference_key(record['source'], media.get('source_url')) or media['id']
            key = 'asset-' + hashlib.sha256(f"{record['source']}:{record['native_id']}:{reference}".encode()).hexdigest()[:24]
            if key in assets:
                counts['reused'] += 1
                continue  # Analyst selection, rejection, policy and history survive.
            basis = (f"Exact retained account {account['account_url']}; {account['verification_basis']}; supporting link {account['supporting_url']}"
                     if account else 'Proposed existing social entity link; account identity requires review')
            asset = Asset(id=key, entity_id=target, origin='social', observation_id=record['id'], media_id=media['id'],
                          source_kind=account.get('source_kind', 'official') if account else 'unknown',
                          match_status='matched' if account else 'review_needed', match_basis=basis,
                          historical_status='dated_reference' if record.get('published_at') else 'date_unknown',
                          policy=Policy(basis=record['permission_basis'], expires_at=expiry), updated_at=now)
            assets[key] = asset.model_dump(mode='json')
            counts['created'] += 1
    _save(inbox, assets)
    return counts


def inspect_asset(asset, records, *, now=None):
    """Resolve references at read time so deletion/restriction/expiry wins."""
    now = now or stamp()
    row = dict(asset)
    row.update(kind_label=KINDS[asset['kind']], blockers=[], image_url=None, inspection_href=None)
    policy = asset['policy']
    if asset['rejected']:
        row['blockers'].append('Analyst rejected')
    if asset['match_status'] != 'matched':
        row['blockers'].append('Identity needs review')
    if asset['kind'] == 'unclassified' or not asset.get('classification_basis'):
        row['blockers'].append('Image classification needs inspection')
    if asset['kind'] == 'pack_render' and asset['source_kind'] != 'official':
        row['blockers'].append('Rendering needs an official publisher')
    if not policy['display'] or not policy.get('source_url') or not policy.get('checked_at'):
        row['blockers'].append('Display policy unresolved')
    elif datetime.fromisoformat(policy['checked_at']) > now:
        row['blockers'].append('Policy check date is in the future')
    if policy.get('expires_at') and datetime.fromisoformat(policy['expires_at']) <= now:
        row['blockers'].append('Retention expired')
    delivery = None
    if asset['origin'] == 'social':
        record = records.get(asset['observation_id'])
        media = next((m for m in (record or {}).get('media', []) if m['id'] == asset['media_id']), None)
        if not record or not media or media['state'] != 'available' or media['storage_permission'] == 'restricted':
            row['blockers'].append('Source removed, restricted or unavailable')
        else:
            expiry = datetime.fromisoformat(record['collected_at'].replace('Z', '+00:00')) + timedelta(days=record['retention_days'])
            if expiry <= now:
                row['blockers'].append('Source retention expired')
            else:
                row.update(source_page_url=record['canonical_url'], original_image_url=media.get('source_url'),
                           source_account=record.get('author_handle') or (urlsplit(record['canonical_url']).path.split('/')[1] if record['source'] == 'facebook' else None),
                           published_at=record.get('published_at'),
                           attribution=asset.get('attribution') or media['attribution'],
                           inspection_href=f"/api/social/{record['id']}/reader?media=metadata-only")
            if media.get('object_ref') and media['storage_permission'] == 'permitted_bytes' and policy['cache']:
                delivery = ('social', record, media)
    elif asset.get('object_ref') and policy['cache']:
        delivery = ('upload', None, None)
    if delivery is None:
        row['blockers'].append('No permitted local raster bytes; no hotlink fallback')
    elif not policy['cache']:
        row['blockers'].append('Local delivery requires caching permission')
    row['display_eligible'] = not row['blockers']
    row['export_eligible'] = row['display_eligible'] and policy['export']
    if row['display_eligible']:
        row['image_url'] = f"/api/brand-media/{asset['id']}/image"
    return row


def inventory(inbox, *, now=None):
    try:
        assets = load(inbox)
        ids = {a['observation_id'] for a in assets.values() if a['origin'] == 'social'}
        records = {r['id']: r for r in retained_records(inbox, ids=ids)} if ids else {}
        rows = [inspect_asset(a, records, now=now) for a in assets.values()]
    except (OSError, ValueError, KeyError, TypeError, sqlite3.Error):
        return []  # A broken acquisition index cannot break investigation pages.
    for row in rows:
        if not row['display_eligible']:
            continue
        if row['origin'] == 'social':
            record = records.get(row['observation_id']) or {}
            media = next((m for m in record.get('media', []) if m['id'] == row['media_id']), {})
            obj = media.get('object_ref') or ''
            if not re.fullmatch(r'[a-f0-9]{64}', obj) or record.get('mode') not in {'live', 'manual', 'imported'}:
                row.update(display_eligible=False, export_eligible=False, image_url=None)
                row['blockers'].append('Local image reference invalid')
                continue
            path = Path(inbox) / 'social' / 'media' / record.get('mode', 'missing') / obj
            expected_mime = media.get('mime')
        else:
            obj = row['object_ref']
            path = Path(inbox) / 'brand_media' / 'objects' / row['object_ref']
            expected_mime = row['mime']
        try:
            if not path.is_file() or path.stat().st_size > 5_000_000:
                raise ValueError('Missing or oversized local image')
            content = path.read_bytes()
            if hashlib.sha256(content).hexdigest() != obj:
                raise ValueError('Image integrity mismatch')
            mime, width, height = raster_info(content)
            if mime != expected_mime:
                raise ValueError('Image type mismatch')
            row.update(width=width, height=height)
        except (OSError, ValueError):
            row.update(display_eligible=False, export_eligible=False, image_url=None)
            row['blockers'].append('Local image unavailable or invalid')
    return rows


def entity_media(inbox, entity_ids, *, now=None):
    """One scan for a comparison/cohort; no I/O to source/provider networks."""
    result = {key: {'logo': None, 'packaging': [], 'observations': []} for key in entity_ids}
    rows = sorted(inventory(inbox, now=now), key=lambda a: (not a['analyst_selected'], not a['primary'], a['id']))
    for row in rows:
        if row['entity_id'] not in result or not row['display_eligible']:
            continue
        group = result[row['entity_id']]
        if row['kind'] == 'logo':
            if group['logo'] is None:
                group['logo'] = row
        elif row['kind'] in PACK_KINDS and row['source_kind'] == 'official':
            group['packaging'].append(row)
        elif row['kind'] in PACK_KINDS | {'shelf_observation'} and row['source_kind'] in {'retailer', 'consumer'}:
            group['observations'].append(row)
    return result


def operational_counts(inbox, *, now=None):
    rows = inventory(inbox, now=now)
    result = {}
    for label, kinds in [('logos', {'logo'}), ('packaging', PACK_KINDS | {'shelf_observation'}), ('unclassified', {'unclassified', 'profile_image', 'campaign'})]:
        selected = [r for r in rows if r['kind'] in kinds]
        result[label] = {'attempted': len(selected), 'matched': sum(r['match_status'] == 'matched' for r in selected),
                         'display_eligible': sum(r['display_eligible'] for r in selected),
                         'review_needed': sum(not r['display_eligible'] and not r['rejected'] for r in selected),
                         'unavailable': sum(any('expired' in b or 'unavailable' in b for b in r['blockers']) for r in selected)}
    return result


@serialized_write
def register_discovery(inbox, entity_id, candidates, *, entities):
    """Connect official-page extraction to this same model, with rights held."""
    if entities.get(entity_id, {}).get('entity_type') not in {'company', 'brand', 'retailer'}:
        raise ValueError('Choose an existing company, brand or retailer')
    if len(candidates) > 120:
        raise ValueError('At most 120 candidates per page')
    assets = load(inbox)
    counts = {'created': 0, 'reused': 0}
    for candidate in candidates:
        # The shared source reference, rather than the discovery provider or
        # entity name, is the stable asset identity across refreshes.
        reference = safe_url(candidate['original_image_url'])
        page = safe_url(candidate['source_page_url'])
        key = 'asset-' + hashlib.sha256(f'official:{entity_id}:{page}:{reference}'.encode()).hexdigest()[:24]
        if key in assets:
            counts['reused'] += 1
            continue
        is_logo = candidate['asset_type'] == 'logo'
        exact = candidate.get('entity_name_match') == 'exact'
        asset = Asset(id=key, entity_id=entity_id, origin='official_reference', original_image_url=reference,
                      source_page_url=page, source_kind='official', source_locator=candidate.get('source_locator'),
                      width=candidate.get('width'), height=candidate.get('height'),
                      kind='logo' if is_logo else 'unclassified', match_status='matched' if exact and is_logo else 'review_needed',
                      match_basis=f"Verified-page extraction; schema subject {candidate.get('declared_subject_name')!r}; name comparison {candidate.get('entity_name_match')}. Parent/subbrand ownership not inferred.",
                      policy=Policy(), updated_at=stamp())
        assets[key] = asset.model_dump(mode='json')
        counts['created'] += 1
    _save(inbox, assets)
    return counts


@serialized_write
def decide(inbox, key, changes, *, reviewer, entities=None):
    if not reviewer or len(reviewer) > 100:
        raise ValueError('Reviewer required')
    allowed = {'kind', 'classification_basis', 'caption', 'attribution', 'primary', 'rejected', 'policy', 'match_status', 'match_basis', 'entity_id'}
    if not isinstance(changes, dict) or not changes or set(changes) - allowed:
        raise ValueError('Unsupported media decision')
    assets = load(inbox)
    if key not in assets:
        raise ValueError('Media reference not found')
    previous = dict(assets[key])
    asset = Asset.model_validate({**previous, **changes, 'analyst_selected': True, 'updated_at': stamp()}).model_dump(mode='json')
    if 'entity_id' in changes and (not entities or entities.get(asset['entity_id'], {}).get('entity_type') not in {'company', 'brand', 'retailer'}):
        raise ValueError('Choose an existing company, brand or retailer')
    if asset['primary'] and not asset['rejected']:
        for other in assets.values():
            if other['entity_id'] == asset['entity_id'] and other['kind'] == asset['kind']:
                other['primary'] = False
    assets[key] = asset
    # Audit before changing the index. Immutable decisions remain recoverable.
    event = hashlib.sha256((key + asset['updated_at']).encode()).hexdigest()
    atomic_json(Path(inbox) / 'brand_media' / 'decisions' / f'{event}.json',
                {'asset_id': key, 'reviewer': reviewer, 'previous': previous, 'changes': changes, 'at': asset['updated_at']})
    _save(inbox, assets)
    return asset


@serialized_write
def authorized_upload(inbox, metadata, content, *, entities):
    """Explicit authorized raster path; content-addressed bytes deduplicate."""
    if not content or len(content) > MAX_LOGO_BYTES:
        raise ValueError('Authorized image must be 1 byte–2 MB')
    mime, width, height = raster_info(content)
    digest = hashlib.sha256(content).hexdigest()
    entity = entities.get(metadata.get('entity_id'))
    if not entity or entity.get('entity_type') not in {'company', 'brand', 'retailer'}:
        raise ValueError('Choose an existing company, brand or retailer')
    if not metadata.get('authorization'):
        raise ValueError('Record the upload authorization')
    key = 'asset-' + hashlib.sha256((entity['id'] + ':' + digest).encode()).hexdigest()[:24]
    assets = load(inbox)
    if key in assets:
        return assets[key]
    policy = Policy.model_validate(metadata.get('policy', {}))
    if not policy.cache:
        raise ValueError('Local storage permission is required for uploaded image bytes')
    asset = Asset(id=key, entity_id=entity['id'], origin='authorized_upload', object_ref=digest, mime=mime, width=width, height=height,
                  source_page_url=metadata.get('source_page_url'), publisher=metadata.get('publisher'),
                  published_at=metadata.get('published_at'),
                  source_kind=metadata.get('source_kind', 'unknown'), kind=metadata.get('kind', 'unclassified'),
                  match_status='matched', match_basis=metadata['authorization'], classification_basis=metadata.get('classification_basis'),
                  caption=metadata.get('caption', ''), attribution=metadata.get('attribution', ''),
                  historical_status=metadata.get('historical_status', 'date_unknown'),
                  analyst_selected=True, policy=policy, updated_at=stamp())
    path = Path(inbox) / 'brand_media' / 'objects' / digest
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_bytes(content)
    assets[key] = asset.model_dump(mode='json')
    _save(inbox, assets)
    return assets[key]


def image_file(inbox, key, *, now=None):
    if not ASSET_ID.fullmatch(key):
        raise ValueError('Invalid media identity')
    row = next((r for r in inventory(inbox, now=now) if r['id'] == key), None)
    if not row or not row['display_eligible']:
        raise ValueError('Image is not display eligible')
    if row['origin'] == 'social':
        records = retained_records(inbox, ids={row['observation_id']})
        record = next((r for r in records if r['id'] == row['observation_id']), None)
        media = next((m for m in (record or {}).get('media', []) if m['id'] == row['media_id']), None)
        if not media or not re.fullmatch(r'[a-f0-9]{64}', media.get('object_ref') or '') or record['mode'] not in {'live', 'manual', 'imported'}:
            raise ValueError('Image no longer available')
        path = Path(inbox) / 'social' / 'media' / record['mode'] / media['object_ref']
        mime = media['mime']
    else:
        path = Path(inbox) / 'brand_media' / 'objects' / row['object_ref']
        mime = row['mime']
    if not path.is_file() or path.stat().st_size > 5_000_000:
        raise ValueError('Image unavailable')
    content = path.read_bytes()
    if hashlib.sha256(content).hexdigest() != (media['object_ref'] if row['origin'] == 'social' else row['object_ref']):
        raise ValueError('Image integrity check failed')
    detected, _, _ = raster_info(content)
    if detected != mime:
        raise ValueError('Image type mismatch')
    return path, mime
