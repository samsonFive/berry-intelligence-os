"""Original images/claims remain cultivar-specific despite printed label errors."""
from copy import deepcopy
import json
from pathlib import Path

from app.services.variety_patent_references import original_patent_references
from app.services.variety_photos import source_photos, gallery
from app.services.variety_portfolio_coverage import load_portfolio_observations, reconcile_portfolios

DATA = Path(__file__).resolve().parents[1]/'data'
PREFIX = 'portfolio-plablue-original-'


def inputs():
    sources = [s for s in load_portfolio_observations(DATA) if s['id'].startswith(PREFIX)]
    varieties = [json.loads(p.read_text(encoding='utf-8')) for p in (DATA/'entities/varieties').glob('*.json')]
    return sources, varieties


def test_existing_aliases_find_distinct_originals_and_full_figures_without_approving_reuse():
    sources, varieties = inputs(); before = deepcopy((sources, varieties))
    expected = {'Blue Manila': ('Plablue 1545', 'USPP31345P2', '15.09.020', [1648, 1223]),
                'Blue Maldiva': ('Plablue 1542', 'USPP31403P2', '15.09.003', [1879, 1355])}
    urls = []
    for name, (legal, number, printed_code, pixels) in expected.items():
        target = next(v for v in varieties if v['name'] == name)
        focal = next(s for s in sources if s['source_type'] == 'plant_patent' and s['names'][0]['candidate_name'] == legal)
        reference = original_patent_references(variety=target, varieties=varieties, entities=[], candidates=[], sources=sources)
        assert [r['number'] for r in reference] == [number]
        assert reference[0]['claim_url'].endswith('#page=4') and reference[0]['figures_url'].endswith('#page=13')
        photo = source_photos(target, sources=sources, varieties=varieties)
        assert len(photo) == 1 and photo[0]['named_variety'] == legal and printed_code in photo[0]['caption']
        assert photo[0]['source_url'].endswith('#page=13') and photo[0]['image_url'].endswith('-D00009.png')
        assert photo[0]['reuse'] == 'unknown' and not photo[0]['license_url']
        assert focal['capture_reference']['image_pixels'] == pixels
        assert focal['capture_reference']['visually_reviewed_pages'] == [1, 2, 3, 4, 13]
        assert not focal['capture_reference']['all_pdf_pages_visually_reviewed']
        assert gallery(target, sourced=photo, authoring=False) == []
        assert not gallery(target, sourced=photo, authoring=True)[0]['display_image']
        urls.append(photo[0]['image_url'])
    assert len(set(urls)) == 2 and (sources, varieties) == before


def test_parents_comparators_and_misprinted_labels_do_not_inherit_focal_rights_or_photos():
    sources, varieties = inputs()
    assert len(sources) == 6 and sum(len(s['names']) for s in sources) == 15
    assert sum(len(n.get('photos', [])) for s in sources for n in s['names']) == 2
    context = [s for s in sources if s['source_type'] == 'patent_context_names']
    names = {n['candidate_name'] for s in context for n in s['names']}
    assert {'14.027.001','14.049.001','Biloxi','Star','15.09.020','15.09.003','Plablue 1542','Legacy','15.07.018'} <= names
    for source in sources:
        assert source['review_state'] == 'unreviewed' and not source['company_ids']
    for source in context:
        for row in source['names']:
            assert row['source_company_ids'] == []
            assert not any(row.get(key) for key in ('photos','grant_number','application_number','aliases','traits'))
    warnings = ' '.join(message for s in sources for message in s.get('review_warnings', []))
    assert 'print Plablue 1542' in warnings and 'Table 2 prints Legacy' in warnings and 'Figure 12 caption prints 15.07.018' in warnings
    rejected = dict(id='fixture-rejected-label', candidate_name='15.07.018', berry_id='berry-blueberry',
        status='rejected', identity_state='rejected', human_gated=True, review_notes='Retain operator decision', knowledge={'notes':'Keep this edit'})
    before = deepcopy(rejected)
    _, derived = reconcile_portfolios(sources=sources, varieties=varieties, entities=[], candidates=[rejected])
    retained = next(c for c in derived if c['id'] == rejected['id'])
    assert rejected == before and retained['identity_state'] == 'rejected' and retained['knowledge'] == before['knowledge']
