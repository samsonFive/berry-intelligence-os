"""Original filings attach only to the named cultivar, never nearby varieties."""
from copy import deepcopy
import json
from pathlib import Path

from app.services.variety_patent_references import load_registry_filing_observations, original_patent_references
from app.services.variety_portfolio_coverage import load_portfolio_observations, reconcile_portfolios

ROOT = Path(__file__).resolve().parents[1]


def corpus():
    entities = [json.loads(p.read_text(encoding='utf-8')) for p in (ROOT / 'data/entities').rglob('*.json')]
    varieties = [e for e in entities if e.get('entity_type') == 'variety']
    sources = load_portfolio_observations(ROOT / 'data') + load_registry_filing_observations(ROOT / 'data')
    return entities, varieties, sources


def test_original_focal_grants_reach_five_existing_profiles_without_catalog_changes():
    entities, varieties, sources = corpus()
    before = deepcopy((varieties, sources))
    index = {v['id']: v for v in varieties}
    expected = {'crimson-night': 'USPP24949P3', 'double-gold': 'USPP24811P3', 'ponca': 'USPP33330P2',
                'sekoya-crunch': 'USPP31793P3', 'sekoya-fiesta': 'USPP36431P3'}
    for slug, grant in expected.items():
        refs = original_patent_references(variety=index['variety-' + slug], varieties=varieties,
                                          entities=entities, candidates=[], sources=sources)
        ref = next(r for r in refs if r['number'] == grant)
        assert ref['claim_url'].endswith('/' + grant + '/en#claims')
        assert ref['document_url'].endswith('#page=3' if slug in {'crimson-night', 'double-gold'} else '#page=4')
        assert ref['figures_url'].endswith('#page=4' if slug in {'crimson-night', 'double-gold'} else '#page=5')
        assert not {'current_rights', 'trusted', 'owner', 'aliases'} & ref.keys()
    assert (varieties, sources) == before and len(varieties) == 64


def test_nsg203_filing_does_not_approve_marimbella_alias_or_rights():
    entities, varieties, sources = corpus()
    selected, _ = reconcile_portfolios(sources=sources, varieties=varieties, entities=entities, candidates=[])
    focal = next(s for s in selected if s['id'] == 'portfolio-original-patent-nsg-203')['names'][0]
    assert focal['candidate_name'] == 'NSG 203' and focal['catalog_id'] is None
    marimbella = next(v for v in varieties if v['id'] == 'variety-marimbella')
    refs = original_patent_references(variety=marimbella, varieties=varieties, entities=entities, candidates=[], sources=sources)
    assert not any(r['number'] == 'USPP32162P3' for r in refs)
    assert 'NSG 203' not in marimbella.get('aliases', [])


def test_parent_and_comparison_names_keep_their_crop_without_inheriting_focal_patents():
    entities, varieties, sources = corpus()
    new = [s for s in sources if s['id'].startswith('portfolio-original-patent-')]
    parents = [s for s in new if s['source_type'] == 'historical_document_mentions']
    assert len(new) == 12 and sum(len(s['names']) for s in parents) == 29
    assert all(not n.get('grant_number') and not n.get('application_number') and not n.get('photos')
               for s in parents for n in s['names'])
    assert all(not s['capture_reference'].get('claim_url') and not s['capture_reference'].get('figures_url') for s in parents)
    double = next(s for s in parents if s['id'] == 'portfolio-original-patent-double-gold-other-names')
    assert {n['candidate_name'] for n in double['names']} == {'NY319', 'Graton Gold', 'Crimson Giant', 'Prelude', 'Caroline', 'Polka'}
    assert all(n['berry_id'] == 'berry-raspberry' for n in double['names'])
    # Duke is a discovered source name in this catalog, so use an explicit
    # test-only profile to check its future authoring cannot inherit a grant.
    duke = {'id': 'test-only-duke', 'name': 'Duke', 'entity_type': 'variety',
            'berry_ids': ['berry-blueberry'], 'aliases': []}
    refs = original_patent_references(variety=duke, varieties=[*varieties, duke], entities=entities,
                                      candidates=[], sources=sources)
    assert not any(r['number'] in {'USPP31793P3', 'USPP36431P3'} for r in refs)
