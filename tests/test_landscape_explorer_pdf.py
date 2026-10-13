"""Real PDF parsing: complete scope, Unicode, links, pagination and privacy."""
from copy import deepcopy
from io import BytesIO

import pytest
from pypdf import PdfReader

from test_landscape_explorer import world, client_world, build
from app.services.landscape_explorer_pdf import pdf_export


def text_and_reader(body):
    reader = PdfReader(BytesIO(body))
    return "\n".join(page.extract_text() for page in reader.pages), reader


def test_pdf_keeps_full_scope_dates_provenance_links_and_no_mutations(world):
    bundle=build(world,countries='',focus='variety-a',window='custom',start='2026-09-01',end='2026-10-02',time='event')
    before=deepcopy(bundle)
    body=pdf_export(bundle,return_url='https://example.test'+bundle['url'])
    assert body.startswith(b'%PDF-') and bundle==before
    text,reader=text_and_reader(body)
    for edge in bundle['edges']:
        assert edge['id'] in text and edge['role'] in text
    assert bundle['version'] in text and bundle['generated_at'] in text
    assert '2026-09-01 to 2026-10-02' in text and 'Azure' in text
    assert 'Company locations do not establish' in text
    assert 'Source summary' in text and bundle['sources'][0]['id'] in text
    uris=[a.get_object().get('/A',{}).get('/URI') for page in reader.pages for a in page.get('/Annots',[])]
    assert bundle['sources'][0]['url'] in uris
    assert 'https://example.test'+bundle['url'] in uris
    assert all('Page '+str(i) in page.extract_text() for i,page in enumerate(reader.pages,1))


def test_pdf_comparison_preserves_distinct_cultivars_and_crop_scopes(world):
    bundle=build(world,berry='berry-blueberry',compare='berry-strawberry',view='compare',countries='')
    text,_=text_and_reader(pdf_export(bundle))
    assert 'Blueberry vs Strawberry landscapes' in text
    assert 'Shared company' in text and 'Strawberry cultivar' in text
    assert 'r-other-berry' in text and 'r-develops' in text
    assert 'Recorded coverage by crop' in text
    assert 'Direct genetics-location links' in text and '\n0' in text


def test_pdf_unicode_and_long_sources_paginate_without_loss(world):
    world['entities']['company-a']['name']='José Łódź α - 中国'
    world['evidence'][0]['title']='Título β - 東京'
    world['evidence'][0]['summary']='BEGIN SUMMARY '+('long original summary content '*200)+' END SUMMARY'
    world['relationships'][0]['notes']='BEGIN NOTES '+('a long scoped relationship note '*200)+' END NOTES'
    text,reader=text_and_reader(pdf_export(build(world,countries='')))
    for value in ('José','Łódź','α','中国','Título','β','東京','BEGIN SUMMARY','END SUMMARY','BEGIN NOTES','END NOTES'):
        assert value in text
    assert len(reader.pages)>1 and '\u25a0' not in text and '\ufffd' not in text


def test_pdf_repeated_notes_share_context_without_merging_connections(world):
    note='Shared exact context: trial scope is not a universal trait.'
    for relationship in world['relationships']:
        relationship['notes']=note
    bundle=build(world,countries='')
    text,_=text_and_reader(pdf_export(bundle))
    assert text.count(note)==1
    assert text.count('Context note 1')==len(bundle['edges'])+1
    assert all(edge['id'] in ''.join(text.split()) for edge in bundle['edges'])


def test_pdf_display_limits_do_not_remove_relationships(world):
    for index in range(65):
        key='variety-'+str(index)
        world['entities'][key]={'id':key,'name':'Cultivar '+str(index),'entity_type':'variety','berry_ids':['berry-blueberry']}
        world['relationships'].append({'id':'r-extra-'+str(index),'subject_id':'company-a','predicate':'licenses','object_id':key,'status':'active','evidence_ids':['ev-a']})
    bundle=build(world,countries='',limit=20)
    assert bundle['coverage']['truncated_display']
    text,_=text_and_reader(pdf_export(bundle))
    assert all(edge['id'] in text for edge in bundle['edges'])


def test_pdf_comparison_oversized_company_row_paginate_without_clipping(world):
    for index in range(110):
        key='variety-tall-'+str(index)
        world['entities'][key]={'id':key,'name':'Long portfolio cultivar '+str(index),'entity_type':'variety','berry_ids':['berry-blueberry']}
        world['relationships'].append({'id':'r-tall-'+str(index),'subject_id':'company-a','predicate':'licenses','object_id':key,'status':'active','evidence_ids':['ev-a']})
    bundle=build(world,berry='berry-blueberry',compare='berry-strawberry',view='compare',countries='')
    text,reader=text_and_reader(pdf_export(bundle))
    assert len(reader.pages)>1
    assert 'Long portfolio cultivar 0' in text and 'Long portfolio cultivar 109' in text
    assert all(edge['id'] in ''.join(text.split()) for edge in bundle['edges'])


def test_download_uses_same_policy_bundle_and_filename(client_world,world):
    world['evidence'].append({'id':'ev-pending','title':'Unreviewed test source','status':'in_review','berry_ids':['berry-blueberry']})
    world['relationships'].append({'id':'r-pending','subject_id':'company-a','object_id':'variety-a','predicate':'licenses','status':'disputed','evidence_ids':['ev-pending']})
    query='berry=berry-blueberry&compare=berry-strawberry&view=compare&countries='
    reviewed=client_world.get('/landscapes/explorer/export/pdf?'+query)
    assert reviewed.status_code==200 and reviewed.headers['content-type']=='application/pdf'
    assert 'blueberry-vs-strawberry-landscape-' in reviewed.headers['content-disposition']
    assert reviewed.headers['cache-control']=='private, no-store'
    assert 'Unreviewed test source' not in text_and_reader(reviewed.content)[0]
    all_news=client_world.get('/landscapes/explorer/export/pdf?'+query+'&evidence=all')
    text,_=text_and_reader(all_news.content)
    assert 'Unreviewed test source' in text and 'Disputed / review required' in text
    api=client_world.get('/api/landscapes/explorer?'+query+'&evidence=all').json()
    assert api['version'] in text and all(e['id'] in text for e in api['edges'])


def test_pdf_empty_scope_is_readable(client_world):
    response=client_world.get('/landscapes/explorer/export/pdf?countries=geography-china')
    text,_=text_and_reader(response.content)
    assert response.status_code==200 and 'No sourced relationships match this selection.' in text


def test_pdf_cannot_bypass_authoring_or_login(client_world,monkeypatch):
    import app.main as main
    monkeypatch.setattr(main,'AUTHORING_MODE',False)
    assert client_world.get('/landscapes/explorer/export/pdf').status_code==404
    monkeypatch.setattr(main,'AUTHORING_MODE',True)
    monkeypatch.setenv('BIOS_REMOTE_INTERACTIVE','true')
    monkeypatch.setenv('BIOS_REVIEW_USERNAME','test-reviewer')
    monkeypatch.setenv('BIOS_REVIEW_PASSWORD','test-only-password')
    monkeypatch.setenv('BIOS_SESSION_SECRET','test-only-secret-with-sufficient-signing-length')
    response=client_world.get('/landscapes/explorer/export/pdf',follow_redirects=False)
    assert response.status_code in {302,401} and not response.content.startswith(b'%PDF-')
