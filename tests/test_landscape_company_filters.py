"""Shared personal marks scope real links; ownership context stays sourced."""
from copy import deepcopy
import csv
from io import BytesIO, StringIO
import json
from pypdf import PdfReader
import pytest

from test_landscape_explorer import world, client_world
from app import main
from app.services import landscape_explorer as lx, landscape_explorer_export as exports
from app.services import feed_first, landscape_workspace as workspace
from app.services.landscape_explorer_pdf import pdf_export


def preferences():
    return {'entity_favorites':{'company-a':True}, 'entity_tiers':{'company-a':'tier1','company-b':'tier2'},
            'company_lists':{'list-a':{'name':'Licensing watch','company_ids':['company-a']},
                             'list-b':{'name':'Other private group','company_ids':['company-b']}}}


def build(world, state, **params):
    return lx.build_bundle(**world,params={'countries':'',**params},state=state)


def test_marks_intersect_on_one_company_and_preserve_owned_program_context(world):
    state=preferences(); before=deepcopy((world,state))
    bundle=build(world,state,favorites='1',tier='tier1',list='list-a')
    assert {edge['id'] for edge in bundle['edges']}=={'r-peru','r-chile','r-program','r-develops'}
    assert 'r-license' not in {edge['id'] for edge in bundle['edges']}
    assert bundle['coverage']['genetic_location_links']==0
    assert bundle['company_scope']['labels']==['Favorites','Tier 1','Licensing watch']
    assert not build(world,state,favorites='1',tier='tier2')['edges']
    assert (world,state)==before
    # Untiered is a real choice, separate from no tier filter.
    assert build(world,state,tier='untiered')['edges'][0]['subject_id']=='breeding_program-a'


def test_role_filter_retains_exact_ownership_support_without_transferring_roles(world):
    state=preferences()
    world['evidence'].append({'id':'ev-control','title':'Original programme ownership report','status':'published','source_url':'https://example.test/control'})
    world['relationships'][2]['evidence_ids']=['ev-control']
    bundle=build(world,state,favorites='1',predicate='develops')
    assert [edge['id'] for edge in bundle['edges']]==['r-develops']
    assert bundle['edges'][0]['subject_id']=='breeding_program-a'
    assert [edge['id'] for edge in bundle['company_scope']['basis']]==['r-program']
    assert {source['id'] for source in bundle['sources']}=={'ev-a','ev-control'}
    for output in (exports.html_export(bundle),exports.svg_export(bundle), ' '.join(p.extract_text() for p in PdfReader(BytesIO(pdf_export(bundle))).pages)):
        assert 'Favorites' in output and 'recorded ownership link' in output
        assert 'Original programme ownership report' in output
        assert 'Other private group' not in output
    rows=list(csv.DictReader(StringIO(exports.csv_export(bundle).lstrip('\ufeff'))))
    assert {row['relationship_id'] for row in rows if row['row_kind']=='relationship'}=={'r-develops'}
    assert {row['relationship_id'] for row in rows if row['row_kind']=='company_scope_context'}=={'r-program'}
    assert all(row['favorites_filter']=='1' for row in rows)


def test_ownership_scope_obeys_source_and_relationship_review_policies(world):
    state=preferences()
    world['evidence'].append({'id':'ev-unreviewed','title':'Unreviewed ownership','status':'in_review'})
    world['relationships'][2].update(evidence_ids=['ev-unreviewed'],status='disputed')
    assert not build(world,state,favorites='1',predicate='develops')['edges']
    all_sources=build(world,state,favorites='1',predicate='develops',evidence='all')
    assert all_sources['company_scope']['basis'][0]['status']=='disputed'
    assert all_sources['company_scope']['basis'][0]['review']=='Includes unreviewed source'
    assert not build(world,state,favorites='1',predicate='develops',evidence='all',status='active')['edges']
    world['evidence'].pop()
    assert not build(world,state,favorites='1',predicate='develops',evidence='all')['edges']


def test_current_preferences_invalidate_cache_without_changing_data_or_old_bundle(world):
    state=preferences()
    initial=build(world,state,list='list-a')
    state['company_lists']['list-a'].update(name='Renamed watch',company_ids=['company-b'])
    updated=build(world,state,list='list-a')
    assert [edge['id'] for edge in updated['edges']]==['r-license']
    assert updated['company_scope']['labels']==['Renamed watch']
    assert initial['company_scope']['labels']==['Licensing watch']
    assert updated['version']==initial['version']  # preferences are not canonical evidence
    state['company_lists']['list-a']['archived']=True
    with pytest.raises(ValueError,match='archived'):
        build(world,state,list='list-a')


def test_all_and_comparison_do_not_mix_genetics_or_drop_company_filters(world):
    state=preferences()
    for params in ({'berry':'all'}, {'view':'compare','compare':'berry-strawberry'}):
        bundle=build(world,state,favorites='1',tier='tier1',list='list-a',**params)
        assert 'r-license' not in {edge['id'] for edge in bundle['edges']}
        assert 'r-other-berry' in {edge['id'] for edge in bundle['edges']}
        assert {edge['id'] for edge in bundle['edges']}==set().union(*(set(crop['edge_ids']) for crop in bundle['crop_scopes']))
        assert 'favorites=1' in bundle['url'] and 'list=list-a' in bundle['url']
        assert all('favorites=1' in crop['url'] for crop in bundle['crop_scopes'])


def test_nested_program_paths_terminate_with_cycles_and_retain_all_support(world):
    state=preferences()
    world['entities']['program-b']={'id':'program-b','name':'Second programme','entity_type':'breeding_program','berry_ids':['berry-blueberry']}
    world['relationships'] += [
        {'id':'r-nested','subject_id':'breeding_program-a','object_id':'program-b','predicate':'owns','status':'active','evidence_ids':['ev-a']},
        {'id':'r-cycle','subject_id':'program-b','object_id':'breeding_program-a','predicate':'owns','status':'active','evidence_ids':['ev-a']},
        {'id':'r-nested-develops','subject_id':'program-b','object_id':'variety-a','predicate':'develops','status':'active','evidence_ids':['ev-a']},
    ]
    result=build(world,state,favorites='1',predicate='develops')
    assert {edge['id'] for edge in result['edges']}=={'r-develops','r-nested-develops'}
    assert {edge['id'] for edge in result['company_scope']['basis']}=={'r-program','r-nested','r-cycle'}


def test_shared_ownership_context_keeps_both_crop_scopes(world):
    state=preferences()
    world['entities']['breeding_program-a']['berry_ids']=['berry-blueberry','berry-strawberry']
    world['relationships'][5].update(subject_id='breeding_program-a')
    result=build(world,state,view='compare',compare='berry-strawberry',favorites='1',predicate='develops')
    basis=next(edge for edge in result['company_scope']['basis'] if edge['id']=='r-program')
    assert set(basis['berry_ids'])=={'berry-blueberry','berry-strawberry'}
    assert {edge['id'] for edge in result['edges']}=={'r-develops','r-other-berry'}


def test_invalid_marks_and_list_ids_are_recoverable_without_writes(client_world):
    feed_first.save_state(main.INBOX_DIR,preferences())
    path=feed_first.state_path(main.INBOX_DIR); before=path.read_bytes()
    for params in ({'favorites':'true'},{'tier':'invented'},{'list':'missing'}):
        assert client_world.get('/landscapes/explorer',params=params).status_code==422
    assert path.read_bytes()==before


def test_saved_company_filters_reopen_current_membership_and_preserve_preferences(client_world):
    state=preferences(); feed_first.save_state(main.INBOX_DIR,state)
    state_path=feed_first.state_path(main.INBOX_DIR); before=state_path.read_bytes()
    created=client_world.post('/landscapes/explorer/views',data={'name':'Personal crop view','countries':'','favorites':'1','tier':'tier1','list':'list-a'},follow_redirects=False)
    assert created.status_code==303
    assert state_path.read_bytes()==before
    page=client_world.get(created.headers['location'])
    assert page.status_code==200 and 'Company tier' in page.text and 'Licensing watch' in page.text
    assert '&favorites=1&tier=tier1&list=list-a">Geography map' in page.text
    row=next(iter(workspace.load_views(main.INBOX_DIR)['views'].values()))
    assert {key:row['filters'][key] for key in ('favorites','tier','list')}=={'favorites':'1','tier':'tier1','list':'list-a'}
    view_path=main.INBOX_DIR/workspace.VIEW_FILE; view_before=view_path.read_bytes()
    state['entity_favorites']['company-a']=False
    feed_first.save_state(main.INBOX_DIR,state)
    reopened=client_world.get('/api'+created.headers['location']).json()
    assert reopened['edges']==[] and view_path.read_bytes()==view_before
    state['company_lists']['list-a']['archived']=True
    feed_first.save_state(main.INBOX_DIR,state)
    assert client_world.get(created.headers['location']).status_code==422
    assert view_path.read_bytes()==view_before


@pytest.mark.parametrize('bad', ['invalid json', {'entity_tiers':[]}, {'company_lists':{'bad':{'company_ids':'wrong'}}}])
def test_unreadable_preferences_do_not_silently_reset_filters_or_overwrite_state(client_world,bad):
    path=feed_first.state_path(main.INBOX_DIR)
    path.write_text(bad if isinstance(bad,str) else json.dumps(bad),encoding='utf-8')
    before=path.read_bytes()
    response=client_world.get('/landscapes/explorer?favorites=1')
    assert response.status_code==422 and 'Restore the saved preferences' in response.text
    assert path.read_bytes()==before
