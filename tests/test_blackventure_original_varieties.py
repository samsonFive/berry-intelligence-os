"""Commercial and experimental source scopes never approve identities or photos."""
from copy import deepcopy
from pathlib import Path
from fastapi.testclient import TestClient
from app import main
from app.services import variety_photos as photos
from app.services.company_variety_discoveries import company_variety_discoveries
from app.services.variety_portfolio_coverage import load_portfolio_observations,reconcile_portfolios

DATA=Path(__file__).resolve().parents[1]/'data'
PREFIX='portfolio-blackventure-original-'

def sources():
    return [s for s in load_portfolio_observations(DATA) if s['id'].startswith(PREFIX)]

def reconcile(candidates=()):
    return reconcile_portfolios(sources=sources(),varieties=[],entities=[],candidates=list(candidates))

def test_complete_panels_keep_pipeline_codes_and_crop_groups_separate_from_commercial_names():
    rows,candidates=reconcile()
    assert len(rows)==2 and len(candidates)==21
    assert all(not s['accounting_view']['issues'] and not s['needs_follow_up'] for s in rows)
    assert all(s['company_ids']==['company-black-venture-farm'] and not s.get('published_date') for s in rows)
    commercial=next(s for s in rows if s['id'].endswith('lowchill'))
    pipeline=next(s for s in rows if s['id'].endswith('pipeline'))
    assert len(commercial['names'])==10 and len(pipeline['names'])==11
    assert {n['candidate_name'] for n in pipeline['names'] if n['berry_id']=='berry-blackberry'}=={
        'PBBlack 1832-16','PBBlack1839-25','Z1843-29','Z601-169','Z1949-17'}
    assert {n['candidate_name'] for n in pipeline['names'] if n['berry_id']=='berry-strawberry'}=={
        'S1714-145','S19111-139','S19111-125'}
    assert {n['candidate_name'] for n in pipeline['names'] if n['berry_id']=='berry-blueberry'}=={
        'A1924-23','A1924-53','A1924-35'}
    assert all('Pipeline selection' in n['display_label'] and 'experimental' in n['portfolio_context'] for n in pipeline['names'])
    assert all(not c['human_gated'] and not c['auto_confirmed'] and not c['aliases'] and not c['proposed_relationships'] for c in candidates)
    assert all(not c.get('denomination') and not c.get('breeder_code') and not c['registration']['status'] for c in candidates)
    table=company_variety_discoveries(entity_id='company-black-venture-farm',sources=rows)
    assert len(table['rows'])==21 and len(table['berries'])==4
    assert sum('Pipeline selection' in r['name'] for r in table['rows'])==11
    assert all('#vcand-' in r['href'] for r in table['rows'])

def test_new_source_batch_keeps_every_old_anchor_and_analyst_fields():
    all_sources=load_portfolio_observations(DATA)
    _,old=reconcile_portfolios(sources=[s for s in all_sources if not s['id'].startswith(PREFIX)],varieties=[],entities=[],candidates=[])
    _,new=reconcile_portfolios(sources=all_sources,varieties=[],entities=[],candidates=[])
    ids={(c['berry_id'],c['candidate_name']):c['id'] for c in new}
    assert all(ids[(c['berry_id'],c['candidate_name'])]==c['id'] for c in old)
    assert len(new)==len(old)+21
    human=dict(id='operator-urani',candidate_name='Urani',berry_id='berry-blackberry',human_gated=True,
        status='reviewed',identity_state='distinct',aliases=['User spelling'],registration={'status':'My status'},
        review_notes='Keep notes',photos=[{'operator':'Keep'}])
    before=deepcopy(human)
    _,merged=reconcile([human])
    saved=next(c for c in merged if c['id']==human['id'])
    assert all(saved[k]==before[k] for k in ('status','identity_state','aliases','registration','review_notes','photos'))
    assert human==before

def test_nine_named_original_photos_are_attributed_hidden_private_and_crop_scoped():
    _,candidates=reconcile()
    named={'Urani','Amelali','Regina','Aketzali','Antonia','Lilou','Dani','Frida','Monarca'}
    for c in candidates:
        gallery=photos.gallery(c,sourced=photos.source_photos(c,candidate=True),authoring=True)
        assert len(gallery)==(1 if c['candidate_name'] in named else 0)
        for p in gallery:
            assert p['named_variety']==c['candidate_name'] and p['berry_id']==c['berry_id']
            assert p['source_url']=='https://blackventurefarm.com/#page-3'
            assert p['image_url'].startswith('https://blackventurefarm.com/_assets/media/')
            assert 'not individually credited' in p['credit'] and not p['license_url']
            assert p['reuse']=='unknown' and not p['display_image']
            assert not photos.compatible(p,dict(candidate_name=c['candidate_name'],berry_id='berry-blueberry'),candidate=True)
        assert not photos.gallery(c,sourced=gallery,authoring=False)

def test_original_photo_choice_and_source_links_never_write_permission(monkeypatch,tmp_path):
    _,candidates=reconcile()
    before=deepcopy(candidates)
    monkeypatch.setattr(main,'INBOX_DIR',tmp_path)
    monkeypatch.setattr(main,'AUTHORING_MODE',True)
    monkeypatch.setattr(main,'variety_candidate_universe',lambda:([],candidates,{}))
    client=TestClient(main.app)
    response=client.get('/varieties/candidates',params={'source':PREFIX+'lowchill','q':'Urani'})
    assert response.status_code==200 and 'https://blackventurefarm.com/#page-3' in response.text
    assert 'Ignore permission' in response.text and 'Permission unconfirmed' in response.text
    image=next(n['photos'][0]['image_url'] for s in sources() for n in s['names'] if n['candidate_name']=='Urani')
    assert 'data-image-url="'+image+'"' in response.text and 'src="'+image+'"' not in response.text
    pipeline=client.get('/varieties/candidates',params={'source':PREFIX+'pipeline','q':'A1924-35'})
    assert pipeline.status_code==200 and 'experimental selection' in pipeline.text
    assert 'Ignore permission' not in pipeline.text
    assert candidates==before and not list(tmp_path.rglob('*.json'))
    monkeypatch.setattr(main,'AUTHORING_MODE',False)
    assert client.get('/varieties/candidates').status_code==403
