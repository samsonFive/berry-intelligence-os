"""An official product/pack catalog can still leave cultivar identity unresolved."""
from pathlib import Path
from fastapi.testclient import TestClient
from app import main
from app.services.variety_portfolio_coverage import load_portfolio_observations, portfolio_coverage, reconcile_portfolios

DATA = Path(__file__).resolve().parents[1] / 'data'
PREFIXES = ('portfolio-surexport-original-', 'portfolio-gempack-original-')
REFRESH_IDS = {'portfolio-gap-surexport-current-brands', 'portfolio-gap-surexport-strawberry',
    'portfolio-gap-surexport-raspberry', 'portfolio-gap-surexport-blueberry',
    'portfolio-gap-surexport-blackberry', 'portfolio-gap-surexport-research',
    'portfolio-gap-gempack-current-crops', 'portfolio-gap-gempack-packaging-catalog'}


def sources():
    return [s for s in load_portfolio_observations(DATA) if s['id'].startswith(PREFIXES) or s['id'] in REFRESH_IDS]


def test_entire_pack_pdf_labels_and_corporate_timeline_do_not_become_cultivars():
    rows, candidates = reconcile_portfolios(sources=sources(), varieties=[], entities=[], candidates=[])
    assert len(rows) == 12 and not candidates
    assert all(s['capture_status'] == 'partial' and s['needs_follow_up'] and not s['names'] for s in rows)
    pack = next(s for s in rows if s['id'] == 'portfolio-gap-gempack-packaging-catalog')
    assert pack['capture_reference']['sku_rows'] == 36
    assert pack['capture_reference']['printed_update_label'] == 'Jan 2024'
    assert {e['label'] for e in pack['accounting_view']['exclusions']} == {
        'Gem-Pack Berries', 'Mainland', 'Fresh', 'Red Blossom', 'Winter Frost'}
    assert pack['accounting_view']['accounted_items'] == 5 and not pack['accounting_view']['issues']
    assert 'underlying cultivar identity' in pack['limitations']
    history = next(s for s in rows if s['id'] == 'portfolio-gempack-original-history-pdf')
    assert 'California Strawberry Cultivars' in {e['label'] for e in history['accounting_view']['exclusions']}
    assert 'not automatically approved as an alias' in history['limitations']
    for s in [pack, history]:
        assert s['capture_reference']['all_pages_read']
        assert s['capture_reference']['visually_checked_pages'] == [1]
        assert len(s['capture_reference']['sha256']) == 64
        assert not s.get('published_date') and not s.get('photos')


def test_brand_program_and_scoped_faq_gaps_cannot_close_named_portfolio_coverage():
    all_rows = sources()
    home = next(s for s in all_rows if s['id'] == 'portfolio-gap-surexport-current-brands')
    assert {e['label'] for e in home['accounting']['exclusions']} == {
        'Doñarosa', 'Berry Sensations', 'Strawberry', 'Raspberry', 'Blueberry', 'Blackberry'}
    history = next(s for s in all_rows if s['id'] == 'portfolio-surexport-original-history')
    assert 'does not map PSI patent subjects' in history['limitations']
    assert history['company_ids'] == ['company-surexport']
    faq = next(s for s in all_rows if s['id'] == 'portfolio-gempack-original-faq')
    assert faq['capture_reference']['answers_read'] == 3
    assert len(faq['capture_reference']['captures']) == 3
    assert 'Other answers not enumerated' in faq['enumerated_scope']
    assert 'Company-wide locations do not locate any individual variety' in faq['limitations']
    report = portfolio_coverage(data_dir=DATA, sources=all_rows, varieties=[], entities=[], candidates=[])
    subjects = [s for s in report['subjects'] if s['sources']]
    assert len(subjects) == 2 and all(not s['checked'] and s['has_source_gaps'] for s in subjects)
    assert report['summary']['registry_entries_checked'] == 0
    assert report['summary']['follow_up_sections'] == 12 and report['summary']['names'] == 0
    assert not report['visible_candidates']


def test_added_gap_sources_leave_all_candidate_ids_and_company_associations_unchanged():
    all_rows = load_portfolio_observations(DATA)
    scoped = [s for s in all_rows if set(s['company_ids']) & {'company-surexport','company-gem-pack-berries'}]
    assert len(scoped) == len({(tuple(s['company_ids']), s['url']) for s in scoped}) == 12
    assert {s['id'] for s in scoped if s['capture_reference'].get('refresh_of_existing_section')} == REFRESH_IDS
    def candidate_set(rows):
        _, candidates = reconcile_portfolios(sources=rows, varieties=[], entities=[], candidates=[])
        return {(c['id'], c['candidate_name'], c['berry_id']) for c in candidates}
    assert candidate_set(all_rows) == candidate_set([s for s in all_rows if not s['id'].startswith(PREFIXES) and s['id'] not in REFRESH_IDS])


def test_live_company_gaps_show_originals_privately_without_public_leaks_or_writes(monkeypatch, tmp_path):
    monkeypatch.setattr(main, 'INBOX_DIR', tmp_path)
    monkeypatch.setattr(main, 'AUTHORING_MODE', True)
    client = TestClient(main.app)
    page = client.get('/varieties/coverage', params={'company': 'company-gem-pack-berries'})
    assert page.status_code == 200
    assert 'We haven’t captured variety names in these pages' in page.text
    assert 'Winter Frost' in page.text and '36 packaging/SKU rows' in page.text
    assert 'https://api.gem-packberries.com/wp-content/uploads/2024/02/product-catalog.pdf' in page.text
    assert 'Review these source names' not in page.text and 'Ignore permission' not in page.text
    assert not list(tmp_path.rglob('*.json'))
    monkeypatch.setattr(main, 'AUTHORING_MODE', False)
    public = client.get('/varieties/coverage', params={'company': 'company-gem-pack-berries'})
    assert public.status_code == 200 and 'Winter Frost' not in public.text
    assert not any(prefix in public.text for prefix in PREFIXES)
    assert not list(tmp_path.rglob('*.json'))
