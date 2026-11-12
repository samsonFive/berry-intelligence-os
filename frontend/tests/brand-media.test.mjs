import assert from 'node:assert/strict';
import test from 'node:test';
import { InvestigationApiError } from '../src/api/client.ts';
import { getBrandMedia, mediaEntityIds, mediaImageUrl, mediaInspectionUrl, parseBrandMedia, publicMediaLink } from '../src/features/brand-media/api.ts';

// Deterministic API fixtures only. No source URLs in this file are fetched.
const key = `asset-${'a'.repeat(24)}`;
const image = { id: key, entity_id: 'company-fixture', kind: 'pack_image', kind_label: 'Packaging image',
  caption: 'Synthetic packaging fixture', image_url: `https://example.org/unit-test/image.png`, attribution: 'Fixture credit',
  source_page_url: 'https://example.org/unit-test/product', historical_status: 'date_unknown', source_kind: 'official' };
function row(id = 'company-fixture', type = 'company') {
  return { entity_id: id, entity_type: type, logo: null, packaging: [{ ...image, entity_id: id }], observations: [], social_images: [], official_images: [] };
}
function payload() { return { version: 1, entities: { 'company-fixture': row() } }; }
function response(value = payload()) { return new Response(JSON.stringify(value), { headers: { 'content-type': 'application/json' } }); }

test('media requests contain only bounded explicit IDs, same-origin credentials, no-store and cancellation', async () => {
  const original = globalThis.fetch;
  const controller = new AbortController(); let captured;
  globalThis.fetch = async (url, options) => { captured = { url, options }; return response(); };
  try {
    const result = await getBrandMedia(['company-fixture', 'company-fixture'], controller.signal);
    assert.equal(captured.url, '/api/brand-media/entities?ids=company-fixture');
    assert.equal(captured.options.credentials, 'same-origin'); assert.equal(captured.options.cache, 'no-store');
    assert.equal(captured.options.signal, controller.signal); assert.equal(captured.options.headers.Accept, 'application/json');
    assert.equal(result.entities['company-fixture'].packaging[0].kind, 'pack_image');
  } finally { globalThis.fetch = original; }
});

test('invalid or excessive organization selectors fail before any request', async () => {
  const original = globalThis.fetch; let requests = 0;
  globalThis.fetch = async () => { requests++; return response(); };
  try {
    for (const ids of [[], ['company-a?next=private'], ['https://external.invalid'], Array.from({ length: 21 }, (_, index) => `company-${index}`)])
      await assert.rejects(getBrandMedia(ids), error => error instanceof InvestigationApiError && error.status === 400);
    assert.equal(requests, 0);
    assert.deepEqual(mediaEntityIds(['company-b', 'brand-a', 'company-b']), ['company-b', 'brand-a']);
  } finally { globalThis.fetch = original; }
});

test('login redirects and both authorization statuses trigger the shared private-session error contract', async () => {
  const original = globalThis.fetch;
  try {
    for (const answer of [{ redirected: true, status: 200 }, { redirected: false, status: 401 }, { redirected: false, status: 403 }]) {
      globalThis.fetch = async () => answer;
      await assert.rejects(getBrandMedia(['company-fixture']), error => error instanceof InvestigationApiError && error.requiresSession);
    }
  } finally { globalThis.fetch = original; }
});

test('outages, absent adapters and non-JSON pages never become cached image payloads', async () => {
  const original = globalThis.fetch;
  try {
    for (const answer of [new Response('upstream diagnostic never shown', { status: 503 }), new Response('missing', { status: 404 }), new Response('<html>login</html>', { headers: { 'content-type': 'text/html' } })]) {
      globalThis.fetch = async () => answer;
      await assert.rejects(getBrandMedia(['company-fixture']), error => error instanceof InvestigationApiError && !error.message.includes('diagnostic'));
    }
  } finally { globalThis.fetch = original; }
});

test('curated image parsing drops raw policy, object storage and analyst state instead of retaining a parallel model', () => {
  const value = payload();
  Object.assign(value.entities['company-fixture'].packaging[0], { policy: { display: true }, object_ref: 'private-object', raw_response: 'private source text', rejected: false, original_image_url: 'https://example.org/raw' });
  const parsed = parseBrandMedia(value, ['company-fixture']).entities['company-fixture'].packaging[0];
  assert.equal(parsed.attribution, 'Fixture credit');
  for (const field of ['policy', 'object_ref', 'raw_response', 'rejected', 'original_image_url']) assert.equal(field in parsed, false);
});

test('brand and retailer types and official, consumer and social groups remain distinct without caption inference', () => {
  const brand = row('brand-fixture', 'brand'); const retailer = row('retailer-fixture', 'retailer');
  brand.packaging = [];
  brand.official_images = [{ ...image, entity_id: 'brand-fixture', kind: 'unclassified', caption: 'Caption mentions packaging and a cultivar; image remains unclassified' }];
  retailer.packaging = []; retailer.observations = [{ ...image, entity_id: 'retailer-fixture', source_kind: 'retailer', kind: 'shelf_observation' }];
  const parsed = parseBrandMedia({ version: 1, entities: { 'brand-fixture': brand, 'retailer-fixture': retailer } }, ['brand-fixture', 'retailer-fixture']);
  assert.equal(parsed.entities['brand-fixture'].entity_type, 'brand'); assert.equal(parsed.entities['retailer-fixture'].entity_type, 'retailer');
  assert.equal(parsed.entities['brand-fixture'].packaging.length, 0); assert.equal(parsed.entities['brand-fixture'].official_images[0].kind, 'unclassified');
  assert.equal(parsed.entities['retailer-fixture'].observations[0].source_kind, 'retailer');
  assert.equal('cultivar' in parsed.entities['brand-fixture'].official_images[0], false);
});

test('foreign response identities and incompatible versions are rejected; foreign asset matches are omitted', () => {
  assert.throws(() => parseBrandMedia({ version: 2, entities: {} }, ['company-fixture']), InvestigationApiError);
  assert.throws(() => parseBrandMedia({ version: 1, entities: { 'company-other': row('company-other') } }, ['company-fixture']), InvestigationApiError);
  const value = payload(); value.entities['company-fixture'].packaging[0].entity_id = 'brand-other';
  assert.deepEqual(parseBrandMedia(value, ['company-fixture']).entities['company-fixture'].packaging, []);
});

test('only explicit HTTPS images or the precise authenticated local image route can render', () => {
  for (const value of ['javascript:alert(1)', 'data:image/svg+xml,unsafe', '//other.example/image', '/private/file',
    'https://user:secret@example.org/image', 'http://example.org/image', 'https://127.0.0.1/image',
    'https://metadata.google.internal/image', 'https://example.org:8443/image', 'https://example.org\\@attacker.example/image']) {
    assert.equal(mediaImageUrl(value), undefined); assert.equal(publicMediaLink(value), undefined);
  }
  assert.equal(mediaImageUrl(`/api/brand-media/${key}/image`), `/api/brand-media/${key}/image`);
  assert.equal(mediaImageUrl('https://example.org/image.png'), 'https://example.org/image.png');
  const value = payload(); value.entities['company-fixture'].packaging[0].image_url = 'javascript:alert(1)';
  assert.deepEqual(parseBrandMedia(value, ['company-fixture']).entities['company-fixture'].packaging, []);
});

test('retained-source inspection accepts only the existing metadata-only reader path', () => {
  const href = `/api/social/ev-social-${'b'.repeat(24)}/reader?media=metadata-only`;
  assert.equal(mediaInspectionUrl(href), href);
  for (const value of ['https://other.example/reader', '/api/social/private/reader', href+'&mode=live', '/api/social/ev-social-'+'b'.repeat(24)+'/reader'])
    assert.equal(mediaInspectionUrl(value), undefined);
});

test('image matte defaults to light without changing image identity, kind or provenance', () => {
  const parsed = parseBrandMedia(payload(), ['company-fixture']).entities['company-fixture'].packaging[0];
  assert.equal(parsed.background, 'light');
  for (const field of ['id', 'entity_id', 'kind', 'kind_label', 'image_url', 'caption', 'attribution', 'source_page_url', 'source_kind'])
    assert.equal(parsed[field], image[field]);
});

test('explicit dark matte is accepted for typed brand logos and all image groups', () => {
  const brand = row('brand-fixture', 'brand');
  const logo = { ...image, entity_id: 'brand-fixture', kind: 'logo', kind_label: 'Actual logo', background: 'dark' };
  const dark = { ...image, entity_id: 'brand-fixture', background: 'dark' };
  Object.assign(brand, { logo, packaging: [dark], observations: [dark], social_images: [dark], official_images: [dark] });
  const parsed = parseBrandMedia({ version: 1, entities: { 'brand-fixture': brand } }, ['brand-fixture']).entities['brand-fixture'];
  assert.equal(parsed.entity_type, 'brand');
  assert.equal(parsed.logo.kind, 'logo'); assert.equal(parsed.logo.background, 'dark');
  for (const field of ['packaging', 'observations', 'social_images', 'official_images']) {
    assert.equal(parsed[field][0].background, 'dark');
    assert.equal(parsed[field][0].image_url, image.image_url);
    assert.equal(parsed[field][0].kind, image.kind);
    assert.equal(parsed[field][0].attribution, image.attribution);
  }
});

test('unknown matte values never become arbitrary CSS or a different enum', () => {
  for (const background of ['light', '', 'DARK', 'dark extra-class', '#000', 'url(https://example.org/image)',
    'dark; background:red', null, false, 1, { dark: true }, ['dark']]) {
    const value = payload(); value.entities['company-fixture'].packaging[0].background = background;
    const parsed = parseBrandMedia(value, ['company-fixture']).entities['company-fixture'].packaging[0];
    assert.equal(parsed.background, 'light');
    assert.equal(parsed.image_url, image.image_url);
  }
});
