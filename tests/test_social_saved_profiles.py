import json
from pathlib import Path
import pytest
from app.services.social_intelligence.profiles import save_profile,saved_profiles,remove_profile,bounded_queries
from app.services.watchlist import add_watch,load_watches,state_path

ENTITIES=[{'id':'company-berry','entity_type':'company','name':'Berry Co','aliases':['Berry Company']}]

def test_social_scope_restart_review_and_existing_watches_preserved(tmp_path):
    add_watch(tmp_path,'company','company-berry')
    row=save_profile(tmp_path,'Corporate berries',{'entity':'company-berry','perspective':'corporate','source':'facebook'},ENTITIES,reviewed_by='Test analyst')
    assert row['filters']['berry']=='all' and row['filters']['mode']=='live'
    assert row['reviewed_at'] and row['targets'][0]['review']=='analyst-approved'
    assert row['monitoring'] is False and row['targets'][0]['enabled'] is False
    assert bounded_queries(row['targets'][0],ENTITIES)==['Berry Co','Berry Company']
    assert saved_profiles(Path(str(tmp_path)))[0]['id']==row['id']
    add_watch(tmp_path,'berry','berry-blueberry')
    assert len(load_watches(tmp_path))==2 and saved_profiles(tmp_path)[0]['revision']==1
    with pytest.raises(ValueError,match='already saved'):save_profile(tmp_path,'Corporate berries',{},ENTITIES)
    updated=save_profile(tmp_path,'Corporate berries',{'perspective':'consumer','mode':'imported'},ENTITIES,revision=1)
    assert updated['id']==row['id'] and updated['revision']==2
    assert not updated['reviewed_by'] and updated['reviewed_at'] is None and updated['targets']==[]
    with pytest.raises(ValueError,match='changed'):remove_profile(tmp_path,row['id'],1)
    remove_profile(tmp_path,row['id'],2)
    assert saved_profiles(tmp_path)==[] and len(load_watches(tmp_path))==2

def test_social_first_save_is_compatible_with_watchlist_and_corruption_fails_closed(tmp_path):
    save_profile(tmp_path,'Sample view',{'mode':'fixture'},ENTITIES)
    assert load_watches(tmp_path)==[]
    add_watch(tmp_path,'company','company-berry')
    original=state_path(tmp_path).read_text(encoding='utf-8')
    payload=json.loads(original);payload['social_profiles'][0]['monitoring']=True
    state_path(tmp_path).write_text(json.dumps(payload),encoding='utf-8')
    bad=state_path(tmp_path).read_bytes()
    with pytest.raises(ValueError,match='left unchanged'):save_profile(tmp_path,'Other',{},ENTITIES)
    assert state_path(tmp_path).read_bytes()==bad

@pytest.mark.parametrize('filters',[{'source':'bad'},{'berry':'berry-phone'},{'entity':'unknown'},{'enabled':'true'},{'start':'2026-10-08','end':'2026-10-07'}])
def test_invalid_watch_scope_cannot_write_or_activate(tmp_path,filters):
    with pytest.raises(ValueError):save_profile(tmp_path,'No',filters,ENTITIES)
    assert not state_path(tmp_path).exists()
