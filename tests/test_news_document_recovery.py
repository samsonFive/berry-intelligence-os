"""Observed public-record parsing gaps, with real bounded PDF extraction."""
from dataclasses import replace
from io import BytesIO
import httpx
import pytest
from reportlab.pdfgen import canvas

from app.services import article_acquisition as aa
from app.services import feed_first_reader as reader
from app.services.source_body import classify_source_body, reader_content
from app.services.source_completeness import source_completeness
from app.services.industry_pulse.models import DiscoveryHit
from app.services.industry_pulse.qualify import qualify_hit
from app.services.feed_first_live import hit_to_record
from app.services.news_workspace import model
from datetime import date


def pdf_bytes():
    stream=BytesIO();pdf=canvas.Canvas(stream,pageCompression=1)
    for page in (1,2):
        for line in range(7):
            pdf.drawString(40,740-line*20,f'Synthetic blueberry production report page {page}, source line {line}.')
        pdf.showPage()
    pdf.save();return stream.getvalue()


def test_normal_article_intake_uses_bounded_reader_for_pdf_and_preserves_limited_status(monkeypatch):
    raw=pdf_bytes();client_type=httpx.Client
    monkeypatch.setattr(aa.httpx,'Client',lambda **kwargs:client_type(
        transport=httpx.MockTransport(lambda request:httpx.Response(200,content=raw,headers={'Content-Type':'application/pdf'})),**kwargs))
    monkeypatch.setattr(aa.httpx,'get',lambda *a,**k:pytest.fail('PDF must not use unbounded HTML transport'))
    body=aa.fetch_article('https://publisher.example/20260922-report.pdf')
    assert body.pdf_page_count==2 and len(body.paragraphs)==2
    assert '[PDF page 1]' in body.paragraphs[0].text and '[PDF page 2]' in body.paragraphs[1].text
    assert body.published_date is None and body.title is None
    data=body.as_dict();assert data['availability']=='excerpt_only' and data['content_kind']=='pdf'
    assert data['paragraphs'][0]['locator']=='pdf:page:1' and data['paragraphs'][1]['locator']=='pdf:page:2'
    record={'id':'ev-fixture','article':data,'summary':'Official blueberry production report'}
    assert classify_source_body(record)['state']=='body_partial'
    assert reader_content(record)['state']=='body_partial'
    assert source_completeness(record)['class']!='FULL_ARTICLE'
    assert replace(body,acquisition_version='article-acquisition-v4').as_dict()['acquisition']['version']=='article-acquisition-v4'


@pytest.mark.parametrize('capture,category',[
    ({'ok':False,'reason':'blocked','status_code':403},'blocked'),
    ({'ok':False,'reason':'timeout'},'timeout'),
    ({'ok':True,'content_kind':'pdf','truncated':True,'reason':'pdf-text-limit'},'empty_body'),
    ({'ok':True,'content_kind':'pdf','passages':['too short']},'empty_body'),
])
def test_pdf_blocked_limited_or_empty_capture_never_becomes_full_article(monkeypatch,capture,category):
    monkeypatch.setattr(reader,'fetch_public_article',lambda *a,**k:capture)
    with pytest.raises(aa.ArticleAcquisitionError) as error:aa.fetch_article('https://publisher.example/report.pdf')
    assert error.value.category==category


def test_statistical_table_and_official_first_publication_metadata_survive_normal_html_acquisition(monkeypatch):
    text='The agricultural land use report describes horticultural production areas and the methods used to estimate them. '
    markup=f'''<html><head><title>Agricultural land use</title>
    <meta name="govuk:first-published-at" content="2026-09-24T09:30:15+01:00">
    <meta name="govuk:updated-at" content="2026-10-21T13:18:38+01:00"></head><body><main><article>
    <h1>Agricultural land use</h1><p>{text*3}</p><h2>Small fruit areas</h2>
    <table><caption>Small fruit areas: synthetic source fixture, hectares</caption>
    <thead><tr><th>Year</th><th>Raspberries</th><th>Wine grapes</th></tr></thead>
    <tbody><tr><td>2025</td><td>100</td><td>200</td></tr><tr><td>2026</td><td>110</td><td>210</td></tr></tbody></table>
    <p>{text*2}</p></article></main></body></html>'''
    url='https://www.gov.uk/government/statistics/land-use'
    monkeypatch.setattr(aa.httpx,'get',lambda *a,**k:httpx.Response(200,text=markup,request=httpx.Request('GET',url)))
    body=aa.fetch_article(url)
    assert 'Raspberries' in body.full_text and '2025' in body.full_text and '110' in body.full_text
    assert body.published_date=='2026-09-24' and body.published_date_basis=='publisher_metadata'
    assert aa.publisher_publication_date(markup,'https://unrelated.example/report')==(None,'unknown')


@pytest.mark.parametrize('title,summary',[
    ('Caída en las exportaciones de berries de México, pero una categoría sigue creciendo',
     'Las exportaciones mexicanas de berries cayeron. Los envíos de fresas, frambuesas y arándanos disminuyeron.'),
    ('Congreso Mundial de Frambuesas llega por primera vez a México',
     'Congreso Mundial de Frambuesas llega por primera vez a México'),
    ('Arándano peruano: Midagri advierte nuevas presiones productivas tras los sucesivos ajustes de la campaña',
     'Arándano peruano: Midagri advierte nuevas presiones productivas tras los sucesivos ajustes de la campaña'),
])
def test_source_reviewed_spanish_trade_congress_and_season_metadata_is_not_hidden(title,summary):
    hit=DiscoveryHit(title=title,snippet=summary,url='https://publisher.example/story',source_domain='',
        published_date='2026-11-05',query_id='control',query_text='',geography='global',berry=None,topic=None,
        provider='specialist_rss',provider_metadata={'publisher_route':'direct_rss'})
    assert qualify_hit(hit).qualifying
    row=hit_to_record(hit,entities=[],today=date(2026,11,12))
    assert model(records={row['id']:row},entities={},relationships=[],facts=[],state={},params={})['matching_ids']==[row['id']]


@pytest.mark.parametrize('title,summary',[
    ('Full On Flapjacks recalls various Flapjack products because of undeclared allergens',
     'Raspberry Yoghurt Flapjack; Blueberry Swirl Flapjack. Undeclared allergens: Soya and Wheat (gluten).'),
    ('Supplier recalls blueberry muffins because of undeclared allergens','Blueberry muffins contain undeclared milk.'),
    ('FRAMBOISES SURGELEES','Risques : Substances allergisantes non déclarées.'),
])
def test_official_recall_verb_inflections_and_allergen_details_survive(title,summary):
    hit=DiscoveryHit(title=title,snippet=summary,url='https://publisher.example/notice',source_domain='',
        published_date='2026-10-21',query_id='control',query_text='',geography='global',berry=None,topic=None,
        provider='specialist_rss',provider_metadata={'publisher_route':'direct_rss'})
    assert qualify_hit(hit).qualifying
    row=hit_to_record(hit,entities=[],today=date(2026,11,12))
    assert model(records={row['id']:row},entities={},relationships=[],facts=[],state={},params={})['matching_ids']==[row['id']]


@pytest.mark.parametrize('title',[
    'Grandmother recalls her blueberry muffin recipe',
    'BlackBerry recalls QNX devices because of defects',
    'Supplier recalls carrot products because of undeclared allergens',
])
def test_recall_inflections_do_not_override_crop_identity_or_recipe_controls(title):
    hit=DiscoveryHit(title=title,snippet='',url='https://publisher.example/story',source_domain='',
        published_date='2026-11-05',query_id='control',query_text='',geography='global',berry=None,topic=None,
        provider='specialist_rss',provider_metadata={'publisher_route':'direct_rss'})
    assert not qualify_hit(hit).qualifying
