from copy import deepcopy
from app.services.research_event_groups import event_groups

ENTITIES={
 'v':{'id':'v','entity_type':'variety','name':'Ervin','aliases':[],'berry_ids':['berry-blackberry']},
 'c':{'id':'c','entity_type':'company','name':'Global Plant Genetics (GPG)','aliases':['GPG']},
 'us':{'id':'us','entity_type':'geography','name':'United States','aliases':[]},
 'eu':{'id':'eu','entity_type':'geography','name':'Europe','aliases':[]},
}

def row(i,day='2026-09-01',company='Global Plant Genetics',place='outside the United States',title='Introducing Ervin blackberry'):
 return {'id':i,'title':title,'source_url':'https://example.org/'+i,'published_date':day,
         'article':{'paragraphs':[{'index':0,'text':'The variety has been licensed to '+company+' for development '+place+'.'}]}}

def test_license_reprint_groups_without_merging_the_breeder_introduction():
 rows=[row('primary'),row('trade','2026-09-03',company='GPG',title='Ervin enters international development'),
       {**row('intro','2026-02-08'),'article':{'paragraphs':[{'index':0,'text':'Ervin is a new floricane blackberry cultivar introduced by its breeder.'}]}}]
 before=deepcopy(rows)
 groups=event_groups(rows,ENTITIES)
 assert [g['member_ids'] for g in groups]==[['primary','trade'],['intro']]
 assert rows==before and 'independence not established' in groups[0]['label']

def test_different_territory_unknown_date_and_ambiguous_variety_stay_separate():
 for other in [row('other',place='in Europe'),row('other',day=''),row('other',company='Another Nursery')]:
  assert len(event_groups([row('primary'),other],ENTITIES))==2
 ambiguous={**ENTITIES,'v2':{**ENTITIES['v'],'id':'v2'}}
 assert len(event_groups([row('a'),row('b',title='Ervin international development')],ambiguous))==2

def test_nearby_date_chain_cannot_merge_distant_events():
 groups=event_groups([row('a'),row('b','2026-09-07'),row('c','2026-09-13')],ENTITIES)
 assert [g['member_ids'] for g in groups]==[['a','b'],['c']]


def test_unknown_license_parties_do_not_merge_even_with_identical_titles():
 assert len(event_groups([row('a',company='Unknown Nursery'),row('b',company='Other Nursery')],ENTITIES))==2


def test_report_group_membership_survives_saved_snapshot_without_research_replay(tmp_path,monkeypatch):
 import hashlib
 from app.services.report_builder.scope import ResolvedScope
 from app.services.report_builder.topic_report import attach_topic_research,topic_sections
 records=[row('a'),row('b','2026-09-03',company='GPG',title='Ervin enters international development')]
 for record in records:
  body=record['article']['paragraphs'][0]['text']
  record.update(source_name='Fixture publisher',source_version=hashlib.sha256(body.encode()).hexdigest(),passage=body,passage_locator='article:0',relevance='direct')
 monkeypatch.setattr('app.services.report_builder.topic_report.discover_topic',lambda *a,**k:{'items':records,'status':'complete','failures':[]})
 scope=ResolvedScope('market_landscape',None,(),(),(),None,None,'',research_query='Floricane blackberry',source_scope='combined')
 packet=attach_topic_research({'topic_matches':[]},scope,entities=ENTITIES,inbox_dir=tmp_path)
 saved=packet['topic_research']
 assert saved['event_groups'][0]['member_ids']==['a','b']
 assert 'members' not in saved['event_groups'][0]
 def forbidden(*a,**k):raise AssertionError('saved report must not requery')
 monkeypatch.setattr('app.services.report_builder.topic_report.discover_topic',forbidden)
 from dataclasses import replace
 replay=attach_topic_research({'topic_matches':[]},replace(scope,research_snapshot=saved),entities=ENTITIES,inbox_dir=tmp_path)
 grouping=next(s for s in topic_sections(replay) if s.section_id=='topic_related_coverage')
 assert grouping.citation_ids==('a','b') and 'independence is not established' in grouping.prose
