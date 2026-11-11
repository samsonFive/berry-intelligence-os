"""Regressions from source-reviewed labor enforcement and official food alerts."""
from datetime import date
import feedparser
import pytest
from app.services.feed_first_live import hit_to_record
from app.services.industry_pulse.models import DiscoveryHit
from app.services.industry_pulse.qualify import qualify_hit
from app.services.industry_pulse.specialist_feeds import SpecialistRssProvider,priority_publisher_feeds,week_specialist_feed_queries
from app.services.news_workspace import model
from app.services.today_relevance import apply_today_relevance


def hit(title,summary='',url='https://publisher.example/article'):
    return DiscoveryHit(title=title,snippet=summary,url=url,source_domain='',published_date='2026-11-11',
        query_id='feed:priority:control',query_text='',geography='global',berry=None,topic=None,
        provider='specialist_rss',provider_metadata={'publisher_route':'direct_rss'})


@pytest.mark.parametrize('title,summary,crop',[
    ('Blueberry labor hire firm fined A$75,600 over worker underpayments',
     'An Australian labor hire company and its director failed to comply with notices requiring back-payments to two migrant workers employed in blueberry harvesting near Coffs Harbour.','blueberry'),
    ('NSW labour hire operator penalised for breaches affecting migrant fruit pickers',
     'Compliance Notices required back-payments to workers supplied to pick blueberries on farms in the Coffs Harbour region.','blueberry'),
    ('Blackberry workers seek guaranteed minimum wage','', 'blackberry'),
    ('Raspberry farm faces irrigation restrictions','', 'raspberry'),
    ('Strawberry workers report wage underpayments','', 'strawberry'),
    ('Dole brand Fresh Packed Blueberries recalled due to Cyclospora','', 'blueberry'),
    ("Rappel de bleuets de marque Driscoll’s en raison de la présence de morceaux de métal",'', 'blueberry'),
    ('Blueberry desserts recalled due to Listeria contamination','', 'blueberry'),
])
def test_material_events_survive_collection_and_current_news(title,summary,crop):
    candidate=qualify_hit(hit(title,summary))
    assert candidate.qualifying,candidate.qualify_reason
    assert apply_today_relevance([candidate],entities=[])[0]==[candidate]
    row=hit_to_record(candidate,entities=[],today=date(2026,11,11))
    assert row['berry_ids']==['berry-'+crop]
    assert row['review_state']=='UNREVIEWED'
    assert model(records={row['id']:row},entities={},relationships=[],facts=[],state={},params={})['matching_ids']==[row['id']]


@pytest.mark.parametrize('title',[
    'BlackBerry faces worker underpayments investigation',
    'BlackBerry Limited reports labour shortage',
    'Raspberry Pi payroll software for workers',
    'Blueberry dessert recipe recalled by grandmother',
    'Rappel de bleuets pour les bouquets de fleurs',
    'Strawberry print shelf paper recalled due to contamination',
    'Carrot workers report wage underpayments',
    'Strawberry farm job posting apply now minimum wage',
])
def test_material_topics_do_not_override_identity_or_consumer_exclusions(title):
    assert not qualify_hit(hit(title)).qualifying


@pytest.mark.parametrize('key,title,path,crop',[
    ('en',"Driscoll's brand blueberries recalled due to pieces of metal",'en/alert-recall/driscoll-s-brand-blueberries-recalled-due-pieces-metal','blueberry'),
    ('fr',"Rappel de bleuets de marque Driscoll’s en raison de la présence de morceaux de métal",'fr/avis-rappel/rappel-bleuets-marque-driscoll-s-en-raison-presence-morceaux-metal','blueberry'),
])
def test_declared_canada_food_feeds_parse_original_links_and_day_precision(key,title,path,crop):
    route=next(r for r in priority_publisher_feeds() if r['id']==f'feed:priority:canada-food-{key}:rss')
    assert route['source_type']=='government_document'
    query=next(q for q in week_specialist_feed_queries(include_priority=True) if q.id==route['id'])
    raw=f'<rss version="2.0"><channel><title>Food recalls</title><item><title>{title}</title><link>https://recalls-rappels.canada.ca/{path}</link><pubDate>2022-01-20T12:00:00</pubDate></item></channel></rss>'.encode()
    provider=SpecialistRssProvider(fetch=lambda _:(feedparser.parse(raw),raw))
    candidate=provider.discover(query)[0]
    assert candidate.published_date=='2022-01-20'
    assert candidate.url==f'recalls-rappels.canada.ca/{path}'
    assert qualify_hit(candidate).qualifying
    row=hit_to_record(candidate,entities=[],today=date(2022,1,20))
    assert row['berry_ids']==['berry-'+crop]
    assert row['source_type']=='government_document'
