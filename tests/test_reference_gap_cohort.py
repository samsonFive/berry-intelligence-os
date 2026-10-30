"""Original reference identities and dates stay narrower than nearby labels."""
import json
from pathlib import Path

from app.services.variety_patent_references import original_patent_references
from app.services.variety_portfolio_coverage import load_portfolio_observations


def sources():
    return [s for s in load_portfolio_observations(Path(__file__).resolve().parents[1]/'data')
            if s['id'].startswith('portfolio-reference-gap-')]


def test_cohort_keeps_complete_scoped_names_and_does_not_transfer_grants():
    rows=sources()
    assert len(rows)==9 and sum(len(s['names']) for s in rows)==19
    background=[s for s in rows if s['source_type']=='patent_context_names']
    assert sum(len(s['names']) for s in background)==12
    assert all(not any(n.get(k) for k in ('grant_number','application_number','photos'))
               for s in background for n in s['names'])
    assert all(not s['company_ids'] for s in rows)
    assert all(s['review_state']=='unreviewed' for s in rows)


def test_original_legal_denominations_do_not_approve_commercial_aliases():
    rows=sources()
    varieties=[{'id':'variety-kwanza','name':'Kwanza','entity_type':'variety','berry_ids':['berry-raspberry']},
        {'id':'variety-bk-6-13','name':'BK 6-13','entity_type':'variety','berry_ids':['berry-blackberry']}]
    assert all(not original_patent_references(variety=v,varieties=varieties,entities=varieties,candidates=[],sources=rows)
               for v in varieties)
    names={n['candidate_name']:n for s in rows for n in s['names']}
    assert names['Advabertwee']['grant_number']=='USPP23914P2'
    assert names['PS-BK3-17.006-13']['grant_number']=='USPP34597P2'
    assert not names['Advabertwee'].get('trade_name')
    assert not names['PS-BK3-17.006-13'].get('trade_name')


def test_application_is_not_a_grant_and_rights_registration_is_not_a_grant_date():
    rows=sources()
    nova=next(s for s in rows if s['id']=='portfolio-reference-gap-cpvo-20252277')
    assert nova['names'][0]['application_number']=='20252277'
    assert nova['names'][0]['grant_number']==nova['names'][0]['grant_date']==''
    assert nova['capture_reference']['reported_application_status']=='Active application'
    assert nova['capture_reference']['reported_title_status']=='No decision'
    ukraine=next(s for s in rows if s['id']=='portfolio-reference-gap-ukraine-raspberry-202604')
    assert not ukraine.get('published_date')
    assert {n['candidate_name'] for n in ukraine['names']}=={'AMALIA ROSSA','EROS'}
    assert all(n['grant_date']=='' and n['jurisdiction']=='UA' for n in ukraine['names'])
    assert '2026-04-17' in ukraine['names'][0]['portfolio_context']
    assert '2026-04-29' in ukraine['names'][1]['portfolio_context']
    assert ukraine['capture_reference']['visually_reviewed_pages']==[1,27]


def test_new_claim_links_open_the_inspected_original_claim_pages():
    rows=sources()
    for number,page in [('USPP23914',3),('USPP32799P2',3),('USPP34597P2',4)]:
        s=next(s for s in rows if s['id']=='portfolio-reference-gap-original-'+number.lower())
        assert s['capture_reference']['claim_page']==page
        assert s['names'][0]['product_url'].endswith('#page='+str(page))
        assert page in s['capture_reference']['visually_reviewed_pages']
        assert not s['capture_reference']['current_legal_status_verified']


def test_starting_cohort_is_not_reduced_to_successful_lookups():
    root=Path(__file__).resolve().parents[1]/'data'
    report=json.loads((root/'imports/variety-portfolio-observations-2026-10-13-reference-gap-cohort/cohort-accounting.json').read_text())
    rows=report['rows']
    assert len(rows)==len({r['profile_id'] for r in rows})==17
    assert sum(len(r['queries']) for r in rows)==23
    counts={state:sum(r['outcome']==state for r in rows) for state in {r['outcome'] for r in rows}}
    assert counts=={'original_reference_available':4,'source_name_association_requires_review':4,
        'fictional_seed_excluded':1,'reference_not_located_in_bounded_name_queries':8}
    known={s['id'] for s in load_portfolio_observations(root)}
    assert all(r.get('source_id') in known for r in rows if r.get('source_id'))
    assert all(not r['identity_approved'] and not r['current_rights_verified'] for r in rows)
    assert sum(q['matching_berry_rows'] for r in rows for q in r['queries'])==2
    assert sum(q['other_crop_rows'] for r in rows for q in r['queries'])==22
    fixture=next(r for r in rows if r['profile_id']=='variety-example-blue')
    assert fixture['queries']==[] and fixture['outcome']=='fictional_seed_excluded'
