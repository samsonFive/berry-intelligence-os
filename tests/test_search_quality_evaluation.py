from app.services.search_quality_evaluation import score_snapshot, score_query


def checked(grade,event=None):
    return dict(grade=grade,event_group=event,source_checked=True,reason='Inspected cited paragraph in fixture source',source_locator='article:0')


def test_missing_source_judgments_never_become_zero_grades_or_an_acceptance_claim():
    row=dict(query='blackberry developments',old_app=[],improved_app=[{'url':'https://source.test/a'}],google=[])
    result=score_snapshot({'queries':[row]}, {'queries':[]},{})
    assert result['judgment_pairs_missing']==1 and not result['acceptance_ready']
    assert result['aggregate_metrics']=={} and result['google_parity']=='UNVERIFIED'
    assert result['queries'][0]['metrics']['improved_app']['direct_precision_at_10'] is None


def test_duplicates_do_not_count_as_independent_results_or_distinct_developments():
    row=dict(query='blackberry developments',old_app=[],improved_app=[{'url':'https://source.test/a'},{'url':'https://source.test/a?utm_source=duplicate'},{'url':'https://other.test/b'}])
    labels={'https://source.test/a':checked(3,'one-event'),'https://other.test/b':checked(3,'one-event')}
    result=score_query(row,labels,{'complete_depth':True,'results':[{'url':'https://source.test/a'}]})
    score=result['metrics']['improved_app']
    assert score['result_count']==2 and score['direct_precision_at_10']==.2
    assert score['pooled_development_coverage_sample']==1
    assert not result['google_comparable']


def test_missing_pool_tail_prevents_ndcg_and_coverage_even_when_the_top_ten_are_checked():
    rows=[{'url':f'https://source.test/{i}'} for i in range(11)]
    labels={row['url']:checked(3,'event-'+str(i)) for i,row in enumerate(rows[:10])}
    result=score_query(dict(query='blackberry developments',improved_app=rows),labels)
    assert result['metrics']['improved_app']['direct_precision_at_10']==1
    assert result['metrics']['improved_app']['ndcg_at_10'] is None
    assert result['metrics']['improved_app']['pooled_development_coverage_sample'] is None


def test_literal_date_query_is_not_an_equivalent_google_date_filter():
    query='blackberry 2026-01-01 through 2026-10-26'
    rows=[{'url':f'https://source.test/{i}'} for i in range(10)]
    labels={r['url']:checked(3,'event-'+str(i)) for i,r in enumerate(rows)}
    row=dict(query=query,improved_app=rows)
    assert not score_query(row,labels,{'complete_depth':True,'results':rows})['google_comparable']
    assert score_query(row,labels,{'complete_depth':True,'results':rows,'date_filters':{'start':'2026-01-01','end':'2026-10-26'}})['google_comparable']


def test_false_source_checked_and_boolean_grades_are_not_valid_judgments():
    row=dict(query='blackberry developments',improved_app=[{'url':'https://source.test/a'}])
    for bad in [dict(checked(3),source_checked='true'),dict(checked(3),grade=True)]:
        assert not score_query(row,{'https://source.test/a':bad})['judged_pool_complete']


def test_changed_captured_source_requires_a_judgment_of_that_version():
    row=dict(query='blackberry developments',improved_app=[{'url':'https://source.test/a','source_version':'new-version'}])
    label=dict(checked(3),source_version='old-version')
    assert not score_query(row,{'https://source.test/a':label})['judged_pool_complete']
    label['source_version']='new-version'
    assert score_query(row,{'https://source.test/a':label})['judged_pool_complete']


def test_a_new_google_capture_cannot_establish_parity_against_a_different_day_app_run():
    rows=[{'url':f'https://source.test/{i}'} for i in range(10)]
    query='blackberry developments'
    run={'started_at':'2026-10-26T12:00:00Z','queries':[dict(query=query,improved_app=rows)]}
    base={'captured_date':'2026-10-28','queries':[dict(query=query,results=rows,complete_depth=True)]}
    labels={query:{r['url']:checked(3,'event-'+str(i)) for i,r in enumerate(rows)}}
    result=score_snapshot(run,base,labels)
    assert not result['same_day_capture_pairing'] and not result['acceptance_ready']
    base['captured_date']='2026-10-26'
    assert score_snapshot(run,base,labels)['acceptance_ready']


def test_unassigned_direct_events_cannot_claim_complete_development_coverage():
 row=dict(query='blackberry developments',improved_app=[{'url':'https://source.test/a'}])
 result=score_query(row,{'https://source.test/a':checked(3)})
 assert result['judged_pool_complete'] and not result['event_judgments_complete']
 assert result['metrics']['improved_app']['direct_precision_at_10']==.1
 assert result['metrics']['improved_app']['pooled_development_coverage_sample'] is None
