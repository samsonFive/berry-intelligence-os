from copy import deepcopy
import re

import pytest

from app.services.variety_universe import corpus_discovery as corpus
from app.services.variety_universe import explicit_article_formats as formats


def source(**changes):
    return {'id': 'ev-document-fixture', 'status': 'published',
            'source_type': 'company_website', 'source_name': 'Fictional publisher',
            'source_url': 'https://example.test/document',
            'berry_ids': ['berry-blueberry'], **changes}


def test_plain_document_skips_unused_list_and_paragraph_preparation(monkeypatch):
    def unexpected(*args, **kwargs):
        pytest.fail('A document without declaration syntax needs no name parser')

    monkeypatch.setattr(formats, 'declared_article_list_rows', unexpected)
    monkeypatch.setattr(formats, 'explicit_article_formats', unexpected)
    record = source()
    before = deepcopy(record)
    assert corpus._declared_names('The growers expanded their farms.\n\nProduction improved.',
                                  record, set(), source_text=True) == ([], [])
    assert record == before


@pytest.mark.parametrize('crop', ['blueberry', 'strawberry', 'raspberry', 'blackberry'])
@pytest.mark.parametrize('text', [
    "Example's 'Fixture Dawn' {crop} variety.",
    'The new {crop} cultivar is called Fixture Dawn.',
    "{crop} cultivar\n\nVariety name: 'Fixture Dawn'",
    '{crop} varieties include Fixture Dawn, Fixture Dusk.',
    'Varieties\nFixture Dawn\nFixture Dusk',
    '| crop | name |\n| {crop} | Fixture Dawn |',
    "selection codes: Fixture Dawn 'FC12-123'.",
    'variedades de arándanos: Fixture Dawn.',
    'odmiany borówki: Fixture Dawn.',
    'Varieties include Fixture Dawn.',
    'No {crop} varieties include Fixture Dawn.',
])
def test_all_existing_declarations_and_exclusions_match_the_unshortened_path(monkeypatch, crop, text):
    record = source(berry_ids=['berry-' + crop], article={'title': crop + ' varieties'})
    before = deepcopy(record)
    text = text.format(crop=crop)
    actual = corpus._declared_names(text, record, set(), source_text=True)
    # Force the new necessary-syntax gate to continue into the original body.
    monkeypatch.setattr(corpus, '_SOURCE_DECLARATION_HINT_RE', re.compile(''))
    expected = corpus._declared_names(text, record, set(), source_text=True)
    assert actual == expected and record == before


def test_new_source_text_and_review_status_are_seen_without_a_result_cache():
    record = source()
    assert corpus._declared_names('The growers expanded their farms.', record, set(), source_text=True) == ([], [])
    text = 'Blueberry varieties include Current Blue.'
    leads, _ = corpus._declared_names(text, record, set(), source_text=True)
    assert [row['candidate_name'] for row in leads] == ['Current Blue']
    assert leads[0]['source_publication_reviewed'] is True
    record['status'] = 'unreviewed'
    leads, _ = corpus._declared_names(text, record, set(), source_text=True)
    assert leads[0]['source_publication_reviewed'] is False


def test_malformed_metadata_and_unicode_crop_errors_keep_their_original_path():
    with pytest.raises(TypeError):
        corpus._declared_names('Plain prose about farms.', source(berry_ids=1), set(), source_text=True)
    with pytest.raises(KeyError):
        corpus._declared_names('strawberrıes expanded production.', source(), set(), source_text=True)
    with pytest.raises(KeyError):
        corpus._declared_names('Plain prose about farms.', source(article={'title': 'strawberrıes'}), set(), source_text=True)
    with pytest.raises(TypeError):
        corpus._declared_names(None, source(), set(), source_text=True)
