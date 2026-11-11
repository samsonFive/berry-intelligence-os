"""Deterministic synthetic media tests; these are never a real demo cohort."""
from copy import deepcopy
from datetime import UTC, datetime, timedelta
import hashlib
from io import BytesIO
import json
import sqlite3
import struct
import zlib

import pytest

from app.services import brand_media as media
from app.services.social_intelligence.adapters import common
from app.services.social_intelligence.store import Store


NOW = datetime(2026, 11, 11, 12, tzinfo=UTC)


def synthetic_png():
    from PIL import Image
    output = BytesIO()
    Image.new('RGB', (1, 1), color=(255, 255, 255)).save(output, format='PNG')
    return output.getvalue()


PNG = synthetic_png()


def png_with_declared_dimensions(width, height):
    """Change only IHDR and its CRC; never allocate a decompressed big image."""
    payload = struct.pack('>II', width, height) + PNG[24:29]
    return PNG[:16] + payload + struct.pack('>I', zlib.crc32(b'IHDR'+payload)) + PNG[33:]


ENTITIES = {
    'company-test': {'id': 'company-test', 'entity_type': 'company', 'name': 'Synthetic Berry Company', 'aliases': []},
    'brand-test': {'id': 'brand-test', 'entity_type': 'brand', 'name': 'Synthetic Berry Brand', 'aliases': []},
    'retailer-test': {'id': 'retailer-test', 'entity_type': 'retailer', 'name': 'Synthetic Test Retailer', 'aliases': []},
    'variety-test': {'id': 'variety-test', 'entity_type': 'variety', 'name': 'Synthetic cultivar', 'aliases': []},
}
ACCOUNTS = [{'entity_id': 'company-test', 'platform': 'facebook',
             'account_url': 'https://www.facebook.com/BerryTestOfficial/', 'source_kind': 'official',
             'supporting_url': 'https://example.org/official-social-links',
             'verification_basis': 'Synthetic test account link fixture; no real verification claim'}]


def source_row(*, native='unit-post', mode='live', author='BerryTestOfficial', count=3):
    row = common('facebook', native, f'https://www.facebook.com/{author}/posts/{native}',
                 'Synthetic caption mentions packaging, shelf display and a logo. It proves no image classification.',
                 'en', (NOW-timedelta(days=90)).isoformat())
    row.update(mode=mode, author_handle=author, collected_at=(NOW-timedelta(days=1)).isoformat(),
               permission_basis='Synthetic test source references only', retention_days=30)
    row['media'] = [{'id': f'{native}-image-{i}', 'parent_native_id': native, 'kind': 'image',
                     'source_url': f'https://example.org/test-media/{native}-{i}.png', 'mime': 'image/png',
                     'attribution': 'Synthetic unit-test image', 'state': 'available',
                     'storage_permission': 'reference_only', 'retention': 'Synthetic test reference; no redisplay permission'}
                    for i in range(count)]
    return row


def seed(inbox, row=None):
    row = row or source_row()
    store = Store(inbox)
    key = store.ingest([row], list(ENTITIES.values()), mode=row['mode'])[0]
    return store, key


def policy(**changes):
    return {'display': True, 'cache': True, 'export': False,
            'basis': 'Authorized synthetic test raster', 'source_url': 'https://example.org/test-permission',
            'checked_at': NOW.isoformat(), 'expires_at': (NOW+timedelta(days=20)).isoformat(), **changes}


def upload_metadata(**changes):
    return {'entity_id': 'company-test', 'authorization': 'Test author owns this synthetic pixel',
            'source_kind': 'official', 'kind': 'pack_photo', 'classification_basis': 'Explicit synthetic test classification',
            'caption': 'Synthetic test pack', 'policy': policy(), **changes}


def classify(inbox, asset_id, **changes):
    return media.decide(inbox, asset_id, {'kind': 'pack_photo', 'classification_basis': 'Test analyst inspected test pixels',
                                        'policy': policy(), **changes}, reviewer='Synthetic test reviewer', entities=ENTITIES)


def test_reuse_registers_every_carousel_without_caption_classification_and_preserves_decisions(tmp_path):
    seed(tmp_path)
    first = media.reuse_social(tmp_path, ENTITIES, accounts=ACCOUNTS, now=NOW)
    assert first['created'] == first['attachments_seen'] == 3
    assets = media.load(tmp_path)
    assert {a['media_id'] for a in assets.values()} == {f'unit-post-image-{i}' for i in range(3)}
    assert all(a['kind'] == 'unclassified' and a['classification_basis'] is None for a in assets.values())
    selected = next(iter(assets))
    classify(tmp_path, selected, primary=True, rejected=True, caption='Analyst rejection survives reruns')
    before = media.load(tmp_path)[selected]
    rerun = media.reuse_social(tmp_path, ENTITIES, accounts=ACCOUNTS, now=NOW+timedelta(hours=1))
    assert rerun['created'] == 0 and rerun['reused'] == 3
    assert len(media.load(tmp_path)) == 3 and media.load(tmp_path)[selected] == before
    assert len(list((tmp_path/'brand_media'/'decisions').glob('*.json'))) == 1


def test_fixtures_expired_sources_and_unsupported_attachments_are_excluded(tmp_path):
    seed(tmp_path, source_row(native='fixture', mode='fixture'))
    old = source_row(native='expired'); old['collected_at'] = (NOW-timedelta(days=31)).isoformat()
    seed(tmp_path, old)
    good = source_row(native='mixed')
    good['media'][0]['state'] = 'restricted'
    good['media'][1]['kind'] = 'video'
    seed(tmp_path, good)
    result = media.reuse_social(tmp_path, ENTITIES, accounts=ACCOUNTS, now=NOW)
    assert result['posts_scanned'] == 2 and result['expired'] == 1 and result['created'] == 1
    assert next(iter(media.load(tmp_path).values()))['media_id'] == 'mixed-image-2'


@pytest.mark.parametrize('author', ['BerryTestOfficialOther', 'BerryTestOfficial-parent', 'DifferentParent'])
def test_official_account_match_is_exact_not_similar_name_or_parent(author):
    assert media.resolve_account(source_row(author=author), ACCOUNTS, ENTITIES) is None


def test_account_match_requires_supporting_link_and_unambiguous_existing_entity():
    row = source_row()
    assert media.resolve_account(row, ACCOUNTS, ENTITIES)['entity_id'] == 'company-test'
    assert media.resolve_account(row, [{**ACCOUNTS[0], 'supporting_url': ''}], ENTITIES) is None
    assert media.resolve_account(row, [{**ACCOUNTS[0], 'entity_id': 'variety-test'}], ENTITIES) is None
    assert media.resolve_account(row, ACCOUNTS*2, ENTITIES) is None
    assert media.resolve_account(row, [{**ACCOUNTS[0], 'account_url': row['canonical_url']}], ENTITIES) is None


def test_official_discovery_metadata_is_held_idempotent_and_does_not_match_parent_subbrand(tmp_path):
    def candidate(n, **changes):
        return {'original_image_url': f'https://example.org/test-media/discovery-{n}.png',
                'source_page_url': 'https://example.org/official-press-kit', 'asset_type': 'logo',
                'entity_name_match': 'exact', 'declared_subject_name': 'Synthetic Berry Company',
                'source_locator': '$.logo.url', 'width': 320, 'height': 100, **changes}
    candidates = [candidate(0), candidate(1, entity_name_match='mismatch', declared_subject_name='Synthetic Parent Company'),
                  candidate(2, asset_type='product_image', source_locator='$.image[0]')]
    assert media.register_discovery(tmp_path, 'company-test', candidates, entities=ENTITIES) == {'created': 3, 'reused': 0}
    rows = media.inventory(tmp_path, now=NOW)
    assert len(rows) == 3 and all(not r['display_eligible'] and not r['export_eligible'] for r in rows)
    exact = next(r for r in rows if r['original_image_url'].endswith('discovery-0.png'))
    parent = next(r for r in rows if r['original_image_url'].endswith('discovery-1.png'))
    product = next(r for r in rows if r['original_image_url'].endswith('discovery-2.png'))
    assert exact['match_status'] == 'matched' and exact['width'] == 320 and exact['source_locator'] == '$.logo.url'
    assert parent['match_status'] == product['match_status'] == 'review_needed'
    assert product['kind'] == 'unclassified' and not product['classification_basis']
    assert not exact['policy']['display'] and exact.get('published_at') is None
    media.decide(tmp_path, exact['id'], {'rejected': True}, reviewer='Test reviewer')
    assert media.register_discovery(tmp_path, 'company-test', candidates, entities=ENTITIES) == {'created': 0, 'reused': 3}
    assert media.load(tmp_path)[exact['id']]['rejected']


def test_same_caption_without_account_needs_identity_review(tmp_path):
    store, key = seed(tmp_path, source_row(author='UnverifiedAccount', count=1))
    with sqlite3.connect(store.path) as db:
        db.execute('UPDATE observations SET analysis=? WHERE id=?',
                   (json.dumps({'entity_links': [{'entity_id': 'company-test', 'basis': 'text', 'review': 'proposed'}]}), key))
    media.reuse_social(tmp_path, ENTITIES, accounts=ACCOUNTS, now=NOW)
    row = media.inventory(tmp_path, now=NOW)[0]
    assert row['match_status'] == 'review_needed' and row['source_kind'] == 'unknown'
    assert row['kind'] == 'unclassified' and not row['display_eligible']
    assert not any(k in row for k in ('cultivar', 'cultivar_id', 'supplier', 'purchase_market', 'inventory'))


def test_reference_url_never_becomes_image_even_after_policy_and_classification(tmp_path):
    seed(tmp_path, source_row(count=1))
    media.reuse_social(tmp_path, ENTITIES, accounts=ACCOUNTS, now=NOW)
    key = next(iter(media.load(tmp_path)))
    classify(tmp_path, key)
    row = media.inventory(tmp_path, now=NOW)[0]
    assert not row['display_eligible'] and row['image_url'] is None and not row['export_eligible']
    assert row['inspection_href'].endswith('media=metadata-only')
    assert any('No permitted local raster bytes' in b for b in row['blockers'])
    assert media.entity_media(tmp_path, ['company-test'], now=NOW)['company-test']['packaging'] == []
    with pytest.raises(ValueError, match='display eligible'):
        media.image_file(tmp_path, key, now=NOW)


def test_social_permitted_bytes_retention_and_removal_govern_existing_mapping(tmp_path):
    source = source_row(count=1); source['media'][0]['storage_permission'] = 'permitted_bytes'
    store, observation_id = seed(tmp_path, source)
    store.attach_media(observation_id, source['media'][0]['id'], PNG, 'image/png')
    media.reuse_social(tmp_path, ENTITIES, accounts=ACCOUNTS, now=NOW)
    key = next(iter(media.load(tmp_path))); classify(tmp_path, key)
    assert media.inventory(tmp_path, now=NOW)[0]['display_eligible']
    assert media.image_file(tmp_path, key, now=NOW)[0].read_bytes() == PNG
    assert not media.inventory(tmp_path, now=NOW+timedelta(days=31))[0]['display_eligible']
    store.remove(observation_id, media_id=source['media'][0]['id'], state='restricted')
    assert not media.inventory(tmp_path, now=NOW)[0]['display_eligible']
    assert len(media.load(tmp_path)) == 1  # The mapping/review history survives source restrictions.


def test_cross_mode_source_deletion_blocks_previous_imported_mapping(tmp_path):
    source = source_row(mode='imported', count=1); source['media'][0]['storage_permission'] = 'permitted_bytes'
    store, observation_id = seed(tmp_path, source)
    store.attach_media(observation_id, source['media'][0]['id'], PNG, 'image/png')
    media.reuse_social(tmp_path, ENTITIES, accounts=ACCOUNTS, now=NOW)
    key = next(iter(media.load(tmp_path))); classify(tmp_path, key)
    live = deepcopy(source); live['mode'] = 'live'
    live_id = store.ingest([live], list(ENTITIES.values()), mode='live')[0]
    store.remove(live_id, state='deleted')
    assert not media.inventory(tmp_path, now=NOW)[0]['display_eligible']


@pytest.mark.parametrize('tombstone', ['media_id', 'url_hash'])
def test_durable_media_tombstones_override_stale_available_payload(tmp_path, tombstone):
    source = source_row(count=1); source['media'][0]['storage_permission'] = 'permitted_bytes'
    store, observation_id = seed(tmp_path, source)
    store.attach_media(observation_id, source['media'][0]['id'], PNG, 'image/png')
    media.reuse_social(tmp_path, ENTITIES, accounts=ACCOUNTS, now=NOW)
    key = next(iter(media.load(tmp_path))); classify(tmp_path, key)
    with sqlite3.connect(store.path) as db:
        if tombstone == 'media_id':
            db.execute('INSERT INTO media_tombstones VALUES(?,?,?)', (observation_id, source['media'][0]['id'], 'restricted'))
        else:
            digest = hashlib.sha256(source['media'][0]['source_url'].encode()).hexdigest()
            db.execute('INSERT INTO media_url_tombstones VALUES(?,?,?)', (observation_id, digest, 'unavailable'))
    row = media.inventory(tmp_path, now=NOW)[0]
    assert not row['display_eligible'] and row['image_url'] is None
    assert 'Source removed, restricted or unavailable' in row['blockers']


def test_authorized_upload_content_hash_dedup_preserves_analyst_override(tmp_path):
    first = media.authorized_upload(tmp_path, upload_metadata(), PNG, entities=ENTITIES)
    media.decide(tmp_path, first['id'], {'rejected': True, 'caption': 'Do not restore'}, reviewer='Test reviewer')
    second = media.authorized_upload(tmp_path, upload_metadata(caption='Replacement caption'), PNG, entities=ENTITIES)
    assert second['id'] == first['id'] and second['rejected'] and second['caption'] == 'Do not restore'
    assert first['object_ref'] == hashlib.sha256(PNG).hexdigest()
    assert len(media.load(tmp_path)) == len(list((tmp_path/'brand_media'/'objects').iterdir())) == 1


@pytest.mark.parametrize('change', [{'authorization': ''}, {'entity_id': 'variety-test'}])
def test_upload_requires_authorization_and_supported_entity(tmp_path, change):
    with pytest.raises(ValueError):
        media.authorized_upload(tmp_path, upload_metadata(**change), PNG, entities=ENTITIES)
    assert not media.load(tmp_path)


def test_upload_without_local_storage_permission_does_not_persist_bytes(tmp_path):
    with pytest.raises(ValueError, match='storage|cach'):
        media.authorized_upload(tmp_path, upload_metadata(policy=policy(cache=False)), PNG, entities=ENTITIES)
    assert not media.load(tmp_path) and not (tmp_path/'brand_media'/'objects').exists()


@pytest.mark.parametrize('content', [b'\x89PNG\r\n\x1a\ninvalid raster', PNG[:-15],
                                  png_with_declared_dimensions(12001, 1),
                                  png_with_declared_dimensions(5000, 5000),
                                  png_with_declared_dimensions(100000, 100000)])
def test_corrupt_or_decompression_bound_uploads_fail_without_storing_bytes(tmp_path, content):
    with pytest.raises(ValueError):
        media.authorized_upload(tmp_path, upload_metadata(), content, entities=ENTITIES)
    assert not media.load(tmp_path) and not (tmp_path/'brand_media'/'objects').exists()


def test_valid_raster_dimensions_are_recorded_and_crc_corruption_is_rejected(tmp_path):
    asset = media.authorized_upload(tmp_path, upload_metadata(), PNG, entities=ENTITIES)
    assert (asset['mime'], asset['width'], asset['height']) == ('image/png', 1, 1)
    corrupt = bytearray(PNG)
    corrupt[PNG.index(b'IDAT')+4] ^= 0x01
    with pytest.raises(ValueError, match='valid bounded raster'):
        media.raster_info(bytes(corrupt))


def test_invalid_retained_raster_cannot_count_as_display_eligible(tmp_path):
    source = source_row(count=1); source['media'][0]['storage_permission'] = 'permitted_bytes'
    store, observation_id = seed(tmp_path, source)
    store.attach_media(observation_id, source['media'][0]['id'], b'\x89PNG\r\n\x1a\ninvalid raster', 'image/png')
    media.reuse_social(tmp_path, ENTITIES, accounts=ACCOUNTS, now=NOW)
    key = next(iter(media.load(tmp_path))); classify(tmp_path, key)
    row = media.inventory(tmp_path, now=NOW)[0]
    assert not row['display_eligible'] and row['image_url'] is None and not row['export_eligible']
    assert media.entity_media(tmp_path, ['company-test'], now=NOW)['company-test']['packaging'] == []
    with pytest.raises(ValueError):
        media.image_file(tmp_path, key, now=NOW)


def test_manual_classification_cannot_add_unsupported_cultivar_or_supplier_fields(tmp_path):
    asset = media.authorized_upload(tmp_path, upload_metadata(), PNG, entities=ENTITIES)
    for changes in ({'cultivar_id': 'variety-test'}, {'supplier_id': 'company-test'}, {'purchase_market': 'US'}):
        with pytest.raises(ValueError, match='Unsupported media decision'):
            media.decide(tmp_path, asset['id'], changes, reviewer='Test reviewer')
    assert not any(k in media.load(tmp_path)[asset['id']] for k in ('cultivar_id', 'supplier_id', 'purchase_market'))


def test_official_packaging_retailer_consumer_observations_and_campaign_stay_separate(tmp_path):
    for n, kind in enumerate(('official', 'retailer', 'consumer')):
        media.authorized_upload(tmp_path, upload_metadata(source_kind=kind), PNG+bytes([n]), entities=ENTITIES)
    media.authorized_upload(tmp_path, upload_metadata(kind='campaign'), PNG+b'campaign', entities=ENTITIES)
    model = media.entity_media(tmp_path, ['company-test'], now=NOW)['company-test']
    assert [r['source_kind'] for r in model['packaging']] == ['official']
    assert {r['source_kind'] for r in model['observations']} == {'retailer', 'consumer'}
    assert all(r['kind'] != 'campaign' for r in model['packaging']+model['observations'])
    render = media.authorized_upload(tmp_path, upload_metadata(kind='pack_render', source_kind='consumer'), PNG+b'render', entities=ENTITIES)
    row = next(r for r in media.inventory(tmp_path, now=NOW) if r['id'] == render['id'])
    assert not row['display_eligible'] and 'Rendering needs an official publisher' in row['blockers']


def test_policy_expiry_export_hold_missing_file_and_integrity_are_enforced(tmp_path):
    asset = media.authorized_upload(tmp_path, upload_metadata(), PNG, entities=ENTITIES)
    assert media.inventory(tmp_path, now=NOW)[0]['display_eligible']
    assert not media.inventory(tmp_path, now=NOW)[0]['export_eligible']
    media.decide(tmp_path, asset['id'], {'policy': policy(expires_at=(NOW-timedelta(seconds=1)).isoformat())}, reviewer='Test reviewer')
    assert not media.inventory(tmp_path, now=NOW)[0]['display_eligible']
    media.decide(tmp_path, asset['id'], {'policy': policy(export=True)}, reviewer='Test reviewer')
    path, _ = media.image_file(tmp_path, asset['id'], now=NOW)
    path.write_bytes(PNG+b'tampered')
    with pytest.raises(ValueError, match='integrity|display eligible'):
        media.image_file(tmp_path, asset['id'], now=NOW)
    path.unlink()
    assert not media.inventory(tmp_path, now=NOW)[0]['display_eligible']


@pytest.mark.parametrize('failure', ['index_json', 'social_sqlite', 'source_payload'])
def test_corrupt_store_never_breaks_shared_entity_read_model(tmp_path, failure):
    store, observation_id = seed(tmp_path, source_row(count=1))
    media.reuse_social(tmp_path, ENTITIES, accounts=ACCOUNTS, now=NOW)
    if failure == 'index_json':
        media.index_path(tmp_path).write_text('{broken', encoding='utf-8')
    elif failure == 'social_sqlite':
        store.path.write_bytes(b'not a sqlite database')
    else:
        with sqlite3.connect(store.path) as db:
            db.execute('UPDATE observations SET payload=? WHERE id=?',
                       (json.dumps({'mode': 'live', 'media': source_row(count=1)['media']}), observation_id))
    assert media.entity_media(tmp_path, ['company-test'], now=NOW) == {'company-test': {'logo': None, 'packaging': [], 'observations': [], 'social_images': [], 'official_images': []}}
