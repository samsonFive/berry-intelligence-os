import assert from 'node:assert/strict';
import test from 'node:test';
import { EMPTY_CONTEXT, serializeInvestigation } from '../src/contracts/investigation.ts';
import { landscapeNewsContext, monitoringContext } from '../src/features/landscape/company-set-context.ts';

const selected = { ...EMPTY_CONTEXT, berry: 'berry-blueberry', countries: 'geography-china', company_set: 'watched',
  actor_roles: 'breeder', relationship_types: 'develops', news_from: '2026-01-01', news_to: '2026-11-11',
  q: 'authored alias', q_scope: 'catalog', lens: 'comparison', comparison_kind: 'variety', focus: 'company-a',
  cohort_companies: 'company-a,company-b', cohort_varieties: 'variety-a', detail_path: 'source:ev-a@brief',
  saved_view_id: 'saved-a', saved_revision: '2', demo_specimens: 'demo-specimen-amber' };

test('the uncapped roster retains authored-name search and applied annotations independently of comparison pins', () => {
  const before = structuredClone(selected), result = monitoringContext(selected);
  for (const field of ['berry', 'countries', 'company_set', 'actor_roles', 'relationship_types', 'q', 'q_scope'])
    assert.equal(result[field], selected[field]);
  for (const field of ['focus', 'cohort_companies', 'cohort_varieties', 'detail_path', 'saved_view_id', 'saved_revision', 'demo_specimens', 'news_from', 'news_to'])
    assert.equal(result[field], '');
  assert.equal(result.lens, 'connections');
  assert.deepEqual(selected, before, 'Reading a roster never changes canonical pins, dates or Reader state');
});

test('Landscape News preserves company-set/source scope and dates while ignoring catalog search and dormant selections', () => {
  const result = landscapeNewsContext(selected);
  for (const field of ['berry', 'countries', 'company_set', 'actor_roles', 'news_from', 'news_to'])
    assert.equal(result[field], selected[field]);
  for (const field of ['focus', 'cohort_companies', 'cohort_varieties', 'detail_path', 'q', 'relationship_types'])
    assert.equal(result[field], '');
  assert.equal(result.q_scope, 'scope'); assert.equal(result.lens, 'news');
  assert.equal(landscapeNewsContext({ ...selected, company_set: 'all' }).company_set, 'all');
});

test('Reader navigation and changes to five-item comparison cohorts do not create roster or News cache identities', () => {
  const other = { ...selected, focus: 'company-c', cohort_companies: 'company-c,company-d,company-e,company-f,company-g',
    cohort_varieties: 'variety-z', comparison_kind: 'company', detail_path: 'company:company-c~source:ev-b', saved_revision: '9' };
  for (const project of [monitoringContext, landscapeNewsContext]) {
    assert.equal(serializeInvestigation(project(selected)), serializeInvestigation(project(other)));
    assert.notEqual(serializeInvestigation(project(selected)), serializeInvestigation(project({ ...selected, company_set: 'all' })));
  }
});
