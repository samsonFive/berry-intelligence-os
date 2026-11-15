import assert from 'node:assert/strict';
import test from 'node:test';
import { AccountGridLayouts } from '../src/features/grids/account-layout.ts';
import { companyPageViewKey } from '../src/features/grids/company-pages.ts';
import { createColumnCatalog, defaultGridLayout, encodeGridLayout, decodeGridLayout, gridLayoutLimits, MAX_PORTFOLIO_LAYOUT_COLUMNS } from '../src/features/grids/layout-codec.ts';

const columns = count => [
  { colId: 'cultivar.identity', defaultWidth: 220, lockedVisible: true },
  { colId: 'cultivar.comparison-pin', defaultWidth: 75, lockedVisible: true },
  ...Array.from({ length: count }, (_, i) => ({ colId: `company.company-${i}.recorded-role`, defaultWidth: 260 })),
];
const empty = () => ({ revision: 0, widths: {}, order: [], hidden: [], filters: {} });
const json = (body, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } });
const catalogFor = async count => {
  const specs = columns(count), key = await companyPageViewKey(specs.slice(2).map(column => column.colId.split('.')[1]), true);
  return { key, catalog: await createColumnCatalog(specs, undefined, key) };
};

test('wide account storage is limited to exact existing Portfolio namespaces', async () => {
  assert.deepEqual(gridLayoutLimits('berry-portfolio-v1'), { columns: 512, bytes: 128 * 1024 });
  const { key, catalog } = await catalogFor(50);
  assert.deepEqual(catalog.limits, gridLayoutLimits(key));
  for (const name of ['berry-pg-v2-short', 'berry-pg-v2-' + 'g'.repeat(64), 'berry-portfolio-v1-other', 'sheet-test']) {
    assert.deepEqual(gridLayoutLimits(name), { columns: 40, bytes: 20_000 });
    await assert.rejects(createColumnCatalog(columns(50), undefined, name), /forty/);
  }
  await assert.rejects(createColumnCatalog(columns(511), undefined, key), /512/);
});

test('50-company and full 186-company account layouts survive a new controller and retain absent-column preferences', async () => {
  for (const count of [50, 186]) {
    const { key, catalog } = await catalogFor(count);
    let wire = empty(); const methods = [];
    const request = async (url, options) => {
      assert.equal(url, '/api/ui/sheets/' + key); assert.equal(options.credentials, 'same-origin');
      methods.push(options.method);
      if (options.method === 'POST') {
        const payload = JSON.parse(options.body); assert.equal(payload.revision, wire.revision);
        wire = { ...payload, revision: wire.revision + 1 };
      }
      return json(wire);
    };
    const first = new AccountGridLayouts({ viewKey: key, catalog, fetch: request, sessionEvents: new EventTarget() });
    assert.equal((await first.load()).status, 'default');
    assert.deepEqual(methods, ['GET'], 'restoration never creates a write');
    const expected = defaultGridLayout(catalog);
    expected.columns = [...expected.columns.slice(0, 2), ...expected.columns.slice(2).reverse()];
    expected.columns[2].width = 450; expected.columns[3].hide = true;
    expected.sort = [{ colId: expected.columns[2].colId, sort: 'desc' }];
    expected.filterModel[expected.columns[3].colId] = { filterType: 'text', type: 'contains', filter: 'licensee' };
    expected.quickFilter = 'Peru';
    await first.save(expected); first.dispose();
    const second = new AccountGridLayouts({ viewKey: key, catalog, fetch: request, sessionEvents: new EventTarget() });
    assert.deepEqual((await second.load()).snapshot, expected);
    assert.deepEqual(methods, ['GET', 'POST', 'GET']); second.dispose();
    const subset = await createColumnCatalog(catalog.columns.slice(0, 20), undefined, key);
    const partial = decodeGridLayout(wire, subset);
    assert.equal(partial.retainedUnknownColumns, count + 2 - 20);
    const updated = encodeGridLayout(partial.snapshot, subset, wire);
    const restored = decodeGridLayout(updated, catalog).snapshot;
    assert.equal(restored.columns.find(column => column.colId === expected.columns[2].colId).width, 450);
    assert.equal(restored.columns.find(column => column.colId === expected.columns[3].colId).hide, true);
    assert.deepEqual(restored.sort, expected.sort); assert.deepEqual(restored.filterModel, expected.filterModel);
  }
});

test('full bounded Portfolio payloads and responses above the old20KB limit round trip without dropping columns', async () => {
  const { key, catalog } = await catalogFor(MAX_PORTFOLIO_LAYOUT_COLUMNS - 2);
  const expected = defaultGridLayout(catalog);
  expected.columns.slice(2).forEach(column => { column.hide = true; column.width = 1200; });
  const wire = { ...encodeGridLayout(expected, catalog), revision: 3 };
  const bytes = new TextEncoder().encode(JSON.stringify(wire)).byteLength;
  assert.ok(bytes > 20_000 && bytes <= catalog.limits.bytes);
  const controller = new AccountGridLayouts({ viewKey: key, catalog, fetch: async () => json(wire), sessionEvents: new EventTarget() });
  assert.deepEqual((await controller.load()).snapshot, expected); controller.dispose();
  const tooMany = { ...wire, order: [...wire.order, 'c-' + 'f'.repeat(32)] };
  assert.throws(() => decodeGridLayout(tooMany, catalog), /invalid/);
});

test('wide-layout concurrent edits freeze queued writes until explicit reload', async () => {
  const { key, catalog } = await catalogFor(186); let wire = empty(), posts = 0;
  const request = async (_, options) => {
    if (options.method === 'POST') {
      posts++; const payload = JSON.parse(options.body);
      if (payload.revision !== wire.revision) return json({ detail: 'Changed in another tab.' }, 409);
      wire = { ...payload, revision: wire.revision + 1 };
    }
    return json(wire);
  };
  const controller = new AccountGridLayouts({ viewKey: key, catalog, fetch: request, sessionEvents: new EventTarget() });
  await controller.load();
  const anotherTab = defaultGridLayout(catalog); anotherTab.columns[5].width = 500;
  wire = { ...encodeGridLayout(anotherTab, catalog), revision: 1 };
  const local = defaultGridLayout(catalog); local.columns[4].hide = true;
  const attempted = await Promise.allSettled([controller.save(local), controller.save(local)]);
  assert.ok(attempted.every(result => result.status === 'rejected' && result.reason.kind === 'conflict'));
  assert.equal(posts, 1); assert.deepEqual(decodeGridLayout(wire, catalog).snapshot, anotherTab);
  assert.deepEqual((await controller.load()).snapshot, anotherTab);
  assert.equal(controller.getState().conflict, false);
  await controller.save(local); assert.equal(wire.revision, 2); controller.dispose();
});
