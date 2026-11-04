import pytest

from app.personal_digest_routes import reader_return_path


@pytest.mark.parametrize('path', [
    '/today?media=video&q=Ica&view=unreviewed&page=2',
    '/news?media=podcast&berry=berry-blueberry',
    '/digest?source=source-podcast',
    '/statements?view=unreviewed',
])
def test_reader_preserves_local_feed_scope(path):
    assert reader_return_path(path) == path


@pytest.mark.parametrize('path', [
    'https://example.org/today', '//example.org/today',
    '/today/other', '/review/record', 'javascript:/today',
    'https://[invalid/today',
])
def test_reader_return_rejects_other_destinations(path):
    assert reader_return_path(path) == '/digest'


@pytest.mark.parametrize('scoped', [False, True])
def test_shared_news_cards_keep_full_personal_reader_separate_from_feed_bookmark(scoped):
    from lxml import html
    from app import main
    from app.services import feed_first

    card = feed_first.present_item(
        {'id': 'ev-recording', 'title': 'Blueberry recording', 'source_name': 'Publisher',
         'source_url': 'https://publisher.org/episode', 'media_format': 'podcast'},
        entities_by_id={}, state=feed_first.empty_state(), filters=feed_first.parse_filters({}))
    assert card['reader_href'].startswith('/today?')
    expected = '/intelligence/ev-recording?personal=1'
    if scoped:
        expected += '&return_to=%2Ftoday%3Fmedia%3Dpodcast'
        card['full_reader_href'] = expected
    rendered = main.templates.get_template('_news_cards.html').render(
        cards=[card], workspace_feed=True, authoring_mode=True)
    assert html.fromstring(rendered).xpath('//a[@data-open-reader]/@href') == [expected, expected]
