import assert from 'node:assert/strict';
import test from 'node:test';
import { mergeConnectionPortraits } from '../src/features/landscape/connection-portraits.ts';

const node = (id, type, evidence_ids = []) => ({ id, type, label: id, identity_status: 'active', evidence_ids });
const edge = (id, subject_id, object_id, role = 'Develops') => ({ id, subject_id, object_id, role, status: 'active', evidence_ids: ['ev-' + id] });
const portrait = (actor, fields = {}) => ({ actor, programs: [], varieties: [], edges: [], portfolio_edges: [], markets: [], ...fields });

test('All berries joins every exact-actor portrait while keeping genetics and geographic paths distinct', () => {
  const a = node('company-a', 'company', ['ev-blueberry']), b = node('company-a', 'company', ['ev-raspberry']);
  const program = node('program-a', 'breeding_program'), blueberry = node('variety-blue', 'variety'), raspberry = node('variety-rasp', 'variety');
  const blue = edge('rel-blue', program.id, blueberry.id), rasp = edge('rel-rasp', program.id, raspberry.id);
  const china = edge('rel-china', a.id, 'geography-china', 'Planned market entry');
  const validation = edge('rel-validation', a.id, 'geography-china', 'Variety validation programme');
  const peru = edge('rel-peru', a.id, 'geography-peru', 'Location only');
  const model = { market_rows: [portrait(a, { programs: [program], varieties: [blueberry], edges: [blue], markets: [{ country: 'China', edges: [china] }] })],
    portfolios: [portrait(b, { programs: [{ ...program, evidence_ids: ['ev-program'] }], varieties: [raspberry], portfolio_edges: [rasp],
      markets: [{ country: 'China', edges: [china, validation] }, { country: 'Peru', edges: [peru] }] }), portrait(node('company-other', 'company'))] };
  const before = structuredClone(model), rows = mergeConnectionPortraits(model), row = rows[0];
  assert.deepEqual(rows.map(item => item.actor.id), ['company-a', 'company-other']);
  assert.deepEqual(row.actor.evidence_ids, ['ev-blueberry', 'ev-raspberry']);
  assert.deepEqual(row.programs.map(item => item.id), [program.id]);
  assert.deepEqual(row.programs[0].evidence_ids, ['ev-program']);
  assert.deepEqual(row.varieties.map(item => item.id), [blueberry.id, raspberry.id]);
  assert.deepEqual(row.edges, [blue]); assert.deepEqual(row.portfolio_edges, [rasp]);
  assert.deepEqual(row.markets, [{ country: 'China', edges: [china, validation] }, { country: 'Peru', edges: [peru] }]);
  assert.equal(row.portfolio_edges[0].subject_id, program.id, 'a program role remains program-attributed');
  assert.deepEqual(rows[1].edges, []); assert.deepEqual(model, before);
});

test('only exact edge IDs deduplicate; same endpoints with distinct roles or qualifications remain accessible', () => {
  const actor = node('company-a', 'company'), one = edge('rel-one', actor.id, 'variety-a');
  const two = { ...edge('rel-two', actor.id, 'variety-a', 'Licenses'), status: 'historical', caveat: 'Expired recorded licence' };
  const model = { market_rows: [portrait(actor, { edges: [one, two] })], portfolios: [portrait(actor, { edges: [one], portfolio_edges: [two] })] };
  const row = mergeConnectionPortraits(model)[0];
  assert.deepEqual(row.edges.map(item => item.id), ['rel-one', 'rel-two']);
  assert.deepEqual(row.portfolio_edges, [two]);
  assert.equal(row.edges[1].caveat, 'Expired recorded licence');
  assert.deepEqual(mergeConnectionPortraits({ market_rows: [], portfolios: [] }), []);
});
