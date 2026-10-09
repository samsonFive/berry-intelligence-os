"""Field gaps must reflect linked/cited data and protected photo overrides."""
from copy import deepcopy

from app.services.variety_profile_coverage import profile_field_coverage


def variety(name='FieldBlue', **attrs):
    return dict(id='variety-fieldblue', entity_type='variety', name=name,
                status='unverified', berry_ids=['berry-blueberry'], attributes=attrs)


def inventory(v, **kwargs):
    return profile_field_coverage(varieties=[v], entities=[v, *kwargs.pop('extra_entities', [])],
        relationships=kwargs.pop('relationships', []), published_evidence=kwargs.pop('published_evidence', []), **kwargs)


def test_free_text_and_uncited_traits_do_not_fill_supported_field_gaps():
    v=variety(breeder='Named breeder', patent_number='US PP99,999',
        traits=[{'trait':'trait-size','value':'large','evidence_ids':['missing']},
                {'trait':'trait-yield','value':0,'evidence_ids':['draft-source']}])
    before=deepcopy(v)
    view=inventory(v,published_evidence=[{'id':'draft-source','status':'draft'}])
    row=view['rows'][0]
    assert row['missing']==['photos','rights','traits','companies']
    assert row['breeder_text_only'] and row['patent_number_only']
    assert row['uncited_traits']==2 and row['cited_traits']==0
    assert v==before and row['status']=='Unverified'


def test_citation_and_explicit_roles_count_without_claiming_current_rights_or_independent_measurement():
    v=variety(patent_number='US PP99,999',traits=[{'trait':'trait-yield','value':0,
        'provenance':'owner_or_marketer_claim','evidence_ids':['published']}])
    company={'id':'company-breeder','entity_type':'company','name':'Source Company'}
    patent={'id':'patent-uspp99999','entity_type':'patent','name':'Granted patent','aliases':['USPP99999']}
    view=inventory(v,extra_entities=[company,patent],relationships=[
        {'subject_id':company['id'],'object_id':v['id'],'predicate':'develops'},
        {'subject_id':company['id'],'object_id':v['id'],'predicate':'owns'}],
        published_evidence=[{'id':'published','status':'published','source_type':'company_press_release'},
                            {'id':'rights','status':'published','source_type':'patent_record','entity_ids':[v['id']]}])
    row=view['rows'][0]
    assert row['cited_traits']==1 and row['rights_refs']==2
    assert {r['role'] for r in row['company_links']}=={'Breeder','Rights holder'}
    assert row['missing']==['photos']
    assert 'current_rights' not in row and 'trusted_traits' not in row


def test_explicit_rights_record_pointer_counts_without_inventing_a_number_match():
    v=variety(rights_id='patent-pbr-record')
    right={'id':'patent-pbr-record','entity_type':'patent','name':'Named PBR record'}
    row=inventory(v,extra_entities=[right])['rows'][0]
    assert row['rights_refs']==1 and 'rights' not in row['missing']
    v['attributes']['rights_id']='missing-right'
    row=inventory(v,extra_entities=[right])['rows'][0]
    assert row['rights_refs']==0 and 'rights' in row['missing']


def photo_source():
    return dict(id='source-fieldblue',title='Source FieldBlue profile',url='https://example.org/profile',
        checked_on='2026-10-09',source_type='plant_patent',company_ids=[],berry_ids=['berry-blueberry'],
        capture_status='names_enumerated',enumerated_scope='One source profile',limitations='Unreviewed source',
        names=[{'candidate_name':'FieldBlue','berry_id':'berry-blueberry','photos':[{
            'image_url':'https://example.org/photo.jpg','source_url':'https://example.org/profile',
            'credit':'Source publisher','caption':'FieldBlue fruit','named_variety':'FieldBlue',
            'berry_id':'berry-blueberry','kind':'fruit','checked_on':'2026-10-09','reuse':'unknown',
            'license_url':'','reuse_note':'Permission unknown'}]}])


def test_held_photo_and_unreviewed_patent_remain_distinct_from_approved_records():
    v=variety()
    source=photo_source()
    original=deepcopy(source)
    row=inventory(v,portfolio_sources=[source])['rows'][0]
    assert row['photos']==1 and row['held_photos']==1
    assert row['rights_refs']==0 and row['unreviewed_rights_refs']==1
    assert row['missing']==['traits','companies']
    assert source==original
    assert 'image_url' not in str(row)


def test_retained_trait_statements_count_but_missing_sources_and_proposals_do_not():
    v=variety()
    trait={'id':'trait-yield','entity_type':'trait','name':'Yield'}
    base={'id':'fact-yield','statement':'Trial yield was measured','entity_ids':[v['id'],trait['id']],
          'evidence_ids':['published']}
    facts=[base,{**base,'id':'fact-proposed','ai_proposed':True},
           {**base,'id':'fact-draft','status':'draft'},
           {**base,'id':'fact-missing','evidence_ids':['missing']}]
    original=deepcopy(facts)
    row=inventory(v,extra_entities=[trait],facts=facts,
                  published_evidence=[{'id':'published','status':'published'}])['rows'][0]
    assert row['cited_traits']==1 and 'traits' not in row['missing']
    assert facts==original


def test_inventory_reuses_unfiltered_reconciliation_without_running_it_again(monkeypatch):
    from app.services import variety_profile_coverage
    v=variety()
    reconciled=[{'id':'source-patent','url':'https://example.org/grant','source_type':'plant_patent',
                 'names':[{'catalog_id':v['id'],'identity_notes':[]}]}]
    original=deepcopy(reconciled)
    def forbidden(**kwargs):
        raise AssertionError('The route already reconciled the complete source set')
    monkeypatch.setattr(variety_profile_coverage,'reconcile_portfolios',forbidden)
    row=inventory(v,reconciled_sources=reconciled,
                  filters={'q':'unrelated portfolio search','profile_gap':'all'})['rows'][0]
    assert row['unreviewed_rights_refs']==1 and 'rights' not in row['missing']
    assert reconciled==original


def test_user_hidden_photo_is_missing_in_inventory_and_source_is_not_deleted():
    from app.services.variety_photos import source_photos
    v=variety()
    source=photo_source()
    key=source_photos(v,sources=[source],varieties=[v])[0]['id']
    profile={v['id']:{'variety_photo_overrides':{key:None}}}
    original=deepcopy(profile)
    row=inventory(v,portfolio_sources=[source],profiles=profile)['rows'][0]
    assert row['photos']==0 and 'photos' in row['missing']
    assert profile==original and source['names'][0]['photos']


def test_ambiguous_alias_or_wrong_crop_source_does_not_fill_rights_gap():
    v=variety()
    twin={**v,'id':'variety-other','name':'Other','aliases':['FieldBlue']}
    source=photo_source()
    view=profile_field_coverage(varieties=[v,twin],entities=[v,twin],relationships=[],
        published_evidence=[],portfolio_sources=[source])
    assert all(row['unreviewed_rights_refs']==0 and row['photos']==0 for row in view['rows'])
    source['names'][0]['berry_id']='berry-raspberry'
    source['names'][0]['photos']=[]
    row=inventory(v,portfolio_sources=[source])['rows'][0]
    assert row['unreviewed_rights_refs']==0 and 'rights' in row['missing']


def test_field_filters_have_scoped_denominators_and_stable_alphabetical_order():
    rows=[variety('Zulu'),{**variety('Alpha'),'id':'variety-alpha'},
          {**variety('Alpha Red'),'id':'variety-red','berry_ids':['berry-raspberry']}]
    view=profile_field_coverage(varieties=rows,entities=rows,relationships=[],published_evidence=[],
        filters={'profile_q':'alpha','profile_berry':'berry-blueberry','profile_gap':'traits'})
    assert view['catalog_total']==3 and view['scoped_total']==1
    assert view['rows'][0]['id']=='variety-alpha' and view['missing_counts']['traits']==1
    empty=profile_field_coverage(varieties=rows,entities=rows,relationships=[],published_evidence=[],
        filters={'profile_q':'missing'})
    assert empty['rows']==[] and empty['scoped_total']==0


def test_live_table_is_read_only_and_absent_outside_authoring(monkeypatch,tmp_path):
    from fastapi.testclient import TestClient
    from app import main
    from app.services import variety_portfolio_coverage
    v=variety()
    report={'mention_count':0,'already_canonical':[],'already_candidate':[],
            'candidates':[],'possible_aliases':[],'unresolved':[],'exclusions':[]}
    monkeypatch.setattr(main,'INBOX_DIR',tmp_path)
    monkeypatch.setattr(main,'variety_candidate_universe',lambda:([v],[],report))
    monkeypatch.setattr(main,'all_entities',lambda:[v])
    monkeypatch.setattr(main,'all_relationships',lambda:[])
    monkeypatch.setattr(main,'published_evidence',lambda:[])
    monkeypatch.setattr(main,'all_facts',lambda:[])
    monkeypatch.setattr(variety_portfolio_coverage,'load_portfolio_observations',lambda _:[photo_source()])
    monkeypatch.setattr(main,'AUTHORING_MODE',True)
    before={p.relative_to(tmp_path):p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}
    client=TestClient(main.app)
    response=client.get('/varieties/coverage?profile_q=FieldBlue&profile_gap=traits')
    assert response.status_code==200
    assert 'What each variety profile needs' in response.text and '1 permission unconfirmed' in response.text
    assert '1 unreviewed source' in response.text and 'No cited traits' in response.text
    # Counts and profile handoffs do not expose or load the source image asset.
    assert 'https://example.org/photo.jpg' not in response.text
    assert before=={p.relative_to(tmp_path):p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}
    monkeypatch.setattr(main,'AUTHORING_MODE',False)
    response=client.get('/varieties/coverage')
    assert response.status_code==200 and 'What each variety profile needs' not in response.text
