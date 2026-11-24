"""Disconnected releases preserve offsite data without leaking personal state."""
import base64
from copy import deepcopy
from datetime import date
from hashlib import sha256
from io import BytesIO
import json
import re
from zipfile import ZipFile

from fastapi.testclient import TestClient
import pytest

from app import main, viewer_export_routes as routes
from app.services import feed_first, personal_digest, personal_scope
from app.services import viewer_export as service
from app.services.analyst_accounts import create_account


def directory():
    return {'title': 'Test directory', 'exported_at': '2026-11-23T10:00:00Z',
            'companies': [{'id': 'company-a', 'name': 'A nursery', 'roles': ['Breeder'], 'berries': ['blueberry']}],
            'varieties': [{'id': 'variety-a', 'name': 'Test variety', 'berry': 'blueberry', 'company_ids': ['company-a']}]}


def flavor(panel='panel-1', **extra):
    return {'id': 'taste-' + panel, 'variety_id': 'variety-a', 'panel': panel, 'date': '2026-11-20',
            'sample': 'Lot one', 'panel_size': 12, 'scale_min': 1, 'scale_max': 9,
            'overall_liking': 7.4, 'taste': 7.1, 'texture': 7.8, 'appearance': 7.6,
            'brix': 14.2, 'acidity': .65, 'acidity_unit': '% titratable acidity', 'notes': 'Chilled sample', **extra}


def issue(id='old-issue'):
    return {'id': id, 'title': 'Previous edition', 'date': '2026-11-16', 'intro': '', 'editor': '',
            'items': [{'id': 'old-story', 'title': 'Previous story', 'source': 'Publisher', 'source_url': 'https://example.invalid/old',
                       'summary': 'Keep this newsletter', 'published_date': '2026-11-15'}]}


def baseline():
    return service.assemble_workspace(directory(), issue=issue(), scores=[flavor(p) for p in service.PANELS])


def unzip(data):
    with ZipFile(BytesIO(data)) as archive:
        return {name: archive.read(name) for name in archive.namelist()}


def test_preserve_all_panels_and_editions_with_corrected_record():
    old = baseline()
    before = deepcopy(old)
    new = service.assemble_workspace(directory(), old, issue('new-issue'), [flavor('panel-1', taste=8.2)])
    assert old == before
    assert [r['id'] for r in new['issues']] == ['old-issue', 'new-issue']
    assert len(new['scores']) == 4
    assert new['scores'][0]['taste'] == 8.2
    assert new['scores'][1:] == old['scores'][1:]
    assert all(r['brix'] == 14.2 and r['acidity'] == .65 and r['acidity_unit'] == '% titratable acidity' for r in new['scores'])
    assert not any('average' in r or 'mean' in r for r in new['scores'])


def test_replacing_an_edition_removes_deselected_stories_without_duplicate():
    old = baseline()
    replacement = issue()
    replacement['items'] = []
    new = service.assemble_workspace(directory(), old, replacement)
    assert len(new['issues']) == 1 and new['issues'][0]['items'] == []
    assert new['scores'] == old['scores']


def test_orphans_and_cross_panel_ids_block_without_mutating_baseline():
    old = baseline()
    changed = directory()
    changed['varieties'] = []
    with pytest.raises(ValueError, match='absent'):
        service.assemble_workspace(changed, old)
    with pytest.raises(ValueError, match='another panel'):
        service.assemble_workspace(directory(), old, scores=[flavor('panel-2', id='taste-panel-1')])
    assert len(old['scores']) == 4


@pytest.mark.parametrize('change', [{'panel': 'panel-5'}, {'overall_liking': 10}, {'overall_liking': True},
                                  {'date': '2026-02-30'}, {'brix': 101}, {'acidity': -1}, {'texture': float('nan')},
                                  {'panel_size': 0}, {'panel_size': 1.5}])
def test_invalid_flavor_inputs_rejected(change):
    with pytest.raises(ValueError):
        service.normalize_scores([flavor(**change)], directory()['varieties'])


def test_csv_round_trip_preserves_values_units_and_panel_identity():
    data = b'variety_id,panel,date,overall liking,taste,texture,appearance,brix,acidity,acidity_unit,notes\r\nvariety-a,Panel 3,2026-11-20,7.4,7.1,7.8,7.6,14.2,0.65,g/L,"chilled, firm"\r\n'
    row = service.parse_flavor(data, 'scores.csv', directory()['varieties'])[0]
    assert row['panel'] == 'panel-3' and row['notes'] == 'chilled, firm'
    assert row['panel_size'] is None and row['acidity_unit'] == 'g/L'
    assert row['brix'] == 14.2 and row['overall_liking'] == 7.4
    assert service.parse_flavor(data, 'scores.csv', directory()['varieties'])[0]['id'] == row['id']
    with pytest.raises(ValueError, match='columns'):
        service.parse_flavor(b'variety_id,panel\nvariety-a,panel-1,extra', 'scores.csv', [])


def test_release_integrity_privacy_and_standalone_script_hashes():
    workspace = baseline()
    workspace['directory']['companies'][0]['private_note'] = 'DO_NOT_EXPORT_PRIVATE'
    workspace['scores'] = []
    workspace['import_log'] = [{'name': 'DO_NOT_EXPORT_PRIVATE'}]
    workspace['issues'][0]['items'][0]['title'] = '</script><img src=x onerror=alert(1)>'
    data, manifest = service.build_release(workspace, issue=workspace['issues'][0])
    files = unzip(data)
    assert {'site/index.html', 'content/workspace.json', 'content/directory.json', 'content/flavor.json',
            'content/digest.json', 'START-HERE.md', 'COPILOT-HANDOFF.md', 'manifest.json'} <= files.keys()
    assert all(b'DO_NOT_EXPORT_PRIVATE' not in body for body in files.values())
    for name, digest in manifest['files'].items():
        assert sha256(files[name]).hexdigest() == digest
    html = files['site/index.html'].decode()
    assert '<script src=' not in html and '<link rel="stylesheet"' not in html
    assert "connect-src 'none'" in html
    assert '</script><img src=x' not in html
    assert '<script' not in html.lower()
    assert "script-src 'none'" in html
    assert 'site/varieties.html' in files and 'site/projects.html' in files and 'site/reports.html' in files
    assert all(b'<script' not in body.lower() for name, body in files.items() if name.startswith('site/') and name.endswith('.html'))
    assert json.loads(files['content/workspace.json'])['scores'] == []
    assert manifest['counts']['panels'] == {p: 0 for p in service.PANELS}


def test_json_only_package_has_no_html_and_no_new_digest_when_none_added():
    files = unzip(service.build_release({**baseline(), 'scores': []}, json_only=True)[0])
    assert 'site/index.html' not in files and 'content/digest.json' not in files
    assert len(json.loads(files['content/workspace.json'])['issues']) == 1


def test_directory_adapter_uses_explicit_links_and_does_not_infer_operating_country():
    company = {'id': 'company-a', 'name': 'Nursery', 'entity_type': 'company', 'berry_ids': ['berry-blueberry'],
               'status': 'unverified', 'attributes': {'operates_in': 'Spain'}, 'favorite': True, 'private_note': 'DO_NOT_EXPORT_PRIVATE'}
    variety = {'id': 'variety-a', 'name': 'Variety', 'entity_type': 'variety', 'berry_ids': ['berry-blueberry'], 'status': 'unverified'}
    rel = {'subject_id': 'company-a', 'object_id': 'variety-a', 'predicate': 'develops', 'status': 'active'}
    result = service.directory_from_catalog([company], [company, variety], [rel])
    assert result['varieties'][0]['company_ids'] == ['company-a']
    assert result['companies'][0]['country'] == ''
    assert 'Identity unverified' in result['companies'][0]['tags']
    assert 'favorite' not in result['companies'][0]
    assert service.directory_from_catalog([company], [company, variety], [{**rel, 'status': 'disputed'}])['varieties'][0]['company_ids'] == []


def test_directory_geography_keeps_headquarters_and_activity_separate():
    company = {'id': 'company-a', 'name': 'Nursery', 'entity_type': 'company', 'berry_ids': ['berry-blueberry'],
               'status': 'active', 'attributes': {'headquarters_country': 'United States'}}
    variety = {'id': 'variety-a', 'name': 'Variety', 'entity_type': 'variety', 'berry_ids': ['berry-blueberry'],
               'status': 'unverified', 'attributes': {'activity_geographies': ['Canada']}}
    geo = {'id': 'geography-spain', 'name': 'Spain', 'entity_type': 'geography'}
    relationships = [{'subject_id': 'company-a', 'object_id': 'variety-a', 'predicate': 'develops', 'status': 'active'},
                     {'subject_id': 'company-a', 'object_id': geo['id'], 'predicate': 'operates_in', 'status': 'active'}]
    result = service.directory_from_catalog([company], [company, variety, geo], relationships)
    assert result['companies'][0]['country'] == 'United States'
    assert result['companies'][0]['activity_geographies'] == ['Spain']
    assert result['varieties'][0]['activity_geographies'] == ['Canada']
    restored = service.normalize_workspace(service.assemble_workspace(result))
    assert restored['directory'] == result


@pytest.fixture
def platform(monkeypatch, tmp_path):
    monkeypatch.setattr(main, 'INBOX_DIR', tmp_path / 'inbox')
    monkeypatch.setattr(main, 'DATA_DIR', tmp_path / 'data')
    monkeypatch.setattr(main, 'AUTHORING_MODE', True)
    for key, value in {'BIOS_REMOTE_INTERACTIVE': 'true', 'BIOS_REVIEW_USERNAME': 'primary',
                       'BIOS_REVIEW_PASSWORD': 'fixture-only-password',
                       'BIOS_SESSION_SECRET': 'fixture-only-export-secret-longer-than-32-characters'}.items():
        monkeypatch.setenv(key, value)
    monkeypatch.delenv('BIOS_BASIC_AUTH', raising=False)
    create_account(main.INBOX_DIR, 'second', 'fixture-only-password')
    entities = {'company-a': {'id': 'company-a', 'name': 'A nursery', 'entity_type': 'company', 'status': 'active', 'berry_ids': ['berry-blueberry']},
                'variety-a': {'id': 'variety-a', 'name': 'Test variety', 'entity_type': 'variety', 'status': 'unverified', 'berry_ids': ['berry-blueberry']}}
    records = {f'ev-{i}': {'id': f'ev-{i}', 'record_type': 'evidence', 'title': f'Story {i:02}', 'summary': f'Digest summary {i}',
                          'source_name': 'Fixture publisher', 'source_url': f'https://example.invalid/story/{i}',
                          'status': 'published', 'published_date': date.today().isoformat(), 'berry_ids': ['berry-blueberry'],
                          'entity_ids': ['company-a'], 'private_note': 'DO_NOT_EXPORT_PRIVATE'} for i in range(45)}
    monkeypatch.setattr(routes, 'world', lambda: (main, {'state': feed_first.load_state(main.INBOX_DIR)}, records, entities))
    monkeypatch.setattr(main, 'living_catalog', lambda: list(entities.values()))
    monkeypatch.setattr(main, 'unified_information', lambda **kwargs: list(records.values()))
    monkeypatch.setattr(main, 'all_relationships', lambda: [{'subject_id': 'company-a', 'object_id': 'variety-a', 'predicate': 'develops', 'status': 'active'}])
    from app.services import company_directory
    monkeypatch.setattr(company_directory.seed_roster, 'build_roster', lambda _: [])
    with personal_scope.bind('primary', 'primary'):
        saved = feed_first.load_state(main.INBOX_DIR)
        saved['decisions'] = {key: {'saved': True} for key in records}
        feed_first.save_state(main.INBOX_DIR, saved)
    clients = []
    for name in ('primary', 'second'):
        client = TestClient(main.app, follow_redirects=False)
        assert client.post('/login', data={'username': name, 'password': 'fixture-only-password'}).status_code == 303
        clients.append(client)
    return clients, records


def form(client, **changes):
    page = client.get('/exports/viewer')
    assert page.status_code == 200, page.text
    values = dict(page.context['values'])
    values.update({'baseline_revision': page.context['baseline_revision'], 'add_newsletter': '1' if values['add_newsletter'] else '',
                   'issue_id': 'new-issue', 'date': '2026-11-23'})
    values.update(changes)
    return values


def get_token(response):
    assert response.status_code == 200, response.text
    return response.context['preview']['token']


def test_dialog_all_digest_pages_and_end_to_end_download(platform):
    (first, second), records = platform
    page = first.get('/exports/viewer')
    assert len(page.context['candidates']) == 45
    assert len(second.get('/exports/viewer').context['candidates']) == 0
    assert 'Export to viewer' in page.text
    before = (main.INBOX_DIR / 'feed_first_state.json').read_bytes()
    response = first.post('/exports/viewer/preview', data=form(first))
    token = get_token(response)
    assert len(response.context['preview']['issue']['items']) == 45
    downloaded = first.post('/exports/viewer/download', data={'token': token})
    assert downloaded.status_code == 200
    files = unzip(downloaded.content)
    workspace = json.loads(files['content/workspace.json'])
    assert len(workspace['issues'][0]['items']) == 45
    assert all('private_note' not in r for r in workspace['issues'][0]['items'])
    assert workspace['directory']['varieties'][0]['company_ids'] == ['company-a']
    assert (main.INBOX_DIR / 'feed_first_state.json').read_bytes() == before
    assert first.get('/exports/viewer').context['latest']['release_id']
    assert 'no-store' in downloaded.headers['cache-control']


def test_research_baseline_retains_newsletter_archive_without_flavor(platform):
    (first, _), _ = platform
    response = first.post('/exports/viewer/preview', data=form(first, baseline_mode='upload'),
                          files={'baseline': ('workspace.json', service.json_bytes({**baseline(), 'scores': []}), 'application/json')})
    token = get_token(response)
    assert first.post('/exports/viewer/download', data={'token': token}).status_code == 200
    next_form = form(first, issue_id='following-issue', story_ids=['ev-2'])
    assert next_form['baseline_mode'] == 'previous'
    token = get_token(first.post('/exports/viewer/preview', data=next_form))
    downloaded = first.post('/exports/viewer/download', data={'token': token})
    workspace = json.loads(unzip(downloaded.content)['content/workspace.json'])
    assert [r['id'] for r in workspace['issues']] == ['old-issue', 'new-issue', 'following-issue']
    assert workspace['scores'] == []


def test_accounts_cannot_export_each_others_stories_snapshots_or_tokens(platform):
    (first, second), _ = platform
    foreign = second.post('/exports/viewer/preview', data=form(second, add_newsletter='1', story_ids=['ev-1']))
    assert foreign.status_code == 422 and 'outside your current Digest' in foreign.text
    token = get_token(first.post('/exports/viewer/preview', data=form(first)))
    assert second.post('/exports/viewer/download', data={'token': token}).status_code == 409
    assert second.get('/exports/viewer').context['latest'] is None
    assert first.post('/exports/viewer/download', data={'token': token}).status_code == 200
    assert second.get('/exports/viewer').context['latest'] is None


def test_stale_baseline_and_invalid_upload_leave_previous_export_intact(platform):
    (first, _), _ = platform
    old_form = form(first)
    token = get_token(first.post('/exports/viewer/preview', data=old_form))
    assert first.post('/exports/viewer/download', data={'token': token}).status_code == 200
    current = first.get('/exports/viewer').context['latest']
    assert first.post('/exports/viewer/preview', data=old_form).status_code == 409
    response = first.post('/exports/viewer/preview', data=form(first, baseline_mode='upload'),
                          files={'baseline': ('broken.json', b'not json', 'application/json')})
    assert response.status_code == 422
    assert first.get('/exports/viewer').context['latest'] == current


def test_auth_readonly_origin_and_request_size_boundaries(platform, monkeypatch):
    (first, _), _ = platform
    anonymous = TestClient(main.app, follow_redirects=False)
    assert anonymous.get('/exports/viewer').status_code == 302
    assert first.post('/exports/viewer/preview', data=form(first), headers={'Origin': 'https://foreign.invalid'}).status_code == 403
    monkeypatch.setattr(main, 'AUTHORING_MODE', False)
    assert first.get('/exports/viewer').status_code == 403
    monkeypatch.setattr(main, 'AUTHORING_MODE', True)
    assert first.post('/exports/viewer/preview', content=b'x' * (22 * 1024 * 1024 + 1)).status_code == 413


def test_failed_build_does_not_remember_unusable_release(platform, monkeypatch):
    (first, _), _ = platform
    token = get_token(first.post('/exports/viewer/preview', data=form(first)))
    monkeypatch.setattr(service, 'build_release', lambda *a, **k: (_ for _ in ()).throw(ValueError('fixture build failure')))
    assert first.post('/exports/viewer/download', data={'token': token}).status_code == 422
    assert first.get('/exports/viewer').context['latest'] is None


def test_corporate_flavor_upload_rejected_and_publication_confirmation_is_explicit(platform):
    (first, second), _ = platform
    response = first.post('/exports/viewer/preview', data=form(first, baseline_mode='upload'),
        files={'baseline': ('private-workspace.json', service.json_bytes(baseline()), 'application/json')})
    assert response.status_code == 422 and 'Flavor data stays corporate' in response.text
    assert first.get('/exports/viewer').context['latest'] is None
    token = get_token(first.post('/exports/viewer/preview', data=form(first)))
    download = first.post('/exports/viewer/download', data={'token': token})
    rid = json.loads(unzip(download.content)['manifest.json'])['release_id']
    assert first.get('/exports/viewer').context['published'] is None
    assert second.post('/exports/viewer/confirm', data={'release_id': rid}).status_code == 409
    assert first.post('/exports/viewer/confirm', data={'release_id': rid}).status_code == 303
    assert first.get('/exports/viewer').context['published']['release_id'] == rid
    preview = first.post('/exports/viewer/preview', data=form(first))
    assert preview.context['preview']['workspace']['changes']['basis'] == 'confirmed_published'


def test_report_selection_is_opt_in_remembered_and_deselection_removes_page(platform):
    from app.services.report_builder import reports_store
    (first, _), _ = platform
    r = reports_store.create_report(main.INBOX_DIR, title='Internal report selection', report_type='company', scope={}, sections=[
        {'title': 'Findings', 'generated_prose': 'Report prose selected for the viewer', 'status': 'draft'}])
    key = 'saved:' + r['id']
    values = form(first)
    assert values['report_ids'] == []
    response = first.post('/exports/viewer/preview', data={**values, 'report_ids': [key]})
    token = get_token(response)
    assert response.context['preview']['workspace']['reports'][0]['id'] == key
    downloaded = first.post('/exports/viewer/download', data={'token': token})
    files = unzip(downloaded.content)
    from app.viewer_assets.static_site import filename
    name = 'site/' + filename('report', key)
    assert b'Report prose selected for the viewer' in files[name]
    assert form(first)['report_ids'] == [key]
    response = first.post('/exports/viewer/preview', data=form(first, report_ids=[]))
    downloaded = first.post('/exports/viewer/download', data={'token': get_token(response)})
    assert name not in unzip(downloaded.content)


def test_viewer_hub_files_latest_download_and_preview_stay_private(platform):
    (first, second), _ = platform
    hub = first.get('/viewer')
    assert hub.status_code == 200 and 'Your first release starts here' in hub.text
    assert first.get('/viewer/guide').status_code == 200
    starter = first.get('/viewer/files/starter-kit.zip')
    assert starter.status_code == 200 and 'publisher/static_site.py' in unzip(starter.content)
    assert first.get('/viewer/files/corporate-site.example.json').json()['tiers'] == {}
    assert first.get('/viewer/files/company-ids.csv').status_code == 200
    assert first.get('/viewer/files/credentials').status_code == 404
    assert first.get('/viewer/releases/latest.zip').status_code == 404
    assert first.get('/viewer/preview/index.html').status_code == 404
    token = get_token(first.post('/exports/viewer/preview', data=form(first)))
    assert first.post('/exports/viewer/download', data={'token': token}).status_code == 200
    assert 'Download release' in first.get('/viewer').text
    assert first.get('/viewer/releases/latest.zip').status_code == 200
    assert first.get('/viewer/files/workspace.json').json()['scores'] == []
    preview = first.get('/viewer/preview/index.html')
    assert preview.status_code == 200 and b'<script' not in preview.content
    assert "script-src 'none'" in preview.headers['content-security-policy']
    assert first.get('/viewer/preview/assets/driscolls-logo.png').status_code == 200
    assert first.get('/viewer/preview/%2e%2e%2flatest.json').status_code == 404
    assert second.get('/viewer/preview/index.html').status_code == 404
    assert second.get('/viewer/releases/latest.zip').status_code == 404
    anonymous = TestClient(main.app, follow_redirects=False)
    assert anonymous.get('/viewer').status_code == 302
