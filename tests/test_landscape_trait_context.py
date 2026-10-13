"""Existing cited traits stay scoped, attributed and read-only in Landscape."""
from copy import deepcopy
from io import BytesIO
from pypdf import PdfReader

from test_landscape_explorer import world, build
from app.services import landscape_explorer as lx
from app.services import landscape_explorer_export as exports
from app.services.landscape_explorer_pdf import pdf_export


def trait_world(world):
    world['entities']['trait-size']={'id':'trait-size','name':'Berry weight','entity_type':'trait'}
    world['entities']['variety-a']['attributes']={'traits':[
        {'trait':'trait-size','value':'6 g per fruit','provenance':'owner_or_marketer_claim','asserted_by':'Alpha','conditions':'Owner website; no method stated','evidence_ids':['ev-a']},
        {'trait':'trait-size','value':0,'units':'g/fruit','provenance':'named_trial_measurement','asserted_by':'Trial team','conditions':'Florida trial, 2025','evidence_ids':['ev-a']},
        {'trait':'trait-size','value':'UNCITED MUST STAY HIDDEN','provenance':'unresolved','evidence_ids':[]},
    ]}
    return world


def test_traits_reuse_records_preserve_conditions_and_do_not_infer_footprints(world):
    trait_world(world)
    before=deepcopy(world)
    bundle=build(world,countries='')
    rows=bundle['nodes']['variety-a']['traits']
    assert len(rows)==2 and rows[0]['source_kind']=='Owner / marketer claim'
    assert rows[0]['is_claim'] and rows[0]['conditions']=='Owner website; no method stated'
    assert rows[1]['source_kind']=='Reported trial measurement' and rows[1]['display_value']=='0'
    assert rows[1]['units']=='g/fruit'
    assert rows[1]['conditions']=='Florida trial, 2025'
    assert bundle['nodes']['variety-a']['unavailable_trait_count']==1
    assert bundle['coverage']['genetic_location_links']==0 and world==before
    assert 'traits' not in bundle['nodes']['company-a']
    assert lx.browser_bundle(bundle)['nodes']['variety-a']['traits']==rows


def test_trait_sources_must_all_be_in_exact_policy_and_selection(world):
    trait_world(world)
    world['entities']['variety-a']['attributes']['traits'][0]['evidence_ids']=['ev-a','ev-pending']
    world['evidence'].append({'id':'ev-pending','title':'Pending source','status':'in_review','berry_ids':['berry-blueberry']})
    world['relationships'].append({'id':'r-pending-trait','subject_id':'company-a','object_id':'variety-a','predicate':'markets','status':'active','evidence_ids':['ev-pending']})
    reviewed=build(world,countries='')
    assert [row['display_value'] for row in reviewed['nodes']['variety-a']['traits']]==['0']
    all_sources=build(world,countries='',evidence='all')
    assert len(all_sources['nodes']['variety-a']['traits'])==2
    assert {'ev-a','ev-pending'}==set(all_sources['nodes']['variety-a']['traits'][0]['evidence_ids'])
    # This role selection cannot reuse sources from otherwise hidden roles.
    scoped=build(world,countries='',evidence='all',predicate='markets')
    assert scoped['nodes']['variety-a']['traits']==[]
    removed=deepcopy(world)
    removed['evidence']=[row for row in removed['evidence'] if row['id']!='ev-pending']
    assert len(build(removed,countries='',evidence='all')['nodes']['variety-a']['traits'])==1


def test_trait_identity_and_crop_do_not_mix_in_comparison(world):
    trait_world(world)
    world['entities']['variety-s']['name']='Azure'
    world['entities']['variety-s']['attributes']={'traits':[{'trait':'trait-size','value':'Strawberry trial value','provenance':'named_trial_measurement','evidence_ids':['ev-a'],'conditions':'Strawberry trial only'}]}
    result=build(world,countries='',view='compare',compare='berry-strawberry')
    assert len(result['nodes']['variety-a']['traits'])==2
    assert result['nodes']['variety-s']['traits'][0]['display_value']=='Strawberry trial value'
    assert result['nodes']['variety-s']['traits'][0]['conditions']=='Strawberry trial only'


def test_trait_context_is_escaped_complete_in_visual_exports(world):
    trait_world(world)
    world['entities']['variety-a']['attributes']['traits'][0]['value']='<script>literal source words</script>'
    bundle=build(world,countries='')
    html=exports.html_export(bundle)
    svg=exports.svg_export(bundle)
    text='\n'.join(p.extract_text() for p in PdfReader(BytesIO(pdf_export(bundle))).pages)
    for output in (html,svg,text):
        assert 'Cited variety traits and sensory context' in output
        assert 'Owner / marketer claim' in output and 'Reported trial measurement' in output
        assert 'Florida trial, 2025' in output and 'no method stated' in output
        assert 'Units: g/fruit' in output
        assert 'not a common ranking' in output
        assert 'UNCITED MUST STAY HIDDEN' not in output
    assert '<script>literal' not in html and '&lt;script&gt;' in html
    assert '<script>literal' not in svg and '&lt;script&gt;' in svg


def test_trait_edits_invalidate_cache_without_aliasing_input(world):
    trait_world(world)
    value={'weight_g':0,'notes':['literal','scope']}
    world['entities']['variety-a']['attributes']['traits'][0]['value']=value
    first=build(world,countries='')
    assert first['nodes']['variety-a']['traits'][0]['display_value']=='weight g: 0; notes: literal; scope'
    first['nodes']['variety-a']['traits'][0]['value']['weight_g']=999
    assert value['weight_g']==0
    value['weight_g']=1
    second=build(world,countries='')
    assert second['version']!=first['version']
    assert second['nodes']['variety-a']['traits'][0]['display_value'].startswith('weight g: 1')


def test_profile_qualification_requires_complete_selected_source_refs(world):
    trait_world(world)
    variety=world['entities']['variety-a']
    variety['attributes']['note']='Storage increase is unexplained in the source.'
    variety['evidence_ids']=['ev-a','ev-outside-selection']
    assert build(world,countries='')['nodes']['variety-a']['trait_note']==''
    variety['evidence_ids']=['ev-a']
    bundle=build(world,countries='')
    assert bundle['nodes']['variety-a']['trait_note']==variety['attributes']['note']
    assert bundle['nodes']['variety-a']['trait_note_evidence_ids']==['ev-a']
    assert 'Storage increase is unexplained' in exports.html_export(bundle)
    assert 'Storage increase is unexplained' in exports.svg_export(bundle)
    text=' '.join(p.extract_text() for p in PdfReader(BytesIO(pdf_export(bundle))).pages)
    assert 'Storage increase is unexplained' in text
