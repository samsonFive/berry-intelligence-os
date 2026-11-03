"""Literal source text, edits and paragraph boundaries survive preparation."""
import pytest
import importlib.util
from app.services import html_text as text


@pytest.mark.parametrize('raw,lines,expected', [
    (None, False, ''), (0, False, ''), (1, False, '1'),
    ('<b>Prime&#8209;Ark</b> &amp; O&#39;Neal', False, "Prime‑Ark & O'Neal"),
    ('  A\tB\nC  ', False, 'A B C'),
    ('\r\n <p>A&nbsp;B</p>\n\n C\tD\u2028 E\u2029F ', True, 'A B\n\nC D\nE\nF'),
    ('\ufeffA\u200bB\x00', False, '\ufeffA\u200bB\x00'),
    ('&doesnotexist; FCM14‑052', False, '&doesnotexist; FCM14‑052'),
    ('<not closed', False, '<not closed'),
])
def test_source_names_codes_entities_and_paragraphs(raw, lines, expected):
    assert text.decode_html_text(raw, preserve_line_breaks=lines) == expected


def test_all_unicode_whitespace_keeps_word_and_line_boundaries():
    line_breaks = '\n\r\v\f\x1c\x1d\x1e\x85\u2028\u2029'
    for value in range(0x110000):
        char = chr(value)
        if char.isspace():
            assert text.decode_html_text('One'+char+'Two') == 'One Two'
            expected = 'One\nTwo' if char in line_breaks else 'One Two'
            assert text.decode_html_text('One'+char+'Two', preserve_line_breaks=True) == expected


def test_custom_values_are_coerced_again_after_an_edit():
    class Edited:
        value = 'First&nbsp;name'
        calls = 0
        def __str__(self):
            self.calls += 1
            return self.value
    value = Edited()
    assert text.decode_html_text(value) == 'First name' and value.calls == 1
    value.value = 'Changed&nbsp;name'
    assert text.decode_html_text(value) == 'Changed name' and value.calls == 2
    class CustomText(str):
        def __str__(self):return 'Rendered&nbsp;value'
    assert text.decode_html_text(CustomText('underlying')) == 'Rendered value'


def test_nonboolean_line_option_retains_its_truth_value_behavior():
    class Option:
        calls = 0
        def __bool__(self):
            self.calls += 1
            return True
    option = Option()
    assert text.decode_html_text('One\nTwo', preserve_line_breaks=option) == 'One\nTwo'
    assert option.calls == 1


def test_literal_reuse_is_bounded_and_long_text_is_not_admitted():
    # Keep capacity assertions independent of any background app warmers.
    spec = importlib.util.spec_from_file_location('isolated_html_preparation', text.__file__)
    isolated = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(isolated)
    isolated._decode_short_text.cache_clear()
    try:
        for i in range(1100):
            assert isolated.decode_html_text('Entry&nbsp;'+str(i)) == 'Entry '+str(i)
        assert isolated._decode_short_text.cache_info().currsize == 1024
        before = isolated._decode_short_text.cache_info()
        isolated.decode_html_text('x'*2049)
        assert isolated._decode_short_text.cache_info() == before
    finally:
        isolated._decode_short_text.cache_clear()
