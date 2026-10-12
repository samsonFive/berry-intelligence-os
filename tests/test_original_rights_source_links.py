"""Original rights references, source strength and photo choice preserve human gates."""
from copy import deepcopy
from pathlib import Path
from fastapi.testclient import TestClient
from app import main
from app.services import variety_photos as photos
from app.services.variety_portfolio_coverage import load_portfolio_observations,reconcile_portfolios

DATA=Path(__file__).resolve().parents[1]/'data'
IDS={'portfolio-enrosadira-original-us-patent','portfolio-alel-italian-register-2022','portfolio-alel-italian-register-2025'}


def sources():
    return [s for s in load_portfolio_observations(DATA) if s['id'] in IDS]


def reconcile(candidates=()):
    return reconcile_portfolios(sources=sources(),varieties=[],entities=[],candidates=list(candidates))


def test_three_original_documents_have_complete_visual_accounting_and_no_company_inference():
    rows,candidates=reconcile()
    assert len(rows)==3 and sum(len(s['names']) for s in rows)==5
    assert {c['candidate_name'] for c in candidates}=={'Enrosadira','ALEL045','ALEL111'}
    assert all(not s['accounting_view']['issues'] and not s['needs_follow_up'] for s in rows)
    assert all(not s['company_ids'] and s['capture_reference']['visually_checked_pages']==[1,2,3,4] for s in rows)
    patent=next(s for s in rows if s['id']=='portfolio-enrosadira-original-us-patent')
    assert patent['published_date']=='2017-06-27' and patent['source_type']=='plant_patent'
    assert {e['label'] for e in patent['accounting_view']['exclusions']}=={'Erika','T44L04 / Lagorai','T35L04'}
    assert all(not s.get('published_date') for s in rows if s!=patent)


def test_original_national_register_strength_does_not_approve_rights_or_commercial_name_matching():
    _,candidates=reconcile()
    for c in candidates:
        expected='tier_1_patent_pvr' if c['candidate_name']=='Enrosadira' else 'tier_1_national_register'
        assert c['source_tier']==expected
        assert not c['human_gated'] and not c['auto_confirmed'] and not c['aliases'] and not c['proposed_relationships']
        assert not c['registration']['status'] and not c['registration']['official_registry_source']
    codes=[c for c in candidates if c['candidate_name'].startswith('ALEL')]
    assert {c['denomination'] for c in codes}=={'ALEL045','ALEL111'}
    assert all(len(c['portfolio_sources'])==2 for c in codes)
    assert not any(c['candidate_name'] in {'EasyStar','EasyRock'} for c in candidates)
    refs={s['id']:s for s in sources()}
    latest={n['candidate_name']:n for n in refs['portfolio-alel-italian-register-2025']['names']}
    assert '69194 EU' in latest['ALEL111']['portfolio_context'] and '22/04/2025' in latest['ALEL111']['portfolio_context']
    assert 'Rights-number/date cells blank' in latest['ALEL045']['portfolio_context']
    assert 'not evidence that no rights exist' in latest['ALEL045']['portfolio_context']


def test_append_order_and_official_reference_refresh_preserve_all_prior_ids_and_user_fields():
    all_sources=load_portfolio_observations(DATA)
    _,old=reconcile_portfolios(sources=[s for s in all_sources if s['id'] not in IDS],varieties=[],entities=[],candidates=[])
    _,new=reconcile_portfolios(sources=all_sources,varieties=[],entities=[],candidates=[])
    ids={(c['berry_id'],c['candidate_name']):c['id'] for c in new}
    assert all(ids[(c['berry_id'],c['candidate_name'])]==c['id'] for c in old)
    assert len(new)==len(old)+2
    human=dict(id='operator-alel',candidate_name='ALEL111',berry_id='berry-raspberry',status='reviewed',
        identity_state='distinct',human_gated=True,reviewer='Analyst',source_tier='User tier',
        aliases=['My label'],registration={'status':'User status','official_registry_source':'User source'},
        review_notes='Keep notes',knowledge={'notes':'My context'},photos=[{'my_edit':'Keep'}])
    before=deepcopy(human)
    _,candidates=reconcile([human])
    saved=next(c for c in candidates if c['id']==human['id'])
    assert all(saved[k]==before[k] for k in ('status','identity_state','source_tier','aliases','registration','review_notes','knowledge','photos'))
    assert human==before


def test_original_named_plate_is_attributed_session_only_and_never_public():
    _,candidates=reconcile()
    target=next(c for c in candidates if c['candidate_name']=='Enrosadira')
    held=photos.gallery(target,sourced=photos.source_photos(target,candidate=True),authoring=True)
    assert len(held)==1
    p=held[0]
    assert p['image_url']=='https://patentimages.storage.googleapis.com/34/fa/d1/d0ddc1126f038c/USPP028138-20170627-D00001.png'
    assert p['source_url']=='https://patents.google.com/patent/USPP28138P3/en'
    assert 'USPP28138P3' in p['credit'] and 'photographer not individually credited' in p['credit']
    assert p['reuse']=='unknown' and not p['display_image'] and not p['license_url']
    assert p['kind']=='plant' and p['named_variety']=='Enrosadira'
    assert not photos.gallery(target,sourced=held,authoring=False)
    assert not photos.compatible(p,dict(candidate_name='Enrosadira',berry_id='berry-blueberry'),candidate=True)


def test_private_review_links_original_claims_and_preserves_hidden_photo_default(monkeypatch,tmp_path):
    _,candidates=reconcile()
    before=deepcopy(candidates)
    monkeypatch.setattr(main,'INBOX_DIR',tmp_path)
    monkeypatch.setattr(main,'AUTHORING_MODE',True)
    monkeypatch.setattr(main,'variety_candidate_universe',lambda:([],candidates,{}))
    client=TestClient(main.app)
    response=client.get('/varieties/candidates',params={'source':'portfolio-enrosadira-original-us-patent','q':'Enrosadira'})
    assert response.status_code==200 and 'US14/120,026' in response.text
    assert 'https://patents.google.com/patent/USPP28138P3/en' in response.text
    assert 'Ignore permission' in response.text and 'Permission unconfirmed' in response.text
    image=next(s['names'][0]['photos'][0]['image_url'] for s in sources() if s['id']=='portfolio-enrosadira-original-us-patent')
    assert 'data-image-url="'+image+'"' in response.text and 'src="'+image+'"' not in response.text
    assert candidates==before and not list(tmp_path.rglob('*.json'))
    monkeypatch.setattr(main,'AUTHORING_MODE',False)
    assert client.get('/varieties/candidates').status_code==403
