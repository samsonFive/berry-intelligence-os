"""Original filings remain separate from marketed names, parents and trust."""
from copy import deepcopy
import json
from pathlib import Path

from app.services.variety_patent_references import original_patent_references
from app.services.variety_photos import gallery, source_photos
from app.services.variety_portfolio_coverage import load_portfolio_observations, reconcile_portfolios, _identity_pair_notes

ROOT = Path(__file__).resolve().parents[1]


def batch():
    return [s for s in load_portfolio_observations(ROOT / 'data')
            if s['id'].startswith('portfolio-raspberry-original-')]


def filings():
    return [s for s in batch() if s['source_type'] == 'plant_patent']


def test_four_original_claims_have_their_own_filing_dates_and_document_pages():
    expected = {
        'ABB 132': ('USPP35834P3', '18/445,158', '2024-05-28', '20221155', 2, 5),
        'ABB 135': ('USPP36008P3', '18/445,160', '2024-07-16', '20221158', 2, 5),
        'ABB 136': ('USPP35904P3', '18/445,159', '2024-07-02', '20221159', 3, 6),
        'ABB 128': ('USPP35872P3', '18/445,157', '2024-06-18', '20221156', 2, 5),
    }
    rows = filings()
    assert len(rows) == 4
    for source in rows:
        row = source['names'][0]
        patent, application, date, cpvo, figure, page = expected[row['candidate_name']]
        assert row['candidate_name'] == row['denomination']
        assert row['grant_number'] == patent and row['application_number'] == application
        assert row['application_date'] == '2023-05-02'
        assert row['grant_date'] == source['published_date'] == date
        capture = source['capture_reference']
        assert capture['claim_page'] == 3 and row['product_url'].endswith('#page=3')
        assert capture['claim_url'] == row['product_url']
        assert capture['fruit_figure'] == figure and capture['fruit_figure_page'] == page
        assert capture['figures_url'].endswith('#page=' + str(page))
        assert {1, 2, 3, page}.issubset(capture['visually_reviewed_pages'])
        assert capture['cpvo_priority_application'] == cpvo
        assert not capture['cpvo_grant_verified'] and not capture['current_legal_status_verified']


def test_applicant_and_marketing_names_do_not_automatically_acquire_patents_or_photos():
    actual = [json.loads((ROOT / 'data/entities/varieties' / ('variety-' + n + '.json')).read_text())
              for n in ('baridi', 'malaika', 'zawadi')]
    original = deepcopy(actual)
    all_sources = load_portfolio_observations(ROOT / 'data')
    for variety in actual:
        refs = original_patent_references(variety=variety, varieties=actual, entities=actual,
                                         candidates=[], sources=batch())
        assert refs == []
        assert source_photos(variety, sources=batch(), varieties=actual) == []
    assert actual == original
    assert all(not s['company_ids'] for s in filings())
    assert all(s['capture_reference']['reported_applicant'] == 'Allberry B.V.' for s in filings())
    notes = _identity_pair_notes(all_sources)
    assert any(messages for key, messages in notes.items() if key[1][0] == 'baridi')


def test_only_exact_legal_identity_gets_its_filing_and_photos_stay_held():
    varieties = [{'id': 'v-' + n.replace(' ', '-'), 'entity_type': 'variety', 'name': n,
                  'berry_ids': ['berry-raspberry']} for n in ('ABB 132', 'ABB 135', 'ABB 136', 'ABB 128')]
    for variety in varieties:
        refs = original_patent_references(variety=variety, varieties=varieties, entities=varieties,
                                         candidates=[], sources=batch())
        assert len(refs) == 1 and refs[0]['claim_url'].endswith('#page=3')
        photos = source_photos(variety, sources=batch(), varieties=varieties)
        assert len(photos) == 1 and photos[0]['named_variety'] == variety['name']
        assert photos[0]['reuse'] == 'unknown' and 'low-resolution' in photos[0]['caption']
        assert gallery(variety, sourced=photos, authoring=False) == []
        assert not any(p['display_image'] for p in gallery(variety, sourced=photos, authoring=True))


def test_parent_selections_do_not_inherit_focal_grants_or_figures():
    background = [s for s in batch() if s['source_type'] == 'patent_context_names']
    assert len(background) == 4 and sum(len(s['names']) for s in background) == 12
    assert all(not any(n.get(k) for k in ('application_number', 'grant_number', 'photos'))
               for s in background for n in s['names'])
    parents = {n['candidate_name'] for s in background for n in s['names']}
    assert {'22', '210001', '211157-009', '211157-6', '211150-009', '211150-9',
            'Advabertwee', 'Advabereen', 'ABB 127'} == parents
    assert all(s['review_state'] == 'unreviewed' for s in batch())
    assert sum(len(s['names']) for s in batch()) == 19


def test_existing_rejection_survives_the_new_original_reference():
    rejected = {'id': 'vcand-existing', 'candidate_name': 'ABB 128', 'berry_id': 'berry-raspberry',
                'status': 'rejected', 'identity_state': 'rejected', 'human_gated': True,
                'review_notes': 'Fixture human decision', 'knowledge': {'notes': 'User note'}}
    before = deepcopy(rejected)
    rows, candidates = reconcile_portfolios(sources=batch(), varieties=[], entities=[],
                                           candidates=[rejected])
    retained = next(c for c in candidates if c['id'] == rejected['id'])
    assert rejected == before
    assert retained['identity_state'] == 'rejected' and retained['review_notes'] == before['review_notes']
    assert retained['knowledge'] == before['knowledge']
    assert any(s['closed'] for s in rows)


def test_exact_named_breeder_photos_fill_profile_references_without_publishing_images():
    sources = [s for s in load_portfolio_observations(ROOT / 'data')
               if s['id'].startswith('portfolio-raspberry-product-photo-')]
    assert len(sources) == 2
    for source in sources:
        name = source['names'][0]['candidate_name']
        variety = json.loads((ROOT / 'data/entities/varieties' / ('variety-' + name.lower() + '.json')).read_text())
        photos = source_photos(variety, sources=sources, varieties=[variety])
        assert len(photos) == 1 and photos[0]['named_variety'] == name
        assert photos[0]['source_url'] == source['url']
        assert source['capture_reference']['image_source_label_attribute'] == 'title'
        assert source['capture_reference']['image_width'] == source['capture_reference']['image_height'] == 300
        assert source['capture_reference']['original_image_visual_reviewed']
        assert photos[0]['reuse'] == 'unknown'
        assert not any(p['display_image'] for p in gallery(variety, sourced=photos, authoring=True))
        assert gallery(variety, sourced=photos, authoring=False) == []
        assert variety['aliases'] == []
        assert not any(source['names'][0].get(k) for k in ('grant_number', 'application_number'))


def test_story_photos_reach_only_the_named_profiles_and_do_not_grant_reuse_or_rights():
    sources = [s for s in load_portfolio_observations(ROOT / 'data')
               if s['id'].startswith('portfolio-sekoya-story-fruit-')]
    expected = {'Beauty': '2012.png', 'Crunch': '2013.png', 'Grande': '2014.png',
                'Pop': '2014_2.png', 'Fiesta': '2023.png'}
    assert len(sources) == len(expected)
    varieties = [json.loads((ROOT / 'data/entities/varieties' /
                            ('variety-sekoya-' + slug.lower() + '.json')).read_text())
                 for slug in [*expected, 'Nova']]
    before = deepcopy(varieties)
    for variety in varieties:
        suffix = variety['name'].split()[-1]
        photos = source_photos(variety, sources=sources, varieties=varieties)
        if suffix == 'Nova':
            assert photos == []  # A shared platform is not an image attribution.
            continue
        assert len(photos) == 1 and photos[0]['named_variety'] == variety['name']
        assert photos[0]['image_url'].endswith('/' + expected[suffix])
        assert photos[0]['reuse'] == 'unknown' and photos[0]['license_url'] == ''
        assert gallery(variety, sourced=photos, authoring=False) == []
        assert not any(p['display_image'] for p in gallery(variety, sourced=photos, authoring=True))
        assert original_patent_references(variety=variety, varieties=varieties,
                                          entities=varieties, candidates=[], sources=sources) == []
    assert varieties == before
    assert all(s['review_state'] == 'unreviewed' for s in sources)
    assert all(s['capture_reference']['image_alt'] == '' for s in sources)
    assert all(s['capture_reference']['image_label_basis'].startswith('adjacent named paragraph')
               for s in sources)
    grande = next(s for s in sources if s['names'][0]['candidate_name'] == 'SEKOYA Grande')
    assert grande['capture_reference']['source_story_year_label'] == '2013'
