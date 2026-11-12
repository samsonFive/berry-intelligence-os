/** Real retained-News/Reader/return checks. No provider, source acquisition or domain mocks. */
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';

const stable = url => {
  const values = Object.fromEntries(new URL(url).searchParams);
  delete values.detail_path;
  return values;
};
const timeout = 60_000;

export async function runBriefingRehearsal({ browser, baseURL, storageState, revision, outputDir }) {
  const origin = new URL(baseURL).origin;
  assert.ok(['127.0.0.1', 'localhost'].includes(new URL(baseURL).hostname));
  await fs.mkdir(outputDir, { recursive: true });
  const context = await browser.newContext({ storageState, viewport: { width: 1440, height: 1000 }, recordVideo: { dir: outputDir, size: { width: 1440, height: 1000 } } });
  const report = { status: 'REWORK', revision, checks: [], failures: [], legacy_destinations: [], explicit_control_checks: [], provider_turns: [], mutation_requests: [], page_errors: [], api_timings: [], screenshots: {} };
  const starts = new Map();
  await context.route('**/*', async route => {
    const request = route.request(), url = new URL(request.url());
    if (/api\.(openai|anthropic|perplexity)\./.test(url.hostname)) {
      report.provider_turns.push({ method: request.method(), path: url.pathname }); await route.abort('blockedbyclient'); return;
    }
    if (url.origin === origin && request.method() === 'POST') {
      const method = url.pathname.startsWith('/api/investigations/v1/copilot') ? request.postDataJSON()?.method : null;
      if (!['info', 'agent/connect', 'agent/stop'].includes(method)) {
        const target = url.pathname.includes('/copilot') ? report.provider_turns : report.mutation_requests;
        let initiator = 'unavailable';
        try { initiator = new URL(request.frame().url()).pathname; } catch { /* No request payload or query enters diagnostics. */ }
        target.push({ method: request.method(), path: url.pathname, initiator_path: initiator }); await route.abort('blockedbyclient'); return;
      }
    }
    await route.continue();
  });
  const page = await context.newPage();
  page.on('pageerror', error => report.page_errors.push(error.message));
  page.on('request', request => { if (new URL(request.url()).origin === origin && new URL(request.url()).pathname.startsWith('/api/')) starts.set(request, Date.now()); });
  page.on('response', response => {
    const started = starts.get(response.request());
    if (started !== undefined) { report.api_timings.push({ endpoint: new URL(response.url()).pathname, status: response.status(), duration_ms: Date.now() - started }); starts.delete(response.request()); }
  });
  const capture = async (label, filename) => {
    await page.waitForFunction(() => !document.querySelector('.berry-main .berry-loading'), null, { timeout });
    await page.waitForFunction(() => Array.from(document.images).filter(img => {
      const rect = img.getBoundingClientRect(); return rect.width && rect.height && rect.bottom > 0 && rect.top < innerHeight;
    }).every(img => img.complete), null, { timeout: 10_000 }).catch(() => {});
    await page.waitForTimeout(200);
    const destination = path.join(outputDir, filename); await page.screenshot({ path: destination }); report.screenshots[label] = destination;
  };
  let step = 'scoped Landscape → native Briefing';
  try {
    const target = new URL('/app/landscape', baseURL);
    target.search = new URLSearchParams({ ctx_v: '1', berry: 'berry-blueberry', countries: 'geography-china', geo_basis: 'company_connections',
      cohort_companies: 'company-fall-creek-farm-and-nursery,company-costa-group-holdings', lens: 'comparison', comparison_kind: 'company',
      news_from: '2024-01-01', news_to: '2026-11-11', q_scope: 'scope' }).toString();
    await page.goto(target.href, { waitUntil: 'domcontentloaded' });
    await page.locator('.berry-comparison-table').waitFor({ timeout });
    await page.locator('.berry-developments .berry-loading').waitFor({ state: 'hidden', timeout });
    const original = stable(page.url());
    await page.getByRole('link', { name: 'Open scoped Briefing →', exact: true }).click();
    await page.waitForURL(url => url.pathname === '/app/briefing');
    await page.getByRole('heading', { name: 'Briefing', exact: true }).waitFor();
    await page.locator('.berry-briefing-cards .berry-news-card').first().waitFor({ timeout });
    assert.deepEqual(stable(page.url()), original);
    const briefingURL = page.url();
    const count = await page.locator('.berry-briefing-cards .berry-news-card').count();
    assert.ok(count > 0 && count <= 6);
    assert.ok((await page.locator('.berry-briefing-basis').innerText()).includes('Selected comparison cohort'));
    assert.ok((await page.locator('.berry-briefing-basis').innerText()).includes('matching retained developments'));
    await capture('populated', '01-native-briefing.png');
    report.checks.push({ name: 'Scoped native Briefing retains full selectors, server comparison basis and bounded six-card count', status: 'PASS', visible_cards: count });

    step = 'shared Reader section/history/reload';
    const trigger = page.locator('.berry-briefing-cards').getByRole('button', { name: 'Read source →', exact: true }).first();
    await trigger.focus(); await page.keyboard.press('Enter');
    await page.locator('.berry-detail [aria-label="Source Reader"]').waitFor({ timeout });
    assert.deepEqual(stable(page.url()), original);
    await page.locator('.berry-detail').getByRole('button', { name: 'Brief', exact: true }).click();
    await page.waitForURL(url => url.searchParams.get('detail_path')?.endsWith('@brief'));
    const sourceURL = page.url();
    await page.reload({ waitUntil: 'domcontentloaded' });
    await page.locator('.berry-detail [aria-label="Source Reader"]').waitFor({ timeout });
    assert.equal(page.url(), sourceURL);
    assert.equal(await page.locator('.berry-detail').getByRole('button', { name: 'Brief', exact: true }).getAttribute('aria-pressed'), 'true');
    await capture('reader', '02-briefing-shared-reader.png');
    await page.locator('.berry-detail').getByRole('button', { name: /Return to investigation|Back to previous detail/ }).first().click();
    await page.waitForURL(briefingURL);
    await page.goBack(); await page.locator('.berry-detail [aria-label="Source Reader"]').waitFor();
    assert.equal(page.url(), sourceURL);
    await page.goForward(); await page.waitForURL(briefingURL);
    report.checks.push({ name: 'Briefing source uses shared Reader; Brief section reload, close and Back/Forward preserve exact context', status: 'PASS' });

    step = 'governed compatibility destinations';
    const deeper = page.getByRole('link', { name: 'Open full scoped News ↗', exact: true });
    const links = [{ label: 'Full scoped News', href: await deeper.getAttribute('href') }, ...await page.getByRole('navigation', { name: 'Existing briefing views', exact: true }).locator('a').evaluateAll(rows => rows.map(link => ({ label: link.querySelector('strong')?.textContent, href: link.getAttribute('href') })))];
    assert.equal(links.length, 6);
    for (const link of links) {
      const destination = new URL(link.href, baseURL);
      assert.equal(destination.origin, origin);
      const returnTo = destination.searchParams.get('return_to');
      assert.equal(new URL(returnTo, baseURL).pathname, '/app/briefing');
      assert.deepEqual(stable(new URL(returnTo, baseURL).href), original);
      const legacyPage = await context.newPage();
      try {
        const response = await legacyPage.goto(destination.href, { waitUntil: 'domcontentloaded', timeout });
        const status = response?.status();
        const returned = await legacyPage.locator('a').evaluateAll((anchors, href) => anchors.some(anchor => anchor.getAttribute('href') === href), returnTo);
        report.legacy_destinations.push({ label: link.label, path: destination.pathname, status, native_return_link: returned });
        assert.equal(status, 200, `${link.label} must resolve to its existing governed view`);
        assert.equal(returned, true, `${link.label} must retain the exact native return link`);
        if (destination.pathname === '/news') {
          const panel = legacyPage.locator('[data-tags-panel]');
          assert.equal(await panel.getAttribute('data-auto-recheck'), 'false');
          const job = await legacyPage.locator('[data-tag-status]').getAttribute('data-job-status');
          assert.equal(job, 'pending', 'A fresh pending job must exercise the former automatic trigger');
          await legacyPage.waitForTimeout(350);
          assert.equal(report.mutation_requests.length, 0, 'A native reading expansion must not queue classification');
          let intercepted = 0;
          await legacyPage.route('**/api/news/tags/classify', route => {
            intercepted++;
            return route.fulfill({ status: 202, contentType: 'application/json', body: JSON.stringify({ status: 'queued' }) });
          });
          await legacyPage.locator('.news-tag-tools > summary').click();
          await legacyPage.getByRole('button', { name: 'Recheck stored articles', exact: true }).click();
          await legacyPage.locator('[data-tag-status]').filter({ hasText: 'Classifying stored articles…' }).waitFor({ timeout });
          assert.equal(intercepted, 1, 'The explicit control must remain connected, without executing its server work');
          report.explicit_control_checks.push({ control: 'Recheck stored articles', pending_on_load_posts: 0, explicit_posts_intercepted: intercepted, response: 202, classifier_executed: false });
        }
      } finally { await legacyPage.close(); }
    }
    report.checks.push({ name: 'Actual News/Following/Saved/Reading/Social/Signals GETs exist and retain exact native return links', status: 'PASS' });

    step = 'narrow Reader keyboard';
    await page.setViewportSize({ width: 390, height: 844 });
    const narrowTrigger = page.locator('.berry-briefing-cards').getByRole('button', { name: 'Read source →', exact: true }).first();
    await narrowTrigger.focus(); await page.keyboard.press('Enter');
    await page.locator('.berry-detail[aria-modal="true"] [aria-label="Source Reader"]').waitFor({ timeout });
    await capture('narrow', '03-briefing-narrow-reader.png');
    for (let i = 0; i < 12; i++) { await page.keyboard.press('Tab'); assert.equal(await page.evaluate(() => document.querySelector('.berry-detail')?.contains(document.activeElement)), true); }
    await page.keyboard.press('Escape'); await page.locator('.berry-detail').waitFor({ state: 'hidden' });
    await page.waitForFunction(() => document.activeElement?.matches('button') && document.activeElement.textContent.includes('Read source'), null, { timeout: 4000 });
    assert.deepEqual(stable(page.url()), original);
    report.checks.push({ name: 'Narrow shared Reader contains keyboard focus and Escape returns to source trigger', status: 'PASS' });
    await page.setViewportSize({ width: 1440, height: 1000 });
    step = 'native surface shell and selector continuity';
    for (const [label, pathname] of [['Workspaces', '/app/workspaces'], ['Learn', '/app/learn'], ['Briefing', '/app/briefing']]) {
      await page.getByRole('navigation', { name: 'Primary', exact: true }).getByRole('link', { name: label, exact: true }).click();
      await page.waitForURL(url => url.pathname === pathname);
      await page.locator('.berry-main h1').waitFor({ timeout });
      assert.deepEqual(stable(page.url()), original);
      assert.equal(await page.locator('.berry-shell').count(), 1); assert.equal(await page.locator('main#investigation-main').count(), 1);
    }
    report.checks.push({ name: 'Workspaces/Learn/Briefing route returns keep one native shell and unchanged outer investigation selectors', status: 'PASS' });
    await page.getByRole('link', { name: 'Back to Landscape →', exact: true }).click();
    await page.locator('.berry-comparison-table').waitFor({ timeout });
    assert.equal(new URL(page.url()).pathname, '/app/landscape'); assert.deepEqual(stable(page.url()), original);
    report.checks.push({ name: 'Native return restores the same Landscape comparison and selectors', status: 'PASS' });
    assert.equal(report.provider_turns.length, 0); assert.equal(report.mutation_requests.length, 0); assert.equal(report.page_errors.length, 0);
    report.status = 'REVIEW_REQUIRED';
  } catch (error) { report.failures.push({ step, message: error.message }); await capture('failure', 'failure-state.png').catch(() => {}); }
  finally { await context.close(); report.video = await page.video()?.path(); await fs.writeFile(path.join(outputDir, 'briefing-acceptance.json'), JSON.stringify(report, null, 2)); }
  return { outputDir, report };
}
