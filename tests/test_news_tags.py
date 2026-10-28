from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

import pytest

from app.services import news_tags as tags, news_workspace, feed_first


def article(key='ev-story', **extra):
    return dict(dict(id=key, title='Blueberry export prices rise at supermarkets', summary='Blueberry growers report higher demand.',
                source_type='trade_press', source_url='https://example.org/' + key, source_name='Berry News',
                status='published', published_date='2026-10-01', berry_ids=['berry-blueberry']), **extra)


def test_reads_do_not_create_runtime(tmp_path):
    assert len(tags.catalog(tmp_path)) == 9
    assert tags.snapshot(tmp_path) == ({}, {})
    assert tags.preferences(tmp_path, 'alice')['tag_mode'] == 'all'
    assert tags.job_state(tmp_path)['status'] == 'pending'
    assert not list(tmp_path.iterdir())


def test_duplicate_unicode_normalization_and_race(tmp_path):
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda name: tags.create(tmp_path, name)['id'],
                                ['markets', ' Markets ', 'Ｍａｒｋｅｔｓ', 'MARKETS']))
    assert results == ['markets'] * 4
    assert len(tags.catalog(tmp_path)) == 9


def test_account_preferences_are_independent_and_empty_is_persisted(tmp_path):
    tags.preferences(tmp_path, 'alice', ['markets', 'retail'], 'any')
    tags.preferences(tmp_path, 'bob', ['genetics'])
    assert tags.preferences(tmp_path, 'alice') == {'tag': 'markets,retail', 'tag_mode': 'any'}
    assert tags.preferences(tmp_path, 'bob') == {'tag': 'genetics', 'tag_mode': 'all'}
    tags.preferences(tmp_path, 'alice', [], 'any')
    assert tags.preferences(tmp_path, 'alice') == {'tag': '', 'tag_mode': 'any'}
    assert tags.preferences(tmp_path, 'bob')['tag'] == 'genetics'


def test_classification_overrides_restore_and_idempotent_retry(tmp_path, monkeypatch):
    row = article()
    tags.backfill(tmp_path, [row])
    catalog = tags.catalog(tmp_path)
    assert {'markets', 'retail'} <= set(tags.effective(row, catalog, *tags.snapshot(tmp_path)))
    tags.override(tmp_path, row['id'], 'markets', 'remove', 'alice')
    tags.override(tmp_path, row['id'], 'weather', 'add', 'alice')
    # Simulate a background decision arriving after the manual correction.
    tags.backfill(tmp_path, [{**row, 'summary': row['summary'] + ' Export prices surge.'}])
    result = tags.effective(row, catalog, *tags.snapshot(tmp_path))
    assert 'markets' not in result and 'weather' in result
    tags.override(tmp_path, row['id'], 'markets', 'automatic', 'alice')
    tags.override(tmp_path, row['id'], 'weather', 'automatic', 'alice')
    assert 'markets' in tags.effective(row, catalog, *tags.snapshot(tmp_path))
    assert 'weather' not in tags.effective(row, catalog, *tags.snapshot(tmp_path))
    before = tags.snapshot(tmp_path)
    def forbidden(*args):
        raise AssertionError('Unchanged input must be cached')
    monkeypatch.setattr(tags, 'decision', forbidden)
    tags.backfill(tmp_path, [{**row, 'summary': row['summary'] + ' Export prices surge.'}])
    assert before == tags.snapshot(tmp_path)
    with tags.database(tmp_path) as db:
        assert db.execute('SELECT count(*) FROM automatic').fetchone()[0] == 9
        assert db.execute('SELECT count(*) FROM audit').fetchone()[0] == 4


def test_name_only_custom_tag_existing_full_text_and_incoming(tmp_path):
    labor = tags.create(tmp_path, 'Labor')
    row = article(article={'full_text': 'Growers raised wages for seasonal workers after a labour shortage.'})
    tags.backfill(tmp_path, [row])
    assert labor['id'] in tags.effective(row, tags.catalog(tmp_path), *tags.snapshot(tmp_path))
    from app.services.feed_first_live import save_bundle
    incoming = article('live-incoming', article={'full_text': 'The labour shortage affects berry harvest workers.'})
    save_bundle(tmp_path, {'today': '2026-10-01', 'records': [incoming]})
    assert labor['id'] in tags.effective(incoming, tags.catalog(tmp_path), *tags.snapshot(tmp_path))


@pytest.mark.parametrize('key,positive,negative', [
    ('markets', 'Blueberry export prices rise', 'Blueberry flower photographs'),
    ('gene-editing', 'CRISPR gene editing in strawberry plants', 'Conventional strawberry breeding introduces a new variety'),
    ('advanced-breeding', 'Genomic selection in blueberry breeding', 'Conventional blueberry breeding'),
    ('agtech', 'Blueberry harvesting robots', 'Blueberry harvest begins'),
    ('retail', 'Supermarket blueberry promotions', 'Blueberry nursery research'),
    ('corporate', 'Blueberry company announces acquisition', 'Company grows blueberries'),
    ('weather', 'Frost damages blueberry crops', 'Blueberry retail display'),
    ('genetics', 'Conventional strawberry cultivar breeding', 'Strawberry export prices'),
    ('sustainability', 'Blueberry farm water conservation', 'Blueberry farm appoints CEO'),
])
def test_seed_positive_and_negative_passages(key, positive, negative):
    tag = dict(id=key, name=tags.SEEDS[key][0], description=tags.SEEDS[key][1])
    yes, passage = tags.decision({'title': positive}, tag)
    assert yes and passage
    assert not tags.decision({'title': negative}, tag)[0]


def test_all_any_three_tags_empty_and_before_pagination(tmp_path):
    rows = [article('ev-' + str(n), summary='Berry news.') for n in range(80)]
    rows.append(article('ev-intersection', article={'full_text': 'Supermarkets use sensors for berry sales.'}))
    tags.backfill(tmp_path, rows)
    def model(selection, mode='all', **params):
        return news_workspace.model(records={r['id']:r for r in rows}, entities={}, relationships=[], facts=[],
            state=feed_first.empty_state(), params={'tag':selection, 'tag_mode':mode, **params},
            now=datetime(2026,10,2,tzinfo=UTC), tags=tags.catalog(tmp_path), tag_assignments=tags.snapshot(tmp_path))
    assert model('markets,retail')['matching'] == 81
    assert model('markets,retail,agtech')['matching_ids'] == ['ev-intersection']
    assert model('weather,retail')['matching'] == 0
    assert model('weather,retail', 'any')['matching'] == 81
    assert model('')['matching'] == 81
    assert model('agtech', q='nothing')['matching'] == 0
    assert model('agtech', berry='strawberry')['matching'] == 0


def test_definition_change_rename_failure_preserves_previous(tmp_path, monkeypatch):
    row = article()
    tag = tags.create(tmp_path, 'Labor')
    tags.backfill(tmp_path, [row])
    assert not tags.update(tmp_path, tag['id'], 'Workforce', '')
    assert tags.update(tmp_path, tag['id'], 'Workforce', 'export prices')
    tags.backfill(tmp_path, [row])
    assert tag['id'] in tags.effective(row, tags.catalog(tmp_path), *tags.snapshot(tmp_path))
    before = tags.snapshot(tmp_path)
    def fail(*args):
        raise RuntimeError('classifier unavailable')
    monkeypatch.setattr(tags, 'decision', fail)
    with pytest.raises(RuntimeError):
        tags.backfill(tmp_path, [{**row, 'summary':'changed'}])
    assert tags.snapshot(tmp_path) == before
    assert tags.job_state(tmp_path)['status'] == 'failed'
