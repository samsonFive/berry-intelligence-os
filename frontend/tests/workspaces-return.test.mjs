import assert from 'node:assert/strict';
import test from 'node:test';
import fs from 'node:fs/promises';
import vm from 'node:vm';

const script = await fs.readFile(new URL('../../app/static/living_editor.js', import.meta.url), 'utf8');
// Exercise the actual controller helper without initializing editors, account
// layout writes, feeds or the store. No duplicated URL logic lives in this test.
const helper = script.match(/  function workspaceHref\(href\) \{[\s\S]*?\n  \}/)?.[0];
assert.ok(helper, 'the existing editor supplies the navigation helper');
function navigation(validatedReturn = '', rawLocation = '/workspaces') {
  const context = { root: { dataset: { investigationReturn: validatedReturn } },
    location: new URL(rawLocation, 'https://berry.example'), URL };
  vm.runInNewContext(`${helper}\nglobalThis.href = workspaceHref;`, context);
  return context.href;
}

const native = '/app/landscape?ctx_v=1&berry=berry-blueberry&countries=geography-china&cohort_companies=company-a%2Ccompany-b&detail_path=source%3Aev-a%40brief&q=Sugar%20%26%20acid&company_set=watched';

test('workspace navigation retains the complete validated investigation while preserving existing destination state', () => {
  const href = navigation(native)('/workspaces/wp-blueberry?view=grid&layout=existing#block-1');
  const target = new URL(href, 'https://berry.example');
  assert.equal(target.pathname, '/workspaces/wp-blueberry');
  assert.equal(target.searchParams.get('view'), 'grid'); assert.equal(target.searchParams.get('layout'), 'existing');
  assert.equal(target.hash, '#block-1'); assert.equal(target.searchParams.get('return_to'), native);
  assert.equal(target.searchParams.has('cohort_companies'), false, 'investigation selectors remain nested in the return only');
  assert.equal(new URL(target.searchParams.get('return_to'), 'https://berry.example').searchParams.get('q'), 'Sugar & acid');
});

test('hub to selected page to evidence and reload retain one bounded return rather than nesting return URLs', () => {
  const page = new URL(navigation(native)('/workspaces/wp-research'), 'https://berry.example');
  const reloaded = navigation(page.searchParams.get('return_to'), page.href);
  const evidence = new URL(reloaded('/workspaces/evidence/item-a?version=3#passage'), page.origin);
  assert.equal(evidence.searchParams.get('return_to'), native);
  assert.equal(evidence.searchParams.getAll('return_to').length, 1);
  assert.equal(evidence.searchParams.get('version'), '3'); assert.equal(evidence.hash, '#passage');
  const landscape = new URL(reloaded('/landscapes/explorer?topic=gene-editing&adjacent=1'), page.origin);
  assert.equal(landscape.searchParams.get('topic'), 'gene-editing');
  assert.equal(landscape.searchParams.get('adjacent'), '1'); assert.equal(landscape.searchParams.get('return_to'), native);
});

test('only explicit validated native metadata can supply a return; raw or external parameters cannot', () => {
  const target = '/workspaces/wp-research?view=cards#notes';
  assert.equal(navigation('', `/workspaces?return_to=${encodeURIComponent(native)}`)(target), target,
    'raw URL return_to is never promoted when the server supplied no validated value');
  for (const invalid of ['https://external.example/app/landscape', '//external.example/app/landscape', '/news?story=ev-a',
    '/app/landscape extra', '/app/landscape\\evil', '/app/learn/concept/.', '/app/learn/concept/..',
    '/app/learn/concept/id/extra', '/app/learn/concept/' + 'a'.repeat(181), '/app/landscape?q=' + 'x'.repeat(4096)])
    assert.equal(navigation(invalid)(target), target);
  const reading = '/app/learn/concept/firmness?ctx_v=1&berry=berry-blueberry';
  assert.equal(new URL(navigation(reading)(target), 'https://berry.example').searchParams.get('return_to'), reading);
});

test('external publishers and nonlocal destinations never receive investigation selectors', () => {
  const href = navigation(native);
  for (const target of ['https://publisher.example/article?view=original#figure', '//publisher.example/article',
    'mailto:publisher@example.org', 'javascript:invalid', '/\\publisher.example/article'])
    assert.equal(href(target), target);
});
