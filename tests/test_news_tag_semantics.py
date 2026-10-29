import json

import pytest

from app.services import news_tags as tags, news_tag_semantics as semantic


def source(key='article-one', text='Fruit became expensive after fewer ships arrived.'):
    return {'id':key,'title':'Berry industry update','summary':text}


def completer(calls, *, select='markets', during=None):
    def complete(prompt, **kwargs):
        request = json.loads(prompt.split('\n')[-1])
        assert kwargs['model'] == 'anthropic/claude-haiku-4-5'
        assert kwargs['max_output_tokens'] == 6000
        calls.append(request)
        if during:
            during()
        return {'articles':[{'id':row['id'],'assignments':[
            {'tag_id':select,'support':row['passages'][0]['id']}] if select else []}
            for row in request['articles']]}
    return complete


def test_semantic_assignments_cache_and_manual_race(tmp_path):
    row = source()
    tags.backfill(tmp_path,[row])
    assert 'markets' not in tags.effective(row,tags.catalog(tmp_path),*tags.snapshot(tmp_path))
    semantic.enqueue(tmp_path,[row])
    calls=[]
    def correction():
        tags.override(tmp_path,row['id'],'markets','remove','alice')
        tags.override(tmp_path,row['id'],'weather','add','alice')
    result=semantic.run(tmp_path,complete_json=completer(calls,during=correction))
    assert result['status']=='ready' and len(calls)==1
    assigned=tags.effective(row,tags.catalog(tmp_path),*tags.snapshot(tmp_path))
    assert 'markets' not in assigned and 'weather' in assigned
    tags.override(tmp_path,row['id'],'markets','automatic','alice')
    assert 'markets' in tags.effective(row,tags.catalog(tmp_path),*tags.snapshot(tmp_path))
    semantic.enqueue(tmp_path,[row])
    assert semantic.run(tmp_path,complete_json=completer(calls))['calls']==0
    assert len(calls)==1
    with tags.database(tmp_path,readonly=True) as db:
        decision=db.execute('SELECT * FROM automatic WHERE article=? AND tag=?',(row['id'],'markets')).fetchone()
        assert decision['classifier_version'].startswith(semantic.VERSION+':perplexity-agent:')
        assert decision['rationale'] in semantic.projection(row)['text']


@pytest.mark.parametrize('source,support',[
    ("Inka’s Berries licenses its cultivars.", "Inka's Berries licenses its cultivars"),
    ('The grower reported “higher prices” this week.', 'The grower reported "higher prices"'),
    ('Exports\u00a0\u00a0fell by ２０ percent.', 'exports fell by 20 percent'),
])
def test_typographic_passages_resolve_to_original_source_characters(source,support):
    passage=semantic.source_passage(source,support)
    assert passage and passage in source
    assert semantic.validate({'articles':[{'id':'one','assignments':[{'tag_id':'markets','support':support}]}]},
        [{'id':'one','text':source}], [{'id':'markets'}])['one']['markets']==passage


@pytest.mark.parametrize('support',[
    'Exports rose by 20 percent', 'Exports fell by 30 percent',
    'Exports fell ... 20 percent', 'Exports fell by twenty percent',
])
def test_typographic_normalization_never_repairs_changed_claims(support):
    assert semantic.source_passage('Exports fell by 20 percent.',support) is None


def test_passage_ids_preserve_source_typos_and_reject_unknown_references():
    source='ndia is facing a structural shortage of fresh raspberries.'
    records=[{'id':'one','text':source}]
    payload={'articles':[{'id':'one','assignments':[{'tag_id':'markets','support':'p0'}]}]}
    assert semantic.validate(payload,records,[{'id':'markets'}])['one']['markets']==source
    payload['articles'][0]['assignments'][0]['support']='p999'
    with pytest.raises(ValueError,match='Unsupported'):
        semantic.validate(payload,records,[{'id':'markets'}])
    spans=semantic.passages('Long stored article. '*1000)
    assert len(spans)>1 and all(len(s)<=600 and s in 'Long stored article. '*1000 for s in spans.values())


def test_schema_limits_ids_and_valid_duplicate_labels_are_idempotent():
    records=[{'id':'one','text':'Berry export prices fell by twenty percent.'}]
    catalog=[{'id':'markets'}]
    schema=semantic.response_schema(catalog,records)
    fields=schema['properties']['articles']['items']['properties']
    assert fields['id']['enum']==['one']
    assert fields['assignments']['items']['properties']['tag_id']['enum']==['markets']
    assert fields['assignments']['items']['properties']['support']['enum']==['p0']
    item={'tag_id':'markets','support':'p0'}
    payload={'articles':[{'id':'one','assignments':[item,item]}]}
    assert semantic.validate(payload,records,catalog)=={'one':{'markets':records[0]['text']}}
    payload['articles'][0]['assignments'][1]={'tag_id':'markets','support':'fabricated passage'}
    with pytest.raises(ValueError,match='Unsupported'):
        semantic.validate(payload,records,catalog)


def test_enqueue_cached_content_clears_obsolete_pending_fingerprints(tmp_path):
    row=source()
    semantic.enqueue(tmp_path,[row]);semantic.run(tmp_path,complete_json=completer([]))
    with tags.database(tmp_path) as db:
        db.execute('INSERT OR REPLACE INTO tag_pending VALUES(?,?)',(row['id'],'obsolete'))
    semantic.enqueue(tmp_path,[row])
    assert semantic.run(tmp_path,complete_json=completer([]))['status']=='ready'
    with tags.database(tmp_path,readonly=True) as db:
        assert db.execute('SELECT count(*) FROM tag_pending').fetchone()[0]==0


def test_name_only_tags_have_a_definition_and_keep_their_meaning_on_rename(tmp_path):
    tag=tags.create(tmp_path,'Labor')
    request=json.loads(semantic.prompt([{'id':'one','text':'Seasonal workers negotiate wages.'}],tags.catalog(tmp_path)).split('\n')[-1])
    definition=next(t['definition'] for t in request['definitions'] if t['id']==tag['id'])
    assert definition=='Reporting about Labor.'
    row=semantic.projection(source())
    before=semantic.fingerprint(row,tags.catalog(tmp_path))
    tags.update(tmp_path,tag['id'],'Workforce','')
    assert semantic.fingerprint(row,tags.catalog(tmp_path))==before


def test_long_stored_body_is_chunked_and_resumed_without_repeating_calls(tmp_path):
    row=source()
    row['article']={'full_text':'The berry nursery reported steady activity. '*210+'Seasonal workers negotiated higher wages.'}
    semantic.enqueue(tmp_path,[row])
    calls=[]
    first=semantic.run(tmp_path,complete_json=completer(calls),max_calls=1,batch_size=1)
    assert first['status']=='partial' and first['calls']==1
    assert tags.snapshot(tmp_path)[0]=={}  # No incomplete article decision becomes final.
    second=semantic.run(tmp_path,complete_json=completer(calls),batch_size=1)
    assert second['status']=='ready'
    assert len(calls)==2
    assert all(sum(len(p['text']) for p in row['passages'])<=semantic.MAX_TEXT for call in calls for row in call['articles'])
    assert len({r['id'] for call in calls for r in call['articles']})==2


def test_running_progress_includes_cached_sources_from_prior_passes(tmp_path):
    semantic.enqueue(tmp_path,[source('first')])
    semantic.run(tmp_path,complete_json=completer([]))
    semantic.enqueue(tmp_path,[source('second')])
    progress=[]
    semantic.run(tmp_path,complete_json=completer([],during=lambda:progress.append(tags.job_state(tmp_path))))
    assert progress[0]['status']=='running'
    assert progress[0]['processed']==1 and progress[0]['total']==2


@pytest.mark.parametrize('failure',['missing','fabricated','duplicate'])
def test_malformed_response_preserves_previous_decisions_and_retries(tmp_path,failure):
    row=source(text='Berry export prices fell this month.')
    tags.backfill(tmp_path,[row]); before=tags.snapshot(tmp_path)
    semantic.enqueue(tmp_path,[row])
    def bad(prompt,**kwargs):
        item=json.loads(prompt.split('\n')[-1])['articles'][0]
        if failure=='missing':
            return {'articles':[]}
        assignments=[{'tag_id':'markets','support':'A passage absent from the article'}]
        if failure=='duplicate':
            return {'articles':[{'id':item['id'],'assignments':[]},{'id':item['id'],'assignments':[]}]}
        return {'articles':[{'id':item['id'],'assignments':assignments}]}
    with pytest.raises(ValueError):
        semantic.run(tmp_path,complete_json=bad)
    assert tags.snapshot(tmp_path)==before
    assert tags.job_state(tmp_path)['status']=='failed'
    assert semantic.run(tmp_path,complete_json=completer([]))['status']=='ready'


def test_rename_keeps_cache_definition_update_rechecks_and_negatives_are_explicit(tmp_path):
    row=source(); calls=[]
    semantic.enqueue(tmp_path,[row]); semantic.run(tmp_path,complete_json=completer(calls))
    assert not tags.update(tmp_path,'markets','Market conditions',tags.SEEDS['markets'][1])
    semantic.enqueue(tmp_path,[row]); assert semantic.run(tmp_path,complete_json=completer(calls))['calls']==0
    assert tags.update(tmp_path,'markets','Market conditions','Only regional crop insurance claims.')
    semantic.enqueue(tmp_path,[row]); semantic.run(tmp_path,complete_json=completer(calls,select=None))
    assert len(calls)==2 and not tags.snapshot(tmp_path)[0][(row['id'],'markets')]


def test_source_update_during_provider_call_cannot_commit_stale_result(tmp_path):
    old=source(); new=source(text='Regional crop insurance changed this year.')
    semantic.enqueue(tmp_path,[old])
    once=[False]
    def change():
        if not once[0]:
            once[0]=True; semantic.enqueue(tmp_path,[new])
    calls=[]
    semantic.run(tmp_path,complete_json=completer(calls,during=change))
    assert len(calls)==2
    with tags.database(tmp_path,readonly=True) as db:
        row=db.execute('SELECT rationale FROM automatic WHERE article=? AND tag=?',(old['id'],'markets')).fetchone()
        assert row[0] in semantic.projection(new)['text']


def test_incremental_queues_without_running_the_provider_on_the_source_write(tmp_path,monkeypatch):
    tags.create(tmp_path,'Labor')
    monkeypatch.setenv('BIOS_NEWS_TAG_CLASSIFIER','semantic')
    scheduled=[]
    monkeypatch.setattr(semantic,'start_worker',lambda inbox:scheduled.append(inbox))
    tags.incremental(tmp_path,[source()])
    assert scheduled==[tmp_path]
    with tags.database(tmp_path,readonly=True) as db:
        assert db.execute('SELECT count(*) FROM tag_pending').fetchone()[0]==1


def test_missing_provider_is_visible_and_does_not_erase_rules(tmp_path,monkeypatch):
    row=source(text='Berry export prices fell this month.')
    tags.backfill(tmp_path,[row]); before=tags.snapshot(tmp_path)
    semantic.enqueue(tmp_path,[row])
    monkeypatch.setattr('app.services.ai_gateway.untrusted_complete.maybe_untrusted_completer',lambda:None)
    with pytest.raises(ValueError,match='unavailable'):
        semantic.run(tmp_path)
    assert tags.snapshot(tmp_path)==before
    assert 'retained' in tags.job_state(tmp_path)['error']
