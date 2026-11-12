import assert from 'node:assert/strict';
import test from 'node:test';
import { retainedSourceLinks } from '../src/features/landscape/retained-source-links.ts';

const link = (url, extra = {}) => ({ url, label: 'Authored publisher label', kind: 'Publisher link', ...extra });

test('retained links preserve the exact original URL, authored label and unresolved kind without mutation', () => {
  const original = Object.freeze(link('HTTPS://News.Google.com:443/rss/articles/opaque?utm_source=pilot&x=%2f#retained',
    { label: 'news.google.com', kind: 'Index link · publisher URL unresolved', private_body: 'Must not be projected' }));
  const source = Object.freeze([original]);
  const result = retainedSourceLinks(source);
  assert.deepEqual(result, [{ url: original.url, label: original.label, kind: original.kind }]);
  assert.equal(result[0].url, original.url); assert.notEqual(result[0], original);
  assert.equal(original.private_body, 'Must not be projected');
});

test('missing and malformed optional metadata is ignored while valid entries retain server order', () => {
  for (const value of [undefined, null, {}, 'not a list']) assert.deepEqual(retainedSourceLinks(value), []);
  const first = link('https://first.example/article'), second = link('https://second.example/article');
  const malformed = [null, [], {}, { ...first, url: 7 }, { ...first, label: null }, { ...first, kind: false }, { ...first, label: ' ' }];
  assert.deepEqual(retainedSourceLinks([first, ...malformed, second]), [first, second]);
});

test('unsafe protocols, credentials, local hosts and nonpublic literal addresses cannot become external links', () => {
  const unsafe = ['javascript:alert(1)', 'data:text/html,unsafe', '//publisher.example/article', '/relative',
    'https://user:secret@publisher.example/article', 'https://localhost./a', 'http://127.0.0.1/a', 'http://2130706433/a',
    'http://10.1.2.3/a', 'https://192.168.1.1/a', 'http://172.31.1.1/a', 'http://169.254.169.254/a',
    'https://publisher.internal/a', 'http://[::1]/a', 'http://[::ffff:127.0.0.1]/a', 'http://[fe80::1]/a', 'http://[fd00::1]/a',
    'https://publisher.example/\nunsafe', 'https://publisher.example/\\unsafe', 'http://[', 'https://publisher.example/' + 'x'.repeat(4096)];
  assert.deepEqual(retainedSourceLinks(unsafe.map(url => link(url))), []);
  assert.deepEqual(retainedSourceLinks([link('https://8.8.8.8/article'), link('https://[2606:4700:4700::1111]/article')]).length, 2);
});

test('retained links are capped at sixteen without reordering or deduplicating authored metadata', () => {
  const source = Object.freeze(Array.from({ length: 20 }, (_, i) => Object.freeze(link(`https://publisher.example/${i}`))));
  assert.deepEqual(retainedSourceLinks(source), source.slice(0, 16));
  assert.equal(source.length, 20);
  assert.equal(retainedSourceLinks([source[0], source[0]]).length, 2, 'Server deduplication is not replaced with a different client policy');
});
