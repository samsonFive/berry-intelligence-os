from io import BytesIO
from unittest.mock import patch
import subprocess

import httpx
from reportlab.pdfgen import canvas

from app.services import feed_first_reader as reader
from app.services.topic_retrieval import match_record,plan_query


def compressed_pdf(pages=2):
    buffer=BytesIO();pdf=canvas.Canvas(buffer,pageCompression=1)
    for i in range(pages):
        pdf.drawString(60,740,'Synthetic fixture: floricane blackberry trial reported on page '+str(i+1))
        pdf.showPage()
    pdf.save();return buffer.getvalue()


def test_compressed_pdf_is_searchable_with_page_locators_and_is_not_a_full_article_claim():
    raw=compressed_pdf()
    assert b'/FlateDecode' in raw
    with httpx.Client(transport=httpx.MockTransport(lambda request:httpx.Response(200,content=raw,headers={'content-type':'application/pdf'}))) as client:
        result=reader.fetch_public_article('https://publisher.example/trials.pdf',client=client)
    assert result['ok'] and result['availability']=='excerpt_only'
    assert result['pdf_page_count']==2 and not result['truncated']
    assert result['passage_locators']==['pdf:page:1','pdf:page:2']
    row={'id':'ev-pdf','title':'Synthetic trial','source_url':'https://publisher.example/trials.pdf','article':{'paragraphs':[{'index':i,'text':p,'locator':result['passage_locators'][i]} for i,p in enumerate(result['passages'])]}}
    match=match_record(row,plan_query('floricane blackberry trial'))
    assert match and match['passage_locator'].startswith('pdf:page:')


def test_pdf_timeout_fails_closed_without_claiming_body_availability():
    with patch.object(reader.subprocess,'run',side_effect=subprocess.TimeoutExpired('fixture',6)):
        assert reader.extract_pdf_text(compressed_pdf())==[]


def test_pdf_page_limit_is_disclosed_in_capture_status():
    raw=compressed_pdf(33)
    with httpx.Client(transport=httpx.MockTransport(lambda request:httpx.Response(200,content=raw,headers={'content-type':'application/pdf'}))) as client:
        result=reader.fetch_public_article('https://publisher.example/trials.pdf',client=client)
    assert len(result['passages'])==32 and result['pdf_page_count']==33
    assert result['truncated'] and result['reason']=='pdf-text-limit'
