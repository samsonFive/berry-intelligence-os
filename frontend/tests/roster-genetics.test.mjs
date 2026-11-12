import assert from 'node:assert/strict';
import test from 'node:test';
import { rosterGenetics } from '../src/features/landscape/roster-genetics.ts';

const node = (id, type) => ({ id, type, label: id, evidence_ids: [] });
const edge = (id, overrides = {}) => ({ id, subject_id: 'company-a', object_id: 'program-a', role: 'Recorded role',
  status: 'disputed', status_label: 'Disputed / review required', caveat: 'Authored limitation', evidence_ids: ['ev-a'],
  company_geography: false, genetic_geography: false, ...overrides });
const portrait = (actor, programs = [], varieties = [], edges = [], portfolio_edges = []) => ({ actor, programs, varieties, edges, portfolio_edges, markets: [] });

test('roster genetics joins exact canonical actors and retains authored paths and qualifications without transferring roles', () => {
  const actor = node('company-a', 'company'), program = node('program-a', 'breeding_program'), variety = node('variety-a', 'variety');
  const limited = edge('rel-a');
  const model = { portfolios: [portrait(actor, [program], [variety], [limited]),
    portrait(node('company-b', 'company'), [program], [node('variety-unrelated', 'variety')], [edge('rel-unrelated')])],
    market_rows: [portrait(actor, [program], [variety], [limited], [edge('rel-geo', { company_geography: true })])] };
  const before = structuredClone(model);
  const result = rosterGenetics(model, actor.id);
  assert.deepEqual(result.programs.map(row => row.id), ['program-a']);
  assert.deepEqual(result.varieties.map(row => row.id), ['variety-a']);
  assert.deepEqual(result.edges, [limited]);
  assert.equal(result.edges[0].caveat, 'Authored limitation');
  assert.deepEqual(result.edges[0].evidence_ids, ['ev-a']);
  assert.deepEqual(model, before);
});

test('a monitored company without an authored portrait gets no inferred genetics from other companies', () => {
  const model = { portfolios: [portrait(node('company-other', 'company'), [node('program-a', 'breeding_program')])], market_rows: [] };
  assert.deepEqual(rosterGenetics(model, 'company-monitored'), { programs: [], varieties: [], edges: [] });
});
