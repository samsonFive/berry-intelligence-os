from copy import deepcopy

from app.services.variety_universe import article_sources


def test_metadata_only_sources_skip_reader_display_work_and_keep_accounting(monkeypatch, tmp_path):
    records = [
        {'id': f'ev-metadata-{index}', 'status': 'published',
         'source_url': f'https://example.test/story/{index}',
         'summary': 'The publisher describes its berry portfolio.'}
        for index in range(100)
    ]
    records[1]['article'] = {'full_text': '   <p> </p> '}
    records[2]['transcript'] = {'text': 'Blueberry cultivars include Transcript Blue.'}
    records[3]['summary'] = 'Before you continue to Google. If you choose to accept all.'
    original = deepcopy(records)

    def unexpected_reader(_):
        raise AssertionError('Metadata-only records do not need Reader body classification')

    monkeypatch.setattr(article_sources, 'reader_content', unexpected_reader)
    selected, counts = article_sources.available_article_sources(records, tmp_path)
    assert selected == []
    assert counts == {'known_sources': 100, 'readable_sources': 0,
                      'reviewed_sources': 0, 'unreviewed_sources': 0,
                      'reader_captures': 0, 'oversized_sources': 0,
                      'affirmed_recoveries': 0, 'recovery_issues': 0}
    assert records == original


def test_new_article_text_is_seen_immediately_without_cached_eligibility(monkeypatch, tmp_path):
    record = {'id': 'ev-current-body', 'status': 'published',
              'source_url': 'https://example.test/current',
              'summary': 'The publisher describes the results.'}
    original = article_sources.reader_content
    seen = []

    def counted(row):
        seen.append(row['article']['full_text'])
        return original(row)

    monkeypatch.setattr(article_sources, 'reader_content', counted)
    assert article_sources.available_article_sources([record], tmp_path)[0] == []
    assert seen == []
    record['article'] = {'full_text': 'Blueberry cultivars include Source Blue and Trial Blue.'}
    selected, counts = article_sources.available_article_sources([record], tmp_path)
    assert selected == [record]
    assert counts['readable_sources'] == counts['reviewed_sources'] == 1
    assert seen == [record['article']['full_text']]
    record['article']['full_text'] = 'Before you continue to Google. If you choose to accept all.'
    assert article_sources.available_article_sources([record], tmp_path)[0] == []
    assert len(seen) == 2
