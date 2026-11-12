import assert from 'node:assert/strict';
import test from 'node:test';
import { CompanyPageMemory, companyUniverseIdentity } from '../src/features/grids/company-page-memory.ts';
import { EMPTY_CONTEXT, parseInvestigation, sameContext, serializeInvestigation } from '../src/contracts/investigation.ts';

const universe = companyUniverseIdentity(Array.from({ length: 25 }, (_, i) => ({ id: `company-${i}` })));
const request = (memory, key, overrides = {}) => ({ key, universe, count: 3, contextMatches: true, epoch: memory.epoch, ...overrides });
const mounted = (input, index) => ({ key: input.key, universe: input.universe, index, epoch: input.epoch });

test('mounted PUSH/REPLACE actions inherit the page and POP restores each exact entry independently', () => {
  const memory = new CompanyPageMemory(), first = request(memory, 'entry-a');
  memory.remember(first, 1);
  const focus = request(memory, 'entry-focus');
  assert.equal(memory.resolve(focus, 'PUSH', mounted(first, 1)), 1);
  memory.remember(focus, 1); memory.remember(focus, 2);
  const pin = request(memory, 'entry-pin');
  assert.equal(memory.resolve(pin, 'REPLACE', mounted(focus, 2)), 2);
  memory.remember(pin, 2);
  assert.equal(memory.resolve(first, 'POP', mounted(pin, 2)), 1);
  assert.equal(memory.resolve(focus, 'POP', mounted(first, 1)), 2);
});

test('unmounting a lens retains its entry, while a fresh document has no persisted page', () => {
  const memory = new CompanyPageMemory(), portfolio = request(memory, 'entry-portfolio');
  memory.remember(portfolio, 1);
  assert.equal(memory.resolve(portfolio, 'POP', null), 1, 'return through Comparison restores before preparing columns');
  assert.equal(memory.resolve(request(memory, 'entry-new'), 'PUSH', null), 0, 'a different fresh entry has no mounted page to inherit');
  const reloaded = new CompanyPageMemory();
  assert.equal(reloaded.resolve(request(reloaded, portfolio.key), 'POP', null), 0, 'RAM memory has no serialized reload state');
});

test('exact company membership invalidates a page while name edits and incoming order do not', () => {
  const companies = [{ id: 'company-b', label: 'B' }, { id: 'company-a', label: 'A' }];
  const before = structuredClone(companies);
  const identity = companyUniverseIdentity(companies);
  assert.equal(identity, companyUniverseIdentity([...companies].reverse().map(row => ({ ...row, label: 'Renamed' }))));
  assert.notEqual(identity, companyUniverseIdentity([...companies, { id: 'company-c', label: 'C' }]));
  assert.deepEqual(companies, before);
  const memory = new CompanyPageMemory(), original = request(memory, 'entry-a');
  memory.remember(original, 2);
  const changed = { ...original, universe: identity };
  assert.equal(memory.resolve(changed, 'POP', mounted(original, 2)), 0);
  assert.equal(memory.resolve(changed, 'PUSH', mounted(original, 2)), 0);
  memory.remember(changed, 0);
  assert.equal(memory.resolve(original, 'POP'), 0, 'a changed universe cannot inherit the former membership page');
});

test('transient URL/context mismatch cannot overwrite the saved POP entry with an old model', () => {
  const memory = new CompanyPageMemory(), saved = request(memory, 'entry-return');
  memory.remember(saved, 2);
  const destination = { ...EMPTY_CONTEXT, berry: 'berry-blueberry', countries: 'geography-china', lens: 'portfolio' };
  const parsed = parseInvestigation(serializeInvestigation(destination)).context;
  const transient = { ...saved, universe: 'old-model-universe', contextMatches: sameContext(parsed, EMPTY_CONTEXT) };
  assert.equal(transient.contextMatches, false);
  assert.equal(memory.resolve(transient, 'POP', mounted(transient, 0)), 0);
  assert.equal(memory.remember(transient, 0), false);
  assert.equal(memory.size, 1);
  const settled = { ...saved, contextMatches: sameContext(parsed, destination) };
  assert.equal(memory.resolve(settled, 'POP'), 2, 'the exact previous page survives provider layout-effect restoration');
});

test('RAM entry count stays bounded and indexes clamp to available company pages', () => {
  const memory = new CompanyPageMemory();
  for (let i = 0; i < 70; i++) memory.remember(request(memory, `entry-${i}`), 1);
  assert.equal(memory.size, 64);
  assert.equal(memory.resolve(request(memory, 'entry-0'), 'POP'), 0);
  assert.equal(memory.resolve(request(memory, 'entry-69'), 'POP'), 1);
  const current = request(memory, 'entry-69');
  memory.remember(current, 999); assert.equal(memory.resolve(current, 'POP'), 2);
  assert.equal(memory.resolve({ ...current, count: 1 }, 'POP'), 0);
  memory.remember(current, Infinity); assert.equal(memory.resolve(current, 'POP'), 0);
  assert.equal(memory.remember({ ...current, key: '../invalid' }, 1), false);
  assert.equal(memory.remember({ ...current, count: 0 }, 1), false);
  assert.equal(memory.size, 64);
});

test('explicit session clearing invalidates old reads and late writes without retaining private entry identities', () => {
  const memory = new CompanyPageMemory(), old = request(memory, 'entry-private');
  memory.remember(old, 2); memory.clear();
  assert.equal(memory.size, 0); assert.notEqual(memory.epoch, old.epoch);
  assert.equal(memory.resolve(old, 'POP', mounted(old, 2)), 0);
  assert.equal(memory.remember(old, 2), false, 'an old hook/effect cannot repopulate cleared session memory');
  const fresh = request(memory, 'entry-fresh');
  assert.equal(memory.resolve(fresh, 'PUSH', mounted(old, 2)), 0, 'a new epoch cannot inherit an old mounted selection');
  assert.equal(memory.remember(fresh, 1), true);
  assert.equal(memory.resolve(fresh, 'POP'), 1);
});
