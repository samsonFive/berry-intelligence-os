/** Mounted native Learn QA. Existing records only; no research/provider turn. */
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const fields = ['ctx_v','berry','countries','geo_basis','actor_roles','relationship_types','news_from','news_to','focus','cohort_companies','cohort_varieties','demo_specimens','lens','comparison_kind','detail_path','q','q_scope','saved_view_id','saved_revision'];
const selectors = address => Object.fromEntries(fields.map(key => [key, new URL(address).searchParams.get(key) ?? '']));
const settled = page => page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
async function selectedReady(page, title) {
  await page.locator('[data-native-learn="selected"] h1').filter({ hasText: title }).waitFor({ timeout: 60000 });
  await settled(page);
}
async function headingState(page) {
  return page.locator('[data-native-learn="selected"] h1').evaluate(element => {
    const box = element.getBoundingClientRect();
    const active = document.activeElement;
    return { top: box.top, bottom: box.bottom, viewport: innerHeight,
      visible: box.top >= 0 && box.bottom <= innerHeight,
      focus_in_main: !!document.querySelector('#investigation-main')?.contains(active),
      focus_tag: active?.tagName, focus_id: active?.id || '' };
  });
}

export async function runLearnRehearsal({ browser, baseURL, storageState, revision = 'unrecorded', outputDir }) {
  const target = new URL(baseURL);
  assert.ok(['127.0.0.1','localhost','[::1]'].includes(target.hostname));
  assert.equal(target.port, '18998', 'Learn QA uses its dedicated provider-disabled server');
  assert.ok(browser, 'Use the prepared authenticated local browser');
  const destination = path.resolve(outputDir ?? path.join(root, 'artifacts/experience-consolidation/native-learn', String(Date.now())));
  await fs.mkdir(destination, { recursive: true });
  const context = await browser.newContext({ storageState, viewport: { width: 1440, height: 1000 },
    recordVideo: { dir: destination, size: { width: 1440, height: 1000 } } });
  const turns = [], requests = [], errors = [];
  await context.route('**/api/investigations/v1/copilot**', async route => {
    const request = route.request();
    if (request.method() === 'POST') { turns.push({ method: 'POST', path: new URL(request.url()).pathname }); await route.abort('blockedbyclient'); return; }
    await route.continue();
  });
  const page = await context.newPage();
  page.on('pageerror', error => errors.push({ name: error.name, message: error.message.slice(0, 250) }));
  page.on('request', request => {
    const url = new URL(request.url());
    if (url.origin === target.origin && url.pathname.startsWith('/api/investigations/v1/learning'))
      requests.push({ path: url.pathname, q: url.searchParams.get('q') ?? '', pillar: url.searchParams.get('pillar') ?? '', knowledge_class: url.searchParams.get('knowledge_class') ?? '' });
    if (/api\.(perplexity|openai|anthropic)\./.test(url.hostname)) turns.push({ method: request.method(), path: 'external-provider' });
  });
  const report = { status: 'REWORK', revision, checks: [], defects: [], screenshots: {}, provider_turns: turns, learning_requests: requests, client_errors: errors, started_at: new Date().toISOString() };
  const pass = (name, metadata = {}) => report.checks.push({ name, status: 'PASS', ...metadata });
  const capture = async name => { const file = path.join(destination, `${name}.png`); await page.screenshot({ path: file, fullPage: false }); report.screenshots[name] = file; };
  const initial = new URL('/app/learn', baseURL);
  initial.search = new URLSearchParams({ ctx_v: '1', berry: 'berry-blueberry', countries: 'geography-chile,geography-china,geography-peru', geo_basis: 'company_connections',
    focus: 'company-fall-creek-farm-and-nursery', cohort_companies: 'company-fall-creek-farm-and-nursery,company-costa-group-holdings', cohort_varieties: 'variety-eterna', lens: 'comparison', comparison_kind: 'company',
    news_from: '2025-01-01', news_to: '2026-11-11', q: 'Costa', q_scope: 'catalog' }).toString();
  let video;
  try {
    await page.goto(initial.href, { waitUntil: 'domcontentloaded' });
    assert.notEqual(new URL(page.url()).pathname, '/login');
    await page.locator('[data-native-learn="library"] .berry-learn-counts').waitFor({ timeout: 60000 });
    const outer = selectors(page.url());
    const asset = path.basename(await page.locator('script[type="module"]').first().getAttribute('src'));
    report.client_asset = asset;
    const expectedAsset = /index-[A-Za-z0-9_-]+\.js/.exec(revision)?.[0];
    if (expectedAsset) assert.equal(asset, expectedAsset);
    const counts = await page.locator('.berry-learn-counts').innerText();
    assert.match(counts, /27 concepts/); assert.match(counts, /0 saved lessons/);
    assert.equal(await page.getByRole('searchbox', { name: 'Search lessons', exact: true }).inputValue(), '');
    assert.equal(requests.find(row => row.path.endsWith('/learning'))?.q, '');
    const availability = await page.evaluate(async () => { const response = await fetch('/api/investigations/v1/copilot/status'); return response.json(); });
    assert.equal(availability.configured, false);
    assert.match(await page.locator('[data-native-learn="library"]').innerText(), /No saved research lessons are present/);
    await capture('01-library');
    pass('Actual 27 concepts, honest empty private lessons and provider-disabled direct reading', { counts });

    const search = page.getByRole('searchbox', { name: 'Search lessons', exact: true });
    await search.fill('firmness');
    await page.getByLabel('Knowledge class').selectOption('foundational_knowledge');
    await page.getByRole('button', { name: 'Apply filters', exact: true }).click();
    const firmness = page.locator('.berry-learn-entry h3').getByRole('link', { name: 'Firmness', exact: true });
    await firmness.waitFor();
    assert.deepEqual(selectors(page.url()), outer);
    assert.ok(requests.some(row => row.path.endsWith('/learning') && row.q === 'firmness' && row.knowledge_class === 'foundational_knowledge'));
    await firmness.click(); await selectedReady(page, 'Firmness');
    await page.goBack(); await page.locator('[data-native-learn="library"] .berry-learn-counts').waitFor();
    assert.equal(await search.inputValue(), 'firmness');
    assert.equal(await page.getByLabel('Knowledge class').inputValue(), 'foundational_knowledge');
    pass('Local library filters stay independent of global Costa query and survive concept Back');
    await page.getByRole('button', { name: 'Clear filters', exact: true }).click();
    await page.waitForFunction(() => document.querySelectorAll('.berry-learn-entry').length === 27);

    await firmness.scrollIntoViewIfNeeded(); await firmness.focus(); await settled(page);
    const libraryScroll = await page.evaluate(() => scrollY);
    assert.ok(libraryScroll > 200, 'The library-to-concept path must begin genuinely scrolled');
    await firmness.click(); await selectedReady(page, 'Firmness');
    const entryHeading = await headingState(page);
    if (!entryHeading.visible || !entryHeading.focus_in_main) {
      report.defects.push({ name: 'Library-to-concept viewport/focus', observed: entryHeading });
      throw new Error('Concept navigation must reveal its heading and move focus into reading');
    } else pass('Scrolled-library navigation reveals and focuses the selected reading heading', { entry_heading: entryHeading });
    const beforeStep = page.url();
    const step = page.locator('.berry-learn-steps button').nth(1);
    await step.focus(); await page.keyboard.press('Enter');
    assert.equal(await step.getAttribute('aria-pressed'), 'true');
    assert.equal(await page.locator('.berry-learn-step-detail article:not([hidden])').count(), 1);
    assert.equal(page.url(), beforeStep);
    await capture('02-firmness');
    pass('Firmness uses its real cited diagram with keyboard step selection', { entry_heading: entryHeading });
    await page.goBack(); await page.locator('[data-native-learn="library"] .berry-learn-counts').waitFor(); await settled(page);
    await page.waitForFunction(expected => Math.abs(scrollY - expected) < 90, libraryScroll, { timeout: 10000 });
    pass('Back restores the scrolled library after committed data DOM', { library_scroll: libraryScroll, restored_scroll: await page.evaluate(() => scrollY) });

    await firmness.click(); await selectedReady(page, 'Firmness');
    const stable = page.url();
    await page.reload({ waitUntil: 'domcontentloaded' }); await selectedReady(page, 'Firmness');
    assert.equal(page.url(), stable); assert.deepEqual(selectors(page.url()), outer);
    pass('Selected concept deep reload retains scope, focus, cohorts, dates and global query');
    const related = page.locator('.berry-learn-companion a[href*="/app/learn/concept/"]').first();
    await related.scrollIntoViewIfNeeded(); await related.focus(); await settled(page);
    const relatedTitle = await related.innerText(), readingScroll = await page.evaluate(() => scrollY);
    assert.ok(readingScroll > 200);
    await related.click(); await selectedReady(page, relatedTitle);
    const relatedHeading = await headingState(page);
    if (!relatedHeading.visible || !relatedHeading.focus_in_main) {
      report.defects.push({ name: 'Related-concept viewport/focus', observed: relatedHeading });
      throw new Error('Related concept navigation must reveal its heading and move focus into reading');
    } else pass('Related-concept navigation reveals and focuses its reading heading', { related_heading: relatedHeading });
    assert.deepEqual(selectors(page.url()), outer);
    await page.goBack(); await selectedReady(page, 'Firmness'); await settled(page);
    await page.waitForFunction(expected => Math.abs(scrollY - expected) < 90, readingScroll, { timeout: 10000 });
    pass('Related native concept opens from scrolled reading and Back restores its source reading position', { related_title: relatedTitle, related_heading: relatedHeading });

    const expansion = page.locator('.berry-learn-heading a').filter({ hasText: 'Research & expand' });
    const legacy = new URL(await expansion.getAttribute('href'), baseURL);
    assert.equal(legacy.pathname, '/learn/firmness'); assert.equal(legacy.searchParams.get('return_to'), page.url().replace(target.origin, ''));
    const native = page.url(); await expansion.click();
    await page.waitForURL(url => url.pathname === '/learn/firmness');
    const back = page.locator('a[href^="/app/learn/concept/concept-firmness"]').first();
    await back.click(); await selectedReady(page, 'Firmness');
    assert.equal(page.url(), native); assert.deepEqual(selectors(page.url()), outer);
    pass('Explicit legacy expansion returns to the exact native concept and investigation selectors');

    await page.getByRole('link', { name: '← Back to Learn', exact: true }).click();
    await page.locator('[data-native-learn="library"] .berry-learn-counts').waitFor();
    await page.getByRole('button', { name: 'Clear filters', exact: true }).click();
    await search.fill('primocane'); await page.getByRole('button', { name: 'Apply filters', exact: true }).click();
    await page.locator('.berry-learn-entry h3').getByRole('link', { name: 'Primocane vs floricane', exact: true }).click();
    await selectedReady(page, 'Primocane vs floricane');
    const cane = page.locator('.berry-learn-cane');
    const firstYear = cane.getByRole('button', { name: 'Primocane-fruiting', exact: true });
    const unchanged = page.url(); await firstYear.focus(); await page.keyboard.press('Space');
    assert.equal(await firstYear.getAttribute('aria-pressed'), 'true');
    assert.match(await cane.innerText(), /May fruit on first-year canes/); assert.equal(page.url(), unchanged);
    const figure = page.locator('.berry-learn-photo'); await figure.waitFor();
    assert.match(await figure.innerText(), /Steffen Flor/); assert.match(await figure.innerText(), /CC BY 2\.5/);
    assert.ok(await figure.locator('img').getAttribute('alt')); assert.ok(await figure.getByRole('link', { name: 'Photo source', exact: true }).getAttribute('href'));
    await cane.scrollIntoViewIfNeeded(); await capture('03-cane-calendar');
    await figure.scrollIntoViewIfNeeded();
    report.licensed_image = await figure.locator('img').evaluate(async image => {
      if (!image.complete) await new Promise(resolve => {
        const timer = setTimeout(resolve, 5000);
        const done = () => { clearTimeout(timer); resolve(); };
        image.addEventListener('load', done, { once: true }); image.addEventListener('error', done, { once: true });
      });
      return { complete: image.complete, natural_width: image.naturalWidth, pixels_confirmed: image.complete && image.naturalWidth > 0 };
    });
    await capture('04-licensed-figure');
    pass('Cane calendar preserves authored biology, keyboard controls and licensed photo attribution');
    await page.setViewportSize({ width: 390, height: 844 });
    await cane.scrollIntoViewIfNeeded(); await settled(page);
    const geometry = await page.evaluate(() => ({ viewport: innerWidth, document: document.documentElement.scrollWidth }));
    assert.ok(geometry.document <= geometry.viewport + 1);
    await cane.getByRole('button', { name: 'Floricane-fruiting', exact: true }).focus(); await page.keyboard.press('Enter');
    assert.match(await cane.innerText(), /First-year growth/); assert.deepEqual(selectors(page.url()), outer);
    await capture('05-narrow-cane');
    pass('Narrow layout and keyboard reading preserve investigation context', geometry);
    assert.equal(errors.length, 0); assert.equal(turns.length, 0);
    report.status = report.defects.length ? 'REWORK' : 'PASS';
  } catch (error) {
    report.defect = { message: error.message };
    await capture('failure-state').catch(() => {});
    report.failed_url = page.url();
  } finally {
    video = page.video(); await context.close();
    if (video) report.continuous_recording = await video.path();
    report.finished_at = new Date().toISOString();
    await fs.writeFile(path.join(destination, 'acceptance.json'), JSON.stringify(report, null, 2));
  }
  return { report, outputDir: destination };
}
