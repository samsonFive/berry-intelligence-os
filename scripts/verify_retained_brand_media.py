"""Real retained-source metadata proof, expressly not packaging-image success.

Uses only the isolated brand-media-preview copy and in-memory ASGI responses.
Browser requests are intercepted; remote requests and mutations are refused.
No provider calls, permission changes, classification, or source promotion.
"""
from __future__ import annotations

import hashlib
import html
import json
import os
from pathlib import Path
import sqlite3
import sys
import threading
from unittest.mock import patch
from urllib.parse import urlsplit

os.environ['ENABLE_SOURCE_POLLING'] = 'false'
os.environ['BIOS_MODE'] = 'authoring'

# The application uses this sentinel to skip collection/startup warm-up in tests.
import pytest  # noqa: F401, E402
import httpx  # noqa: E402
import requests  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
PREVIEW = ROOT / 'inbox/brand-media-preview'
OUTPUT = ROOT / 'inbox/retained-brand-media-proof'
ORIGIN = 'https://retained-media.invalid'
ENTITY = 'company-driscolls'
SOURCE_ID = 'ev-social-db4a4837771a228cf42a5285'
SOURCE_ENDPOINT = '/api/social/' + SOURCE_ID + '/reader?media=metadata-only'
OVERVIEW = '/entities/company/' + ENTITY + '?tab=overview'
DETAILS = '/entities/company/' + ENTITY + '?tab=details'
REVIEW = '/media-review?entity=' + ENTITY


def retained_snapshot():
    db_path = PREVIEW / 'social/observations.sqlite3'
    with sqlite3.connect(db_path.resolve().as_uri() + '?mode=ro', uri=True) as db:
        rows = db.execute('SELECT id,payload,analysis,removed FROM observations ORDER BY id').fetchall()
    record = json.loads(next(row[1] for row in rows if row[0] == SOURCE_ID))
    digest = hashlib.sha256(json.dumps(rows, ensure_ascii=False).encode()).hexdigest()
    return record, len(rows), digest


def main():
    assert PREVIEW.resolve() == (ROOT / 'inbox/brand-media-preview').resolve()
    assert (PREVIEW / 'brand_media/index.json').is_file(), 'Prepare the isolated retained preview first'
    OUTPUT.mkdir(parents=True, exist_ok=True)
    record, count, before = retained_snapshot()
    assert count == 205, 'This proof expects the retained 205-record preview copy'
    index_before = hashlib.sha256((PREVIEW / 'brand_media/index.json').read_bytes()).hexdigest()
    os.environ['BIOS_INBOX_DIR'] = str(PREVIEW)
    from app import main as app_main
    from app.services import brand_media
    app_main.INBOX_DIR = PREVIEW
    app_main.AUTHORING_MODE = True
    app_main.SOURCE_POLLING_ENABLED = False
    assets = brand_media.inventory(PREVIEW)
    case = [asset for asset in assets if asset.get('observation_id') == SOURCE_ID]
    assert case, 'Retained post has no shared-media mapping'
    assert not any(asset['display_eligible'] for asset in assets)
    assert len(record['media']) == 5 and not any(media.get('object_ref') for media in record['media'])
    network_attempts = []

    def deny_network(*args, **kwargs):
        network_attempts.append('External Python transport refused')
        raise AssertionError('No external transport is allowed in the retained proof')

    # TestClient uses its own in-memory transport, separate from these HTTP lanes.
    with patch.object(httpx.HTTPTransport, 'handle_request', deny_network), patch.object(requests.Session, 'request', deny_network):
        client = TestClient(app_main.app, base_url=ORIGIN)
        pages = {}
        for path in (OVERVIEW, DETAILS, REVIEW, SOURCE_ENDPOINT):
            print('Rendering retained page ' + path, flush=True)
            response = client.get(path)
            assert response.status_code == 200, (path, response.status_code)
            pages[path] = response
        company_html = pages[OVERVIEW].text
        source_html = pages[SOURCE_ENDPOINT].text
        assert 'data-brand-gallery' not in company_html
        assert 'data-brand-logo-fallback=' in company_html
        assert 'alt="Driscoll&#39;s, Inc. logo"' in company_html
        assert '<img' not in source_html.lower() and '<iframe' not in source_html.lower()
        decoded = html.unescape(source_html)
        for value in (record['canonical_url'], record['native_id'], record['published_at'], record['author_name']):
            assert value in decoded
        assert 'Display policy unresolved' in pages[REVIEW].text
        assert 'No permitted local raster bytes' in pages[REVIEW].text
        requested_paths, blocked_hosts, mutations, errors = [], set(), [], []
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path=os.environ.get('CHROME_PATH', r'C:\Program Files\Google\Chrome\Application\chrome.exe'), headless=True, timeout=15000)
            context = browser.new_context(viewport={'width': 1440, 'height': 1000}, record_video_dir=str(OUTPUT / 'video'))
            page = context.new_page()
            page.set_default_timeout(10000)
            page.on('pageerror', lambda error: errors.append(str(error)))

            def intercept(route):
                request = route.request
                url = urlsplit(request.url)
                if url.hostname != 'retained-media.invalid':
                    blocked_hosts.add(url.hostname or 'unknown')
                    route.abort()
                    return
                path = url.path + ('?' + url.query if url.query else '')
                requested_paths.append(path)
                if request.method not in ('GET', 'HEAD'):
                    mutations.append(request.method + ' ' + url.path)
                    route.fulfill(status=403, content_type='text/plain', body='Read-only proof')
                    return
                # Page bodies and source metadata are actual app responses.
                response = pages.get(path) or client.get(path)
                route.fulfill(status=response.status_code, headers={key: value for key, value in response.headers.items() if key.lower() in ('content-type', 'cache-control', 'x-content-type-options')}, body=response.content)

            page.route('**/*', intercept)
            page.goto(ORIGIN + OVERVIEW)
            page.get_by_role('heading', name="Driscoll's, Inc.", exact=True).wait_for()
            page.locator('.company-identity .company-monogram').wait_for()
            logo_fallback = page.locator('.company-identity .company-monogram').count() == 1
            assert not page.locator('.company-identity img').evaluate_all('(images)=>images.some(image=>image.complete && !image.naturalWidth)')
            assert page.locator('[data-brand-gallery]').count() == 0
            page.screenshot(path=str(OUTPUT / 'real-company-clean-layout.png'))
            page.get_by_role('link', name='Profile & links', exact=True).click()
            page.wait_for_url('**' + DETAILS)
            page.locator('a[href="' + REVIEW + '"]').scroll_into_view_if_needed()
            page.screenshot(path=str(OUTPUT / 'real-profile-media-entry.png'))
            page.locator('a[href="' + REVIEW + '"]').click()
            page.wait_for_url('**' + REVIEW)
            card = page.locator('[data-media-review="' + case[0]['id'] + '"]')
            card.scroll_into_view_if_needed()
            page.screenshot(path=str(OUTPUT / 'real-retained-media-held.png'))
            card.get_by_role('link', name='Inspect source', exact=True).click()
            page.locator('#v2ReaderBody .v2-reader-title').wait_for()
            page.locator('#v2ReaderBody summary').filter(has_text='Source details and why these labels were suggested').click()
            page.locator('#v2ReaderBody').get_by_text('Post ID: ' + record['native_id'], exact=False).scroll_into_view_if_needed()
            assert page.locator('#v2ReaderBody img, #v2ReaderBody iframe').count() == 0
            page.screenshot(path=str(OUTPUT / 'real-source-metadata-only.png'))
            reader_url = page.url
            page.get_by_role('button', name='Close reader', exact=True).click()
            page.wait_for_selector('#v2ReaderOffcanvas.show', state='hidden')
            page.wait_for_timeout(350)
            scope_preserved = page.url == ORIGIN + REVIEW
            video_path = page.video.path()
            context.close()
            browser.close()
        assert not errors and not mutations and not network_attempts, json.dumps({'errors': errors, 'refused_mutations': mutations, 'refused_external_transport': network_attempts})
        assert SOURCE_ENDPOINT in requested_paths and scope_preserved
    _, after_count, after = retained_snapshot()
    assert (after_count, after) == (count, before)
    assert hashlib.sha256((PREVIEW / 'brand_media/index.json').read_bytes()).hexdigest() == index_before
    result = {
        'result': 'BLOCKED — retained metadata path verified; no display-eligible packaging image',
        'real_packaging_e2e_success': False,
        'entity_id': ENTITY, 'observation_id': SOURCE_ID,
        'source_account': case[0].get('source_account'), 'retained_author': record.get('author_name'),
        'source_post_id': record['native_id'], 'source_url': record['canonical_url'],
        'published_at': record['published_at'], 'collected_at': record['collected_at'],
        'retained_records': count, 'shared_media_mappings': len(assets), 'case_media_references': len(record['media']),
        'display_eligible': 0, 'retained_local_media_objects': 0,
        'blockers': case[0]['blockers'], 'permission_basis': record['permission_basis'],
        'source_reader_endpoint': SOURCE_ENDPOINT, 'reader_scope_url': reader_url,
        'company_gallery_omitted': True, 'source_reader_contains_images_or_iframes': False,
        'existing_missing_logo_uses_neutral_mark': logo_fallback,
        'scope_preserved_after_reader_close': scope_preserved,
        'browser_page_errors': errors, 'mutating_requests': mutations,
        'external_python_transport_attempts': network_attempts,
        'external_browser_requests_prevented_hosts': sorted(blocked_hosts),
        'retained_payloads_unchanged': True, 'shared_index_unchanged': True,
        'video_path': str(video_path),
    }
    (OUTPUT / 'results.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    def timeout():
        print('Retained metadata proof exceeded 180 seconds', flush=True)
        os._exit(3)
    watchdog = threading.Timer(180, timeout)
    watchdog.daemon = True
    watchdog.start()
    try:
        main()
    finally:
        watchdog.cancel()
