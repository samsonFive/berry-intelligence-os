"""Source-shaped regressions from the independent November 12 review."""
from copy import deepcopy
import json

import pytest

from app.services import feed_first, feed_first_reader as reader, news_images
from app.services.news_translation_quality import checked_translation
from app.services.industry_pulse.qualify import qualify_hit
from tests.test_news_qualification_decision import hit
from tests.test_news_workspace import article, project


POLISH = 'Jak powstają nowe odmiany borówki? Beata i Paweł Korfanty pokazują hodowlę od zaplecza'
TITLE = 'Strawberry price on the rise, butterhead lettuce is struggling'
QUOTE = ('Strawberry prices are rising, as is usual for this time of year. Supply is lagging behind 2025, '
         'while the price, at 8.91 euros per kilo, is higher.')


def test_reviewed_polish_idiom_repairs_only_known_headline_and_keeps_guards():
    cached = dict(title='How are new varieties of blueberry produced? Beata and Paweł Korfanty show rearing from the back',
                  summary='', source_language='pl', translation_method='local-argos-ctranslate2')
    before = deepcopy(cached)
    checked = checked_translation(POLISH, '', cached)
    assert 'behind the scenes' in checked['title']
    assert cached == before
    assert 'rearing from the back' in checked_translation('Inna hodowla', '', cached)['title']
    assert checked_translation(POLISH, '25', {**cached, 'summary': '250'}) is None
    assert checked_translation(POLISH, '', {**cached, 'title': cached['title'] + ' 250'}) is None


def test_government_crest_uses_existing_reference_without_rejecting_real_photos():
    crest = 'https://www.gob.pe/assets/escudo-rojo-200-f4bf73f7.png'
    row = article(image_url=crest)
    before = deepcopy(row)
    assert feed_first.safe_image_url(row) == ''
    card = project([row])['cards'][0]
    assert '/static/news-images/reference/' in str(card)
    assert row == before
    for url in ['https://cdn.www.gob.pe/uploads/document/file/123/blueberries.jpg',
                'https://publisher.example/assets/escudo-rojo-photo.jpg']:
        assert feed_first.safe_image_url({'image_url': url}) == url


def test_crop_excerpt_is_source_exact_bounded_metadata_and_survives_image_refresh(tmp_path, monkeypatch):
    row = article(status='draft', title=TITLE, summary="At Belgian auctions, the average price for truss tomatoes has fallen after peaking in mid-October. The average price came to 1.57 euros per kilo in week 45. That is still above both the five-year average and last year's level, despite higher volumes.",
                  source_url='https://www.freshplaza.com/article/9891876/strawberry-price-on-the-rise-butterhead-lettuce-is-struggling/',
                  berry_ids=['berry-strawberry'])
    capture = dict(headline=TITLE, requested_url=row['source_url'], availability='full',
                   passages=[row['summary'], QUOTE], content_kind='article')
    before = deepcopy(capture)
    reader.save_capture(tmp_path, row['id'], capture)
    projected = reader.attach_capture_previews({row['id']: row}, tmp_path)[row['id']]
    assert projected['news_preview_excerpt'] == QUOTE
    assert project([projected])['cards'][0]['deck'] == QUOTE
    assert projected['summary'] == row['summary'] and capture == before
    from app.services import personal_digest
    monkeypatch.setattr(personal_digest, 'retained_news', lambda *args, **kwargs: [row])
    monkeypatch.setattr(reader, 'load_capture', lambda *args, **kwargs: pytest.fail('Browse must not load article bodies'))
    metadata = personal_digest.source_records([], tmp_path, metadata_only=True)[row['id']]
    assert metadata['news_preview_excerpt'] == QUOTE and metadata['summary'] == row['summary']
    news_images.collect(tmp_path, [row], retry_missing=True, fetch=lambda _: 'https://publisher.example/photo.jpg')
    preview = json.loads(news_images.preview_path(tmp_path, row['id']).read_text())
    assert preview['crop_excerpt'] == QUOTE
    assert json.loads(reader.capture_path(tmp_path, row['id']).read_text())['passages'] == capture['passages']
    changed = {**row, 'source_url': 'https://publisher.example/new'}
    news_images.collect(tmp_path, [changed], retry_missing=True, fetch=lambda _: '')
    assert 'crop_excerpt' not in json.loads(news_images.preview_path(tmp_path, row['id']).read_text())


@pytest.mark.parametrize('changes', [dict(status='published'), dict(translated=True), dict(title='Other strawberry headline'),
                                    dict(source_url='https://publisher.example/other'), dict(summary=QUOTE)])
def test_crop_excerpt_never_overrides_reviewed_translated_changed_or_already_relevant_prose(tmp_path, changes):
    row = article(status='draft', title=TITLE, summary='Tomato statistics lead this mixed report.')
    reader.save_capture(tmp_path, row['id'], dict(headline=TITLE, requested_url=row['source_url'],
                        availability='full', passages=[QUOTE]))
    changed = {**row, **changes}
    assert 'news_preview_excerpt' not in reader.attach_capture_previews({row['id']: changed}, tmp_path)[row['id']]


def test_moroccan_collective_berry_logistics_survives_both_screens():
    title = "Moroccan soft fruit sector still on the quest for alternatives to Tangiers-Algeciras corridor"
    snippet = ("Morocco's berry industry is still struggling to find viable alternatives to the Tangier-Algeciras route, "
               "the main artery for Moroccan berry shipments to Europe.")
    assert qualify_hit(hit(title, snippet, host='freshplaza.com')).qualifying
    assert project([article(title=title, summary=snippet, berry_ids=[])])['cards']


@pytest.mark.parametrize('crop', ['Cranberry', 'Carrot', 'Pineapple', 'Tomato'])
def test_collective_shipping_vocabulary_does_not_admit_other_crops(crop):
    title = crop + ' shipments expand'
    snippet = crop + ' industry expands berry shipments to Europe.'
    assert not qualify_hit(hit(title, snippet)).qualifying
    assert not project([article(title=title, summary=snippet, berry_ids=[])])['cards']
