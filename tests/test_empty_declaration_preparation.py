"""Empty-declaration preparation must retain every supported source form."""
from copy import deepcopy

import pytest

from app.services.variety_universe import corpus_discovery as corpus


def record(**changes):
    return {'id': 'ev-declaration', 'title': 'Source report', 'source_type': 'trade_press',
            'source_url': 'https://publisher.example/story', 'status': 'published',
            'berry_ids': ['berry-blueberry'], **changes}


@pytest.mark.parametrize('text,expected', [
    ('Blueberry varieties include Aurora, Brisa.', ['Aurora', 'Brisa']),
    ('Blueberry cultivars: Aurora.', ['Aurora']),
    ('Blueberry denominations are Aurora.', ['Aurora']),
    ('Blueberry varietiesincluding Aurora.', ['Aurora']),
    ('Blueberry varıeties include Aurora.', ['Aurora']),
    ('Blueberry varietieſ include Aurora.', ['Aurora']),
    ('variedades de arándanos: Aurora, Brisa.', ['Aurora', 'Brisa']),
    ('odmiany borówki: Aurora oraz Brisa.', ['Aurora', 'Brisa']),
    ("Selection codes: Aurora 'FC12-123'.", []),  # Existing code declaration is case-sensitive.
    ("selection codes: Aurora 'FC12-123'.", ['Aurora']),
    ('| crop | name |\n| blueberry | Aurora |', ['Aurora']),
    ('| uprawa | nazwa |\n| borówka | Aurora |', ['Aurora']),
    ('No blueberry varieties include Aurora.', []),
])
def test_existing_names_negation_and_case_rules_survive_the_empty_gate(text, expected):
    source = record()
    before = deepcopy(source)
    leads, _ = corpus._declared_names(text, source, set())
    assert [row['candidate_name'] for row in leads] == expected
    assert source == before


def test_unknown_crop_and_malformed_tables_keep_review_exclusions():
    leads, excluded = corpus._declared_names('Varieties include Aurora.', record(berry_ids=[]), set())
    assert not leads and [row['reason'] for row in excluded] == ['berry_not_established']
    leads, excluded = corpus._declared_names('| crop | name |\n| unknown | Aurora |', record(), set())
    assert not leads and [row['reason'] for row in excluded] == ['berry_not_established']
    leads, excluded = corpus._declared_names('| crop | name |\n| blueberry | Aurora | extra |', record(), set())
    assert not leads and [row['reason'] for row in excluded] == ['table_row_shape_unresolved']


@pytest.mark.parametrize('crop', ['blueberry', 'strawberry', 'raspberry', 'blackberry'])
def test_source_paragraph_singular_variety_format_is_still_checked(crop):
    leads, excluded = corpus._declared_names(
        f"Example's 'Fixture Dawn' {crop} variety.", record(berry_ids=[]), set(), source_text=True)
    assert [row['candidate_name'] for row in leads] == ['Fixture Dawn']
    assert [row['berry_id'] for row in leads] == ['berry-'+crop]
    assert not excluded


def test_profile_heading_scope_does_not_skip_over_unrelated_paragraph_positions():
    text = "Blueberry cultivar\n\nVariety name: 'Fixture Dawn'"
    leads, _ = corpus._declared_names(text, record(berry_ids=[]), set(), source_text=True)
    assert [row['candidate_name'] for row in leads] == ['Fixture Dawn']
    # The existing four-paragraph heading scope is not stretched by skipped prose.
    text = "Blueberry cultivar\n\n" + '\n\n'.join(['A field report with no declarations.']*4) + "\n\nVariety name: 'Fixture Dawn'"
    leads, excluded = corpus._declared_names(text, record(berry_ids=[]), set(), source_text=True)
    assert not leads and any(row['reason'] == 'berry_not_established' for row in excluded)


def test_source_edit_is_reprocessed_without_id_or_result_caching():
    source = record()
    assert corpus._declared_names('A nursery expanded its production.', source, set()) == ([], [])
    leads, _ = corpus._declared_names('Blueberry varieties include Aurora.', source, set())
    assert [row['candidate_name'] for row in leads] == ['Aurora']


def test_empty_fast_path_does_not_change_existing_malformed_input_failures():
    with pytest.raises(TypeError):
        corpus._declared_names('A plain source paragraph.', record(berry_ids=1), set())
    with pytest.raises(AttributeError):
        corpus._declared_names(None, record(), set())
