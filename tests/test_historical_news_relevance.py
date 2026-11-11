"""Regressions from the independent global historical News audit."""

import pytest

from app.services.feed_first_live import hit_to_record
from app.services.industry_pulse.models import DiscoveryHit
from app.services.industry_pulse.qualify import qualify_hit
from app.services.news_workspace import model
from app.services.today_relevance import apply_today_relevance
from datetime import date


@pytest.mark.parametrize(('title', 'url', 'edition'), [
    ('Could steam help California strawberry farmers grow more with fewer chemicals?',
     'https://latimes.com/business/story/strawberry-farmers', 'US:en'),
    ('Huelva se prepara para la nueva campaña de fresas y frutos rojos con el inicio de la plantación de 15.200 hectáreas',
     'https://huelvainformacion.es/huelva/plantacion', 'ES:es'),
])
def test_eligible_production_news_survives_metadata_and_display(title, url, edition):
    hit = qualify_hit(DiscoveryHit(
        title=title, url=url, source_domain='', published_date='2026-10-20', snippet='',
        query_id='feed:priority:archive', query_text='', geography='global', berry=None,
        topic=None, provider='specialist_rss', origin_publisher_url=url,
        provider_metadata={'publisher_route': 'indexed', 'publisher_source_type': 'news_search', 'query_edition': edition},
    ))
    kept, _ = apply_today_relevance([hit], entities=[])
    assert kept == [hit]
    record = hit_to_record(hit, entities=[], today=date(2026, 10, 21))
    projected = model(records={record['id']: record}, entities={}, relationships=[], facts=[], state={}, params={})
    assert projected['matching_ids'] == [record['id']]
    assert record['berry_ids'] == ['berry-strawberry']
