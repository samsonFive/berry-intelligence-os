from copy import deepcopy
from tests.test_social_intelligence import sample, ENTITIES
from app.services.social_intelligence.store import Store

def test_facebook_signed_variants_keep_one_photo_id_and_removal(tmp_path):
    store=Store(tmp_path)
    row=sample('live',source='facebook',discovery_method='provider-one',media=[])
    row['media']=[{'id':'original-photo','parent_native_id':row['native_id'],'kind':'image',
        'source_url':'https://scontent-one.fbcdn.net/v/photos/123.jpg?size=large&sig=one',
        'mime':'image/jpeg','attribution':'Original','state':'available',
        'storage_permission':'reference_only','retention':'Reference only'}]
    key=store.ingest([row],ENTITIES)[0]
    updated=deepcopy(row);updated['discovery_method']='provider-two'
    updated['media'][0].update(id='new-provider-photo',source_url='https://scontent-two.fbcdn.net/v/photos/123.jpg?size=small&sig=two')
    store.ingest([updated],ENTITIES)
    assert len(store.records()[0]['media'])==1
    assert store.records()[0]['media'][0]['id']=='original-photo'
    store.remove(key,media_id='original-photo')
    updated['media'][0]['source_url']='https://scontent-three.fbcdn.net/v/photos/123.jpg?sig=three'
    store.ingest([updated],ENTITIES)
    assert all(m['state']=='deleted' and m['source_url'] is None for m in store.records()[0]['media'])

def test_other_hosts_query_variants_are_not_assumed_identical(tmp_path):
    from app.services.social_intelligence.store import media_reference_key
    one='https://cdn.example.org/photo.jpg?id=1'
    two='https://cdn.example.org/photo.jpg?id=2'
    assert media_reference_key('facebook',one)!=media_reference_key('facebook',two)


def test_second_provider_preserves_images_and_receipts_after_restart(tmp_path):
    store=Store(tmp_path)
    original=sample('live',discovery_method='provider-one',media=[])
    original['media']=[{'id':'provider-one-photo','parent_native_id':original['native_id'],
        'kind':'image','source_url':'https://cdn.example.org/one.jpg','mime':'image/jpeg',
        'attribution':'Original','state':'available','storage_permission':'reference_only',
        'retention':'Reference only'}]
    key=store.ingest([original],ENTITIES)[0]
    incoming=deepcopy(original);incoming.update(discovery_method='provider-two',media=[])
    assert Store(tmp_path).ingest([incoming],ENTITIES)[0] == key
    assert len(store.records()) == 1 and len(store.records()[0]['media']) == 1
    assert {r['method'] for r in store.collection_receipts(key)} == {'provider-one','provider-two'}
    store.ingest([incoming],ENTITIES)
    assert len(store.collection_receipts(key)) == 2
    assert len(store.records()[0]['media']) == 1


def test_provider_switch_cannot_resurrect_removed_media(tmp_path):
    store=Store(tmp_path);original=sample('live',discovery_method='provider-one')
    original['media']=[{'id':'shared-photo','parent_native_id':original['native_id'],
        'kind':'image','source_url':'https://cdn.example.org/one.jpg','mime':'image/jpeg',
        'attribution':'Original','state':'available','storage_permission':'reference_only',
        'retention':'Reference only'}]
    key=store.ingest([original],ENTITIES)[0]
    media_id=original['media'][0]['id']
    store.remove(key,media_id=media_id)
    incoming=deepcopy(original);incoming['discovery_method']='provider-two'
    store.ingest([incoming],ENTITIES)
    media=store.records()[0]['media'][0]
    assert media['state']=='deleted' and media['source_url'] is None
    incoming['media'][0]['id']='different-provider-id'
    store.ingest([incoming],ENTITIES)
    assert all(m['state']=='deleted' and m['source_url'] is None for m in store.records()[0]['media'])
