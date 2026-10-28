from copy import deepcopy
from datetime import UTC, datetime
import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient
from starlette.datastructures import QueryParams

from app.services.gene_editing import classify, landscape_model, csv_export, html_export, topic_selection
from app.services.gene_editing_import import import_snapshot
from app.services import feed_first, news_workspace
from scripts.backfill_gene_editing import backfill

ROOT=Path(__file__).resolve().parents[1]
SNAPSHOT=json.loads(sorted((ROOT/'data/imports').glob('gene-editing-*/snapshot.json'))[-1].read_text(encoding='utf-8'))


@pytest.mark.parametrize('text',[
    'CRISPR gene editing creates compact blackberry plants.',
    'Strawberry genome editing targets heat tolerance.',
    'Plant base editing and prime editing improve crops.',
    '植物基因编辑用于草莓育种。',
    'New plant NGT genome editing regulation is published.',
])
def test_explicit_agricultural_editing(text):
    assert 'gene-editing' in classify({'title':text})['topics']


@pytest.mark.parametrize('text',[
    'Pairwise hires finance director.', 'Fall Creek opens a new blueberry nursery.',
    'CRISPR cancer therapy helps patients.', 'AI makes office work faster.',
    'NGT launches a new service in Hudson River.',
    'Genome editing in blueberry is not established in this research pass.',
    'The release does not establish CRISPR use in this strawberry program.',
    'A strawberry grower announces results. Human CRISPR therapy enters clinical trials.',
])
def test_company_monitoring_and_ambiguous_terms_are_not_topic_evidence(text):
    assert classify({'title':text})['topics']==[]


def test_ohalo_separate_from_crispr_and_crop_unassigned_stays_unassigned():
    row={'title':'Ohalo Boosted Breeding plant technology uses whole parental genomes.'}
    result=classify(row)
    assert result['topics']==['advanced-breeding']
    assert not result['berry_related']
    assert 'berry_ids' not in row
    assert topic_selection(QueryParams('topic=gene-editing&topic=advanced-breeding'))==['advanced-breeding','gene-editing']


def test_analyst_classifier_correction_overrides_automatic_tags():
    record={'title':'CRISPR plant editing in strawberry', 'classification':{'origin':'analyst','topics':[],'reviewed_by':'Johnny'}}
    assert classify(record)['topics']==[]
    assert classify({'title':'CRISPR plant editing in strawberry','tags':['topic-exclude-gene-editing']})['topics']==[]


def test_ambiguous_company_aliases_do_not_link_geography_or_ordinary_adjectives():
    from app.services.entity_alias_recall import match_evidence_to_entity
    entities,_=model_data()
    assert not match_evidence_to_entity(entities['company-hudson-river-biotechnology'],
        {'title':'Blueberry festival beside the Hudson River'})
    assert not match_evidence_to_entity(entities['company-heritable-agriculture'],
        {'title':'Heritable traits in strawberry breeding'})


def test_import_is_add_only_url_deduplicated_and_preserves_analyst_corrections(tmp_path):
    data,inbox=tmp_path/'data',tmp_path/'inbox'
    (data/'entities/companies').mkdir(parents=True)
    original={'id':'company-pairwise','entity_type':'company','name':'Analyst corrected name','aliases':['Analyst alias']}
    path=data/'entities/companies/company-pairwise.json'
    path.write_text(json.dumps(original))
    (data/'evidence').mkdir()
    duplicate={**SNAPSHOT['evidence'][0],'id':'ev-already-captured','status':'published'}
    duplicate['source_url'] += '?utm_source=analyst'
    (data/'evidence/ev-already-captured.json').write_text(json.dumps(duplicate))
    first=import_snapshot(SNAPSHOT,data,inbox)
    assert first['duplicate_urls']==1
    assert json.loads(path.read_text())==original
    pending=next((inbox/'evidence').glob('*.json'))
    corrected=json.loads(pending.read_text())
    corrected.update(summary='Human correction',review_state='rejected',status='rejected')
    pending.write_text(json.dumps(corrected))
    before={str(p):p.read_bytes() for folder in (data/'entities',inbox/'evidence') for p in folder.rglob('*.json')}
    second=import_snapshot(SNAPSHOT,data,inbox)
    assert second['companies_created']==second['programs_created']==second['news_created']==second['sources_created']==0
    assert all(Path(p).read_bytes()==content for p,content in before.items())
    assert all(json.loads(p.read_text())['status']!='published' for p in (inbox/'evidence').glob('*.json'))


def test_backfill_preserves_dates_and_manual_decisions(tmp_path):
    path=tmp_path/'ev-old.json'
    row={'id':'ev-old','title':'CRISPR plant editing in strawberry','published_date':'2020-01-01','captured_date':'2026-10-21','status':'in_review'}
    path.write_text(json.dumps(row))
    assert backfill(tmp_path,apply=True)['changed']==1
    after=path.read_bytes()
    assert backfill(tmp_path,apply=True)['changed']==0
    assert path.read_bytes()==after
    result=json.loads(after)
    assert all(result[k]==row[k] for k in ('published_date','captured_date','status'))
    result['classification'].update(origin='analyst',topics=[])
    path.write_text(json.dumps(result))
    assert backfill(tmp_path,apply=True)['analyst_preserved']==1


def model_data():
    entities={r['id']:r for p in (ROOT/'data/entities').rglob('*.json') for r in [json.loads(p.read_text(encoding='utf-8'))]}
    # Real versioned import, not demonstration fixtures.
    return entities,SNAPSHOT['evidence']


def test_landscape_all_seeds_real_programs_and_evidence_edges():
    entities,records=model_data()
    model=landscape_model(ROOT/'data',entities,records,{})
    assert len(model['companies'])==11
    assert model['counts']['programs']>10
    assert len(model['relationships'])==3
    assert all(edge['sources'] for edge in model['relationships'])
    by_id={c['entity_id']:c for c in model['companies']}
    assert by_id['company-planasa']['editing_status']=='not established in this research pass'
    assert 'plant-sciences-genetics' in by_id['company-plant-sciences-genetics']['entity_id']
    adjacent=landscape_model(ROOT/'data',entities,records,{'adjacent':'1'})
    assert adjacent['counts']['programs']==28 and len(adjacent['relationships'])==4
    focused=landscape_model(ROOT/'data',entities,records,{'company':'company-hudson-river-biotechnology','adjacent':'1'})
    assert len(focused['companies'])==1 and len(focused['relationships'])==2
    assert 'https://' in csv_export(adjacent)
    assert 'Unknown' in html_export(adjacent)


def test_program_filters_and_native_analyst_program_corrections():
    entities,records=model_data()
    key='program-gene-heat-strawberry'
    entities[key]['attributes']['gene_editing']['stage']='Analyst revised stage'
    model=landscape_model(ROOT/'data',entities,records,{'crop':'strawberry','stage':'Analyst revised'})
    assert {p['id'] for p in model['programs']}=={key}
    assert all(p['stage']=='Analyst revised stage' for p in model['programs'])


def test_rejected_sources_remove_edges_and_disputes_remain_visible():
    entities,records=model_data()
    records=deepcopy(records)
    next(r for r in records if r['id']=='ev-gene-simplot-alliance')['status']='rejected'
    next(r for r in records if r['id']=='ev-gene-hrb-plantik')['verification_state']='disputed'
    # Rejecting one announcement does not erase a separately sourced current
    # partner account. Remove both before asserting that the edge disappears.
    partial=landscape_model(ROOT/'data',entities,records,{})
    assert any(e['id']=='rel-gene-simplot-psi' for e in partial['relationships'])
    next(r for r in records if r['id']=='ev-gene-closeout-psg-research')['status']='rejected'
    model=landscape_model(ROOT/'data',entities,records,{})
    assert not any(e['id']=='rel-gene-simplot-psi' for e in model['relationships'])
    assert all('evidence gap' in p['verification'] for p in model['programs'] if p['id']=='program-gene-simplot-psi')
    assert any('disputed' in e['verification'] for e in model['relationships'] if e['id']=='rel-gene-hrb-plantik')
    disputed=landscape_model(ROOT/'data',entities,records,{'verification':'disputed'})
    assert {p['id'] for p in disputed['programs']}=={'program-gene-heat-strawberry'}


def test_composed_news_filters_berry_geo_date_source_and_adjacent():
    entities,records=model_data()
    # Compact program has real US/Colombia scope. No HQ geography inference.
    model=news_workspace.model(records={r['id']:r for r in records},entities=entities,relationships=[],facts=[],
        state=feed_first.empty_state(),params={'topic':'gene-editing','berry':'blackberry','countries':'geography-united-states',
        'company':'company-pairwise','source':'Pairwise','view':'unreviewed','window':'custom','start':'2026-01-01','end':'2026-10-20'},
        now=datetime(2026,10,21,tzinfo=UTC))
    assert model['matching_ids']==['ev-gene-pairwise-2026']
    assert model['filters']['topic']=='gene-editing'
    assert model['cards'][0]['topic_match']['excerpt']
    assert all(not c['trusted'] for c in model['cards'])


def test_analyst_route_html_api_exports_and_no_public_mode(monkeypatch):
    from app import main
    entities,records=model_data()
    monkeypatch.setattr(main,'all_entities',lambda:list(entities.values()))
    monkeypatch.setattr(main,'all_evidence',lambda:records)
    monkeypatch.setattr(main,'AUTHORING_MODE',True)
    client=TestClient(main.app)
    for endpoint in ('/landscapes/explorer?topic=gene-editing',
                     '/api/landscapes/explorer?topic=gene-editing&adjacent=1',
                     '/landscapes/explorer/export/csv?topic=gene-editing&adjacent=1',
                     '/landscapes/explorer/briefing?topic=gene-editing'):
        response=client.get(endpoint)
        assert response.status_code==200, response.text[:500]
        assert 'private' in response.headers.get('cache-control','')
    monkeypatch.setattr(main,'AUTHORING_MODE',False)
    for endpoint in ('/landscapes/explorer?topic=gene-editing','/api/landscapes/explorer?topic=gene-editing',
                     '/landscapes/explorer/export/csv?topic=gene-editing'):
        assert client.get(endpoint).status_code==404


def test_source_claims_have_original_provenance_and_no_false_seed_crispr():
    for row in SNAPSHOT['evidence']:
        assert row['source_url'] and row['source_name'] and row['captured_date']
        assert row['supporting_excerpt'] and row['attribution'] and row['source_fidelity']['sha256']
        assert row['status']=='in_review' and row['verification_state']=='single_source'
    for key in ('ev-gene-planasa-about','ev-gene-fall-creek-collection','ev-gene-heritable-strawberry','ev-gene-ohalo-launch'):
        row=next(r for r in SNAPSHOT['evidence'] if r['id']==key)
        assert 'gene-editing' not in classify(row)['topics']


def test_manual_primary_supplement_keeps_regulatory_and_breeding_boundaries():
    programs = {p['id']: p for p in SNAPSHOT['programs']}
    soybean = programs['program-gene-qi-soybean']
    assert soybean['milestone_date'] == '2024-05-29'
    assert 'ev-gene-qi-rsr-response' in soybean['evidence_ids']
    assert 'sales' in soybean['gaps'] and 'P16' in soybean['gaps']
    florida = programs['program-gene-ohalo-florida']
    assert 'ev-gene-ohalo-florida' in florida['evidence_ids']
    assert 'ev-gene-closeout-uf-ohalo-report' in florida['evidence_ids']
    assert 'growth-room' in florida['stage'] and 'nuclease unspecified' in florida['technology']
    berry = programs['program-gene-qi-small-berry']
    assert berry['milestone_date'] is None
    assert 'Not a named edited-blueberry product' in berry['gaps']


def test_closeout_keeps_source_audit_separate_from_trust_and_product_claims():
    rows={r['id']:r for r in SNAPSHOT['evidence']}
    assert len(rows)==46
    assert all(r['research_review']['publication_decision']=='not_made' for r in rows.values())
    assert all(r['status']=='in_review' for r in rows.values())
    assert 'not an FDA food-safety evaluation' in rows['ev-gene-closeout-fda-pairwise']['summary']
    programs={p['id']:p for p in SNAPSHOT['programs']}
    assert 'company program not established' in programs['program-gene-fall-creek-paper-affiliation']['trait']
    assert programs['program-gene-heritable-edit-design']['berry_ids']==[]
    assert 'Not independent benchmarking' in programs['program-gene-heritable-edit-design']['gaps']
    assert len(programs['program-gene-simplot-s4a']['line_identifiers'])==8
    for key in ('fda-simplot','fda-pairwise','mara-soybean','heritable-products','uf-ohalo-report'):
        assert 'gene-editing' in classify(rows['ev-gene-closeout-'+key])['topics']
    assert not classify(rows['ev-gene-closeout-heritable-products'])['berry_related']
    assert rows['ev-gene-closeout-fda-simplot']['geography_ids']==['geography-united-states']
    assert 'Not a cultivation' in rows['ev-gene-closeout-mara-soybean']['geography_provenance']


def test_closeout_reconciliation_preserves_analyst_edits_and_is_idempotent(tmp_path):
    from scripts.apply_gene_editing_closeout import reconcile
    old=json.loads((ROOT/'data/imports/gene-editing-2026-10-20/snapshot.json').read_text(encoding='utf-8'))
    data=tmp_path/'data';inbox=tmp_path/'inbox'
    for date,value in [('2026-10-20',old),('2026-10-28',SNAPSHOT)]:
        path=data/'imports'/('gene-editing-'+date)/'snapshot.json';path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(value),encoding='utf-8')
    old_programs={p['id']:p for p in old['programs']}
    for key in ('program-gene-simplot-s4a','program-gene-ohalo-florida'):
        p=deepcopy(old_programs[key])
        if key.endswith('ohalo-florida'):p['stage']='Analyst correction: preserve this'
        path=data/'entities/breeding_programs'/(key+'.json');path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(dict(id=key,name=p['name'],status='unverified',evidence_ids=p['evidence_ids'],attributes={'gene_editing':p})),encoding='utf-8')
    for key in ('company-plant-sciences-genetics','company-qi-biodesign','company-shandong-shunfeng-biotechnology'):
        path=data/'entities/companies'/(key+'.json');path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps({'id':key,'attributes':{}}),encoding='utf-8')
    path=data/'configuration/sources.json';path.parent.mkdir(parents=True);path.write_text('[]',encoding='utf-8')
    first=reconcile(data,inbox,apply=True)
    assert first['program_updates']==['program-gene-simplot-s4a']
    assert first['analyst_programs_preserved']==['program-gene-ohalo-florida']
    second=reconcile(data,inbox,apply=True)
    assert second['program_updates']==[] and second['identity_notes_added']==[]
    assert second['publication_decisions']==0 and second['facts_created']==0
    retained=json.loads((data/'entities/breeding_programs/program-gene-ohalo-florida.json').read_text())
    assert retained['attributes']['gene_editing']['stage']=='Analyst correction: preserve this'


def test_remote_closeout_reconciliation_requires_a_verified_backup(tmp_path,monkeypatch):
    from scripts.apply_gene_editing_closeout import reconcile
    monkeypatch.setenv('BIOS_REMOTE_INTERACTIVE','true')
    with pytest.raises(ValueError,match='verified-backup'):
        reconcile(tmp_path/'data',tmp_path/'inbox',apply=True)
