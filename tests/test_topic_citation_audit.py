from dataclasses import replace
import hashlib
from app.services.topic_citation_audit import audit_topic_citations
from app.services.report_builder.topic_report import topic_sections


def fixture():
 body='This floricane blackberry was introduced following field trials.'
 source={'id':'web-a','title':'New blackberry cultivar','source_name':'Breeder','source_url':'https://example.org/a','published_date':'2026-09-01','article':{'paragraphs':[{'index':0,'text':body}]}}
 row={**source,'origin':'web','trust_class':'LIVE / UNREVIEWED','source_version':hashlib.sha256(body.encode()).hexdigest(),'passage':body,'passage_locator':'article:0','relevance':'direct'}
 packet={'topic_sources':[row],'topic_research':{'plan':{'raw_query':'blackberry','interpreted_query':'blackberry','start':'2026-01-01','end':'2026-10-26'},'source_scope':'combined','discovery':{'status':'complete'}}}
 return packet,source


def test_real_report_quotes_are_bound_to_the_captured_source():
 packet,source=fixture()
 result=audit_topic_citations(packet,topic_sections(packet),{'web-a':source})
 assert result['passed'] and result['quoted_sources_checked']==1


def test_known_citation_id_cannot_launder_fabricated_prose_or_changed_source():
 packet,source=fixture();sections=topic_sections(packet)
 findings=next(s for s in sections if s.section_id=='topic_findings')
 fabricated=[replace(s,prose=s.prose.replace('introduced','sold worldwide')) if s is findings else s for s in sections]
 assert not audit_topic_citations(packet,fabricated,{'web-a':source})['passed']
 changed={**source,'article':{'paragraphs':[{'index':0,'text':'Different source text'}]}}
 assert not audit_topic_citations(packet,sections,{'web-a':changed})['passed']
 packet['topic_sources'][0]['passage_locator']='article:9'
 assert not audit_topic_citations(packet,sections,{'web-a':source})['passed']


def test_snippet_and_review_label_promotion_fail_the_audit():
 packet,source=fixture();packet['topic_sources'][0]['trust_class']='REVIEWED EVIDENCE'
 assert not audit_topic_citations(packet,topic_sections(packet),{'web-a':source})['passed']
 packet,source=fixture();source['article']={'paragraphs':[]};source['snippet']=packet['topic_sources'][0]['passage']
 assert not audit_topic_citations(packet,topic_sections(packet),{'web-a':source})['passed']


def test_verbatim_related_card_is_not_support_from_its_host_article():
 packet,source=fixture()
 body=source['article']['paragraphs'][0]['text']
 source['article']['paragraphs']=[{'index':0,'text':'This page describes a cherry breeding partnership.'},
                                  {'index':1,'text':'Related articles'}, {'index':2,'text':body}]
 row=packet['topic_sources'][0]
 row['article']=source['article'];row['passage_locator']='article:2'
 row['source_version']=hashlib.sha256('\n'.join(p['text'] for p in source['article']['paragraphs']).encode()).hexdigest()
 result=audit_topic_citations(packet,topic_sections(packet),{'web-a':source})
 assert not result['passed'] and any('locator' in failure['reason'] for failure in result['failures'])


def test_semantic_reviews_require_exact_query_excerpt_section_and_source_bindings():
 from app.services.topic_citation_audit import audit_semantic_reviews
 packet,source=fixture();sections=topic_sections(packet)
 section=next(s for s in sections if s.section_id=='topic_findings');row=packet['topic_sources'][0]
 review={'query':'blackberry','section_id':section.section_id,'source_id':row['id'],'source_version':row['source_version'],
         'passage_sha256':hashlib.sha256(row['passage'].encode()).hexdigest(),'section_sha256':hashlib.sha256(section.prose.encode()).hexdigest(),
         'disposition':'needs_review','reason':'Fixture review flags a scope concern','reviewer':'Fixture reviewer','checked_at':'2026-10-30'}
 result=audit_semantic_reviews('blackberry',packet,sections,[review])
 assert result['reviewed']==1 and result['issues']==1 and not result['unreviewed']
 for key in ('query','source_version','passage_sha256','section_sha256'):
  result=audit_semantic_reviews('blackberry',packet,sections,[{**review,key:'changed'}])
  assert result['reviewed']==0 and result['unreviewed']==1
 assert audit_semantic_reviews('blackberry',packet,sections,[review,review])['unreviewed']==1
