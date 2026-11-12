import assert from 'node:assert/strict';
import test from 'node:test';
import fs from 'node:fs/promises';
import vm from 'node:vm';

const drawerScript = await fs.readFile(new URL('../../app/static/news_article_tags.js', import.meta.url), 'utf8');
const workspaceScript = await fs.readFile(new URL('../../app/static/news_workspace.js', import.meta.url), 'utf8');
const settle = () => new Promise(resolve => setImmediate(resolve));

function bootDrawer(respond, { onPage = false } = {}) {
  const requests = [], listeners = {}, drawerListeners = {};
  const element = () => ({ textContent: '', hidden: false, value: '', disabled: false, dataset: {}, addEventListener() {}, focus() {} });
  const title = element(), reason = element(), status = element(), search = element(), filter = element(), source = element();
  const toggle = { ...element(), attributes: {}, setAttribute(key, value) { this.attributes[key] = value; },
    getAttribute(key) { return this.attributes[key]; } };
  const restore = element();
  const row = { dataset: { drawerTagRow: 'tag-a', tagName: 'Authored tag' }, classList: { toggle() {} },
    querySelector: () => toggle, querySelectorAll: () => [toggle, restore] };
  const card = { querySelector(selector) { return selector === 'h2' ? { textContent: 'Stored on-page headline' }
    : selector === '.news-article-tags' ? { replaceChildren() {}, appendChild() {} } : null; } };
  const drawer = { dataset: { canEdit: '1' },
    querySelector(selector) { return ({ '[data-article-tag-title]': title, '[data-article-tag-reason]': reason,
      '[data-article-tag-status]': status, '[data-article-tag-search]': search, '[data-filter-article-tag]': filter,
      '[data-article-tag-source]': source })[selector] ?? null; },
    querySelectorAll: selector => selector === '[data-drawer-tag-row]' ? [row] : [toggle, restore],
    addEventListener(name, callback) { drawerListeners[name] = callback; } };
  const document = { activeElement: { isConnected: true, focus() {} },
    querySelector(selector) { return selector === '[data-news-tag-drawer]' ? drawer
      : selector === '[data-news-card-tags]' ? { textContent: onPage ? '{"ev-page":["tag-a"]}' : '{}' }
        : selector.startsWith('[data-item-id=') && onPage ? card : null; },
    addEventListener(name, callback) { listeners[name] = callback; }, createElement: element };
  let shows = 0;
  const bootstrap = { Offcanvas: { getOrCreateInstance: () => ({ show() { shows++; } }) } };
  const window = { bootstrap, location: { href: 'http://127.0.0.1/news?return_to=%2Fapp%2Fbriefing' } };
  vm.runInNewContext(drawerScript, { document, window, bootstrap, URL,
    fetch: async (url, options = {}) => { requests.push({ url, ...options }); return respond(url, options); } });
  return { window, requests, reason, status, source, toggle, restore, listeners, drawerListeners, card, shows: () => shows };
}

const reply = assignments => ({ ok: true, json: async () => ({ assignments }) });
const assignment = { id: 'tag-a', name: 'Authored tag', origin: 'Manual addition', rationale: 'Recorded analyst correction.' };

test('an off-page tags deep link reads actual assignments before enabling the existing edit controls', async () => {
  let finish;
  const page = bootDrawer(() => new Promise(resolve => { finish = resolve; }));
  assert.equal(page.window.openArticleTags('ev-off-page'), true);
  assert.equal(page.shows(), 1); assert.equal(page.source.textContent, 'Selected stored article');
  assert.equal(page.toggle.disabled, true); assert.equal(page.restore.disabled, true);
  page.drawerListeners.click({ target: { closest: selector => selector === '[data-drawer-tag-toggle]' ? page.toggle : null } });
  assert.equal(page.requests.length, 1, 'unknown assignment state cannot issue an accidental edit');
  assert.equal(page.requests[0].url, '/api/news/tags/explanations/ev-off-page');
  assert.equal(page.requests[0].method, undefined); assert.equal(page.requests[0].credentials, 'same-origin');
  finish(reply([assignment])); await settle();
  assert.equal(page.toggle.attributes['aria-pressed'], 'true');
  assert.equal(page.toggle.disabled, false); assert.equal(page.toggle.textContent, '✓ Assigned');
  assert.equal(page.requests.some(request => request.method === 'POST'), false);
});

test('explicit off-page tag removal uses the existing assignment endpoint and safely has no source card to rewrite', async () => {
  let removed = false;
  const page = bootDrawer(async (_url, options) => {
    if (options.method === 'POST') { removed = true; return { ok: true, json: async () => ({ tags: [] }) }; }
    return reply(removed ? [] : [assignment]);
  });
  page.toggle.dataset.drawerTagToggle = 'tag-a';
  page.window.openArticleTags('ev-off-page'); await settle();
  page.drawerListeners.click({ target: { closest: selector => selector === '[data-drawer-tag-toggle]' ? page.toggle : null } });
  await settle(); await settle();
  const writes = page.requests.filter(request => request.method === 'POST');
  assert.equal(writes.length, 1); assert.equal(writes[0].url, '/api/news/tags/assignment');
  assert.deepEqual(JSON.parse(writes[0].body), { article: 'ev-off-page', tag: 'tag-a', action: 'remove' });
  assert.equal(page.toggle.attributes['aria-pressed'], 'false'); assert.equal(page.toggle.disabled, false);
  assert.equal(page.status.textContent, 'Article tags saved.');
  assert.equal(page.requests.every(request => request.url.startsWith('/api/news/tags/')), true,
    'the controller never opens a Reader, acquires a body or starts classification');
});

test('missing/authenticated metadata errors remain visible and stale responses cannot retarget the selected article', async () => {
  for (const response of [{ ok: false, status: 404 }, { ok: false, status: 401 }]) {
    const page = bootDrawer(async () => response);
    page.window.openArticleTags('ev-unavailable'); await settle();
    assert.match(page.reason.textContent, response.status === 401 ? /Sign in/ : /unavailable/);
    assert.equal(page.toggle.disabled, true); assert.equal(page.requests.length, 1);
  }
  const pending = [];
  const page = bootDrawer(() => new Promise(resolve => pending.push(resolve)));
  page.window.openArticleTags('ev-first'); page.window.openArticleTags('ev-second');
  pending[1](reply([])); await settle();
  pending[0](reply([assignment])); await settle();
  assert.equal(page.toggle.attributes['aria-pressed'], 'false');
  assert.equal(page.requests.at(-1).url, '/api/news/tags/explanations/ev-second');
});

test('existing on-page tag buttons retain their selected tag/headline and invalid identities never request metadata', async () => {
  const page = bootDrawer(async () => reply([assignment]), { onPage: true });
  const button = { dataset: { openArticleTags: 'ev-page', tagId: 'tag-a' }, closest: () => page.card };
  page.listeners.click({ target: { closest: () => button } }); await settle();
  assert.equal(page.source.textContent, 'Stored on-page headline');
  assert.equal(page.reason.textContent, 'Manual addition · Recorded analyst correction.');
  assert.equal(page.toggle.attributes['aria-pressed'], 'true');
  const count = page.requests.length;
  for (const id of ['', '.', '..', '../ev-other', 'ev?a=1', 'ev#fragment', 'a'.repeat(181), null, ['ev-a']])
    assert.equal(page.window.openArticleTags(id), false);
  assert.equal(page.requests.length, count);
});

function bootWorkspace(search) {
  const calls = [], listeners = {}, replacements = [], requests = [];
  const status = { textContent: '' }, root = { dataset: { initialStory: '', newsCompleted: '' } };
  const document = { readyState: 'loading',
    querySelector: selector => selector === '[data-news-workspace]' ? root : selector === '[data-news-refresh-status]' ? status : null,
    querySelectorAll: () => [], addEventListener(name, callback) { listeners[name] = callback; } };
  const window = { location: { href: `http://127.0.0.1/news?return_to=%2Fapp%2Fbriefing&${search}` },
    matchMedia: () => ({ matches: false }), history: { state: null, replaceState(_state, _title, url) { replacements.push(String(url)); } },
    addEventListener() {}, openArticleTags(id) { calls.push(id); return true; } };
  vm.runInNewContext(workspaceScript, { document, window, URL, setTimeout: () => 1, clearTimeout() {},
    fetch: (...args) => { requests.push(args); throw new Error('Startup must not fetch source data'); } });
  return { calls, requests, status, replacements, ready: () => listeners.DOMContentLoaded() };
}

test('tags_for startup waits for the existing controller, consumes only its marker and never selects a story', () => {
  const page = bootWorkspace('tags_for=ev-off-page');
  assert.deepEqual(page.calls, []); page.ready();
  assert.deepEqual(page.calls, ['ev-off-page']); assert.deepEqual(page.requests, []);
  const final = new URL(page.replacements[0]);
  assert.equal(final.searchParams.get('return_to'), '/app/briefing');
  for (const field of ['tags_for', 'story', 'item', 'refresh']) assert.equal(final.searchParams.has(field), false);
  for (const query of ['tags_for=ev-a&tags_for=ev-b', 'tags_for=..', 'tags_for=ev%2Fa', `tags_for=${'a'.repeat(181)}`]) {
    const invalid = bootWorkspace(query); invalid.ready();
    assert.deepEqual(invalid.calls, []); assert.deepEqual(invalid.requests, []);
    assert.match(invalid.status.textContent, /could not be opened/);
  }
});
