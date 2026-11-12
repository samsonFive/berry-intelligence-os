import assert from 'node:assert/strict';
import test from 'node:test';
import { createColumnCatalog, decodeGridLayout, defaultGridLayout, encodeGridLayout } from '../src/features/grids/layout-codec.ts';
import { captureGridLayout, isUserLayoutEvent, restoredColumnState } from '../src/features/grids/grid-state.ts';

const specs = [
  { colId: 'cultivar.identity', defaultWidth: 220, lockedVisible: true },
  { colId: 'cultivar.comparison-pin', defaultWidth: 75, minWidth: 65, maxWidth: 90, lockedVisible: true },
  { colId: 'company.company-a.recorded-role', defaultWidth: 260 },
  { colId: 'company.company-b.recorded-role', defaultWidth: 260 },
];

test('AG state captures order, sort priority and cloned filters without row/cohort state', async () => {
  const catalog = await createColumnCatalog(specs);
  const filter = { [specs[2].colId]: { filterType: 'text', type: 'contains', filter: 'Breeder' } };
  const state = [
    { colId: specs[0].colId, width: 210, hide: true },
    { colId: specs[1].colId, width: 75 },
    { colId: specs[3].colId, width: 410, hide: true, sort: 'asc', sortIndex: 1 },
    { colId: specs[2].colId, width: 310, sort: 'desc', sortIndex: 0 },
  ];
  const snapshot = captureGridLayout(state, filter, 'SEKOYA', catalog);
  assert.deepEqual(snapshot.columns.map(column => column.colId), state.map(column => column.colId));
  assert.equal(snapshot.columns[0].hide, false);
  assert.equal(snapshot.columns[2].hide, true);
  assert.deepEqual(snapshot.sort, [{ colId: specs[2].colId, sort: 'desc' }, { colId: specs[3].colId, sort: 'asc' }]);
  filter[specs[2].colId].filter = 'Changed after capture';
  assert.equal(snapshot.filterModel[specs[2].colId].filter, 'Breeder');
  assert.equal(snapshot.quickFilter, 'SEKOYA');
  assert.deepEqual(Object.keys(snapshot).sort(), ['columns', 'filterModel', 'quickFilter', 'sort']);
});

test('restoration fixes identity/pin positions, clears stale sort and preserves dynamic widths', async () => {
  const catalog = await createColumnCatalog(specs);
  const saved = defaultGridLayout(catalog);
  saved.columns.reverse(); saved.columns[0].width = 380; saved.columns[0].hide = true;
  saved.sort = [{ colId: specs[2].colId, sort: 'desc' }];
  const decoded = decodeGridLayout({ ...encodeGridLayout(saved, catalog), revision: 1 }, catalog);
  const state = restoredColumnState(decoded.snapshot, catalog);
  assert.deepEqual(state.slice(0, 2).map(column => [column.colId, column.pinned, column.hide]), specs.slice(0, 2).map(column => [column.colId, 'left', false]));
  assert.equal(state.find(column => column.colId === specs[3].colId).width, 380);
  assert.equal(state.find(column => column.colId === specs[3].colId).sort, null);
  assert.equal(state.find(column => column.colId === specs[2].colId).sortIndex, 0);
  assert.equal(state.find(column => column.colId === specs[2].colId).pinned, null);
});

test('only completed user gestures trigger autosave; restore/data/viewport events do not', () => {
  for (const source of ['api', 'gridOptionsChanged', 'rowDataUpdated', 'viewportSizeFeature', 'gridInitializing', undefined]) {
    for (const kind of ['move', 'resize', 'visible', 'sort', 'filter']) assert.equal(isUserLayoutEvent(kind, source), false);
  }
  assert.equal(isUserLayoutEvent('move', 'uiColumnMoved', false), false);
  assert.equal(isUserLayoutEvent('resize', 'uiColumnResized', false), false);
  assert.equal(isUserLayoutEvent('move', 'uiColumnMoved'), true);
  assert.equal(isUserLayoutEvent('resize', 'uiColumnResized'), true);
  assert.equal(isUserLayoutEvent('sort', 'uiColumnSorted'), true);
  assert.equal(isUserLayoutEvent('filter', 'columnFilter'), true);
  assert.equal(isUserLayoutEvent('visible', 'columnMenu'), true);
});

test('an incomplete grid cannot overwrite the complete saved column layout', async () => {
  const catalog = await createColumnCatalog(specs);
  assert.throws(() => captureGridLayout([{ colId: specs[0].colId, width: 220 }], {}, '', catalog), /complete grid columns/);
});
