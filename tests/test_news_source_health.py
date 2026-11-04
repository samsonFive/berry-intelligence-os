import json
from app.services.news_source_health import model
from app.services.article_dedup import find_duplicate_article


def test_shared_show_url_and_advisory_title_never_merge_recordings():
    existing = dict(id='ev-one', source_id='source-show', source_url='https://show.org',
                    title='Blueberry update', published_date='2026-11-01',
                    discovery_provenance={'dedupe_key': 'one', 'dedupe_strategy': 'guid'})
    item = dict(id='discovered-two', source_id='source-show', canonical_url='https://show.org',
                title=existing['title'], published_date=existing['published_date'],
                media_format='podcast', dedupe_key='two', dedupe_strategy='guid')
    assert find_duplicate_article(item, existing_records=[existing]) is None
    assert find_duplicate_article({**item, 'dedupe_key': 'one'}, existing_records=[existing]) == 'ev-one'


def test_health_corruption_is_visible_and_zero_contribution_is_not_failure(tmp_path):
    folder = tmp_path / 'discovered_media'
    (folder / '_state').mkdir(parents=True)
    (folder / 'broken.json').write_text('{')
    (folder / '_state/source-a.json').write_text('[]')
    sources = [{'id': 'source-a', 'label': 'A'}, {'id': 'source-b', 'label': 'B'}]
    records = {'ev-b': {'id': 'ev-b', 'source_id': 'source-b', 'status': 'unreviewed'}}
    before = sorted(str(p) for p in tmp_path.rglob('*'))
    result = model(sources, records, [], tmp_path)
    assert result['health_issues'] == 1
    assert result['health_rows'][0]['health'] == 'Unknown'
    assert 'current media' in result['health_rows'][1]['reason']
    assert result['health_rows'][1]['execution'] == 'Manual source'
    assert before == sorted(str(p) for p in tmp_path.rglob('*'))


def test_malformed_dispatcher_values_cannot_surface_request_urls(tmp_path):
    folder = tmp_path / 'operations/pipelines'
    folder.mkdir(parents=True)
    (folder / 'dispatcher.json').write_text(json.dumps({'selection': 'explicit', 'due_ids': [],
        'requested_ids': ['https://provider.invalid/?token=PRIVATE'], 'state': 'IDLE',
        'generated_at': '2026-11-04T08:00:00+00:00'}))
    result = model([], {}, [], tmp_path)
    assert result['dispatcher'] == {}
    assert 'PRIVATE' not in json.dumps(result)
