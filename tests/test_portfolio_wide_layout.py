"""Wide private Portfolio preferences retain the existing session, actor and CAS boundary."""
import json

import pytest
from fastapi.testclient import TestClient

from app.services import variety_view_state as state


PORTFOLIO = 'berry-pg-v2-' + 'a' * 64


def payload(count=188):
    keys = ['c-' + format(index, '032x') for index in range(count)]
    return dict(revision=0, widths={key: 260 for key in keys}, order=keys,
                hidden=keys[2:], filters={'schema': 'berry-grid-semantic-v1', 'quick': 'Peru', 'sort': '[]'})


def test_wide_layout_roundtrip_is_actor_scoped_and_stale_revision_cannot_replace_it(tmp_path):
    original = payload()
    saved = state.save(tmp_path, 'one', PORTFOLIO, original)
    assert saved['revision'] == 1 and len(saved['order']) == 188
    assert state.get(tmp_path, 'one', PORTFOLIO) == saved
    assert state.get(tmp_path, 'two', PORTFOLIO)['revision'] == 0
    before = (tmp_path / state.NAME).read_bytes()
    with pytest.raises(ValueError, match='another tab'):
        state.save(tmp_path, 'one', PORTFOLIO, original)
    assert (tmp_path / state.NAME).read_bytes() == before
    changed = {**saved, 'widths': {**saved['widths'], saved['order'][5]: 470}}
    assert state.save(tmp_path, 'one', PORTFOLIO, changed)['revision'] == 2


@pytest.mark.parametrize('key', ['catalog', 'berry-portfolio-v1-other', 'berry-pg-v2-short', 'berry-pg-v2-' + 'g' * 64])
def test_other_sheet_namespaces_keep_existing_column_and_byte_limits(key):
    assert state.layout_limits(key) == (40, 20_000)
    with pytest.raises(ValueError, match='dimensions'):
        state.clean(payload(52), key)


def test_wide_limits_are_bounded_and_invalid_saves_leave_the_original_intact(tmp_path):
    saved = state.save(tmp_path, 'one', PORTFOLIO, payload(state.PORTFOLIO_MAX_COLUMNS))
    before = (tmp_path / state.NAME).read_bytes()
    for invalid in [payload(513), {**payload(), 'widths': {'bad/id': 260}},
                    {**payload(), 'order': ['same', 'same']}]:
        with pytest.raises(ValueError):
            state.save(tmp_path, 'one', PORTFOLIO, {**invalid, 'revision': saved['revision']})
        assert (tmp_path / state.NAME).read_bytes() == before
    large = payload(512)
    keys = ['c-' + format(index, '078x') for index in range(512)]
    large.update(widths={key: 1200 for key in keys}, order=keys, hidden=keys,
                 filters={str(index): '界' * 400 for index in range(25)})
    with pytest.raises(ValueError, match='too large'):
        state.clean(large, PORTFOLIO)


def test_route_accepts_wide_payload_and_preserves_csrf_privacy_and_request_bounds(monkeypatch, tmp_path):
    from app import main
    monkeypatch.setattr(main, 'AUTHORING_MODE', True)
    monkeypatch.setattr(main, 'INBOX_DIR', tmp_path / 'inbox')
    monkeypatch.setattr(main, 'session_username', lambda request: request.headers.get('x-test-actor', 'one'))
    client = TestClient(main.app)
    original = payload()
    raw = json.dumps(original).encode()
    assert 20_000 < len(raw) < state.layout_limits(PORTFOLIO)[1]
    path = '/api/ui/sheets/' + PORTFOLIO
    result = client.post(path, content=raw, headers={'content-type': 'application/json'})
    assert result.status_code == 200 and len(result.json()['order']) == 188
    restored = client.get(path)
    assert restored.json() == result.json()
    assert restored.headers['cache-control'] == 'private, no-store'
    assert restored.headers['vary'] == 'Cookie'
    assert client.get(path, headers={'x-test-actor': 'two'}).json()['revision'] == 0
    assert client.post(path, json=original).status_code == 409
    assert client.post(path, json=original, headers={'origin': 'https://elsewhere.example'}).status_code == 403
    assert client.post('/api/ui/sheets/catalog', content=raw).status_code == 413
    assert client.post(path, content=b' ' * (128 * 1024 + 1)).status_code == 413
    assert client.get(path).json() == result.json()
    monkeypatch.setattr(main, 'AUTHORING_MODE', False)
    assert client.post(path, json=original).status_code == 403
    assert client.get(path).status_code == 403
