import assert from 'node:assert/strict';
import test from 'node:test';
import { EMPTY_CONTEXT, normalizeContext, parseInvestigation, serializeInvestigation } from '../src/contracts/investigation.ts';
import { appliedScopeLabels, resetInvestigationContext, scopeHasChanges } from '../src/components/scope-state.ts';
import { initialInvestigation, reduceInvestigation } from '../src/state/reducer.ts';
import { clearSheetFilters, sheetFilterSummary, SheetFilterReset } from '../src/features/grids/filter-summary.ts';
import { defaultSheetColumnState } from '../src/features/grids/sheet-layout.ts';
import { rosterResultSummary } from '../src/features/landscape/roster-display.ts';

test('editing scope stays pending until apply; discard restores the applied values without navigation', () => {
  const applied = { ...EMPTY_CONTEXT, berry: 'berry-blueberry', countries: 'geography-chile' };
  const before = structuredClone(applied), draft = { ...applied, countries: '', news_from: '2026-11-01' };
  assert.equal(scopeHasChanges(applied, draft), true);
  assert.deepEqual(applied, before);
  assert.equal(scopeHasChanges(applied, { ...applied }), false, 'Discard uses the unchanged applied context');
  const result = reduceInvestigation(initialInvestigation(normalizeContext(applied)), { type: 'applyScope', scope: draft });
  assert.equal(result.changed, true); assert.equal(result.state.context.countries, '');
  assert.equal(result.state.context.news_from, '2026-11-01');
  assert.equal(scopeHasChanges(result.state.context, draft), false);
  assert.deepEqual(parseInvestigation(serializeInvestigation(result.state.context)).context, result.state.context);
});

test('Reset scope clears applied filters and stale detail, preserving the active comparison selections', () => {
  const context = { ...EMPTY_CONTEXT, berry: 'berry-strawberry', countries: 'geography-china', geo_basis: 'source_geography',
    actor_roles: 'breeder', relationship_types: 'owns', news_from: '2026-11-01', news_to: '2026-11-15', company_set: 'watched',
    q: 'expo', q_scope: 'catalog', saved_view_id: 'saved-a', saved_revision: '2', focus: 'company-a', detail_path: 'company:company-a',
    lens: 'comparison', comparison_kind: 'variety', cohort_companies: 'company-a,company-b', cohort_varieties: 'variety-a,variety-b', demo_specimens: 'demo-specimen-fern' };
  const before = structuredClone(context), reset = resetInvestigationContext(context);
  for (const key of ['berry', 'countries', 'geo_basis', 'actor_roles', 'relationship_types', 'news_from', 'news_to', 'company_set', 'q', 'q_scope', 'saved_view_id', 'saved_revision', 'focus', 'detail_path'])
    assert.equal(reset[key], EMPTY_CONTEXT[key], key);
  for (const key of ['lens', 'comparison_kind', 'cohort_companies', 'cohort_varieties', 'demo_specimens']) assert.equal(reset[key], context[key], key);
  assert.deepEqual(context, before, 'No analyst selection or underlying data is mutated');
});

test('the applied summary describes actual selectors, independent of draft changes', () => {
  const context = { ...EMPTY_CONTEXT, countries: 'geography-chile,geography-china', company_set: 'watched', news_from: '2026-11-01', q: 'expo' };
  const labels = appliedScopeLabels(context, [{ id: 'geography-chile', name: 'Chile' }, { id: 'geography-china', name: 'China' }]);
  assert.deepEqual(labels, ['All berries', 'Chile, China', 'Watched companies', 'Company connections', 'Published 2026-11-01 – present', 'Company search: “expo”']);
});

test('active table filters include hidden columns and full compound conditions', () => {
  const filters = { geography: { filterType: 'text', operator: 'OR', conditions: [
    { type: 'contains', filter: 'Chile' }, { type: 'contains', filter: 'Peru' }] } };
  assert.deepEqual(sheetFilterSummary('expo', filters, [{ id: 'geography', label: 'Geography' }], { geography: false }), [
    { id: '$quick', label: 'Search', detail: '“expo”' },
    { id: 'geography', label: 'Geography', detail: 'contains “Chile” or contains “Peru”', hidden: true },
  ]);
  assert.deepEqual(sheetFilterSummary('', {}, [], {}), []);
});

test('clear filters preserves display, column order/width/visibility and sort; reset layout does not clear filters', () => {
  const display = { columns: [{ colId: 'b', width: 410, hide: true, sort: 'desc' }, { colId: 'a', width: 220 }], view: 'cards' };
  const before = structuredClone(display), state = { quick: 'expo', filters: { b: { type: 'contains', filter: 'Chile' } }, page: 2 };
  const grid = { setFilterModel: value => { state.filters = value ?? {}; }, paginationGoToFirstPage: () => { state.page = 0; } };
  clearSheetFilters(grid, value => { state.quick = value; });
  assert.deepEqual(state, { quick: '', filters: {}, page: 0 }); assert.deepEqual(display, before);
  state.quick = 'keep'; state.filters = { b: { type: 'equals', filter: 'Peru' } };
  display.columns = defaultSheetColumnState([{ colId: 'a', defaultWidth: 210 }, { colId: 'b', defaultWidth: 300 }]);
  assert.equal(state.quick, 'keep'); assert.equal(state.filters.b.filter, 'Peru'); assert.equal(display.view, 'cards');
});

test('initial load never triggers a reset save; a reset requested before restoration waits and runs once', () => {
  const gate = new SheetFilterReset(), actions = [], state = { filters: { geography: { filter: 'Chile' } } };
  const grid = { isDestroyed: () => false, getFilterModel: () => state.filters,
    setFilterModel: model => { state.filters = model ?? {}; actions.push('columns cleared'); }, paginationGoToFirstPage: () => actions.push('page zero') };
  const quick = value => actions.push(['quick', value]), ack = token => actions.push(['ack', token]);
  assert.equal(gate.apply(0, true, grid, 'expo', quick, ack), false); assert.deepEqual(actions, []);
  assert.equal(gate.apply(1, false, grid, 'expo', quick, ack), false); assert.deepEqual(actions, []);
  assert.equal(gate.apply(1, true, grid, 'expo', quick, ack), true);
  assert.deepEqual(actions, ['columns cleared', ['quick', ''], 'page zero', ['ack', 1]]);
  assert.equal(gate.apply(1, true, grid, '', quick, ack), false); assert.equal(actions.length, 4);
  const empty = new SheetFilterReset(); actions.length = 0;
  empty.apply(2, true, grid, '', quick, ack);
  assert.deepEqual(actions, ['page zero', ['ack', 2]], 'Resetting an unfiltered view does not save a redundant account layout');
});

test('counts distinguish whole-set filtering, partial-page filtering and server company search', () => {
  assert.equal(rosterResultSummary(186, 186, 186, true), '186 companies');
  assert.equal(rosterResultSummary(6, 186, 186, true), '6 matches of 186 companies');
  assert.equal(rosterResultSummary(6, 50, 186, false), '6 matches on this page · 186 in company set');
  assert.equal(rosterResultSummary(15, 15, 186, true, true), '15 search matches · 186 in company set');
  assert.equal(rosterResultSummary(2, 15, 186, true, true), '2 matches of 15 companies · 186 in company set');
});
