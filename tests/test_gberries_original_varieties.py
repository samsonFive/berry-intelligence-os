"""Recovered original programs/PDFs improve recall without trust writes."""
from copy import deepcopy
import json
from pathlib import Path

from fastapi.testclient import TestClient
from app import main
from app.services.company_variety_discoveries import company_variety_discoveries
from app.services.variety_portfolio_coverage import load_portfolio_observations, reconcile_portfolios

DATA=Path(__file__).resolve().parents[1]/'data'
COMPANY='company-g-berries'


def sources():
    return [s for s in load_portfolio_observations(DATA) if COMPANY in s['company_ids']]


def reconcile(candidates=()):
    return reconcile_portfolios(sources=sources(),varieties=[],entities=[],candidates=list(candidates))


def test_original_crop_selectors_and_six_complete_sheets_account_for_offerings():
    rows,candidates=reconcile()
    assert len(rows)==11 and sum(len(row['names']) for row in rows)==15
    assert len(candidates)==8
    assert {c['candidate_name'] for c in candidates}=={'Enrosadira','Dorotea','Halley','EasyStar','EasyRock','Cupla','Naike','Tafì'}
    assert all(not row['accounting_view']['issues'] for row in rows)
    assert sum(row['needs_follow_up'] for row in rows)==3
    sheets=[s for s in rows if s['id'].endswith('-sheet')]
    assert len(sheets)==6 and sum(s['capture_reference']['pages'] for s in sheets)==18
    for sheet in sheets:
        ref=sheet['capture_reference']
        assert len(ref['sha256'])==64 and ref['visually_checked_pages']==list(range(1,ref['pages']+1))
        assert not ref['rights_claim_verified'] and not ref['photo_reuse_verified']


def test_original_timeout_is_retained_but_current_retrieval_gap_is_recovered():
    path=DATA/'imports/variety-portfolio-observations-2026-10-08-niab-bayer-masia/observations.json'
    historical=next(s for s in json.loads(path.read_text(encoding='utf-8'))['sources'] if s['id']=='portfolio-g-berries-retrieval-gap')
    current=next(s for s in sources() if s['id']==historical['id'])
    assert historical['capture_status']=='unreadable' and not historical['capture_reference']['body_read']
    assert current['capture_status']=='partial' and current['capture_reference']['body_read']
    assert not current['names'] and 'no empty-portfolio conclusion' in current['limitations']


def test_company_code_search_and_original_technical_sheet_links_without_approved_aliases():
    rows,candidates=reconcile()
    view=company_variety_discoveries(entity_id=COMPANY,sources=rows)
    assert len(view['rows'])==8 and view['source_count']==11 and view['follow_up_count']==3
    for name,code,number in [('EasyStar','ALEL045',1053),('EasyRock','ALEL111',1055)]:
        row=next(r for r in view['rows'] if r['name']==name)
        assert code.casefold() in row['search'] and not row['code']
        assert len(row['sources'])==2 and any(f'/download/{number}/?' in s['href'] for s in row['sources'])
        assert '#vcand-' in row['href'] and f'q={name}' in row['href']
    assert all(not c['aliases'] and not c['registration']['status'] and not c['proposed_relationships'] for c in candidates)
    assert all(not c.get('breeder_code') and not c.get('denomination') for c in candidates)
    taf=next(c for c in candidates if c['candidate_name']=='Tafì')
    assert {s['candidate_name'] for s in taf['portfolio_sources']}=={'Tafì','Tafí'}
    assert not taf['human_gated'] and not taf['auto_confirmed']


def test_programs_comparators_and_paired_codes_do_not_become_company_offerings():
    rows,candidates=reconcile()
    names={c['candidate_name'] for c in candidates}
    assert not names & {'Naike Blueberry Club','Molari Società Agricola','Polka','Autumn Bliss','Castion','Aurora','ALEL045','ALEL111','GIL'}
    excluded=[e for row in rows for e in row['accounting_view']['exclusions']]
    assert any(e['label']=='Polka' and 'Comparative' in e['reason'] for e in excluded)
    assert not any(n.get('photos') for row in rows for n in row['names'])


def test_all_prior_candidate_anchors_and_human_fields_survive_recovery():
    all_sources=load_portfolio_observations(DATA)
    old_sources=[s for s in all_sources if not s['id'].startswith('portfolio-gberries-')]
    _,old=reconcile_portfolios(sources=old_sources,varieties=[],entities=[],candidates=[])
    _,new=reconcile_portfolios(sources=all_sources,varieties=[],entities=[],candidates=[])
    ids={(c['berry_id'],c['candidate_name']):c['id'] for c in new}
    assert all(ids[(c['berry_id'],c['candidate_name'])]==c['id'] for c in old)
    human=dict(id='operator-easystar',candidate_name='EasyStar',berry_id='berry-raspberry',status='rejected',
        identity_state='rejected',human_gated=True,reviewer='Analyst',aliases=['My label'],
        registration={'status':'User status','application_number':'User number'},review_notes='Keep rejected',knowledge={'notes':'Keep notes'})
    before=deepcopy(human)
    rows,candidates=reconcile([human])
    saved=next(c for c in candidates if c['id']==human['id'])
    assert all(saved[k]==before[k] for k in ('status','identity_state','aliases','registration','knowledge','review_notes'))
    assert not any(r['name']=='EasyStar' for r in company_variety_discoveries(entity_id=COMPANY,sources=rows)['rows'])
    assert before==human


def test_private_reader_retains_original_pdf_and_code_context_without_persistence(monkeypatch,tmp_path):
    _,candidates=reconcile()
    before=deepcopy(candidates)
    monkeypatch.setattr(main,'INBOX_DIR',tmp_path)
    monkeypatch.setattr(main,'AUTHORING_MODE',True)
    monkeypatch.setattr(main,'variety_candidate_universe',lambda:([],candidates,{}))
    client=TestClient(main.app)
    response=client.get('/varieties/candidates',params={'source':'portfolio-gberries-easystar-sheet','q':'EasyStar'})
    assert response.status_code==200 and 'ALEL045' in response.text and '/download/1053/?' in response.text
    assert 'Needs identity review' in response.text and 'Not saved' in response.text
    assert candidates==before and not list(tmp_path.rglob('*.json'))
    monkeypatch.setattr(main,'AUTHORING_MODE',False)
    assert client.get('/varieties/candidates').status_code==403
