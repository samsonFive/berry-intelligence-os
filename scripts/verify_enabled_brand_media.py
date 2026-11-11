"""Actual private-preview image proof: ASGI pages plus exact approved image URLs.

No paid provider calls, source crawl, source decisions, image-object caching or
export. Browser image retrieval is explicitly limited to the shared read model.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys
import threading
from unittest.mock import patch
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
PREVIEW = ROOT / 'inbox/brand-media-production-retained-preview'
OUTPUT = ROOT / 'inbox/image-display-proof'
ORIGIN = 'https://enabled-media.invalid'
DRISCOLL = 'company-driscolls'
FALL_CREEK = 'company-fall-creek-farm-and-nursery'
DRISCOLL_PAGE = '/entities/company/' + DRISCOLL + '?tab=overview'
FALL_CREEK_PAGE = '/entities/company/' + FALL_CREEK + '?tab=overview'
COMPARE = '/entities/company/compare?ids=' + DRISCOLL + ',' + FALL_CREEK
os.environ.update(ENABLE_SOURCE_POLLING='false', BIOS_MODE='authoring', BIOS_INBOX_DIR=str(PREVIEW))
import pytest  # noqa: E402,F401 — prevents collection/startup warm-up
import httpx  # noqa: E402
import requests  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    index = PREVIEW / 'brand_media/index.json'
    before = hashlib.sha256(index.read_bytes()).hexdigest()
    from app import main as app_main
    from app.services.brand_media import inventory
    app_main.INBOX_DIR = PREVIEW
    app_main.AUTHORING_MODE = True
    app_main.SOURCE_POLLING_ENABLED = False
    assets = inventory(PREVIEW)
    official = [asset for asset in assets if asset['origin'] == 'official_reference' and asset['display_eligible']]
    assert len(official) == 5 and sum(asset['kind'] == 'logo' for asset in official) == 2
    assert all(not asset.get('object_ref') and not asset['policy']['cache'] and not asset['policy']['export'] for asset in official)
    allowed = {asset['image_url'] for asset in assets if asset['display_eligible'] and (asset.get('image_url') or '').startswith('https://')}
    expected = {asset['image_url']: asset['id'] for asset in official}
    driscoll_urls = [asset['image_url'] for asset in official if asset['entity_id'] == DRISCOLL]
    fall_creek_urls = [asset['image_url'] for asset in official if asset['entity_id'] == FALL_CREEK]
    driscoll_tiles = [asset['image_url'] for asset in official if asset['entity_id'] == DRISCOLL and asset['kind'] != 'logo']
    network_attempts = []

    def deny_network(*args, **kwargs):
        network_attempts.append('External Python transport refused')
        raise AssertionError('Only browser image requests may use external transport')

    with patch.object(httpx.HTTPTransport, 'handle_request', deny_network), patch.object(requests.Session, 'request', deny_network):
        client = TestClient(app_main.app, base_url=ORIGIN)
        pages = {}
        for path in (DRISCOLL_PAGE, FALL_CREEK_PAGE, COMPARE):
            print('Preparing actual preview ' + path, flush=True)
            response = client.get(path)
            assert response.status_code == 200, (path, response.status_code)
            pages[path] = response
        errors, mutations, blocked_hosts, image_requests, loaded = [], [], set(), set(), {}
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path=os.environ.get('CHROME_PATH', r'C:\Program Files\Google\Chrome\Application\chrome.exe'), headless=True, timeout=15000)
            context = browser.new_context(viewport={'width': 1440, 'height': 1050}, record_video_dir=str(OUTPUT / 'video'))
            page = context.new_page()
            page.set_default_timeout(30000)
            page.on('pageerror', lambda error: errors.append(str(error)))

            def intercept(route):
                request = route.request
                url = urlsplit(request.url)
                if url.hostname != 'enabled-media.invalid':
                    if request.url in allowed and request.method == 'GET' and request.resource_type == 'image':
                        image_requests.add(request.url)
                        route.continue_()
                    else:
                        blocked_hosts.add(url.hostname or 'unknown')
                        route.abort()
                    return
                if request.method not in ('GET', 'HEAD'):
                    mutations.append(request.method + ' ' + url.path)
                    route.fulfill(status=403, body='Read-only image proof')
                    return
                path = url.path + ('?' + url.query if url.query else '')
                response = pages.get(path) or client.get(path)
                route.fulfill(status=response.status_code, headers={key: value for key, value in response.headers.items() if key.lower() in ('content-type', 'cache-control', 'x-content-type-options')}, body=response.content)

            page.route('**/*', intercept)

            def wait_loaded(urls):
                # Eager loading is local test scheduling only; source/model stays unchanged.
                page.locator('img').evaluate_all("images=>images.forEach(image=>image.loading='eager')")
                page.wait_for_function('urls=>urls.every(url=>Array.from(document.images).some(image=>image.src===url && image.complete && image.naturalWidth>0))', arg=urls, timeout=45000)
                values = page.locator('img').evaluate_all('images=>images.filter(image=>image.complete&&image.naturalWidth>0).map(image=>({url:image.src,width:image.naturalWidth,height:image.naturalHeight}))')
                for value in values:
                    if value['url'] in expected:
                        loaded[expected[value['url']]] = {'naturalWidth': value['width'], 'naturalHeight': value['height']}

            page.goto(ORIGIN + DRISCOLL_PAGE)
            wait_loaded(driscoll_urls)
            page.wait_for_function("()=>!Array.from(document.querySelectorAll('[data-brand-gallery] img')).some(image=>image.complete&&!image.naturalWidth&&!image.closest('[hidden]'))")
            page.screenshot(path=str(OUTPUT / 'driscolls-real-images.png'))
            print('SCREENSHOT READY ' + str(OUTPUT / 'driscolls-real-images.png'), flush=True)
            # Expand an actual official product tile with the shared inspector.
            image = page.locator('[data-brand-expand] > img').filter(visible=True).first
            for i in range(page.locator('[data-brand-expand] > img').count()):
                candidate = page.locator('[data-brand-expand] > img').nth(i)
                if candidate.get_attribute('src') in driscoll_tiles:
                    image = candidate
                    break
            image.locator('..').click()
            page.locator('dialog[open]').wait_for()
            page.screenshot(path=str(OUTPUT / 'driscolls-real-image-expanded.png'))
            source = page.locator('dialog[open] .brand-media-actions a').last
            assert source.get_attribute('href') == 'https://www.driscolls.com/Berries/blueberries'
            assert source.get_attribute('target') == '_blank'
            page.get_by_role('button', name='Close image inspection', exact=True).click()
            assert page.url == ORIGIN + DRISCOLL_PAGE
            page.goto(ORIGIN + FALL_CREEK_PAGE)
            wait_loaded(fall_creek_urls)
            page.screenshot(path=str(OUTPUT / 'fall-creek-real-logo.png'))
            print('SCREENSHOT READY ' + str(OUTPUT / 'fall-creek-real-logo.png'), flush=True)
            page.goto(ORIGIN + COMPARE)
            wait_loaded(list(expected))
            page.locator('#compare-packaging').scroll_into_view_if_needed()
            page.screenshot(path=str(OUTPUT / 'real-image-comparison.png'))
            compare_scope = page.url
            assert page.locator('#compare-packaging [data-brand-expand] > img').evaluate_all('images=>images.filter(image=>image.complete&&image.naturalWidth>0).length') >= 3
            video_path = page.video.path()
            context.close()
            browser.close()
    assert len(loaded) == 5 and not errors and not mutations and not network_attempts
    assert hashlib.sha256(index.read_bytes()).hexdigest() == before
    result = {
        'result': 'Actual private-preview source images displayed',
        'official_images_loaded': len(loaded), 'loaded_dimensions': loaded,
        'image_delivery': 'Direct source references; browser retrieval only',
        'license_approval_inferred': False, 'local_media_objects_created': 0,
        'cache_or_export_permission_changed': False, 'index_unchanged': True,
        'comparison_scope': compare_scope, 'browser_page_errors': errors, 'mutating_requests': mutations,
        'external_python_transport_attempts': network_attempts,
        'exact_image_urls_requested_count': len(image_requests), 'other_external_hosts_blocked': sorted(blocked_hosts),
        'video_path': str(video_path),
    }
    (OUTPUT / 'results.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    def timeout():
        print('Enabled image proof exceeded 180 seconds', flush=True)
        os._exit(3)
    watchdog = threading.Timer(180, timeout)
    watchdog.daemon = True
    watchdog.start()
    try:
        main()
    finally:
        watchdog.cancel()
