import assert from 'node:assert/strict';
import test from 'node:test';
import { readFile } from 'node:fs/promises';
import { BRAND_DEMO_IDS, brandFlavorContext, parseSensoryFixture } from '../src/features/demo/sensory-model.ts';
import { EMPTY_CONTEXT, normalizeContext, parseInvestigation, serializeInvestigation } from '../src/contracts/investigation.ts';
const fixture = { api_v: 1, ...JSON.parse(await readFile(new URL('../../app/demo_data/flavor/synthetic-overall-liking-v1.json', import.meta.url), 'utf8')) };

test('six consumer-label demo profiles preserve typed company and brand references with five explicit scales', () => {
  const parsed = parseSensoryFixture(fixture);
  assert.deepEqual(parsed.brand_profiles.map(row => row.id), BRAND_DEMO_IDS);
  assert.equal(parsed.brand_profiles.find(row => row.id === 'demo-brand-driscolls').canonical_entity.type, 'company');
  assert.equal(parsed.brand_profiles.find(row => row.id === 'demo-brand-fruitist').canonical_entity.type, 'brand');
  assert.equal(parsed.metrics.filter(row => row.scale_type === 'intensity').length, 4);
  assert.equal(parsed.metrics.find(row => row.id === 'overall_liking').scale_type, 'hedonic');
});
test('a company cannot be relabeled as a canonical brand, and ratings cannot escape the scale', () => {
  const cast = structuredClone(fixture); cast.brand_profiles[0].canonical_entity.type = 'brand';
  assert.throws(() => parseSensoryFixture(cast), /unsupported/);
  for (const value of [0, 10, NaN, true]) {
    const changed = structuredClone(fixture); changed.brand_profiles[0].values.sweetness = value;
    assert.throws(() => parseSensoryFixture(changed), /unsupported/);
  }
  const unlabeled = structuredClone(fixture); unlabeled.brand_profiles[0].label = 'Real result';
  assert.throws(() => parseSensoryFixture(unlabeled), /unsupported/);
});
test('opening flavor explicitly selects the six brands and keeps investigation focus, pins and scope', () => {
  const prior = { ...EMPTY_CONTEXT, countries: 'geography-china', company_set: 'watched', focus: 'company-costa-group-holdings',
    cohort_companies: 'company-driscolls,company-costa-group-holdings', cohort_varieties: 'variety-zara' };
  const next = brandFlavorContext(prior);
  assert.equal(next.lens, 'sensory'); assert.equal(next.demo_specimens, BRAND_DEMO_IDS.join(','));
  assert.deepEqual({ ...next, lens: prior.lens, demo_specimens: prior.demo_specimens }, prior);
  assert.deepEqual(parseInvestigation(serializeInvestigation(next)).context, next);
  assert.equal(normalizeContext(next).issues.length, 0);
});
test('brand view preserves explicit legacy and unavailable saved demo IDs for honest recovery', () => {
  for (const selected of ['demo-specimen-fern', 'demo-brand-future,demo-brand-fruitist']) {
    const context = brandFlavorContext({ ...EMPTY_CONTEXT, demo_specimens: selected });
    assert.equal(context.demo_specimens, selected);
    assert.equal(normalizeContext(context).issues.length, 0);
  }
  assert.ok(normalizeContext({ ...EMPTY_CONTEXT, demo_specimens: 'company-driscolls,demo-brand-' }).issues.length);
});
