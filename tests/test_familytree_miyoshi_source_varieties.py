"""Original historical names retain scope, code distinctions and human review."""
from copy import deepcopy
from pathlib import Path

from fastapi.testclient import TestClient

from app import main
from app.services.company_variety_discoveries import company_variety_discoveries
from app.services.variety_portfolio_coverage import load_portfolio_observations, reconcile_portfolios

DATA = Path(__file__).resolve().parents[1] / 'data'
ENTITIES = [dict(id='company-family-tree-farms',name='Family Tree Farms',entity_type='company'),
            dict(id='company-miyoshi-group',name='Miyoshi Group',entity_type='company')]


def sources():
    return [s for s in load_portfolio_observations(DATA)
            if s['id'].startswith(('portfolio-familytree-','portfolio-gap-familytree-',
                                   'portfolio-miyoshi-','portfolio-gap-miyoshi-','portfolio-gap-rijk-'))]


def test_historical_sheet_and_revision_dates_are_not_publication_or_growing_dates():
    original = sources()
    before = deepcopy(original)
    rows,candidates = reconcile_portfolios(sources=original,varieties=[],entities=ENTITIES,candidates=[])
    assert len(rows) == 8 and len(candidates) == 5
    assert {c['candidate_name'] for c in candidates} == {'Star','Spring High','Snow Chaser','Bluecrisp','19FAG-1'}
    assert not any(s.get('published_date') for s in rows)
    historical = next(s for s in rows if s['id'] == 'portfolio-familytree-historical-blueberry-sheet')
    assert historical['capture_reference']['document_creation_metadata'] == '2011-04-19'
    assert historical['capture_reference']['visually_checked_pages'] == [1,2]
    miyoshi = next(s for s in rows if s['id'] == 'portfolio-miyoshi-19fag1-english-sheet')
    assert miyoshi['capture_reference']['sheet_revision_date'] == '2021-03-08'
    assert miyoshi['capture_reference']['visually_checked_pages'] == [1]
    assert all(not c['human_gated'] and not c['auto_confirmed'] and not c['aliases'] for c in candidates)
    assert all(not c['proposed_relationships'] and not c['registration']['status'] for c in candidates)
    assert not any(n.get('photos') for s in original for n in s['names'])
    assert original == before


def test_later_historical_reference_keeps_existing_star_id_and_spaced_name_separate():
    fall_creek = deepcopy(next(s for s in load_portfolio_observations(DATA) if s['id'] == 'portfolio-fall-creek-blueberry'))
    fall_creek['names'] = [n for n in fall_creek['names'] if n['candidate_name'] in {'Star','Snowchaser'}]
    _,before = reconcile_portfolios(sources=[fall_creek],varieties=[],entities=ENTITIES,candidates=[])
    _,after = reconcile_portfolios(sources=[fall_creek,*sources()],varieties=[],entities=ENTITIES,candidates=[])
    old_star = next(c for c in before if c['candidate_name'] == 'Star')
    star = next(c for c in after if c['candidate_name'] == 'Star')
    assert star['id'] == old_star['id'] and star['registration'] == old_star['registration']
    assert len(star['portfolio_sources']) == 2
    names = {c['candidate_name']: c for c in after}
    assert names['Snow Chaser']['id'] != names['Snowchaser']['id']
    assert not names['Snow Chaser']['aliases'] and not names['Snowchaser']['aliases']


def test_human_rejection_and_user_registration_survive_new_reference():
    human = dict(id='human-star',candidate_name='Star',berry_id='berry-blueberry',
        status='rejected',identity_state='rejected',human_gated=True,reviewer='Analyst',
        registration={'status':'User status','application_number':'User number'},
        aliases=['User alias'],review_notes='Keep my rejection',knowledge={'notes':'User notes'})
    before = deepcopy(human)
    rows,candidates = reconcile_portfolios(sources=sources(),varieties=[],entities=ENTITIES,candidates=[human])
    star = next(c for c in candidates if c['id'] == human['id'])
    assert star['registration'] == before['registration'] and star['aliases'] == before['aliases']
    assert star['knowledge'] == before['knowledge'] and star['review_notes'] == before['review_notes']
    assert not any(r['name'] == 'Star' for r in company_variety_discoveries(entity_id='company-family-tree-farms',sources=rows)['rows'])
    assert human == before


def test_company_rows_show_original_sheet_code_and_do_not_turn_categories_into_varieties():
    rows,_ = reconcile_portfolios(sources=sources(),varieties=[],entities=ENTITIES,candidates=[])
    family = company_variety_discoveries(entity_id='company-family-tree-farms',sources=rows)
    assert {r['name'] for r in family['rows']} == {'Star','Spring High','Snow Chaser','Bluecrisp'}
    assert family['follow_up_count'] == 3
    assert all(r['sources'][0]['href'].endswith('BlueberrySalesSheet.pdf#page=1') for r in family['rows'])
    miyoshi = company_variety_discoveries(entity_id='company-miyoshi-group',sources=rows)
    assert len(miyoshi['rows']) == 1 and miyoshi['follow_up_count'] == 2
    row = miyoshi['rows'][0]
    assert row['name'] == 'Berry Pop SAKURA' and row['code'] == '19FAG-1'
    assert 'q=19FAG-1' in row['href'] and row['sources'][0]['href'].endswith('19fag1_en.pdf')
    assert 'sakura' in row['search'] and '19fag-1' in row['search']
    html = main.templates.env.get_template('_company_variety_discoveries.html').render(
        authoring_mode=True,static_build=False,company_source_varieties=miyoshi)
    assert '1 additional name to check' in html and 'from 3 source sections' in html
    assert '3 checked source sections' not in html
    assert not company_variety_discoveries(entity_id='company-unrelated',sources=rows)['rows']
    assert all(not s['accounting_view']['issues'] for s in rows)
    gaps = [s for s in rows if not s['names']]
    assert len(gaps) == 6 and all(s['needs_follow_up'] for s in gaps)
    assert sum(s['capture_status'] == 'unreadable' for s in gaps) == 3
    rijk = next(s for s in rows if s['id'] == 'portfolio-gap-rijk-corporate-crops')
    assert rijk['accounting_view']['accounted_items'] == 20


def test_private_code_and_market_label_search_is_read_only_and_public_queue_stays_closed(monkeypatch,tmp_path):
    _,candidates = reconcile_portfolios(sources=sources(),varieties=[],entities=ENTITIES,candidates=[])
    before = deepcopy(candidates)
    monkeypatch.setattr(main,'INBOX_DIR',tmp_path)
    monkeypatch.setattr(main,'AUTHORING_MODE',True)
    monkeypatch.setattr(main,'variety_candidate_universe',lambda: ([],candidates,{}))
    page = TestClient(main.app).get('/varieties/candidates',params={'q':'SAKURA','company':'company-miyoshi-group'})
    assert page.status_code == 200
    assert 'Berry Pop SAKURA' in page.text and '19FAG-1' in page.text and '19fag1_en.pdf' in page.text
    assert 'Needs identity review' in page.text and 'Not saved' in page.text
    assert 'Not yet in inbox' not in page.text and '<span class="badge">DISTINCT</span>' not in page.text
    assert 'Filing dates describe the source document' not in page.text
    assert 'data-image-url=' not in page.text and '<img src="https://miyoshi-strawberry.jp/' not in page.text
    assert candidates == before and not list(tmp_path.rglob('*.json'))
    monkeypatch.setattr(main,'AUTHORING_MODE',False)
    assert TestClient(main.app).get('/varieties/candidates').status_code == 403
