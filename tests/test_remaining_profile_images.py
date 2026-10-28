"""Existing aliases locate the right figures; comparisons never inherit rights."""
from copy import deepcopy
import json
from pathlib import Path

from app.services.variety_patent_references import original_patent_references
from app.services.variety_photos import source_photos, gallery
from app.services.variety_portfolio_coverage import load_portfolio_observations, reconcile_portfolios

DATA = Path(__file__).resolve().parents[1] / 'data'
PREFIX = 'portfolio-remaining-profile-images-'


def inputs():
    sources = [s for s in load_portfolio_observations(DATA) if s['id'].startswith(PREFIX)]
    varieties = [json.loads(p.read_text(encoding='utf-8')) for p in (DATA/'entities/varieties').glob('*.json')]
    return sources, varieties


def test_eureka_and_opi_keep_their_own_legal_identity_and_eterna_does_not_gain_a_patent():
    sources, varieties = inputs(); original = deepcopy(varieties)
    expected = {'Eureka': ('USPP25432P3', 4, 'USPP025432-20150414-D00002.png'),
                'Opi': ('USPP23572P3', 3, 'USPP023572-20130430-D00002.png'),
                'Eterna': ('', 0, 'Eterna.png')}
    for name, (grant, page, image) in expected.items():
        target = next(v for v in varieties if v['name'] == name)
        refs = original_patent_references(variety=target, varieties=varieties, entities=[], candidates=[], sources=sources)
        assert [r['number'] for r in refs] == ([grant] if grant else [])
        if grant:
            assert refs[0]['claim_url'].endswith('#page='+str(page))
        photos = source_photos(target, sources=sources, varieties=varieties)
        assert len(photos) == 1 and photos[0]['image_url'].endswith(image)
        assert photos[0]['reuse'] == 'unknown' and not photos[0]['license_url']
        assert gallery(target, sourced=photos, authoring=False) == []
        assert not gallery(target, sourced=photos, authoring=True)[0]['display_image']
    # Even a future separately authored Kirra profile cannot inherit Eterna's image.
    kirra = dict(id='fixture-future-kirra', name='Kirra', entity_type='variety', berry_ids=['berry-blueberry'])
    assert source_photos(kirra, sources=sources, varieties=[*varieties, kirra]) == []
    assert varieties == original


def test_correction_and_all_other_names_stay_separate_from_focal_grants_photos_and_aliases():
    sources, varieties = inputs()
    assert len(sources) == 7 and sum(len(s['names']) for s in sources) == 13
    names = {n['candidate_name'] for s in sources for n in s['names']}
    assert {'M08-14-03', 'S02-25-05', 'S03-08-02', 'C99-42', 'CO3-158', 'Jewel', 'Snowchaser', 'Kirra'} <= names
    for source in sources:
        assert source['review_state'] == 'unreviewed' and not source['company_ids']
        if source['id'].endswith(('-context', '-correction')):
            for name in source['names']:
                assert name['source_company_ids'] == []
                assert not any(name.get(k) for k in ('grant_number','application_number','photos'))
    correction = next(s for s in sources if s['id'].endswith('-correction'))
    assert correction['published_date'] == '2016-03-08' and correction['url'].endswith('#page=9')
    assert correction['names'][0]['candidate_name'] == 'C99-42'
    assert 'not a new variety release' in correction['names'][0]['portfolio_context']
    # Retained operator rejection remains authoritative when this provenance arrives.
    rejected = dict(id='fixture-rejected-parent', candidate_name='M08-14-03', berry_id='berry-blueberry',
                    status='rejected', identity_state='rejected', human_gated=True,
                    review_notes='Fixture operator decision', knowledge={'notes':'Retain this edit'})
    before=deepcopy(rejected)
    _, derived = reconcile_portfolios(sources=sources, varieties=varieties, entities=[], candidates=[rejected])
    retained = next(c for c in derived if c['id'] == rejected['id'])
    assert rejected == before and retained['identity_state'] == 'rejected'
    assert retained['review_notes'] == before['review_notes'] and retained['knowledge'] == before['knowledge']
