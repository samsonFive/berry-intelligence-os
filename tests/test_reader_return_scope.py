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
