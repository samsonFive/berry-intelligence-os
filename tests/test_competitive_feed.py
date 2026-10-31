from app.services.competitive_feed import select


def story(key, entities=(), berry=('berry-strawberry',), destinations=(), **kwargs):
    return dict(id=key, entity_ids=list(entities), berry_ids=list(berry), destination_market_ids=list(destinations), **kwargs)


def test_company_any_separate_tags_and_shared_focus():
    records = [story('a', ['c1'], tags=['x']), story('b', ['c2'], tags=['x', 'y']), story('s', ['c1', 'c2'], tags=['x', 'y'])]
    assert select(records, {'companies': 'c1,c2', 'lane': 'company'})['total'] == 3
    assert select(records, {'companies': 'c1,c2', 'lane': 'company', 'focus': 'shared'})['all_ids'] == ['s']
    assert select(records, {'companies': 'c1,c2', 'tags': 'x,y', 'tag_mode': 'all'})['total'] == 2
    assert select(records, {'companies': 'c1,c2', 'tags': 'x,y', 'tag_mode': 'any'})['total'] == 3


def test_explicit_market_context_not_hq_or_parent_and_enabling_explained():
    records = [story('market', destinations=['uk']), story('hq', geography_ids=['uk']), story('variety', ['v']), story('parent', ['p'])]
    relations = [dict(id='r', subject_id='c', object_id='v', predicate='develops', status='active'),
                 dict(id='ownership', subject_id='c', object_id='p', predicate='owns', status='active')]
    result = select(records, {'companies': 'c', 'lane': 'company'}, relationships=relations)
    assert result['all_ids'] == ['variety']
    assert 'Connected v' in result['items'][0]['inclusion'][0]
    assert select(records, {'companies': 'c', 'berry': 'berry-strawberry', 'destination': 'uk'})['all_ids'] == ['market']


def test_full_archive_date_before_pagination_unknown_date_not_first_seen_and_dedup():
    records = [story(str(i), published_date='2020-01-01', source_url=f'https://example.org/{i}') for i in range(60)]
    records += [story('copy', published_date='2020-01-01', source_url='https://example.org/0?utm_source=foo'),
                story('undated', captured_date='2026-10-30')]
    result = select(records, {'after': '2019-01-01', 'before': '2021-01-01', 'page': '3'})
    assert result['total'] == 60 and len(result['items']) == 12
    assert 'undated' not in result['all_ids']


def test_canonical_program_ownership_is_relevance_without_company_inheritance():
    entities = {'v':{'entity_type':'variety'}, 'p':{'entity_type':'company'}}
    relations = [dict(id='variety-right',subject_id='c',object_id='v',predicate='owns',status='active',evidence_ids=['proof']),
                 dict(id='parent',subject_id='c',object_id='p',predicate='owns',status='active')]
    result = select([story('variety',['v']),story('parent',['p']),story('proof')],
                    {'companies':'c','lane':'company'},relationships=relations,entities=entities)
    assert set(result['all_ids']) == {'variety','proof'}


def test_existing_dedup_publisher_fallback_without_merging_distinct_publishers():
    records = [story('rss', title='Original article', source_name='Publisher One', published_date='2025-01-01',source_url='https://publisher.one/a'),
               story('redirect',title='Original article',source_name='Publisher One',published_date='2025-01-01',source_url='https://news.google.com/rss/a'),
               story('different',title='Original article',source_name='Different Publisher',published_date='2025-01-01',source_url='https://other.example/a')]
    assert select(records,{})['total'] == 2


def test_existing_reviewed_source_recall_is_labelled_and_does_not_change_identity():
    entities={'c':{'id':'c','name':'North Coast Berry Genetics','entity_type':'company','aliases':[]}}
    record=story('legacy',title='North Coast Berry Genetics announces strawberry trials',status='published',submitted_by='analyst')
    result=select([record],{'companies':'c','lane':'company'},entities=entities)
    assert result['total']==1 and 'Reviewed-source mention' in result['items'][0]['inclusion'][0]
    assert record['entity_ids']==[]


def test_shared_software_company_exclusion_preserves_mixed_agtech():
    noise=story('noise',['c'],berry=['berry-blackberry'],title='BlackBerry expands QNX software licensing')
    mixed=story('mixed',['c'],berry=['berry-blackberry'],title='BlackBerry software used by berry growers for crop robotics')
    assert select([noise,mixed],{'companies':'c'})['all_ids']==['mixed']


def test_multiple_selected_berries_and_empty_parent_cohort_are_explicit():
    records=[story('blue',['c'],berry=['berry-blueberry']),story('straw',['c']),story('rasp',['c'],berry=['berry-raspberry'])]
    params={'companies':'c','berry':'berry-blueberry,berry-strawberry'}
    assert set(select(records,params)['all_ids'])=={'blue','straw'}
    assert select(records,{**params,'empty_cohort':'1'})['total']==0
