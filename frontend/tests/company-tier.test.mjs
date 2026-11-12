import assert from 'node:assert/strict';
import test from 'node:test';
import { CompanyTierConflict, saveCompanyTier } from '../src/features/landscape/company-tier.ts';

const json = (body, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } });
test('tier save sends only the explicit existing mark and expected value to one authenticated same-origin endpoint', async () => {
  const original = globalThis.fetch, signal = new AbortController().signal; let captured;
  globalThis.fetch = async (url, options) => { captured = { url, options }; return json({ api_v: 1, request_id: 'req-a', data: { id: 'company-a', assigned_tier: 'tier2', assigned_tier_label: 'Tier 2', changed: true } }); };
  try {
    const result = await saveCompanyTier('company-a', 'tier2', 'tier1', signal);
    assert.equal(result.changed, true); assert.equal(captured.url, '/api/investigations/v1/companies/company-a/tier');
    assert.deepEqual(JSON.parse(captured.options.body), { tier: 'tier2', expected_tier: 'tier1' });
    assert.equal(captured.options.method, 'POST'); assert.equal(captured.options.credentials, 'same-origin');
    assert.equal(captured.options.cache, 'no-store'); assert.equal(captured.options.signal, signal);
  } finally { globalThis.fetch = original; }
});
test('conflicts expose the current tier and never retry or reinterpret the failed write as success', async () => {
  const original = globalThis.fetch; let calls = 0;
  globalThis.fetch = async () => { calls++; return json({ detail: { code: 'tier_conflict', id: 'company-a', assigned_tier: 'tier3', assigned_tier_label: 'Tier 3' } }, 409); };
  try {
    await assert.rejects(saveCompanyTier('company-a', 'tier2', 'tier1'), error => error instanceof CompanyTierConflict && error.current.assigned_tier === 'tier3');
    assert.equal(calls, 1);
  } finally { globalThis.fetch = original; }
});
test('invalid IDs and new legacy assignments fail before fetch while retaining an actual current legacy mark is allowed', async () => {
  const original = globalThis.fetch; let calls = 0;
  globalThis.fetch = async () => { calls++; return json({ api_v: 1, request_id: 'req-a', data: { id: 'company-a', assigned_tier: 'watch', assigned_tier_label: 'Legacy watch', changed: false } }); };
  try {
    for (const [id, tier, expected] of [['../company-a', 'tier1', 'untiered'], ['company-a', 'watch', 'tier1'], ['company-a', 'invented', 'tier1'], ['company-a', 'tier2', '']])
      await assert.rejects(saveCompanyTier(id, tier, expected));
    assert.equal(calls, 0); assert.equal((await saveCompanyTier('company-a', 'watch', 'watch')).changed, false);
    assert.equal(calls, 1);
  } finally { globalThis.fetch = original; }
});
test('expired sessions, wrong response identities and non-JSON failure stay explicit', async () => {
  const original = globalThis.fetch;
  try {
    for (const status of [401, 403]) {
      globalThis.fetch = async () => json({}, status);
      await assert.rejects(saveCompanyTier('company-a', 'tier2', 'tier1'), error => error.requiresSession);
    }
    globalThis.fetch = async () => json({ api_v: 1, request_id: 'req-a', data: { id: 'company-other', assigned_tier: 'tier2', assigned_tier_label: 'Tier 2', changed: true } });
    await assert.rejects(saveCompanyTier('company-a', 'tier2', 'tier1'), /incompatible/);
    globalThis.fetch = async () => new Response('private diagnostics', { status: 503 });
    await assert.rejects(saveCompanyTier('company-a', 'tier2', 'tier1'), error => error.status === 503 && !error.message.includes('private diagnostics'));
  } finally { globalThis.fetch = original; }
});
