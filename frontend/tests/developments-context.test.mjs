import assert from 'node:assert/strict';
import test from 'node:test';
import { EMPTY_CONTEXT, serializeInvestigation } from '../src/contracts/investigation.ts';
import { developmentsContext } from '../src/features/landscape/developments-context.ts';

test('development read context retains applied scope/date/roles and strips unrelated presentation state', () => {
  const original = { ...EMPTY_CONTEXT, berry: 'berry-blueberry', countries: 'geography-china', actor_roles: 'breeder',
    relationship_types: 'develops', news_from: '2026-01-01', news_to: '2026-11-11', focus: 'company-a',
    detail_path: 'company:company-a~source:ev-a@brief', q: 'analytical search', q_scope: 'catalog',
    saved_view_id: 'private-view', saved_revision: '4', demo_specimens: 'demo-specimen-amber' };
  const before = structuredClone(original);
  const result = developmentsContext(original, { 'company-a': {} });
  for (const field of ['berry', 'countries', 'actor_roles', 'news_from', 'news_to', 'focus']) assert.equal(result[field], original[field]);
  for (const field of ['detail_path', 'relationship_types', 'q', 'saved_view_id', 'saved_revision', 'demo_specimens']) assert.equal(result[field], '');
  assert.equal(result.q_scope, 'scope'); assert.deepEqual(original, before);
});

test('typed comparison keeps explicit invalid cohort and valid focal fallback for server resolution', () => {
  const original = { ...EMPTY_CONTEXT, lens: 'comparison', comparison_kind: 'variety', cohort_varieties: 'variety-unavailable',
    cohort_companies: 'company-other', focus: 'company-a' };
  const native = developmentsContext(original);
  const rail = developmentsContext(original, { 'company-a': {} });
  assert.equal(native.cohort_varieties, 'variety-unavailable'); assert.equal(native.focus, 'company-a');
  assert.equal(native.comparison_kind, 'variety'); assert.equal(native.lens, 'comparison');
  assert.equal(serializeInvestigation(native), serializeInvestigation(rail));
});

test('non-comparison lenses retain pins canonically while the news read ignores dormant cohorts', () => {
  const original = { ...EMPTY_CONTEXT, lens: 'sensory', cohort_companies: 'company-a', cohort_varieties: 'variety-a',
    demo_specimens: 'demo-specimen-amber', focus: 'company-outside' };
  const rail = developmentsContext(original, {}), native = developmentsContext(original);
  assert.equal(rail.focus, ''); assert.equal(native.focus, 'company-outside', 'The standalone server resolves unsupported focal scope itself');
  assert.equal(native.cohort_companies, ''); assert.equal(native.cohort_varieties, ''); assert.equal(native.demo_specimens, '');
  assert.equal(original.cohort_companies, 'company-a'); assert.equal(original.demo_specimens, 'demo-specimen-amber');
});
