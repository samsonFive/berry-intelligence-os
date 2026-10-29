"""Printed cultivar names are not asserted breeding codes or alias approvals."""
from copy import deepcopy

import pytest

from tests.test_variety_patent_references import VARIETY, source, refs


def filing(**fields):
    return source(names=[{'candidate_name':'Named','denomination':'Named',
                         'berry_id':'berry-blueberry','grant_number':'USPP12345P2',**fields}])


def portfolio(code='Code-1', item_id='portfolio'):
    return source(id=item_id,source_type='corporate_breeder_website',
                  url='https://example.test/'+item_id,
                  names=[{'candidate_name':'Named','breeder_code':code,'berry_id':'berry-blueberry'}])


def test_a_filing_denomination_repeating_its_name_does_not_conflict_with_a_known_code():
    sources = [filing(),portfolio()]
    before = deepcopy(sources)
    result = refs(sources)
    assert len(result)==1 and result[0]['number']=='USPP12345P2'
    assert sources==before
    assert not {'trusted','current_rights','owner','aliases'} & result[0].keys()


def test_explicit_breeding_code_is_used_when_denomination_repeats_the_name():
    assert len(refs([filing(breeder_code='Code-1'),portfolio()]))==1
    assert refs([filing(breeder_code='Code-2'),portfolio()])==[]


def test_actual_different_codes_remain_ambiguous_for_denomination_only_filing():
    assert refs([filing(),portfolio(),portfolio('Code-2','other-programme')])==[]


def test_bare_portfolio_name_still_requires_review_against_code_bearing_release():
    bare = source(id='bare-portfolio',source_type='corporate_breeder_website')
    assert refs([bare,portfolio()])==[]


@pytest.mark.parametrize('state,status',[('rejected','rejected'),('distinct','reviewed')])
def test_denomination_name_does_not_reverse_a_human_identity_decision(state,status):
    human = {'id':'human-held','candidate_name':'Named','berry_id':'berry-blueberry',
             'human_gated':True,'identity_state':state,'status':status,
             'review_notes':'Preserve the actual decision'}
    before = deepcopy(human)
    assert refs([filing(),portfolio()],candidates=[human])==[]
    assert human==before
