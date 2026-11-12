import assert from 'node:assert/strict';
import test from 'node:test';
import { InvestigationApiError } from '../src/api/client.ts';
import { newsTagEditorHref, saveNewsAction, updateNewsDecision } from '../src/features/landscape/news-actions.ts';

test('personal actions use the existing fixed story endpoint and only its governed action payload', async () => {
  const original = globalThis.fetch, requests = [], controller = new AbortController();
  globalThis.fetch = async (url, options) => { requests.push({ url, options }); return new Response(JSON.stringify({ ok: true, decision: { reaction: 'up', saved: true, read: true }, progress: { private: 'ignored' } }), { headers: { 'content-type': 'application/json' } }); };
  try {
    assert.deepEqual(await saveNewsAction('ev-source-a', 'useful', controller.signal), { reaction: 'up', saved: true });
    assert.equal(requests[0].url, '/digest/stories/ev-source-a');
    assert.equal(requests[0].options.method, 'POST'); assert.equal(requests[0].options.credentials, 'same-origin');
    assert.equal(requests[0].options.cache, 'no-store'); assert.equal(requests[0].options.signal, controller.signal);
    assert.deepEqual(JSON.parse(requests[0].options.body), { action: 'useful' });
    for (const [id, action] of [['../other', 'save'], ['ev-source-a', 'capture'], ['ev-source-a', 'publish'], ['https://external.invalid', 'save']])
      await assert.rejects(saveNewsAction(id, action), error => error instanceof InvestigationApiError && error.status === 400);
    assert.equal(requests.length, 1);
  } finally { globalThis.fetch = original; }
});

test('expired sessions and malformed decisions cannot become saved marks', async () => {
  const original = globalThis.fetch;
  try {
    globalThis.fetch = async () => ({ redirected: true, status: 200 });
    await assert.rejects(saveNewsAction('ev-a', 'save'), error => error instanceof InvestigationApiError && error.requiresSession);
    globalThis.fetch = async () => new Response('', { status: 403 });
    await assert.rejects(saveNewsAction('ev-a', 'save'), error => error instanceof InvestigationApiError && error.requiresSession);
    for (const decision of [{ reaction: 'approved', saved: true }, { reaction: null, saved: 'true' }, { saved: false }]) {
      globalThis.fetch = async () => new Response(JSON.stringify({ ok: true, decision }), { headers: { 'content-type': 'application/json' } });
      await assert.rejects(saveNewsAction('ev-a', 'save'), error => error.status === 502);
    }
  } finally { globalThis.fetch = original; }
});

test('exact-story cache updates preserve context, review labels, evidence, source links and unrelated cards', () => {
  const other = { id: 'ev-other', trusted: true, decision: { reaction: null, saved: false } };
  const cache = { revision: 8, scope_key: 'scope-8', applied_scope: { company_set: 'watched' }, data: { cards: [{ id: 'ev-a', trusted: false, source_reviewed: true, retained_source_links: [{ url: 'https://publisher.invalid/exact?b=2&a=1' }], decision: { reaction: null, saved: false } }, other], matching_count: 24 } };
  const before = structuredClone(cache), decision = { reaction: 'down', saved: true };
  const result = updateNewsDecision(cache, 'ev-a', decision);
  assert.deepEqual(cache, before); assert.equal(result.revision, 8); assert.equal(result.applied_scope, cache.applied_scope);
  assert.deepEqual(result.data.cards[0], { ...before.data.cards[0], decision });
  assert.equal(result.data.cards[1], other); assert.equal(result.data.matching_count, 24);
  assert.equal(updateNewsDecision(cache, 'ev-missing', decision), cache);
  const detail = { data: { title: 'Selected source', sections: [] } }; assert.equal(updateNewsDecision(detail, 'ev-a', decision), detail);
});

test('tag links preserve scoped native return while removing Reader and acquisition markers', () => {
  const native = '/app/landscape?berry=berry-blueberry&countries=&company_set=watched&lens=news';
  const link = newsTagEditorHref('/news?berry=blueberry&story=ev-old&item=ev-old&refresh=1&tags_for=ev-old&tags_for=ev-other&return_to=' + encodeURIComponent(native), 'ev-source-a');
  const url = new URL(link, 'https://test.invalid');
  assert.equal(url.pathname, '/news'); assert.equal(url.searchParams.get('berry'), 'blueberry');
  assert.deepEqual(url.searchParams.getAll('tags_for'), ['ev-source-a']); assert.equal(url.searchParams.get('return_to'), native);
  for (const key of ['story', 'item', 'refresh']) assert.equal(url.searchParams.has(key), false);
  for (const href of ['https://external.invalid/news', '//external.invalid/news', '/review', '/news\\other']) assert.throws(() => newsTagEditorHref(href, 'ev-a'));
  assert.throws(() => newsTagEditorHref('/today', '../ev-a'));
});
