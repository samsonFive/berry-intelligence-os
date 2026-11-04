import os, secrets, threading, time, json
from pathlib import Path
os.environ.update(BIOS_REMOTE_INTERACTIVE='true', BIOS_REVIEW_USERNAME='watchlist-review', BIOS_REVIEW_PASSWORD=secrets.token_urlsafe(24), BIOS_SESSION_SECRET=secrets.token_urlsafe(48), ENABLE_SOURCE_POLLING='false')
import pytest  # Disable startup warm-up/collection in this bounded visual test.
import uvicorn
from app import main
from playwright.sync_api import sync_playwright
main.INBOX_DIR=Path('tmp/global-watchlist-visual')
server=uvicorn.Server(uvicorn.Config(main.app, host='127.0.0.1',port=18765,log_level='warning'))
thread=threading.Thread(target=server.run,daemon=True);thread.start()
for _ in range(100):
 if server.started: break
 time.sleep(.1)
folder=Path('docs/missions/global-watchlist-20261104/screenshots');folder.mkdir(parents=True,exist_ok=True)
results={}
try:
 with sync_playwright() as p:
  browser=p.chromium.launch(executable_path=os.environ.get('CHROME_PATH', r'C:\Program Files\Google\Chrome\Application\chrome.exe'),headless=True)
  context=browser.new_context(viewport={'width':1440,'height':1000})
  page=context.new_page(); errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  page.goto('http://127.0.0.1:18765/global-watchlist');page.locator('#username').fill('watchlist-review');page.locator('#password').fill(os.environ['BIOS_REVIEW_PASSWORD']);page.locator('button[type=submit]').click();page.goto('http://127.0.0.1:18765/global-watchlist')
  page.screenshot(path=str(folder/'desktop-watchlist.png'),full_page=False)
  page.locator('#gw-results').scroll_into_view_if_needed();page.screenshot(path=str(folder/'desktop-results.png'),full_page=False)
  page.locator('.gw-select').nth(0).check();page.locator('.gw-select').nth(1).check();page.locator('#gw-compare-button').click();page.wait_for_url('**/global-watchlist?**compare=**');page.screenshot(path=str(folder/'desktop-comparison.png'),full_page=False)
  results['comparison_profile_count']=page.locator('.gw-profile').count()
  page.locator('#gw-results').scroll_into_view_if_needed();page.screenshot(path=str(folder/'desktop-comparison-details.png'),full_page=False)
  page.goto('http://127.0.0.1:18765/global-watchlist?company=company-planasa&berry=blueberry');page.screenshot(path=str(folder/'desktop-profile.png'),full_page=False)
  with page.expect_download() as download:
   page.get_by_role('link',name='Export PDF').click()
  download.value.save_as('output/pdf/global-watchlist-planasa.pdf')
  page.set_viewport_size({'width':390,'height':844});page.goto('http://127.0.0.1:18765/global-watchlist');page.screenshot(path=str(folder/'mobile-watchlist.png'),full_page=False)
  results['mobile_body_width']=page.evaluate('document.body.scrollWidth');results['mobile_viewport_width']=390
  page.goto('http://127.0.0.1:18765/global-watchlist?company=company-planasa');page.screenshot(path=str(folder/'mobile-profile.png'),full_page=False)
  results['mobile_profile_width']=page.evaluate('document.body.scrollWidth')
  page.locator('#gw-results').scroll_into_view_if_needed();page.screenshot(path=str(folder/'mobile-profile-details.png'),full_page=False)
  results['page_errors']=errors
  browser.close()
finally:
 server.should_exit=True;thread.join(timeout=10)
Path('docs/missions/global-watchlist-20261104/visual-results.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
print(json.dumps(results),flush=True)
