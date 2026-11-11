import assert from 'node:assert/strict';
import test from 'node:test';
import { EMPTY_CONTEXT, investigationHref } from '../src/contracts/investigation.ts';
import { InvestigationApiError } from '../src/api/client.ts';
import { DEFAULT_LEARNING_SELECTION, getLearningCatalog, getLearningContent, learningRequestURL, legacyExpansionHref } from '../src/features/learn/api.ts';

const context = { ...EMPTY_CONTEXT, q: 'Costa', countries: 'geography-china,geography-peru', focus: 'company-one', cohort_companies: 'company-one,company-two' };
const envelope = data => ({ api_v: 1, request_id: 'learning-fixture', revision: 7, scope_key: 'learning-fixture', applied_scope: {}, issues: [], data });
const catalog = { collections: { concepts: { items: [] }, lessons: { items: [] } }, facets: { pillars: [], knowledge_classes: [] }, counts: { concepts: 27, lessons: 0 } };

test('the library defaults to its own empty search while investigation context is preserved separately', () => {
  const url = new URL(learningRequestURL(context, 7, DEFAULT_LEARNING_SELECTION), 'https://berry.test');
  assert.equal(url.searchParams.get('q'), ''); assert.equal(url.searchParams.get('kind'), 'all');
  assert.equal(url.searchParams.get('countries'), context.countries);
  assert.equal(url.searchParams.get('cohort_companies'), context.cohort_companies);
  assert.equal(context.q, 'Costa');
  assert.equal(new URL(investigationHref('/app/learn/concept/concept-firmness', context), 'https://berry.test').searchParams.get('q'), 'Costa');
  const own = new URL(learningRequestURL(context, 7, { ...DEFAULT_LEARNING_SELECTION, q: 'chill', pillar: 'plant_biology_agronomy', offset: 40 }), 'https://berry.test');
  assert.equal(own.searchParams.get('q'), 'chill'); assert.equal(own.searchParams.get('offset'), '40');
});

test('learning request serialization never accepts arbitrary body or destination fields', () => {
  const url = learningRequestURL(context, 7, { ...DEFAULT_LEARNING_SELECTION, article_text: 'PRIVATE BODY', destination: 'https://external.example' });
  assert.equal(url.includes('PRIVATE'), false); assert.equal(url.includes('destination'), false);
  assert.throws(() => learningRequestURL(context, 7, DEFAULT_LEARNING_SELECTION, { kind: 'concept', id: '../private' }), InvestigationApiError);
  assert.throws(() => learningRequestURL(context, -1, DEFAULT_LEARNING_SELECTION), InvestigationApiError);
  assert.throws(() => learningRequestURL(context, 7, { ...DEFAULT_LEARNING_SELECTION, q: 'x'.repeat(201) }), InvestigationApiError);
});

test('native read uses the existing same-origin envelope, cancellation and private caching boundary', async () => {
  const original = globalThis.fetch; const controller = new AbortController(); let captured;
  globalThis.fetch = async (url, options) => { captured = { url, options }; return new Response(JSON.stringify(envelope(catalog)), { headers: { 'content-type': 'application/json' } }); };
  try {
    const response = await getLearningCatalog(context, 7, DEFAULT_LEARNING_SELECTION, controller.signal);
    assert.equal(response.data.counts.concepts, 27);
    assert.equal(captured.options.credentials, 'same-origin'); assert.equal(captured.options.cache, 'no-store');
    assert.equal(captured.options.signal, controller.signal); assert.match(captured.url, /^\/api\/investigations\/v1\/learning\?/);
  } finally { globalThis.fetch = original; }
});

test('expired sessions and incompatible model/revision responses stay explicit', async () => {
  const original = globalThis.fetch;
  try {
    globalThis.fetch = async () => new Response('Sign in', { status: 401 });
    await assert.rejects(getLearningCatalog(context, 7, DEFAULT_LEARNING_SELECTION), error => error.requiresSession && error.status === 401);
    for (const value of [{ ...envelope(catalog), revision: 6 }, envelope({})]) {
      globalThis.fetch = async () => new Response(JSON.stringify(value), { headers: { 'content-type': 'application/json' } });
      await assert.rejects(getLearningCatalog(context, 7, DEFAULT_LEARNING_SELECTION), error => error.status === 502);
    }
  } finally { globalThis.fetch = original; }
});

test('a selected read cannot substitute a different lesson identity', async () => {
  const original = globalThis.fetch;
  globalThis.fetch = async () => new Response(JSON.stringify(envelope({ item: { kind: 'concept', id: 'concept-other' }, sections: [], citations: [], media: [], berry_notes: [], related: [] })), { headers: { 'content-type': 'application/json' } });
  try { await assert.rejects(getLearningContent('concept', 'concept-firmness', context, 7, '/app/learn'), error => error.status === 502); }
  finally { globalThis.fetch = original; }
});

test('legacy expansion reconstructs the current full native return and refuses external destinations', () => {
  const current = investigationHref('/app/learn/concept/concept-firmness', context);
  const href = legacyExpansionHref('/learn/firmness?return_to=%2Fapp%2Flandscape', current);
  const parsed = new URL(href, 'https://berry.test');
  assert.equal(parsed.pathname, '/learn/firmness'); assert.equal(parsed.searchParams.get('return_to'), current);
  assert.equal(legacyExpansionHref('https://external.example/learn/firmness', current), undefined);
  const fallback = new URL(legacyExpansionHref('/learn/firmness', 'https://external.example/app/learn'), 'https://berry.test');
  assert.equal(fallback.searchParams.get('return_to'), '/app/learn');
});
