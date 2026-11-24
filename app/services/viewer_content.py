"""Portable public-source content, asset retrieval, and deterministic release diffs.

This adapter never publishes research or accepts corporate flavor records.
Network access is limited to recorded public asset URLs during an operator export.
"""
import base64
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from hashlib import sha256
import http.client
import ipaddress
import json
from pathlib import Path
import re
import socket
import ssl
from time import monotonic
from urllib.parse import urljoin, urlsplit

INACTIVE = {'rejected', 'archived', 'withdrawn', 'deleted'}
CATEGORIES = {'news', 'social', 'jobs', 'communications', 'other'}
MAX_ASSET = 2_000_000
MAX_TOTAL = 5_000_000
MIMES = {'image/png': 'png', 'image/jpeg': 'jpg', 'image/webp': 'webp', 'image/gif': 'gif', 'application/pdf': 'pdf'}


def information_records(main, *, include_private=True):
    """Read the current catalog or the older live platform's complete source reader.

    The compatibility path reads raw Digest source candidates, before personal
    selection/filtering, plus every stored Evidence record. Current explicit
    Evidence states win over older source projections. Output privacy gates
    still run in the directory/activity/report adapters.
    """
    catalog = getattr(main, 'unified_information', None)
    if callable(catalog):
        return catalog(include_private=include_private)
    from app.personal_digest_routes import world
    platform, _, sources, _ = world()
    if platform is not main:
        raise ValueError('The viewer source reader does not match this platform.')
    records = dict(sources)
    records.update({r['id']: r for r in main.all_evidence() if r.get('id')})
    return [r for r in records.values() if include_private or r.get('publication_scope') != 'private']


def logo_reference_kind(url):
    """Discovery URLs are not a visual classification or identity review."""
    value = url.lower()
    if re.search(r'(?:linkedin|facebook|instagram|twitter|youtube|pinterest)[-_](?:icon|logo)|(?:icon|logo)[-_](?:linkedin|facebook|instagram|twitter|youtube|pinterest)', value):
        return 'social_ui_icon'
    return 'logo' if any(word in value for word in ('logo', 'favicon', 'icon', 'wordmark', 'brandmark')) else 'reference_image'


def api():
    from app.services import viewer_export
    return viewer_export


def category(record):
    kind = str(record.get('source_type') or '').lower()
    if kind in {'social_observation', 'social_post', 'social_media'}:
        return 'social'
    if kind in {'job_posting', 'job_listing', 'job_advertisement', 'careers_listing'}:
        return 'jobs'
    if kind in {'company_press_release', 'company_announcement', 'press_release', 'corporate_communication', 'company_website'}:
        return 'communications'
    if kind in {'trade_press', 'news', 'news_article', 'mainstream_news', 'regional_press', 'industry_news', 'business_press', 'news_search', 'news_media', 'web_article'}:
        return 'news'
    return 'other'


def activity_from_records(records, directory):
    from app.services.information_catalog import information_flags
    from app.services.association_corrections import excluded
    s = api()
    companies = {r['id'] for r in directory['companies']}
    varieties = {r['id'] for r in directory['varieties']}
    result = []
    for r in records:
        if (r.get('record_type', 'evidence') != 'evidence' or r.get('publication_scope') == 'private'
                or r.get('status') in INACTIVE or r.get('review_state') in INACTIVE
                or r.get('evidence_role') in {'atomic_evidence', 'atomic_proposal'}):
            continue
        refs = {v for v in (r.get('entity_ids') or []) + (r.get('company_ids') or []) + (r.get('variety_ids') or []) if isinstance(v, str)}
        refs = {v for v in refs if not excluded(r, v)}
        if not refs & (companies | varieties):
            continue
        try:
            link = s.public_url(r.get('source_url') or r.get('url'))
        except ValueError:
            continue
        if not link or not r.get('title'):
            continue
        flags = information_flags(r)
        result.append({'id': r['id'], 'title': r['title'], 'summary': r.get('summary') or r.get('excerpt') or '',
                       'source': r.get('source_name') or '', 'source_url': link, 'category': category(r),
                       'source_type': r.get('source_type') or '', 'published_date': str(r.get('published_date') or '')[:10],
                       'captured_date': str(r.get('captured_date') or '')[:10],
                       'company_ids': sorted(refs & companies), 'variety_ids': sorted(refs & varieties),
                       'berries': r.get('berry_ids') or [], 'status': flags['review_status'],
                       'confidence': flags['confidence_label'], 'caveats': flags.get('caveats') or [],
                       'job_status': r.get('job_status') or ''})
    return normalize_activity(result)


def normalize_activity(value):
    s = api()
    result = []
    for r in s.rows(value or [], 'Activity'):
        result.append({'id': s.identifier(r.get('id')), 'title': s.text(r.get('title'), 500),
                       'summary': s.text(r.get('summary')), 'source': s.text(r.get('source'), 250),
                       'source_url': s.public_url(r.get('source_url')), 'category': r.get('category') if r.get('category') in CATEGORIES else 'other',
                       'source_type': s.text(r.get('source_type'), 150),
                       'published_date': s.iso_date(r['published_date']) if r.get('published_date') else '',
                       'captured_date': s.iso_date(r['captured_date']) if r.get('captured_date') else '',
                       'company_ids': s.strings(r.get('company_ids')), 'variety_ids': s.strings(r.get('variety_ids')),
                       'berries': [s.crop(v) for v in s.strings(r.get('berries'))], 'status': s.text(r.get('status'), 100),
                       'confidence': s.text(r.get('confidence'), 200), 'caveats': [s.text(v) for v in (r.get('caveats') or [])] if isinstance(r.get('caveats', []), list) else [s.text(r['caveats'])],
                       'job_status': s.text(r.get('job_status'), 100),
                       'availability': 'retained_archive' if r.get('availability') == 'retained_archive' else 'stored_current'})
    return sorted(s.unique(result, 'activity'), key=lambda r: (r['published_date'] or r['captured_date'], r['id']), reverse=True)


def retain_archive(current, baseline, source_records, directory, *, blocked=()):
    """Keep previously exported older sources; explicit exclusions always win."""
    known = {r['id'] for r in source_records}
    entities = {r['id'] for r in directory['companies'] + directory['varieties']}
    merged = {r['id']: r for r in current if r['id'] not in blocked}
    for r in (baseline or {}).get('activity', []):
        if r['id'] in known or r['id'] in blocked or r['id'] in merged:
            continue
        if not (set(r['company_ids']) | set(r['variety_ids'])) & entities:
            continue
        merged[r['id']] = {**r, 'availability': 'retained_archive'}
    return normalize_activity(list(merged.values()))


def _address(url):
    """Resolve every hop and pin the connection to a verified public IP."""
    s = api()
    url = s.public_url(url)
    p = urlsplit(url)
    if p.port not in {None, 80, 443} or p.hostname.lower().rstrip('.').endswith(('.local', '.internal', '.localhost')):
        raise ValueError('Asset destination is not a public web address.')
    port = p.port or (443 if p.scheme == 'https' else 80)
    answers = socket.getaddrinfo(p.hostname, port, type=socket.SOCK_STREAM)
    if not answers or any(not ipaddress.ip_address(a[4][0]).is_global for a in answers):
        raise ValueError('Asset destination resolves to a nonpublic address.')
    return p, port, answers[0][4][0]


def fetch_asset(url, *, deadline=None):
    """No ambient proxies, credentials, cookies or DNS re-resolution on connect."""
    deadline = deadline or monotonic() + 12
    for _ in range(4):
        if monotonic() >= deadline:
            raise ValueError('Asset retrieval time limit reached.')
        p, port, address = _address(url)
        timeout = max(.1, min(4, deadline - monotonic()))
        conn = (http.client.HTTPSConnection(p.hostname, port, timeout=timeout, context=ssl.create_default_context())
                if p.scheme == 'https' else http.client.HTTPConnection(p.hostname, port, timeout=timeout))
        conn._create_connection = lambda ignored, timeout=timeout, source_address=None: socket.create_connection((address, port), timeout, source_address)
        try:
            conn.request('GET', (p.path or '/') + ('?' + p.query if p.query else ''), headers={'User-Agent': 'BerryIntelligence-ViewerExport/2.0', 'Accept-Encoding': 'identity'})
            response = conn.getresponse()
            if response.status in {301, 302, 303, 307, 308}:
                url = urljoin(url, response.getheader('Location') or '')
                continue
            if response.status != 200:
                raise ValueError(f'Asset server returned HTTP {response.status}.')
            if int(response.getheader('Content-Length') or 0) > MAX_ASSET:
                raise ValueError('Asset exceeds the 2 MB file limit.')
            chunks, total = [], 0
            while True:
                if monotonic() >= deadline:
                    raise ValueError('Asset retrieval time limit reached.')
                block = response.read(min(65536, MAX_ASSET + 1 - total))
                if not block:
                    break
                total += len(block)
                if total > MAX_ASSET:
                    raise ValueError('Asset exceeds the 2 MB file limit.')
                chunks.append(block)
            return b''.join(chunks)
        finally:
            conn.close()
    raise ValueError('Asset redirect limit reached.')


def asset_bytes(content):
    if len(content) > MAX_ASSET:
        raise ValueError('Asset exceeds the 2 MB file limit.')
    if content.startswith(b'%PDF-'):
        return 'application/pdf'
    from app.services.brand_media import raster_info
    return raster_info(content)[0]


def normalize_assets(value):
    s = api()
    result, total = [], 0
    for r in s.rows(value or [], 'Assets'):
        mime = r.get('mime')
        data = s.text(r.get('data_url'), MAX_ASSET * 2)
        if mime not in MIMES or not data.startswith(f'data:{mime};base64,'):
            raise ValueError('Packaged assets must be raster images or PDF files.')
        try:
            body = base64.b64decode(data.split(',', 1)[1], validate=True)
        except (ValueError, TypeError):
            raise ValueError('Invalid asset bytes.') from None
        total += len(body)
        if total > MAX_TOTAL or asset_bytes(body) != mime:
            raise ValueError('Invalid asset type or the package exceeds the 5 MB asset limit.')
        digest = sha256(body).hexdigest()
        result.append({'id': s.identifier(r.get('id')), 'entity_ids': s.strings(r.get('entity_ids')),
                       'kind': s.text(r.get('kind'), 80), 'title': s.text(r.get('title'), 500),
                       'source_url': s.public_url(r.get('source_url')), 'attribution': s.text(r.get('attribution'), 500),
                       'mime': mime, 'sha256': digest, 'path': f'assets/{digest}.{MIMES[mime]}', 'data_url': data})
    return s.unique(result, 'asset')


def normalize_omissions(value):
    s = api()
    return [{'entity_id': s.identifier(r.get('entity_id')), 'asset_id': s.identifier(r['asset_id']) if r.get('asset_id') else '', 'title': s.text(r.get('title'), 500),
             'source_url': s.public_url(r.get('source_url')), 'reason': s.text(r.get('reason'), 500)}
            for r in s.rows(value or [], 'Asset omissions')]


def collect_assets(candidates, *, fetch=fetch_asset, seconds=90, budget=MAX_TOTAL):
    """Candidates originate in platform adapters, never submitted arbitrary URLs."""
    output, omissions, total = [], [], 0
    deadline = monotonic() + seconds
    def retrieve(c):
        try:
            if c.get('blocked'):
                raise ValueError(c['blocked'])
            if monotonic() >= deadline:
                raise ValueError('Export asset time budget reached; retry in the next export.')
            body = c['content'] if 'content' in c else fetch(c['url'], deadline=min(deadline, monotonic() + 12))
            mime = asset_bytes(body)
            return body, mime, ''
        except (OSError, ValueError, http.client.HTTPException) as exc:
            # Do not include network exception text: it can disclose local paths/IPs.
            return None, '', str(exc) if isinstance(exc, ValueError) else 'Asset could not be retrieved.'
    with ThreadPoolExecutor(max_workers=4) as pool:
        for c, (body, mime, error) in zip(candidates, pool.map(retrieve, candidates)):
            if body is not None and total + len(body) > budget:
                error = 'Package asset budget reached (5 MB); reduce image sizes or export scope.'
            if error:
                omissions.append({'entity_id': c['entity_id'], 'asset_id': c['id'], 'title': c['title'], 'source_url': c.get('source_url') or c.get('url') or '', 'reason': error})
                continue
            total += len(body)
            output.append({'id': c['id'], 'entity_ids': c.get('entity_ids') or [c['entity_id']], 'kind': c['kind'], 'title': c['title'],
                           'source_url': c.get('source_url') or c.get('url') or '', 'attribution': c.get('attribution') or '',
                           'mime': mime, 'data_url': f'data:{mime};base64,' + base64.b64encode(body).decode()})
    return normalize_assets(output), normalize_omissions(omissions)


def activity_asset_candidates(activity):
    """Direct recorded PDF/image URLs; never scrape source bodies for attachments."""
    result = {}
    for r in activity:
        url = r['source_url']
        extension = Path(urlsplit(url).path).suffix.lower()
        if extension not in {'.pdf', '.png', '.jpg', '.jpeg', '.gif', '.webp'}:
            continue
        refs = sorted(set(r['company_ids'] + r['variety_ids']))
        if not refs:
            continue
        key = 'viewer-asset-' + sha256(('source-attachment:' + url).encode()).hexdigest()[:24]
        if url not in result:
            result[url] = {'id': key, 'entity_id': refs[0], 'entity_ids': refs, 'kind': 'document' if extension == '.pdf' else 'source_image',
                           'title': r['title'], 'url': url, 'attribution': r['source']}
        else:
            result[url]['entity_ids'] = sorted(set(result[url]['entity_ids'] + refs))
    return list(result.values())


def asset_candidates(inbox, company_rows, entities, directory):
    from app.services import brand_media, entity_logo_overrides
    known = {r['id'] for r in directory['companies'] + directory['varieties']}
    result, seen = [], set()
    inventory = brand_media.inventory(inbox)
    def add(entity, key, kind, title, url='', **more):
        if (entity, key) in seen:
            return
        seen.add((entity, key))
        result.append({'id': 'viewer-asset-' + sha256((entity + ':' + key).encode()).hexdigest()[:24],
                       'entity_id': entity, 'kind': kind, 'title': title, 'url': url, **more})
    for r in company_rows:
        if r['id'] not in known:
            continue
        url = r.get('logo_url') or ''
        if url.startswith('/entity-logos/'):
            try:
                path, _ = entity_logo_overrides.logo_file(inbox, r['id'], url.rsplit('/', 1)[-1])
                add(r['id'], 'logo', 'logo', r['name'] + ' logo', content=path.read_bytes(), attribution=r.get('logo_attribution', ''))
            except (OSError, ValueError):
                add(r['id'], 'logo', 'logo', r['name'] + ' logo', blocked='Stored logo unavailable.')
        elif url.startswith(('https://', 'http://')):
            managed = next((a for a in inventory if a['entity_id'] == r['id'] and url in {a.get('image_url'), a.get('original_image_url')}), None)
            if not managed:
                kind = logo_reference_kind(url)
                extra = {'blocked': 'Recorded image is a social-platform icon, not a company logo.'} if kind == 'social_ui_icon' else {}
                add(r['id'], 'logo', kind, r['name'] + (' logo' if kind == 'logo' else ' recorded website image (logo identity unconfirmed)'), url, attribution=r.get('logo_attribution', ''), **extra)
        elif not url:
            add(r['id'], 'logo', 'logo', r['name'] + ' logo', blocked='No recorded logo URL or stored image.')
    for a in inventory:
        if a['entity_id'] not in known:
            continue
        opts = {'attribution': a.get('attribution') or '', 'source_url': a.get('source_page_url') or ''}
        if not a.get('export_eligible'):
            opts['blocked'] = 'Existing media policy or source availability does not permit this asset export.'
        else:
            try:
                path, _ = brand_media.image_file(inbox, a['id'])
                opts['content'] = path.read_bytes()
            except (OSError, ValueError):
                opts['blocked'] = 'Stored media unavailable.'
        add(a['entity_id'], a['id'], a['kind'], a.get('caption') or a['kind_label'], **opts)
    for r in entities:
        if r['id'] not in known:
            continue
        attrs = r.get('attributes') or {}
        # Explicit URLs only; no discovery, scraping, raw attachment paths or caches.
        for field, kind in [('image_url', 'variety_image'), ('brochure_url', 'document'), ('technical_sheet_url', 'document')]:
            url = attrs.get(field)
            if isinstance(url, str) and url.startswith(('http://', 'https://')):
                managed = next((a for a in inventory if a['entity_id'] == r['id'] and url in {a.get('image_url'), a.get('original_image_url')}), None)
                if not managed:
                    add(r['id'], field, kind, r['name'] + ' ' + field.replace('_url', '').replace('_', ' '), url)
        for a in attrs.get('viewer_assets') or []:
            if isinstance(a, dict) and isinstance(a.get('url'), str):
                managed = next((m for m in inventory if m['entity_id'] == r['id'] and a['url'] in {m.get('image_url'), m.get('original_image_url')}), None)
                if not managed:
                    add(r['id'], a['url'], a.get('kind') or 'document', a.get('title') or 'Supporting asset', a['url'])
    return result


def supplemental_records(inbox, entities):
    """Read public post/job projections without constructing mutable stores."""
    from contextlib import closing
    from datetime import UTC, datetime
    import sqlite3
    from app.services.brand_media import retained_records, resolve_account
    from app.brand_media_routes import bundled_configuration
    accounts = json.loads(bundled_configuration('brand_media_accounts.json').read_text(encoding='utf-8'))['accounts']
    result = []
    for r in retained_records(inbox):
        if datetime.fromisoformat(r['collected_at'].replace('Z', '+00:00')) + timedelta(days=r['retention_days']) <= datetime.now(UTC):
            continue
        account = resolve_account(r, accounts, entities)
        refs = [l['entity_id'] for l in r.get('analysis', {}).get('entity_links', []) if l.get('entity_id') in entities]
        if account:
            refs.append(account['entity_id'])
        result.append({'id': r['id'], 'record_type': 'evidence', 'status': 'unreviewed', 'source_type': 'social_observation',
                       'title': r.get('text', '')[:150] or 'Social post', 'summary': r.get('text', ''),
                       'source_url': r['canonical_url'], 'source_name': r['source'], 'entity_ids': refs,
                       'published_date': (r.get('published_at') or '')[:10], 'captured_date': r['collected_at'][:10]})
    path = Path(inbox) / 'living_workspaces' / 'workspace.sqlite3'
    if path.is_file():
        with closing(sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True, timeout=5)) as db:
            # Existing research rows only; no schema creation, personal pages or task logs.
            values = db.execute("SELECT body FROM objects WHERE kind='competitive_record'").fetchall()
        for body, in values:
            r = json.loads(body)
            f = r.get('fields') or {}
            if r.get('kind') != 'job' or r.get('resolution') != 'accepted_structure' or r.get('publication_scope') == 'private':
                continue
            url, title = f.get('original_url'), f.get('title')
            if not isinstance(url, str) or not isinstance(title, str) or title.lower() in {'unknown', 'not captured', 'none', 'n/a'}:
                continue
            day = str(f.get('last_observed_date') or f.get('observed_date') or '')[:10]
            try:
                date.fromisoformat(day)
            except ValueError:
                day = ''
            result.append({'id': r['id'], 'record_type': 'evidence', 'status': 'unreviewed', 'source_type': 'job_posting',
                           'title': title, 'summary': f.get('supporting_text') or '', 'source_url': url,
                           'source_name': f.get('source_name') or 'Public job listing', 'entity_ids': [r['entity_id']],
                           'captured_date': day, 'job_status': f.get('observed_status') or 'Not confirmed active'})
    return result


def stable(value):
    if isinstance(value, dict):
        return {k: stable(v) for k, v in sorted(value.items()) if k not in {'exported_at', 'generated_at', 'first_exported_at', 'data_url', 'path'}}
    if isinstance(value, list):
        return sorted([stable(v) for v in value], key=lambda v: json.dumps(v, sort_keys=True))
    return value


def change_report(workspace, baseline=None, *, baseline_id='', basis='previous_generated', old_scope='', scope=''):
    changes = []
    for name, current, old in [('companies', workspace['directory']['companies'], (baseline or {}).get('directory', {}).get('companies', [])),
                                ('varieties', workspace['directory']['varieties'], (baseline or {}).get('directory', {}).get('varieties', [])),
                                ('activity', workspace.get('activity', []), (baseline or {}).get('activity', [])),
                                ('assets', workspace.get('assets', []), (baseline or {}).get('assets', [])),
                                ('editions', workspace.get('issues', []), (baseline or {}).get('issues', [])),
                                ('reports', workspace.get('reports', []), (baseline or {}).get('reports', []))]:
        before, after = {r['id']: r for r in old}, {r['id']: r for r in current}
        for key in sorted(before.keys() | after.keys()):
            a, b = before.get(key), after.get(key)
            status, fields = '', []
            if a is None:
                status = 'added'
            elif b is None:
                missing_assets = {r.get('asset_id') for r in workspace.get('asset_omissions', [])}
                status = 'outside_scope' if old_scope != scope else 'unavailable' if name == 'assets' and key in missing_assets else 'no_longer_exported'
            else:
                fields = sorted(k for k in a.keys() | b.keys() if (a.get(k) != b.get(k) if k == 'items' else stable(a.get(k)) != stable(b.get(k))) and k not in {'data_url', 'path', 'first_exported_at'})
                if fields:
                    status = 'updated'
            if status:
                row = b or a
                changes.append({'container': name, 'id': key, 'title': row.get('name') or row.get('title') or key, 'change': status, 'fields': fields})
    return {'baseline_id': baseline_id, 'basis': basis if baseline else 'first_release', 'scope_changed': old_scope != scope,
            'counts': {k: sum(r['change'] == k for r in changes) for k in ['added', 'updated', 'no_longer_exported', 'outside_scope']}, 'items': changes}


def normalize_changes(raw):
    s = api()
    raw = raw or {}
    changes = [{'container': s.text(r.get('container'), 50), 'id': s.identifier(r.get('id')),
                'title': s.text(r.get('title'), 500), 'change': s.text(r.get('change'), 50), 'fields': s.strings(r.get('fields'))}
               for r in s.rows(raw.get('items', []), 'Changes')]
    return {'baseline_id': s.text(raw.get('baseline_id'), 100), 'basis': s.text(raw.get('basis'), 50),
            'scope_changed': raw.get('scope_changed') is True, 'counts': {k: sum(r['change'] == k for r in changes) for k in ['added', 'updated', 'no_longer_exported', 'outside_scope']}, 'items': changes}
