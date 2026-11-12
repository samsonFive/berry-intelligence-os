import assert from 'node:assert/strict';
import test from 'node:test';
import { portfolioData } from '../src/features/grids/portfolio-data.ts';
import { companyPage } from '../src/features/grids/company-pages.ts';

test('multi-berry company portraits share one column while all cultivar edges and export values remain', () => {
  const actor = { id: 'company-a', label: 'Company A', type: 'company' };
  const blueberry = { id: 'variety-blue', label: 'Blue cultivar', type: 'variety' };
  const raspberry = { id: 'variety-red', label: 'Red cultivar', type: 'variety' };
  const edge = (id, cultivar) => ({ id, subject_id: actor.id, object_id: cultivar.id,
    role: 'Recorded seller', label: 'Recorded seller', evidence_ids: [`ev-${id}`] });
  const blue = edge('rel-blue', blueberry), red = edge('rel-red', raspberry), otherBlue = edge('rel-blue-other', blueberry);
  const model = { nodes: Object.fromEntries([actor, blueberry, raspberry].map(node => [node.id, node])), portfolios: [
    { actor, portfolio_edges: [blue] }, { actor: { ...actor }, portfolio_edges: [red, otherBlue] },
    { actor: { ...actor }, portfolio_edges: [blue] },
  ] };
  const before = structuredClone(model);
  const { companies, rows } = portfolioData(model);
  assert.deepEqual(companies.map(company => company.id), [actor.id]);
  assert.equal(companyPage(companies).total, 1, 'distinct-ID paging guard still accepts the canonical column set');
  assert.deepEqual(rows.map(row => row.id), [blueberry.id, raspberry.id]);
  assert.deepEqual(rows[0].byCompany[actor.id].map(item => item.id), ['rel-blue', 'rel-blue-other']);
  assert.deepEqual(rows[1].byCompany[actor.id].map(item => item.id), ['rel-red']);
  assert.deepEqual(rows.flatMap(row => row.byCompany[actor.id]).flatMap(item => item.evidence_ids),
    ['ev-rel-blue', 'ev-rel-blue-other', 'ev-rel-red']);
  assert.equal(rows[0].byCompany[actor.id].map(item => item.label).join('; '), 'Recorded seller; Recorded seller',
    'equal role text on different exact edges is retained for the existing filter/CSV value getter');
  assert.deepEqual(model, before, 'identity dedup never replaces or trims original portraits');
});
