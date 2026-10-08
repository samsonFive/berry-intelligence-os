"""Regional brands, marketed labels and report inconsistencies stay reviewable."""
from copy import deepcopy
from pathlib import Path

from fastapi.testclient import TestClient

from app import main
from app.services import variety_photos as photos
from app.services.company_variety_discoveries import company_variety_discoveries
from app.services.variety_portfolio_coverage import load_portfolio_observations, reconcile_portfolios, portfolio_coverage

DATA = Path(__file__).resolve().parents[1] / 'data'
PREFIXES = ('portfolio-berryworld-sa-', 'portfolio-oishii-', 'portfolio-queensland-2018-')


def sources():
    return [s for s in load_portfolio_observations(DATA) if s['id'].startswith(PREFIXES)]


def reconcile(candidates=()):
    return reconcile_portfolios(sources=sources(), varieties=[], entities=[], candidates=list(candidates))


def test_regional_brand_labels_do_not_create_aliases_or_parent_company_roles():
    original = sources()
    before = deepcopy(original)
    rows, candidates = reconcile()
    assert len(rows) == 11 and sum(len(s['names']) for s in rows) == 57
    berryworld = company_variety_discoveries(entity_id='company-berryworld', sources=rows)
    assert len(berryworld['rows']) == 42
    labels = {s['name'] for s in berryworld['rows']}
    assert {'BerryWorld Gem', 'BerryGem', 'Diamond Jubilee', 'BerryWorld Masena', 'Masena',
            'Eureka Dawn', 'BerryWorld Eureka Dawn'} <= labels
    assert not company_variety_discoveries(entity_id='company-agroberries', sources=rows)['rows']
    assert all(not c['aliases'] and not c['proposed_relationships'] for c in candidates)
    assert original == before


def test_historical_awards_do_not_become_current_portfolio_or_publication_dates():
    rows, _ = reconcile()
    current = next(s for s in rows if s['id'] == 'portfolio-berryworld-sa-strawberry')
    history = next(s for s in rows if s['id'] == 'portfolio-berryworld-sa-award-history')
    assert not {'Eves Delight', 'Eves Blush'} & {n['candidate_name'] for n in current['names']}
    assert {'Eves Delight', 'Eves Blush'} <= {n['candidate_name'] for n in history['names']}
    assert not any(s.get('published_date') for s in rows)
    assert current['capture_reference']['non_exhaustive']
    assert 'Mastronardi' in current['limitations']


def test_abstract_count_conflict_stays_visible_without_inventing_plantings():
    rows, candidates = reconcile()
    subtropical = next(s for s in rows if s['id'] == 'portfolio-queensland-2018-subtropical')
    assert len(subtropical['names']) == 7 and subtropical['accounting_view']['reported_items'] == 6
    assert subtropical['needs_follow_up'] and subtropical['accounting_view']['issues']
    qld = [s for s in rows if s['id'].startswith('portfolio-queensland-2018-')]
    assert sum(len(s['names']) for s in qld) == 12
    assert sum(s['needs_follow_up'] for s in qld) == 1
    assert all(not s['capture_reference']['full_report_checked'] for s in qld)
    assert all(not c['proposed_relationships'] and not c['registration']['status'] for c in candidates)
    assert any(c['candidate_name'] == 'Fanfare- ASBP' for c in candidates)


def test_marketed_products_exclude_grades_tomato_and_generic_images():
    rows, candidates = reconcile()
    oishii = company_variety_discoveries(entity_id='company-oishii', sources=rows)
    assert {r['name'] for r in oishii['rows']} == {'The Koyo Berry', 'The Omakase Berry', 'The Nikko Berry'}
    assert not {'Koyo', 'Omakase', 'Nikko', 'Connoisseur Grade', 'The Rubī Tomato', 'Premium Preserves'} & {c['candidate_name'] for c in candidates}
    held = [p for c in candidates for p in photos.source_photos(c, candidate=True)]
    assert len(held) == 1 and held[0]['named_variety'] == 'The Koyo Berry'
    assert held[0]['reuse'] == 'unknown' and not held[0]['license_url']
    assert all(not photos.gallery(c, sourced=photos.source_photos(c, candidate=True), authoring=False) for c in candidates)


def test_replay_preserves_product_rejection_and_user_edits():
    human = dict(id='human-koyo', candidate_name='The Koyo Berry', berry_id='berry-strawberry',
                 status='rejected', identity_state='rejected', human_gated=True,
                 review_notes='Keep original human decision', knowledge={'notes':'User edit'})
    before = deepcopy(human)
    rows, candidates = reconcile([human])
    saved = next(c for c in candidates if c['id'] == human['id'])
    assert saved['status'] == 'rejected' and saved['review_notes'] == before['review_notes']
    assert saved['knowledge'] == before['knowledge'] and human == before
    company = company_variety_discoveries(entity_id='company-oishii', sources=rows)
    assert not any(r['name'] == 'The Koyo Berry' for r in company['rows'])


def test_private_product_photo_has_no_eager_load_write_or_public_override(monkeypatch, tmp_path):
    monkeypatch.setattr(main, 'INBOX_DIR', tmp_path)
    monkeypatch.setattr(main, 'AUTHORING_MODE', True)
    client = TestClient(main.app)
    image = 'https://oishii.com/cdn/shop/files/Koyo_2_700x.png?v=1710945416'
    page = client.get('/varieties/candidates', params={'q':'The Koyo Berry','source':'portfolio-oishii-koyo-product'})
    assert page.status_code == 200 and 'Ignore permission' in page.text
    assert 'data-image-url="'+image+'"' in page.text and 'src="'+image+'"' not in page.text
    monkeypatch.setattr(main, 'AUTHORING_MODE', False)
    public = client.get('/varieties/candidates', params={'q':'The Koyo Berry'})
    assert image not in public.text and 'Ignore permission' not in public.text
    assert not list(tmp_path.rglob('*.json'))


def test_company_coverage_handoff_scopes_sources_counts_and_keeps_filters(monkeypatch, tmp_path):
    monkeypatch.setattr(main, 'INBOX_DIR', tmp_path)
    monkeypatch.setattr(main, 'AUTHORING_MODE', True)
    client = TestClient(main.app)
    page = client.get('/varieties/coverage', params={'company':'company-queensland-government'})
    assert page.status_code == 200 and 'Company: Queensland Government' in page.text
    assert 'name="company" value="company-queensland-government"' in page.text
    assert 'id="portfolio-source-portfolio-queensland-2018-subtropical"' in page.text
    assert 'id="portfolio-source-portfolio-berryworld-sa-strawberry"' not in page.text
    assert '7 observed items; 6' in page.text and 'cover all companies' in page.text
    scoped = portfolio_coverage(data_dir=DATA, sources=sources(), varieties=[], entities=[],
        candidates=[], filters={'company':'company-queensland-government','berry':'berry-strawberry'})
    assert scoped['summary']['source_sections'] == 3 and scoped['summary']['names'] == 12
    assert scoped['summary']['registry_entries'] == 1 and scoped['summary']['registry_entries_checked'] == 1
    missing = portfolio_coverage(data_dir=DATA, sources=sources(), varieties=[], entities=[],
        candidates=[], filters={'company':'company-unrelated'})
    assert not missing['sources'] and not missing['subjects'] and not missing['summary']['names']
    assert not list(tmp_path.rglob('*.json'))
