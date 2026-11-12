"""Source-shaped primary records and local-language relevance regressions."""
from copy import deepcopy
from datetime import date
import json

import feedparser
import pytest

from app.services.feed_first_live import hit_to_record
from app.services.industry_pulse.models import DiscoveryHit
from app.services.industry_pulse.qualify import qualify_hit
from app.services.industry_pulse.regional_news import regional_news_queries, regional_crop_ids
from app.services.industry_pulse.specialist_feeds import SpecialistRssProvider, priority_publisher_feeds, week_specialist_feed_queries
from app.services.news_workspace import model
from app.services.today_relevance import apply_today_relevance


def candidate(title, summary=''):
    return DiscoveryHit(title=title, snippet=summary, url='https://publisher.example/news/1',
        source_domain='publisher.example', published_date='2026-11-05', query_id='control',
        query_text='', geography='global', berry=None, topic=None, provider='specialist_rss',
        provider_metadata={'publisher_route': 'direct_rss'})


@pytest.mark.parametrize('title,summary,crops', [
    ('NALED: Izvoz smrznutog voća mogao bi da poraste za 90 miliona dolara',
     'Srbija ima dodatni izvozni potencijal od 90 miliona dolara za smrznute maline, kupine i drugo bobičasto voće, pokazuje analiza NALED-a.', ['raspberry','blackberry']),
    ('Извоз малине и купине из Србије', '', ['raspberry','blackberry']),
    ('Proizvođači jagode očekuju bolju berbu', '', ['strawberry']),
    ('Производња боровнице и наводњавање', '', ['blueberry']),
    ('Xuất khẩu dâu tây từ Sơn La', '', ['strawberry']),
    ('Sản lượng việt quất và thị trường xuất khẩu', '', ['blueberry']),
    ('Trồng phúc bồn tử phục vụ thị trường', '', ['raspberry']),
    ('Thu hoạch mâm xôi đen', '', ['blackberry']),
    ('FRAMBOISES SURGELEES', 'Risques : Norovirus. Motif : contamination par des norovirus.', ['raspberry']),
    ('MÛRES SURGELÉES', 'Motif : présence de Listeria monocytogenes.', ['blackberry']),
    ('Myrtille marocaine : la main-d’œuvre, premier frein identifié par les professionnels',
     'Les professionnels interrogés placent le coût de la main-d’œuvre devant l’eau et la concurrence internationale.', ['blueberry']),
])
def test_native_primary_metadata_survives_discovery_projection_and_crop_filters(title, summary, crops):
    hit = qualify_hit(candidate(title, summary))
    assert hit.qualifying, hit.qualify_reason
    assert apply_today_relevance([hit], entities=[])[0] == [hit]
    record = hit_to_record(hit, entities=[], today=date(2026,11,12))
    assert set(record['berry_ids']) == {'berry-'+crop for crop in crops}
    assert record['title'] == title and record['summary'] == summary
    assert record['review_state'] == 'UNREVIEWED'
    assert not record['entity_ids']
    assert model(records={record['id']:record},entities={},relationships=[],facts=[],state={},params={})['matching_ids'] == [record['id']]


@pytest.mark.parametrize('title', [
    'Recept za maline i kupine', 'Рецепт за малине',
    'Công thức dâu tây cho gia đình', 'Trồng dâu nuôi tằm',
    'Fruits mûres et marché automobile', 'Roboti pakuju krompir u Guči',
    'Xuất khẩu cà chua tăng trưởng', 'BlackBerry launches automotive software in China',
])
def test_language_expansion_does_not_assign_ambiguous_fruit_or_admit_observed_noise(title):
    assert not qualify_hit(candidate(title)).qualifying
    assert not regional_crop_ids('Trồng dâu nuôi tằm')
    assert not regional_crop_ids('Fruits mûres')


def query(key):
    return next(q for q in week_specialist_feed_queries(include_priority=True) if q.id==key)


def alert():
    return {'@id':'http://data.food.gov.uk/food-alerts/id/FSA-PRIN-29-2026',
        'notation':'FSA-PRIN-29-2026','created':'2026-06-23','modified':'2026-06-24T10:00:00Z',
        'title':'Prepworld recalls fruit products because of possible contamination with Salmonella',
        'alertURL':'https://alerts.food.gov.uk/news-alerts/alert/fsa-prin-29-2026',
        'status':{'label':'Published'}, 'productDetails':[{'productName':'Strawberry & Grape'}],
        'problem':[{'riskStatement':'Possible contamination with Salmonella.'}]}


def provider_for(rows):
    payload={'items':rows}
    return SpecialistRssProvider(fetch=lambda _: (payload,json.dumps(payload).encode()))


def test_opaque_official_alert_headline_uses_publisher_product_names_and_original_created_day():
    q=query('feed:priority:uk-food-alerts:json')
    hit=provider_for([alert()]).discover(q)[0]
    assert 'Strawberry & Grape' in hit.snippet
    assert hit.published_date=='2026-06-23'
    assert hit.provider_metadata['date_basis']=='publisher_created_day'
    assert qualify_hit(hit).qualifying
    record=hit_to_record(hit,entities=[],today=date(2026,11,12))
    assert record['berry_ids']==['berry-strawberry']
    assert record['source_type']=='government_document'
    assert record['discovery_provenance']['official_record_id']=='FSA-PRIN-29-2026'
    assert record['discovery_provenance']['date_basis']=='publisher_created_day'
    assert record['review_state']=='UNREVIEWED'
    assert model(records={record['id']:record},entities={},relationships=[],facts=[],state={},params={})['matching_ids']==[record['id']]


@pytest.mark.parametrize('changes', [
    {'alertURL':'http://alerts.food.gov.uk/news-alerts/alert/1'},
    {'alertURL':'https://food.gov.uk.attacker.example/news-alerts/alert/1'},
    {'alertURL':'https://user:secret@alerts.food.gov.uk/news-alerts/alert/1'},
    {'alertURL':'https://127.0.0.1/news-alerts/alert/1'},
    {'alertURL':'https://alerts.food.gov.uk:wrong/news-alerts/alert/1'},
    {'alertURL':'https://alerts.food.gov.uk/login'}, {'created':None},
    {'created':'not-a-date'}, {'status':{'label':'Draft'}}, {'status':'Published'},
])
def test_official_adapter_does_not_follow_unverified_links_or_substitute_modified_dates(changes):
    row=alert();row.update(changes)
    assert provider_for([row]).discover(query('feed:priority:uk-food-alerts:json'))==[]


def test_official_page_is_bounded_and_nonberry_alerts_remain_excluded():
    row=alert();row.update(title='Chicken recalled due to Salmonella',productDetails=[{'productName':'Chicken'}])
    hits=provider_for([row]*101).discover(query('feed:priority:uk-food-alerts:json'))
    assert len(hits)==100
    assert all(not qualify_hit(hit).qualifying for hit in hits)
    assert apply_today_relevance(hits,entities=[])[0]==[]


def test_serbian_feed_keeps_original_links_dates_and_attribution_without_source_approval():
    q=query('feed:priority:serbia-stips:rss')
    raw='''<rss version="2.0"><channel><item><title>NALED: Izvoz smrznutog voća</title>
    <link>https://www.stips.minpolj.gov.rs/srl/vest/naled-izvoz</link>
    <pubDate>Thu, 05 Nov 2026 06:23:54 +0000</pubDate>
    <description>Srbija ima dodatni izvozni potencijal za smrznute maline i kupine, pokazuje analiza NALED-a.</description>
    </item></channel></rss>'''.encode()
    hit=SpecialistRssProvider(fetch=lambda _: (feedparser.parse(raw),raw)).discover(q)[0]
    assert hit.published_date=='2026-11-05'
    assert hit.url.endswith('/srl/vest/naled-izvoz')
    assert qualify_hit(hit).qualifying
    assert hit.provider_metadata['specialist_source_id']==''
    feeds=priority_publisher_feeds()
    assert len({f['id'] for f in feeds})==len(feeds)
    assert {'RS:sr','VN:vi'} <= {q.ceid for q in regional_news_queries()}
    assert not any('senasacontigo/feed' in f['feed_url'] for f in feeds)
