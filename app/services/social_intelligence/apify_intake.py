"""Normalize inspected Apify post schemas; transport/entitlement stays separate.

No fetching, translation, role inference or promotion occurs here. Raw receipts
must remain private. Relative LinkedIn dates are not precise publication facts.
"""
from urllib.parse import urlsplit
import hashlib

from .adapters import common, AccessBlocked
from .model import safe_url, validate_intake
import re


def instagram_parent_context(context):
    """Explicit known parent identity; shortcode alone is not its numeric ID."""
    if not isinstance(context,dict) or set(context)!={'native_id','canonical_url'}:
        raise AccessBlocked('Known Instagram parent identity and URL required')
    native=context['native_id'];url=context['canonical_url']
    if not isinstance(native,str) or not re.fullmatch(r'[0-9]{1,40}',native) or not isinstance(url,str):
        raise AccessBlocked('Invalid Instagram parent context')
    parsed=urlsplit(safe_url(url))
    match=re.fullmatch(r'/(?:p|reel)/([A-Za-z0-9_-]+)/?',parsed.path)
    if parsed.hostname not in ('instagram.com','www.instagram.com') or not match or parsed.query or parsed.fragment:
        raise AccessBlocked('Instagram parent must be an exact public post/reel URL')
    if match[1].isdigit() and match[1]!=native:
        raise AccessBlocked('Numeric parent URL and native ID disagree')
    return native,parsed


def apify_instagram_comment(item, *, parent_context, build, collected_at, mode='live'):
    """Inspected direct-comment schema; never treats avatars as attachments."""
    parent,parent_url=instagram_parent_context(parent_context)
    native=item.get('id');text=item.get('text')
    if not isinstance(native,(str,int)) or isinstance(native,bool) or not re.fullmatch(r'[0-9]{1,40}',str(native)) or not isinstance(text,str) or not text.strip():
        raise AccessBlocked('Instagram comment identity/body absent')
    if item.get('timestamp') is not None and not isinstance(item['timestamp'],str):
        raise AccessBlocked('Instagram comment publication timestamp must be a string')
    post=item.get('postUrl');url=item.get('commentUrl')
    if not isinstance(post,str) or not isinstance(url,str):
        raise AccessBlocked('Explicit comment and parent source URLs required')
    post_url=urlsplit(safe_url(post));comment_url=urlsplit(safe_url(url))
    hosts=('instagram.com','www.instagram.com')
    if (post_url.hostname not in hosts or comment_url.hostname not in hosts
            or post_url.path.rstrip('/')!=parent_url.path.rstrip('/')
            or comment_url.path.rstrip('/')!=parent_url.path.rstrip('/')+'/c/'+str(native)):
        raise AccessBlocked('Instagram comment/parent identities disagree')
    row=common('instagram',str(native),url,text,published=item.get('timestamp'),parent=parent)
    row.update(mode=mode,collected_at=collected_at,discovery_method='apify-instagram-comment',
               query_version='apify-inspected-'+build,attribution='Instagram original comment via Apify',
               permission_basis='Third-party comment response; explicit known parent mapping; retention/redisplay rights unverified')
    row['author_handle']=item.get('ownerUsername')
    owner=item.get('owner') or {}
    if not isinstance(owner,dict):raise AccessBlocked('Instagram comment owner object required')
    row['author_name']=owner.get('full_name')
    likes=item.get('likesCount')
    if type(likes) is int and likes>=0:row['engagement']={'likes':likes}
    # The inspected schema supplies profile pictures, not comment attachments.
    # No guessed media, language, geography or business ownership.
    return validate_intake(row,mode=mode)


def apify_x_post(item, *, build, collected_at, mode='live'):
    """Inspected Atomus tweet shape; no author-location or quoted-media inference."""
    from email.utils import parsedate_to_datetime
    native = str(item.get('tweet_id') or '')
    url = item.get('url'); text = item.get('text')
    if not native.isdigit() or not isinstance(text, str) or not text.strip() or not isinstance(url, str) or not url:
        raise AccessBlocked('Tweet identity/body absent')
    parsed = urlsplit(safe_url(url))
    if parsed.hostname not in ('x.com', 'www.x.com', 'twitter.com', 'www.twitter.com') or parsed.path.rstrip('/').split('/')[-2:] != ['status', native]:
        raise AccessBlocked('Tweet URL and native identity disagree')
    if not isinstance(item.get('created_at'), str):
        raise AccessBlocked('Tweet publication date string required')
    stamp = parsedate_to_datetime(item['created_at'])
    if stamp.tzinfo is None:
        raise AccessBlocked('Tweet publication timezone absent')
    parent = str(item.get('in_reply_to_status_id')) if item.get('is_reply') is True and item.get('in_reply_to_status_id') else None
    if parent is not None and not parent.isdigit():
        raise AccessBlocked('Tweet reply parent identity invalid')
    row = common('x', native, url, text, language=item.get('lang') or 'und', published=stamp.isoformat(), parent=parent)
    if item.get('is_reply') is True:row['record_role'] = 'reply'
    row.update(mode=mode, collected_at=collected_at, discovery_method='apify-x', query_version='apify-inspected-'+build,
               attribution='X original tweet via Apify', permission_basis='Third-party response; reference only; retention/redisplay rights unverified')
    author = item.get('author') or {}
    if not isinstance(author, dict):raise AccessBlocked('Tweet author object required')
    row.update(author_handle=author.get('screen_name'), author_name=author.get('name'))
    media = item.get('media') or []
    if not isinstance(media, list) or len(media)>30:
        raise AccessBlocked('Tweet media schema/item ceiling exceeded')
    seen = set()
    for m in media:
        if not isinstance(m, dict):raise AccessBlocked('Tweet media object required')
        for field, kind in (('image_url','image'), ('video_url','video')):
            ref = m.get(field)
            if not ref:continue
            if not isinstance(ref, str):raise AccessBlocked('Tweet media URL string required')
            if ref in seen:continue
            safe_url(ref);seen.add(ref)
            row['media'].append({'id':'apify-'+kind+'-'+hashlib.sha256(ref.encode()).hexdigest()[:24],
                'parent_native_id':native,'kind':kind,'source_url':ref,'mime':kind+'/reference','state':'available',
                'storage_permission':'reference_only','attribution':'X tweet media via Apify',
                'retention':'Availability and retention/redisplay rights require verification'})
    return validate_intake(row, mode=mode)


def apify_post(item, *, source, build, collected_at, mode='live'):
    if source == 'x':
        return apify_x_post(item, build=build, collected_at=collected_at, mode=mode)
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


def apify_linkedin_comment(item, *, build, collected_at, parent_native_id=None, mode='live'):
    """Inspected comment body only; parent pictures/avatars are not attachments."""
    native = item.get('id')
    parent = item.get('postId') or parent_native_id
    if parent_native_id and item.get('postId') and str(item['postId']) != str(parent_native_id):
        raise AccessBlocked('Nested comment parent conflicts with containing post')
    text = item.get('commentary')
    url = item.get('linkedinUrl')
    if not native or not parent or not url or not isinstance(text, str) or not text.strip():
        raise AccessBlocked('Comment identity/parent/source/body absent')
    host = urlsplit(safe_url(url)).hostname or ''
    if host != 'linkedin.com' and not host.endswith('.linkedin.com'):
        raise AccessBlocked('Comment URL does not belong to LinkedIn')
    row = common('linkedin', str(native), url, text, published=item.get('createdAt'), parent=str(parent))
    row.update(mode=mode, collected_at=collected_at, discovery_method='apify-linkedin-comment',
               query_version='apify-inspected-' + build,
               attribution='LinkedIn original comment via Apify',
               permission_basis='Third-party comment response; reference only; retention/redisplay rights unverified')
    actor = item.get('actor') or {}
    row['author_name'] = actor.get('name')
    row['author_handle'] = actor.get('publicIdentifier')
    row['engagement'] = {k: v for k, v in (item.get('engagement') or {}).items()
                         if isinstance(v, int) and not isinstance(v, bool) and v >= 0}
    # No inspected comment-image field in this response. Preserve no guessed
    # avatars, post photos, inferred language, geography or corporate role.
    return validate_intake(row, mode=mode)


def apify_dataset(items, *, source, build, collected_at, mode='live', parent_context=None):
    """Bounded rows + explicit rejects; duplicate copies cannot inflate counts.

    Conflicting same-ID bodies/parents fail the batch, rather than silently
    choosing a nested or standalone variant. No transport or Store writes.
    """
    if not isinstance(items, list) or len(items) > 20:
        raise AccessBlocked('Inspected dataset item ceiling is twenty')
    rows, rejected, seen = [], [], {}
    duplicates = 0
    def retain(row):
        nonlocal duplicates
        key = (row['source'], row['native_id'])
        prior = seen.get(key)
        if prior:
            if prior != row:
                raise AccessBlocked('Conflicting duplicate native identity in dataset')
            duplicates += 1
            return
        seen[key] = row
        rows.append(row)
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            rejected.append({'index': index, 'reason': 'Dataset item is not an object'})
            continue
        try:
            if source == 'instagram' and ('commentUrl' in item or parent_context is not None):
                row=apify_instagram_comment(item,parent_context=parent_context,build=build,collected_at=collected_at,mode=mode)
            elif source == 'linkedin' and item.get('type') == 'comment':
                row = apify_linkedin_comment(item, build=build, collected_at=collected_at, mode=mode)
            else:
                row = apify_post(item, source=source, build=build, collected_at=collected_at, mode=mode)
        except (AccessBlocked, ValueError):
            rejected.append({'index': index, 'reason': 'Inspected identity/body/schema validation failed'})
            continue
        retain(row)
        if source == 'linkedin' and row['record_role'] == 'original':
            comments = item.get('comments', [])
            if not isinstance(comments, list) or len(comments) > 20:
                raise AccessBlocked('Nested comment schema/item ceiling exceeded')
            for comment in comments:
                if not isinstance(comment, dict):
                    raise AccessBlocked('Nested comment schema unrecognized')
                retain(apify_linkedin_comment(comment, build=build, collected_at=collected_at,
                                              parent_native_id=row['native_id'], mode=mode))
    return {'rows': rows, 'rejected': rejected, 'duplicate_copies': duplicates, 'input_items': len(items)}
