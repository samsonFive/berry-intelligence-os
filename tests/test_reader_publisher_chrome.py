"""Publisher site chrome must not displace article photographs or section titles."""
import httpx

from app.services.article_structure import publisher_heading_levels
from app.services.feed_first_reader import extract_article_images, fetch_public_article, paragraphs_from_html


def test_article_photo_is_not_displaced_by_many_header_images():
    navigation = ''.join(f'<img src="https://publisher.test/menu-{i}.jpg">' for i in range(12))
    page = f'<header>{navigation}</header><main><article><img src="https://publisher.test/berries.jpg" alt="Fruit in the trial"></article></main>'
    assert extract_article_images(page) == [{'url': 'https://publisher.test/berries.jpg', 'alt': 'Fruit in the trial'}]


def test_article_header_photo_and_flag_in_an_article_remain_eligible():
    page = '''<header><img src="https://publisher.test/country-selector.png"></header>
    <article><header><img src="https://publisher.test/fruit.jpg" alt="Harvest"></header>
    <img src="https://publisher.test/flags/chile.png" alt="Flag discussed in the article">
    <aside><img src="https://publisher.test/related.jpg"></aside></article>
    <footer><img src="https://publisher.test/site-award.jpg"></footer>'''
    assert [row['url'] for row in extract_article_images(page)] == [
        'https://publisher.test/fruit.jpg', 'https://publisher.test/flags/chile.png']


def test_declared_social_image_precedes_article_photos_and_is_deduplicated():
    page = '''<meta content="https://publisher.test/cover.jpg" property="og:image">
    <article><img src="https://publisher.test/cover.jpg"><img src="https://publisher.test/field.jpg"></article>'''
    assert [row['url'] for row in extract_article_images(page)] == [
        'https://publisher.test/cover.jpg', 'https://publisher.test/field.jpg']


def test_body_fallback_excludes_chrome_without_requiring_article_markup():
    page = '''<header><img src="https://publisher.test/menu.jpg"></header>
    <nav><img src="https://publisher.test/country-selector.png"></nav>
    <div><img src="https://publisher.test/crop.jpg" alt="Original publisher crop photo"></div>
    <footer><img src="https://publisher.test/award.jpg"></footer>'''
    assert extract_article_images(page) == [{'url': 'https://publisher.test/crop.jpg', 'alt': 'Original publisher crop photo'}]


def test_relative_images_and_alt_text_are_retained_but_unsafe_and_hidden_are_not():
    page = '''<main><img src="/fruit.jpg?size=2&amp;crop=1" alt="Field &amp; fruit">
    <img src="http://127.0.0.1/private"><img src="javascript:alert(1)">
    <div hidden><img src="https://publisher.test/hidden.jpg"></div>
    <div aria-hidden="true"><img src="https://publisher.test/invisible.jpg"></div>
    <img src="https://publisher.test/logo.png"></main>'''
    assert extract_article_images(page, page_url='https://publisher.test/story') == [
        {'url': 'https://publisher.test/fruit.jpg?size=2&crop=1', 'alt': 'Field & fruit'}]


def test_navigation_only_page_does_not_supply_a_fake_article_image():
    assert extract_article_images('<header><img src="https://publisher.test/fruit.jpg"></header>') == []


def test_missing_or_fragment_image_source_cannot_become_the_article_url():
    page = '<article><img alt="Missing source"><img src=""><img src="#local-fragment"></article>'
    assert extract_article_images(page, page_url='https://publisher.test/story') == []


def test_publisher_figure_precedes_a_generic_category_banner_in_body_fallback():
    page = '''<section><div><img src="https://publisher.test/category-banner.jpg"></div>
    <div><h2>New trial results</h2><figure><img src="https://publisher.test/harvest.jpg" alt="Fruit from the reported trial"></figure>
    <p>The article explains the reported harvest results and their limitations.</p></div></section>'''
    images = extract_article_images(page)
    assert images[0] == {'url': 'https://publisher.test/harvest.jpg', 'alt': 'Fruit from the reported trial'}


def test_site_buy_heading_is_removed_without_blacklisting_article_wording():
    prose = '<p>' + 'The fictional field trial compared harvest timing at one location. ' * 3 + '</p>'
    page = f'<header><div class="buy"><h4>Buy</h4></div></header><div><h2>Growing results</h2>{prose}</div>'
    assert paragraphs_from_html(page) == ['Growing results', ('The fictional field trial compared harvest timing at one location. ' * 3).strip()]
    assert publisher_heading_levels(page, ['Buy', 'Growing results']) == {1: 2}
    article = f'<article><header><h2>Buy</h2></header>{prose}</article>'
    assert paragraphs_from_html(article)[0] == 'Buy'
    assert publisher_heading_levels(article, ['Buy']) == {0: 2}


def test_selected_article_capture_keeps_scoped_photo_caption_and_actual_section_title():
    page = '''<html><header><h4>Buy</h4><img src="https://publisher.test/menu.jpg"></header>
    <main><header><h2>Harvest details</h2></header><img src="/trial.jpg" alt="Fruit from the fictional trial">
    <p>The fictional blueberry trial compared fruit harvested at one experimental
    location over a single season. The report describes the sampling method and
    its limitations without establishing universal performance claims.</p>
    <p>Researchers retained separate observations for the harvest dates. These
    illustrative fixture observations are not real commercial intelligence and
    do not approve a variety identity, trait or growing-region claim.</p></main></html>'''
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, text=page))) as client:
        capture = fetch_public_article('https://publisher.test/story', client=client)
    assert capture['ok']
    assert capture['images'] == [{'url': 'https://publisher.test/trial.jpg', 'alt': 'Fruit from the fictional trial'}]
    assert capture['passages'][0] == 'Harvest details'
    assert 'Buy' not in capture['passages']
    assert capture['heading_levels'] == {'0': 2}
