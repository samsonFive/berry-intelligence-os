from dataclasses import replace
from datetime import date
from urllib.parse import parse_qs, urlsplit
import feedparser

import pytest

from app.services.feed_first_live import hit_to_record
from app.services.industry_pulse.global_publishers import expanded_publisher_feeds
from app.services.industry_pulse.models import DiscoveryHit
from app.services.industry_pulse.qualify import qualify_hit
from app.services.industry_pulse.regional_news import regional_crop_ids, regional_news_queries
from app.services.industry_pulse.specialist_feeds import SpecialistRssProvider, priority_publisher_feeds, week_specialist_feed_queries
from app.services.today_relevance import apply_today_relevance


def hit(title):
    return DiscoveryHit(title=title,url='https://publisher.example/news/1',source_domain='publisher.example',
        published_date='2026-11-11',snippet='',query_id='regional-fixture',query_text='',geography='global',
        berry=None,topic=None,provider='specialist_rss',provider_metadata={'publisher_route':'direct_rss'})


@pytest.mark.parametrize('title,crop',[
    ('زيادة صادرات الفراولة من المغرب','strawberry'),
    ('الجفاف يهدد إنتاج التوت الأزرق في المغرب','blueberry'),
    ('Dürre reduziert die Ernte von Heidelbeeren','blueberry'),
    ('Erzeuger steigern Exporte von Erdbeeren','strawberry'),
    ('Frost gefährdet die Ernte von Himbeeren','raspberry'),
    ('Neue Sorten für den Anbau von Brombeeren','blackberry'),
    ('Récolte de bleuets sauvages au Québec','blueberry'),
    ('Heladas afectan la cosecha de frutillas en Ñuble','strawberry'),
    ('Exportación de mora de Castilla en Colombia','blackberry'),
    ('Incertidumbre por El Niño y expectativa de mayores precios marcan la temporada de arándanos en Ñuble','blueberry'),
    ('Hausse des recettes d’exportation de fraises au Maroc','strawberry'),
])
def test_native_news_survives_both_screens_without_inferred_crop(title,crop):
    candidate=qualify_hit(hit(title))
    assert candidate.qualifying
    assert apply_today_relevance([candidate],entities=[])[0]==[candidate]
    record=hit_to_record(candidate,today=date(2026,11,11),entities=[])
    assert record['berry_ids']==['berry-'+crop]
    assert record['review_state']=='UNREVIEWED'
    assert not record.get('entity_ids')


@pytest.mark.parametrize('title',[
    'وصفة كعكة الفراولة اللذيذة',
    'Erdbeeren mit Sahne: ein einfaches Dessert Rezept',
    'زراعة التوت لإنتاج الحرير',
    'Récolte de bleuets pour les bouquets de fleurs',
    'BlackBerry launches QNX software for the auto industry in China',
    'Carrot exports rise as pineapple farms expand',
    'Recette de fraises au meilleur prix',
    'Recetas de fresas cuando suben los precios',
])
def test_new_vocabulary_does_not_admit_food_software_other_crop_or_ambiguous_names(title):
    assert not qualify_hit(hit(title)).qualifying


def test_publisher_inventory_covers_mainstream_and_regional_with_working_feed_fallbacks():
    rows=priority_publisher_feeds()
    assert len({r['id'] for r in rows})==len(rows)
    hosts={r['host'] for r in rows}
    assert {'nytimes.com','wsj.com','reuters.com','apnews.com','hespress.com','ladiscusion.cl',
            'laterre.ca','cbc.ca','diariodehuelva.es','agronegocios.co','rnz.co.nz'}<=hosts
    # The stale January 2025 WSJ RSS is deliberately excluded.
    assert not any('feeds.a.dj.com' in r['feed_url'] for r in rows)
    for r in expanded_publisher_feeds():
        if r['route']=='indexed':
            query=parse_qs(urlsplit(r['feed_url']).query)['q'][0]
            assert 'when:7d' in query and 'site:'+r['host'] in query


def test_new_native_queries_have_unique_ids_and_no_generic_arabic_mulberry_identity():
    queries=regional_news_queries()
    assert len({q.id for q in queries})==len(queries)
    assert {'MA:ar','EG:ar','DE:de','CA:fr','PE:es','CL:es','CO:es'}<={q.ceid for q in queries}
    assert not regional_crop_ids('زراعة التوت لإنتاج الحرير')


def test_bbc_host_alias_preserves_publisher_boundary():
    query=next(q for q in week_specialist_feed_queries(include_priority=True) if q.id=='feed:priority:bbc-business:rss')
    def feed(link):
        return f'<rss version="2.0"><channel><title>BBC News</title><item><title>Strawberry growers report export growth</title><link>{link}</link><pubDate>Wed, 11 Nov 2026 12:00:00 GMT</pubDate></item></channel></rss>'.encode()
    def parsed(link):
        raw=feed(link)
        return feedparser.parse(raw),raw
    provider=SpecialistRssProvider(fetch=lambda _:parsed('https://www.bbc.com/news/articles/example'))
    assert provider.discover(query)[0].source_domain=='bbc.com'
    provider.fetch=lambda _:parsed('https://impostor.example/news/1')
    with pytest.raises(ValueError,match='declared host'):
        provider.discover(query)
