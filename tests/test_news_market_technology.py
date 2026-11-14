"""Frozen November 13 coverage misses and neighbouring precision boundaries."""
from copy import deepcopy
from datetime import date, datetime, UTC

import pytest

from app.services.industry_pulse.models import DiscoveryHit
from app.services.industry_pulse.qualify import qualify_hit, QualificationIndex, is_qualifying_hit
from app.services.today_relevance import apply_today_relevance
from app.services.feed_first_live import hit_to_record, _keep_window_hits
from app.services.news_workspace import model

BELORTA = (
    '"Limited competition strengthens market position of Dutch and Belgian strawberries"',
    'Although the Belgian soft fruit season is gradually drawing to a close, activity remains strong at BelOrta. '
    'Strawberries, blackberries, and redcurrants continue to reach consumers throughout the autumn, with the festive '
    'season traditionally representing an important sales period despite declining…',
    'https://www.freshplaza.com/article/9892317/limited-competition-strengthens-market-position-of-dutch-and-belgian-strawberries/',
)
BOGAERTS = (
    'Autonomous driving platform for greenhouses without rail tubes launched',
    'Bogaerts, a Belgian company, has developed an autonomous platform that can navigate greenhouses without heating '
    'pipe rails: the Bull-Qii DS. It is suitable for tunnels, plastic-covered greenhouses and glasshouses, and is '
    'designed to treat strawberry crops with UV-C light at night. Inside a dark…',
    'https://www.hortidaily.com/article/9892322/autonomous-driving-platform-for-greenhouses-without-rail-tubes-launched/',
)


def hit(title, summary, url='https://publisher.example/article/control'):
    return DiscoveryHit(title=title, snippet=summary, url=url, source_domain='', published_date='2026-11-13',
        query_id='frozen-control', query_text='', geography='europe', berry=None, topic=None, provider='specialist_rss',
        provider_metadata={'publisher_route': 'direct_rss'})


def projected(record):
    return model(records={record['id']: record}, entities={}, relationships=[], facts=[], state={}, params={},
                 now=datetime(2026, 11, 13, 23, tzinfo=UTC))


@pytest.mark.parametrize('control', [BELORTA, BOGAERTS])
def test_source_shaped_reports_survive_collection_and_unknown_source_news_screen_without_mutation(control):
    original = hit(*control)
    before = deepcopy(original.as_dict())
    qualified = qualify_hit(deepcopy(original))
    assert qualified.qualifying, qualified.qualify_reason
    assert is_qualifying_hit(original, index=QualificationIndex.compile())
    kept, _ = apply_today_relevance([qualified], entities=[])
    assert kept == [qualified]
    collected, _ = _keep_window_hits([deepcopy(original)], entities=[], sources=[], today=date(2026, 11, 13))
    assert len(collected) == 1
    record = hit_to_record(qualified, entities=[], today=date(2026, 11, 13))
    saved = deepcopy(record)
    view = projected(record)
    assert view['matching_ids'] == [record['id']]
    assert record['review_state'] == 'UNREVIEWED' and not record.get('validated')
    assert record['title'] == control[0] and record['summary'] == control[1]
    assert original.as_dict() == before and record == saved
    assert '/article/' in record['source_url'] and not record['entity_ids']


@pytest.mark.parametrize('crop', ['Blueberry', 'Strawberry', 'Raspberry', 'Blackberry'])
def test_market_and_crop_technology_wording_works_across_all_four_crops(crop):
    for title, summary in [
        (crop + ' market position strengthens', 'Locally grown fruit has declining supplies and wholesale prices are firmer.'),
        (crop + ' UV-C platform', 'A new autonomous unit moves through greenhouses and treats crops at night.'),
        (crop + ' picking robot launched', 'The autonomous robot works in greenhouses and helps growers handle their crops.'),
    ]:
        qualified = qualify_hit(hit(title, summary))
        assert qualified.qualifying
        assert projected(hit_to_record(qualified, entities=[], today=date(2026, 11, 13)))['cards']


@pytest.mark.parametrize('title,summary', [
    ('Carrot market position strengthens', 'The carrot sector discusses declining supplies and producer prices.'),
    ('Pineapple greenhouse robotics', 'Autonomous robots handle pineapple crops in greenhouses.'),
    ('Tomato greenhouse UV-C platform', 'A new autonomous unit treats tomato crops at night.'),
    ('Cranberry market position strengthens', 'The cranberry berry sector discusses declining supplies.'),
    ('Blackcurrant market position strengthens', 'The berry industry sees declining supplies of blackcurrants.'),
    ('BlackBerry stock market position improves', 'The Chinese auto industry adopts BlackBerry QNX for autonomous vehicles.'),
    ('Strawberry shelf paper market position', 'Decorative household shelf paper with strawberry patterns has declining supplies.'),
    ('Strawberry smoothie recipe', 'A greenhouse robot shares a strawberry smoothie recipe for consumers.'),
    ('How to grow blueberries in pots', 'Autonomous robots help in a home garden with blueberry pots.'),
    ('Blueberry picking this weekend', 'Pick-your-own visitors join greenhouse robot demonstrations.'),
    ('Strawberry kitchen UV-C lamp', 'A new kitchen lamp helps consumers store their fruit.'),
])
def test_industry_wording_never_overrides_crop_company_consumer_or_hobby_gates(title, summary):
    qualified = qualify_hit(hit(title, summary))
    if qualified.qualifying:
        kept, _ = apply_today_relevance([qualified], entities=[])
        assert not kept
    assert not projected(hit_to_record(qualified, entities=[], today=date(2026, 11, 13)))['cards']


def test_belorta_mixed_crop_report_retains_target_berries_despite_redcurrants():
    qualified = qualify_hit(hit(*BELORTA))
    assert qualified.qualifying
    assert projected(hit_to_record(qualified, entities=[], today=date(2026, 11, 13)))['cards']
