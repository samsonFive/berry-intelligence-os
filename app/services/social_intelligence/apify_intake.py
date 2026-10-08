"""Normalize inspected Apify post schemas; transport/entitlement stays separate.

No fetching, translation, role inference or promotion occurs here. Raw receipts
must remain private. Relative LinkedIn dates are not precise publication facts.
"""
from urllib.parse import urlsplit
import hashlib

from .adapters import common, AccessBlocked
from .model import safe_url, validate_intake


def apify_post(item, *, source, build, collected_at, mode='live'):
    if source not in ('instagram', 'facebook', 'linkedin'):
        raise AccessBlocked('Apify platform schema not inspected')
    native = item.get('postId') if source == 'facebook' else item.get('id')
    url = item.get('linkedinUrl') if source == 'linkedin' else item.get('url')
    text = item.get({'instagram': 'caption', 'facebook': 'text', 'linkedin': 'content'}[source])
    if not native or not url or not isinstance(text, str) or not text.strip():
        raise AccessBlocked('Post identity/text absent; discovery metadata or article preview is not a post body')
    host = urlsplit(safe_url(url)).hostname or ''
    domain = {'instagram': 'instagram.com', 'facebook': 'facebook.com', 'linkedin': 'linkedin.com'}[source]
    if host != domain and not host.endswith('.' + domain):
        raise AccessBlocked('Post URL does not belong to its platform')
    published = item.get('timestamp') if source == 'instagram' else item.get('time') if source == 'facebook' else None
    row = common(source, str(native), url, text, published=published)
    row.update(mode=mode, collected_at=collected_at, discovery_method='apify-' + source,
               query_version='apify-inspected-' + build,
               attribution=source + ' original post via Apify',
               permission_basis='Third-party response; reference only; retention/redisplay rights unverified')
    if source == 'linkedin':
        estimate = (item.get('postedAt') or {}).get('date')
        if estimate:
            row.update(published_at=estimate, publication_date_basis='estimated')
        row['permission_basis'] += '; provider relative dates retained privately, not verified publication timestamps'
    author = item.get('author') or item.get('user') or {}
    row['author_handle'] = item.get('ownerUsername') or author.get('publicIdentifier') or author.get('username')
    row['author_name'] = item.get('ownerFullName') or author.get('name')
    urls = []
    if source == 'instagram':
        urls = item.get('images') or [item.get('displayUrl')]
    elif source == 'linkedin':
        urls = [m.get('url') for m in item.get('postImages', []) if isinstance(m, dict)]
    elif source == 'facebook':
        urls = [(m.get('image') or {}).get('uri') for m in item.get('media', [])
                if isinstance(m, dict) and m.get('__typename') == 'Photo']
    seen = set()
    for ref in urls:
        if not isinstance(ref, str) or not ref or ref in seen:
            continue
        safe_url(ref)
        seen.add(ref)
        row['media'].append({'id':'apify-image-' + hashlib.sha256(ref.encode()).hexdigest()[:24],
            'parent_native_id':str(native), 'kind':'image', 'source_url':ref,
            'mime':'image/reference', 'state':'available', 'storage_permission':'reference_only',
            'attribution':source + ' post image via Apify',
            'retention':'Reference availability and retention/redisplay rights require verification'})
        if len(row['media']) == 30:
            break
    return validate_intake(row, mode=mode)
