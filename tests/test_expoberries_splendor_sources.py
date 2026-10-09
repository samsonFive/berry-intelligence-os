"""Patent identity and unnamed portfolios remain sourced, private review leads."""
from copy import deepcopy
import json
from pathlib import Path

from fastapi.testclient import TestClient
from app import main
from app.services.variety_photos import gallery, source_photos
from app.services.variety_portfolio_coverage import load_portfolio_observations, portfolio_coverage, reconcile_portfolios

DATA=Path(__file__).resolve().parents[1]/'data'


def sources():
    return [s for s in load_portfolio_observations(DATA)
            if s['id'].startswith(('portfolio-expoberries-','portfolio-splendor-'))]


def test_original_patents_keep_exact_denominations_parents_and_historical_document_metadata():
    patents=[s for s in sources() if s['source_type']=='plant_patent']
    assert len(patents)==2
    expected={'EXPB3181':('berry-blackberry','USPP32907P2','2021-03-23',{'Kiowa','SP709'}),
              'EXPR02':('berry-raspberry','USPP32948P2','2021-04-06',{'SP804','SP821','Autumn Bliss'})}
    for source in patents:
        name,=source['names']
        berry,number,granted,parents=expected[name['candidate_name']]
        assert name['berry_id']==berry and name['denomination']==name['candidate_name']
        assert name['grant_number']==number and name['grant_date']==source['published_date']==granted
        assert name['application_date']=='2019-10-17' and name['jurisdiction']=='US'
        assert name['product_url'].endswith('.pdf') and not name.get('trade_name')
        assert {e['label'] for e in source['accounting']['exclusions']}==parents
        assert source['accounting']['observed_items']==len(parents)+1
        assert source['capture_reference']['fruit_visual_review']
        assert not source['capture_reference']['all_pdf_pages_visually_reviewed']
    rows,candidates=reconcile_portfolios(sources=patents,varieties=[],entities=[],candidates=[])
    assert {c['candidate_name'] for c in candidates}==set(expected)
    assert not any(c['human_gated'] or c['auto_confirmed'] or c['aliases'] or c['proposed_relationships'] for c in candidates)
    assert not any(c['registration']['status'] or c['registration']['official_registry_source'] for c in candidates)
    assert all(not r['accounting_view']['issues'] for r in rows)


def test_original_splendor_pages_remain_unnamed_without_brand_or_crop_photo_candidates():
    current=[s for s in sources() if 'portfolio-splendor-' in s['id']]
    assert len(current)==3 and all(s['capture_status']=='partial' and not s['names'] for s in current)
    assert {s['url'] for s in current}=={
        'https://splendorproduce.com/actualmente/','https://splendorproduce.com/nosotros/',
        'https://splendorproduce.com/productos/'}
    product=next(s for s in current if s['url'].endswith('/productos/'))
    assert product['capture_reference']['graphical_products_and_seasons_visually_checked']
    assert product['accounting']['observed_items']==6
    rows,candidates=reconcile_portfolios(sources=current,varieties=[],entities=[],candidates=[])
    assert not candidates and all(r['needs_follow_up'] for r in rows)
    assert json.loads((DATA/'entities/companies/company-splendor-produce.json').read_text())['status']=='unverified'
    assert json.loads((DATA/'entities/companies/company-expoberries.json').read_text())['status']=='unverified'


def test_expoberries_blueberry_filter_cannot_borrow_rubus_patents():
    report=portfolio_coverage(data_dir=DATA,sources=sources(),varieties=[],entities=[dict(
        id='company-expoberries',name='Expoberries',entity_type='company',berry_ids=['berry-blueberry','berry-blackberry','berry-raspberry'])],
        candidates=[],filters={'company':'company-expoberries','berry':'berry-blueberry'})
    assert len(report['subjects'])==1
    assert report['subjects'][0]['source_status']=='not_started'
    assert not report['sources'] and report['summary']['registry_entries_checked']==0


def test_saved_identity_registration_and_photo_choices_survive_patent_provenance():
    human=dict(id='operator-expr02',candidate_name='EXPR02',berry_id='berry-raspberry',
        status='reviewed',identity_state='distinct',human_gated=True,reviewer='Analyst',
        review_notes='Keep separate',aliases=['User label'],registration={'status':'Operator status'},
        knowledge={'notes':'User notes'},photos=[{'operator':'User photo'}])
    original=deepcopy(human)
    _,candidates=reconcile_portfolios(sources=sources(),varieties=[],entities=[],candidates=[human])
    row=next(c for c in candidates if c['id']==human['id'])
    assert human==original
    for field in ('review_notes','reviewer','aliases','registration','knowledge','photos','identity_state'):
        assert row[field]==original[field]
    assert any(r.get('grant_number')=='USPP32948P2' for r in row['portfolio_sources'])


def test_exact_fruit_photos_require_session_choice_and_do_not_write_or_leak(monkeypatch,tmp_path):
    _,candidates=reconcile_portfolios(sources=sources(),varieties=[],entities=[],candidates=[])
    assert len(candidates)==2
    for candidate in candidates:
        photo,=source_photos(candidate,candidate=True)
        assert photo['reuse']=='unknown' and photo['kind']=='fruit'
        assert photo['named_variety']==candidate['candidate_name']
        assert not gallery(candidate,sourced=[photo],authoring=False)
    monkeypatch.setattr(main,'INBOX_DIR',tmp_path)
    monkeypatch.setattr(main,'AUTHORING_MODE',True)
    monkeypatch.setattr(main,'variety_candidate_universe',lambda:([],candidates,{}))
    before=deepcopy(candidates)
    page=TestClient(main.app).get('/varieties/candidates',params={'q':'EXPR02','berry':'berry-raspberry'})
    assert page.status_code==200
    assert 'USPP32948P2' in page.text and 'Original claim ↗' in page.text and 'Ignore permission' in page.text
    assert 'data-image-url="https://patentimages.storage.googleapis.com/' in page.text
    assert '<img src="https://patentimages.storage.googleapis.com/' not in page.text
    assert before==candidates and not list(tmp_path.rglob('*.json'))
    monkeypatch.setattr(main,'AUTHORING_MODE',False)
    assert TestClient(main.app).get('/varieties/candidates').status_code==403
