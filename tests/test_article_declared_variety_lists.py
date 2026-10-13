"""Explicit publisher list rows must reach review without inferred trust."""
from copy import deepcopy

import pytest

from app.services.variety_universe.corpus_discovery import build_discovered_candidates


def source(text, title='Blueberry programme', **changes):
    row = {'id':'ev-list','status':'draft','source_url':'https://example.test/programme',
           'source_name':'Synthetic publisher','summary':'','berry_ids':['berry-blueberry'],
           'article':{'title':title,'paragraphs':[{'index':i,'text':p} for i,p in enumerate(text.split('\n\n'))]}}
    return {**row,**changes}


def scan(row, *, varieties=None, candidates=None):
    return build_discovered_candidates(varieties=varieties or [],entities=varieties or [],
        published_evidence=[],facts=[],source_text_records=[row],existing_candidates=candidates or [])


def narrative():
    return ('The publisher describes its programme and lists the selections offered to growers. '
            'These source statements do not establish ownership, identity equivalence, performance '
            'or a growing footprint. Those matters require their own evidence and review.')


@pytest.mark.parametrize('crop', ['blueberry','strawberry','raspberry','blackberry'])
def test_printed_rows_codes_and_marks_preserve_unreviewed_provenance(crop):
    text = '\n\n'.join([narrative(),'Varieties','HIGH CHILL',
                       'Goldenstar® ‘FC-123’\nMorningstar™ ‘FL 12-34’','LOW CHILL','Evening Star',narrative()])
    row = source(text,title=f'Programme for {crop} growers')
    original = deepcopy(row)
    report = scan(row)
    names = {r['candidate_name']:r for r in report['mentions']}
    assert set(names)=={'Goldenstar','Morningstar','Evening Star'}
    assert {r['berry_id'] for r in names.values()}=={f'berry-{crop}'}
    assert names['Goldenstar']['breeder_code']=='FC-123'
    assert names['Morningstar']['breeder_code']=='FL 12-34'
    assert 'breeder_code' not in names['Evening Star']
    assert all(r['source_text_basis']=='available_article_text' and not r['source_publication_reviewed'] for r in names.values())
    assert all(r['article_text_sources'][0]['source_url']==row['source_url'] for r in names.values())
    assert 'Goldenstar® ‘FC-123’' in names['Goldenstar']['mention_context']
    assert all(not c['human_gated'] and not c['auto_confirmed'] for c in report['candidates'])
    assert all(not c['breeder_owner'] and not c['proposed_relationships'] and not c['deployment'] for c in report['candidates'])
    assert row==original


def test_publication_tags_cannot_supply_missing_source_crop():
    report = scan(source('Varieties\n\nGoldenstar\n\n'+narrative(),title='Our programme'))
    assert report['mentions']==[]
    assert any(r['reason']=='berry_not_established' for r in report['exclusions'])


def test_mixed_document_disables_generic_title_fallback():
    text = f'Varieties\n\nGoldenstar\n\nOur raspberry programme is separate.\n\n{narrative()}'
    assert scan(source(text))['mentions']==[]


def test_explicit_section_crop_scopes_each_list_in_mixed_document():
    text = f'Blueberry varieties\n\nGoldenstar\n\nStrawberry cultivars:\n\nMorningstar\n\n{narrative()}'
    mentions = scan(source(text,title='Our multi-crop programmes'))['mentions']
    assert {(m['candidate_name'],m['berry_id']) for m in mentions}=={
        ('Goldenstar','berry-blueberry'),('Morningstar','berry-strawberry')}


@pytest.mark.parametrize('heading',['No varieties','Not blueberry varieties','Varieties not offered','Products','Brands'])
def test_no_guessing_from_unqualified_or_negated_headings(heading):
    assert scan(source(f'{heading}\n\nGoldenstar\n\n{narrative()}'))['mentions']==[]


def test_prose_and_malformed_rows_stop_without_losing_earlier_complete_rows():
    text = f'Varieties\n\nGoldenstar\nThis is ordinary prose.\nStray Name\n\nMorningstar\n\n{narrative()}'
    assert {m['candidate_name'] for m in scan(source(text))['mentions']}=={'Goldenstar'}
    bad = f'Varieties\n\nGoldenstar ‘FC-123’ trailing prose\n\n{narrative()}'
    assert scan(source(bad))['mentions']==[]


def test_chill_categories_are_not_varieties_and_tm_text_is_not_guessed_away():
    text = f'Varieties\n\nMID-HIGH CHILL\n\nEverlastTM ‘FC-123’\n\nNO CHILL\n\nGoldenstar\n\n{narrative()}'
    mentions = scan(source(text))['mentions']
    assert {m['candidate_name'] for m in mentions}=={'EverlastTM','Goldenstar'}


def test_overlong_list_reports_its_bound_and_retains_complete_rows():
    from app.services.variety_universe.explicit_article_formats import declared_article_list_rows
    from app.services.variety_universe.corpus_discovery import _NAMED_TOKEN
    text = 'Varieties\n\n'+'\n'.join(f'Selection{i}' for i in range(1025))+'\n\n'+narrative()
    rows, excluded = declared_article_list_rows(text,name_token=_NAMED_TOKEN,title_crop_ids=['berry-blueberry'])
    assert len(rows)==1024
    assert any(e['reason']=='article_list_limit' for e in excluded)


def test_long_catalogue_is_not_silently_cut_at_portrait_sized_counts():
    text = 'Varieties\n\n'+'\n'.join(f'Selection{i}' for i in range(100))+'\n\n'+narrative()
    assert len(scan(source(text))['mentions'])==100


def test_long_or_unclosed_row_cannot_become_a_huge_identity_string():
    text = 'Varieties\n\n'+'X'*1000+'\n\nGoldenstar\n\n'+narrative()
    assert scan(source(text))['mentions']==[]


def test_heading_and_chill_categories_inside_one_multiline_block():
    text = f'Varieties\nHIGH CHILL\nGoldenstar ‘FC-123’\nLOW CHILL\nMorningstar\n\n{narrative()}'
    assert {m['candidate_name'] for m in scan(source(text))['mentions']}=={'Goldenstar','Morningstar'}


def test_pending_list_reaches_reader_and_queue_without_get_writes_or_trust(monkeypatch, tmp_path):
    from app import main
    from app.services.variety_universe.candidates import load_variety_candidates
    from tests.test_captured_article_variety_coverage import setup
    from tests.test_pending_article_variety_coverage import draft, write_draft

    text = f'Varieties\nHIGH CHILL\nGoldenstar® ‘TEST-123’\nMorningstar\n\n{narrative()}'
    row = draft('ev-fictional-list', title='Fictional blueberry list', summary='',
                article={'title':'Fictional blueberry list','full_text':text})
    path = write_draft(tmp_path, row)
    client = setup(monkeypatch, tmp_path, [])
    before = {p:p.read_bytes() for p in tmp_path.rglob('*.json')}
    response = client.get('/api/intelligence/ev-fictional-list/reader?personal=1')
    assert response.status_code == 200
    assert 'Varieties in this article · 2 named' in response.text
    assert 'Needs catalog review' in response.text and 'Unreviewed' in response.text
    queue = client.get('/varieties/candidates?q=Goldenstar&berry=berry-blueberry')
    assert queue.status_code == 200 and 'TEST-123' in queue.text
    assert 'Goldenstar®' in queue.text and 'Unreviewed source' in queue.text
    assert before == {p:p.read_bytes() for p in tmp_path.rglob('*.json')}
    assert load_variety_candidates(tmp_path) == []
    assert client.post('/varieties/discover-source/ev-fictional-list', follow_redirects=False).status_code == 303
    saved = load_variety_candidates(tmp_path)
    assert {c['candidate_name'] for c in saved} == {'Goldenstar','Morningstar'}
    assert all(not c['auto_confirmed'] and not c['human_gated'] for c in saved)
    assert path.read_bytes() == before[path]
    monkeypatch.setattr(main, 'AUTHORING_MODE', False)
    assert client.get('/api/intelligence/ev-fictional-list/reader?personal=1').status_code == 404


def test_existing_human_rejection_and_edits_survive_rediscovery():
    row = source(f'Varieties\n\nGoldenstar\n\n{narrative()}')
    human = deepcopy(scan(row)['candidates'][0])
    human.update(status='rejected',human_gated=True,identity_state='rejected',
                 review_notes='Keep analyst decision',photos=[{'operator_choice':'Retain'}])
    original = deepcopy(human)
    report = scan(row,candidates=[human])
    assert not report['new_mentions'] and not report['candidates']
    assert report['already_candidate'][0]['existing_candidate_id']==human['id']
    assert human==original


def test_same_spelling_in_another_crop_cannot_attach_to_catalog():
    variety = {'id':'variety-known','name':'Goldenstar','entity_type':'variety','berry_ids':['berry-blueberry']}
    row = source(f'Raspberry varieties\n\nGoldenstar\n\n{narrative()}',title='Raspberry programme')
    original = deepcopy(variety)
    report = scan(row,varieties=[variety])
    assert not report['already_canonical']
    assert any(e['reason']=='berry_mismatch' for e in report['exclusions'])
    assert variety==original
