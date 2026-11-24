from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from app import viewer_export_routes as routes
from app.services import viewer_reports, viewer_export as exports
from app.services.report_builder import reports_store
from app.viewer_assets.static_site import build_site, clean_html, filename


def workspace():
    return exports.normalize_workspace({**exports.empty_workspace(), 'as_of': '2026-11-23', 'directory': {
        'companies': [{'id': 'company-a', 'name': 'Alpine', 'country': 'Spain', 'berries': ['blueberry'], 'tier': 'tier-3'},
                      {'id': 'company-b', 'name': 'Bay', 'country': 'Chile', 'berries': ['strawberry']}],
        'varieties': [{'id': 'variety-a', 'name': 'Arrow', 'berry': 'blueberry', 'company_ids': ['company-a', 'company-b']}]
    }})


def test_all_pages_are_real_html_with_inline_css_and_no_active_dependencies():
    files = build_site(workspace())
    assert {'index.html', 'varieties.html', 'projects.html', 'reports.html', 'project-template.html'} <= files.keys()
    for name, body in files.items():
        if name.endswith('.html'):
            assert b'<style>' in body and b"script-src 'none'" in body
            assert b'<script' not in body.lower() and b'<link' not in body.lower()
            assert b'onclick=' not in body.lower() and b'<form' not in body.lower()


def test_corporate_tiers_are_local_and_variety_rows_match_any_associated_company():
    w = workspace()
    copy = deepcopy(w)
    corp = {'schema_version': 1, 'kind': 'corporate_site', 'tiers': {'company-a': 'tier-1', 'company-b': 'tier-2'}}
    files = build_site(w, corp)
    assert b'data-tiers="tier-1 tier-2"' in files['varieties.html']
    assert b'data-tiers="tier-1"' in files['index.html']
    assert b'data-tiers="unassigned"' in build_site(w)['index.html']
    assert w == copy


def test_missing_company_or_flavor_identity_blocks_instead_of_dropping_corporate_data():
    with pytest.raises(ValueError, match='known company'):
        build_site(workspace(), {'schema_version': 1, 'kind': 'corporate_site', 'tiers': {'deleted': 'tier-1'}})
    with pytest.raises(ValueError, match='known variety'):
        build_site(workspace(), flavor={'schema_version': 1, 'kind': 'flavor', 'scores': [{'variety_id': 'deleted', 'panel': 'panel-1'}]})


def test_flavor_zero_is_preserved_and_panels_are_never_summarized():
    flavor = {'schema_version': 1, 'kind': 'flavor', 'scores': [
        {'variety_id': 'variety-a', 'panel': p, 'overall_liking': 0, 'taste': 1, 'texture': 2, 'appearance': 3, 'brix': 0, 'acidity': 0}
        for p in ('panel-1', 'panel-2', 'panel-3', 'panel-4')]}
    files = build_site(workspace(), flavor=flavor)
    assert all(p.encode() in files['flavor.html'] for p in ('panel-1', 'panel-2', 'panel-3', 'panel-4'))
    assert b'<td>0</td>' in files['flavor.html']
    assert 'flavor.html' not in build_site(workspace())


def test_project_pages_support_native_controls_and_remove_active_embeds():
    corp = {'schema_version': 1, 'kind': 'corporate_site', 'projects': [{'id': 'project-a', 'title': 'Trial tracker',
        'owner': 'Corporate owner', 'tasks': [{'title': 'Milestone one', 'done': True}],
        'html': '<details><summary>Notes</summary><p>Keep this</p></details><script>PRIVATE_SCRIPT</script><iframe src="https://example.com"></iframe><style>body{display:none}</style>'}]}
    files = build_site(workspace(), corp)
    page = files[filename('project', 'project-a')]
    assert b'<input type="checkbox" checked>' in page and b'<details>' in page
    assert b'Keep this' in page and b'PRIVATE_SCRIPT' not in page and b'<iframe' not in page
    assert b'body{display:none}' not in page and b'temporary visual marks' in page
    assert b'Corporate owner' not in files['index.html']


def test_report_and_project_html_cannot_add_remote_assets_or_event_handlers():
    result = clean_html('<p onclick="alert(1)" style="color:red">Text</p><img src="https://example.com/tracker"><a href="javascript:alert(1)">Bad</a><a href="https://example.com/source">Source</a>')
    assert 'onclick' not in result and 'javascript' not in result and '<img' not in result
    assert 'style="color:red"' in result and 'href="https://example.com/source"' in result


@pytest.fixture
def reports(tmp_path):
    root = tmp_path / 'reports'
    root.mkdir()
    (root / 'one.html').write_text('<h1>Finished findings</h1><script>SECRET_SCRIPT</script><p>Useful findings</p>')
    (root / 'one.pdf').write_bytes(b'%PDF-1.4\nfixture')
    (root / 'library.json').write_text(json.dumps({'reports': [{'id': 'one', 'title': 'Finished report', 'published_date': '2026-11-23',
        'berry_id': 'berry-blueberry', 'page_count': 1, 'files': {'html': 'one.html', 'pdf': 'one.pdf'}}]}))
    return SimpleNamespace(INBOX_DIR=tmp_path / 'inbox', _report_library_roots=lambda: (root,), unified_information=lambda **k: [])


def test_finished_reports_are_opt_in_and_package_real_downloads(reports):
    assert viewer_reports.selected_reports(reports, []) == []
    values = viewer_reports.selected_reports(reports, ['finished:one'])
    assert values[0]['files'][0]['extension'] == 'pdf'
    assert 'Useful findings' in values[0]['html'] and 'SECRET_SCRIPT' not in values[0]['html']
    w = workspace()
    w['reports'] = values
    files = build_site(w)
    assert any(name.startswith('report-files/') and name.endswith('.pdf') for name in files)
    assert filename('report', 'finished:one') in files
    assert filename('report', 'finished:one') not in build_site(workspace())


def test_saved_report_exports_stored_edits_not_provider_metadata_or_regenerated_content(reports):
    r = reports_store.create_report(reports.INBOX_DIR, title='Saved report', report_type='company', scope={}, sections=[
        {'section_id': 'findings', 'title': 'Findings', 'generated_prose': 'Old generated prose', 'edited_prose': 'Edited prose', 'provider': 'PRIVATE_PROVIDER', 'citation_ids': []}])
    selected = viewer_reports.selected_reports(reports, ['saved:' + r['id']])[0]
    assert 'Edited prose' in selected['html'] and 'Old generated prose' not in selected['html']
    assert 'PRIVATE_PROVIDER' not in json.dumps(selected)
    assert 'AI-assisted' in selected['status']
    with pytest.raises(ValueError, match='unavailable'):
        viewer_reports.selected_reports(reports, ['finished:unknown'])


def test_report_normalization_rejects_path_extensions_and_invalid_bytes():
    with pytest.raises(ValueError, match='PDF or XLSX'):
        viewer_reports.normalize_reports([{'id': 'bad', 'files': [{'extension': '../html', 'base64': ''}]}])
    with pytest.raises(ValueError, match='Invalid'):
        viewer_reports.normalize_reports([{'id': 'bad', 'files': [{'extension': 'pdf', 'base64': 'AAAA'}]}])


def test_publisher_source_matches_the_production_asset_copy():
    assert (Path(__file__).parents[1] / 'publisher/static_site.py').read_bytes() == (exports.ASSETS / 'static_site.py').read_bytes()
