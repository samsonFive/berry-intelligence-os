/** Actual authenticated UI and private saved-selector/export APIs; no provider requests. */
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import { EMPTY_CONTEXT, parseInvestigation, serializeInvestigation } from '../src/contracts/investigation.ts';

export async function runWorkspacesRehearsal({ browser, baseURL, storageState, revision, outputDir }) {
  await fs.mkdir(outputDir, { recursive: true });
  const origin = new URL(baseURL).origin;
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, storageState, acceptDownloads: true, recordVideo: { dir: outputDir, size: { width: 1440, height: 1000 } } });
  const page = await context.newPage(), clientErrors = [], modelTurns = [], mutations = [];
  const report = { status: 'RUNNING', application_revision: revision, checks: [], defects: [], client_errors: clientErrors, model_turns: modelTurns, screenshots: {}, started_at: new Date().toISOString() };
  const pass = name => report.checks.push({ name, status: 'PASS' });
  const snapshot = () => parseInvestigation(new URL(page.url()).search).context;
  const selectorsOnly = value => ({ ...value, saved_view_id: '', saved_revision: '' });
  const shot = async (name, filename) => { const target = path.join(outputDir, filename); await page.screenshot({ path: target, fullPage: true }); report.screenshots[name] = target; };
  const nativeLink = name => page.getByRole('navigation', { name: 'Primary', exact: true }).getByRole('link', { name, exact: true });
  const ready = async () => {
    await page.getByRole('heading', { name: 'Keep an investigation. Share its evidence.', exact: true }).waitFor({ timeout: 90_000 });
    await page.waitForFunction(() => ![...document.querySelectorAll('.berry-workspaces-page .berry-loading')].some(node => node.getBoundingClientRect().height));
  };
  await context.route('**/*', async route => {
    const request = route.request(), url = new URL(request.url());
    if (url.origin !== origin) { await route.abort('blockedbyclient'); return; }
    if (request.method() === 'POST') {
      if (url.pathname === '/api/investigations/v1/copilot') {
        let method; try { method = request.postDataJSON()?.method; } catch { /* No payload is retained. */ }
        if (method === 'agent/run') { modelTurns.push({ method: 'agent/run' }); await route.abort('blockedbyclient'); return; }
      } else mutations.push(url.pathname);
    }
    await route.continue();
  });
  page.on('pageerror', error => clientErrors.push(error.message.slice(0, 500)));
  try {
    const selection = { ...EMPTY_CONTEXT, berry: 'berry-blueberry', countries: 'geography-chile,geography-china,geography-peru',
      focus: 'company-fall-creek-farm-and-nursery', cohort_companies: 'company-fall-creek-farm-and-nursery,company-costa-group-holdings',
      lens: 'comparison', detail_path: 'company:company-fall-creek-farm-and-nursery~relationship:rel-agrovision-partners-with-fall-creek~source:ev-blueberriesconsulting-agrovision-2024@brief',
      demo_specimens: 'demo-specimen-fern' };
    await page.goto(`${origin}/app/workspaces?${serializeInvestigation(selection)}`, { waitUntil: 'domcontentloaded' });
    await ready();
    // Resolve an actual catalog ID to exercise the separate cultivar cohort too.
    const variety = await page.evaluate(async () => {
      const response = await fetch('/api/investigations/v1/options?ctx_v=1&revision=0', { credentials: 'same-origin', cache: 'no-store' });
      const body = await response.json(); return body.data?.varieties?.[0]?.id ?? '';
    });
    assert.ok(variety, 'The real options API supplies a canonical cultivar identity');
    selection.cohort_varieties = variety;
    await page.goto(`${origin}/app/workspaces?${serializeInvestigation(selection)}`, { waitUntil: 'domcontentloaded' }); await ready();
    assert.deepEqual(selectorsOnly(snapshot()), selectorsOnly(selection));
    await shot('entry', '01-workspaces-entry.png');
    pass('Native Workspaces retains complete scope, both cohorts, nested Reader Brief and isolated demo selection');

    const name = `Rehearsal investigation ${Date.now()}`;
    await page.getByLabel('Investigation name', { exact: true }).fill(name);
    const firstSave = page.waitForResponse(response => new URL(response.url()).pathname === '/api/investigations/v1/saved' && response.request().method() === 'POST');
    await page.getByRole('button', { name: 'Save new investigation', exact: true }).click();
    const first = await firstSave; assert.equal(first.status(), 201);
    const firstRow = (await first.json()).data;
    await page.waitForFunction(id => new URLSearchParams(location.search).get('saved_view_id') === id, firstRow.id);
    assert.equal(firstRow.revision, 1); assert.equal(firstRow.filters.detail_path, selection.detail_path); assert.equal(firstRow.filters.demo_specimens, selection.demo_specimens);
    assert.equal(firstRow.filters.cohort_varieties, variety);
    await shot('saved', '02-saved-investigation.png');
    const savedCard = page.locator('.berry-saved-list li').filter({ has: page.getByRole('heading', { name, exact: true }) });
    await savedCard.getByRole('link', { name: 'Reopen investigation', exact: false }).click();
    await page.waitForURL(url => url.pathname === '/app/landscape');
    assert.deepEqual(selectorsOnly(snapshot()), selectorsOnly(selection));
    assert.equal(snapshot().saved_view_id, firstRow.id);
    await page.reload({ waitUntil: 'domcontentloaded' });
    await page.locator('.berry-comparison-table').waitFor({ timeout: 90_000 });
    assert.deepEqual(selectorsOnly(snapshot()), selectorsOnly(selection));
    pass('Actual selector-only save, returned native href reopen and reload preserve the investigation');

    await nativeLink('Workspaces').click(); await ready();
    await page.getByLabel('Update a saved investigation', { exact: true }).check();
    await page.getByRole('combobox', { name: /Saved investigation to update/ }).selectOption(firstRow.id);
    const updatedName = name + ' updated';
    await page.getByLabel('Investigation name', { exact: true }).fill(updatedName);
    const updateResponse = page.waitForResponse(response => new URL(response.url()).pathname === '/api/investigations/v1/saved' && response.request().method() === 'POST');
    await page.getByRole('button', { name: 'Update investigation', exact: true }).click();
    const updated = await updateResponse; assert.equal(updated.status(), 200);
    const updatedRow = (await updated.json()).data; assert.equal(updatedRow.revision, 2);
    await page.waitForFunction(() => new URLSearchParams(location.search).get('saved_revision') === '2');
    pass('Explicit update uses the opened saved revision and preserves the same saved row');

    // A real second writer advances the private saved row; no response mock is used.
    const concurrent = await page.evaluate(async payload => {
      const response = await fetch('/api/investigations/v1/saved', { method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
      return { status: response.status, body: await response.json() };
    }, { name: updatedName, context: selection, id: firstRow.id, revision: 2, save_as_new: false });
    assert.equal(concurrent.status, 200); assert.equal(concurrent.body.data.revision, 3);
    const conflictResponse = page.waitForResponse(response => new URL(response.url()).pathname === '/api/investigations/v1/saved' && response.request().method() === 'POST');
    await page.getByRole('button', { name: 'Update investigation', exact: true }).click();
    assert.equal((await conflictResponse).status(), 409);
    await page.getByRole('button', { name: 'Reload saved investigation', exact: true }).waitFor();
    assert.equal(await page.getByRole('button', { name: 'Update investigation', exact: true }).isDisabled(), true);
    await shot('conflict', '03-saved-revision-conflict.png');
    await page.getByRole('button', { name: 'Reload saved investigation', exact: true }).click();
    await page.waitForURL(url => url.pathname === '/app/landscape');
    assert.equal(snapshot().saved_revision, '3');
    assert.deepEqual(selectorsOnly(snapshot()), selectorsOnly(selection));
    pass('Real concurrent-save 409 freezes updates until explicit Reload saved investigation opens the latest snapshot');

    await nativeLink('Workspaces').click(); await ready();
    const previewResponse = page.waitForResponse(response => new URL(response.url()).pathname === '/api/investigations/v1/export/preview');
    await page.getByRole('button', { name: 'Preview complete output', exact: true }).click();
    const previewResult = await previewResponse; assert.equal(previewResult.status(), 200);
    const preview = await previewResult.json();
    await page.getByRole('heading', { name: 'Preview of the full output', exact: true }).waitFor();
    assert.equal(preview.include_demo, false); assert.equal(preview.synthetic_annex, null);
    assert.equal(preview.sections.length, 6); assert.ok(preview.sections.some(section => section.row_count > 0)); assert.ok(preview.sources.length > 0);
    const visiblePreview = page.getByLabel('Reviewed PDF contents', { exact: true });
    assert.match(await visiblePreview.textContent(), /Blueberry.*Chile.*China.*Peru/s);
    report.output_preview = { sections: preview.sections.map(({ id, row_count, source_ids }) => ({ id, row_count, source_count: source_ids.length })), source_count: preview.sources.length, content_hash: preview.content_hash };
    await shot('preview', '04-complete-output-preview.png');
    const downloadEvent = page.waitForEvent('download');
    await page.getByRole('button', { name: 'Download reviewed PDF', exact: true }).click();
    const download = await downloadEvent, pdfPath = path.join(outputDir, 'reviewed-investigation.pdf');
    await download.saveAs(pdfPath); assert.equal((await fs.readFile(pdfPath)).subarray(0, 5).toString(), '%PDF-'); report.pdf = pdfPath;
    pass('Actual UI previews all selected rows, source appendix and human scope before a hash-bound real PDF download');

    await page.getByLabel('Include synthetic sensory demo annex', { exact: false }).check();
    const annexResponse = page.waitForResponse(response => new URL(response.url()).pathname === '/api/investigations/v1/export/preview');
    await page.getByRole('button', { name: 'Preview complete output', exact: true }).click();
    const annexResult = await annexResponse; assert.equal(annexResult.status(), 200);
    const annex = await annexResult.json(); assert.equal(annex.include_demo, true); assert.equal(annex.synthetic_annex.specimen_count, 1);
    assert.deepEqual(annex.synthetic_annex.specimen_labels, ['Specimen Fern']);
    await page.getByText('Synthetic demonstration annex · 1 fictitious specimens', { exact: true }).waitFor();
    const annexDownload = page.waitForEvent('download');
    await page.getByRole('button', { name: 'Download reviewed PDF', exact: true }).click();
    const annexFile = await annexDownload, annexPath = path.join(outputDir, 'reviewed-investigation-synthetic-annex.pdf');
    await annexFile.saveAs(annexPath); assert.equal((await fs.readFile(annexPath)).subarray(0, 5).toString(), '%PDF-'); report.annex_pdf = annexPath;
    await shot('annex', '05-explicit-synthetic-annex.png');
    pass('Explicit synthetic annex resolves exactly the chosen fictitious cohort and stays absent from ordinary output');

    for (const label of ['Open authored Workspaces', 'Open reports', 'Open saved Brief Packs']) {
      const href = await page.getByRole('link', { name: label, exact: false }).getAttribute('href');
      const returned = new URL(new URL(href, origin).searchParams.get('return_to'), origin);
      assert.equal(returned.pathname, '/app/workspaces'); assert.deepEqual(selectorsOnly(parseInvestigation(returned.search).context), selectorsOnly(selection));
    }
    assert.ok(mutations.every(url => ['/api/investigations/v1/saved', '/api/investigations/v1/export/preview', '/api/investigations/v1/export/pdf'].includes(url)));
    assert.equal(modelTurns.length, 0); assert.equal(clientErrors.length, 0);
    pass('Legacy authored links retain exact native return context; no canonical writes, model turns or page errors');
    report.status = 'REVIEW_REQUIRED';
  } catch (error) {
    report.status = 'REWORK'; report.defects.push({ message: String(error.message).slice(0, 1500), owner: 'Workspaces implementation or explicit QA assertion' });
    await shot('failure', 'failure-state.png').catch(() => {});
  } finally {
    report.finished_at = new Date().toISOString();
    await context.close(); report.continuous_recording = await page.video()?.path();
    await fs.writeFile(path.join(outputDir, 'acceptance.json'), JSON.stringify(report, null, 2));
  }
  return { outputDir, report };
}
