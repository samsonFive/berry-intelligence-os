from copy import deepcopy

import pytest

from app.services import source_body


@pytest.mark.parametrize(
    'summary,publisher,expected',
    [
        ('The blueberry trial recorded firm fruit and a later harvest.', '',
         'The blueberry trial recorded firm fruit and a later harvest.'),
        ('', 'The publisher describes a new strawberry breeding collaboration.',
         'The publisher describes a new strawberry breeding collaboration.'),
        ('Accept all cookies.', 'The publisher describes a new raspberry trial.',
         'The publisher describes a new raspberry trial.'),
        ('We use cookies and data to improve this website. The blackberry trial has new results.', '',
         'The blackberry trial has new results.'),
        ('Firm &amp; sweet fruit in the grower&#39;s trial.', '',
         "Firm & sweet fruit in the grower's trial."),
    ],
)
def test_reader_retains_summary_priority_literal_text_and_current_edits(summary, publisher, expected):
    record = {
        'summary': summary, 'publisher_description': publisher,
        'article': {'full_text': 'The original blueberry trial reports firm fruit and a later harvest.'},
        'review_notes': 'Keep this human note.',
    }
    before = deepcopy(record)
    content = source_body.reader_content(record)
    assert content['summary'] == expected
    assert content['contaminated'] is False
    assert record == before
    record['summary'] = 'A different current summary describing this source after an analyst edit.'
    assert source_body.reader_content(record)['summary'] == record['summary']
    assert record['review_notes'] == before['review_notes']


def test_repeated_summary_analysis_is_avoided_without_cross_record_caching(monkeypatch):
    original = source_body.clean_reader_text
    seen = []

    def counted(text):
        seen.append(text)
        return original(text)

    monkeypatch.setattr(source_body, 'clean_reader_text', counted)
    summary = 'A source summary with clear results from a blueberry trial.'
    record = {'summary': summary}
    assert source_body.reader_content(record)['summary'] == summary
    assert seen.count(summary) == 1
    assert source_body.reader_content(record)['summary'] == summary
    assert seen.count(summary) == 2


def test_duplicate_wall_blocks_keep_the_original_dominance_threshold():
    wall = 'We use cookies and data to improve this website.'
    article = 'The blueberry grower reports a successful harvest with firm fruit for several export markets.'
    assert source_body.looks_like_interstitial('\n'.join([wall] * 8 + [article])) is True
    assert source_body.looks_like_interstitial('\n'.join([wall] + [article] * 8)) is False
