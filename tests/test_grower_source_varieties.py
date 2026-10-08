"""Grower lists retain literal identity, historical scope and private photo gates."""
from copy import deepcopy
from pathlib import Path

from fastapi.testclient import TestClient

from app import main
from app.services import variety_photos as photos
from app.services.company_variety_discoveries import company_variety_discoveries
from app.services.variety_portfolio_coverage import load_portfolio_observations, reconcile_portfolios

DATA=Path(__file__).resolve().parents[1]/'data'
IDS={'portfolio-freshkampo-english-fruit','portfolio-freshkampo-spanish-fruit','portfolio-freshkampo-kali-post',
     'portfolio-calgiant-2020-grower-update','portfolio-calgiant-2018-grower-update','portfolio-gap-calgiant-current-faq',
     'portfolio-cuna-strawberry-calendar','portfolio-cuna-raspberry-calendar','portfolio-cuna-blueberry-calendar',
     'portfolio-gap-cuna-blackberry-calendar','portfolio-cuna-cupla-page'}

def sources():
    return [s for s in load_portfolio_observations(DATA) if s['id'] in IDS]

def reconcile():
    return reconcile_portfolios(sources=sources(),varieties=[],entities=[],candidates=[])

def test_complete_lists_account_for_languages_summer_crop_and_nonberry_exclusions():
    original=sources()
    before=deepcopy(original)
    rows,candidates=reconcile()
    assert len(rows)==11 and sum(len(s['names']) for s in rows)==53
    assert all(not s['accounting_view']['issues'] for s in rows)
    assert len([s for s in rows if s['needs_follow_up']])==2
    assert len([s for s in rows if s['id']=='portfolio-cuna-strawberry-calendar'][0]['names'])==6
    assert not {'Hass','Black Mission','UC157NuP','Grande','Moras'} & {c['candidate_name'] for c in candidates}
    assert original==before

def test_literal_spelling_and_ambiguous_wording_do_not_create_approved_aliases():
    rows,candidates=reconcile()
    names={c['candidate_name']:c for c in candidates}
    for first,second in [('Biloxi','Biloxy'),('Frontera','Fronteras'),('Blue Ribbon','Blue Ribbon Great')]:
        assert names[first]['id']!=names[second]['id']
    assert 'Prime Mark' in names and 'Prime-Ark' not in names
    assert 'Kali' in names and 'Kalika' not in names and 'Rocío' in names
    assert all(not c['aliases'] and not c['human_gated'] and not c['auto_confirmed'] for c in candidates)
    assert all(not c['proposed_relationships'] and not c['registration']['status'] for c in candidates)
    assert any('Ambiguous original wording' in ref['portfolio_context'] for ref in names['Blue Ribbon Great']['portfolio_sources'])

def test_historical_newsletter_dates_are_not_current_release_or_rights_dates():
    rows,candidates=reconcile()
    dated={s['id']:s.get('published_date') for s in rows}
    assert dated['portfolio-calgiant-2020-grower-update']=='2020-07-10'
    assert dated['portfolio-calgiant-2018-grower-update']=='2018-12-18'
    assert sum(bool(value) for value in dated.values())==2
    historic=[s for s in rows if s.get('published_date')]
    assert all('Historical grower supply update' in n['portfolio_context'] for s in historic for n in s['names'])
    assert all(not c['registration']['grant_date'] and not c['registration']['expiry'] for c in candidates)

def test_all_existing_ids_and_human_registration_rejection_survive_the_new_references():
    all_sources=load_portfolio_observations(DATA)
    _,old=reconcile_portfolios(sources=[s for s in all_sources if s['id'] not in IDS],varieties=[],entities=[],candidates=[])
    _,new=reconcile_portfolios(sources=all_sources,varieties=[],entities=[],candidates=[])
    keys={(c['berry_id'],c['candidate_name']):c['id'] for c in new}
    assert all(keys[(c['berry_id'],c['candidate_name'])]==c['id'] for c in old)
    human=dict(id='human-cupla',candidate_name='Cupla',berry_id='berry-blueberry',status='rejected',
        identity_state='rejected',human_gated=True,reviewer='Analyst',review_notes='Keep rejection',
        aliases=['User alias'],registration={'status':'Saved status','application_number':'Saved number'},
        knowledge={'notes':'Saved notes'})
    before=deepcopy(human)
    rows,candidates=reconcile_portfolios(sources=sources(),varieties=[],entities=[],candidates=[human])
    saved=next(c for c in candidates if c['id']==human['id'])
    assert all(saved[k]==before[k] for k in ('aliases','registration','knowledge','review_notes','status'))
    assert 'Cupla' not in {r['name'] for r in company_variety_discoveries(entity_id='company-cuna-de-platero',sources=rows)['rows']}
    assert human==before

def test_company_handoff_includes_every_crop_name_and_keeps_sources_specific():
    rows,_=reconcile()
    for company,count in [('company-fresh-kampo',13),('company-california-giant-berry-farms',14),('company-cuna-de-platero',14)]:
        view=company_variety_discoveries(entity_id=company,sources=rows)
        assert len(view['rows'])==count
        assert all('company='+company in r['href'] and 'source=portfolio-' in r['href'] for r in view['rows'])
        assert all(r['sources'] for r in view['rows'])
    cuna=company_variety_discoveries(entity_id='company-cuna-de-platero',sources=rows)
    assert cuna['follow_up_count']==1
    portola=next(r for r in cuna['rows'] if r['name']=='Portola')
    assert portola['sources'][0]['href']=='https://www.cunadeplatero.com/fresas/'

def test_cupla_photo_is_attributed_hidden_and_never_public_or_generic_crop_photo():
    original=sources()
    before=deepcopy(original)
    _,candidates=reconcile()
    target=next(c for c in candidates if c['candidate_name']=='Cupla')
    gallery=photos.gallery(target,sourced=photos.source_photos(target,candidate=True),authoring=True)
    assert len(gallery)==1
    image=gallery[0]
    assert image['named_variety']=='Cupla' and image['berry_id']=='berry-blueberry'
    assert image['credit']=='Cuna de Platero' and image['reuse']=='unknown' and not image['display_image']
    assert image['source_url']=='https://www.cunadeplatero.com/descubre-cupla/'
    assert image['image_url'].endswith('/Recurso-11.png') and not image['license_url']
    assert not photos.gallery(target,sourced=gallery,authoring=False)
    assert sum(len(n.get('photos',[])) for s in original for n in s['names'])==1
    assert original==before

def test_cupla_private_get_offers_session_preview_without_permission_or_identity_writes(monkeypatch,tmp_path):
    _,candidates=reconcile()
    before=deepcopy(candidates)
    monkeypatch.setattr(main,'INBOX_DIR',tmp_path)
    monkeypatch.setattr(main,'AUTHORING_MODE',True)
    monkeypatch.setattr(main,'variety_candidate_universe',lambda:([],candidates,{}))
    page=TestClient(main.app).get('/varieties/candidates',params={'source':'portfolio-cuna-cupla-page','q':'Cupla','berry':'berry-blueberry'})
    assert page.status_code==200 and 'Cupla' in page.text
    image='https://www.cunadeplatero.com/wp-content/uploads/2024/10/Recurso-11.png'
    assert 'data-image-url="'+image+'"' in page.text and 'src="'+image+'"' not in page.text
    assert 'Ignore permission' in page.text and 'Permission unconfirmed' in page.text
    assert 'Needs identity review' in page.text and 'Not saved' in page.text
    assert candidates==before and not list(tmp_path.rglob('*.json'))
    monkeypatch.setattr(main,'AUTHORING_MODE',False)
    assert TestClient(main.app).get('/varieties/candidates').status_code==403
