"""Deterministic redirect and streaming limits for explicit public capture."""
import httpx
import pytest

from app.services import feed_first_reader as reader

URL = 'https://publisher.example/article'
ARTICLE = '<title>Berry article</title>' + ''.join('<p>' + ('Blueberry breeding and harvest improvements. ' * 12) + '</p>' for _ in range(4))


@pytest.mark.parametrize('target', ['http://127.0.0.1/private', 'http://10.0.0.2/private',
    'http://metadata.google.internal/credentials', 'file:///private', 'https://user:password@publisher.example/private',
    'http://2130706433/private', 'http://0x7f000001/private', 'http://127.1/private'])
@pytest.mark.parametrize('method', [reader.fetch_public_article, reader.fetch_source_preview_image, reader.fetch_publisher_home_preview])
def test_private_redirect_is_never_requested_even_with_auto_redirect_client(target, method):
    calls = []
    def serve(request):
        calls.append(str(request.url))
        return httpx.Response(302, headers={'location': target})
    with httpx.Client(transport=httpx.MockTransport(serve), follow_redirects=True) as client:
        if method is reader.fetch_publisher_home_preview:
            result = method(URL, 'Berry article', client=client)
        else:
            result = method(URL, client=client)
    assert calls == [URL]
    if method is reader.fetch_public_article:
        assert not result['ok'] and result['reason'] == 'redirect-not-public'
    else:
        assert result == ''


def test_public_relative_redirect_retains_body_and_original_requested_identity(tmp_path):
    calls = []
    def serve(request):
        calls.append(str(request.url))
        if request.url.path == '/article':
            return httpx.Response(301, headers={'location': '/new-article'})
        return httpx.Response(200, text=ARTICLE, headers={'content-type': 'text/html'})
    with httpx.Client(transport=httpx.MockTransport(serve)) as client:
        result = reader.capture_item(tmp_path, {'id': 'ev-bounds', 'source_url': URL}, client=client)
    assert calls == [URL, 'https://publisher.example/new-article']
    assert result['ok'] and result['requested_url'] == URL and result['url'] == calls[-1]
    assert len(result['passages']) == 4 and result['truncated'] is False


def test_redirect_loop_has_fixed_request_limit():
    calls = []
    def serve(request):
        calls.append(str(request.url))
        return httpx.Response(302, headers={'location': '/article'})
    with httpx.Client(transport=httpx.MockTransport(serve)) as client:
        result = reader.fetch_public_article(URL, client=client)
    assert len(calls) == reader.MAX_REDIRECTS + 1
    assert not result['ok'] and result['reason'] == 'redirect-limit'


class Stream(httpx.SyncByteStream):
    def __init__(self):
        self.reads = 0
        self.closed = False
    def __iter__(self):
        for _ in range(100):
            self.reads += 1
            yield ARTICLE.encode() * 10
    def close(self):
        self.closed = True


def test_large_body_is_not_fully_consumed_and_readable_capture_is_marked_partial(monkeypatch):
    stream = Stream()
    monkeypatch.setattr(reader, 'MAX_BYTES', 3000)
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, stream=stream))) as client:
        result = reader.fetch_public_article(URL, client=client)
    assert stream.closed and stream.reads < 100
    assert result['ok'] and result['availability'] == 'partial'
    assert result['truncated'] and result['reason'] == 'response-size-limit'


def test_slow_capture_stops_with_retryable_timeout(monkeypatch):
    times = iter([0, 0, 5])
    monkeypatch.setattr(reader, 'monotonic', lambda: next(times))
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, text=ARTICLE))) as client:
        result = reader.fetch_public_article(URL, client=client)
    assert not result['ok'] and result['reason'] == 'capture-timeout'


@pytest.mark.parametrize('value', ['http://[bad', 'https://publisher.example:99999/article', 'https://publisher.example:notaport/article'])
def test_malformed_url_is_a_safe_unavailable_result(value):
    assert reader.is_public_http_url(value) is False
    assert reader.fetch_public_article(value)['reason'] == 'url-not-public'


@pytest.mark.parametrize('status', [401, 403, 451, 500])
@pytest.mark.parametrize('content_type', ['text/html', 'application/pdf'])
def test_access_restrictions_and_errors_are_not_parsed_as_article(status, content_type, monkeypatch):
    def forbidden_parser(*args):
        pytest.fail('An unsuccessful response must not be parsed as an article.')
    monkeypatch.setattr(reader, 'extract_pdf_text', forbidden_parser)
    monkeypatch.setattr(reader, '_paragraphs_from_html', forbidden_parser)
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(status, text=ARTICLE, headers={'content-type': content_type}))) as client:
        result = reader.fetch_public_article(URL, client=client)
    assert result['availability'] == ('error' if status == 500 else 'blocked') and not result['ok']
    assert result['passages'] == [] and result['status_code'] == status
