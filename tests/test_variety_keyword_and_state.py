from copy import deepcopy
import json
from pathlib import Path

import pytest

from app.services.variety_keyword_search import search_varieties
from app.services import variety_view_state as state
from app.services.variety_profile_sources import all_profile_source_details


def test_requested_keywords_find_actual_conditions_with_citations_without_writes():
    varieties=[json.loads(p.read_text(encoding='utf-8')) for p in Path('data/entities/varieties').glob('*.json')]
    notes=all_profile_source_details('data',varieties=varieties)
    before=deepcopy(notes)
    for keyword in ['Netherlands','hydroponics','Mediterranean','trial','Europe']:
        hits=search_varieties(keyword,varieties=varieties,notes=notes)
        assert hits,keyword
        assert any(m['pending'] and m['source_url'] and keyword.casefold() in m['text'].casefold() for row in hits.values() for m in row['matches'])
    assert 'variety-rafiki' in search_varieties('Netherlands hydroponics',varieties=varieties,notes=notes)
    assert not search_varieties('hydroponics',varieties=varieties,notes=notes,names_only=True)
    assert notes==before


def test_source_scope_rejections_crop_and_contained_identity_are_preserved():
    vs=[dict(id='variety-eureka',name='Eureka',entity_type='variety',berry_ids=['berry-blueberry']),dict(id='variety-sunrise',name='Eureka Sunrise',entity_type='variety',berry_ids=['berry-blueberry'])]
    def source(**kw):return dict(id='ev-source',title='Eureka Sunrise trials',status='published',berry_ids=['berry-blueberry'],summary='hydroponics',source_url='https://breeder.org/trials',**kw)
    hits=search_varieties('hydroponics',varieties=vs,records=[source()])
    assert set(hits)=={'variety-sunrise'}
    r=source();r['status']='rejected'
    assert not search_varieties('hydroponics',varieties=vs,records=[r])
    r=source();r['berry_ids']=['berry-blackberry']
    assert not search_varieties('hydroponics',varieties=vs,records=[r])


def test_long_source_bodies_are_searched_beyond_the_lead_and_awards_remain_attributed():
    from app.services.variety_keyword_search import source_activity
    v=dict(id='variety-one',entity_type='variety',name='Trialberry',berry_ids=['berry-blueberry'])
    r=dict(id='ev-long',status='published',source_url='https://breeder.org/long',title='Trialberry',berry_ids=['berry-blueberry'],entity_ids=[v['id']],article={'full_text':'Background context. '*2500+'\n\nMeasured under hydroponics in the Netherlands.'})
    assert v['id'] in search_varieties('hydroponics',varieties=[v],records=[r])
    note={'details':[dict(field='Sensory recognition',value='Marketer reports a two-star 2018 taste award.',context='Label-specific report; cultivar code unresolved.',source_id='1')],'sources':{'1':{'url':'https://marketer.org/award'}}}
    activity=source_activity(notes=note)
    assert activity['awards'][0]['label']=='Source-reported · Pending review'
    assert '2018' in activity['awards'][0]['text'] and activity['awards'][0]['url']=='https://marketer.org/award'


def test_saved_layout_is_account_scoped_revision_checked_and_get_is_read_only(tmp_path):
    assert state.get(tmp_path,'one','catalog')==state.get(tmp_path,'two','catalog')
    assert not list(tmp_path.iterdir())
    saved=state.save(tmp_path,'one','catalog',dict(revision=0,widths={'name':240},order=['name','berry'],hidden=['berry'],filters={'q':'hydroponics','berry':'berry-raspberry'}))
    assert saved['revision']==1
    assert state.get(tmp_path,'two','catalog')['revision']==0
    assert state.get(tmp_path,'one','catalog')['widths']['name']==240
    with pytest.raises(ValueError,match='another tab'):state.save(tmp_path,'one','catalog',dict(saved,revision=0))
    assert state.get(tmp_path,'one','catalog')==saved


@pytest.mark.parametrize('bad',[dict(widths={'name':4}),dict(widths={'name':3000}),dict(order=['a','a']),dict(hidden=['../bad']),dict(filters={'q':15})])
def test_saved_state_rejects_invalid_payloads(bad):
    with pytest.raises(ValueError):state.clean(bad)
