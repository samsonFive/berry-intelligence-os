import assert from 'node:assert/strict';
import test from 'node:test';
import { catalogSearchResults } from './catalog-results.ts';

test('a unique authored exact match survives the tool result bound while other matches remain available', () => {
  const rows = Array.from({ length: 15 }, (_, index) => ({ id: `company-${index}`, label: `A Orchard ${index}`, match_basis: 'substring', matched_label: `A Orchard ${index}` }));
  rows.push({ id: 'company-exact', label: 'Zeta Farm', match_basis: 'exact_alias', matched_label: 'Orchard', status: 'active' });
  const result = catalogSearchResults(rows, 'company', 'Orchard');
  assert.equal(result.results[0].id, 'company-exact');
  assert.equal(result.results[1].id, 'company-0');
  assert.equal(result.results[0].matched_label, 'Orchard');
  assert.equal(result.exact_match_count, 1); assert.equal(result.returned_count, 12);
  assert.equal(result.available_match_count, 16); assert.equal(result.results_limited, true);
});

test('multiple exact aliases are reported as ambiguous without selecting or inventing a winner', () => {
  const rows = ['company-a', 'company-b'].map(id => ({ id, label: id, match_basis: 'exact_alias', matched_label: 'Shared' }));
  const result = catalogSearchResults(rows, 'company', 'Shared');
  assert.equal(result.exact_match_count, 2);
  assert.deepEqual(result.results.map(row => row.id), ['company-a', 'company-b']);
  assert.equal('selected_id' in result, false); assert.equal(result.results_limited, false);
});

test('geography aliases and authored substring matches survive literal-label filtering', () => {
  const rows = [
    { id: 'geography-one', label: 'Country One', match_basis: 'exact_alias', matched_label: 'CN' },
    { id: 'geography-two', label: 'Country Two', match_basis: 'substring', matched_label: 'CN region' },
    { id: 'geography-unmatched', label: 'Elsewhere', match_basis: 'unfiltered' },
  ];
  const result = catalogSearchResults(rows, 'geography', 'CN');
  assert.deepEqual(result.results.map(row => row.id), ['geography-one', 'geography-two']);
  assert.equal(result.exact_match_count, 1);
});

test('empty-query results and status metadata retain their existing order', () => {
  const result = catalogSearchResults([{ id: 'company-a', label: 'Alpha', status: 'candidate', match_basis: 'unfiltered' }, { id: 'company-b', label: 'Beta', status: 'active', match_basis: 'unfiltered' }], 'company', '');
  assert.deepEqual(result.results.map(row => row.id), ['company-a', 'company-b']);
  assert.equal(result.results[0].status, 'candidate'); assert.equal(result.exact_match_count, 0);
});
