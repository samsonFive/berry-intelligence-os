import base64
from hashlib import sha256
import json
from io import BytesIO
from zipfile import ZipFile

import pytest

from app.services import viewer_content as c, viewer_export as s


def test_older_live_reader_keeps_unselected_sources_and_current_evidence_states(monkeypatch):
    from types import SimpleNamespace
    from app import personal_digest_routes
    main = SimpleNamespace(all_evidence=lambda: [record(id='stored'), record(id='removed', status='withdrawn')])
    sources = {r['id']: r for r in [record(id='unselected'), record(id='removed'), record(id='private', publication_scope='private')]}
    monkeypatch.setattr(personal_digest_routes, 'world', lambda: (main, {}, sources, {}))
    rows = {r['id']: r for r in c.information_records(main)}
    assert set(rows) == {'stored', 'unselected', 'removed', 'private'}
    assert rows['removed']['status'] == 'withdrawn'
    assert 'private' not in {r['id'] for r in c.information_records(main, include_private=False)}
    main.unified_information = lambda **kwargs: [record(id='canonical')]
    assert [r['id'] for r in c.information_records(main)] == ['canonical']


def workspace():
    return s.normalize_workspace({**s.empty_workspace(), 'directory': {
        'companies': [{'id': 'company-a', 'name': 'Example', 'socials': [{'platform': 'linkedin', 'url': 'https://example.com/company'}]}],
        'varieties': [{'id': 'variety-a', 'name': 'Example berry', 'berry': 'blueberry', 'company_ids': ['company-a']}]}})


def record(**updates):
    return {'id': 'source-a', 'title': 'Public source', 'summary': 'Stored summary', 'record_type': 'evidence',
            'source_url': 'https://example.com/story', 'source_type': 'company_press_release',
            'status': 'unreviewed', 'published_date': '2026-11-01', 'captured_date': '2026-11-02',
            'entity_ids': ['company-a', 'variety-a'], 'private_note': 'PRIVATE_SENTINEL', **updates}


def test_activity_is_independent_of_digest_and_keeps_labels_not_private_fields():
    values = c.activity_from_records([record(), record(id='other', source_type='new_unknown_kind')], workspace()['directory'])
    assert len(values) == 2
    assert {r['category'] for r in values} == {'communications', 'other'}
    assert all(r['status'] == 'unreviewed' for r in values)
    assert all(r['variety_ids'] == ['variety-a'] for r in values)
    assert 'PRIVATE_SENTINEL' not in json.dumps(values)


@pytest.mark.parametrize('updates', [{'publication_scope': 'private'}, {'status': 'rejected'}, {'review_state': 'archived'},
                                     {'evidence_role': 'atomic_proposal'}, {'source_url': 'javascript:alert(1)'}, {'entity_ids': ['company-other']}])
def test_ineligible_activity_stays_out(updates):
    assert not c.activity_from_records([record(**updates)], workspace()['directory'])


def test_changes_ignore_order_and_export_timestamps_but_find_real_edits():
    old = workspace()
    old['directory']['companies'][0]['aliases'] = ['A', 'B']
    new = json.loads(json.dumps(old))
    new['directory']['exported_at'] = '2026-11-24'
    new['directory']['companies'][0]['aliases'].reverse()
    assert not c.change_report(new, old)['items']
    new['directory']['companies'][0]['name'] = 'Updated'
    report = c.change_report(new, old, baseline_id='prior', basis='confirmed_published')
    assert report['items'][0]['fields'] == ['name']
    assert report['basis'] == 'confirmed_published'


def test_scope_loss_is_separate_from_no_longer_exported():
    old = workspace()
    new = workspace()
    new['directory']['varieties'] = []
    assert c.change_report(new, old)['items'][0]['change'] == 'no_longer_exported'
    assert c.change_report(new, old, scope='berry-strawberry')['items'][0]['change'] == 'outside_scope'


def test_asset_packaging_has_verified_bytes_and_reports_failures():
    body = (s.ASSETS / 'driscolls-logo.png').read_bytes()
    candidates = [{'id': 'logo-a', 'entity_id': 'company-a', 'kind': 'logo', 'title': 'Logo', 'url': 'https://example.com/logo.png'},
                  {'id': 'logo-b', 'entity_id': 'variety-a', 'kind': 'image', 'title': 'Missing', 'blocked': 'No source file'}]
    assets, omissions = c.collect_assets(candidates, fetch=lambda url, **kwargs: body)
    assert len(assets) == 1 and omissions[0]['reason'] == 'No source file'
    assert assets[0]['sha256'] == sha256(body).hexdigest()
    w = workspace()
    w.update(assets=assets, asset_omissions=omissions)
    package, manifest = s.build_release(w)
    with ZipFile(BytesIO(package)) as z:
        assert z.read('site/' + assets[0]['path']) == body
        assert 'publisher/static_site.py' in z.namelist()
        assert json.loads(z.read('content/workspace.json'))['scores'] == []
        assert manifest['flavor_boundary'] == 'corporate_only'


def test_active_content_is_not_a_packaged_image():
    with pytest.raises(ValueError):
        c.asset_bytes(b'<svg onload="alert(1)"></svg>')


def test_dns_checks_reject_mixed_public_private_answers(monkeypatch):
    monkeypatch.setattr(c.socket, 'getaddrinfo', lambda *a, **k: [(2,1,6,'',('8.8.8.8',443)), (2,1,6,'',('127.0.0.1',443))])
    with pytest.raises(ValueError, match='nonpublic'):
        c._address('https://example.com/image.png')


def test_research_export_cannot_embed_flavor():
    w = workspace()
    w['scores'] = [{'id': 'taste-a', 'variety_id': 'variety-a', 'date': '2026-11-23', 'panel': 'panel-1', 'overall_liking': 7}]
    with pytest.raises(ValueError, match='corporate flavor'):
        s.build_release(w)


def test_confirmed_publication_is_account_scoped_and_not_automatic(tmp_path):
    w = workspace()
    preview = s.prepare(tmp_path, w, {'format': 'site'}, expected_revision='')
    _, manifest = s.download_prepared(tmp_path, preview['token'])
    assert s.load_published(tmp_path) is None
    with pytest.raises(ValueError):
        s.confirm_published(tmp_path, 'wrong')
    s.confirm_published(tmp_path, manifest['release_id'])
    assert s.load_published(tmp_path)['release_id'] == manifest['release_id']


def test_archive_retains_missing_old_sources_but_never_known_private_or_deleted():
    w = workspace()
    old = c.activity_from_records([record()], w['directory'])
    assert c.retain_archive([], {'activity': old}, [], w['directory'])[0]['availability'] == 'retained_archive'
    assert not c.retain_archive([], {'activity': old}, [record(publication_scope='private')], w['directory'])
    assert not c.retain_archive([], {'activity': old}, [], w['directory'], blocked={'source-a'})


def test_asset_omission_is_not_a_false_withdrawal():
    old, new = workspace(), workspace()
    old['assets'] = [{'id': 'asset-a', 'title': 'Logo'}]
    new['asset_omissions'] = [{'asset_id': 'asset-a'}]
    assert c.change_report(new, old)['items'][0]['change'] == 'unavailable'


def test_managed_media_policy_cannot_be_bypassed_by_recorded_logo_url(tmp_path, monkeypatch):
    from app.services import brand_media
    url = 'https://example.com/logo.png'
    monkeypatch.setattr(brand_media, 'inventory', lambda _: [{'id': 'asset-a', 'entity_id': 'company-a', 'kind': 'logo',
        'kind_label': 'Logo', 'image_url': url, 'original_image_url': url, 'export_eligible': False}])
    candidates = c.asset_candidates(tmp_path, [{'id': 'company-a', 'name': 'Example', 'logo_url': url}], [], workspace()['directory'])
    assert len(candidates) == 1 and candidates[0]['blocked']


def test_direct_document_source_is_linked_to_company_and_variety():
    records = c.activity_from_records([record(source_url='https://example.com/sheet.pdf')], workspace()['directory'])
    candidates = c.activity_asset_candidates(records)
    assert candidates[0]['entity_ids'] == ['company-a', 'variety-a']
    assert candidates[0]['kind'] == 'document'


def test_redirect_to_private_destination_is_rejected_before_connection(monkeypatch):
    calls = []
    class Reply:
        status = 302
        def getheader(self, key):
            return 'http://127.0.0.1/secret'
    class Connection:
        def __init__(self, *args, **kwargs):
            calls.append(args[0])
        def request(self, *args, **kwargs):
            pass
        def getresponse(self):
            return Reply()
        def close(self):
            pass
    monkeypatch.setattr(c.http.client, 'HTTPSConnection', Connection)
    monkeypatch.setattr(c.socket, 'getaddrinfo', lambda host, *a, **k: [(2,1,6,'',('127.0.0.1' if host=='127.0.0.1' else '8.8.8.8',443))])
    with pytest.raises(ValueError, match='nonpublic'):
        c.fetch_asset('https://example.com/logo.png')
    assert calls == ['example.com']


def test_discovery_photographs_and_social_icons_do_not_become_company_logos():
    assert c.logo_reference_kind('https://example.com/linkedin-icon.png') == 'social_ui_icon'
    assert c.logo_reference_kind('https://example.com/greenhouse-flowers.jpg') == 'reference_image'
    assert c.logo_reference_kind('https://example.com/Tomv4-scaled.jpg') == 'reference_image'
    assert c.logo_reference_kind('https://example.com/company-logo.png') == 'logo'
