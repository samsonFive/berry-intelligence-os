"""Synthetic offline checks of explicitly requested reference display.

No URL in this module is fetched. These fixtures do not demonstrate real source
availability, licensing, or packaging photography.
"""
from datetime import timedelta
import hashlib
import json
import sqlite3

import pytest

from app.services import brand_media as media
from tests.test_brand_media import ACCOUNTS, ENTITIES, NOW, seed, source_row
from tests.test_brand_media_routes import client


REFERENCE = 'https://scontent-test.xx.fbcdn.net/v/test-only-photo.jpg?synthetic=fixture'


def reference_asset(inbox):
    row = source_row(count=1)
    row['media'][0]['source_url'] = REFERENCE
    store, observation_id = seed(inbox, row)
    media.reuse_social(inbox, ENTITIES, accounts=ACCOUNTS, now=NOW)
    key = next(iter(media.load(inbox)))
    return store, observation_id, key


def request_display(inbox, key):
    policy = media.load(inbox)[key]['policy']
    policy['reference_display_requested'] = True
    return media.decide(inbox, key, {'policy': policy}, reviewer='Synthetic operator request')


def update_source(store, key, change):
    with sqlite3.connect(store.path) as db:
        row = json.loads(db.execute('SELECT payload FROM observations WHERE id=?', (key,)).fetchone()[0])
        change(row)
        db.execute('UPDATE observations SET payload=? WHERE id=?', (json.dumps(row), key))


def test_explicit_request_enables_reference_without_license_storage_or_export_grant(tmp_path, monkeypatch):
    store, observation_id, key = reference_asset(tmp_path)
    assert not media.inventory(tmp_path, now=NOW)[0]['display_eligible']
    before = media.load(tmp_path)[key]
    selected = request_display(tmp_path, key)
    row = media.inventory(tmp_path, now=NOW)[0]
    assert row['display_eligible'] and row['image_url'] == REFERENCE
    assert row['image_delivery'] == 'reference'
    assert row['display_basis'] == 'operator_requested_reference' and row['policy_status'] == 'unresolved'
    assert row['kind'] == 'unclassified' and row['kind_label'] == 'Post image'
    assert not row['export_eligible'] and row['object_ref'] is None
    assert selected['policy'] == {**before['policy'], 'reference_display_requested': True}
    assert not any(selected['policy'][name] for name in ('display', 'cache', 'export'))
    assert selected['policy']['source_url'] is None and selected['policy']['checked_at'] is None
    assert not (tmp_path/'social'/'media').exists() and not (tmp_path/'brand_media'/'objects').exists()
    # A reference never becomes a server-side fetch/proxy through the local image route.
    with pytest.raises(ValueError):
        media.image_file(tmp_path, key, now=NOW)


def test_unclassified_official_post_stays_social_imagery_and_rerun_preserves_request(tmp_path):
    _, _, key = reference_asset(tmp_path)
    request_display(tmp_path, key)
    model = media.entity_media(tmp_path, ['company-test'], now=NOW)['company-test']
    assert model['logo'] is None and model['packaging'] == [] and model['observations'] == []
    assert [r['id'] for r in model['social_images']] == [key]
    assert model['social_images'][0]['source_kind'] == 'official'
    assert model['social_images'][0]['published_at'] != model['social_images'][0]['updated_at']
    assert media.reuse_social(tmp_path, ENTITIES, accounts=ACCOUNTS, now=NOW)['created'] == 0
    assert media.load(tmp_path)[key]['policy']['reference_display_requested']


@pytest.mark.parametrize('hold', ['unmatched', 'rejected', 'policy_expired', 'source_expired',
                                'unavailable', 'restricted', 'source_deleted', 'media_tombstone', 'url_tombstone'])
def test_reference_request_never_overrides_identity_rejection_retention_or_source_holds(tmp_path, hold):
    store, observation_id, key = reference_asset(tmp_path)
    request_display(tmp_path, key)
    if hold == 'unmatched':
        media.decide(tmp_path, key, {'match_status': 'review_needed'}, reviewer='Synthetic reviewer')
    elif hold == 'rejected':
        media.decide(tmp_path, key, {'rejected': True}, reviewer='Synthetic reviewer')
    elif hold == 'policy_expired':
        policy = media.load(tmp_path)[key]['policy']; policy['expires_at'] = (NOW-timedelta(seconds=1)).isoformat()
        media.decide(tmp_path, key, {'policy': policy}, reviewer='Synthetic reviewer')
    elif hold == 'source_expired':
        update_source(store, observation_id, lambda r: r.update(collected_at=(NOW-timedelta(days=31)).isoformat()))
    elif hold in {'unavailable', 'restricted'}:
        store.remove(observation_id, media_id='unit-post-image-0', state=hold)
    elif hold == 'source_deleted':
        store.remove(observation_id, state='deleted')
    else:
        with sqlite3.connect(store.path) as db:
            if hold == 'media_tombstone':
                db.execute('INSERT INTO media_tombstones VALUES(?,?,?)', (observation_id, 'unit-post-image-0', 'restricted'))
            else:
                digest = hashlib.sha256(media.media_reference_key('facebook', REFERENCE).encode()).hexdigest()
                db.execute('INSERT INTO media_url_tombstones VALUES(?,?,?)', (observation_id, digest, 'unavailable'))
    rows = media.inventory(tmp_path, now=NOW)
    assert len(rows) == 1 and not rows[0]['display_eligible'] and rows[0]['image_url'] is None
    assert not rows[0]['export_eligible'] and rows[0]['blockers']
    model = media.entity_media(tmp_path, ['company-test'], now=NOW)['company-test']
    assert model['social_images'] == [] and model['packaging'] == []


@pytest.mark.parametrize('url', [
    'http://scontent-test.xx.fbcdn.net/photo.jpg', 'https://127.0.0.1/photo.jpg',
    'https://metadata.google.internal/photo.jpg', 'https://evil.fbcdn.net.example.org/photo.jpg',
    'https://fbcdn.net@attacker.example/photo.jpg', 'https://scontent-test.xx.fbcdn.net:8443/photo.jpg',
    'https://scontent-test.xx.fbcdn.net\\@evil.example/photo.jpg', 'https://example.org/test-media/image.jpg',
    'https://pbs.twimg.com/media/test.jpg', 'data:image/png;base64,invalid', 'javascript:alert(1)',
])
def test_unsafe_wrong_platform_or_noncdn_retained_reference_stays_held(tmp_path, url):
    store, observation_id, key = reference_asset(tmp_path)
    request_display(tmp_path, key)
    update_source(store, observation_id, lambda r: r['media'][0].update(source_url=url))
    assert media.retained_image_reference('facebook', url) is None
    row = media.inventory(tmp_path, now=NOW)[0]
    assert not row['display_eligible'] and row['image_url'] is None


def test_explicit_reference_request_does_not_relax_packaging_classification(tmp_path):
    _, _, key = reference_asset(tmp_path)
    request_display(tmp_path, key)
    media.decide(tmp_path, key, {'kind': 'pack_photo'}, reviewer='Synthetic reviewer')
    row = media.inventory(tmp_path, now=NOW)[0]
    assert not row['display_eligible'] and 'Image classification needs inspection' in row['blockers']


def test_reference_delivery_cannot_be_exported_even_if_raw_export_flag_was_set(tmp_path):
    _, _, key = reference_asset(tmp_path)
    request_display(tmp_path, key)
    policy = media.load(tmp_path)[key]['policy']; policy['export'] = True
    media.decide(tmp_path, key, {'policy': policy}, reviewer='Synthetic reviewer')
    row = media.inventory(tmp_path, now=NOW)[0]
    assert row['display_eligible'] and row['image_delivery'] == 'reference' and not row['export_eligible']


def official_asset(inbox, image_url='https://www.example.org/test-image.png'):
    media.register_discovery(inbox, 'company-test', [{
        'original_image_url': image_url, 'source_page_url': 'https://www.example.org/official-product-page',
        'asset_type': 'product_image', 'entity_name_match': 'exact', 'declared_subject_name': 'Synthetic Berry Company',
        'source_locator': 'Synthetic test product gallery'}], entities=ENTITIES)
    key = next(k for k, value in media.load(inbox).items() if value['origin'] == 'official_reference')
    media.decide(inbox, key, {'match_status': 'matched', 'match_basis': 'Explicit synthetic official-page identity review'},
                 reviewer='Synthetic reviewer')
    return key


@pytest.mark.parametrize('url', ['https://www.example.org/test-image.png',
                                 'https://images.example.org/test-image.png',
                                 'https://edge.sitecorecloud.io/synthetic/test-image.png'])
def test_explicit_official_reference_display_allows_same_site_subdomain_and_exact_cdn(tmp_path, url):
    key = official_asset(tmp_path, url)
    assert not media.inventory(tmp_path, now=NOW)[0]['display_eligible']
    request_display(tmp_path, key)
    row = media.inventory(tmp_path, now=NOW)[0]
    assert row['display_eligible'] and row['image_url'] == url and row['image_delivery'] == 'reference'
    assert row['kind'] == 'unclassified' and row['kind_label'] == 'Official image'
    assert row['policy_status'] == 'unresolved' and not row['export_eligible']
    assert not any(row['policy'][flag] for flag in ('display', 'cache', 'export'))
    assert row['object_ref'] is None and row.get('published_at') is None
    model = media.entity_media(tmp_path, ['company-test'], now=NOW)['company-test']
    assert [r['id'] for r in model['official_images']] == [key]
    assert model['social_images'] == [] and model['packaging'] == []
    assert not (tmp_path/'brand_media'/'objects').exists()
    with pytest.raises(ValueError):
        media.image_file(tmp_path, key, now=NOW)


@pytest.mark.parametrize('url', ['https://other.example.net/image.png',
    'https://edge.sitecorecloud.io.attacker.example/image.png', 'https://evil.edge.sitecorecloud.io/image.png',
    'https://www.example.org.attacker.example/image.png', 'http://www.example.org/image.png',
    'https://127.0.0.1/image.png', 'https://metadata.google.internal/image.png',
    'https://www.example.org:8443/image.png', 'https://www.example.org\\@attacker.example/image.png',
    'javascript:alert(1)', 'data:image/png;base64,invalid'])
def test_official_reference_offsite_and_unsafe_destinations_remain_held(tmp_path, url):
    key = official_asset(tmp_path)
    request_display(tmp_path, key)
    raw = media.load(tmp_path)[key]
    raw['original_image_url'] = url
    assert media.official_image_reference(url, raw['source_page_url']) is None
    row = media.inspect_asset(raw, {}, now=NOW)
    assert not row['display_eligible'] and row['image_url'] is None


@pytest.mark.parametrize('hold', ['default_request_false', 'unmatched', 'rejected', 'expired'])
def test_official_reference_request_never_overrides_other_gates(tmp_path, hold):
    key = official_asset(tmp_path)
    if hold != 'default_request_false': request_display(tmp_path, key)
    if hold == 'unmatched':
        media.decide(tmp_path, key, {'match_status': 'review_needed'}, reviewer='Synthetic reviewer')
    elif hold == 'rejected':
        media.decide(tmp_path, key, {'rejected': True}, reviewer='Synthetic reviewer')
    elif hold == 'expired':
        policy = media.load(tmp_path)[key]['policy']; policy['expires_at'] = (NOW-timedelta(seconds=1)).isoformat()
        media.decide(tmp_path, key, {'policy': policy}, reviewer='Synthetic reviewer')
    row = media.inventory(tmp_path, now=NOW)[0]
    assert not row['display_eligible'] and row['image_url'] is None
    assert media.entity_media(tmp_path, ['company-test'], now=NOW)['company-test']['official_images'] == []


@pytest.mark.parametrize('kind', ['pack_photo', 'pack_image'])
def test_official_reference_requires_explicit_packaging_inspection_before_pack_gallery(tmp_path, kind):
    key = official_asset(tmp_path)
    request_display(tmp_path, key)
    media.decide(tmp_path, key, {'kind': kind}, reviewer='Synthetic reviewer')
    assert not media.inventory(tmp_path, now=NOW)[0]['display_eligible']
    media.decide(tmp_path, key, {'classification_basis': 'Synthetic test analyst explicitly inspected a test package'},
                 reviewer='Synthetic reviewer')
    model = media.entity_media(tmp_path, ['company-test'], now=NOW)['company-test']
    assert [r['id'] for r in model['packaging']] == [key] and model['official_images'] == []


def test_curated_api_separates_official_and_social_reference_groups(client, tmp_path):
    _, _, social_key = reference_asset(tmp_path)
    request_display(tmp_path, social_key)
    official_key = official_asset(tmp_path)
    request_display(tmp_path, official_key)
    response = client.get('/api/brand-media/entities?ids=company-test')
    assert response.status_code == 200, response.text
    model = response.json()['entities']['company-test']
    assert model['entity_type'] == 'company' and model['packaging'] == []
    assert [r['id'] for r in model['social_images']] == [social_key]
    assert [r['id'] for r in model['official_images']] == [official_key]
    for row in model['social_images']+model['official_images']:
        assert not {'original_image_url', 'object_ref', 'policy', 'rejected', 'analyst_selected'}.intersection(row)
    assert client.get(f'/api/brand-media/{official_key}/image').status_code == 410
    assert client.get('/api/brand-media?export=true').json()['assets'] == []
