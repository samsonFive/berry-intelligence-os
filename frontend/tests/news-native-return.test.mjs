import assert from 'node:assert/strict';
import test from 'node:test';
import fs from 'node:fs/promises';
import vm from 'node:vm';

const script = await fs.readFile(new URL('../../app/static/news_tags.js', import.meta.url), 'utf8');
const settle = () => new Promise(resolve => setImmediate(resolve));
function boot(autoRecheck, jobStatus) {
  const requests = [], timers = [], listeners = {};
  const status = { dataset: { jobStatus }, appendChild() {}, hidden: true, textContent: '' };
  const retry = { addEventListener(name, callback) { listeners[name] = callback; } };
  const form = { addEventListener() {}, requestSubmit() {}, checkValidity: () => true };
  const panel = { dataset: { autoRecheck, canSave: '1' }, closest: () => form, querySelectorAll: () => [],
    querySelector(selector) { return selector === '[data-tag-status]' ? status : selector === '[data-retry-tags]' ? retry : selector === '[data-tag-search]' ? { addEventListener() {} } : null; } };
  const document = { querySelector: selector => selector === '[data-tags-panel]' ? panel : null, querySelectorAll: () => [], createElement: () => ({}) };
  vm.runInNewContext(script, { document, window: { location: { href: 'http://127.0.0.1/news?return_to=%2Fapp%2Fbriefing' } }, URL,
    fetch: async (url, options = {}) => { requests.push({ url, method: options.method ?? 'GET' }); return { ok: true, json: async () => ({ status: 'ready', processed: 0, total: 0 }) }; },
    setTimeout: callback => { timers.push(callback); return timers.length; } });
  return { requests, timers, listeners };
}

test('native reading expansion does not start pending classification', async () => {
  const page = boot('false', 'pending'); await settle();
  assert.deepEqual(page.requests, []); assert.equal(page.timers.length, 0);
});
test('native expansion preserves the explicit Recheck control', async () => {
  const page = boot('false', 'pending'); page.listeners.click(); await settle();
  assert.deepEqual(page.requests, [{ url: '/api/news/tags/classify', method: 'POST' }]);
  assert.equal(page.timers.length, 1);
});
test('ordinary legacy pending behavior remains available with or without the new attribute', async () => {
  for (const setting of ['true', undefined]) {
    const page = boot(setting, 'pending'); await settle();
    assert.deepEqual(page.requests, [{ url: '/api/news/tags/classify', method: 'POST' }]);
  }
});
test('native expansion still observes an already running or queued job without starting work', async () => {
  for (const state of ['running', 'queued']) {
    const page = boot('false', state); assert.deepEqual(page.requests, []); assert.equal(page.timers.length, 1);
    page.timers[0](); await settle();
    assert.deepEqual(page.requests, [{ url: '/api/news/tags/status', method: 'GET' }]);
  }
});
