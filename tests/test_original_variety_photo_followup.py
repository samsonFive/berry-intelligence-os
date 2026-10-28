"""Keep original-photo identities, comparison positions and permissions separate."""
from copy import deepcopy
import json
from pathlib import Path

from app import main
from app.services.variety_photos import gallery, source_photos
from app.services.variety_portfolio_coverage import load_portfolio_observations, observation_company_ids

DATA=Path(__file__).resolve().parents[1]/'data'
PREFIX='portfolio-original-photo-followup-'

def cohort():
    return [s for s in load_portfolio_observations(DATA) if s['id'].startswith(PREFIX)]

def varieties():
    return [json.loads(p.read_text(encoding='utf-8')) for p in (DATA/'entities/varieties').glob('*.json')]

def test_shared_registry_image_keeps_two_named_positions_without_spreading_to_other_entries():
    sources=cohort(); vs=varieties(); original=deepcopy(vs)
    source=next(s for s in sources if s['id']==PREFIX+'drisbluetwentyone')
    names={n['candidate_name']:n for n in source['names']}
    centre=names['DrisBlueTwentyOne']['photos'][0]
    right=names['DrisBlueSeventeen']['photos'][0]
    assert centre['image_url']==right['image_url']
    assert 'centre column' in centre['caption'] and 'right column' in right['caption']
    assert centre['named_variety']=='DrisBlueTwentyOne' and right['named_variety']=='DrisBlueSeventeen'
    assert all(not names[n]['photos'] and observation_company_ids(source,names[n])==[]
               for n in ['DrisBlueOne','136D 2','181C 1'])
    assert observation_company_ids(source,names['DrisBlueSeventeen'])==[]
    assert names['DrisBlueOne']['trade_name']=='Rockinoee'
    assert names['DrisBlueSeventeen']['trade_name']=='Carlotta'
    leaf_source=next(s for s in sources if s['id']==PREFIX+'drisblueseventeen')
    assert next(n for n in leaf_source['names']if n['candidate_name']=='DrisBlueFifteen')['breeder_code']=='136d5'
    rosita=next(s for s in sources if s['id']==PREFIX+'drisbluetwentythree')
    assert {n['candidate_name']:n.get('trade_name') for n in rosita['names'] if n['candidate_name'] in {'DrisBlueSeven','DrisBlueTwentyTwo'}}=={
        'DrisBlueSeven':'Stella Blue','DrisBlueTwentyTwo':'Regina'}
    assert len(sources)==8 and sum(len(s['names'])for s in sources)==20
    photos=[p for s in sources for n in s['names'] for p in n['photos']]
    assert len(photos)==9 and len({p['image_url']for p in photos})==8
    reached={v['name']for v in vs if source_photos(v,sources=sources,varieties=vs)}
    assert reached=={'DrisBlueSeventeen','DrisBlueTwentyOne','DrisBlueTwentyThree','Keepsake','Medallion','SEKOYA Nova','Ponca','Ouachita'}
    assert vs==original

def test_government_and_university_hosting_do_not_grant_image_reuse_or_create_profile_facts():
    sources=cohort(); vs=varieties()
    for source in sources:
        assert source['review_state']=='unreviewed' and not source['capture_reference']['reuse_permission_verified']
        assert not source['capture_reference']['current_legal_status_verified']
        for name in source['names']:
            assert not any(name.get(k) for k in ['traits','growing_regions','grant_number','application_number','roles'])
        for v in vs:
            sourced=source_photos(v,sources=[source],varieties=vs)
            assert gallery(v,sourced=sourced,authoring=False)==[]
            private=gallery(v,sourced=sourced,authoring=True)
            assert all(p['reuse']=='unknown' and not p['license_url'] and not p['display_image'] for p in private)
            html=main.templates.get_template('_variety_photo_gallery.html').render(
                photo_gallery=private,authoring_mode=True,static_build=False)
            assert '<img ' not in html
            if private:
                assert 'data-photo-session' in html and 'Photo source' in html
    cfia=next(s for s in sources if s['id']==PREFIX+'drisblueseventeen')
    assert cfia['names'][0]['photos'][0]['kind']=='plant'
    assert 'flowers' in cfia['names'][0]['photos'][0]['caption']

def test_literal_labels_crop_and_displayed_story_dates_win_over_filenames():
    sources=cohort()
    strawberry={'id':'fixture-keepsake-strawberry','name':'Keepsake','aliases':[],
                'entity_type':'variety','berry_ids':['berry-strawberry']}
    assert source_photos(strawberry,sources=sources,varieties=[strawberry])==[]
    medallion=next(s for s in sources if s['id']==PREFIX+'mbg-medallion')
    assert medallion['capture_reference']['image_title']=='Medallio43n'
    assert medallion['names'][0]['candidate_name']=='Medallion'
    assert 'Medallio43n.jpg' in medallion['names'][0]['photos'][0]['image_url']
    assert not medallion['published_date']  # Upload directory does not date the card.
    ponca=next(s for s in sources if s['id']==PREFIX+'ponca')
    assert '12-09-2019' in ponca['url'] and ponca['published_date']=='2019-12-20'
    assert 'John R. Clark' in ponca['names'][0]['photos'][0]['credit']
    nova=next(s for s in sources if s['id']==PREFIX+'nova')
    assert nova['capture_reference']['image_alt']==''
    assert 'no separate variety caption' in nova['names'][0]['photos'][0]['caption']
    assert 'Picture2.jpg' in nova['names'][0]['photos'][0]['image_url']
