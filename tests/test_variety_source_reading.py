from copy import deepcopy

from app.services.variety_source_reading import profile_source_reading


def variety(name='Ervin', key='variety-ervin', aliases=()):
    return dict(id=key, entity_type='variety', name=name, aliases=list(aliases), berry_ids=['berry-blackberry'])


def source(key='ev-pending', title="Meet 'Ervin' Blackberry", **extra):
    row = dict(id=key, title=title, record_type='evidence', evidence_role='publication_artifact', status='draft',
        review_state='in_review', berry_ids=['berry-blackberry'], entity_ids=[], source_url='https://example.org/'+key,
        source_name='University', published_date='2026-02-08', source_type='company_website',
        article={'paragraphs':[{'index':0, 'text':('Ervin is described by its breeder as a thornless floricane blackberry. ' * 10)}]})
    return {**row, **extra}


def present(records, *, varieties=None, load=None, limit=12):
    target = variety()
    return profile_source_reading(target, varieties=varieties or [target], records=records,
                                  load_record=load or (lambda key: next(r for r in records if r['id']==key)), limit=limit)


def test_known_name_exposes_captured_pending_source_without_approving_link_or_traits():
    row = source(); original = deepcopy(row)
    result = present([row])
    shown = result['rows'][0]
    assert shown['pending'] and not shown['linked'] and shown['readable']
    assert 'thornless floricane' in shown['excerpt'] and shown['published_date']=='2026-02-08'
    assert shown['reader_href']=='/intelligence/ev-pending' and shown['review_href']=='/review/ev-pending'
    assert row == original and 'traits' not in shown and 'facts' not in shown


def test_summaries_and_access_screens_remain_explicit_capture_gaps():
    rows=[source(article={},summary='Ervin has flavor.'),
          source(key='ev-wall',article={'full_text':'Accept all cookies. Manage consent. Cookie preferences. ' * 20})]
    result=present(rows)
    assert result['missing']==2 and result['readable']==0
    assert all(not r['excerpt'] and not r['passages'] for r in result['rows'])


def test_overlap_ambiguous_alias_and_wrong_crop_do_not_attach_other_varieties():
    target=variety('Eureka','variety-eureka')
    other=variety('Eureka Sunrise','variety-eureka-sunrise')
    record=source(title='Introducing Eureka Sunrise blackberry')
    assert not profile_source_reading(target,varieties=[target,other],records=[record],load_record=lambda _:record)['rows']
    other=variety('Another','variety-another',aliases=['Ervin'])
    assert not present([source()],varieties=[variety(),other])['rows']
    assert not present([source(berry_ids=['berry-strawberry'])])['rows']
    assert not present([source(title='Marvin blackberry breeding')])['rows']


def test_recorded_link_is_distinct_from_name_mention_and_preserves_original_date():
    row=source(title='Breeder technical sheet',entity_ids=['variety-ervin'],status='published')
    shown=present([row])['rows'][0]
    assert shown['linked'] and not shown['pending'] and shown['published_date']=='2026-02-08'


def test_rejected_atomic_and_unsafe_records_are_never_hydrated():
    calls=[]
    records=[source(status='rejected'),source(evidence_role='atomic_evidence'),source(source_url='javascript:bad'),source(id='../bad')]
    assert not present(records,load=lambda key:calls.append(key))['rows']
    assert calls==[]


def test_loader_cannot_substitute_other_source_body_or_rejected_record():
    meta=source(article={})
    for full in [source(source_url='https://elsewhere.org/story'),source(id='ev-other')]:
        assert not present([meta],load=lambda _:full)['rows'][0]['readable']
    assert not present([meta],load=lambda _:source(status='rejected'))['rows']


def test_hydration_and_excerpt_budget_is_bounded_and_primary_sources_are_visible():
    records=[source(key=f'ev-{i}',published_date=f'2026-02-{i+1:02d}',source_type='trade_press') for i in range(20)]
    records.append(source(key='ev-primary',published_date='2025-01-01'))
    byid={r['id']:r for r in records};calls=[]
    def load(key):calls.append(key);return byid[key]
    result=present(records,load=load,limit=3)
    assert result['truncated'] and result['matched_sources']==21 and len(calls)==3
    assert result['rows'][0]['id']=='ev-primary'
    assert all(len(row['excerpt'])<=700 and len(row['passages'])<=6 for row in result['rows'])


def test_template_explicitly_excludes_private_panel_from_static_and_read_only():
    from jinja2 import Environment,FileSystemLoader
    env=Environment(loader=FileSystemLoader('app/templates'),autoescape=True)
    env.filters['us_date']=str
    template=env.get_template('_variety_source_reading.html')
    panel=present([source(title="Ervin blackberry <script>secret</script>")])
    for authoring,static in [(False,False),(False,True),(True,True)]:
        assert 'thornless' not in template.render(authoring_mode=authoring,static_build=static,variety_source_reading=panel)
    html=template.render(authoring_mode=True,static_build=False,variety_source_reading=panel)
    assert 'thornless' in html and 'Publication review pending' in html
    assert '<script>secret</script>' not in html and '&lt;script&gt;' in html


def test_reader_capture_requires_exact_source_and_does_not_replace_saved_body(tmp_path):
    from app.services.variety_source_reading import stored_source_reading
    from app.services.feed_first_reader import save_capture
    record=source(status='published',article={})
    capture=dict(item_id=record['id'],requested_url=record['source_url'],url=record['source_url'],ok=True,
        availability='full',passages=['Ervin source text for a captured blackberry introduction. ' * 10])
    save_capture(tmp_path,record['id'],capture)
    loaded=stored_source_reading(record['id'],load_record=lambda _:record,inbox_dir=tmp_path)
    assert loaded['_private_capture_unreviewed'] and loaded['article']['paragraphs']
    capture['requested_url']='https://elsewhere.org/wrong';save_capture(tmp_path,record['id'],capture)
    assert not stored_source_reading(record['id'],load_record=lambda _:record,inbox_dir=tmp_path).get('article')
    edited=source(status='published')
    assert stored_source_reading(edited['id'],load_record=lambda _:edited,inbox_dir=tmp_path)==edited
