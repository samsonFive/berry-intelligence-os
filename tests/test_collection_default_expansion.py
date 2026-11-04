import json
from pathlib import Path

import pytest

from app.services import collection_settings as settings, keyword_backfill as backfill
from app.services.default_keyword_monitors import queries, metadata
from app.services.monitor_expression import matches, grouped_expression


def test_rotation_survives_restarts_and_failure_without_starvation(tmp_path):
    from app.services.feed_first_live import today_official_site_queries
    from app.services.official_rotation import reserve, record_results
    rows = today_official_site_queries({f'host-{i}.example' for i in range(15)}, include_all=True)
    seen = set()
    for turn in range(3):
        batch = reserve(rows, tmp_path)
        assert len(batch) == 6
        assert not seen.intersection(row.id for row in batch)
        seen.update(row.id for row in batch)
        record_results(batch, [{'query_id': batch[0].id}], tmp_path)
    assert seen == {row.id for row in rows}
    state = json.loads((tmp_path/'operations/official_host_rotation.json').read_text())
    assert 'last_success' not in state['hosts'][batch[0].id]
    assert state['hosts'][batch[1].id]['last_success']
    assert len(reserve(rows, tmp_path)) == 6


def test_catalog_lists_all_hosts_without_advancing_rotation(tmp_path, monkeypatch):
    monkeypatch.setenv('BIOS_INBOX_DIR', str(tmp_path))
    hosts = {f'host-{i}.example' for i in range(15)}
    catalog = settings.catalog(hosts)
    assert sum(row.get('group') == 'today_official' for row in catalog.values()) == 18
    assert not (tmp_path/'operations').exists()


def test_registry_live_feeds_follow_source_url_and_lifecycle(tmp_path, monkeypatch):
    from app.services.industry_pulse.specialist_feeds import configured_feeds
    from app.repositories.json.sources import JsonSourceRepository
    monkeypatch.setenv('BIOS_DATA_DIR', str(tmp_path))
    monkeypatch.setenv('BIOS_INBOX_DIR', str(tmp_path/'inbox'))
    repo = JsonSourceRepository(tmp_path)
    row = dict(id='source-20260824-james-hutton-news', label='Hutton', url='https://hutton.ac.uk/',
               enabled=True, discovery=dict(adapter='article_rss', feed_url='https://hutton.ac.uk/feed/'))
    repo.create(row)
    def feed(): return next(r for r in configured_feeds() if r['source_id'] == row['id'])
    assert feed()['feed_url'] == row['discovery']['feed_url']
    key = feed()['id']
    settings.change(tmp_path/'inbox', key=key, kind='feed', group='specialist', action='save',
        revision=settings.fingerprint({}), label='Custom Hutton label', text=feed()['feed_url'])
    row['discovery']['feed_url'] = 'https://hutton.ac.uk/new/feed/'
    repo.update(row['id'], row)
    assert feed()['feed_url'].endswith('/new/feed/')
    displayed = settings.view_model([], tmp_path/'inbox', tmp_path)['feeds']
    assert next(r for r in displayed if r['id'] == key)['feed_url'].endswith('/new/feed/')
    row['enabled'] = False; repo.update(row['id'], row)
    assert not any(r['source_id'] == row['id'] for r in configured_feeds())
    assert next(r for r in settings.view_model([], tmp_path/'inbox', tmp_path)['feeds'] if r['id'] == key)['enabled'] is False


def test_defaults_are_scoped_editable_backfillable_and_language_survives_dispatch(tmp_path, monkeypatch):
    monkeypatch.setenv('BIOS_INBOX_DIR', str(tmp_path))
    all_queries = queries('today_google') + queries('week')
    assert len(all_queries) == len({q.id for q in all_queries}) == 13
    key = 'monitor:raspberry-polish'
    row = backfill.monitor(tmp_path, key, settings.fingerprint({}))
    assert row['hl'] == 'pl-PL' and row['query_builder']
    settings.change(tmp_path, key=key, kind='query', group='week', action='save', revision=settings.fingerprint({}),
        label='Polish breeding', query_builder=True, input_mode='simple', query_input='hodowla',
        scope_berry='raspberry', scope_region='europe', search_language='pl-PL')
    from app.services.global_week import week_queries
    saved = next(q for q in week_queries() if q.id == key)
    assert (saved.hl, saved.gl, saved.ceid, saved.berry) == ('pl-PL', 'PL', 'PL:pl', 'raspberry')
    page = settings.view_model([], tmp_path, tmp_path/'data')
    displayed = next(q for q in page['queries'] if q['id'] == key)
    assert displayed['query_input'] == 'hodowla' and displayed['language_label'] == 'Polish'
    with pytest.raises(ValueError, match='changed'):
        backfill.monitor(tmp_path, key, settings.fingerprint({}))
    for q in queries('today_google'):
        assert q.text.endswith('when:30d')
        assert metadata(q.id)['query_builder']
    from app.services.global_week import week_catch_net_queries
    assert not any(q.id.startswith('monitor:') for q in week_catch_net_queries(week_queries()))


def test_advanced_alternatives_preserve_scope_without_redundant_google_groups():
    expression = '(floricane OR "second-year canes") AND (cultivar OR trial)'
    compiled = settings.compile_custom_query(query_input=expression, input_mode='advanced', scope_berry='blackberry')
    assert compiled['text'].startswith('(floricane OR "second-year canes") AND (cultivar OR trial) AND (blackberry')
    assert matches(expression, 'The blackberry floricane cultivar was released.')
    assert matches(expression, 'A trial of second-year canes.')
    assert not matches(expression, 'A blackberry primocane cultivar release.')
    assert matches('floricane OR primocane AND NOT software', 'floricane software')
    assert not matches('floricane OR primocane AND NOT software', 'primocane software')
    assert grouped_expression('floricane OR primocane') == '(floricane OR primocane)'
    with pytest.raises(ValueError):
        matches('(floricane OR', 'floricane')


@pytest.mark.parametrize('text,crop,query', [
    ('Nowa odmiana malin. Hodowla i licencja w Polsce.', 'raspberry', 'raspberry breeding'),
    ('Melhoramento e licenciamento de variedade de amora-preta no Brasil.', 'blackberry', 'blackberry breeding'),
    ('Nova variedade de morango para cultivo.', 'strawberry', 'strawberry variety'),
    ('O melhoramento de mirtilos e framboesas.', 'blueberry', 'blueberry breeding'),
])
def test_native_crop_screen_tag_qualification_and_archive_retrieval(text, crop, query):
    from app.services.deterministic_tagging import infer_berry_ids_from_text
    from app.services.relevance_screen import screen_relevance
    from app.services.topic_retrieval import retrieve, plan_query
    from app.services.industry_pulse.qualify import qualify_hit
    from app.services.industry_pulse.models import DiscoveryHit
    assert 'berry-' + crop in infer_berry_ids_from_text(text)
    assert screen_relevance(title=text, description='', body=text * 5).relevant
    hit = DiscoveryHit(title=text, url='https://example.org/native', source_domain='example.org', published_date='2026-10-26',
        snippet=text, query_id='fixture', query_text='', geography='global', berry=crop, topic=None, provider='fixture')
    assert qualify_hit(hit).qualifying
    record = dict(id='native-fixture', title=text, article={'paragraphs':[{'index':0, 'text':text * 5}]}, published_date='2026-10-26')
    assert retrieve([record], plan_query(query))


def test_native_backfill_stages_body_and_preserves_review_gate(tmp_path):
    from app.repositories.paths import SCHEMAS_DIR
    text = 'Melhoramento de variedade de amora-preta para cultivo no Brasil. ' * 7
    key = 'monitor:berries-portuguese'
    job = backfill.enqueue(tmp_path, key=key, revision=settings.fingerprint({}), start='2026-01-01',
                           end='2026-10-26', limit=2, actor='fixture')
    candidate = dict(title='Variedade de amora-preta', source_url='https://example.org/native', published_date='2026-05-20',
                     retrieved_at='2026-10-27T12:00:00+00:00', publication_date_basis='publisher_metadata',
                     article={'paragraphs':[{'index':0,'text':text}]}, passage=text, capture_status='full', source_version='fixture')
    def discover(plan, **kwargs):
        assert plan.cane_type is None and not plan.phrases
        return dict(status='complete', failures=[], items=[candidate])
    result = backfill.execute(tmp_path, job['id'], tmp_path/'data', SCHEMAS_DIR, discoverer=discover)
    assert result['counts']['collected'] == 1, result
    drafts = [json.loads(p.read_text(encoding='utf-8')) for p in (tmp_path/'evidence').glob('*.json')]
    assert drafts[0]['status'] == 'draft' and drafts[0]['review_state'] == 'in_review'
    assert not list((tmp_path/'data/evidence').glob('*.json'))


def test_no_legacy_keyword_pretends_to_collect_and_primary_paths_have_native_editions():
    from app.services.source_lifecycle import is_collection_eligible
    rows = json.loads((Path(__file__).resolve().parents[1]/'data/configuration/sources.json').read_text(encoding='utf-8'))
    legacy = [r for r in rows if r['type'] == 'keyword' and not (r.get('discovery') or {}).get('adapter')]
    assert len(legacy) == 33
    assert all(not r['enabled'] and r['lifecycle']['state'] == 'DISABLED' for r in legacy)
    for key, edition in [('source-inhort-berry-breeding','PL%3Apl'), ('source-embrapa-berry-research','BR%3Apt'), ('source-nc-state-rubus-portal','US%3Aen')]:
        row = next(r for r in rows if r['id'] == key)
        assert is_collection_eligible(row) and edition in row['discovery']['feed_url']
        assert row['discovery']['adapter'] == 'news_search_rss'


def test_native_region_checks_use_article_heading_and_geography_not_language():
    from app.services.collection_regions import article_matches_region
    assert article_matches_region('europe', title='Nowe polskie odmiany malin', body='Odmiana malin po próbach.')
    assert article_matches_region('europe', body='Licencje dla polskich producentów malin.')
    assert article_matches_region('americas', body='Uma variedade brasileira de morango.')
    assert not article_matches_region('europe', title='Nowa odmiana malin', body='Uprawa w Australii.')
    assert not article_matches_region('americas', title='Nova variedade de morango', body='Cultivo na Austrália.')
    assert not article_matches_region('europe', body='Polish the fruit containers before a raspberry trial.')
    assert not article_matches_region('europe', body='These polyphenols occur in raspberry varieties.')


def test_backfill_native_heading_repairs_region_without_relaxing_body_topic_or_crop():
    row = metadata('monitor:raspberry-polish')
    def candidate(title, text): return dict(title=title, article={'paragraphs':[{'text':text * 8}]})
    good = candidate('Dwie nowe polskie odmiany malin', 'Odmiany malin mają jędrne owoce. ')
    assert backfill._scope_matches(row, good)
    assert not backfill._scope_matches(row, candidate(good['title'], 'Nowa odmiana pszenicy. '))
    assert not backfill._scope_matches(row, candidate('Maliny w Australii', 'Nowe odmiany malin w Australii. '))


def test_corrected_heading_and_publisher_date_reach_backfill_review_drafts(tmp_path):
    from app.repositories.paths import SCHEMAS_DIR
    from app.services.article_acquisition import publisher_publication_date
    html = ("<div class='visualizacao-noticias'><div class='data-categoria'><span class='data'>05/09/25</span>"
            "</div><h1 class='titulo'>A strawberry recommendation</h1></div>")
    stamp, basis = publisher_publication_date(html, 'https://www.embrapa.br/en/-/noticia/123/research')
    cases = [('monitor:raspberry-polish', 'Nowe polskie odmiany malin', 'Nowa odmiana malin o jędrnych owocach. ' * 10,
              '2026-01-15', 'publisher_metadata'),
             ('monitor:berries-portuguese', 'Variedade brasileira de morango', 'Melhoramento de variedade brasileira de morango. ' * 10,
              stamp, basis)]
    for index, (key, title, text, published, provenance) in enumerate(cases):
        candidate = dict(title=title, source_url=f'https://example.org/native/{index}', published_date=published,
            publication_date_basis=provenance, retrieved_at='2026-10-27T12:00:00+00:00',
            article={'paragraphs':[{'index':0,'text':text}]}, passage=text, capture_status='full', source_version=f'fixture-{index}')
        job = backfill.enqueue(tmp_path, key=key, revision=settings.fingerprint({}), start='2025-01-01',
                               end='2026-10-26', limit=2, actor='fixture')
        result = backfill.execute(tmp_path, job['id'], tmp_path/'data', SCHEMAS_DIR,
            discoverer=lambda *a, **kw: dict(status='complete', items=[candidate], failures=[]))
        assert result['counts']['collected'] == 1 and result['counts']['failed'] == 0, result
    drafts = [json.loads(p.read_text(encoding='utf-8')) for p in (tmp_path/'evidence').glob('*.json')]
    assert {r['published_date'] for r in drafts} == {'2026-01-15', '2025-09-05'}
    assert all(r['review_state'] == 'in_review' and r['status'] == 'draft' for r in drafts)
    assert not list((tmp_path/'data/evidence').glob('*.json'))
