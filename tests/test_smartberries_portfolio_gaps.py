"""Named wholesale brands and unnamed crops must not create cultivar identities."""
from pathlib import Path

from fastapi.testclient import TestClient
from app import main
from app.services.variety_portfolio_coverage import load_portfolio_observations, portfolio_coverage, reconcile_portfolios

DATA = Path(__file__).resolve().parents[1] / 'data'
PREFIX = 'portfolio-smartberries-original-'


def test_original_brands_archives_and_video_gap_do_not_change_the_candidate_universe():
    all_sources = load_portfolio_observations(DATA)
    sources = [s for s in all_sources if s['id'].startswith(PREFIX)]
    assert len(sources) == 9 and len({s['url'] for s in sources}) == 9
    report = portfolio_coverage(data_dir=DATA, sources=sources, varieties=[], entities=[], candidates=[])
    assert not report['visible_candidates']
    assert report['summary']['names'] == 0 and report['summary']['registry_entries_checked'] == 0
    assert report['summary']['follow_up_sections'] == 9
    company = next(s for s in report['subjects'] if s['sources'])
    assert not company['checked'] and company['has_source_gaps']
    assert all(s['capture_status'] == 'partial' and not s['names'] and not s.get('photos') for s in sources)
    brands = next(s for s in sources if s['id'] == PREFIX+'brands')
    assert {e['label'] for e in brands['accounting']['exclusions']} == {'Smart Berries','Betty Blues','Ruby Reds'}
    video = next(s for s in sources if s['id'] == PREFIX+'weekender-video')
    assert video['published_date'] == '2016-11-04'
    assert not video['capture_reference']['video_content_read'] and not video['capture_reference']['transcript_read']
    assert video['capture_reference']['video_url'] == 'https://www.youtube.com/embed/yx3-uN7L6M8?wmode=transparent'
    for source in sources:
        assert len(source['capture_reference']['sha256']) == 64
        assert '2026' not in source.get('published_date','')
    def keys(rows):
        _, candidates = reconcile_portfolios(sources=rows,varieties=[],entities=[],candidates=[])
        return {(c['id'],c['candidate_name'],c['berry_id']) for c in candidates}
    assert keys(all_sources) == keys([s for s in all_sources if not s['id'].startswith(PREFIX)])


def test_private_company_view_keeps_original_gaps_visible_without_public_leaks(monkeypatch,tmp_path):
    monkeypatch.setattr(main,'INBOX_DIR',tmp_path)
    monkeypatch.setattr(main,'AUTHORING_MODE',True)
    client = TestClient(main.app)
    page = client.get('/varieties/coverage',params={'company':'company-smart-berries'})
    assert page.status_code == 200
    assert 'We haven’t captured variety names in these pages' in page.text
    assert 'Betty Blues' in page.text and 'Ruby Reds' in page.text
    assert 'Video content remains unchecked' in page.text
    assert 'Review these source names' not in page.text and 'Ignore permission' not in page.text
    assert not list(tmp_path.rglob('*.json'))
    monkeypatch.setattr(main,'AUTHORING_MODE',False)
    public = client.get('/varieties/coverage',params={'company':'company-smart-berries'})
    assert public.status_code == 200 and PREFIX not in public.text and 'Betty Blues' not in public.text
    assert not list(tmp_path.rglob('*.json'))
