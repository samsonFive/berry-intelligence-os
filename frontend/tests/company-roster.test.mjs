import assert from 'node:assert/strict';
import test from 'node:test';
import { COMPANY_ROSTER_COLUMNS, COMPANY_ROSTER_VIEW_KEY, companyRosterText, companyTierRows, isRosterTierHeader, orderCompanyTierNodes, rosterTextMatch } from '../src/features/landscape/company-roster-data.ts';
import { createColumnCatalog, decodeGridLayout, defaultGridLayout, encodeGridLayout } from '../src/features/grids/layout-codec.ts';

test('Grid/Cards view round trips as bounded layout metadata separate from AG column filters', async () => {
  const catalog = await createColumnCatalog(COMPANY_ROSTER_COLUMNS), snapshot = defaultGridLayout(catalog);
  snapshot.view = 'cards'; snapshot.quickFilter = 'China';
  snapshot.filterModel['company.geography'] = { filterType: 'text', type: 'contains', filter: 'trial' };
  const wire = encodeGridLayout(snapshot, catalog), loaded = decodeGridLayout(wire, catalog);
  assert.equal(wire.filters.view, 'cards'); assert.equal(loaded.snapshot.view, 'cards');
  assert.deepEqual(loaded.snapshot.filterModel, snapshot.filterModel);
  assert.equal('view' in loaded.snapshot.filterModel, false);
  assert.equal(loaded.snapshot.columns.find(column => column.colId === 'company.collection').hide, true);
  assert.equal(loaded.snapshot.columns.find(column => column.colId === 'company.identity').hide, false);
  loaded.snapshot.columns.find(column => column.colId === 'company.collection').hide = false;
  assert.equal(decodeGridLayout(encodeGridLayout(loaded.snapshot, catalog, wire), catalog).snapshot.columns.find(column => column.colId === 'company.collection').hide, false,
    'explicitly showing the optional collection column survives reload');
});

test('invalid display enums reject without changing older portfolio snapshots or legacy layouts', async () => {
  const catalog = await createColumnCatalog([{ colId: 'cultivar.identity', lockedVisible: true }]);
  const snapshot = defaultGridLayout(catalog), wire = encodeGridLayout(snapshot, catalog);
  assert.equal('view' in wire.filters, false); assert.deepEqual(decodeGridLayout(wire, catalog).snapshot, snapshot);
  for (const value of ['table', 'Cards', '', null, 1, { view: 'cards' }]) {
    assert.throws(() => encodeGridLayout({ ...snapshot, view: value }, catalog), /display view/);
    assert.throws(() => decodeGridLayout({ ...wire, filters: { ...wire.filters, view: value } }, catalog));
  }
  const withView = encodeGridLayout({ ...snapshot, view: 'cards' }, catalog);
  assert.equal(encodeGridLayout(snapshot, catalog, withView).filters.view, 'cards', 'an unmodified optional value is retained');
  const legacy = { revision: 3, widths: {}, order: [], hidden: [], filters: { old: 'preserved' } };
  assert.equal(decodeGridLayout(legacy, catalog).writable, false);
  assert.throws(() => encodeGridLayout(snapshot, catalog, legacy), /earlier layout/);
});

test('roster semantic columns remain stable across company pages and collection starts secondary', async () => {
  const a = await createColumnCatalog(COMPANY_ROSTER_COLUMNS), b = await createColumnCatalog([...COMPANY_ROSTER_COLUMNS]);
  assert.equal(COMPANY_ROSTER_VIEW_KEY, 'berry-company-roster-v1');
  assert.equal(a.columns.length, 7); assert.deepEqual(a.columns.map(column => column.key), b.columns.map(column => column.key));
  assert.equal(defaultGridLayout(a).columns.filter(column => !column.hide).length, 6);
  assert.deepEqual(a.columns.slice(0, 3).map(column => column.colId), ['company.identity', 'company.tier', 'company.compare']);
  assert.equal(a.columns.filter(column => column.lockedVisible).length, 1, 'only the original identity is frozen');
  for (const id of ['company.tier', 'company.compare']) assert.equal(a.byId.get(id).restoreAfter, 'company.identity');
  const protectedIdentity = await createColumnCatalog([{ colId: 'company.identity', lockedVisible: true, defaultHidden: true }]);
  assert.equal(defaultGridLayout(protectedIdentity).columns[0].hide, false);
});

test('roster filtering retains complete authored names, exact path attribution, qualifiers and collection detail', () => {
  const company = { id: 'company-a', label: 'Named company', identity_note: 'Identity caveat', in_scope: true, watched: true,
    roles: ['breeder', 'marketer', 'seller', 'fourth_authored_role'], berry_ids: ['berry-blueberry', 'berry-raspberry'],
    geographies: [{ label: 'China', activity: 'Planned entry', status: 'Not active', review: 'Unreviewed', caveat: 'Review first' }],
    monitoring: { state: 'manual_monitoring_required', detail: 'Full authored collection detail' } };
  const program = { id: 'program-a', label: 'Named program', type: 'breeding_program' }, cultivar = { id: 'variety-a', label: 'Cultivar A', type: 'variety' };
  const edge = { id: 'rel-a', subject_id: program.id, object_id: cultivar.id, role: 'Recorded breeder', status: 'disputed',
    status_label: 'Disputed record', caveat: 'Full material limitation', notes: 'Recorded full path note', company_geography: false, genetic_geography: false };
  const model = { nodes: { [program.id]: program, [cultivar.id]: cultivar }, market_rows: [],
    portfolios: [{ actor: company, programs: [program], varieties: [cultivar], edges: [], portfolio_edges: [edge] }] };
  const before = structuredClone({ company, model }), values = companyRosterText(company, model);
  assert.match(values['company.genetics'], /Named program · Recorded breeder · Cultivar A · Disputed record · Full material limitation · Recorded full path note/);
  assert.match(values['company.roles'], /fourth authored role/); assert.match(values['company.roles'], /blueberry · raspberry/);
  assert.match(values['company.geography'], /Planned entry · Not active · Unreviewed · Review first/);
  assert.match(values['company.collection'], /Full authored collection detail/);
  assert.deepEqual({ company, model }, before);
});

test('Community tier headers retain full-universe counts and every real row while sorting stays within tiers', () => {
  const companies = [{ id: 'company-b', assigned_tier: 'tier2' }, { id: 'company-a', assigned_tier: 'tier1' },
    { id: 'company-c', assigned_tier: 'tier1' }, { id: 'company-legacy', assigned_tier: 'historic-custom' }];
  const groups = [{ tier: 'tier1', label: 'Tier 1', count: 57, matching_count: 12 },
    { tier: 'tier2', label: 'Tier 2', count: 31, matching_count: 8 }, { tier: 'other_legacy', label: 'Other legacy tiers', count: 9, matching_count: 4 }];
  const rows = companyTierRows(companies, groups), headers = rows.filter(isRosterTierHeader);
  assert.deepEqual(headers.map(header => [header.tier, header.count, header.matching_count, header.loaded_count]),
    [['tier1', 57, 12, 2], ['tier2', 31, 8, 1], ['other_legacy', 9, 4, 1]]);
  assert.deepEqual(rows.filter(row => !isRosterTierHeader(row)).map(row => row.id), ['company-a', 'company-c', 'company-b', 'company-legacy']);
  const nodes = [...rows].reverse().map(data => ({ data }));
  const ordered = orderCompanyTierNodes(nodes);
  assert.deepEqual(ordered.filter(node => !isRosterTierHeader(node.data)).map(node => node.data.id), ['company-c', 'company-a', 'company-b', 'company-legacy'],
    'user order inside a tier stays intact while tier hierarchy is fixed');
  assert.equal(new Set(ordered).size, nodes.length); assert.equal(ordered.length, nodes.length);
  assert.equal(companyTierRows([companies[0]], [])[0].count, null, 'missing metadata never becomes a false global page count');
});

test('tier header matching does not turn presentation rows into company matches or alter normal text operations', () => {
  const header = companyTierRows([{ id: 'company-a', assigned_tier: 'tier1' }], [{ tier: 'tier1', label: 'Tier 1', count: 99, matching_count: 5 }])[0];
  for (const option of ['contains', 'notContains', 'equals', 'notEqual', 'startsWith', 'endsWith'])
    assert.equal(rosterTextMatch({ data: header, value: '', filterText: 'unrelated', filterOption: option }), true);
  const data = { id: 'company-a', assigned_tier: 'tier1' };
  for (const [filterOption, filterText] of [['contains', 'creek'], ['notContains', 'costa'], ['equals', 'fall creek'],
    ['notEqual', 'costa'], ['startsWith', 'fall'], ['endsWith', 'creek']])
    assert.equal(rosterTextMatch({ data, value: 'fall creek', filterText, filterOption }), true);
  assert.equal(rosterTextMatch({ data, value: 'fall creek', filterText: 'costa', filterOption: 'contains' }), false);
});
