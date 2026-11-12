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
  assert.deepEqual(rosterGenetics(model, 'company-monitored'), { programs: [], varieties: [], edges: [], qualifierGroups: [] });
});

test('repeated exact qualifiers compact once while retaining every unique attributed path and source edge', () => {
  const actor = { ...node('company-a', 'company'), label: 'Company A' };
  const partner = { ...node('company-partner', 'company'), label: 'Named Partner' };
  const program = { ...node('program-a', 'breeding_program'), label: 'Program A' };
  const cultivar = { ...node('variety-a', 'variety'), label: 'Cultivar A' };
  const companyPath = edge('rel-company', { object_id: cultivar.id });
  const programPath = edge('rel-program', { subject_id: program.id, object_id: cultivar.id, evidence_ids: ['ev-b'] });
  const partnerPath = edge('rel-partner', { object_id: partner.id, evidence_ids: ['ev-c'] });
  const model = { nodes: Object.fromEntries([actor, partner, program, cultivar].map(row => [row.id, row])),
    portfolios: [portrait(actor, [program], [cultivar], [companyPath, partnerPath], [programPath])],
    market_rows: [portrait(actor, [program], [cultivar], [companyPath], [programPath])] };
  const before = structuredClone(model);
  const result = rosterGenetics(model, actor.id);
  assert.equal(result.qualifierGroups.length, 1);
  const group = result.qualifierGroups[0];
  assert.equal(group.key, JSON.stringify(['Recorded role', 'disputed', 'Disputed / review required', 'Authored limitation']));
  assert.deepEqual(group.edgeIds, ['rel-company', 'rel-partner', 'rel-program']);
  assert.deepEqual(group.paths.map(path => [path.edgeId, path.subjectId, path.objectId]),
    [['rel-company', actor.id, cultivar.id], ['rel-partner', actor.id, partner.id], ['rel-program', program.id, cultivar.id]]);
  assert.deepEqual(group.paths.map(path => [path.subjectLabel, path.subjectType, path.objectLabel, path.objectType]),
    [['Company A', 'company', 'Cultivar A', 'variety'], ['Company A', 'company', 'Named Partner', 'company'],
      ['Program A', 'breeding_program', 'Cultivar A', 'variety']]);
  assert.deepEqual(result.edges.flatMap(row => row.evidence_ids), ['ev-a', 'ev-c', 'ev-b']);
  assert.deepEqual(model, before, 'grouping does not mutate or replace the authored portraits');
});

test('qualifier grouping uses the exact four-field tuple without merging distinct status or authored text', () => {
  const actor = node('company-a', 'company');
  const authored = [edge('rel-1'), edge('rel-2', { role: 'Recorded role ' }),
    edge('rel-3', { status: 'legacy' }), edge('rel-4', { status_label: 'Different review label' }),
    edge('rel-5', { caveat: 'Authored limitation ' }), edge('rel-6', { status: 'active', caveat: '' }),
    edge('rel-7', { status: 'active', caveat: 'Still material' }), edge('rel-geo', { company_geography: true })];
  const model = { portfolios: [portrait(actor, [], [], authored)], market_rows: [] };
  const result = rosterGenetics(model, actor.id);
  assert.deepEqual(result.qualifierGroups.map(group => group.edgeIds),
    [['rel-1'], ['rel-2'], ['rel-3'], ['rel-4'], ['rel-5'], ['rel-7']]);
  assert.equal(new Set(result.qualifierGroups.map(group => group.key)).size, 6);
  assert.equal(result.edges.some(row => row.id === 'rel-6'), true, 'unqualified active paths remain available in full records');
  assert.equal(result.edges.some(row => row.id === 'rel-geo'), false, 'geography is not recast as genetics');
});

test('group identities survive display-name edits and missing endpoints remain exact rather than inferred', () => {
  const actor = node('company-a', 'company'), program = node('program-a', 'breeding_program');
  const authored = edge('rel-a', { subject_id: program.id, object_id: 'variety-unavailable' });
  const model = { portfolios: [portrait(actor, [program], [], [], [authored])], market_rows: [] };
  const before = rosterGenetics(model, actor.id).qualifierGroups[0];
  const renamed = { ...model, nodes: { [program.id]: { ...program, label: 'Renamed Program' } } };
  const after = rosterGenetics(renamed, actor.id).qualifierGroups[0];
  assert.equal(after.key, before.key);
  assert.equal(after.paths[0].subjectLabel, 'Renamed Program');
  assert.equal(after.paths[0].subjectId, program.id);
  assert.equal(after.paths[0].objectId, 'variety-unavailable');
  assert.equal(after.paths[0].objectLabel, 'variety-unavailable');
  assert.equal(after.paths[0].objectType, undefined, 'an unavailable endpoint never becomes a guessed cultivar/company');
});
