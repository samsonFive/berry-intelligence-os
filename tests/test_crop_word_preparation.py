"""Skip unrelated prose without changing crop scope or Unicode matching."""
import random

import pytest

from app.services.variety_universe import explicit_article_formats as formats


def original(text):
    return sorted({formats._CROPS[m.group(1).casefold()]
                   for m in formats._CROP_WORDS.finditer(text)})


def observed(function, text):
    try:
        return ('value', function(text))
    except (TypeError, KeyError) as error:
        return ('error', type(error), error.args)


@pytest.mark.parametrize('text', [
    '', 'BLUEBERRY', 'strawberries and RASPBERRIES', 'blackberry-blueberry',
    'notblueberries', 'blueberries2', '_raspberry', 'blueberry_',
    'İblueberry', 'blueberryİ', 'blueberrİes', 'blueberrıes', 'blacKberry',
    'raſpberry', '\u0307blueberry', 'éblueberry', 'blueberryé', 'blueberry\u0307',
    'raspberry\n\nBLACKBERRIES', '<p>Blueberry</p>', 'blueberry &amp; blackberry',
    'Black growers recorded a new trial.', 'Straw was used as mulch.',
    None, 1, b'blueberry', [], {},
])
def test_values_and_invalid_input_behavior_match_original_word_pattern(text):
    assert observed(formats.paragraph_crop_ids, text) == observed(original, text)


def test_plain_and_unicode_boundaries_match_original_on_mixed_source_text():
    rng = random.Random(484485)
    alphabet = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 _-\t\n,.!\x00İıſKé\u0307'
    for _ in range(2500):
        text = (''.join(rng.choices(alphabet, k=rng.randint(0, 50)))
                + rng.choice(list(formats._CROPS))
                + ''.join(rng.choices(alphabet, k=rng.randint(0, 50))))
        assert observed(formats.paragraph_crop_ids, text) == observed(original, text)


def test_unrelated_prose_needs_no_crop_word_scan(monkeypatch):
    class Unexpected:
        def finditer(self, _):
            raise AssertionError('Unrelated source prose needs no crop-word scan')
    monkeypatch.setattr(formats, '_CROP_WORDS', Unexpected())
    assert formats.paragraph_crop_ids('The grower recorded a later harvest and firmer fruit.') == []
    assert formats.paragraph_crop_ids('Récolte et essai de fruits.') == []


def test_current_text_edits_and_returned_lists_remain_independent():
    record = {'summary':'BLUEBERRY'}
    result = formats.paragraph_crop_ids(record['summary'])
    result.append('fixture-edit')
    assert formats.paragraph_crop_ids(record['summary']) == ['berry-blueberry']
    record['summary'] = 'RASPBERRY and BLACKBERRIES'
    assert formats.paragraph_crop_ids(record['summary']) == ['berry-blackberry', 'berry-raspberry']
    record['summary'] = 'An unrelated current source summary.'
    assert formats.paragraph_crop_ids(record['summary']) == []


def test_non_plain_text_keeps_original_pattern_path():
    class SourceText(str):
        def casefold(self):
            raise AssertionError('Do not normalize an opaque string subclass')
    assert formats.paragraph_crop_ids(SourceText('BLUEBERRY')) == ['berry-blueberry']
