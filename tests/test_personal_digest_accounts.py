"""Two real fixture logins share research, but never each other's Digest."""
from datetime import date
import json
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest

from app import main
from app.services import analyst_queue, feed_first, personal_digest, personal_scope
from app.services.analyst_accounts import create_account
from app.services.review_events import load_review_events


@pytest.fixture
def team(monkeypatch, tmp_path):
    monkeypatch.setattr(main, 'INBOX_DIR', tmp_path / 'inbox')
    monkeypatch.setattr(main, 'DATA_DIR', tmp_path / 'data')
    monkeypatch.setattr(main, 'AUTHORING_MODE', True)
    for key, value in {'BIOS_REMOTE_INTERACTIVE': 'true', 'BIOS_REVIEW_USERNAME': 'primary',
                       'BIOS_REVIEW_PASSWORD': 'fixture-only-password',
                       'BIOS_SESSION_SECRET': 'fixture-only-secret-longer-than-32-characters'}.items():
        monkeypatch.setenv(key, value)
    monkeypatch.delenv('BIOS_BASIC_AUTH', raising=False)
    repos = main.get_repositories(main.DATA_DIR, main.SCHEMAS_DIR)
    repos.entities.create({'id':'company-team','record_type':'entity','entity_type':'company','name':'Team Nursery','status':'active'})
    repos.evidence.create({
        'id':'ev-team','record_type':'evidence','status':'published','source_type':'trade_press',
        'source_name':'Fixture Publisher','source_url':'https://example.invalid/fixture',
        'title':'A nursery expands its blueberry programme','summary':'A source for isolated account tests.',
        'published_date':date.today().isoformat(),'captured_date':date.today().isoformat(),
        'submitted_by':'fixture','reviewed_by':'fixture','reviewed_at':date.today().isoformat(),
        'berry_ids':['berry-blueberry'],'entity_ids':['company-team'],'geography_ids':[],
        'priority':{key:{'level':'none','rationale':''} for key in ('reading','testing','monitoring','commercial_position')},
    })
    create_account(main.INBOX_DIR, 'second', 'fixture-only-password')
    clients = []
    for name in ('primary', 'second'):
        client = TestClient(main.app, follow_redirects=False)
        assert client.post('/login', data={'username':name,'password':'fixture-only-password'}).status_code == 303
        clients.append(client)
    return clients, tmp_path


def cards(client):
    response = client.get('/digest')
    assert response.status_code == 200
    return response.context['cards']


def action(client, name):
    response = client.post('/digest/stories/ev-team', json={'action':name})
    assert response.status_code == 200, response.text
    return response.json()


def test_saves_progress_and_reader_locations_are_account_specific(team):
    (first, second), _ = team
    assert cards(first) == cards(second) == []
    assert action(first, 'save')['decision']['saved']
    assert [row['id'] for row in cards(first)] == ['ev-team']
    assert cards(second) == []
    assert action(first, 'start')['progress'] == 'in_progress'
    assert second.post('/digest/stories/ev-team', json={'action':'location','mode':'article','position':250}).status_code == 200
    assert action(second, 'save')['progress'] == 'unread'
    assert action(second, 'mark_read')['progress'] == 'read'
    assert action(first, 'save')['progress'] == 'in_progress'
    with personal_scope.bind('primary', 'primary'):
        assert 'reader_positions' not in analyst_queue.load_state(main.INBOX_DIR)['reading']['ev-team']
        assert all(row['actor'] == 'primary' for row in load_review_events(main.INBOX_DIR, workflow='reading_queue'))
    with personal_scope.bind('second', 'primary'):
        assert analyst_queue.load_state(main.INBOX_DIR)['reading']['ev-team']['reader_positions']['article'] == 250
        assert all(row['actor'] == 'second' for row in load_review_events(main.INBOX_DIR, workflow='reading_queue'))


def test_shared_lists_and_reactions_keep_independent_digest_subscriptions(team):
    (first, second), _ = team
    response = first.post('/digest/lists', data={'action':'create','name':'Shared watch','company_ids':'company-team'})
    assert response.status_code == 303
    list_id = next(iter(feed_first.load_state(main.INBOX_DIR)['company_lists']))
    assert first.post('/digest/lists', data={'action':'subscribe','list_id':list_id}).status_code == 303
    assert len(cards(first)) == 1 and cards(second) == []
    assert any(row['name'] == 'Shared watch' for row in second.get('/digest').context['lists'])
    action(first, 'useful')
    with personal_scope.bind('second', 'primary'):
        state = feed_first.load_state(main.INBOX_DIR)
        assert feed_first.decision_for('ev-team', state)['reaction'] == 'up'
        assert state['digest_subscriptions'] == []
    assert second.post('/digest/lists', data={'action':'subscribe','list_id':list_id}).status_code == 303
    assert first.post('/digest/lists', data={'action':'unsubscribe','list_id':list_id}).status_code == 303
    assert cards(first) == [] and len(cards(second)) == 1


def test_workspaces_are_collaborative_and_only_layouts_are_account_specific(team):
    (first, second), _ = team
    created = first.post('/api/workspaces', json={'title':'Team research','token':uuid4().hex})
    assert created.status_code == 200
    page_id = created.json()['id']
    page = second.get('/api/workspaces/page/' + page_id).json()['page']
    page['title'] = 'Edited by another analyst'
    assert second.put('/api/workspaces/page/' + page_id, json=page).status_code == 200
    assert first.get('/api/workspaces/page/' + page_id).json()['page']['title'] == page['title']
    values = {'view':'cards','widths':None,'order':list(range(8)),'card_columns':'3','source_sort':'asc'}
    saved = first.put('/api/workspaces/preferences/layout', json={'version':0,'values':values,'token':uuid4().hex})
    assert saved.status_code == 200
    assert second.get('/api/workspaces/preferences/layout').json()['values'] is None
    assert first.get('/api/workspaces/preferences/layout').json()['values'] == values


def test_legacy_personal_fields_survive_and_are_not_copied_to_other_accounts(tmp_path):
    feed = feed_first.empty_state()
    feed['decisions'] = {'ev-legacy':{'saved':True,'read':True,'reaction':'up'}}
    feed['digest_subscriptions'] = ['list-old']
    feed_first.save_state(tmp_path, feed)
    queue = {'reading':{'ev-legacy':{'state':'saved','reviewer':'older analyst'}},'testing':{'ev-shared':{'state':'pass'}}}
    analyst_queue.save_state(tmp_path, queue)
    original_feed = json.loads(feed_first.state_path(tmp_path).read_text())
    original_queue = json.loads(analyst_queue.state_path(tmp_path).read_text())
    with personal_scope.bind('second', 'primary'):
        assert feed_first.load_state(tmp_path)['digest_subscriptions'] == []
        assert not feed_first.decision_for('ev-legacy', feed_first.load_state(tmp_path))['saved']
        assert analyst_queue.load_state(tmp_path)['reading'] == {}
        personal_digest.set_personal_decision(tmp_path, 'ev-new', 'save')
        analyst_queue.apply_action(tmp_path, dimension='reading', item_id='ev-new', action='start')
        assert analyst_queue.load_state(tmp_path)['testing'] == queue['testing']
    with personal_scope.bind('primary', 'primary'):
        assert feed_first.decision_for('ev-legacy', feed_first.load_state(tmp_path))['saved']
        assert feed_first.load_state(tmp_path)['digest_subscriptions'] == ['list-old']
        assert analyst_queue.load_state(tmp_path)['reading'] == queue['reading']
        assert not feed_first.decision_for('ev-new', feed_first.load_state(tmp_path))['saved']
    stored_feed = json.loads(feed_first.state_path(tmp_path).read_text())
    stored_queue = json.loads(analyst_queue.state_path(tmp_path).read_text())
    assert stored_feed['decisions']['ev-legacy'] == original_feed['decisions']['ev-legacy']
    assert stored_feed['digest_subscriptions'] == original_feed['digest_subscriptions']
    assert stored_queue['reading'] == original_queue['reading']
    assert personal_scope.account_key() == ''


def test_legacy_source_priorities_do_not_populate_another_accounts_digest():
    record = {'id':'ev-old-queue','priority':{'reading':{'level':'high'}}}
    with personal_scope.bind('primary', 'primary'):
        assert personal_digest.inclusion(record, {}, {}) == [{'key':'queue','label':'Reading queue'}]
        primary_key = main._nav_work_cache_key()
    with personal_scope.bind('second', 'primary'):
        assert personal_digest.inclusion(record, {}, {}) == []
        assert main._nav_work_cache_key() != primary_key


def test_concurrent_personal_writes_keep_both_accounts(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    def save(name):
        with personal_scope.bind(name, 'primary'):
            for number in range(8):
                personal_digest.set_personal_decision(tmp_path, f'ev-{name}-{number}', 'save')
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(save, ['primary', 'second']))
    for name, other in [('primary','second'),('second','primary')]:
        with personal_scope.bind(name, 'primary'):
            state = feed_first.load_state(tmp_path)
            assert all(feed_first.decision_for(f'ev-{name}-{number}', state)['saved'] for number in range(8))
            assert all(not feed_first.decision_for(f'ev-{other}-{number}', state)['saved'] for number in range(8))


def test_unreadable_existing_state_is_never_replaced_by_an_empty_account(tmp_path):
    for service in (feed_first, analyst_queue):
        path = service.state_path(tmp_path)
        original = b'{"personal_accounts":{"retained-user":'
        path.write_bytes(original)
        with personal_scope.bind('second', 'primary'), pytest.raises(ValueError, match='changes were not saved'):
            service.save_state(tmp_path, service.load_state(tmp_path))
        assert path.read_bytes() == original
