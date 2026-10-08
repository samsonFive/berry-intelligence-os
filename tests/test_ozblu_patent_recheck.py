"""Patent subjects, historical source gaps and rejected species stay distinct."""
import json
from pathlib import Path

from fastapi.testclient import TestClient
from app import main
from app.services.variety_portfolio_coverage import load_portfolio_observations, reconcile_portfolios

DATA = Path(__file__).resolve().parents[1] / 'data'
BATCH = DATA / 'imports/variety-portfolio-observations-2026-10-07-ozblu-patent-recheck/observations.json'


def sources():
    ids = {s['id'] for s in json.loads(BATCH.read_text(encoding='utf-8'))['sources']}
    return [s for s in load_portfolio_observations(DATA) if s['id'] in ids]


def test_existing_filing_denominations_reuse_catalog_without_new_candidates():
    varieties = [json.loads(p.read_text(encoding='utf-8')) for p in (DATA/'entities/varieties').glob('*.json')]
    rows, candidates = reconcile_portfolios(sources=sources(), varieties=varieties, entities=[], candidates=[])
    named = [n for s in rows for n in s['names']]
    assert len(rows) == 11 and len(named) == 8 and not candidates
    assert {n['catalog_id'] for n in named} == {
        'variety-julieta','variety-bella','variety-magica','variety-magnifica',
        'variety-bonita','variety-elaina','variety-dina','variety-olivia'}
    assert all(n['status'] == 'catalog_match' for n in named)
    assert all(s['capture_reference']['claim_section_checked'] and
               not s['capture_reference']['current_official_rights_checked']
               for s in rows if s['names'])
    assert all(not n.get('photos') and not n.get('trade_name') for n in named)


def test_wrong_patent_species_is_excluded_instead_of_admitted_as_a_berry():
    wrong = next(s for s in sources() if s['id'] == 'portfolio-ozblu-rejected-patent-25358')
    assert not wrong['names']
    assert wrong['capture_reference']['botanical_subject'] == 'Aglaonema commutatum'
    assert wrong['accounting']['exclusions'][0]['label'] == 'KKAG201303'
    assert wrong['capture_reference']['corrected_reference'].endswith('/USPP28358P3/en')
    _, candidates = reconcile_portfolios(sources=[wrong], varieties=[], entities=[], candidates=[])
    assert not candidates


def test_changed_publisher_page_and_blank_pdf_remain_gaps_not_zero_portfolios():
    rows, _ = reconcile_portfolios(sources=sources(), varieties=[], entities=[], candidates=[])
    gaps = [s for s in rows if s['needs_follow_up']]
    assert {s['id'] for s in gaps} == {'portfolio-ozblu-old-mapping-recheck','portfolio-psg-rejoice-english-sheet-attempt'}
    assert all(not s['names'] and not s['accounting_view'] for s in gaps)
    mapping = next(s for s in gaps if s['capture_status'] == 'partial')
    assert mapping['url'].endswith('/where-we-grow/')
    assert mapping['capture_reference']['final_url'].endswith('/growing-our-blueberries/')
    assert not mapping['capture_reference']['current_mapping_found']
    assert 'Brand country cards do not locate every cultivar' in mapping['limitations']
    blank = next(s for s in gaps if s['capture_status'] == 'unreadable')
    assert not blank['capture_reference']['body_readable']
    assert 'filename is not an observed body code' in blank['limitations']


def test_private_rechecks_and_existing_patent_links_render_without_writing(monkeypatch, tmp_path):
    originals = {p:p.read_bytes() for p in (DATA/'entities/varieties').glob('*.json')}
    monkeypatch.setattr(main, 'INBOX_DIR', tmp_path)
    monkeypatch.setattr(main, 'AUTHORING_MODE', True)
    client = TestClient(main.app)
    page = client.get('/varieties/coverage?q=OZblu&berry=berry-blueberry')
    assert page.status_code == 200
    assert 'old variety table no longer appears' in page.text
    assert 'USPP28358P3/en' in page.text and 'KKAG201303' in page.text
    profile = client.get('/entities/variety/variety-bonita')
    assert profile.status_code == 200 and '/entities/patent/patent-uspp028358p3' in profile.text
    assert not list(tmp_path.rglob('*.json'))
    assert all(p.read_bytes() == body for p, body in originals.items())
    monkeypatch.setattr(main, 'AUTHORING_MODE', False)
    public = client.get('/varieties/coverage')
    assert 'portfolio-ozblu-filing-' not in public.text
    assert 'portfolio-ozblu-old-mapping-recheck' not in public.text
