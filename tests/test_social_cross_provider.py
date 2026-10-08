from copy import deepcopy
from tests.test_social_intelligence import sample, ENTITIES
from app.services.social_intelligence.store import Store


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
