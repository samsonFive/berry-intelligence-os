import assert from 'node:assert/strict';
import test from 'node:test';
import { inlineText, parseInline, parseLessonMarkdown, safeSourceHref } from '../src/features/learn/markdown.ts';

const sources = [{ title: 'Regional extension guide', publisher: 'University', url: 'https://extension.example/guide', reference_ids: ['web:1'] }];

test('captured citation references retain their exact source and missing references stay explicit', () => {
  const nodes = parseInline('A regional example [web:1] and missing source [web:2].', sources);
  const citation = nodes.find(node => node.kind === 'citation');
  assert.deepEqual(citation, { kind: 'citation', text: '1', title: sources[0].title, url: sources[0].url });
  assert.equal(nodes.find(node => node.kind === 'source_gap').text, 'Source link unavailable');
});

test('HTML stays literal text and arbitrary generated links do not become active media or sources', () => {
  const raw = '<script>alert("body")</script> <img src=x onerror=alert(1)> [unverified](https://invented.example/claim)';
  const nodes = parseInline(raw, sources);
  assert.equal(nodes.every(node => node.kind === 'text'), true);
  assert.match(inlineText(nodes), /<script>/);
  assert.match(inlineText(nodes), /unverified \(link not verified\)/);
  assert.equal(JSON.stringify(nodes).includes('https://invented.example'), false);
  const image = parseInline('![Teaching suggestion](https://extension.example/guide)', sources);
  assert.deepEqual(image, [{ kind: 'link', text: 'Teaching suggestion (image source)', url: sources[0].url }]);
  assert.equal('image_url' in image[0], false);
});

test('only credential-free http sources can activate captured links', () => {
  for (const value of ['javascript:alert(1)', 'data:text/html,<script>', '//evil.example', '/local', 'https://user:pass@example.org', 'https://example.org/\nsecret', 'https://example.org\\other'])
    assert.equal(safeSourceHref(value), undefined);
  assert.equal(safeSourceHref('https://extension.example/guide#page=2'), 'https://extension.example/guide#page=2');
  assert.equal(parseInline('[web:1]', [{ ...sources[0], url: 'javascript:alert(1)' }])[0].kind, 'source_gap');
});

test('lesson reading preserves heading, order numbers, paragraphs, tables and inline citations', () => {
  const text = '# The lesson\n\nAn explanation with **strong text** and *emphasis* [web:1].\n\n## Steps\n3. First recorded step\n7. Later recorded step\n\n- A crop-specific limit\n\n| Crop | Note |\n| --- | --- |\n| Raspberry | Regional [web:1] |\n| Blueberry | Separate biology |';
  const blocks = parseLessonMarkdown(text, sources, 'The lesson');
  assert.deepEqual(blocks.map(block => block.kind), ['paragraph', 'heading', 'list', 'list', 'table']);
  assert.equal(blocks[0].text.some(node => node.kind === 'strong'), true);
  assert.equal(blocks[0].text.some(node => node.kind === 'em'), true);
  assert.equal(blocks[2].ordered, true); assert.deepEqual(blocks[2].numbers, [3, 7]);
  assert.equal(blocks[3].ordered, false);
  assert.equal(blocks[4].headers.length, 2); assert.equal(blocks[4].rows.length, 2);
  assert.equal(blocks[4].rows[0][1].some(node => node.kind === 'citation'), true);
  assert.equal(parseLessonMarkdown('# A different heading', [], 'The lesson')[0].kind, 'heading');
});

test('oversized formatting fails explicitly instead of losing the rest of a selected lesson', () => {
  assert.throws(() => parseLessonMarkdown('x'.repeat(2_000_001)), /bounded reader/);
  const wide = '| ' + Array(33).fill('Cell').join(' | ') + ' |\n| ' + Array(33).fill('---').join(' | ') + ' |';
  assert.throws(() => parseLessonMarkdown(wide), /table exceeds/);
  assert.throws(() => parseLessonMarkdown(Array(4097).fill('# Section').join('\n')), /too many sections/);
});

test('empty lessons stay empty and pure rendering preparation never requests a provider or source', () => {
  const original = globalThis.fetch;
  globalThis.fetch = () => { throw new Error('A read-only parser must not fetch'); };
  try {
    assert.deepEqual(parseLessonMarkdown('', sources), []);
    assert.equal(inlineText(parseInline('The regional source [web:1].', sources)), 'The regional source 1.');
  } finally { globalThis.fetch = original; }
});
