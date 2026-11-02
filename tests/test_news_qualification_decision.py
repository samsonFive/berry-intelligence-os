"""News' Boolean projection must preserve the complete qualifier's decisions."""
from copy import deepcopy
from itertools import product

from app.services.industry_pulse.models import DiscoveryHit
from app.services.industry_pulse.qualification_benchmark import load_benchmark, _hit_from_entry
from app.services.industry_pulse.qualify import (
    QualificationIndex, SOURCE_TRADE, SOURCE_BREEDER, SOURCE_GOV_AG,
    SOURCE_GOV_UNRELATED, SOURCE_UNIVERSITY, is_qualifying_hit, qualify_hit,
)


def hit(title, snippet='', host='fixture.test'):
    return DiscoveryHit(title=title,snippet=snippet,url='https://'+host+'/article',
        source_domain=host,published_date=None,query_id='fixture',query_text='',
        geography='',berry=None,topic=None,provider='memory')


def test_decision_matches_full_qualifier_for_existing_benchmark_without_mutation():
    index=QualificationIndex.compile(company_names=['Fall Creek','Planasa'],variety_names=['Emerald','Blue Ribbon'])
    for entry in load_benchmark()['entries']:
        original=_hit_from_entry(entry); before=deepcopy(original.as_dict())
        assert is_qualifying_hit(original,index=index) is qualify_hit(deepcopy(original),index=index).qualifying, entry['id']
        assert original.as_dict()==before


def test_decision_preserves_exclusions_named_only_hits_and_source_contexts():
    names=['Unknown organization','Fall Creek','Emerald']
    titles=['Blueberry harvest expands','Berry production grows','Strawberry field trial',
        'Blackberry cultivation','Raspberry Pi farm genetics','BlackBerry stock price',
        'Blueberry smoothie recipe','Strawberry breeding job posting','Cannabis genetics',
        'Blueberry food recall','Blueberry industry outbreak','Unknown topic','Blueberry',
        'Berry festival','Fall Creek partnership','Emerald launch','Tomato exports']
    contexts=[SOURCE_TRADE,SOURCE_BREEDER,SOURCE_GOV_AG,SOURCE_GOV_UNRELATED,SOURCE_UNIVERSITY,'unknown']
    index=QualificationIndex.compile(company_names=['Fall Creek'],variety_names=['Emerald'])
    for title,snippet,context in product(titles,names,contexts):
        scoped=QualificationIndex(index.company_re,index.variety_re,{'fixture.test':context})
        original=hit(title,snippet); before=deepcopy(original.as_dict())
        assert is_qualifying_hit(original,index=scoped) is qualify_hit(deepcopy(original),index=scoped).qualifying, (title,snippet,context)
        assert original.as_dict()==before


def test_decision_preserves_government_url_and_origin_host_resolution():
    index=QualificationIndex.compile()
    for host in ['fda.gov','accessdata.fda.gov','cdc.gov','jobcorps.gov','usda.gov','defra.gov.uk','fixture.test']:
        for title in ['Blueberry harvest production','Blueberry food recall','Berry outbreak','Strawberry','Unknown']:
            original=hit(title,host=''); original.url='https://wrapper.test/story'; original.origin_publisher_url='https://'+host+'/original'
            assert is_qualifying_hit(original,index=index) is qualify_hit(deepcopy(original),index=index).qualifying
