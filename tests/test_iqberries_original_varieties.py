"""Prepared tests for the next original IQ Berries batch; not yet imported."""
from copy import deepcopy
from pathlib import Path
from fastapi.testclient import TestClient
from app import main
from app.services import variety_photos as photos
from app.services.variety_portfolio_coverage import load_portfolio_observations,reconcile_portfolios

DATA=Path(__file__).resolve().parents[1]/'data'
PREFIX='portfolio-iqberries-'
LABELS={'MEGAEARLY':'T11-319','MEGACROP':'T11-119','MEGAGRAND':'T112-219',
    'MEGACRISP':'T111-519','MEGAONE':'F116','MEGAGEM':'T111-219','MEGASTAR':'T112-519'}

def sources():
    return [s for s in load_portfolio_observations(DATA) if s['id'].startswith(PREFIX)]

def reconcile(candidates=()):
    return reconcile_portfolios(sources=sources(),varieties=[],entities=[],candidates=list(candidates))

def test_complete_named_original_portfolio_and_detail_accounting():
    rows,candidates=reconcile()
    assert len(rows)==8 and sum(len(s['names']) for s in rows)==14 and len(candidates)==7
    assert all(not s['accounting_view']['issues'] and not s['needs_follow_up'] for s in rows)
    assert all(s['capture_reference']['body_read'] and s['company_ids']==['company-iq-berries'] for s in rows)
    assert all(not s.get('published_date') for s in rows)
    assert {c['candidate_name'] for c in candidates}==set(LABELS)
    for c in candidates:
        assert len(c['portfolio_sources'])==2
        assert all(ref['display_label']==f"{c['candidate_name']} ({LABELS[c['candidate_name']]})" for ref in c['portfolio_sources'])
        assert not c['human_gated'] and not c['auto_confirmed'] and not c['aliases'] and not c['proposed_relationships']
        assert not c.get('denomination') and not c.get('breeder_code') and not c['registration']['status']
    grand=next(s for s in rows if s['id']=='portfolio-iqberries-megagrand-original')
    assert [e['label'] for e in grand['accounting_view']['exclusions']]==['MegaEarly']
    gem=next(s for s in rows if s['id']=='portfolio-iqberries-megagem-original')
    assert 'omits the year' in gem['names'][0]['portfolio_context']

def test_next_append_retains_every_existing_anchor_and_human_photo_edits():
    all_sources=load_portfolio_observations(DATA)
    _,old=reconcile_portfolios(sources=[s for s in all_sources if not s['id'].startswith(PREFIX)],varieties=[],entities=[],candidates=[])
    _,new=reconcile_portfolios(sources=all_sources,varieties=[],entities=[],candidates=[])
    ids={(c['berry_id'],c['candidate_name']):c['id'] for c in new}
    assert all(ids[(c['berry_id'],c['candidate_name'])]==c['id'] for c in old)
    assert len(new)==len(old)+7
    human={'id':'operator-iq-early','candidate_name':'MEGAEARLY','berry_id':'berry-blueberry',
        'human_gated':True,'identity_state':'distinct','status':'reviewed','aliases':['User alias'],
        'registration':{'status':'Keep my rights note'},'review_notes':'Keep notes','photos':[{'operator':'Keep'}]}
    before=deepcopy(human)
    _,new=reconcile([human])
    saved=next(c for c in new if c['id']==human['id'])
    assert all(saved[k]==before[k] for k in ['identity_state','status','aliases','registration','review_notes','photos'])
    assert human==before

def test_every_named_original_photo_keeps_unknown_reuse_and_private_crop_gate():
    _,candidates=reconcile()
    for c in candidates:
        p=photos.gallery(c,sourced=photos.source_photos(c,candidate=True),authoring=True)
        assert len(p)==1
        photo=p[0]
        assert photo['named_variety']==c['candidate_name'] and photo['berry_id']=='berry-blueberry'
        assert photo['source_url'].startswith('https://iqberries.com/varieties/')
        assert photo['image_url'].startswith('https://iqberries.com/wp-content/uploads/2023/04/')
        assert 'TablasTemporadas' not in photo['image_url']
        assert 'IQ Berries' in photo['credit'] and 'not individually credited' in photo['credit']
        assert photo['reuse']=='unknown' and not photo['display_image'] and not photo['license_url']
        assert not photos.gallery(c,sourced=p,authoring=False)
        assert not photos.compatible(photo,dict(candidate_name=c['candidate_name'],berry_id='berry-raspberry'),candidate=True)

def test_original_detail_handoff_leaves_photo_hidden_until_session_choice(monkeypatch,tmp_path):
    _,candidates=reconcile()
    before=deepcopy(candidates)
    monkeypatch.setattr(main,'INBOX_DIR',tmp_path)
    monkeypatch.setattr(main,'AUTHORING_MODE',True)
    monkeypatch.setattr(main,'variety_candidate_universe',lambda:([],candidates,{}))
    client=TestClient(main.app)
    response=client.get('/varieties/candidates',params={'source':'portfolio-iqberries-megaearly-original','q':'MEGAEARLY'})
    assert response.status_code==200 and 'T11-319' in response.text
    assert 'https://iqberries.com/varieties/megaearly/' in response.text
    assert 'Ignore permission' in response.text and 'Permission unconfirmed' in response.text
    ref=next(s for s in sources() if s['id']=='portfolio-iqberries-megaearly-original')
    image=ref['names'][0]['photos'][0]['image_url']
    assert 'data-image-url="'+image+'"' in response.text and 'src="'+image+'"' not in response.text
    assert candidates==before and not list(tmp_path.rglob('*.json'))
    monkeypatch.setattr(main,'AUTHORING_MODE',False)
    assert client.get('/varieties/candidates').status_code==403
