"""Avoid repeated access-wall analysis without relaxing source-text checks."""
from copy import deepcopy

import pytest

from app.services import source_body

ARTICLE = 'The grower reported firm blueberry fruit and a successful harvest in the trial.'
WALL = 'We use cookies and data to improve this website.'


@pytest.mark.parametrize('text', [ARTICLE, ARTICLE * 12])
def test_unchanged_article_is_checked_once_without_mutating_source(monkeypatch, text):
    original = source_body.looks_like_interstitial
    checked = []
    def counted(value):
        checked.append(value)
        return original(value)
    monkeypatch.setattr(source_body, 'looks_like_interstitial', counted)
    record = {'article': {'full_text': text}, 'review_notes': 'Keep this decision.'}
    before = deepcopy(record)
    result = source_body.reader_content.__wrapped__(record)
    assert result['body'] == text and result['usable_in_app']
    assert not result['contaminated'] and checked == [text]
    assert record == before


def test_changed_article_is_checked_again_after_removing_a_consent_sentence(monkeypatch):
    original = source_body.looks_like_interstitial
    checked = []
    def counted(value):
        checked.append(value)
        return original(value)
    monkeypatch.setattr(source_body, 'looks_like_interstitial', counted)
    record = {'article': {'full_text': WALL + ' ' + ARTICLE * 8}}
    result = source_body.reader_content.__wrapped__(record)
    assert result['body'] == ARTICLE * 8 and result['usable_in_app']
    assert len(checked) == 2 and checked[0] != checked[1]
    assert checked[1] == result['body']


def test_current_access_wall_and_later_source_edits_are_always_reconsidered():
    record = {'article': {'full_text': ARTICLE}}
    assert source_body.reader_content(record)['usable_in_app']
    record['article']['full_text'] = WALL * 8
    rejected = source_body.reader_content(record)
    assert rejected['state'] == 'interstitial' and rejected['contaminated']
    assert not rejected['usable_in_app']
    assert source_body.atomic_extraction_source_text(record) == ''
    record['article']['full_text'] = ARTICLE * 10
    assert source_body.reader_content(record)['usable_in_app']
    assert source_body.atomic_extraction_source_text(record) == ARTICLE * 10


def test_metadata_only_consent_page_is_still_rejected():
    record = {'summary': WALL, 'publisher_description': 'Accept all cookies.'}
    result = source_body.reader_content(record)
    assert result['state'] == 'interstitial' and result['contaminated']
    assert result['summary'] == '' and not result['usable_in_app']
