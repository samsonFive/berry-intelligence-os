"""Offline gallery interaction proof using explicitly synthetic UI fixtures.

No real-media delivery claim, provider call, server, or application mutation.
Run with the application Python environment; outputs stay in gitignored inbox.
"""
from __future__ import annotations

import base64
import json
import os
from pathlib import Path
import threading

from jinja2 import Environment, FileSystemLoader, select_autoescape
from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'inbox/brand-media-ui-proof'


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    image = 'data:image/png;base64,' + base64.b64encode(
        (ROOT / 'artifacts/social-blueberry/synthetic-package.png').read_bytes()).decode()
    row = dict(
        id='fixture-only', image_url=image,
        caption='Illustrative UI fixture — not real packaging evidence',
        kind_label='UI fixture', attribution='Synthetic test fixture',
        source_kind='official', source_account='@fixture', published_at='2020-01-01',
        historical_status='historical', match_basis='Layout test only',
        source_page_url='https://example.org/post',
        inspection_href='/api/social/ev-social-' + 'a' * 24 + '/reader?media=metadata-only',
    )
    env = Environment(loader=FileSystemLoader(ROOT / 'app/templates'), autoescape=select_autoescape())
    gallery = env.from_string("{% from '_brand_media.html' import entity_galleries %}{{ entity_galleries(media,'company-test') }}").render(
        media={'packaging': [row, {**row, 'caption': 'Second illustrative UI fixture'}], 'observations': []})
    styles = (ROOT / 'app/static/vendor/bootstrap/bootstrap.min.css').read_text() + (ROOT / 'app/static/brand_media.css').read_text()
    html = ('<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            '<style>' + styles + 'body{font-family:sans-serif;padding:24px;background:#f5f8f1}</style>'
            '</head><body data-personal-digest><main id="digest-main"><h1>Gallery interaction test</h1>'
            '<p>Illustrative UI fixtures only; this is not delivery proof of real imagery.</p>' + gallery +
            '</main><div class="offcanvas offcanvas-end" id="v2ReaderOffcanvas" tabindex="-1">'
            '<div class="offcanvas-header"><h2 id="v2ReaderTitle">Reader</h2>'
            '<button data-bs-dismiss="offcanvas" aria-label="Close reader">Close reader</button></div>'
            '<div class="offcanvas-body" id="v2ReaderBody"></div></div></body></html>')
    results, requests, errors = {}, [], []
    print('Starting offline browser fixture check', flush=True)
    with sync_playwright() as p:
        print('Playwright driver ready', flush=True)
        browser = p.chromium.launch(executable_path=os.environ.get('CHROME_PATH', r'C:\Program Files\Google\Chrome\Application\chrome.exe'), headless=True, timeout=15000)
        context = browser.new_context(viewport={'width': 1280, 'height': 900}, has_touch=True, record_video_dir=str(OUTPUT / 'video'))
        page = context.new_page()
        page.set_default_timeout(5000)
        page.on('pageerror', lambda error: errors.append(str(error)))

        def route(request):
            requests.append(request.request.url)
            if '/api/social/' in request.request.url:
                request.fulfill(content_type='text/html', body='<article><h2 class="v2-reader-title">Metadata-only source fixture</h2><p>No media retrieved.</p></article>')
            else:
                request.fulfill(content_type='text/html', body=html)

        page.route('http://media-ui.invalid/**', route)
        page.goto('http://media-ui.invalid/entities/company/company-test?ids=keep&berry=blueberry')
        for script in ('vendor/bootstrap/bootstrap.bundle.min.js', 'v2.js', 'brand_media.js'):
            page.add_script_tag(path=str(ROOT / 'app/static' / script))
        print('Gallery loaded', flush=True)
        page.screenshot(path=str(OUTPUT / 'desktop-gallery-fixture.png'))
        page.locator('[data-brand-expand]').first.focus()
        page.screenshot(path=str(OUTPUT / 'desktop-context-fixture.png'))
        page.keyboard.press('Enter')
        page.wait_for_selector('dialog[open]')
        results['keyboard_open'] = page.locator('dialog[open]').count() == 1
        page.keyboard.press('ArrowRight')
        results['next_caption'] = page.locator('dialog[open] h3').inner_text()
        page.keyboard.press('Escape')
        page.wait_for_selector('dialog[open]', state='hidden')
        results['focus_restored'] = page.locator('[data-brand-expand]').first.evaluate('(e)=>e===document.activeElement')
        page.locator('[data-brand-expand]').first.click()
        page.locator('dialog[open] [data-brand-source]').click()
        page.wait_for_selector('.v2-reader-title')
        results['source_reader'] = page.locator('.v2-reader-title').inner_text()
        results['source_url'] = page.url
        page.get_by_role('button', name='Close reader', exact=True).click()
        page.wait_for_selector('.offcanvas.show', state='hidden')
        page.wait_for_timeout(350)
        results['scope_retained'] = page.url.endswith('?ids=keep&berry=blueberry')
        results['source_focus_restored'] = page.locator('[data-brand-expand]').first.evaluate('(e)=>e===document.activeElement')
        page.set_viewport_size({'width': 390, 'height': 844})
        page.screenshot(path=str(OUTPUT / 'mobile-gallery-fixture.png'))
        results['mobile_width'] = page.evaluate('document.body.scrollWidth')
        results['viewport'] = 390
        page.locator('[data-brand-expand]').first.tap()
        page.screenshot(path=str(OUTPUT / 'mobile-inspector-fixture.png'))
        results['touch_open'] = page.locator('dialog[open]').count() == 1
        results['errors'] = errors
        results['metadata_endpoint_requested'] = any('/reader?media=metadata-only' in url for url in requests)
        context.close()
        browser.close()
    (OUTPUT / 'results.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
    print(json.dumps(results), flush=True)
    assert all(results[key] for key in ('keyboard_open', 'focus_restored', 'source_focus_restored', 'scope_retained', 'touch_open', 'metadata_endpoint_requested'))
    assert results['mobile_width'] <= results['viewport'] and not errors


if __name__ == '__main__':
    def timeout():
        print('Offline browser check exceeded 55 seconds', flush=True)
        os._exit(3)
    watchdog = threading.Timer(55, timeout)
    watchdog.daemon = True
    watchdog.start()
    try:
        main()
    finally:
        watchdog.cancel()
