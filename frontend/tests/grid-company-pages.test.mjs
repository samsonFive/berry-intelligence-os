import assert from 'node:assert/strict';
import test from 'node:test';
import { companyPage, companyPageSwitchBlocked, companyPageViewKey, LEGACY_PORTFOLIO_VIEW_KEY, DEFAULT_COMPANY_COLUMN_SIZE } from '../src/features/grids/company-pages.ts';
import { createColumnCatalog, defaultGridLayout, encodeGridLayout, validViewKey } from '../src/features/grids/layout-codec.ts';
import { AccountGridLayouts } from '../src/features/grids/account-layout.ts';

const companies = count => Array.from({ length: count }, (_, index) => ({ id: `company-${String(index).padStart(4, '0')}`, label: `Company ${index}` }));

test('every company remains accessible beyond the former cap and each page fits existing sheet bounds', async () => {
  const all = companies(103), seen = [];
  for (let index = 0; index < companyPage(all).count; index++) {
    const page = companyPage(all, index);
    assert.equal(page.total, 103); assert.ok(page.companies.length <= 10);
    seen.push(...page.companies.map(company => company.id));
    const catalog = await createColumnCatalog([{ colId: 'cultivar.identity', lockedVisible: true }, { colId: 'cultivar.comparison-pin', lockedVisible: true },
      ...page.companies.map(company => ({ colId: `company.${company.id}.recorded-role` }))]);
    const wire = encodeGridLayout(defaultGridLayout(catalog), catalog, { revision: 0, widths: {}, order: [], hidden: [], filters: {} });
    assert.equal(wire.order.length, page.companies.length + 2);
  }
  assert.deepEqual(seen, all.map(company => company.id)); assert.equal(new Set(seen).size, 103);
});

test('page membership is independent of names/API order and requested pages clamp without dropping the universe', () => {
  const all = companies(23), original = structuredClone(all);
  const renamedReordered = [...all].reverse().map(company => ({ ...company, label: 'Renamed' }));
  assert.deepEqual(companyPage(all, 1).companies.map(company => company.id), companyPage(renamedReordered, 1).companies.map(company => company.id));
  assert.equal(companyPage(all, 999).index, 2); assert.equal(companyPage(all, -1).index, 0); assert.equal(companyPage(all, NaN).index, 0);
  assert.deepEqual(all, original); assert.equal(companyPage(all, 2).end, 23);
});

test('paged namespaces bind exact canonical membership, not page number, labels or ordering', async () => {
  const first = companies(10).map(company => company.id), other = companies(20).slice(10).map(company => company.id);
  const key = await companyPageViewKey(first, true);
  assert.equal(key, await companyPageViewKey([...first].reverse(), true));
  assert.notEqual(key, await companyPageViewKey(other, true));
  assert.notEqual(key, await companyPageViewKey(first.slice(1), true));
  assert.equal(key.length, 76); assert.equal(validViewKey(key), true);
  assert.equal(await companyPageViewKey(first, false), LEGACY_PORTFOLIO_VIEW_KEY);
});

test('invalid or duplicate identities cannot retarget a saved page and only unsafe switch phases block navigation', async () => {
  assert.throws(() => companyPage([{ id: 'company-a' }, { id: 'company-a' }]), /distinct/);
  await assert.rejects(companyPageViewKey(companies(11).map(company => company.id), false), /identified safely/);
  await assert.rejects(companyPageViewKey(['company-a', '../other'], true), /identified safely/);
  for (const phase of ['loading', 'pending', 'saving', 'conflict']) assert.equal(companyPageSwitchBlocked(phase), true);
  for (const phase of ['ready', 'saved', 'error', 'local']) assert.equal(companyPageSwitchBlocked(phase), false);
});

test('variable company windows expose every column, including All, while the legacy ten-column default remains intact', async () => {
  const all = companies(103);
  assert.equal(DEFAULT_COMPANY_COLUMN_SIZE, 25);
  assert.equal(companyPage(all).size, 10);
  for (const size of [10, 25, 50, 'all']) {
    const seen = [];
    for (let index = 0; index < companyPage(all, 0, size).count; index++) {
      const page = companyPage(all, index, size); seen.push(...page.companies.map(row => row.id));
      assert.equal(page.membershipBound, true);
      assert.notEqual(await companyPageViewKey(page.companies.map(row => row.id), page.membershipBound), LEGACY_PORTFOLIO_VIEW_KEY);
    }
    assert.deepEqual(seen, all.map(row => row.id));
  }
  const everything = companyPage(all, 99, 'all');
  assert.equal(everything.companies.length, 103); assert.equal(everything.index, 0); assert.equal(everything.paged, false);
  assert.equal(everything.membershipBound, true, 'All must never fall back to the old full-portfolio layout');
  assert.equal(companyPage(companies(10), 0, 'all').membershipBound, false);
  assert.throws(() => companyPage(all, 0, 38), /supported/);
});

test('twenty-five company windows fit unchanged account caps and fifty never relaxes that wire', async () => {
  const columns = count => [{ colId: 'cultivar.identity', lockedVisible: true }, { colId: 'cultivar.comparison-pin', lockedVisible: true },
    ...companies(count).map(row => ({ colId: `company.${row.id}.recorded-role` }))];
  const catalog = await createColumnCatalog(columns(25));
  assert.equal(encodeGridLayout(defaultGridLayout(catalog), catalog).order.length, 27);
  await assert.rejects(createColumnCatalog(columns(50)), /forty/);
  const firstTen = companies(10).map(row => row.id);
  assert.equal(await companyPageViewKey(firstTen, true), await companyPageViewKey(companyPage(companies(20)).companies.map(row => row.id), true));
});

test('saving two company pages preserves each page and the earlier full-portfolio layout independently', async () => {
  const all = companies(20), legacy = { revision: 7, widths: {}, order: [], hidden: [], filters: { preserved: 'earlier-layout' } };
  const saved = new Map([[LEGACY_PORTFOLIO_VIEW_KEY, structuredClone(legacy)]]);
  const request = async (url, options) => {
    const key = url.split('/').at(-1), current = saved.get(key) ?? { revision: 0, widths: {}, order: [], hidden: [], filters: {} };
    if (options.method === 'POST') {
      const payload = JSON.parse(options.body);
      assert.equal(payload.revision, current.revision);
      saved.set(key, { ...payload, revision: current.revision + 1 });
    }
    return new Response(JSON.stringify(saved.get(key) ?? current), { status: 200, headers: { 'content-type': 'application/json' } });
  };
  const controllers = [], keys = [], expected = [];
  for (const index of [0, 1]) {
    const page = companyPage(all, index), key = await companyPageViewKey(page.companies.map(company => company.id), true);
    keys.push(key);
    const catalog = await createColumnCatalog([{ colId: 'cultivar.identity', lockedVisible: true }, { colId: 'cultivar.comparison-pin', lockedVisible: true },
      ...page.companies.map(company => ({ colId: `company.${company.id}.recorded-role` }))]);
    const controller = new AccountGridLayouts({ viewKey: key, catalog, fetch: request, sessionEvents: new EventTarget() });
    controllers.push(controller); await controller.load();
    const snapshot = defaultGridLayout(catalog); snapshot.columns[2].width = 375 + index * 35; snapshot.columns[3].hide = true;
    expected.push(structuredClone(snapshot)); await controller.save(snapshot);
  }
  assert.deepEqual((await controllers[0].load()).snapshot, expected[0]);
  assert.deepEqual((await controllers[1].load()).snapshot, expected[1]);
  assert.deepEqual(saved.get(LEGACY_PORTFOLIO_VIEW_KEY), legacy);
  assert.notDeepEqual(saved.get(keys[0]).widths, saved.get(keys[1]).widths);
  controllers.forEach(controller => controller.dispose());
});
