"""Opt-in browser acceptance: run app on localhost:18321, then run this script.
Requires the existing local Playwright installation; no collection/AI calls.
Writes screenshots and a PDF under artifacts/global-explorer (not canonical data).
"""
from playwright.sync_api import sync_playwright
from pathlib import Path
Path('artifacts/global-explorer').mkdir(parents=True, exist_ok=True)
with sync_playwright() as p:
    browser=p.chromium.launch()
    page=browser.new_page(viewport={'width':1440,'height':1000})
    errors=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto('http://127.0.0.1:18321/explorer')
    page.locator('#gx-boundaries path').first.wait_for()
    for eid in ['geography-peru','geography-chile','geography-china']:
        el=page.locator(f'path[data-country="{eid}"]')
        el.focus(); el.press('Enter')
    page.locator('#gx-berry').select_option('berry-blueberry')
    page.wait_for_function("location.search.includes('berry-blueberry') && document.getElementById('gx-map-status').textContent.includes('updated')")
    assert page.locator('.gx-chip').count()==3
    assert 'berry-blueberry' in page.locator('[data-clear-countries]').get_attribute('href')
    assert page.locator('path.is-selected').count()>=3
    page.screenshot(path='artifacts/global-explorer/desktop.png',full_page=False)
    first = page.locator('[data-intel-card] [data-open-reader]').first
    item_id = first.locator('xpath=ancestor::li').get_attribute('data-item-id')
    first.click()
    page.locator('#v2ReaderOffcanvas.show').wait_for()
    page.wait_for_function("document.getElementById('v2ReaderBody').textContent.length > 200")
    assert item_id in page.url
    page.keyboard.press('Escape')
    page.locator('#v2ReaderOffcanvas.show').wait_for(state='hidden')
    page.get_by_role('link',name='Create Market Snapshot').click()
    assert 'geography-peru' in page.url and 'berry-blueberry' in page.url
    page.locator('[data-section="varieties"]').uncheck()
    page.get_by_role('button',name='Update composition').click()
    assert 'varieties' not in page.url
    page.wait_for_load_state('networkidle')
    page.screenshot(path='artifacts/global-explorer/snapshot.png',full_page=False)
    with page.expect_download() as dl:
        page.get_by_role('button',name='Export PDF').click()
    dl.value.save_as('artifacts/global-explorer/market-snapshot.pdf')
    page.get_by_role('link',name='Back to explorer').click()
    assert page.locator('.gx-chip').count()==3
    mobile=browser.new_page(viewport={'width':390,'height':844},is_mobile=True,has_touch=True)
    mobile.goto('http://127.0.0.1:18321/explorer?countries=geography-peru,geography-chile,geography-china&berry=berry-blueberry')
    mobile.locator('#gx-boundaries path').first.wait_for()
    assert mobile.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
    mobile.locator('.gx-country-picker summary').click()
    mobile.locator('#gx-search').fill('Peru')
    mobile.locator('.gx-country-list input[value="geography-peru"]').uncheck()
    mobile.wait_for_function("document.getElementById('gx-map-status').textContent.includes('updated')")
    assert mobile.locator('.gx-chip').count()==2
    mobile.locator('path[data-country="geography-peru"]').tap()
    mobile.wait_for_function("document.getElementById('gx-map-status').textContent.includes('updated')")
    assert mobile.locator('.gx-chip').count()==3
    mobile.screenshot(path='artifacts/global-explorer/mobile.png',full_page=False)
    tablet=browser.new_page(viewport={'width':820,'height':1180})
    tablet.goto('http://127.0.0.1:18321/explorer?countries=geography-peru&berry=berry-blackberry')
    tablet.locator('#gx-boundaries path').first.wait_for()
    assert tablet.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
    tablet.screenshot(path='artifacts/global-explorer/tablet.png',full_page=False)
    empty=browser.new_page()
    empty.goto('http://127.0.0.1:18321/explorer?countries=iso:KW&berry=berry-blueberry')
    empty.get_by_text('No published evidence in this scope').wait_for()
    assert empty.locator('.gx-chip').count()==1
    fallback=browser.new_page()
    fallback.route('**/countries.geojson', lambda route: route.abort())
    fallback.goto('http://127.0.0.1:18321/explorer')
    fallback.get_by_text('Map unavailable. Use the country selection list below.').wait_for()
    assert fallback.locator('.gx-country-picker').get_attribute('open') is not None
    print('Browser acceptance passed; errors:', errors)
    assert not errors
    browser.close()
