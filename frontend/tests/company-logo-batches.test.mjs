import assert from 'node:assert/strict';
import test from 'node:test';
import { companyLogoBatch } from '../src/features/brand-media/company-logo-batches.ts';
test('every one of186 companies has a stable bounded curated-media batch without a first20 cutoff', () => {
  const ids = Array.from({ length: 186 }, (_, i) => `company-${String(i).padStart(3, '0')}`), before = [...ids], batches = new Map();
  for (const id of ids) { const batch = companyLogoBatch(id, ids); assert.ok(batch.length <= 20 && batch.includes(id)); batches.set(batch.join(','), batch); }
  assert.equal(batches.size, 10); assert.deepEqual([...batches.values()].flat(), ids); assert.deepEqual(ids, before);
  assert.deepEqual(companyLogoBatch(ids[100], [...ids].reverse()), companyLogoBatch(ids[100], ids));
  assert.deepEqual(companyLogoBatch('company-alone'), ['company-alone']);
});
