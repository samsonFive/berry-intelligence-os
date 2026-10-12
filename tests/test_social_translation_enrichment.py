from copy import deepcopy
import json
from pathlib import Path
import pytest
from app.services.social_intelligence.store import Store,translation_source_hash
from app.services.social_intelligence.presentation import readable_in_english

FIXTURE=json.loads((Path(__file__).resolve().parents[1]/'benchmarks/social-blueberry-fixtures.json').read_text(encoding='utf-8'))['records'][0]

def setup(tmp_path):
    item=deepcopy(FIXTURE);item.update(mode='imported',language='und',translation=None)
    store=Store(tmp_path);key=store.ingest([item],[])[0]
    return store,key,item

def translation():
    return {'text':'Blueberries are crunchy.','language':'en','method':'machine','version':'verified-web-check-v1','uncertainty':'Caption only; not independently graded'}

def test_restart_replay_and_changed_text(tmp_path):
    store,key,item=setup(tmp_path)
    with store.connect() as db: before=db.execute('select payload,analysis from observations where id=?',(key,)).fetchone()
    store.enrich_translation(key,translation_source_hash(item),translation(),'operator')
    with store.connect() as db: assert db.execute('select payload,analysis from observations where id=?',(key,)).fetchone()==before
    row=Store(tmp_path).records()[0]
    assert row['language']=='und' and readable_in_english(row)
    assert row['translation_review']['reviewer']=='operator'
    store.ingest([item],[]);assert readable_in_english(store.records()[0])
    item['text']+=' Changed source';store.ingest([item],[])
    assert not readable_in_english(store.records()[0])
    with pytest.raises(ValueError,match='changed'):store.enrich_translation(key,translation_source_hash(row),translation(),'operator')

def test_invalid_and_deleted_are_not_enriched(tmp_path):
    store,key,item=setup(tmp_path)
    for changes in ({'text':''},{'method':'synthetic'},{'version':''},{'language':'es'}):
        value=translation();value.update(changes)
        with pytest.raises(ValueError):store.enrich_translation(key,translation_source_hash(item),value,'operator')
    store.remove(key,state='deleted')
    with pytest.raises(ValueError):store.enrich_translation(key,translation_source_hash(item),translation(),'operator')
    assert store.records()==[]


def test_preserves_analyst_review_and_prior_translation_history(tmp_path):
    store,key,item=setup(tmp_path)
    store.correct(key,store.records()[0]['analysis'],'human-reviewer')
    before=store.records()[0]['analysis']
    digest=translation_source_hash(item)
    store.enrich_translation(key,digest,translation(),'operator')
    second=translation();second['text']='A corrected English rendering.'
    store.enrich_translation(key,digest,second,'second-reviewer')
    assert store.records()[0]['analysis']==before
    with store.connect() as db:
        history=[json.loads(e) for (e,) in db.execute("select event from audit where event like '%translation_enrichment_before%'")]
    assert history[-1]['translation_enrichment_before']['translation']==translation()
    assert history[-1]['reviewer']=='second-reviewer'


def test_fixture_enrichment_does_not_cross_to_real_mode(tmp_path):
    store,key,item=setup(tmp_path)
    fixture=deepcopy(item);fixture['mode']='fixture'
    fixture_key=store.ingest([fixture],[])[0]
    value=translation();value['method']='synthetic'
    store.enrich_translation(fixture_key,translation_source_hash(fixture),value,'fixture-author')
    assert readable_in_english(store.records(mode='fixture')[0])
    assert not readable_in_english(store.records(mode='imported')[0])
