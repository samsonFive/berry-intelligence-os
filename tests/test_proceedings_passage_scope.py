"""A PDF page break is not an abstract boundary or cultivar equivalence."""
from copy import deepcopy
import hashlib

from app.services.source_passage_scope import owned_pdf_abstracts
from app.services.topic_retrieval import record_passages, match_record, plan_query
from app.services.topic_support import identity_in_passage
from app.services.topic_citation_audit import audit_topic_citations
from app.services.report_builder.topic_report import topic_sections


def proceedings():
    return [('pdf:page:5', '[PDF page 5]\nS05-I-O-5\nStrawberry drought experiment.\nKeywords: drought\n'
             'S05-I-O-6\nRaspberry cultivars from a breeding program.\n'
             'The evaluated primocane raspberries demonstrated higher yield on primocanes (\'First\','),
            ('pdf:page:6', '[PDF page 6]\n\'Second\', \'Example\', 1 kg/cane). '
             'The blackberry Other had larger fruit.\nKeywords: raspberry\n'
             'S05-I-O-7\nKiwifruit breeding trial in New Zealand.\nKeywords: kiwifruit\n')]


def test_continuation_has_owned_section_and_all_pages_without_adjacent_experiments():
    original = proceedings(); before = deepcopy(original)
    sections = owned_pdf_abstracts(original)
    selected = dict(sections)['pdf:section:S05-I-O-6:pages:5-6']
    assert 'Example' in selected and 'breeding program' in selected
    assert 'drought' not in selected and 'New Zealand' not in selected
    assert original == before
    entity = {'id':'v-example','entity_type':'variety','name':'Example','berry_ids':['berry-raspberry']}
    record = {'id':'e-fixture','title':'Conference proceedings','article':{'paragraphs':[
        {'locator':loc,'text':text} for loc,text in original]}}
    body = '\n'.join(text for _,text in original)
    row = match_record(record, plan_query('Raspberry "Example" breeder technical sheet'), entities={'v-example':entity})
    assert row and row['support_status'] == 'body_supported'
    assert row['passage_locator'] == 'pdf:section:S05-I-O-6:pages:5-6'
    assert 'New Zealand' not in row['passage']
    assert '\n'.join(p['text'] for p in record['article']['paragraphs']) == body
    assert row['passage'] in dict(record_passages(record))[row['passage_locator']]
    source = {**record, 'source_url':'https://example.org/proceedings.pdf', 'published_date':'2024-05-01'}
    snapshot = {**source, **row, 'origin':'web', 'trust_class':'LIVE / UNREVIEWED',
                'source_version':hashlib.sha256(body.encode()).hexdigest()}
    plan = plan_query('Raspberry "Example" breeder technical sheet').as_dict()
    packet = {'topic_sources':[snapshot], 'topic_research':{'plan':plan,
              'source_scope':'combined','discovery':{'status':'complete'}}}
    audit = audit_topic_citations(packet, topic_sections(packet), {'e-fixture':source})
    assert audit['passed'] and audit['quotations_checked'] == 1
    source['article']['paragraphs'][0]['text'] += ' changed'
    assert not audit_topic_citations(packet, topic_sections(packet), {'e-fixture':source})['passed']


def test_missing_pages_and_ordinary_pdfs_are_not_joined():
    rows = proceedings(); rows[1] = ('pdf:page:7', rows[1][1])
    assert owned_pdf_abstracts(rows) == rows
    ordinary = [('pdf:page:1','Ordinary paper'), ('pdf:page:2','Unrelated appendix')]
    assert owned_pdf_abstracts(ordinary) == ordinary


def test_incomplete_abstract_and_unowned_people_do_not_gain_crop_context():
    rows = proceedings()
    rows[-1] = (rows[-1][0], rows[-1][1].replace('Keywords: raspberry','Not an explicit ending'))
    assert not any('S05-I-O-6' in loc for loc,_ in owned_pdf_abstracts(rows))
    entity={'name':'Alice','berry_ids':['berry-strawberry']}
    assert identity_in_passage('Alice a main-season strawberry variety. Parentage follows.',entity)
    assert identity_in_passage('Alice is a day-neutral strawberry variety.',entity)
    assert not identity_in_passage('Alice conducted the main season strawberry trials.',entity)
    assert not identity_in_passage('The evaluated strawberries had high yield. Authors (Alice, Bob).',entity)
    assert not identity_in_passage('The evaluated raspberries had high yield (Alice, Other).',entity)
