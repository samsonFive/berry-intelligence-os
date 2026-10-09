"""Original patent subjects do not turn comparator mentions into company releases."""
from copy import deepcopy
from pathlib import Path

from fastapi.testclient import TestClient
from app import main
from app.services.variety_photos import gallery, source_photos
from app.services.variety_portfolio_coverage import load_portfolio_observations, portfolio_coverage, reconcile_portfolios

DATA=Path(__file__).resolve().parents[1]/'data'
PROGRAM='breeding_program-atlantic-blue-royal-berries'


def sources():
    return [s for s in load_portfolio_observations(DATA)
            if s['id'].startswith(('portfolio-royalberries-patent-','portfolio-cas-strawberry-'))]


def test_patent_subjects_keep_literal_names_dates_and_account_for_comparators():
    patents=[s for s in sources() if s['source_type']=='plant_patent']
    assert len(patents)==12
    expected={'RB A063':'USPP34718P3','RB A097':'USPP34719P3','RB A140':'USPP36024P2',
        'Rocio':'USPP20374P2','Romero':'USPP20373P2','Sevilla':'USPP21180P3',
        'Alba':'USPP21182P3','Celeste':'USPP20807P3','Magna':'USPP20806P3',
        'Corona':'USPP21153P3','Altair':'USPP20830P3','Lucero':'USPP21072P3'}
    for source in patents:
        name,=source['names']
        assert source['company_ids']==[PROGRAM] and source['berry_ids']==['berry-blueberry']
        assert name['denomination']==name['candidate_name'] and name['grant_number']==expected[name['candidate_name']]
        assert name['jurisdiction']=='US' and name['grant_date']==source['published_date']
        assert name['product_url'].endswith('.pdf') and not name.get('trade_name')
        assert source['capture_reference']['heading_description_and_claim_read']
        assert not source['capture_reference']['all_pdf_pages_visually_reviewed']
        assert source['accounting']['observed_items']==1+len(source['accounting']['exclusions'])
    rows,candidates=reconcile_portfolios(sources=patents,varieties=[],entities=[],candidates=[])
    assert {c['candidate_name'] for c in candidates}==set(expected)
    assert not {'S124','New Hanover','Suziblue','Windor','Millenia','FL 98-19'} & {c['candidate_name'] for c in candidates}
    assert all(not r['accounting_view']['issues'] for r in rows)
    assert all(not c['human_gated'] and not c['aliases'] and not c['proposed_relationships']
        and not c['registration']['status'] and not c['registration']['official_registry_source'] for c in candidates)
    newer=next(s for s in patents if s['names'][0]['candidate_name']=='RB A140')['names'][0]
    assert (newer['application_number'],newer['application_date'],newer['grant_date'])==('18/523,419','2023-11-29','2024-07-23')


def test_priority_claims_and_source_typography_do_not_create_aliases_or_registry_grants():
    by_name={s['names'][0]['candidate_name']:s for s in sources() if s['names']}
    assert by_name['RB A063']['capture_reference']['cpvo_priority_claim']=='2021/0331'
    assert by_name['RB A097']['capture_reference']['cpvo_priority_claim']=='2021/0333'
    for name in ('RB A063','RB A097','Rocio','Romero','Alba','Magna'):
        assert by_name[name]['review_warnings']
    assert all(not by_name[name]['names'][0].get('breeder_code') for name in ('Rocio','Romero'))
    assert 'SO1-29-01' in by_name['Rocio']['names'][0]['portfolio_context']


def test_cas_research_has_no_cultivar_releases_and_does_not_borrow_another_institute():
    source,=[s for s in sources() if s['id'].startswith('portfolio-cas-')]
    assert source['company_ids']==['company-institute-of-botany-cas']
    assert source['berry_ids']==['berry-strawberry'] and source['published_date']=='2021-06-04'
    assert source['capture_status']=='partial' and not source['names']
    assert {'NCED5','ABAR','AREB1','MTA','MTB'} <= {e['label'] for e in source['accounting']['exclusions']}
    assert 'Wuhan' in source['limitations']
    rows,candidates=reconcile_portfolios(sources=[source],varieties=[],entities=[],candidates=[])
    assert not candidates and rows[0]['needs_follow_up']
    report=portfolio_coverage(data_dir=DATA,sources=sources(),varieties=[],entities=[],candidates=[],
        filters={'company':PROGRAM,'berry':'berry-strawberry'})
    assert not report['sources'] and not report['subjects'] and report['summary']['names']==0


def test_human_aliases_registration_notes_and_photo_choices_win_on_replay():
    human=dict(id='operator-rb-a063',candidate_name='RB A063',berry_id='berry-blueberry',
        status='reviewed',identity_state='distinct',human_gated=True,reviewer='Analyst',
        review_notes='Preserve operator decision',aliases=['Operator label'],
        registration={'status':'User status'},photos=[{'operator':'Photo choice'}],knowledge={'notes':'User notes'})
    original=deepcopy(human)
    _,candidates=reconcile_portfolios(sources=sources(),varieties=[],entities=[],candidates=[human])
    result=next(c for c in candidates if c['id']==human['id'])
    assert original==human
    for field in ('review_notes','aliases','registration','photos','knowledge','identity_state'):
        assert result[field]==original[field]
    assert any(r.get('grant_number')=='USPP34718P3' for r in result['portfolio_sources'])


def test_only_named_visually_checked_figures_enter_the_private_session_gallery():
    _,candidates=reconcile_portfolios(sources=sources(),varieties=[],entities=[],candidates=[])
    photos={c['candidate_name']:source_photos(c,candidate=True) for c in candidates}
    assert {name for name,p in photos.items() if p}=={'RB A063','RB A097','RB A140'}
    for candidate in candidates:
        for photo in photos[candidate['candidate_name']]:
            assert photo['named_variety']==candidate['candidate_name'] and photo['kind']=='fruit'
            assert photo['reuse']=='unknown' and 'monochrome' in photo['caption']
            assert not gallery(candidate,sourced=[photo],authoring=False)


def test_source_and_claim_handoff_is_visible_without_get_writes_or_public_leakage(monkeypatch,tmp_path):
    _,candidates=reconcile_portfolios(sources=sources(),varieties=[],entities=[],candidates=[])
    monkeypatch.setattr(main,'INBOX_DIR',tmp_path)
    monkeypatch.setattr(main,'AUTHORING_MODE',True)
    corpus={'mention_count':0,**{key:[] for key in ('already_canonical','already_candidate',
        'candidates','possible_aliases','unresolved','exclusions')}}
    monkeypatch.setattr(main,'variety_candidate_universe',lambda:([],candidates,corpus))
    page=TestClient(main.app).get('/varieties/candidates',params={'q':'RB A063','berry':'berry-blueberry'})
    assert page.status_code==200 and 'USPP34718P3' in page.text
    assert 'Original claim ↗' in page.text and 'Ignore permission' in page.text
    assert 'CPVO' in page.text and '2022-11-08' in page.text
    assert '<img src="https://patentimages.storage.googleapis.com/' not in page.text
    assert not list(tmp_path.rglob('*.json'))
    monkeypatch.setattr(main,'AUTHORING_MODE',False)
    assert TestClient(main.app).get('/varieties/candidates').status_code==403
    public=TestClient(main.app).get('/varieties/coverage')
    assert public.status_code==200 and 'portfolio-royalberries-patent-' not in public.text
    assert not list(tmp_path.rglob('*.json'))
