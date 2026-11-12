/** Real local-app rehearsal. No mocked records, provider results, or saved credentials. */
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { createRequire } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { installCommandDiagnostics, sanitizeRunEnvelope } from './command-diagnostics.mjs';

const repository = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const runtime = process.env.BERRY_PLAYWRIGHT_ROOT ?? path.join(os.homedir(), '.cache/codex-runtimes/codex-primary-runtime/dependencies/node');
const runtimeRequire = createRequire(path.join(runtime, 'package.json'));
const { chromium } = runtimeRequire('playwright');
const chromiumPath = process.env.BERRY_CHROMIUM_PATH ?? path.join(os.homedir(), 'AppData/Local/ms-playwright/chromium-1234/chrome-win64/chrome.exe');

const fields = ['ctx_v', 'berry', 'countries', 'geo_basis', 'actor_roles', 'relationship_types', 'news_from', 'news_to', 'focus', 'cohort_companies', 'cohort_varieties', 'demo_specimens', 'lens', 'comparison_kind', 'detail_path', 'q', 'q_scope', 'saved_view_id', 'saved_revision'];
function selectors(url) {
  const params = new URL(url).searchParams;
  return Object.fromEntries(fields.map(field => [field, params.get(field) ?? '']));
}
function presentationURL(baseURL) {
  const url = new URL('/app/landscape', baseURL);
  url.search = new URLSearchParams({ ctx_v: '1', berry: 'berry-blueberry', countries: 'geography-chile,geography-china,geography-peru', geo_basis: 'company_connections', lens: 'connections', comparison_kind: 'company', q_scope: 'scope' }).toString();
  return url.href;
}
async function populated(page) {
  await page.locator('.berry-relationship-row').first().waitFor({ state: 'visible', timeout: 90_000 });
  await page.locator('.berry-relationship-edge').first().waitFor({ state: 'visible' });
}
async function closeDetails(page) {
  for (let index = 0; index < 10 && await page.locator('.berry-detail').count(); index++) {
    const back = page.locator('.berry-detail').getByRole('button', { name: /Back to previous detail|Return to investigation/ }).first();
    if (!await back.count()) break;
    await back.click();
    await page.waitForTimeout(60);
  }
  assert.equal(await page.locator('.berry-detail').count(), 0, 'One coordinated detail area must close completely');
}
async function actorButton(page, label) {
  let button = page.locator('.berry-relationship-actor .berry-entity-button').filter({ hasText: label }).first();
  if (!await button.count()) {
    const expand = page.getByRole('button', { name: /Show all \d+ actors in this scope/ });
    if (await expand.count()) await expand.click();
    button = page.locator('.berry-relationship-actor .berry-entity-button').filter({ hasText: label }).first();
  }
  assert.equal(await button.count(), 1, `The current scope must visibly contain ${label}`);
  return button;
}
function isProviderTurn(request, origin) {
  const url = new URL(request.url());
  if (url.origin !== origin || request.method() !== 'POST' || !url.pathname.includes('/api/investigations/v1/copilot')) return false;
  if (/\/(info|status|connect|stop)$/.test(url.pathname)) return false;
  try {
    const body = request.postDataJSON();
    if (['info', 'agent/info', 'connect', 'agent/connect', 'stop', 'agent/stop'].includes(body?.method)) return false;
  } catch { /* A non-JSON runtime POST is conservatively a possible turn. */ }
  return true;
}
function usageOnly(value) {
  if (!Array.isArray(value)) return [];
  return value.filter(row => row && typeof row === 'object').map(row => {
    const result = {};
    for (const key of ['provider', 'model']) if (typeof row[key] === 'string') result[key] = row[key].slice(0, 180);
    for (const key of ['inputTokens', 'outputTokens', 'totalTokens', 'reasoningTokens', 'cachedInputTokens', 'cacheReadInputTokens', 'cacheWriteInputTokens']) {
      if (Number.isFinite(row[key]) && row[key] >= 0) result[key] = row[key];
    }
    return result;
  });
}

/** Root may pass in-memory storageState/cookies. Neither is written to artifacts. */
export async function runRehearsal(options) {
  const { baseURL, storageState, cookies = [], revision = 'unrecorded', approvedCopilotCommand, saveAndReopen } = options;
  const target = new URL(baseURL);
  assert.ok(['localhost', '127.0.0.1', '[::1]'].includes(target.hostname), 'This rehearsal runs only against the explicitly started local app');
  assert.ok(['http:', 'https:'].includes(target.protocol));
  const stamp = new Date().toISOString().replaceAll(':', '-').replaceAll('.', '-');
  const outputDir = path.resolve(options.outputDir ?? path.join(repository, 'artifacts/experience-consolidation', `v1-${stamp}`));
  await fs.mkdir(outputDir, { recursive: true });
  const browser = options.browser ?? await chromium.launch({ executablePath: chromiumPath, headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, reducedMotion: 'no-preference',
    ...(storageState ? { storageState } : {}), recordVideo: { dir: outputDir, size: { width: 1440, height: 1000 } } });
  if (cookies.length) await context.addCookies(cookies);
  await context.addInitScript(installCommandDiagnostics);
  let providerPhase = false;
  const unexpectedTurns = [];
  const approvedTurns = [];
  const runShapes = [];
  const usageRecords = [];
  const usageReads = [];
  await context.route('**/api/investigations/v1/copilot**', async route => {
    const request = route.request();
    if (isProviderTurn(request, target.origin)) {
      if (!providerPhase) { unexpectedTurns.push({ method: request.method(), path: new URL(request.url()).pathname }); await route.abort('blockedbyclient'); return; }
      approvedTurns.push({ method: request.method(), path: new URL(request.url()).pathname });
      try { const shape = sanitizeRunEnvelope(request.postDataJSON()); if (shape) runShapes.push(shape); } catch { runShapes.push({ unavailable: true }); }
    }
    await route.continue();
  });
  const page = await context.newPage();
  const apiTimings = [], apiStarts = new Map();
  page.on('request', request => { if (new URL(request.url()).origin === target.origin && new URL(request.url()).pathname.startsWith('/api/')) apiStarts.set(request, Date.now()); });
  page.on('response', response => {
    const started = apiStarts.get(response.request());
    if (started !== undefined) { apiTimings.push({ endpoint: new URL(response.url()).pathname, status: response.status(), duration_ms: Date.now() - started }); apiStarts.delete(response.request()); }
    if (!providerPhase || !isProviderTurn(response.request(), target.origin)) return;
    const requestIndex = usageReads.length + 1;
    usageReads.push((async () => {
      let terminal = 'NOT_EXPOSED'; const usage = [];
      if ((response.headers()['content-type'] ?? '').includes('text/event-stream')) {
        const stream = await response.text();
        for (const line of stream.split(/\r?\n/)) {
          if (!line.startsWith('data:')) continue;
          try {
            const event = JSON.parse(line.slice(5).trim());
            if (event.type === 'RUN_ERROR') terminal = 'RUN_ERROR';
            if (event.type === 'RUN_FINISHED') {
              terminal = 'RUN_FINISHED';
              usage.push(...usageOnly(event.usage ?? event.result?.usage ?? event.data?.usage));
            }
          } catch { /* Other event payloads are discarded, never logged. */ }
        }
      }
      usageRecords.push({ request_index: requestIndex, status: response.status(), terminal, usage });
    })().catch(() => { usageRecords.push({ request_index: requestIndex, status: response.status(), terminal: 'UNAVAILABLE', usage: [] }); }));
  });
  const clientErrors = [];
  page.on('pageerror', error => clientErrors.push(error.message));
  const report = { v1_status: 'REWORK', application_revision: revision, environment: target.origin,
    started_at: new Date().toISOString(), record_ids: {}, screenshots: {}, checks: [],
    copilot: { status: 'NOT_RUN', reason: 'A real approved provider command was not supplied.' },
    save_reopen: { status: 'NOT_RUN', reason: 'Use the dedicated native Workspaces save/reopen packet unless an explicit callback is supplied to this direct-flow run.' },
    defects: [], manual_visual_review: 'REQUIRED', unexpected_provider_turns: unexpectedTurns,
    approved_provider_turn_requests: approvedTurns, provider_usage: usageRecords, command_run_shapes: runShapes, client_errors: clientErrors, api_timings: apiTimings };
  const pass = (name, evidence = {}) => report.checks.push({ name, status: 'PASS', ...evidence });
  const capture = async (name, filename) => {
    await page.locator('.berry-developments .berry-loading').waitFor({ state: 'hidden', timeout: 90_000 });
    await page.waitForFunction(() => Array.from(document.images).filter(img => {
      const rect = img.getBoundingClientRect(); return rect.width > 0 && rect.height > 0 && rect.bottom > 0 && rect.top < innerHeight && rect.right > 0 && rect.left < innerWidth;
    }).every(img => img.complete), null, { timeout: 10_000 }).catch(() => {});
    const file = path.join(outputDir, filename); await page.screenshot({ path: file, fullPage: false }); report.screenshots[name] = file;
  };
  let videoPath;
  try {
    const initialURL = presentationURL(baseURL);
    await page.goto(initialURL, { waitUntil: 'domcontentloaded' });
    assert.notEqual(new URL(page.url()).pathname, '/login', 'An authenticated local session is required; credentials are never recorded by this script');
    await populated(page);
    const applied = selectors(page.url());
    // Use Chromium's real authenticated network stack. Windows may deny Node's
    // raw loopback sockets even while the application itself is reachable.
    const response = await page.evaluate(async endpoint => {
      const result = await fetch(endpoint, { credentials: 'same-origin', cache: 'no-store' });
      return { status: result.status, body: await result.json() };
    }, `/api/investigations/v1/landscape?${new URLSearchParams(applied)}&revision=0`);
    assert.equal(response.status, 200);
    const model = response.body.data;
    const actorTypes = rows => Object.fromEntries([...new Set(rows.map(row => row.actor.type))].map(type => [type, rows.filter(row => row.actor.type === type).length]));
    report.portrait_actor_types = { market_rows: actorTypes(model.market_rows), portfolios: actorTypes(model.portfolios) };
    report.non_company_portrait_ids = [...new Set([...model.market_rows, ...model.portfolios].filter(row => row.actor.type !== 'company').map(row => row.actor.id))];
    assert.equal(report.non_company_portrait_ids.length, 0, 'Company bands may not reinterpret a breeding program as a company');
    const companies = Object.values(model.nodes).filter(node => node.type === 'company');
    const fallCreek = companies.find(node => /fall creek/i.test(node.label));
    const costa = companies.find(node => /costa/i.test(node.label));
    const candidates = fallCreek && costa ? [fallCreek, costa] : companies.slice(0, 2);
    assert.equal(candidates.length, 2, 'Two actual in-scope actors are needed for the populated comparison');
    report.scenario_note = fallCreek && costa ? 'Current scope contains the candidate Fall Creek/Costa actors.' : 'Candidate cohort incomplete; actual supported scope actors used transparently.';
    const company = candidates[0];
    const exactEdge = model.edges.find(edge => edge.subject_id === company.id || edge.object_id === company.id);
    assert.ok(exactEdge?.evidence_ids?.length, 'An exact sourced relationship is required');
    report.record_ids = { companies: candidates.map(node => node.id), relationship: exactEdge.id, source: exactEdge.evidence_ids[0] };
    const readout = await page.locator('.berry-readout').innerText();
    await capture('initial', '01-initial-landscape.png');
    pass('Populated relationships and activity are visible before interaction', { edge_count: model.edges.length });

    const previewTrigger = page.locator('.berry-relationship-edge .berry-preview-trigger').first();
    const beforePreview = page.url();
    await previewTrigger.hover();
    await page.locator('.berry-preview').waitFor({ state: 'visible' });
    assert.equal(page.url(), beforePreview, 'Hover preview must not change history or selectors');
    await page.locator('.berry-preview').getByRole('button', { name: 'Open detail', exact: true }).focus();
    await page.keyboard.press('Escape');
    await page.locator('.berry-preview').waitFor({ state: 'hidden' });
    assert.equal(page.url(), beforePreview);
    for (let repeat = 0; repeat < 2; repeat++) {
      await previewTrigger.focus(); await page.keyboard.press('Enter');
      await page.waitForFunction(() => {
        const detail = document.querySelector('.berry-detail');
        return detail && !detail.hasAttribute('aria-busy');
      }, null, { timeout: 60_000 });
      await page.waitForTimeout(200);
      assert.ok(await page.evaluate(() => document.querySelector('.berry-detail')?.contains(document.activeElement)), 'Preview activation must leave stable focus in persistent detail, including cached reopen');
      await closeDetails(page);
    }
    pass('Enterable hover/focus preview, Escape dismissal and repeated keyboard detail activation');

    await (await actorButton(page, company.label)).click();
    await page.locator('.berry-detail h2').filter({ hasText: company.label }).waitFor({ timeout: 60_000 });
    assert.equal(selectors(page.url()).focus, company.id);
    assert.equal(await page.locator('.berry-readout').innerText(), readout, 'Focus must not redefine scope findings');
    assert.equal(selectors(page.url()).cohort_companies, '', 'Focus does not pin a comparison subject');
    await capture('company', '02-company-selected.png');
    pass('Company focus preserves base scope, findings and separate pins');

    const relationshipButton = page.locator('.berry-detail').getByRole('button', { name: exactEdge.label, exact: true }).first();
    await relationshipButton.click();
    await page.locator('.berry-detail h2').filter({ hasText: exactEdge.label }).waitFor({ timeout: 60_000 });
    const relationshipURL = page.url();
    const sourceLink = page.locator('.berry-detail').locator(`[data-detail-trigger="source:${exactEdge.evidence_ids[0]}"]`).first();
    await sourceLink.click();
    await page.locator('.berry-detail [aria-label="Source Reader"]').waitFor({ timeout: 60_000 });
    assert.equal(selectors(page.url()).countries, applied.countries);
    assert.ok(selectors(page.url()).detail_path.includes(`relationship:${exactEdge.id}~source:${exactEdge.evidence_ids[0]}`));
    await page.locator('.berry-detail').getByRole('button', { name: 'Brief', exact: true }).click();
    await page.waitForURL(url => url.searchParams.get('detail_path')?.endsWith('@brief'));
    const sourceBriefURL = page.url();
    await page.reload({ waitUntil: 'domcontentloaded' });
    await page.locator('.berry-detail [aria-label="Source Reader"]').waitFor({ timeout: 60_000 });
    assert.equal(await page.locator('.berry-detail').getByRole('button', { name: 'Brief', exact: true }).getAttribute('aria-pressed'), 'true');
    assert.equal(page.url(), sourceBriefURL);
    await page.locator('.berry-detail').getByRole('button', { name: 'Article', exact: true }).click();
    await page.waitForURL(url => !url.searchParams.get('detail_path')?.endsWith('@brief'));
    pass('Nested Reader Brief section survives URL reload and restores canonical Article state');
    await capture('evidence', '04-evidence-reader.png');
    await page.locator('.berry-detail').getByRole('button', { name: /Back to previous detail/ }).click();
    assert.equal(page.url(), relationshipURL, 'Closing source restores the exact parent context URL');
    await page.goBack();
    await page.locator('.berry-detail [aria-label="Source Reader"]').waitFor();
    await page.goForward();
    await page.locator('.berry-detail h2').filter({ hasText: exactEdge.label }).waitFor();
    await page.reload({ waitUntil: 'domcontentloaded' });
    await page.locator('.berry-detail h2').filter({ hasText: exactEdge.label }).waitFor({ timeout: 60_000 });
    assert.equal(page.url(), relationshipURL);
    pass('Exact relationship/source ancestry survives close, Back, Forward and reload');
    await closeDetails(page);

    await page.goto(initialURL, { waitUntil: 'domcontentloaded' });
    await populated(page);
    for (const candidate of candidates) {
      const actor = (await actorButton(page, candidate.label)).locator('..');
      await actor.getByRole('button', { name: 'Pin for comparison', exact: true }).click();
    }
    await page.locator('.berry-country-selector > summary').click();
    await page.locator('.berry-country-options').getByRole('button', { name: 'All geographies', exact: true }).click();
    await page.locator('.berry-country-options').getByRole('checkbox', { name: 'China', exact: true }).check();
    await page.getByRole('button', { name: 'Apply scope', exact: true }).click();
    await page.getByRole('button', { name: 'Comparison', exact: true }).click();
    await page.locator('.berry-comparison-table').waitFor({ timeout: 90_000 });
    const directComparison = selectors(page.url());
    assert.equal(directComparison.cohort_companies, candidates.map(node => node.id).join(','));
    assert.equal(directComparison.countries, 'geography-china');
    await capture('comparison', '03-company-comparison.png');
    await page.getByRole('button', { name: 'Portfolio', exact: true }).click();
    await page.locator('[data-grid-edition="community"] .ag-root').waitFor({ timeout: 60_000 });
    pass('Actual AG Grid Community mounts with independent company/cultivar pin controls');
    await page.getByRole('button', { name: 'Comparison', exact: true }).click();
    const comparisonURL = page.url();
    await page.locator('.berry-developments .berry-loading').waitFor({ state: 'hidden', timeout: 90_000 });
    const relatedSource = page.locator('.berry-news-card').getByRole('button', { name: 'Read source →', exact: true }).first();
    if (await relatedSource.count()) {
      await relatedSource.click();
      await page.locator('.berry-detail [aria-label="Source Reader"]').waitFor({ timeout: 60_000 });
      assert.equal(selectors(page.url()).cohort_companies, directComparison.cohort_companies);
      assert.equal(selectors(page.url()).lens, 'comparison');
      await capture('evidence', '04-evidence-reader.png');
      await page.locator('.berry-detail').getByRole('button', { name: /Return to investigation|Back to previous detail/ }).first().click();
      await page.waitForURL(comparisonURL);
      pass('Relevant comparison development opens Reader and restores the same cohort/lens/scope');
    } else report.defects.push({ message: 'No current scoped comparison development was available for the populated comparison-to-Reader segment.', owner: 'W3 scenario/data review; do not broaden or fabricate' });

    if (approvedCopilotCommand) {
      await page.goto(initialURL, { waitUntil: 'domcontentloaded' }); await populated(page);
      await page.getByRole('button', { name: 'Ask Berry', exact: true }).click();
      const command = page.getByLabel('What would you like to inspect?', { exact: true });
      if (await command.count()) {
        await command.fill(approvedCopilotCommand);
        report.copilot = { status: 'IN_PROGRESS', command: approvedCopilotCommand };
        providerPhase = true;
        try {
          await page.getByRole('button', { name: 'Run command', exact: true }).click();
          await page.waitForFunction(expected => new URL(location.href).searchParams.get('lens') === 'comparison' && new URL(location.href).searchParams.get('cohort_companies') === expected, candidates.map(node => node.id).join(','), { timeout: 90_000 });
          await page.getByRole('button', { name: 'Run command', exact: true }).waitFor({ state: 'visible', timeout: 120_000 });
          await Promise.allSettled(usageReads);
          const back = page.getByRole('button', { name: 'Return to investigation', exact: true });
          if (await back.count()) await back.click();
          await page.locator('.berry-comparison-table').waitFor();
          assert.deepEqual(selectors(page.url()), directComparison, 'Copilot and equivalent direct controls must produce the same normalized context');
          assert.ok(approvedTurns.length > 0, 'A fixture-only action is not real provider acceptance');
          report.copilot = { status: 'REAL_TURN_COMPLETED', command: approvedCopilotCommand, provider_requests: approvedTurns.length,
            normalized_direct_context: directComparison, normalized_copilot_context: selectors(page.url()),
            usage_status: usageRecords.some(record => record.usage.length) ? 'CAPTURED' : 'NOT_EXPOSED' };
        } catch (error) {
          report.copilot = { status: 'FAILED', command: approvedCopilotCommand, provider_requests: approvedTurns.length };
          const cancel = page.getByRole('button', { name: 'Cancel', exact: true });
          if (await cancel.count()) await cancel.click().catch(() => {});
          throw error;
        } finally {
          report.command_wire_diagnostics = await page.evaluate(() => window.__berryCommandWire).catch(() => ({ unavailable: true }));
          providerPhase = false;
        }
      } else report.copilot = { status: 'BLOCKED', reason: 'The real configured runtime command form is unavailable.' };
    }

    const realCohort = selectors(page.url()).cohort_companies;
    await page.getByRole('button', { name: 'Sensory demo', exact: true }).click();
    await page.locator('[data-synthetic="true"] svg').waitFor({ timeout: 60_000 });
    assert.equal(selectors(page.url()).cohort_companies, realCohort);
    assert.ok(await page.locator('[data-synthetic="true"]').innerText().then(text => /synthetic|fictitious/i.test(text)));
    await page.waitForFunction(() => !document.querySelector('.berry-loading'));
    await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
    await page.waitForTimeout(150);
    await page.locator('[data-synthetic="true"]').evaluate(element => scrollTo({ top: scrollY + element.getBoundingClientRect().top - 60, behavior: 'instant' }));
    assert.ok(await page.locator('[data-synthetic="true"] svg').evaluate(element => element.getBoundingClientRect().bottom <= innerHeight), 'The sensory evidence screenshot must show the complete 1–9 axis');
    await capture('sensory', '05-synthetic-sensory.png');
    assert.ok(await page.locator('[data-synthetic="true"] svg').evaluate(element => element.getBoundingClientRect().bottom <= innerHeight), 'The captured sensory frame must retain the complete axis after layout settles');
    pass('Synthetic metric, fictitious specimens and visible 1-9 axis are separate from real cohorts');
    const demoChoices = page.locator('[data-synthetic="true"] input[type="checkbox"]');
    const demoCount = await demoChoices.count();
    assert.ok(demoCount >= 3, 'The fixture needs three available specimens for a subset round trip');
    await demoChoices.nth(0).uncheck(); await demoChoices.nth(2).uncheck();
    const chosenDemo = selectors(page.url()).demo_specimens;
    assert.equal(chosenDemo.split(',').filter(Boolean).length, demoCount - 2);
    await page.reload({ waitUntil: 'domcontentloaded' });
    await page.locator('[data-synthetic="true"] svg').waitFor({ timeout: 60_000 });
    assert.equal(selectors(page.url()).demo_specimens, chosenDemo);
    assert.equal(await page.locator('[data-synthetic="true"] input[type="checkbox"]:checked').count(), demoCount - 2);
    assert.equal(selectors(page.url()).cohort_companies, realCohort);
    pass('Explicit demo specimen cohort survives reload without changing company pins');

    await page.getByRole('button', { name: 'Connections', exact: true }).click();
    await populated(page);
    await page.setViewportSize({ width: 390, height: 844 });
    const keyboardTrigger = await actorButton(page, company.label);
    await keyboardTrigger.focus(); await page.keyboard.press('Enter');
    await page.locator('.berry-detail[aria-modal="true"]').waitFor({ timeout: 60_000 });
    await page.locator('.berry-detail h2').filter({ hasText: company.label }).waitFor({ timeout: 60_000 });
    await page.screenshot({ path: path.join(outputDir, '06-narrow-detail.png') });
    for (let index = 0; index < 16; index++) {
      await page.keyboard.press('Tab');
      assert.ok(await page.evaluate(() => document.querySelector('.berry-detail')?.contains(document.activeElement)), 'Narrow detail must contain keyboard focus');
    }
    await page.screenshot({ path: path.join(outputDir, '06b-narrow-keyboard-traversal.png') });
    await page.keyboard.press('Escape');
    await page.waitForFunction(() => !document.querySelector('.berry-detail'));
    let focusReturned = true;
    try {
      await page.waitForFunction(label => document.activeElement?.matches('button')
        && document.activeElement.querySelector('.berry-entity-name')?.textContent === label, company.label, { timeout: 4000 });
    } catch { focusReturned = false; }
    pass('Populated keyboard-only narrow detail contains focus and closes with Escape');
    if (focusReturned) pass('Narrow Escape restores the exact entity trigger focus');
    else {
      report.defects.push({ message: 'Narrow Escape closed detail without restoring focus to the entity trigger.', owner: 'W5 DetailHost focus/visibility restoration' });
      report.checks.push({ name: 'Narrow Escape trigger focus return', status: 'FAIL' });
      // Explicit harness recovery permits independent motion/status-failure checks;
      // it does not turn the failed product behavior into a pass.
      await keyboardTrigger.focus();
    }
    await page.emulateMedia({ reducedMotion: 'reduce' });
    assert.equal(await page.evaluate(() => matchMedia('(prefers-reduced-motion: reduce)').matches), true);
    await (await actorButton(page, company.label)).click();
    await page.locator('.berry-detail').waitFor();
    assert.ok(await page.locator('.berry-detail').evaluate(element => parseFloat(getComputedStyle(element).animationDuration) < .01), 'Reduced-motion panel must avoid significant animation');
    await closeDetails(page);
    pass('Touch-equivalent click and reduced-motion detail remain functional');
    const invalidComparison = new URL(initialURL);
    invalidComparison.searchParams.set('lens', 'comparison');
    invalidComparison.searchParams.set('cohort_companies', 'company-unavailable-rehearsal');
    invalidComparison.searchParams.set('focus', company.id);
    await page.goto(invalidComparison.href, { waitUntil: 'domcontentloaded' });
    await page.locator('#developments-heading').filter({ hasText: company.label }).waitFor({ timeout: 60_000 });
    assert.equal(selectors(page.url()).cohort_companies, 'company-unavailable-rehearsal');
    pass('An all-invalid comparison cohort retains explicit pins and falls back to valid in-scope focus');
    const scrollURL = new URL(initialURL);
    scrollURL.searchParams.set('lens', 'comparison');
    scrollURL.searchParams.set('countries', 'geography-china');
    scrollURL.searchParams.set('cohort_companies', candidates.map(node => node.id).join(','));
    await page.setViewportSize({ width: 1440, height: 1000 });
    await page.goto(scrollURL.href, { waitUntil: 'domcontentloaded' });
    await page.locator('.berry-comparison-table').waitFor({ timeout: 60_000 });
    await page.waitForFunction(() => !document.querySelector('.berry-loading'), null, { timeout: 90_000 });
    await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
    const scrollPoint = await page.evaluate(() => {
      const y = Math.min(240, document.documentElement.scrollHeight - innerHeight);
      scrollTo({ top: y, behavior: 'instant' }); return y;
    });
    assert.ok(scrollPoint > 0, 'The populated comparison must have a real nonzero viewport position');
    await page.waitForFunction(y => Math.abs(scrollY - y) <= 2, scrollPoint);
    await page.waitForTimeout(150);
    const scrollMemory = async () => {
      const raw = await page.evaluate(() => sessionStorage.getItem('berry:surface-scroll:v1') ?? '');
      assert.ok(!/company-|variety-|geography-|demo-specimen-|detail_path/.test(raw), 'Diagnostic scroll memory is UI-only');
      return raw ? JSON.parse(raw) : null;
    };
    report.scroll_memory_before_leave = await scrollMemory();
    report.scroll_stages = [];
    const scrollStage = async name => {
      try {
        await page.waitForFunction(y => Math.abs(scrollY - y) <= 2, scrollPoint, { timeout: 10_000 });
        report.scroll_stages.push({ name, status: 'PASS', expected_y: scrollPoint, actual_y: await page.evaluate(() => scrollY) });
      } catch {
        const actual = await page.evaluate(() => ({ y: scrollY, height: document.documentElement.scrollHeight, viewport: innerHeight }));
        report.scroll_stages.push({ name, status: 'FAIL', expected_y: scrollPoint, ...actual });
        report.defects.push({ message: `Viewport restore failed after ${name}: expected ${scrollPoint}, actual ${actual.y}.`, owner: 'W1 SurfaceScroll' });
      }
    };
    // Activate the real anchor without Playwright's preparatory autoscroll to
    // an offscreen header, which would overwrite the viewport under test.
    await page.getByRole('navigation', { name: 'Primary', exact: true }).getByRole('link', { name: 'Briefing', exact: true }).evaluate(link => link.click());
    await page.getByRole('heading', { name: 'Briefing', exact: true }).waitFor();
    report.scroll_memory_after_leave = await scrollMemory();
    await page.getByRole('navigation', { name: 'Primary', exact: true }).getByRole('link', { name: 'Landscape', exact: true }).click();
    await page.locator('.berry-comparison-table').waitFor({ timeout: 60_000 });
    await scrollStage('native surface return');
    await page.goBack(); await page.getByRole('heading', { name: 'Briefing', exact: true }).waitFor();
    await page.goForward(); await page.locator('.berry-comparison-table').waitFor();
    await scrollStage('Back/Forward');
    await page.reload({ waitUntil: 'domcontentloaded' });
    await page.locator('.berry-comparison-table').waitFor({ timeout: 60_000 });
    await scrollStage('reload');
    const layoutMemory = await page.evaluate(() => sessionStorage.getItem('berry:surface-scroll:v1') ?? '');
    assert.ok(layoutMemory.length > 0 && !/company-|variety-|geography-|demo-specimen-|detail_path/.test(layoutMemory), 'Scroll storage contains only layout coordinates and native surface/history keys');
    if (report.scroll_stages.every(row => row.status === 'PASS')) pass('Native surface return, Back/Forward and reload preserve a populated nonzero viewport', { y: scrollPoint });
    if (saveAndReopen) { await saveAndReopen({ page, context }); report.save_reopen = { status: 'PASS' }; }
    if (options.checkStatusFailure !== false) {
      await page.setViewportSize({ width: 1440, height: 1000 });
      await page.route('**/api/investigations/v1/copilot/status', route => route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ detail: 'Deliberately injected status-unavailable test' }) }), { times: 1 });
      await page.goto(initialURL, { waitUntil: 'domcontentloaded' });
      await populated(page);
      await (await actorButton(page, company.label)).click();
      await page.locator('.berry-detail h2').filter({ hasText: company.label }).waitFor({ timeout: 60_000 });
      await closeDetails(page);
      await page.getByRole('button', { name: 'Ask Berry', exact: true }).click();
      await page.locator('.berry-copilot').getByRole('status').filter({ hasText: /could not connect|unavailable/i }).waitFor();
      await page.screenshot({ path: path.join(outputDir, '07-injected-status-failure.png') });
      report.runtime_failure_injection = { status: 'PASS', injected: 'HTTP503 on Copilot status only', domain_records: 'Unmodified real local APIs', model_turns: 0 };
      pass('Explicit SDK-status failure preserves populated direct investigation and detail');
    }
    await page.getByRole('button', { name: 'Sign out', exact: true }).click();
    await page.waitForURL(url => url.pathname === '/login');
    assert.equal(await page.evaluate(() => sessionStorage.getItem('berry:surface-scroll:v1')), null);
    pass('Actual local logout clears private layout memory');
    assert.equal(unexpectedTurns.length, 0, 'Ordinary navigation, scope, grid and detail must not start provider turns');
    assert.equal(clientErrors.length, 0, 'The continuous flow must not emit uncaught client errors');
    report.v1_status = report.defects.length ? 'REWORK' : 'REVIEW_REQUIRED';
  } catch (error) {
    report.defects.push({ message: error instanceof Error ? error.message : String(error), owner: 'Existing implementation owner; assign after reproduction' });
    await page.screenshot({ path: path.join(outputDir, 'failure-state.png') }).catch(() => {});
  } finally {
    report.finished_at = new Date().toISOString();
    report.wire_diagnostics = await page.evaluate(() => window.__berryCommandWire).catch(() => ({ unavailable: true }));
    await context.close();
    videoPath = await page.video()?.path();
    report.continuous_recording = videoPath;
    await fs.writeFile(path.join(outputDir, 'acceptance.json'), JSON.stringify(report, null, 2));
    if (!options.browser) await browser.close();
  }
  return { outputDir, report };
}

if (process.argv[1] && pathToFileURL(path.resolve(process.argv[1])).href === import.meta.url) {
  if (!process.env.BERRY_REHEARSAL_BASE_URL) throw new Error('Set BERRY_REHEARSAL_BASE_URL to the explicitly started authenticated local server.');
  // The CLI accepts a memory-only session cookie; it never prints or saves it.
  const cookies = process.env.BERRY_REHEARSAL_SESSION_COOKIE ? [{ name: process.env.BERRY_REHEARSAL_COOKIE_NAME ?? 'bios_session', value: process.env.BERRY_REHEARSAL_SESSION_COOKIE, url: process.env.BERRY_REHEARSAL_BASE_URL }] : [];
  const result = await runRehearsal({ baseURL: process.env.BERRY_REHEARSAL_BASE_URL, cookies, revision: process.env.BERRY_REHEARSAL_REVISION });
  process.stdout.write(JSON.stringify({ outputDir: result.outputDir, v1_status: result.report.v1_status, defects: result.report.defects }) + '\n');
  if (result.report.defects.length) process.exitCode = 1;
}
