from copy import deepcopy
import json
from pathlib import Path
import sqlite3
import pytest
from app.services.social_intelligence.extraction import analyze
from app.services.social_intelligence.store import Store


USHBC = {'id':'company-ushbc', 'entity_type':'company',
         'name':'U.S. Highbush Blueberry Council', 'status':'active',
         'aliases':['USHBC', 'North American Blueberry Council', 'NABC']}


def test_distinct_council_mentions_do_not_inherit_ushbc_identity():
    entity = deepcopy(USHBC)
    text = 'North American Blueberry Council (NABC) meets with USHBC about blueberries.'
    result = analyze({'text':text, 'media':[]}, [entity])
    assert [link['name'] for link in result['entity_links']] == ['ushbc']
    assert {c['name'] for c in result['candidates']} == {'nabc', 'north american blueberry council'}
    assert all(c['candidate_ids'] == [] and 'identity conflict' in c['reason'] for c in result['candidates'])
    assert entity == USHBC
    assert all(text[c['span']['start']:c['span']['end']] == c['span']['text'] for c in result['candidates'])


def test_separately_registered_council_can_match_without_wrong_alias():
    nabc = {'id':'company-nabc', 'entity_type':'company', 'status':'active',
            'name':'North American Blueberry Council', 'aliases':['NABC']}
    result = analyze({'text':'NABC and USHBC discuss blueberries.', 'media':[]}, [USHBC,nabc])
    assert {(x['name'],x['entity_id']) for x in result['entity_links']} == {
        ('nabc','company-nabc'), ('ushbc','company-ushbc')}
    assert result['candidates'] == []


def test_packaging_alias_hold_uses_same_identity_gate():
    item = {'text':'Blueberries', 'media':[{'id':'label', 'parent_native_id':'post', 'state':'available',
            'literal':[{'text':'NABC', 'locator':'label', 'method':'human_label', 'version':'test-v1', 'confidence':1}]}]}
    result = analyze(item,[USHBC])
    assert result['entity_links'] == []
    assert result['candidates'][0]['basis'] == 'packaging_label'
    assert result['candidates'][0]['candidate_ids'] == []


def test_refresh_changes_only_unreviewed_proposals_and_is_atomic(tmp_path):
    fixture=json.loads((Path(__file__).resolve().parents[1]/'benchmarks/social-blueberry-fixtures.json').read_text(encoding='utf-8'))
    store=Store(tmp_path)
    keys=store.ingest(fixture['records'][:3],[])
    with sqlite3.connect(store.path) as db:
        for key in keys:db.execute('update observations set analysis=? where id=?',
                                  (json.dumps({'version':'old','entity_links':[]}),key))
    store.correct(keys[1],{'version':'human','entity_links':[]},'Test reviewer')
    store.remove(keys[2])
    with sqlite3.connect(store.path) as db:
        before={i:p for i,p in db.execute('select id,payload from observations')}
        removed_analysis=json.loads(db.execute('select analysis from observations where id=?',(keys[2],)).fetchone()[0])
    with pytest.raises(ValueError,match='Unavailable'):
        store.refresh_proposals([keys[0],'missing'],[])
    with sqlite3.connect(store.path) as db:
        assert json.loads(db.execute('select analysis from observations where id=?',(keys[0],)).fetchone()[0])['version']=='old'
    assert store.refresh_proposals(keys,[])==[keys[0]]
    assert store.refresh_proposals(keys,[])==[]
    with sqlite3.connect(store.path) as db:
        after={i:(p,json.loads(a),removed) for i,p,a,removed in db.execute('select id,payload,analysis,removed from observations')}
    assert all(after[k][0]==before[k] for k in keys)
    assert after[keys[1]][1]['reviewed'] and after[keys[1]][1]['version']=='human'
    assert after[keys[2]][2]==1 and after[keys[2]][1]==removed_analysis
    with pytest.raises(ValueError):store.refresh_proposals([keys[0],keys[0]],[])
