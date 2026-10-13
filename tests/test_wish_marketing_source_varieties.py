"""Historical grower mentions and market labels do not approve variety identity."""
from copy import deepcopy
from pathlib import Path

from app import main
from app.services.company_variety_discoveries import company_variety_discoveries
from app.services.variety_portfolio_coverage import load_portfolio_observations, portfolio_coverage, reconcile_portfolios

DATA=Path(__file__).resolve().parents[1]/'data'
IDS={'portfolio-wish-2019-blackberry-growers','portfolio-gap-wish-misty-redirect',
     'portfolio-gap-wish-2026-caneberry-pipeline','portfolio-gap-gempack-current-crops',
     'portfolio-gap-gempack-packaging-catalog','portfolio-gap-surexport-current-brands',
     'portfolio-gap-surexport-research','portfolio-gap-surexport-blueberry',
     'portfolio-gap-surexport-blackberry','portfolio-gap-perfection-current-crops',
     'portfolio-gap-perfection-raspberry','portfolio-gap-pairwise-blackberry-products',
     'portfolio-gap-surexport-raspberry','portfolio-gap-surexport-strawberry'}
ENTITIES=[dict(id='company-wish-farms',entity_type='company',name='Wish Farms')]

def sources():
    return [s for s in load_portfolio_observations(DATA) if s['id'] in IDS]


def test_original_grower_source_keeps_literal_names_and_conflicting_dates_separate():
    original=sources()
    before=deepcopy(original)
    rows,candidates=reconcile_portfolios(sources=original,varieties=[],entities=ENTITIES,candidates=[])
    assert len(rows)==14 and len(candidates)==4
    assert {c['candidate_name'] for c in candidates}=={'PrimeArk 45','Osage','Ouachita','Natchez'}
    source=next(s for s in rows if s['id']=='portfolio-wish-2019-blackberry-growers')
    assert source['published_date']=='2019-05-06'
    assert source['capture_reference']['article_dateline']=='2019-05-07'
    assert all('historical supply context' in n['portfolio_context'] for n in source['names'])
    assert all(not c['aliases'] and not c['proposed_relationships'] and not c['human_gated'] for c in candidates)
    assert all(not c['registration']['status'] and not c['auto_confirmed'] for c in candidates)
    assert not any(n.get('photos') for s in rows for n in s['names'])
    assert original==before


def test_redirected_cache_unnamed_trials_and_pack_labels_never_become_candidates():
    rows,candidates=reconcile_portfolios(sources=sources(),varieties=[],entities=ENTITIES,candidates=[])
    assert len([s for s in rows if s['needs_follow_up']])==13
    assert all(not s['accounting_view']['issues'] for s in rows)
    redirect=next(s for s in rows if s['id']=='portfolio-gap-wish-misty-redirect')
    assert redirect['capture_status']=='unreadable' and not redirect['names']
    assert redirect['capture_reference']['resolved_url']=='https://wishfarms.com/our-growers/'
    assert 'Pearl' in redirect['capture_reference']['cached_identity_leads_only']
    catalog=next(s for s in rows if s['id']=='portfolio-gap-gempack-packaging-catalog')
    assert catalog['capture_reference']['visually_checked_pages']==[1]
    assert catalog['capture_reference']['packaging_rows']==36
    assert catalog['capture_reference']['sheet_revision']=='Last Updated Jan 2024'
    assert not catalog.get('published_date')
    assert {r['label'] for r in catalog['accounting']['exclusions']}=={'Gem-Pack Berries','Mainland','Fresh','Red Blossom','Winter Frost'}
    assert not {'Winter Frost','Pearl','Rafiki','Seedless blackberries','Doñarosa'} & {c['candidate_name'] for c in candidates}


def test_new_reference_preserves_every_existing_derived_identity_and_user_rejection():
    all_sources=load_portfolio_observations(DATA)
    _,before=reconcile_portfolios(sources=[s for s in all_sources if s['id'] not in IDS],varieties=[],entities=ENTITIES,candidates=[])
    _,after=reconcile_portfolios(sources=all_sources,varieties=[],entities=ENTITIES,candidates=[])
    ids={(c['berry_id'],c['candidate_name']):c['id'] for c in after}
    assert all(ids[(c['berry_id'],c['candidate_name'])]==c['id'] for c in before)
    human=dict(id='human-natchez',candidate_name='Natchez',berry_id='berry-blackberry',
        status='rejected',identity_state='rejected',human_gated=True,reviewer='Analyst',
        aliases=['User alias'],registration={'application_number':'Saved number','status':'Saved status'},
        review_notes='Keep my rejection',knowledge={'notes':'User notes'})
    original=deepcopy(human)
    rows,candidates=reconcile_portfolios(sources=sources(),varieties=[],entities=ENTITIES,candidates=[human])
    saved=next(c for c in candidates if c['id']==human['id'])
    assert saved['registration']==original['registration'] and saved['aliases']==original['aliases']
    assert saved['review_notes']==original['review_notes'] and saved['knowledge']==original['knowledge']
    assert human==original
    view=company_variety_discoveries(entity_id='company-wish-farms',sources=rows)
    assert {r['name'] for r in view['rows']}=={'PrimeArk 45','Osage','Ouachita'}
    assert view['rejected_count']==1 and view['follow_up_count']==2


def test_grower_names_link_to_original_article_and_private_review_without_roles():
    rows,_=reconcile_portfolios(sources=sources(),varieties=[],entities=ENTITIES,candidates=[])
    company=company_variety_discoveries(entity_id='company-wish-farms',sources=rows)
    assert len(company['rows'])==4 and company['source_count']==3
    assert all('source=portfolio-wish-2019-blackberry-growers' in row['href'] for row in company['rows'])
    assert all('wish-farms-anticipating-june-boom-for-blackberries/' in row['sources'][0]['href'] for row in company['rows'])
    assert all(any('current growing confirmation' in note for note in row['notes']) for row in company['rows'])
    assert not company_variety_discoveries(entity_id='company-pairwise',sources=rows)['rows']


def test_read_pages_without_variety_lists_have_honest_coverage_copy(tmp_path):
    original=sources()
    before=deepcopy(original)
    coverage=portfolio_coverage(data_dir=tmp_path,sources=original,varieties=[],entities=ENTITIES,candidates=[])
    html=main.templates.env.get_template('_variety_portfolio_coverage.html').render(coverage={'portfolios':coverage})
    assert 'Partial variety coverage' in html and 'Named-variety coverage is incomplete' in html
    assert 'Only part of the source was captured' not in html and 'Partial capture' not in html
    assert 'Could not read this source' in html
    assert 'Winter Frost' in html and '36 packaging/SKU rows' in html
    assert 'Published <time datetime="2019-05-06">2019-05-06</time>' in html
    assert 'Seedless blackberries' in html
    assert original==before and not list(tmp_path.rglob('*.json'))


def test_read_market_pages_explain_that_zero_captured_names_is_not_zero_varieties(tmp_path):
    original=[s for s in sources() if s['company_ids']==['company-surexport']]
    coverage=portfolio_coverage(data_dir=tmp_path,sources=original,varieties=[],
        entities=[dict(id='company-surexport',name='Surexport',entity_type='company')],candidates=[],
        filters={'company':'company-surexport'})
    assert coverage['summary']['source_sections']==6 and coverage['summary']['names']==0
    assert coverage['summary']['unreadable_sections']==0 and coverage['summary']['follow_up_sections']==6
    html=main.templates.env.get_template('_variety_portfolio_coverage.html').render(coverage={'portfolios':coverage})
    assert 'We haven’t captured variety names in these pages.' in html
    assert 'This company may have varieties that aren’t listed here.' in html
    assert '6 source sections read' in html and 'Partial variety coverage' in html
