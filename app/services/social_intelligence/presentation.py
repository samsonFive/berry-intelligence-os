"""Public platform players derived from validated post URLs, never supplied HTML."""
import re
from urllib.parse import urlsplit, parse_qs


def player(row):
    if row.get('mode') == 'fixture' or row.get('record_role') != 'original':
        return None
    media = row.get('media', [])
    if any(m.get('state') != 'available' or m.get('storage_permission') == 'restricted' for m in media):
        return None
    url = urlsplit(row.get('canonical_url', ''))
    host = (url.hostname or '').lower()
    if url.scheme != 'https' or url.username or url.password:
        return None
    source = row.get('source')
    if source == 'youtube' and host in ('www.youtube.com', 'youtube.com', 'youtu.be'):
        parts = url.path.strip('/').split('/')
        native = parts[0] if host == 'youtu.be' else parse_qs(url.query).get('v', [''])[0]
        if not native and len(parts) == 2 and parts[0] in ('shorts', 'embed'):
            native = parts[1]
        if re.fullmatch(r'[A-Za-z0-9_-]{11}', native) and native == row.get('native_id'):
            return {'url': 'https://www.youtube-nocookie.com/embed/' + native + '?playsinline=1', 'label': 'YouTube video', 'shape': 'video'}
    if source == 'tiktok' and host in ('www.tiktok.com', 'tiktok.com'):
        match = re.fullmatch(r'/@[^/]+/video/(\d+)/?', url.path)
        if match and match[1] == row.get('native_id'):
            return {'url': 'https://www.tiktok.com/player/v1/' + match[1] + '?autoplay=0', 'label': 'TikTok video', 'shape': 'portrait'}
    if source == 'linkedin' and host in ('www.linkedin.com', 'linkedin.com'):
        match = re.search(r'(?:activity-|urn:li:activity:)(\d+)', url.path)
        if match and match[1] == row.get('native_id'):
            urn = row.get('source_embed_urn') or 'urn:li:activity:' + match[1]
            if not re.fullmatch(r'urn:li:(?:activity|share|ugcPost):\d{1,30}', urn):
                return None
            return {'url': 'https://www.linkedin.com/embed/feed/update/' + urn, 'label': 'LinkedIn public post', 'shape': 'post'}
    return None
