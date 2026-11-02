"""Directory preparation must retain photo holds, edits and request boundaries."""
from copy import deepcopy
from datetime import date
import json

from fastapi.testclient import TestClient
import pytest

from app import main
from app.services import company_directory, identity_read_model, variety_photos as photos
from app.services import variety_portfolio_coverage as portfolios


@pytest.fixture
def directory_fixture(monkeypatch, tmp_path):
    monkeypatch.setattr(main, 'INBOX_DIR', tmp_path)
    monkeypatch.setattr(main, 'AUTHORING_MODE', True)
    original = main.living_catalog()
    base = next(row for row in original if row.get('entity_type') == 'variety')
    varieties = []
    for key, name in [('clear', 'Fixture Clear'), ('held', 'Fixture Held'), ('empty', 'Fixture Empty')]:
        varieties.append({**deepcopy(base), 'id': 'variety-fixture-' + key, 'name': name,
                          'aliases': [], 'berry_ids': ['berry-blueberry'], 'attributes': {}, 'status': 'unverified'})
    catalog = [*original, *varieties]
    index = {row['id']: row for row in catalog}
    monkeypatch.setattr(main, 'living_catalog', lambda: catalog)
    monkeypatch.setattr(main, 'entity_index', lambda: index)
    scopes = []
    def universe():
        scope = identity_read_model._active_scope.get()
        assert scope is not None, 'Only the directory count calculation opts in'
        scopes.append(scope)
        return varieties, [], {}
    monkeypatch.setattr(main, 'variety_candidate_universe', universe)
    def photo(name):
        return {'image_url': 'https://images.example.test/' + name.replace(' ', '-') + '.jpg',
                'source_url': 'https://publisher.example.test/photo', 'credit': 'Fixture photographer',
                'caption': name + ' in a synthetic trial', 'named_variety': name,
                'berry_id': 'berry-blueberry', 'reuse': 'unknown', 'license_url': '', 'reuse_note': '',
                'checked_on': date.today().isoformat(), 'kind': 'fruit'}
    sources = [{'id': 'fixture-photo-source', 'title': 'Synthetic source', 'company_ids': [], 'names': [
        {'candidate_name': varieties[0]['name'], 'berry_id': 'berry-blueberry', 'photos': [photo(varieties[0]['name'])]},
        {'candidate_name': varieties[1]['name'], 'berry_id': 'berry-blueberry', 'photos': [photo(varieties[1]['name'])],
         'identity_notes': ['Check the original identity before linking this photo.']},
    ]}]
    monkeypatch.setattr(portfolios, 'load_portfolio_observations', lambda _path: sources)
    state = {'version': 1, 'profiles': {varieties[0]['id']: {'revision': 9, 'notes': 'Keep my annotation'}},
             'history': [{'note': 'Keep earlier human work'}]}
    profile_path = tmp_path / company_directory.PROFILE_FILE
    profile_path.write_text(json.dumps(state), encoding='utf-8')
    return {'varieties': varieties, 'catalog': catalog, 'sources': sources, 'scopes': scopes,
            'profile_path': profile_path, 'state': state, 'tmp': tmp_path}


def rows(response):
    assert response.status_code == 200
    return {row['id']: row for row in response.context['variety_rows']}


def test_one_preparation_retains_unknown_permission_and_identity_holds(directory_fixture, monkeypatch):
    f = directory_fixture
    before = deepcopy((f['catalog'], f['sources']))
    saved = f['profile_path'].read_bytes()
    raw = [ref['photos'][0] for ref in f['sources'][0]['names']]
    validations, notes, indexes = [], [], []
    original_validate, original_notes = photos.validate_photo, portfolios._identity_pair_notes
    original_index, original_source = photos.SourcePhotoIndex, photos.source_photos
    def validate(value):
        if any(value is photo for photo in raw):
            validations.append(id(value))
        return original_validate(value)
    def index(sources, varieties):
        value = original_index(sources, varieties)
        indexes.append(value)
        return value
    def source(*args, **kwargs):
        assert identity_read_model._active_scope.get() is None, 'Photo reads keep the existing matcher path'
        assert kwargs['_index'] is indexes[0]
        return original_source(*args, **kwargs)
    monkeypatch.setattr(photos, 'validate_photo', validate)
    monkeypatch.setattr(photos, 'SourcePhotoIndex', index)
    monkeypatch.setattr(photos, 'source_photos', source)
    monkeypatch.setattr(portfolios, '_identity_pair_notes', lambda value: (notes.append(1), original_notes(value))[1])
    result = rows(TestClient(main.app).get('/entities/variety?q=Fixture'))
    clear, held, empty = f['varieties']
    assert len(indexes) == 1 and len(notes) == 1
    assert len(validations) == len(set(validations)) == 2
    assert len(result[clear['id']]['photos']) == 1
    assert result[clear['id']]['photos'][0]['display_image'] is False
    assert result[held['id']]['photos'] == [] and result[held['id']]['photo_identity_reviews']
    assert result[empty['id']]['photos'] == []
    assert (f['catalog'], f['sources']) == before and f['profile_path'].read_bytes() == saved


def test_next_request_rechecks_source_edits_saved_hides_and_catalog_ambiguity(directory_fixture):
    f = directory_fixture
    client = TestClient(main.app)
    clear, held, _ = f['varieties']
    first = rows(client.get('/entities/variety?q=Fixture'))[clear['id']]
    photo_id = first['photos'][0]['id']
    f['sources'][0]['names'][0]['photos'][0]['credit'] = 'A corrected source credit'
    updated = rows(client.get('/entities/variety?q=Fixture'))[clear['id']]
    assert updated['photos'][0]['credit'] == 'A corrected source credit'
    f['state']['profiles'][clear['id']]['variety_photo_overrides'] = {photo_id: None}
    f['profile_path'].write_text(json.dumps(f['state']), encoding='utf-8')
    saved = f['profile_path'].read_bytes()
    hidden = rows(client.get('/entities/variety?q=Fixture'))[clear['id']]
    assert hidden['photos'] == [] and hidden['photo_identity_reviews'] == []
    held['aliases'].append(clear['name'])
    ambiguous = rows(client.get('/entities/variety?q=Fixture'))[clear['id']]
    assert ambiguous['photos'] == [] and ambiguous['photo_identity_reviews']
    assert 'more than one catalog entry' in str(ambiguous['photo_identity_reviews'])
    assert f['profile_path'].read_bytes() == saved
    assert len({id(scope) for scope in f['scopes']}) == 4


def test_unrelated_bad_photo_is_not_silently_skipped(directory_fixture):
    f = directory_fixture
    f['sources'][0]['names'][1]['photos'][0]['source_url'] = 'http://127.0.0.1/private'
    before = f['profile_path'].read_bytes()
    response = TestClient(main.app).get('/entities/variety?q=Fixture%20Clear')
    assert response.status_code == 422
    assert f['profile_path'].read_bytes() == before


def test_single_row_keeps_original_photo_path(directory_fixture, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('There is no cross-card work to share for one row')
    monkeypatch.setattr(photos, 'SourcePhotoIndex', forbidden)
    result = rows(TestClient(main.app).get('/entities/variety?q=Fixture%20Clear'))
    assert len(result) == 1
    row = next(iter(result.values()))
    assert len(row['photos']) == 1 and row['photos'][0]['display_image'] is False


def test_empty_result_keeps_deferred_photo_validation(directory_fixture, monkeypatch):
    f = directory_fixture
    f['sources'][0]['names'][0]['photos'][0]['source_url'] = 'http://127.0.0.1/private'
    def forbidden(*args, **kwargs):
        raise AssertionError('An empty result has no photo enrichment to prepare')
    monkeypatch.setattr(photos, 'SourcePhotoIndex', forbidden)
    assert rows(TestClient(main.app).get('/entities/variety?q=Fixture%20Missing')) == {}


def test_readonly_never_prepares_private_photos(directory_fixture, monkeypatch):
    monkeypatch.setattr(main, 'AUTHORING_MODE', False)
    def forbidden(*args, **kwargs):
        raise AssertionError('Read-only directory must not hydrate private photos')
    monkeypatch.setattr(photos, 'SourcePhotoIndex', forbidden)
    monkeypatch.setattr(company_directory, 'load_profiles', forbidden)
    response = TestClient(main.app).get('/entities/variety?q=Fixture')
    assert response.status_code == 200
    assert 'Fixture photographer' not in response.text
