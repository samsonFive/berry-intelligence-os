"""Dossier/timeline Fact links open the exact record without changing trust."""
from copy import deepcopy
import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app import main
from app.services.canonical_statements import statement_detail


def source(identity='ev-first', **changes):
    return dict(dict(id=identity, record_type='evidence', status='published',
        source_type='trade_press', source_name='Fixture publisher', title='Named source '+identity,
        source_url='https://example.test/article?original=1', published_date='2024-02-01',
        captured_date='2026-08-03', summary='Recorded reporting', submitted_by='fixture',
        entity_ids=[], berry_ids=[], fact_ids=[], relationship_ids=[], strategic_question_ids=[], tags=[], priority={}), **changes)


def fact(**changes):
    return dict(dict(id='fact-fixture', record_type='fact', statement='A qualified claim [limited scope].',
        classification='claim', confidence='medium', status='active', reviewer='Fixture reviewer',
        created_at='2026-08-03', event_date='2024-02-01', evidence_ids=['ev-first','ev-second'],
        entity_ids=['company-fixture']), **changes)


def test_every_citation_retains_order_original_url_classification_dates_and_inputs():
    record=fact(evidence_ids=['ev-second','ev-first','ev-second','ev-missing'])
    sources=[source(),source('ev-second')]
    entities={'company-fixture':dict(id='company-fixture',entity_type='company',name='Fixture company')}
    before=deepcopy((record,sources,entities))
    view=statement_detail(record,sources,entities)
    assert view['statement']==record['statement'] and view['classification']=='claim'
    assert view['status']=='active' and view['event_date']=='2024-02-01' and view['recorded_date']=='2026-08-03'
    assert [row['id']for row in view['sources']]==['ev-second','ev-first']
    assert all(row['original_url']=='https://example.test/article?original=1'for row in view['sources'])
    assert view['unavailable_sources']==1 and view['linked_entities']==list(entities.values())
    assert (record,sources,entities)==before


@pytest.mark.parametrize('changes',[{'status':'draft'},{'live':True},{'trust_state':'LIVE'},
    {'auto_captured':True,'validated':False},{'submitted_by':'auto','review_state':'unreviewed'}])
def test_pending_live_and_unvalidated_sources_cannot_supply_public_detail(changes):
    record=fact(evidence_ids=['ev-first'])
    # The canonical statement already appears in published dossiers. Missing
    # sources stay explicit; their unreviewed titles/URLs do not become public.
    view=statement_detail(record,[source(**changes)],{})
    assert view['sources']==[] and view['unavailable_sources']==1
    assert 'Named source' not in str(view)


@pytest.mark.parametrize('status',['superseded','withdrawn'])
def test_history_is_explicit_and_not_a_new_public_finding(status):
    record=fact(status=status)
    assert statement_detail(record,[source()],{}) is None
    view=statement_detail(record,[source()],{},include_history=True)
    assert view['status']==status and view['is_history']


def test_safe_urls_and_escaped_literal_wording_no_body_or_unpublished_title(monkeypatch,tmp_path):
    record=fact(statement='<script>alert(1)</script> [Analyst qualifier]',evidence_ids=['ev-first','ev-hidden'])
    sources=[source(source_url='javascript:alert(1)',article={'paragraphs':[{'text':'Unrequested article body'}]}),
             source('ev-hidden',status='draft',title='PRIVATE DRAFT TITLE')]
    monkeypatch.setattr(main,'INBOX_DIR',tmp_path)
    monkeypatch.setattr(main,'all_facts',lambda:[record])
    selected = []
    def get_source(identity):
        selected.append(identity)
        return next((row for row in sources if row['id']==identity),None)
    monkeypatch.setattr(main,'get_repositories',lambda *args:SimpleNamespace(evidence=SimpleNamespace(get=get_source)))
    def no_full_corpus():
        raise AssertionError('A statement detail must not copy every article body')
    monkeypatch.setattr(main,'published_evidence',no_full_corpus)
    monkeypatch.setattr(main,'entity_index',lambda:{})
    monkeypatch.setattr(main,'AUTHORING_MODE',True)
    response=TestClient(main.app).get('/facts/fact-fixture')
    assert response.status_code==200
    assert '&lt;script&gt;alert(1)&lt;/script&gt; [Analyst qualifier]' in response.text
    assert '<script>alert(1)</script>' not in response.text
    assert 'javascript:' not in response.text and 'PRIVATE DRAFT TITLE' not in response.text
    assert 'Unrequested article body' not in response.text and '<form' not in response.text
    assert 'data-open-reader data-item-id="ev-first"' in response.text
    assert 'recorded claim' in response.text and 'verified fact' in response.text
    assert selected==['ev-first','ev-hidden']
    assert list(tmp_path.iterdir())==[]


def test_existing_missing_and_output_excluded_records_use_existing_read_boundary(monkeypatch,tmp_path):
    monkeypatch.setattr(main,'INBOX_DIR',tmp_path)
    monkeypatch.setattr(main,'AUTHORING_MODE',False)
    client=TestClient(main.app)
    response=client.get('/facts/fact-agrovision-peru-scale')
    assert response.status_code==200
    assert 'Agrovision describes itself as' in response.text and '>Claim</span>' in response.text
    assert 'ev-agrovision-10-years-2024' in response.text and 'ev-blueberriesconsulting-agrovision-2024' in response.text
    assert client.get('/facts/fact-does-not-exist').status_code==404
    # An eligible-output exclusion must not be bypassed via a direct raw get.
    monkeypatch.setattr(main,'all_facts',lambda:[])
    assert client.get('/facts/fact-agrovision-peru-scale').status_code==404
    assert list(tmp_path.iterdir())==[]


def test_remote_route_requires_existing_login(monkeypatch,tmp_path):
    monkeypatch.setattr(main,'INBOX_DIR',tmp_path)
    monkeypatch.setenv('BIOS_REMOTE_INTERACTIVE','true')
    monkeypatch.setenv('BIOS_REVIEW_USERNAME','fixture-statement-login')
    monkeypatch.setenv('BIOS_REVIEW_PASSWORD','fixture-statement-only')
    monkeypatch.setenv('BIOS_SESSION_SECRET','fixture-statement-login-secret-at-least-32-characters')
    monkeypatch.setenv('BIOS_BASIC_AUTH','false')
    response=TestClient(main.app,follow_redirects=False).get('/facts/fact-agrovision-peru-scale')
    assert response.status_code in {302,303,307} and '/login' in response.headers['location']


def test_static_library_has_relocatable_statement_and_all_published_source_links(monkeypatch,tmp_path):
    data=tmp_path/'data';(data/'evidence').mkdir(parents=True)
    sources=[source(),source('ev-second'),source('ev-hidden',status='draft',title='PRIVATE DRAFT TITLE')]
    for row in sources:(data/'evidence'/f"{row['id']}.json").write_text(json.dumps(row),encoding='utf-8')
    (data/'facts').mkdir()
    records=[fact(evidence_ids=['ev-first','ev-second','ev-hidden']),
             fact(id='fact-withdrawn',status='withdrawn',statement='PRIVATE WITHDRAWN FINDING')]
    for row in records:(data/'facts'/f"{row['id']}.json").write_text(json.dumps(row),encoding='utf-8')
    monkeypatch.setattr(main,'DATA_DIR',data)
    monkeypatch.setattr(main,'INBOX_DIR',tmp_path/'inbox')
    import scripts.build_static as build
    monkeypatch.setattr(build,'DATA_DIR',data)
    monkeypatch.setattr(build,'OUTPUT_DIR',tmp_path/'generated')
    build.build()
    page=build.OUTPUT_DIR/'facts/fact-fixture/index.html'
    assert page.is_file()
    html=page.read_text(encoding='utf-8')
    assert '../../evidence/ev-first/index.html' in html and '../../evidence/ev-second/index.html' in html
    assert 'data-open-reader' not in html and 'PRIVATE DRAFT TITLE' not in html
    assert not (build.OUTPUT_DIR/'facts/fact-withdrawn/index.html').exists()
    assert 'PRIVATE WITHDRAWN FINDING' not in html
    assert '<form' not in html and 'Fixture reviewer' not in html
