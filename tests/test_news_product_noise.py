"""Observed global feed false positives must fail discovery and projection."""
import pytest
from app.services.industry_pulse.models import DiscoveryHit
from app.services.industry_pulse.qualify import qualify_hit
from app.services.news_workspace import model


@pytest.mark.parametrize('title', [
    'Blackberry Tokenized bStocks price today, BBB to USD chart, marketcap and volume - CryptoSlate',
    'Blackberry tokenised stocks price today',
    'Vintage Roylcraft Shelf Paper Fruit Border Watermelon Strawberry 9in x 5yds NEW khorasantimes.com',
    'Strawberry print shelf-liner production expands',
])
def test_nonagricultural_product_is_excluded_at_both_stages(title):
    hit=DiscoveryHit(title=title,snippet=title,url='https://fixture.test/article',source_domain='fixture.test',
        published_date='2026-11-11',query_id='feed:priority:fixture',query_text='',geography='global',
        berry=None,topic=None,provider='specialist_rss')
    assert not qualify_hit(hit).qualifying
    row={'id':'live-noise-control','title':title,'summary':title,'source_type':'news_search',
        'source_url':hit.url,'published_date':hit.published_date,'status':'unreviewed'}
    assert not model(records={row['id']:row},entities={},relationships=[],facts=[],state={},params={})['matching_ids']


@pytest.mark.parametrize('title', [
    'Strawberry growers trial packaging to extend shelf life',
    'Blackberry growers use blockchain traceability for fruit exports',
    'BlackBerry software supports strawberry farm robotics and harvest monitoring',
])
def test_agricultural_packaging_and_technology_remain_available(title):
    hit=DiscoveryHit(title=title,snippet='',url='https://fixture.test/article',source_domain='fixture.test',
        published_date='2026-11-11',query_id='fixture',query_text='',geography='global',berry=None,
        topic=None,provider='memory')
    assert qualify_hit(hit).qualifying
