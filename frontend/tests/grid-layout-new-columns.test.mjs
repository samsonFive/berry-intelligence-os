import assert from 'node:assert/strict';
import test from 'node:test';
import { AccountGridLayouts } from '../src/features/grids/account-layout.ts';
import { createColumnCatalog, decodeGridLayout, defaultGridLayout, encodeGridLayout } from '../src/features/grids/layout-codec.ts';

const oldColumns = [
  { colId: 'company.identity', defaultWidth: 220, lockedVisible: true },
  { colId: 'company.genetics', defaultWidth: 360 },
  { colId: 'company.roles', defaultWidth: 185 },
  { colId: 'company.geography', defaultWidth: 240 },
  { colId: 'company.collection', defaultWidth: 180, defaultHidden: true },
];
const addedColumns = [
  { colId: 'company.tier', defaultWidth: 105, restoreAfter: 'company.identity' },
  { colId: 'company.compare', defaultWidth: 80, restoreAfter: 'company.identity' },
];
const currentColumns = [oldColumns[0], ...addedColumns, ...oldColumns.slice(1)];
const ids = snapshot => snapshot.columns.map(column => column.colId);
const withoutPlacement = columns => columns.map(({ restoreAfter, ...column }) => column);

function savedLayout(catalog) {
  const snapshot = defaultGridLayout(catalog);
  const order = ['company.identity', 'company.geography', 'company.collection', 'company.roles', 'company.genetics'];
  snapshot.columns.sort((left, right) => order.indexOf(left.colId) - order.indexOf(right.colId));
  snapshot.columns.forEach((column, index) => { column.width = 240 + index * 37; column.hide = column.colId === 'company.roles'; });
  snapshot.sort = [{ colId: 'company.geography', sort: 'desc' }];
  snapshot.filterModel = { 'company.genetics': { filterType: 'text', type: 'contains', filter: 'licensed' } };
  snapshot.quickFilter = 'authored company';
  snapshot.view = 'cards';
  return { ...encodeGridLayout(snapshot, catalog), revision: 7 };
}

test('old five-column preferences gain two visible columns beside identity without moving old columns or writing on restore', async () => {
  const previous = await createColumnCatalog(oldColumns), current = await createColumnCatalog(currentColumns);
  const wire = savedLayout(previous), original = JSON.stringify(wire), before = decodeGridLayout(wire, previous).snapshot;
  const calls = [];
  const owner = new AccountGridLayouts({ viewKey: 'berry-company-roster-v1', catalog: current, fetch: async (url, options) => {
    calls.push({ url, method: options.method });
    assert.equal(options.method, 'GET', 'Restoring new columns must not persist a migration automatically');
    return new Response(JSON.stringify(wire), { status: 200, headers: { 'content-type': 'application/json' } });
  } });
  const loaded = await owner.load();
  assert.deepEqual(ids(loaded.snapshot), ['company.identity', 'company.tier', 'company.compare', ...ids(before).slice(1)]);
  assert.deepEqual(loaded.snapshot.columns.filter(column => !addedColumns.some(added => added.colId === column.colId)), before.columns);
  assert.deepEqual(loaded.snapshot.columns.slice(1, 3), [
    { colId: 'company.tier', width: 105, hide: false }, { colId: 'company.compare', width: 80, hide: false },
  ]);
  assert.deepEqual(loaded.snapshot.filterModel, before.filterModel);
  assert.deepEqual(loaded.snapshot.sort, before.sort);
  assert.equal(loaded.snapshot.quickFilter, before.quickFilter);
  assert.equal(loaded.snapshot.view, before.view);
  assert.equal(loaded.revision, 7);
  assert.equal(JSON.stringify(wire), original);
  assert.deepEqual(calls, [{ url: '/api/ui/sheets/berry-company-roster-v1', method: 'GET' }]);
  owner.dispose();
});

test('already saved Tier and Compare retain explicit order, widths, visibility and filters', async () => {
  const catalog = await createColumnCatalog(currentColumns), snapshot = defaultGridLayout(catalog);
  const order = ['company.identity', 'company.geography', 'company.compare', 'company.collection', 'company.genetics', 'company.tier', 'company.roles'];
  snapshot.columns.sort((left, right) => order.indexOf(left.colId) - order.indexOf(right.colId));
  snapshot.columns.find(column => column.colId === 'company.tier').width = 157;
  snapshot.columns.find(column => column.colId === 'company.compare').width = 96;
  snapshot.columns.find(column => column.colId === 'company.tier').hide = true;
  snapshot.columns.find(column => column.colId === 'company.compare').hide = true;
  snapshot.filterModel['company.tier'] = { filterType: 'text', type: 'equals', filter: 'Tier 2' };
  snapshot.sort = [{ colId: 'company.compare', sort: 'asc' }];
  snapshot.quickFilter = 'display choice'; snapshot.view = 'cards';
  const saved = { ...encodeGridLayout(snapshot, catalog), revision: 3 };
  assert.deepEqual(decodeGridLayout(saved, catalog).snapshot, snapshot);
});

test('a reference anywhere in the original saved wire counts as an existing column', async () => {
  const previous = await createColumnCatalog(oldColumns), catalog = await createColumnCatalog(currentColumns);
  const plain = await createColumnCatalog(withoutPlacement(currentColumns)), tier = catalog.byId.get('company.tier').key;
  for (const channel of ['order', 'width', 'hidden', 'sort', 'filter']) {
    const wire = savedLayout(previous);
    if (channel === 'order') wire.order.splice(3, 0, tier);
    if (channel === 'width') wire.widths[tier] = 143;
    if (channel === 'hidden') wire.hidden.push(tier);
    if (channel === 'sort') wire.filters.sort = JSON.stringify([[tier, 'asc']]);
    if (channel === 'filter') wire.filters[tier] = JSON.stringify({ filterType: 'text', type: 'contains', filter: 'Tier' });
    const original = JSON.stringify(wire), expected = decodeGridLayout(wire, plain).snapshot;
    const loaded = decodeGridLayout(wire, catalog).snapshot;
    assert.deepEqual(loaded.columns.filter(column => column.colId !== 'company.compare'), expected.columns.filter(column => column.colId !== 'company.compare'), channel);
    assert.equal(ids(loaded)[1], 'company.compare', channel);
    assert.deepEqual(loaded.filterModel, expected.filterModel, channel);
    assert.deepEqual(loaded.sort, expected.sort, channel);
    assert.equal(JSON.stringify(wire), original, channel);
  }
});

test('normal user save after migration round trips choices and retains opaque absent-column preferences', async () => {
  const oldWithAbsent = await createColumnCatalog([...oldColumns, { colId: 'company.temporarily-absent', defaultWidth: 321 }]);
  const current = await createColumnCatalog(currentColumns), wire = savedLayout(oldWithAbsent);
  const absent = oldWithAbsent.byId.get('company.temporarily-absent').key;
  wire.hidden.push(absent);
  wire.filters[absent] = JSON.stringify({ filterType: 'text', type: 'equals', filter: 'retained' });
  const original = JSON.stringify(wire), loaded = decodeGridLayout(wire, current);
  assert.equal(loaded.retainedUnknownColumns, 1);
  assert.equal(JSON.stringify(wire), original);
  const tier = loaded.snapshot.columns.find(column => column.colId === 'company.tier');
  tier.width = 119; tier.hide = true;
  const compare = loaded.snapshot.columns.find(column => column.colId === 'company.compare');
  loaded.snapshot.columns = [...loaded.snapshot.columns.filter(column => column !== compare), compare];
  const encoded = encodeGridLayout(loaded.snapshot, current, wire);
  assert.equal(encoded.revision, wire.revision);
  assert.equal(encoded.widths[absent], wire.widths[absent]);
  assert.ok(encoded.hidden.includes(absent));
  assert.equal(encoded.filters[absent], wire.filters[absent]);
  assert.deepEqual(decodeGridLayout({ ...encoded, revision: 8 }, current).snapshot, loaded.snapshot);
  const plain = await createColumnCatalog(withoutPlacement(currentColumns));
  for (const column of current.columns) assert.equal(column.key, plain.byId.get(column.colId).key);
});
