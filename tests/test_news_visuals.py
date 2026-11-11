"""Reference photos stay contextual, credited, diverse, and separate from evidence."""
from copy import deepcopy
from collections import Counter
import hashlib

from app.services import news_visuals, news_images
from tests.test_news_workspace import article, project


def test_catalog_has_real_files_and_per_file_rights_evidence():
    assets = news_visuals.catalog()
    assert len(assets) >= 24
    assert {row['crop'] for row in assets} >= {'blueberry','strawberry','raspberry','blackberry',None}
    for row in assets:
        assert row['license'] in {'CC0','Public domain'} and row['rights_status'] == 'source_license_checked'
        assert row['creator'] and row['source_url'].startswith('https://commons.wikimedia.org/wiki/')
        assert hashlib.sha256((news_visuals.ROOT/row['file']).read_bytes()).hexdigest() == row['sha256']


def test_source_crop_wording_overrides_bad_inferred_assignment_and_never_changes_source():
    row = article(title='Raspberry growers expand harvest', summary='Raspberry production increases.', berry_ids=['berry-blueberry'])
    before = deepcopy(row)
    reference = news_visuals.reference_for(row)
    assert reference['crop'] == 'raspberry'
    assert reference['label'] == 'Reference photo' and 'not a photo' in reference['note']
    assert row == before
    assert news_visuals.reference_for(row)['id'] == reference['id']


def test_page_variety_and_publisher_photo_preference():
    rows = [article('ev-ref-'+str(i), published_date='2026-09-30') for i in range(7)]
    rows.append(article('ev-source-photo', image_url='https://publisher.example/actual.jpg'))
    result = project(rows)
    references = [card['reference_image'] for card in result['cards'] if not card['image_url']]
    counts = Counter(row['id'] for row in references)
    assert max(counts.values()) <= 2 and len(counts) >= 6
    assert all(row['crop'] == 'blueberry' for row in references)
    source = next(card for card in result['cards'] if card['id'] == 'ev-source-photo')
    assert source['image_url'] == 'https://publisher.example/actual.jpg'
    assert all(card['image_url'] == '' for card in result['cards'] if card['id'] != source['id'])


def test_unknown_crop_uses_only_generic_context_not_a_guessed_blueberry():
    row = article(title='SoCal Berry Growers plans farm closures', summary='The berry grower reports planned closures.', berry_ids=[])
    reference = news_visuals.reference_for(row)
    assert reference['crop'] is None
    assert 'mixed' in reference['alt'].lower() or 'research' in reference['alt'].lower()


def test_scheduled_image_budget_scans_beyond_first_page_and_respects_missing_retry(tmp_path):
    rows = [article('ev-photo-'+str(i), image_url='https://example.org/photo.jpg') for i in range(36)]
    rows += [article('ev-missing-'+str(i)) for i in range(20)]
    calls = []
    result = news_images.collect(tmp_path, rows, limit=12, scan_limit=108,
        fetch=lambda url: calls.append(url) or 'https://publisher.example/new.jpg')
    assert result == {'checked':12,'found':12} and len(calls)==12
    second = news_images.collect(tmp_path, rows, limit=12, scan_limit=108,
        fetch=lambda _: 'https://publisher.example/new.jpg')
    assert second == {'checked':8,'found':8}
