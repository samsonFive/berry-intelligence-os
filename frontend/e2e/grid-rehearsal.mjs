/** Mounted account-layout QA. Real domain/layout APIs; only the explicit 409 is injected. */
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import { createHash } from 'node:crypto';

const endpoint = '/api/ui/sheets/berry-portfolio-v1';
const key = id => 'c-' + createHash('sha256').update(`berry-grid-column:v1\0${id}`).digest('hex').slice(0, 32);
const fixed = ['cultivar.identity', 'cultivar.comparison-pin'];
const timeout = 45_000;

export async function runGridRehearsal({ browser, baseURL, storageState, outputDir, revision }) {
  assert.ok(['127.0.0.1', 'localhost'].includes(new URL(baseURL).hostname));
  await fs.mkdir(outputDir, { recursive: true });
  const context = await browser.newContext({ storageState, viewport: { width: 1440, height: 1000 }, recordVideo: { dir: outputDir, size: { width: 1440, height: 1000 } } });
  const page = await context.newPage();
  const report = { status: 'REWORK', revision, checks: [], failures: [], layout_posts: [], provider_turns: [], page_errors: [], api_timings: [], screenshots: {} };
  const starts = new Map();
  page.on('request', request => { if (new URL(request.url()).origin === new URL(baseURL).origin && new URL(request.url()).pathname.startsWith('/api/')) starts.set(request, Date.now()); });
  let step = 'initial load';
  page.on('pageerror', error => report.page_errors.push(error.message));
  await context.route('**/api/investigations/v1/copilot**', async route => {
    const request = route.request();
    if (request.method() === 'POST' && !['info', 'agent/connect', 'agent/stop'].includes(request.postDataJSON()?.method)) {
      report.provider_turns.push({ method: request.method(), path: new URL(request.url()).pathname }); await route.abort('blockedbyclient'); return;
    }
    await route.continue();
  });
  page.on('response', response => {
    const started = starts.get(response.request());
    if (started !== undefined) { report.api_timings.push({ endpoint: new URL(response.url()).pathname, status: response.status(), duration_ms: Date.now() - started }); starts.delete(response.request()); }
    if (new URL(response.url()).pathname === endpoint && response.request().method() === 'POST') report.layout_posts.push({ status: response.status() });
  });
  const status = page.locator('.berry-grid-layout-status');
  const ready = async () => {
    await page.locator('[data-grid-edition="community"] .ag-root').waitFor({ timeout });
    await page.waitForFunction(() => {
      const status = document.querySelector('.berry-grid-layout-status');
      return status && ['ready', 'saved', 'local', 'error', 'conflict'].includes(status.getAttribute('data-phase'));
    }, null, { timeout });
    assert.ok(['ready', 'saved'].includes(await status.getAttribute('data-phase')), await status.innerText());
  };
  const savedChange = async action => {
    const response = page.waitForResponse(item => new URL(item.url()).pathname === endpoint && item.request().method() === 'POST', { timeout });
    await action();
    const result = await response;
    assert.equal(result.status(), 200, 'A user display change must receive an actual account save acknowledgement');
    const wire = await result.json();
    await page.waitForFunction(() => document.querySelector('.berry-grid-layout-status')?.getAttribute('data-phase') === 'saved', null, { timeout });
    return wire;
  };
  const readLayout = () => page.evaluate(async url => {
    const response = await fetch(url, { credentials: 'same-origin', cache: 'no-store' });
    if (!response.ok) throw new Error(`Layout read HTTP ${response.status}`);
    return response.json();
  }, endpoint);
  const header = id => page.locator(`.ag-header-cell[col-id="${id}"]`).first();
  const snapshot = async (label, name) => { const dest = path.join(outputDir, name); await page.screenshot({ path: dest }); report.screenshots[label] = dest; };
  const fixedColumns = async () => {
    const columns = await page.locator('.ag-header-row .ag-grid-pinned-left-cells .ag-header-cell').evaluateAll(cells => cells.map(cell => cell.getAttribute('col-id')));
    assert.deepEqual(columns.slice(0, 2), fixed, 'Cultivar identity must be first and both identity/pin remain frozen left');
    for (const id of fixed) assert.equal(await header(id).isVisible(), true);
  };
  try {
    const target = new URL('/app/landscape', baseURL);
    target.search = new URLSearchParams({ ctx_v: '1', berry: 'berry-blueberry', countries: 'geography-chile,geography-china,geography-peru', geo_basis: 'company_connections', lens: 'portfolio', comparison_kind: 'company', q_scope: 'scope' }).toString();
    await page.goto(target.href, { waitUntil: 'domcontentloaded' });
    await ready(); await fixedColumns();
    const initialURL = page.url();
    const initialSelectors = Object.fromEntries(new URL(initialURL).searchParams);
    const unchanged = () => assert.deepEqual(Object.fromEntries(new URL(page.url()).searchParams), initialSelectors, 'Display preferences must not mutate focus, cohorts, scope or query selectors');
    const model = await page.evaluate(async query => (await (await fetch('/api/investigations/v1/landscape?' + query, { credentials: 'same-origin' })).json()).data, new URL(page.url()).searchParams.toString() + '&revision=0');
    const actors = model.portfolios.map(row => row.actor);
    assert.ok(actors.length >= 2, 'Two actual company columns are required');
    const a = `company.${actors[0].id}.recorded-role`, b = `company.${actors[1].id}.recorded-role`;
    const postsAtLoad = report.layout_posts.length;
    await page.waitForTimeout(800);
    assert.equal(report.layout_posts.length, postsAtLoad, 'Initial restoration must not autosave');
    report.checks.push({ name: 'Actual account load without restoration POST; fixed leading identity/pin', status: 'PASS' });

    step = 'visible company columns';
    await page.locator('.berry-grid-columns > summary').click();
    for (const actor of actors.slice(0, 2)) {
      const checkbox = page.getByRole('checkbox', { name: `Show ${actor.label} column`, exact: true });
      if (!await checkbox.isChecked()) await savedChange(() => checkbox.check());
    }
    await page.keyboard.press('Escape');
    step = 'drag resize';
    const beforeWidth = (await header(a).boundingBox()).width;
    let wire = await savedChange(async () => {
      const handle = header(a).locator('.ag-header-cell-resize'); const box = await handle.boundingBox();
      assert.ok(box); await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2); await page.mouse.down();
      await page.mouse.move(box.x + box.width / 2 + 48, box.y + box.height / 2, { steps: 12 }); await page.mouse.up();
    });
    assert.ok(wire.widths[key(a)] >= beforeWidth + 25);
    const resizedWidth = wire.widths[key(a)]; unchanged();

    step = 'drag company order';
    const firstBox = await header(a).boundingBox(), secondBox = await header(b).boundingBox();
    const reversed = wire.order.indexOf(key(b)) < wire.order.indexOf(key(a));
    const drag = reversed ? header(a) : header(b), destination = reversed ? secondBox : firstBox;
    wire = await savedChange(async () => {
      const box = await drag.locator('.ag-header-cell-label').boundingBox(); assert.ok(box && destination);
      await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2); await page.mouse.down();
      await page.mouse.move(destination.x + 10, destination.y + destination.height / 2, { steps: 18 }); await page.waitForTimeout(300); await page.mouse.up();
    });
    assert.equal(wire.order.indexOf(key(b)) < wire.order.indexOf(key(a)), !reversed);
    unchanged();

    step = 'sort and column filter';
    for (let attempt = 0; attempt < 3 && await header(fixed[0]).getAttribute('aria-sort') !== 'ascending'; attempt++) await savedChange(() => header(fixed[0]).locator('.ag-header-cell-label').click());
    await header(fixed[0]).hover();
    await header(fixed[0]).locator('.ag-header-cell-filter-button').click();
    const columnFilter = page.locator('.ag-filter-body input[type="text"]').first();
    await columnFilter.waitFor({ timeout });
    if (await columnFilter.inputValue() === 'SEKOYA') await savedChange(() => columnFilter.fill('Cargo'));
    await savedChange(() => columnFilter.fill('SEKOYA'));
    await page.keyboard.press('Escape');
    step = 'quick filter';
    if (await page.getByRole('searchbox', { name: 'Filter loaded rows', exact: true }).inputValue() === 'Crunch') await savedChange(() => page.getByRole('searchbox', { name: 'Filter loaded rows', exact: true }).fill('Nova'));
    wire = await savedChange(() => page.getByRole('searchbox', { name: 'Filter loaded rows', exact: true }).fill('Crunch'));
    assert.equal(wire.filters.quick, 'Crunch');
    assert.ok(wire.filters[key(fixed[0])]?.includes('SEKOYA'));
    assert.ok(JSON.parse(wire.filters.sort).some(row => row[0] === key(fixed[0]) && row[1] === 'asc'));
    step = 'hide company';
    await page.locator('.berry-grid-columns > summary').click();
    wire = await savedChange(() => page.getByRole('checkbox', { name: `Show ${actors[0].label} column`, exact: true }).uncheck());
    await page.keyboard.press('Escape');
    assert.ok(wire.hidden.includes(key(a))); assert.ok(fixed.every(id => !wire.hidden.includes(key(id))));
    await fixedColumns(); unchanged();
    report.checks.push({ name: 'Actual drag resize/order, Community hide, column filter, quick filter and sort receive server acknowledgements', status: 'PASS', confirmed_revision: wire.revision });
    await snapshot('saved', '01-grid-saved.png');

    step = 'lens return and reload';
    const expected = await readLayout(); const beforeRestorePosts = report.layout_posts.length;
    await page.getByRole('button', { name: 'Connections', exact: true }).click();
    await page.locator('.berry-relationship-row').first().waitFor({ timeout });
    await page.getByRole('button', { name: 'Portfolio', exact: true }).click(); await ready();
    assert.equal(page.url(), initialURL);
    assert.equal(await page.getByRole('searchbox', { name: 'Filter loaded rows', exact: true }).inputValue(), 'Crunch');
    await page.reload({ waitUntil: 'domcontentloaded' }); await ready(); await fixedColumns();
    assert.deepEqual(await readLayout(), expected);
    assert.equal(report.layout_posts.length, beforeRestorePosts, 'Returning/reloading must apply preferences without rewriting them');
    assert.equal(await header(fixed[0]).getAttribute('aria-sort'), 'ascending');
    assert.equal((await readLayout()).widths[key(a)], resizedWidth);
    unchanged();
    report.checks.push({ name: 'Width/order/hide/filter/sort/quick restore across lens return and reload without selector changes or new POST', status: 'PASS' });

    step = 'injected layout conflict';
    await page.route('**' + endpoint, async route => {
      if (route.request().method() === 'POST') { await route.fulfill({ status: 409, contentType: 'application/json', body: JSON.stringify({ detail: 'Layout changed in another tab.' }) }); }
      else await route.continue();
    }, { times: 1 });
    const conflictResponse = page.waitForResponse(response => new URL(response.url()).pathname === endpoint && response.request().method() === 'POST');
    await page.getByRole('searchbox', { name: 'Filter loaded rows', exact: true }).fill('Nova');
    assert.equal((await conflictResponse).status(), 409);
    await page.waitForFunction(() => document.querySelector('.berry-grid-layout-status')?.getAttribute('data-phase') === 'conflict');
    const conflictPosts = report.layout_posts.length;
    await page.getByRole('searchbox', { name: 'Filter loaded rows', exact: true }).fill('Fiesta');
    await page.waitForTimeout(1100);
    assert.equal(report.layout_posts.length, conflictPosts);
    assert.equal(await page.getByRole('searchbox', { name: 'Filter loaded rows', exact: true }).inputValue(), 'Fiesta');
    unchanged(); await snapshot('conflict', '02-grid-conflict.png');
    await page.getByRole('button', { name: 'Reload saved layout', exact: true }).click(); await ready();
    assert.equal(await page.getByRole('searchbox', { name: 'Filter loaded rows', exact: true }).inputValue(), 'Crunch');
    assert.equal(report.layout_posts.length, conflictPosts, 'Explicit reload is a read, not an automatic overwrite');
    wire = await savedChange(() => page.getByRole('searchbox', { name: 'Filter loaded rows', exact: true }).fill('Nova'));
    assert.equal(wire.filters.quick, 'Nova'); unchanged();
    report.checks.push({ name: '409 keeps local display and blocks subsequent writes until explicit reload; saving resumes only afterward', status: 'PASS', injected: 'layout POST only' });

    step = 'narrow fixed identity and keyboard controls';
    await page.setViewportSize({ width: 390, height: 844 }); await fixedColumns();
    await page.locator('.berry-grid-columns > summary').focus(); await page.keyboard.press('Enter');
    assert.equal(await page.locator('.berry-grid-columns').getAttribute('open'), '');
    assert.equal(await page.getByRole('checkbox', { name: 'Show Cultivar column', exact: true }).isDisabled(), true);
    assert.equal(await page.getByRole('checkbox', { name: 'Show Comparison pin column', exact: true }).isDisabled(), true);
    await page.keyboard.press('Escape');
    assert.equal(await page.locator('.berry-grid-columns > summary').evaluate(element => element === document.activeElement), true);
    await snapshot('narrow', '03-grid-narrow.png');
    report.checks.push({ name: 'Narrow grid retains frozen leading identity/pin; keyboard Columns Escape restores summary focus', status: 'PASS' });
    assert.equal(report.provider_turns.length, 0); assert.equal(report.page_errors.length, 0);
    report.status = 'REVIEW_REQUIRED';
  } catch (error) {
    report.failures.push({ step, message: error.message });
    await snapshot('failure', 'failure-state.png').catch(() => {});
  } finally {
    await context.close(); report.video = await page.video()?.path();
    await fs.writeFile(path.join(outputDir, 'grid-acceptance.json'), JSON.stringify(report, null, 2));
  }
  return { outputDir, report };
}
