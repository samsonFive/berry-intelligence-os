"""Original PDF references improve source depth without creating identities or rights."""
from copy import deepcopy
import json
from pathlib import Path
import re

from fastapi.testclient import TestClient
from app import main
from app.services import variety_photos
from app.services.variety_portfolio_coverage import load_portfolio_observations, reconcile_portfolios

DATA = Path(__file__).resolve().parents[1] / 'data'
PARENT = DATA / 'imports/variety-portfolio-observations-2026-11-01-abz-current-photos/observations.json'
CURRENT = DATA / 'imports/variety-portfolio-observations-2026-11-02-abz-original-infosheets/observations.json'


def snapshots():
    return (json.loads(PARENT.read_text())['sources'], json.loads(CURRENT.read_text())['sources'])


def test_exact_original_links_and_body_provenance_do_not_invent_dates_codes_or_regions():
    parent, current = snapshots()
    originals = {row['name']: row['urls'] for source in parent for row in source['capture_reference']['infosheet_destinations']}
    assert len(originals) == 18 and len(current) == 6
    names = []
    for source in current:
        assert source['checked_on'] == '2026-11-02' and not source.get('published_date')
        assert source['review_state'] == 'unreviewed'
        assert source['url'].endswith('?hsLang=en') and '.pdf' not in source['url']
        for entry in source['capture_reference']['infosheet_destinations']:
            names.append(entry['name'])
            assert entry['urls'] == originals[entry['name']] and entry['bodies_checked']
            pdf, = entry['pdf_documents']
            assert pdf['url'] == originals[entry['name']][0]
            assert pdf['http_status'] == 200 and pdf['pages'] == 2 and pdf['bytes'] > 1000
            assert re.fullmatch('[0-9a-f]{64}', pdf['sha256'])
            assert re.fullmatch('[0-9a-f]{64}', pdf['extracted_text_sha256'])
            assert pdf['identity_pages'] == [1] and pdf['cultivation_and_publisher_disclaimer_pages'] == [2]
            assert not pdf['publication_date_established'] and not pdf['independent_corroboration']
        for row in source['names']:
            assert row['product_url'] == originals[row['candidate_name']][0]
            assert not any(row.get(key) for key in ('denomination', 'breeder_code', 'growing_regions', 'rights', 'patents'))
    assert len(names) == len(set(names)) == 18
    loaded = load_portfolio_observations(DATA)
    booklet = next(source for source in loaded if source['id'] == 'portfolio-abz-booklet')
    assert booklet['capture_status'] == 'unreadable' and not booklet['names']


def test_existing_names_photos_company_context_and_scoped_holds_are_preserved():
    parent, current = snapshots()
    previous = {source['id']: source for source in parent}
    for source in current:
        old = previous[source['id']]
        assert source['review_warnings'] == old['review_warnings']
        assert source['review_warning_scopes'] == old['review_warning_scopes']
        assert source['accounting'] == old['accounting']
        for now, before in zip(source['names'], old['names']):
            assert {key: value for key, value in now.items() if key not in {'product_url', 'portfolio_context'}} == {
                key: value for key, value in before.items() if key not in {'product_url', 'portfolio_context'}}
    latest = [source for source in load_portfolio_observations(DATA) if source['id'].startswith('portfolio-abz-') and source['id'] != 'portfolio-abz-booklet']
    _, candidates = reconcile_portfolios(sources=latest, varieties=[], entities=[], candidates=[])
    assert len(candidates) == 21
    for candidate in candidates:
        assert not candidate['auto_confirmed'] and not candidate['human_gated'] and not candidate['aliases']
        assert not candidate['proposed_relationships'] and not candidate['deployment'] and not candidate['breeder_owner']
        assert not variety_photos.gallery(candidate, sourced=variety_photos.source_photos(candidate, candidate=True), authoring=False)


def test_saved_rejection_notes_spelling_and_chosen_photo_survive_document_refresh():
    parent, current = snapshots()
    _, before = reconcile_portfolios(sources=parent, varieties=[], entities=[], candidates=[])
    target = next(row for row in before if row['candidate_name'] == 'Milan F1')
    target.update(human_gated=True, status='rejected', identity_state='rejected', review_notes='Keep my decision',
                  aliases=['My spelling'], knowledge={'notes': 'My research'}, photos=[{'operator': 'My chosen photo'}])
    immutable = deepcopy((before, current))
    rows, after = reconcile_portfolios(sources=current, varieties=[], entities=[], candidates=before)
    indexed = {row['id']: row for row in after}
    for prior in before:
        for key, value in prior.items():
            if key not in {'portfolio_sources', 'portfolio_review_warnings', 'portfolio_identity_notes'}:
                assert indexed[prior['id']][key] == value
    assert len(after) == len(before) and {row['id'] for row in after} == {row['id'] for row in before}
    assert reconcile_portfolios(sources=current, varieties=[], entities=[], candidates=after) == (rows, after)
    assert (before, current) == immutable


def test_reader_handoff_exposes_pdf_and_original_product_page_without_loading_held_images(monkeypatch, tmp_path):
    monkeypatch.setattr(main, 'INBOX_DIR', tmp_path)
    monkeypatch.setattr(main, 'AUTHORING_MODE', True)
    client = TestClient(main.app)
    response = client.get('/varieties/candidates', params={'source': 'portfolio-abz-5', 'q': 'Milan F1'})
    assert response.status_code == 200 and len(response.context['candidates']) == 1
    row = response.context['candidates'][0]
    pdf = 'https://www.abzseeds.com/hubfs/infosheets%20Milan%20-%20Online-1.pdf?hsLang=en'
    assert 'href="' + pdf + '"' in response.text and 'Name reference' in response.text
    assert 'https://www.abzseeds.com/homegrown?hsLang=en' in response.text
    assert 'PBR/PVP wording are ABZ claims' in response.text
    assert 'actual growing locations' in response.text and 'current individual rights' in response.text
    photo, = variety_photos.source_photos(row, candidate=True)
    assert 'src="' + photo['image_url'] + '"' not in response.text
    assert not list(tmp_path.rglob('*.json'))
    monkeypatch.setattr(main, 'AUTHORING_MODE', False)
    assert client.get('/varieties/candidates').status_code == 403
