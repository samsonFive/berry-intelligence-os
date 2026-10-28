"""Actual filing subjects, comparison photographs and claim links stay separate."""
from copy import deepcopy
import json
from pathlib import Path

from app.services.variety_patent_references import original_patent_references
from app.services.variety_photos import gallery,source_photos
from app.services.variety_portfolio_coverage import load_portfolio_observations,reconcile_portfolios

DATA=Path(__file__).resolve().parents[1]/'data'
PREFIX='portfolio-original-filing-figures-'
def inputs():
    sources=[s for s in load_portfolio_observations(DATA)if s['id'].startswith(PREFIX)]
    varieties=[json.loads(p.read_text(encoding='utf-8'))for p in (DATA/'entities/varieties').glob('*.json')]
    return sources,varieties

def test_comparison_photos_do_not_give_a_catalog_variety_the_other_subjects_claim_or_image_permission():
    sources,varieties=inputs();before=deepcopy(varieties)
    expected={'Bella':'USPP26173P3','Bonita':'USPP28358P3','Dina':'USPP33138P3',
        'Elaina':'USPP30934P3','Julieta':'USPP25858P3','Magnifica':'USPP27142P3','Olivia':'USPP32897P3'}
    for label,number in expected.items():
        variety=next(v for v in varieties if v['name']==label)
        refs=original_patent_references(variety=variety,varieties=varieties,entities=[],candidates=[],sources=sources)
        assert [r['number']for r in refs]==[number]
        assert refs[0]['claim_url'].endswith('#page='+str(next(s for s in sources
            if s['id']==refs[0]['source_id'])['capture_reference']['claim_page']))
        photos=source_photos(variety,sources=sources,varieties=varieties)
        assert photos and gallery(variety,sourced=photos,authoring=False)==[]
        held=gallery(variety,sourced=photos,authoring=True)
        assert all(p['reuse']=='unknown'and not p['license_url']and not p['display_image']for p in held)
    comparison=next(s for s in sources if s['id']==PREFIX+'bonita-context')['names']
    other=next(n for n in comparison if n['candidate_name']=='EB 8-46')
    assert 'on the right' in other['photos'][0]['caption']
    assert not other.get('grant_number')and not other.get('source_company_ids')
    assert varieties==before

def test_later_comparisons_and_inconsistent_labels_survive_without_becoming_aliases_or_focal_patents():
    sources,varieties=inputs();before=deepcopy(varieties)
    observed={n['candidate_name']for s in sources for n in s['names']}
    assert {'NS 15-5','NS 15-22','NS 16-15','Ivanhoe','Darrow','Patriot','Heerma',
        'Bluetta','Concord','Burlington',"O'Neal",'EB 9-42','EB 8-42','BB-2','BB 2'}<=observed
    for source in sources:
        if source['source_type']=='plant_patent':
            # Candidate disclosures use product_url for their Original claim link.
            assert source['names'][0]['product_url']==source['capture_reference']['claim_url']
        if source['source_type']=='patent_context_names':
            assert not source['company_ids']
            assert all(not n.get('grant_number')and not n.get('application_number')
                and n['source_company_ids']==[]for n in source['names'])
    rows,derived=reconcile_portfolios(sources=sources,varieties=varieties,entities=[],candidates=[])
    unresolved=next(r for r in derived if r['candidate_name']=='EB 9-42')
    assert not unresolved.get('candidate_canonical_match')and not unresolved['human_gated']
    assert any('prints EB 9-42 once'in warning for warning in unresolved['portfolio_review_warnings'])
    elaina=next(s for s in rows if s['id']==PREFIX+'elaina')
    assert not elaina.get('review_warnings')
    assert varieties==before
