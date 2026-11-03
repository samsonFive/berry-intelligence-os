from types import SimpleNamespace

from app.services.topic_discovery import discover_topic, geographic_query_variant
from app.services.topic_retrieval import plan_query


def places():
    return {'uk': {'id': 'uk', 'entity_type': 'geography', 'status': 'active',
                   'name': 'United Kingdom', 'aliases': ['UK', 'Great Britain'],
                   'description': 'PRIVATE REGISTRY NOTE'}}


def test_registered_place_alternative_preserves_literal_query_boundaries():
    plan = plan_query('Raspberry primocane trials United Kingdom 2020-01-01 through 2026-01-01 -software')
    variant = geographic_query_variant(plan, places())
    assert variant == 'Raspberry primocane trials UK 2020-01-01 through 2026-01-01 -software'
    assert plan.start == '2020-01-01' and plan.end == '2026-01-01'
    assert 'United Kingdom' in plan.raw_query
    assert geographic_query_variant(plan_query('Raspberry trials "United Kingdom"'), places()) is None
    assert geographic_query_variant(plan_query('Raspberry trials -UK'), places()) is None
    assert geographic_query_variant(plan_query('show us raspberry trials'), {
        'us': {'id':'us', 'entity_type':'geography', 'status':'active',
               'name':'United States', 'aliases':['US']}}) is None


def test_ambiguous_or_unreviewed_places_do_not_expand():
    entities = places()
    entities['other'] = {'id':'other', 'entity_type':'geography', 'status':'active',
                         'name':'Other place', 'aliases':['UK']}
    assert geographic_query_variant(plan_query('Raspberry trials UK'), entities) is None
    entities = places()
    entities['uk']['status'] = 'unverified'
    assert geographic_query_variant(plan_query('Raspberry trials UK'), entities) is None


def test_discovery_buys_one_bounded_variant_and_warm_cache_buys_none(tmp_path):
    calls = []
    class Client:
        def search(self, query, **kwargs):
            calls.append(query)
            return SimpleNamespace(provider='fixture', hits=[])
    plan = plan_query('Raspberry primocane trials United Kingdom')
    result = discover_topic(plan, inbox_dir=tmp_path, entities=places(), client=Client())
    assert calls == [plan.raw_query, 'Raspberry primocane trials UK',
                     plan.interpreted_query+' new variety releases trials',
                     plan.interpreted_query+' licensing international development']
    assert result['queries_this_request'] == 4
    assert all('PRIVATE REGISTRY NOTE' not in query for query in calls)
    before = len(calls)
    warm = discover_topic(plan, inbox_dir=tmp_path, entities=places(), client=Client())
    assert warm['cache_hit'] and warm['queries_this_request'] == 0 and len(calls) == before
