"""Synthetic controls for the inspected citation failure mechanisms."""
import hashlib
from datetime import date
from types import SimpleNamespace

from app.services.topic_retrieval import match_record,plan_query,record_passages
from app.services.report_builder.topic_report import topic_sections

ENTITIES={'ervin':{'id':'ervin','entity_type':'variety','name':'Ervin','aliases':['NC 740'],'berry_ids':['berry-blackberry']},
          'uk':{'id':'uk','entity_type':'geography','name':'United Kingdom','aliases':['UK','Great Britain']}}


def source(title,paragraphs,**extra):
    return {'id':'web-fixture','title':title,'source_url':'https://example.org/fixture','published_date':'2026-09-01',
            'article':{'paragraphs':[{'index':i,'text':p} for i,p in enumerate(paragraphs)]},**extra}


def test_namesake_and_other_cultivar_cannot_supply_named_variety_quotes():
    for record in [source('A berry grower remembered',['Ervin Lineberger was a blackberry grower.']),
                   source('Marion management',['A fictional Marion blackberry trial compared pruning.'],snippet='Ervin blackberry')]:
        match=match_record(record,plan_query('Ervin blackberry'),entities=ENTITIES)
        assert match is None or match['support_status']=='scope_unverified'
    quoted=source('Fictional cultivar introduction',['The cultivar ‘Ervin’ is a floricane‑fruiting blackberry introduced in fictional trials.'])
    assert match_record(quoted,plan_query('Ervin blackberry'),entities=ENTITIES)['support_status']=='body_supported'
    from app.services.topic_retrieval import normalize
    assert normalize("O’Neal")=="o'neal"


def test_verified_code_prefers_the_named_cultivar_to_program_economics():
    record=source('Fictional blackberry programme update',[
        'This fictional blackberry programme contributed to a growing regional market.',
        'The new cultivar Ervin debuted in the fictional evaluation plots.'])
    result=match_record(record,plan_query('NC 740 blackberry'),entities=ENTITIES)
    assert result['passage_locator']=='article:1' and result['support_status']=='body_supported'


def test_concrete_release_passage_precedes_a_more_keyword_dense_opinion():
    record=source('Four blueberry introductions',[
        'Four fictional blueberry cultivars were introduced at the event.',
        'The blueberry breeding programme has impressive blueberry breeding ambitions.'])
    assert match_record(record,plan_query('Blueberry breeding developments'))['passage_locator']=='article:0'


def test_cane_growth_does_not_establish_fruiting_type():
    record=source('Blackberry architecture',['The fictional blackberry has primocanes and floricanes with an erect growth habit.'])
    match=match_record(record,plan_query('Floricane blackberry developments'))
    assert match is None or match['support_status']=='scope_unverified'


def test_trial_geography_is_not_the_breeders_origin_or_a_future_market():
    query=plan_query('Raspberry primocane trials United Kingdom')
    for body in ['A UK breeder conducted raspberry primocane trials in Morocco.',
                 'The raspberry primocane crop had trials in Italy; assessments for the United Kingdom are planned.']:
        match=match_record(source('Raspberry trial', [body]),query,entities=ENTITIES)
        assert match is None or match['support_status']=='scope_unverified'
    positive=source('Raspberry trial',['Raspberry primocane trials were conducted in Scotland.'])
    # The query's own geographic constraint must be satisfied by trial prose.
    positive['snippet']='United Kingdom raspberry primocane trials'
    assert match_record(positive,query,entities=ENTITIES)['support_status']=='body_supported'


def test_flattened_news_attribution_ends_owned_quote_without_changing_raw_capture():
    raw='A fictional blueberry trial evaluated mechanical harvesting. Source: Fictional Institute Other unrelated news headline.'
    record=source('Blueberry trial',[raw])
    assert record_passages(record)[0][1]=='A fictional blueberry trial evaluated mechanical harvesting.'
    assert record['article']['paragraphs'][0]['text']==raw


def test_source_conflict_is_visible_as_a_hold_without_quoting_or_model_export():
    from app.services.research_desk import compose_research_answer,_public_digest
    url='https://italianberry.it/en/news/white-blackberry-sweet-ark-immaculate'
    row=source('Disputed cultivar account',['Fictional disputed cultivar claim.'],source_url=url)
    row.update(origin='web',trust_class='LIVE / UNREVIEWED',source_version='fixture-sha',passage='Fictional disputed cultivar claim.',passage_locator='article:0',relevance='direct')
    packet={'topic_sources':[row],'topic_research':{'plan':plan_query('Sweet-Ark Immaculate blackberry release').as_dict(),'source_scope':'combined','discovery':{'status':'complete'}}}
    sections=topic_sections(packet,as_of=date(2026,10,30))
    assert all('Fictional disputed cultivar claim.' not in s.prose for s in sections)
    assert any(s.section_id=='topic_verification_leads' for s in sections)
    live={'items':[{**row,'url':url,'date':'2026-09-01','source_name':'Publisher'}]}
    assert _public_digest({},live)==[]
    answer=compose_research_answer({},live=live,completer=lambda *a,**k:SimpleNamespace(parsed={'findings':[{'text':'Unsupported','source_ids':['web-fixture']}],'implications':[]}))
    assert not answer['findings'] and len(answer['verification_leads'])==1


def test_licensing_background_is_not_promoted_to_research_desk_findings():
    from app.services.research_desk import compose_research_answer,_public_digest
    row={'id':'background','title':'Cultivar identity','date':'2026-09-01','source_name':'Publisher',
         'url':'https://example.org/background','support_status':'body_supported','relevance':'background'}
    live={'items':[row]}
    assert _public_digest({},live)==[]
    answer=compose_research_answer({},live=live)
    assert not answer['findings'] and answer['historical_developments']==[row]
    british=source('Fictional blackberry agreement',['A fictional floricane blackberry was introduced.', 'An exclusive licence for this variety was announced.'])
    result=match_record(british,plan_query('Floricane blackberry licensing'))
    assert result['relevance']=='direct' and 'licence' in result['passage']


def test_saved_quote_endpoint_rejects_held_snapshots_before_workspace_write(monkeypatch):
    from fastapi.testclient import TestClient
    from app import main,living_workspace_routes
    row={'id':'held','passage':'Disputed quotation','source_url':'https://italianberry.it/en/news/white-blackberry-sweet-ark-immaculate'}
    monkeypatch.setattr(main,'_load_report_or_404',lambda _: {'scope':{'research_snapshot':{'web':[row]}}})
    monkeypatch.setattr(living_workspace_routes,'context',lambda *a:(main,SimpleNamespace(),{'id':'fixture'}))
    assert TestClient(main.app).post('/reports/test/topic-source/held/save').status_code==422


def test_replay_does_not_close_a_stale_or_missing_original_flag():
    from scripts.replay_topic_citation_fixes import replay
    row=source('Synthetic blackberry release',['A fictional floricane blackberry was introduced.'])
    row.update(source_version=hashlib.sha256(row['article']['paragraphs'][0]['text'].encode()).hexdigest(),
               passage=row['article']['paragraphs'][0]['text'],passage_locator='article:0',source_name='Fixture',relevance='direct')
    query='Floricane blackberry developments'
    run={'started_at':'2026-10-26T00:00:00Z','queries':[{'query':query,'split':'development','improved_app':[row],'discovery':{'status':'complete'}}]}
    review={'query':query,'section_id':'topic_findings','source_id':row['id'],'source_url':row['source_url'],
            'source_version':'changed','passage_sha256':hashlib.sha256(row['passage'].encode()).hexdigest(),'reason':'Fixture flag','disposition':'needs_review'}
    _,metadata=replay(run,{},[review])
    assert metadata['stale_review_bindings']==1 and metadata['resolutions'][0]['action']=='stale_review_binding'
    _,metadata=replay(run,{},[{**review,'query':'Unknown query'}])
    assert metadata['original_flag_count']==1 and metadata['unmapped_flags']==1
    assert replay(run,{},[review,review])[1]['duplicate_flag_bindings']==1
