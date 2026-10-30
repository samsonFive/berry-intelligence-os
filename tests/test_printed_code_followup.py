"""Printed labels never silently select a genotype, grant or photo permission."""
from copy import deepcopy
import json
from pathlib import Path
from app.services.variety_portfolio_coverage import load_portfolio_observations, _identity_pair_notes, _coded_label_keys, _code_comparison_key
from app.services.variety_patent_references import original_patent_references
from app.services.variety_photos import source_photos, gallery

ROOT=Path(__file__).resolve().parents[1]

def batch():
    return [row for row in load_portfolio_observations(ROOT/'data')
            if row['id'].startswith('portfolio-printed-code-')]

def test_all_printed_code_checks_preserve_empty_results_and_conflicting_labels():
    report=json.loads((ROOT/'data/imports/variety-portfolio-observations-2026-10-13-printed-code-followup/printed-code-accounting.json').read_text())
    rows=report['queries']
    assert len(rows)==6 and len({row['name'] for row in rows})==5
    assert sum(row['result_count'] for row in rows)==1
    assert sum(row['matching_berry_rows'] for row in rows)==1
    assert all(not row['identity_approved'] and not row['current_rights_verified'] for row in rows)
    assert all('not evidence of absent rights' in row['outcome'] for row in rows if not row['result_count'])
    baridi=[row for source in batch() for row in source['names'] if row['candidate_name']=='Baridi']
    assert {row['breeder_code'] for row in baridi}=={'ABB132','ABB 137'}
    assert all(source['review_warnings'] for source in batch() if any(row['candidate_name']=='Baridi' for row in source['names']))

def test_original_filing_is_not_assigned_to_an_unapproved_commercial_alias():
    sources=batch()
    redsayra=json.loads((ROOT/'data/entities/varieties/variety-redsayra.json').read_text())
    assert redsayra['aliases']==[]
    assert not original_patent_references(variety=redsayra,varieties=[redsayra],entities=[redsayra],candidates=[],sources=sources)
    row=next(source for source in sources if source['id']=='portfolio-printed-code-cpvo-20202126')
    filing=row['names'][0]
    assert filing['candidate_name']==filing['denomination']=='Plared 15121'
    assert filing['application_number']=='20202126' and filing['grant_number']=='63205'
    assert filing['application_date']=='2020-09-07' and filing['grant_date']=='2023-02-20'
    assert row['capture_reference']['native_detail_verified']
    assert not row['capture_reference']['current_legal_status_verified']


def test_issuer_code_spacing_does_not_create_false_holds_but_real_numbers_do():
    sources=batch()
    notes=_identity_pair_notes(sources)
    assert not any(messages for key,messages in notes.items() if key[1][0] in {'malaika','zawadi'})
    assert any(messages for key,messages in notes.items() if key[1][0]=='baridi')
    keys=_coded_label_keys(sources)
    assert ('baridi','berry-raspberry') in keys
    assert ('malaika','berry-raspberry') not in keys
    assert ('zawadi','berry-raspberry') not in keys
    assert _code_comparison_key('ABB 135')==_code_comparison_key('ABB135')
    assert _code_comparison_key('ABB 137')!=_code_comparison_key('ABB132')
    assert _code_comparison_key('ABB 13 5')!=_code_comparison_key('ABB135')
    assert _code_comparison_key('CODE 135')!=_code_comparison_key('CODE135')

def test_focal_context_does_not_transfer_to_comparisons_or_related_navigation():
    sources=batch()
    assert len(sources)==9 and sum(len(row['names']) for row in sources)==12
    context=[source for source in sources if source['source_type'] in {'company_context_names','research_context_names'}]
    assert {row['candidate_name'] for source in context for row in source['names']}=={'Plared 18009','Red Samantha','Von'}
    assert all(not any(row.get(key) for key in ('application_number','grant_number','photos')) for source in context for row in source['names'])
    assert all(source['review_state']=='unreviewed' for source in sources)

def test_two_ervin_photos_are_attributed_held_and_never_people_portraits():
    sources=batch()
    target=json.loads((ROOT/'data/entities/varieties/variety-ervin.json').read_text())
    before=deepcopy(target)
    photos=source_photos(target,sources=sources,varieties=[target])
    assert len(photos)==2 and {row['kind'] for row in photos}=={'fruit','plant'}
    assert all(row['named_variety']=='Ervin' and row['reuse']=='unknown' for row in photos)
    assert all(not row['display_image'] for row in gallery(target,sourced=photos,authoring=True))
    assert gallery(target,sourced=photos,authoring=False)==[]
    assert all(row['credit']=='NC State Extension; photographer not credited' for row in photos)
    assert all('Ervin_Lineberger' not in row['image_url'] and 'Gina' not in row['image_url'] for row in photos)
    assert target == before
    # The separately source-backed NC 740 alias is not a photo approval.
    assert target['aliases'] == ['NC 740']
    assert target['attributes']['alias_sources'][0]['alias'] == 'NC 740'
