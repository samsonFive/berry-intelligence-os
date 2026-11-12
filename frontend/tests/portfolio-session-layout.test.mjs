import assert from 'node:assert/strict';
import test from 'node:test';
import { PortfolioSessionLayouts } from '../src/features/grids/portfolio-session-layout.ts';
import { companyPageViewKey } from '../src/features/grids/company-pages.ts';

const ids = count => ['cultivar.identity', 'cultivar.comparison-pin', ...Array.from({ length: count }, (_, i) => `company.company-${i}.recorded-role`)];
const snapshot = keys => ({ columns: keys.map(colId => ({ colId, width: 260, hide: false })), filterModel: {}, quickFilter: '' });

test('fifty/All window layouts preserve full order, resize, hiding, sort and filters in RAM by exact membership', async () => {
  const memory = new PortfolioSessionLayouts(), columns = ids(50);
  const key = await companyPageViewKey(Array.from({ length: 50 }, (_, i) => `company-${i}`), true);
  const value = snapshot(columns);
  value.columns[10].width = 710; value.columns[20].hide = true; value.columns[30].sort = 'desc';
  value.columns.splice(5, 0, value.columns.splice(25, 1)[0]);
  value.filterModel[columns[10]] = { filterType: 'text', type: 'contains', filter: 'Recorded breeder' };
  value.quickFilter = 'Eterna';
  assert.equal(memory.save(key, columns, value, memory.epoch), true);
  assert.deepEqual(memory.load(key, [...columns].reverse(), memory.epoch), value);
  const restored = memory.load(key, columns, memory.epoch); restored.columns[0].width = 999;
  assert.deepEqual(memory.load(key, columns, memory.epoch), value, 'a consumer cannot mutate the retained RAM layout');
  assert.equal(memory.load(key, [...columns, 'company.other.recorded-role'], memory.epoch), null);
  assert.throws(() => memory.save(key, columns, { ...value, columns: value.columns.slice(1) }, memory.epoch), /exact/);
});

test('session end erases large-window preferences and rejects stale callbacks; no disk or account transport is involved', () => {
  const memory = new PortfolioSessionLayouts(), columns = ids(186), old = memory.epoch;
  memory.save('berry-pg-v2-session', columns, snapshot(columns), old);
  assert.equal(memory.size, 1); memory.clear(); assert.equal(memory.size, 0);
  assert.equal(memory.load('berry-pg-v2-session', columns, old), null);
  assert.equal(memory.save('berry-pg-v2-session', columns, snapshot(columns), old), false);
  assert.equal(memory.save('berry-pg-v2-session', columns, snapshot(columns), memory.epoch), true);
});
