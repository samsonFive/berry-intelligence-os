"""National history must not become active rights or an automatic name bridge."""
from copy import deepcopy
import json
from pathlib import Path

from app import main
from app.services.variety_photos import gallery, source_photos
from app.services.variety_photo_review import photo_identity_reviews
from app.services.variety_patent_references import original_patent_references
from app.services.variety_portfolio_coverage import load_portfolio_observations, reconcile_portfolios

DATA=Path(__file__).resolve().parents[1]/'data'
PREFIX='portfolio-national-'


def inputs():
    vs=[json.loads(p.read_text(encoding='utf-8'))for p in sorted((DATA/'entities/varieties').glob('*.json'))]
    sources=load_portfolio_observations(DATA)
    return vs,sources,[s for s in sources if s['id'].startswith(PREFIX)]


def test_accepted_filed_recommended_withdrawn_and_expired_stages_keep_their_actual_dates():
    _,_,cohort=inputs()
    assert len(cohort)==19 and sum(len(s['names'])for s in cohort)==69
    sa=next(s for s in cohort if s['id'].endswith('applications_received-strawberry'))
    row=next(n for n in sa['names']if n['candidate_name']=='Plared 15121')
    assert row['application_number']=='PT 10534' and row['application_date']==row['grant_number']==row['grant_date']==''
    assert 'Date accepted 2025-03-06' in row['portfolio_context'] and sa['published_date']=='2025-06-20'
    ma=next(s for s in cohort if s['id'].endswith('applications_filed-strawberry'))
    assert 'published_date'not in ma and ma['capture_reference']['publication_period']=='2021-04'
    assert next(n for n in ma['names']if n['candidate_name']=='PLARED 15121')['application_date']=='2020-10-26'
    proposed=next(s for s in cohort if s['id'].endswith('proposed_for_protection-strawberry'))
    assert all(not n['grant_number']and not n['grant_date']for n in proposed['names'])
    assert all('2021-04-23' in n['portfolio_context']for n in proposed['names'])
    withdrawn=next(s for s in cohort if s['id'].startswith('portfolio-national-ma')and s['id'].endswith('applications_withdrawn-raspberry'))
    assert all('withdrawal date is not given' in n['portfolio_context']for n in withdrawn['names'])
    ar=next(s for s in cohort if s['id']=='portfolio-national-ar-2026-resolution47-plared')
    assert ar['published_date']=='2026-03-20' and ar['capture_reference']['resolution_date']=='2026-01-30'
    assert all(not n['application_number']and not n['grant_number']and not n['grant_date']for n in ar['names'])
    assert ar['capture_reference']['direct_http_error']=='ConnectTimeout' and 'Article 2' in ar['limitations']
    unavailable=next(s for s in cohort if s['capture_status']=='unreadable')
    assert unavailable['names']==[]
    assert all(not s['company_ids']and s['review_state']=='unreviewed'for s in cohort)


def test_duplicate_printed_grant_numbers_and_literal_codes_remain_distinct():
    _,_,cohort=inputs();before=deepcopy(cohort)
    names=[n for s in cohort for n in s['names']]
    collision=[n for n in names if n.get('grant_number')=='ZA 20258459']
    assert {(n['candidate_name'],n['berry_id'],n['application_number'])for n in collision}=={
        ('Columbia Giant','berry-blackberry','PT 9084'),('EMR 20172','berry-raspberry','PT 9415')}
    repeated=[n for n in names if n.get('grant_number')=='ZA 20258418']
    assert {n['candidate_name']for n in repeated}=={'T111-519','T112-219'}
    assert len({n['application_number']for n in repeated})==2
    assert any(n['candidate_name']=='FF11-118'for n in names)
    assert not any(n['candidate_name']=='FC11-118'for n in names)
    assert any(n['candidate_name']=='PS-08 019-25'for n in names)
    rows,candidates=reconcile_portfolios(sources=cohort,varieties=[],entities=[],candidates=[])
    assert {n['candidate_name']for s in rows for n in s['names']if n.get('grant_number')=='ZA 20258418'}=={'T111-519','T112-219'}
    assert all(not c['auto_confirmed']for c in candidates)and cohort==before


def test_new_usda_name_pair_holds_the_existing_photo_without_deleting_user_details_or_transferring_a_grant():
    vs,sources,cohort=inputs();target=next(v for v in vs if v['id']=='variety-kwanza')
    before=deepcopy((target,sources))
    prior=[s for s in sources if not s['id'].startswith(PREFIX)]
    old=source_photos(target,sources=prior,varieties=vs)
    assert len(old)==1 and source_photos(target,sources=sources,varieties=vs)==[]
    held=photo_identity_reviews(target,sources=sources,varieties=vs)
    assert len(held)==1 and 'q=Kwanza' in held[0]['review_href']and 'image_url'not in held[0]
    assert not original_patent_references(variety=target,varieties=vs,entities=vs,candidates=[],sources=sources)
    saved={**old[0],'caption':'My existing photo caption'}
    result=gallery(target,sourced=[],profile={'revision':8,'variety_photo_overrides':{old[0]['id']:saved}},authoring=True)
    assert len(result)==1 and result[0]['caption']=='My existing photo caption'and not result[0]['display_image']
    assert gallery(target,sourced=old,authoring=False)==[]
    assert (target,sources)==before and target['aliases']==[]
    abstract=next(s for s in cohort if s['id'].endswith('raspberry-name-pairs'))
    assert len(abstract['names'])==10 and sum(bool(n.get('trade_name'))for n in abstract['names'])==4


def test_expired_reference_remains_historical_and_is_defensively_excluded_from_public_output():
    _,_,cohort=inputs()
    target={'id':'fixture-camarillo','entity_type':'variety','name':'Camarillo','aliases':[],'berry_ids':['berry-strawberry']}
    refs=original_patent_references(variety=target,varieties=[target],entities=[target],candidates=[],sources=cohort)
    assert len(refs)==1 and refs[0]['number']=='ZA 20053234'
    assert refs[0]['recorded_status'].startswith('Protection expired')and '2025-01-10' in refs[0]['context']
    assert 'current status not verified' in refs[0]['recorded_status']
    template=main.templates.env.get_template('_variety_patent_references.html')
    for authoring,static in [(False,False),(False,True),(True,True)]:
        html=template.render(variety_original_patents=refs,authoring_mode=authoring,static_build=static)
        assert 'ZA 20053234'not in html and 'Protection expired'not in html
