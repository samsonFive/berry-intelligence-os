"""Pending capture → raw News → subscribed Digest → selected original Reader."""
from copy import deepcopy
from datetime import date
import json

import pytest

from app import main
from app.services import feed_first, personal_digest, publication_sources as sources
from app.services.feed_first_live import save_bundle
from app.personal_digest_routes import world
from tests.test_personal_digest import article, workspace


def pending(item_id='ev-pending-news', **changes):
    row = article(item_id, status='draft', review_state='in_review', evidence_role='publication_artifact',
                  title='New blueberry breeding programme', published_date=date.today().isoformat(),
                  article={'paragraphs': [{'index': 0, 'text': 'Original source answer, not the feed synopsis.'}],
                           'image_url': 'https://publisher.example/blueberries.jpg'})
    row.update(changes)
    return row


@pytest.mark.parametrize('media_format,visible', [('web_article', True), ('audio', False), ('video', False), ('pdf', False), ('', False)])
def test_actual_article_pipeline_metadata_admits_web_articles_only(workspace, media_format, visible):
    client, _ = workspace
    row = pending(source_type='discovered_media', media_format=media_format)
    path = write(row)
    original = path.read_bytes()
    response = client.get('/today?q=New+blueberry&view=unreviewed')
    assert response.status_code == 200
    assert (row['title'] in response.text) is visible
    assert (row['article']['image_url'] in response.text) is visible
    assert row['article']['paragraphs'][0]['text'] not in response.text
    assert path.read_bytes() == original


def write(row):
    path = main.INBOX_DIR / 'evidence' / (row['id'] + '.json')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(row, ensure_ascii=False), encoding='utf-8')
    return path


def test_stream_preview_never_constructs_body_objects_or_writes_files(workspace, monkeypatch):
    row = pending()
    row.update(transcript={'segments': [{'text': 'PRIVATE-BODY-SENTINEL'}]}, raw_html='PRIVATE-BODY-SENTINEL')
    row['article']['paragraphs'][0]['text'] = 'PRIVATE-BODY-SENTINEL'
    path = write(row)
    original = path.read_bytes()
    builder = sources.ObjectBuilder
    class NoBodyBuilder(builder):
        def event(self, event, value):
            assert value != 'PRIVATE-BODY-SENTINEL'
            super().event(event, value)
    monkeypatch.setattr(sources, 'ObjectBuilder', NoBodyBuilder)
    rows, issues = sources.pending_source_previews(main.INBOX_DIR)
    assert issues == [] and len(rows) == 1
    assert 'PRIVATE-BODY-SENTINEL' not in json.dumps(rows)
    assert 'article' not in rows[0] and 'transcript' not in rows[0] and 'raw_html' not in rows[0]
    assert rows[0]['image_url'] == row['article']['image_url']
    assert path.read_bytes() == original


def test_pending_story_is_in_raw_news_before_save_and_only_in_subscribed_digest(workspace, monkeypatch):
    client, _ = workspace
    row = pending()
    path = write(row)
    original = path.read_bytes()
    monkeypatch.setattr(main, 'get_draft', lambda *args: pytest.fail('Feed browsing hydrated a selected draft body'))
    monkeypatch.setattr(main, 'list_drafts', lambda: pytest.fail('Feed browsing loaded the draft backlog'))
    _, context, records, _ = world()
    assert records[row['id']]['status'] == 'unreviewed' and 'article' not in records[row['id']]
    assert context['pending_source_issue_count'] == 0
    news = client.get('/today?q=New+blueberry&view=unreviewed')
    assert news.status_code == 200 and row['title'] in news.text and row['article']['image_url'] in news.text
    assert row['article']['paragraphs'][0]['text'] not in news.text
    assert row['title'] not in client.get('/today?q=New+blueberry&view=trusted').text
    assert row['title'] not in client.get('/digest').text
    list_id = personal_digest.edit_list(main.INBOX_DIR, action='create', name='Breeding watch',
                                      company_ids=['company-digest'], allowed_companies={'company-digest'})
    personal_digest.edit_list(main.INBOX_DIR, action='subscribe', list_id=list_id, allowed_companies={'company-digest'})
    result = client.get('/digest')
    assert result.status_code == 200 and row['title'] in result.text and 'Breeding watch' in result.text
    assert row['article']['image_url'] in result.text and row['article']['paragraphs'][0]['text'] not in result.text
    assert feed_first.load_state(main.INBOX_DIR).get('decisions', {}) == {}
    personal_digest.edit_list(main.INBOX_DIR, action='unsubscribe', list_id=list_id, allowed_companies={'company-digest'})
    assert row['title'] not in client.get('/digest').text
    assert path.read_bytes() == original


def test_selected_reader_actions_and_source_review_remain_separate(workspace):
    client, _ = workspace
    row = pending()
    path = write(row)
    original = path.read_bytes()
    text = client.get(f'/api/intelligence/{row["id"]}/reader?personal=1').text
    assert row['article']['paragraphs'][0]['text'] in text and 'Unreviewed' in text
    assert client.post(f'/digest/stories/{row["id"]}', json={'action': 'useful'}).status_code == 200
    assert row['title'] not in client.get('/digest').text
    assert client.post(f'/digest/stories/{row["id"]}', json={'action': 'save'}).status_code == 200
    assert row['title'] in client.get('/digest').text
    assert row['title'] not in client.get('/today?view=trusted').text
    assert path.read_bytes() == original


@pytest.mark.parametrize('field,state', [('status','rejected'),('status','archived'),('review_state','rejected'),('review_state','archived')])
def test_terminal_review_suppresses_pending_and_retained_cache_without_losing_marks(workspace, field, state):
    client, _ = workspace
    row = pending()
    save_bundle(main.INBOX_DIR, {'today': date.today().isoformat(), 'records': [row]})
    path = write(row)
    assert client.post(f'/digest/stories/{row["id"]}', json={'action':'save'}).status_code == 200
    row[field] = state
    write(row)
    assert row['title'] not in client.get('/today').text
    assert row['title'] not in client.get('/digest').text
    assert 'Source no longer available' in client.get('/digest').text
    assert feed_first.load_state(main.INBOX_DIR)['decisions'][row['id']]['saved']
    assert client.get(f'/api/intelligence/{row["id"]}/reader?personal=1').status_code == 404
    assert client.get(f'/intelligence/{row["id"]}?personal=1').status_code == 404
    assert json.loads(path.read_text(encoding='utf-8'))[field] == state


def test_canonical_wins_and_conflicting_urls_never_lend_metadata(workspace):
    client, repos = workspace
    canonical = article('ev-canonical', article={'paragraphs':[{'index':0,'text':'Canonical original prose.'}]})
    repos.evidence.create(canonical)
    same = pending(canonical['id'])
    write(same)
    _, _, records, _ = world()
    assert records[canonical['id']]['title'] == canonical['title'] and records[canonical['id']]['status'] == 'published'
    assert 'Canonical original prose.' in client.get('/api/intelligence/ev-canonical/reader?personal=1').text
    cached = pending('ev-conflicting')
    save_bundle(main.INBOX_DIR, {'today':date.today().isoformat(), 'records':[cached]})
    conflict = deepcopy(cached)
    conflict.update(title='Conflicting incoming blueberry story', source_url='https://different.example/story')
    write(conflict)
    _, _, records, _ = world()
    assert records[cached['id']]['title'] == cached['title'] and records[cached['id']]['source_url'] == cached['source_url']


@pytest.mark.parametrize('change', [{'status':'published'}, {'evidence_role':'atomic_evidence'}, {'status':{'invalid':'shape'}}])
def test_inbox_cannot_spoof_publication_or_atomic_source(workspace, change):
    client, _ = workspace
    row = pending()
    row.update(change)
    write(row)
    assert row['title'] not in client.get('/today').text
    assert row['title'] not in client.get('/digest').text


def test_malformed_mismatched_and_size_limited_sources_have_visible_issue_without_stale_data(workspace, monkeypatch):
    client, _ = workspace
    path = write(pending())
    path.write_text('{"id":"ev-pending-news","article":broken}', encoding='utf-8')
    other = write(pending('ev-mismatch'))
    other.write_text(json.dumps(pending('ev-another-id')), encoding='utf-8')
    rows, issues = sources.pending_source_previews(main.INBOX_DIR)
    assert rows == [] and len(issues) == 2
    response = client.get('/today')
    assert response.status_code == 200 and 'Some captured sources couldn’t be listed.' in response.text
    assert 'broken' not in response.text and str(path) not in response.text
    write(pending())
    monkeypatch.setattr(sources,'MAX_DRAFT_BYTES',10)
    assert sources.pending_source_previews(main.INBOX_DIR)[0] == []


def test_public_view_never_opens_private_pending_inventory(workspace, monkeypatch):
    client, _ = workspace
    row = pending()
    write(row)
    monkeypatch.setattr(main,'AUTHORING_MODE',False)
    monkeypatch.setattr(sources,'pending_source_previews',lambda *args: pytest.fail('Public view opened private inventory'))
    assert row['title'] not in client.get('/today').text
    assert row['title'] not in client.get('/digest').text
    assert client.get(f'/api/intelligence/{row["id"]}/reader?personal=1').status_code == 404


@pytest.mark.parametrize('route', ['/today', '/digest'])
@pytest.mark.parametrize('query,visible', [
    ('berry=berry-blueberry,berry-raspberry', True), ('berry=berry-blackberry', False),
    ('country=geography-chile', True), ('country=geography-mexico', False),
    ('favorites=1&tier=tier1', True), ('tier=tier2', False),
    ('window=7d', True), ('window=custom&start=2000-01-01&end=2000-12-31', False),
])
def test_pending_metadata_uses_shared_company_crop_region_and_date_filters(workspace, route, query, visible):
    client, repos = workspace
    for code, name in [('chile', 'Chile'), ('mexico', 'Mexico')]:
        repos.entities.create({'id': 'geography-' + code, 'record_type':'entity', 'entity_type':'geography',
                               'name':name, 'status':'active'})
    row = pending(source_type='discovered_media', media_format='web_article')
    path = write(row)
    original = path.read_bytes()
    state = feed_first.load_state(main.INBOX_DIR)
    state.update(entity_favorites={'company-digest': True}, entity_tiers={'company-digest': 'tier1'})
    feed_first.save_state(main.INBOX_DIR, state)
    assert client.post(f'/digest/stories/{row["id"]}', json={'action':'save'}).status_code == 200
    response = client.get(route + '?q=New+blueberry&' + query)
    assert response.status_code == 200
    assert (row['title'] in response.text) is visible
    assert path.read_bytes() == original


def test_next_read_reflects_operator_edit_without_recollecting_or_changing_queue(workspace):
    client, _ = workspace
    row = pending()
    write(row)
    assert row['title'] not in client.get('/digest').text
    row['title'] = 'Updated blueberry breeding programme'
    row['summary'] = 'The publisher has updated its blueberry breeding announcement.'
    row['priority']['reading']['level'] = 'high'
    path = write(row)
    original = path.read_bytes()
    assert row['title'] in client.get('/today?q=Updated+blueberry').text
    assert row['title'] in client.get('/digest?priority=high').text
    assert path.read_bytes() == original
    assert not (main.INBOX_DIR / 'news_workspace' / 'refresh.json').exists()
