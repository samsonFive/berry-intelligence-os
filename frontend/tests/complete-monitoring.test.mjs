import assert from 'node:assert/strict';
import test from 'node:test';
import { loadCompleteMonitoring } from '../src/features/landscape/complete-monitoring.ts';
import { EMPTY_CONTEXT } from '../src/contracts/investigation.ts';

const context = { ...EMPTY_CONTEXT, company_set: 'all' };
function page(offset, total = 186) {
  const end = Math.min(offset + 100, total);
  return { api_v: 1, request_id: `req-${offset}`, revision: 4, scope_key: 'same-scope', issues: [], data: {
    company_set: 'all', company_set_key: 'same-membership', basis: 'all_companies', total, universe_count: total, matching_count: total, offset, limit: 100,
    has_more: end < total, next_offset: end < total ? end : null,
    companies: Array.from({ length: end - offset }, (_, index) => ({ id: `company-${offset + index}`, type: 'company', assigned_tier: 'untiered' })),
    tier_groups: [{ tier: 'untiered', label: 'Untiered', count: total, matching_count: total }],
  } };
}
test('complete roster reads existing100-item pages sequentially and retains186 canonical companies and global tier counts', async () => {
  const calls = [], signal = new AbortController().signal;
  const result = await loadCompleteMonitoring(context, 4, signal, async (endpoint, actual, revision, received) => {
    calls.push(endpoint); assert.deepEqual(actual, context); assert.equal(revision, 4); assert.equal(received, signal);
    return page(Number(new URL(endpoint, 'https://fixture.invalid').searchParams.get('offset')));
  });
  assert.deepEqual(calls, ['/monitoring?offset=0&limit=100', '/monitoring?offset=100&limit=100', '/monitoring?offset=0&limit=100']);
  assert.equal(result.data.companies.length, 186); assert.equal(result.data.companies.at(-1).id, 'company-185');
  assert.equal(result.data.tier_groups[0].count, 186); assert.equal(result.data.has_more, false);
});
test('a valid empty selected universe is complete; changed counts, duplicate identities and broken page chains fail visibly', async () => {
  assert.deepEqual((await loadCompleteMonitoring(context, 4, undefined, async () => page(0, 0))).data.companies, []);
  for (const alter of [
    second => { second.data.universe_count++; }, second => { second.data.companies[0].id = 'company-0'; },
    second => { second.scope_key = 'different-scope'; }, second => { second.data.total++; },
    second => { second.data.companies.pop(); }, second => { second.revision = 3; },
  ]) {
    await assert.rejects(loadCompleteMonitoring(context, 4, undefined, async endpoint => {
      const offset = Number(new URL(endpoint, 'https://fixture.invalid').searchParams.get('offset')), result = page(offset);
      if (offset) alter(result); return result;
    }), /roster|identities/);
  }
  await assert.rejects(loadCompleteMonitoring(context, 4, undefined, async () => ({ ...page(0), data: { ...page(0).data, next_offset: 0 } })), /page sequence/);
});
test('abort between sequential reads prevents a partial result or late second request', async () => {
  const controller = new AbortController(); let calls = 0;
  await assert.rejects(loadCompleteMonitoring(context, 4, controller.signal, async () => { calls++; controller.abort(); return page(0); }), { name: 'AbortError' });
  assert.equal(calls, 1);
});
test('search-matched total governs completeness independently of the larger selected universe', async () => {
  const response = page(0, 12); response.data.universe_count = 186; response.data.tier_groups[0].count = 186;
  let calls = 0;
  const result = await loadCompleteMonitoring(context, 4, undefined, async () => { calls++; return response; });
  assert.equal(calls, 1); assert.equal(result.data.companies.length, 12); assert.equal(result.data.universe_count, 186);
});
test('membership drift and a changed first chunk at final confirmation reject instead of publishing a mixed roster', async () => {
  let calls = 0;
  await assert.rejects(loadCompleteMonitoring(context, 4, undefined, async endpoint => {
    const result = page(Number(new URL(endpoint, 'https://fixture.invalid').searchParams.get('offset')));
    if (++calls === 3) result.data.companies[0].assigned_tier = 'tier1';
    return result;
  }), /changed during loading/);
  await assert.rejects(loadCompleteMonitoring(context, 4, undefined, async endpoint => {
    const offset = Number(new URL(endpoint, 'https://fixture.invalid').searchParams.get('offset')), result = page(offset);
    if (offset) result.data.company_set_key = 'changed-membership'; return result;
  }), /changed while loading/);
});
