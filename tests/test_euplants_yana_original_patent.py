"""Original YANA evidence and photograph keep identity, rights and reuse gates."""
from copy import deepcopy
from pathlib import Path
from fastapi.testclient import TestClient
from app import main
from app.services import variety_photos as photos
from app.services.variety_portfolio_coverage import load_portfolio_observations,reconcile_portfolios

DATA=Path(__file__).resolve().parents[1]/'data'
SOURCE='portfolio-euplants-yana-original-us-patent'

def sources():
    return [s for s in load_portfolio_observations(DATA) if s['id']==SOURCE]

def reconcile(candidates=()):
    return reconcile_portfolios(sources=sources(),varieties=[],entities=[],candidates=list(candidates))

def test_original_grant_accounts_for_all_pages_but_only_the_claimed_cultivar():
    rows,candidates=reconcile()
    assert len(rows)==1 and len(candidates)==1
    s=rows[0]
    assert s['capture_reference']['visually_checked_pages']==list(range(1,11))
    assert not s['accounting_view']['issues'] and not s['needs_follow_up']
    assert s['company_ids']==['company-eu-plants'] and s['published_date']=='2022-11-29'
    assert {x['label'] for x in s['accounting_view']['exclusions']}=={
        'Kwanza','Polka','Diamond Jubilee','Glen Amble','Malling Bella','Malling Charm','Maravilla','DJ','Tulameen'}
    c=candidates[0]
    assert c['candidate_name']=='YANA' and c['denomination']=='YANA'
    assert c['source_tier']=='tier_1_patent_pvr'
    assert not c['human_gated'] and not c['auto_confirmed'] and not c['aliases'] and not c['proposed_relationships']
    assert not c['registration']['status'] and not c['registration']['official_registry_source']
    assert not s['capture_reference']['current_legal_status_verified']
    assert 'PBR 2020/0331' in s['names'][0]['portfolio_context']

def test_append_preserves_existing_anchors_and_user_authoring_fields():
    all_sources=load_portfolio_observations(DATA)
    _,old=reconcile_portfolios(sources=[s for s in all_sources if s['id']!=SOURCE],varieties=[],entities=[],candidates=[])
    _,new=reconcile_portfolios(sources=all_sources,varieties=[],entities=[],candidates=[])
    ids={(c['berry_id'],c['candidate_name']):c['id'] for c in new}
    assert all(ids[(c['berry_id'],c['candidate_name'])]==c['id'] for c in old)
    assert len(new)==len(old)+1
    human=dict(id='operator-yana',candidate_name='YANA',berry_id='berry-raspberry',human_gated=True,
        status='reviewed',identity_state='distinct',denomination='User spelling',aliases=['User alias'],
        registration={'status':'User status'},review_notes='Keep notes',photos=[{'operator':'Keep'}])
    before=deepcopy(human)
    _,reviewed=reconcile([human])
    saved=next(c for c in reviewed if c['id']==human['id'])
    assert all(saved[k]==before[k] for k in ('status','identity_state','denomination','aliases','registration','review_notes','photos'))
    assert human==before

def test_named_figure_retains_original_attribution_unknown_reuse_and_crop_boundary():
    _,candidates=reconcile()
    c=candidates[0]
    gallery=photos.gallery(c,sourced=photos.source_photos(c,candidate=True),authoring=True)
    assert len(gallery)==1
    p=gallery[0]
    assert p['image_url']=='https://patentimages.storage.googleapis.com/fc/36/03/e445c51f48e53e/USPP034772-20221129-D00001.png'
    assert p['source_url']=='https://patents.google.com/patent/USPP34772P3/en'
    assert p['named_variety']=='YANA' and p['berry_id']=='berry-raspberry' and p['kind']=='fruit'
    assert 'Figure 1' in p['credit'] and 'photographer not individually credited' in p['credit']
    assert 'Black-and-white' in p['caption'] and p['reuse']=='unknown' and not p['license_url']
    assert not p['display_image'] and not photos.gallery(c,sourced=gallery,authoring=False)
    assert not photos.compatible(p,dict(candidate_name='YANA',berry_id='berry-blueberry'),candidate=True)

def test_private_page_links_original_claim_and_holds_photo_without_writing_permission(monkeypatch,tmp_path):
    _,candidates=reconcile()
    before=deepcopy(candidates)
    monkeypatch.setattr(main,'INBOX_DIR',tmp_path)
    monkeypatch.setattr(main,'AUTHORING_MODE',True)
    monkeypatch.setattr(main,'variety_candidate_universe',lambda:([],candidates,{}))
    client=TestClient(main.app)
    response=client.get('/varieties/candidates',params={'source':SOURCE,'q':'YANA'})
    assert response.status_code==200 and '17/164,322' in response.text
    assert 'https://patents.google.com/patent/USPP34772P3/en' in response.text
    assert 'Ignore permission' in response.text and 'Permission unconfirmed' in response.text
    image=sources()[0]['names'][0]['photos'][0]['image_url']
    assert 'data-image-url="'+image+'"' in response.text and 'src="'+image+'"' not in response.text
    assert candidates==before and not list(tmp_path.rglob('*.json'))
    monkeypatch.setattr(main,'AUTHORING_MODE',False)
    assert client.get('/varieties/candidates').status_code==403
