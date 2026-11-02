"""Reader preparation must preserve legacy regex and attribution semantics."""
from copy import deepcopy
import re

from app.services import draft_attribution as attribution


def legacy(haystack,needle):
    return bool(haystack and needle and re.search(r'\b'+re.escape(needle)+r'\b',haystack,re.IGNORECASE))


def test_prepared_patterns_retain_unicode_punctuation_and_word_boundaries():
    names=['Hortifrut','Blue Ribbon','F.C.M. 12-097','C++','Prime-Ark® 45','İstanbul','I','ı','ſ','K','Straße','Strasse','苗木','A_B','(Ruby)']
    for needle in names:
        for text in ['',needle,needle.upper(),needle.lower(),' '+needle+' ',needle+'X','X'+needle,'_'+needle,needle+'_','('+needle+')','İ I ı i ſ s K k Straße Strasse 苗木']:
            assert attribution._boundary_search(text,needle)==legacy(text,needle),(text,needle)


def test_repeated_matches_prepare_each_literal_once_and_edits_use_a_new_pattern(monkeypatch):
    attribution._boundary_pattern.cache_clear()
    compiled=[];original=re.compile
    def compile(pattern,flags=0):
        compiled.append((pattern,flags));return original(pattern,flags)
    monkeypatch.setattr(attribution.re,'compile',compile)
    for _ in range(4):
        assert attribution._boundary_search('Ruby and Garnet','Ruby')
        assert not attribution._boundary_search('Rubystone','Ruby')
    assert compiled==[(r'\bRuby\b',re.IGNORECASE)]
    assert attribution._boundary_search('Ruby and Garnet','Garnet')
    assert len(compiled)==2


def test_long_and_nonbuiltin_needles_keep_the_legacy_path_without_cache_admission():
    attribution._boundary_pattern.cache_clear()
    class Name(str):pass
    for needle in ['N'*257,Name('Ruby')]:
        assert attribution._boundary_search(' '+needle+' ',needle)==legacy(' '+needle+' ',needle)
        assert attribution._boundary_pattern.cache_info().currsize==0
    for i in range(4100):attribution._boundary_search('No matching entity','Fixture '+str(i))
    assert attribution._boundary_pattern.cache_info().maxsize==4096
    assert attribution._boundary_pattern.cache_info().currsize<=4096


def test_full_attribution_keeps_inventory_order_and_refreshes_names_aliases_and_source_identity(monkeypatch):
    entities={
        'variety-a':{'id':'variety-a','name':'Long Ruby','entity_type':'variety','aliases':['Ruby']},
        'variety-b':{'id':'variety-b','name':'Garnet','entity_type':'variety','aliases':[]},
        'company-c':{'id':'company-c','name':'İstanbul Berries','entity_type':'company','aliases':['İSTANBUL']},
    }
    record={'title':'Garnet and Ruby varieties','summary':'İstanbul Berries announces research.',
            'source_url':'https://grower.example/news','source_id':'fixture-source'}
    sources={'fixture-source':{'id':'fixture-source','linked_competitor_ids':['company-c']}}
    original=deepcopy((entities,record,sources));prepared=attribution._boundary_search
    for update in [None,'alias','name','source']:
        if update=='alias':entities['variety-b']['aliases']=['Ruby']
        if update=='name':entities['company-c']['name']='Changed company'
        if update=='source':sources['fixture-source']['linked_competitor_ids']=[]
        monkeypatch.setattr(attribution,'_boundary_search',prepared)
        current=attribution.attribute_draft(record,entities,sources=sources)
        monkeypatch.setattr(attribution,'_boundary_search',legacy)
        expected=attribution.attribute_draft(record,entities,sources=sources)
        assert current==expected
    assert record==original[1]
