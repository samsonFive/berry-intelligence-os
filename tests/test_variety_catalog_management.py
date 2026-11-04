from copy import deepcopy
import json
from pathlib import Path
import pytest

from app.services.variety_catalog_management import canonical_record,promotion_plan,set_removed
from app.services.entity_identity import living_entities


@pytest.mark.parametrize('name,berry', [('Roberto','berry-blueberry'),('Clery','berry-strawberry'),('Dickens','berry-strawberry')])
def test_admitted_real_identity_is_a_catalog_match_instead_of_a_new_candidate(name, berry):
    from app.services.variety_universe.identity import resolve_identity
    varieties = [json.loads(path.read_text(encoding='utf8')) for path in Path('data/entities/varieties').glob('*.json')]
    target = next(row for row in varieties if row['name'].casefold() == name.casefold() and berry in row['berry_ids'])
    assert target['status'] == 'unverified' and target['attributes']['identity_review']['source_url']
    resolution = resolve_identity({'candidate_name':name, 'berry_id':berry}, varieties)
    assert any(row['variety_id'] == target['id'] and row['reason'] == 'exact_identity_string' for row in resolution['matches'])


def candidate(**kw):
    return dict(id='candidate-one',candidate_name='Clearberry',berry_id='berry-blueberry',identity_state='distinct',status='proposed',source_tier='tier_1_breeder_catalog',source_url='https://breeder.org/clearberry',**kw)


def test_catalog_admission_contains_identity_provenance_without_claim_promotion():
    c=candidate();record=canonical_record(c,varieties=[],actor='Delegated analyst audit',authorization='User authorized clear source-backed identity admission')
    assert record['status']=='unverified' and record['aliases']==[]
    assert record['evidence_ids']==record['fact_ids']==record['relationship_ids']==[]
    assert not record['attributes'].get('traits')
    assert record['attributes']['identity_review']['source_url']==c['source_url']
    assert canonical_record(c,varieties=[],actor='same',authorization='same')['id']==record['id']


def test_ambiguous_shared_labels_weak_sources_and_coded_names_stay_in_review():
    c=candidate()
    other={**c,'id':'candidate-other','candidate_name':'Othername','trade_name':'Clearberry'}
    assert not promotion_plan(c,varieties=[],candidates=[c,other])['ready']
    for changes in [dict(source_tier='weak_noncanonical_lead'),dict(identity_state='possible_alias'),dict(candidate_name='FC 123'),dict(source_url='javascript:unsafe')]:
        assert not promotion_plan({**c,**changes},varieties=[])['ready']
    record=canonical_record(c,varieties=[],actor='analyst',authorization='user')
    assert not promotion_plan(c,varieties=[record])['ready']


def test_remove_restore_preserves_original_status_source_and_relationships():
    original=canonical_record(candidate(),varieties=[],actor='analyst',authorization='user')
    original['evidence_ids']=['ev-source'];original['relationship_ids']=['rel-history'];before=deepcopy(original)
    removed=set_removed(original,removed=True,actor='analyst')
    assert not living_entities([removed])
    assert original==before and removed['evidence_ids']==['ev-source'] and removed['relationship_ids']==['rel-history']
    restored=set_removed(removed,removed=False,actor='analyst')
    assert restored['status']=='unverified' and living_entities([restored])==[restored]
    with pytest.raises(ValueError):set_removed({'entity_type':'company'},removed=True,actor='analyst')
