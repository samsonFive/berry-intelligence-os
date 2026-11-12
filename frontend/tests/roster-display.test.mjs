import assert from 'node:assert/strict';
import test from 'node:test';
import { rosterDisplayPage } from '../src/features/landscape/roster-display.ts';
test('25/50/100/All display exactly actual company rows and every identity remains accessible', () => {
  const companies = Array.from({ length: 186 }, (_, id) => ({ id: 'company-' + id }));
  for (const size of [25, 50, 100, 'all']) {
    const first = rosterDisplayPage(companies, size, 0), pages = Array.from({ length: first.count }, (_, i) => rosterDisplayPage(companies, size, i));
    assert.equal(first.rows.length, size === 'all' ? 186 : size);
    assert.deepEqual(pages.flatMap(page => page.rows), companies);
    assert.equal(pages.at(-1).end, 186);
  }
  assert.equal(rosterDisplayPage(companies, 50, 99).index, 3);
  assert.deepEqual(rosterDisplayPage([], 'all', 0).rows, []);
});
