"""Offline route checks with synthetic pixels; no provider/network requests."""
import base64
from datetime import UTC, datetime, timedelta

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from app import brand_media_routes as routes
from app.services import brand_media as media
from tests.test_brand_media import ENTITIES, PNG, upload_metadata, policy, source_row, seed


@pytest.fixture
def client(tmp_path, monkeypatch):
    from app import main
    monkeypatch.setattr(main, 'INBOX_DIR', tmp_path)
    monkeypatch.setattr(main, 'AUTHORING_MODE', True)
    monkeypatch.setattr(main, 'all_entities', lambda: list(ENTITIES.values()))
    monkeypatch.setattr(media, 'stamp', lambda: datetime(2026, 11, 11, 12, tzinfo=UTC))
    app = FastAPI()
    app.include_router(routes.router)
    from app.social_routes import router as social_router
    app.include_router(social_router)
    return TestClient(app)


def upload(client, **changes):
    return client.post('/api/brand-media/upload', json={'metadata': upload_metadata(**changes),
        'content_base64': base64.b64encode(PNG).decode()}, headers={'Origin': 'http://testserver'})


def test_image_and_export_enforce_policy_while_returning_permitted_raster(client, tmp_path):
    response = upload(client)
    assert response.status_code == 200, response.text
    key = response.json()['asset_id']
    image = client.get(f'/api/brand-media/{key}/image')
    assert image.status_code == 200 and image.content == PNG
    assert image.headers['content-type'] == 'image/png'
    assert image.headers['cache-control'] == 'private, no-store'
    assert image.headers['x-content-type-options'] == 'nosniff'
    assert client.get('/api/brand-media?export=true').json()['assets'] == []
    media.decide(tmp_path, key, {'policy': policy(export=True)}, reviewer='Synthetic reviewer')
    assert [r['id'] for r in client.get('/api/brand-media?export=true').json()['assets']] == [key]
    media.decide(tmp_path, key, {'policy': policy(display=False)}, reviewer='Synthetic reviewer')
    assert client.get(f'/api/brand-media/{key}/image').status_code == 410
    assert client.get('/api/brand-media').json()['assets'][0]['image_url'] is None
    assert client.get('/api/brand-media/not-an-asset/image').status_code == 410


def test_mutations_require_origin_validate_payload_and_preserve_repeat_upload(client):
    payload = {'metadata': upload_metadata(), 'content_base64': base64.b64encode(PNG).decode()}
    assert client.post('/api/brand-media/upload', json=payload).status_code == 403
    assert client.post('/api/brand-media/upload', json=payload, headers={'Origin': 'https://evil.example'}).status_code == 403
    first = upload(client); second = upload(client)
    assert first.status_code == second.status_code == 200 and first.json() == second.json()
    headers = {'Origin': 'http://testserver'}
    assert client.post('/api/brand-media/upload', json={'metadata': {}, 'content_base64': 'invalid!'}, headers=headers).status_code == 422
    key = first.json()['asset_id']
    assert client.post(f'/api/brand-media/{key}/decision', json={'reviewer': 'Synthetic reviewer', 'changes': {'cultivar_id': 'variety-test'}}, headers=headers).status_code == 422
    assert client.post(f'/api/brand-media/{key}/decision', json={'reviewer': 'Synthetic reviewer', 'changes': {'rejected': True}}, headers=headers).status_code == 200
    assert client.get(f'/api/brand-media/{key}/image').status_code == 410


def test_upload_accepts_advertised_two_megabyte_raster_and_rejects_oversize(client):
    data = PNG + b'\0' * (2*1024*1024-len(PNG))
    payload = {'metadata': upload_metadata(), 'content_base64': base64.b64encode(data).decode()}
    headers = {'Origin': 'http://testserver'}
    response = client.post('/api/brand-media/upload', json=payload, headers=headers)
    assert response.status_code == 200, response.text
    payload['content_base64'] = base64.b64encode(data+b'!').decode()
    assert client.post('/api/brand-media/upload', json=payload, headers=headers).status_code == 422
    assert upload(client, policy=policy(cache=False)).status_code == 422


@pytest.mark.parametrize('url', ['/api/brand-media', '/api/brand-media/entities?ids=company-test',
                                 '/api/brand-media/asset-000000000000000000000000/image', '/media-review'])
def test_media_routes_are_private_authoring_only(client, monkeypatch, url):
    from app import main
    monkeypatch.setattr(main, 'AUTHORING_MODE', False)
    assert client.get(url).status_code == 404


def test_routes_join_existing_remote_session_protection(tmp_path, monkeypatch):
    from app import main
    from tests.test_remote_auth import _enable_remote
    monkeypatch.setattr(main, 'INBOX_DIR', tmp_path)
    monkeypatch.setattr(main, 'AUTHORING_MODE', True)
    _enable_remote(monkeypatch)
    remote = TestClient(main.app, follow_redirects=False)
    assert remote.get('/api/brand-media').status_code == 302
    assert remote.get('/api/brand-media/entities?ids=company-test').status_code == 302
    assert remote.get('/api/brand-media/asset-000000000000000000000000/image').status_code == 302
    assert remote.post('/api/brand-media/upload', json={}).status_code == 302


def test_metadata_only_social_source_reader_suppresses_images_players_and_expired_posts(client, tmp_path):
    row = source_row(native='123456789', count=2)
    row.update(source='linkedin', canonical_url='https://www.linkedin.com/posts/test_activity-123456789-test',
               source_embed_urn='urn:li:activity:123456789', collected_at=datetime.now(UTC).isoformat())
    store, key = seed(tmp_path, row)
    reader = client.get(f'/api/social/{key}/reader?media=metadata-only')
    assert reader.status_code == 200, reader.text
    assert row['text'] in reader.text
    assert 'example.org/test-media/' not in reader.text and '<iframe' not in reader.text
    normal = client.get(f'/api/social/{key}/reader')
    assert normal.status_code == 200 and '<iframe' in normal.text
    old = source_row(native='expired-source')
    old['collected_at'] = (datetime.now(UTC)-timedelta(days=31)).isoformat()
    _, old_id = seed(tmp_path, old)
    assert client.get(f'/api/social/{old_id}/reader?media=metadata-only').status_code == 410


def test_default_company_profile_uses_authorized_shared_logo(tmp_path, monkeypatch):
    from app import main
    from lxml import html
    monkeypatch.setattr(main, 'INBOX_DIR', tmp_path)
    monkeypatch.setattr(main, 'AUTHORING_MODE', True)
    monkeypatch.setattr(media, 'stamp', lambda: datetime(2026, 11, 11, 12, tzinfo=UTC))
    entity = next(e for e in main.all_entities() if e['id'] == 'company-driscolls')
    asset = media.authorized_upload(tmp_path,
        upload_metadata(entity_id=entity['id'], kind='logo', caption='Synthetic test logo; not actual Driscoll branding'),
        PNG, entities={entity['id']: entity})
    response = TestClient(main.app).get('/entities/company/company-driscolls')
    assert response.status_code == 200, response.text[:500]
    document = html.fromstring(response.text)
    assert document.xpath(f'//header[contains(@class,"company-profile-heading")]//img[@src="/api/brand-media/{asset["id"]}/image"]')
    assert not document.xpath('//section[@id="company-driscolls-packaging"]')


def test_curated_entity_api_preserves_entity_types_and_limits_private_projection(client, tmp_path):
    logo = media.authorized_upload(tmp_path, upload_metadata(kind='logo', attribution='Visible synthetic logo credit'), PNG, entities=ENTITIES)
    media.authorized_upload(tmp_path, upload_metadata(entity_id='brand-test', source_page_url='https://example.org/brand-product'), PNG, entities=ENTITIES)
    media.authorized_upload(tmp_path, upload_metadata(entity_id='retailer-test', source_kind='retailer'), PNG, entities=ENTITIES)
    held = media.authorized_upload(tmp_path, upload_metadata(kind='pack_photo'), PNG+b'held', entities=ENTITIES)
    media.decide(tmp_path, held['id'], {'rejected': True}, reviewer='Synthetic reviewer')
    response = client.get('/api/brand-media/entities?ids=company-test,brand-test,retailer-test')
    assert response.status_code == 200, response.text
    assert response.headers['cache-control'] == 'private, no-store' and response.headers['x-robots-tag'] == 'noindex'
    payload = response.json()
    assert payload['version'] == 1
    entities = payload['entities']
    assert {key: value['entity_type'] for key, value in entities.items()} == {
        'company-test': 'company', 'brand-test': 'brand', 'retailer-test': 'retailer'}
    assert entities['company-test']['logo']['id'] == logo['id']
    assert entities['company-test']['logo']['attribution'] == 'Visible synthetic logo credit'
    assert entities['company-test']['packaging'] == []  # Rejected assets never escape in the curated seam.
    assert entities['brand-test']['packaging'][0]['entity_id'] == 'brand-test'
    assert entities['retailer-test']['observations'][0]['source_kind'] == 'retailer'
    forbidden = {'original_image_url', 'object_ref', 'policy', 'rejected', 'analyst_selected', 'blockers',
                 'origin', 'updated_at', 'evidence_ids', 'retail_observation_ids', 'display_eligible', 'export_eligible'}
    def check(value):
        if isinstance(value, dict):
            assert not forbidden.intersection(value)
            for nested in value.values(): check(nested)
        elif isinstance(value, list):
            for nested in value: check(nested)
    check(payload)


@pytest.mark.parametrize('ids', ['', 'unknown-company', 'company-test,unknown-company', 'variety-test'])
def test_curated_entity_api_rejects_implicit_unknown_and_nonorganization_scope(client, ids):
    assert client.get('/api/brand-media/entities', params={'ids': ids}).status_code == 422


def test_curated_entity_api_requires_explicit_scope_of_at_most_twenty_existing_ids(client, monkeypatch):
    from app import main
    entities = [{'id': f'company-limit-{i}', 'entity_type': 'company', 'name': f'Synthetic company {i}'} for i in range(21)]
    monkeypatch.setattr(main, 'all_entities', lambda: entities)
    assert client.get('/api/brand-media/entities').status_code == 422
    ids = ','.join(e['id'] for e in entities)
    assert client.get('/api/brand-media/entities', params={'ids': ids}).status_code == 422
    response = client.get('/api/brand-media/entities', params={'ids': ','.join(e['id'] for e in entities[:20])})
    assert response.status_code == 200 and len(response.json()['entities']) == 20


def test_directory_shared_logo_credit_and_override_priority_render_without_source_requests(client, tmp_path, monkeypatch):
    from app import main
    from app.services import company_directory
    from app.services.entity_logo_overrides import set_logo_upload
    from lxml import html
    import httpx
    import requests

    monkeypatch.setattr(main, 'living_catalog', lambda: [{**e, 'status': 'active'} for e in ENTITIES.values()])
    monkeypatch.setattr(company_directory.seed_roster, 'build_roster', lambda existing: [])
    media.authorized_upload(tmp_path, upload_metadata(kind='logo', attribution='Required synthetic logo credit'), PNG, entities=ENTITIES)
    shared = media.load(tmp_path)
    key = next(iter(shared))
    calls = []
    original = media.entity_media
    def counted(inbox, entities, **kwargs):
        calls.append(list(entities))
        return original(inbox, entities, **kwargs)
    monkeypatch.setattr(media, 'entity_media', counted)
    def no_network(*args, **kwargs):
        raise AssertionError('Rendering must never request a source or media provider')
    monkeypatch.setattr(httpx.HTTPTransport, 'handle_request', no_network)
    monkeypatch.setattr(requests.adapters.HTTPAdapter, 'send', no_network)
    app_client = TestClient(main.app)
    response = app_client.get('/entities/company')
    assert response.status_code == 200, response.text[:500]
    row = html.fromstring(response.text).get_element_by_id('organization-company-test')
    assert row.xpath(f'.//img[@src="/api/brand-media/{key}/image"]')
    assert row.xpath('.//small[contains(@class,"brand-media-credit") and text()="Required synthetic logo credit"]')
    assert len(calls) == 1
    override = set_logo_upload(tmp_path, 'company-test', PNG+b'analyst-override')
    response = app_client.get('/entities/company')
    row = html.fromstring(response.text).get_element_by_id('organization-company-test')
    assert row.xpath(f'.//img[@src="{override["url"]}"]')
    assert not row.xpath('.//small[contains(@class,"brand-media-credit")]')
    assert len(calls) == 2  # One bounded shared-media read for each directory request.


def test_curated_api_returns_white_wordmark_matte_without_rewriting_source_or_policy(client, tmp_path, monkeypatch):
    import hashlib
    import json
    import httpx
    import requests

    image_url = 'https://example.org/brand/white-wordmark.svg?version=2&variant=original'
    page_url = 'https://example.org/brand'
    key = 'asset-' + hashlib.sha256(f'official:company-test:{page_url}:{image_url}'.encode()).hexdigest()[:24]
    row = media.Asset(id=key, entity_id='company-test', origin='official_reference',
        original_image_url=image_url, source_page_url=page_url, source_kind='official', kind='logo',
        background='dark', match_status='matched', match_basis='Synthetic official-brand test identity',
        classification_basis='Synthetic white wordmark reference; no real branding claim',
        attribution='Synthetic brand credit', policy=media.Policy(reference_display_requested=True),
        updated_at=datetime(2026, 11, 11, 12, tzinfo=UTC)).model_dump(mode='json')
    path = media.index_path(tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({'version': media.VERSION, 'assets': {key: row}}), encoding='utf-8')
    before = path.read_bytes()

    def no_network(*args, **kwargs):
        raise AssertionError('The curated projection must never fetch or alter source image bytes')
    monkeypatch.setattr(httpx.HTTPTransport, 'handle_request', no_network)
    monkeypatch.setattr(requests.adapters.HTTPAdapter, 'send', no_network)

    response = client.get('/api/brand-media/entities?ids=company-test')
    assert response.status_code == 200
    logo = response.json()['entities']['company-test']['logo']
    assert logo['background'] == 'dark'
    assert logo['image_url'] == image_url and logo['source_page_url'] == page_url
    assert logo['attribution'] == 'Synthetic brand credit'
    assert 'policy' not in logo and 'object_ref' not in logo
    assert path.read_bytes() == before
    assert row['policy']['display'] is False and row['policy']['cache'] is False and row['policy']['export'] is False


def test_retained_refresh_reads_the_deployed_seed_configuration_layout(client, tmp_path, monkeypatch):
    import json
    image_root = tmp_path / 'image'
    directory = image_root / 'seed/data/configuration'
    directory.mkdir(parents=True)
    (directory / 'brand_media_accounts.json').write_text(json.dumps({'accounts': []}), encoding='utf-8')
    monkeypatch.setattr(routes, 'ROOT', image_root)
    called = []
    def reuse(inbox, entities, *, accounts, entity_ids):
        called.append((accounts, entity_ids))
        return {'created': 0}
    monkeypatch.setattr(media, 'reuse_social', reuse)
    response = client.post('/api/brand-media/reuse', json={'entity_id': 'company-test'}, headers={'Origin': 'http://testserver'})
    assert response.status_code == 200, response.text
    assert called == [([], ['company-test'])]
