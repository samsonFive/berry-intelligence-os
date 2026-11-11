"""Shared gallery presentation keeps source classes and empty states honest."""
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape


ROOT = Path(__file__).resolve().parents[1]


def render(media):
    env = Environment(loader=FileSystemLoader(ROOT / 'app/templates'), autoescape=select_autoescape())
    return env.from_string("{% from '_brand_media.html' import entity_galleries %}{{ entity_galleries(media, 'company-test') }}").render(media=media)


def asset(**overrides):
    return {
        'id': 'asset-test', 'image_url': '/api/brand-media/asset-test/image',
        'caption': 'Example package', 'kind_label': 'Packaging photograph',
        'attribution': 'Required photographer credit', 'source_kind': 'official',
        'source_account': '@example', 'published_at': '2020-04-01T10:00:00Z',
        'historical_status': 'historical', 'match_basis': 'Recorded official account link',
        'source_page_url': 'https://www.instagram.com/p/example/',
        'inspection_href': '/api/social/ev-social-' + 'a' * 24 + '/reader?media=metadata-only',
        **overrides,
    }


def test_no_eligible_media_omits_gallery_and_candidate_urls():
    page = render({'packaging': [asset(image_url=None)], 'observations': []})
    assert '<section' not in page
    assert 'instagram.com' not in page
    assert 'Required photographer' not in page


def test_credits_historical_status_and_source_inspection_are_accessible():
    page = render({'packaging': [asset()], 'observations': []})
    assert '<dialog' in page and 'aria-haspopup="dialog"' in page
    assert 'Required photographer credit' in page
    assert 'historical' in page and '2020-04-01' in page
    assert 'data-reader-url="/api/social/ev-social-' + 'a' * 24 + '/reader?media=metadata-only"' in page
    assert 'data-item-id="ev-social-' + 'a' * 24 + '"' in page
    assert 'data-brand-source' in page


def test_retailer_and_consumer_observations_remain_separate_from_official_packs():
    page = render({'packaging': [asset()], 'observations': [asset(source_kind='retailer'), asset(source_kind='consumer')]})
    assert 'Official imagery' in page and 'Retailer observation' in page and 'Consumer sighting' in page
    assert 'company-test-packaging' in page
    assert 'company-test-retail-observations' in page
    assert 'Retail Packaging' in page and 'Retail observations' in page


def test_source_text_is_escaped_in_gallery_and_dialog():
    page = render({'packaging': [asset(caption='<script>alert(1)</script>')], 'observations': []})
    assert '<script>' not in page
    assert '&lt;script&gt;' in page


def test_shared_logo_displays_credit_and_retains_text_identity_alternative():
    env = Environment(loader=FileSystemLoader(ROOT / 'app/templates'), autoescape=select_autoescape())
    template = env.from_string("{% from '_brand_media.html' import logo %}{{ logo(asset, 'Example brand') }}")
    page = template.render(asset=asset())
    assert 'alt="Example brand logo"' in page
    assert '<figcaption>Required photographer credit</figcaption>' in page
    assert '<img' not in template.render(asset=None)


def test_existing_logo_keeps_full_identity_alt_and_safe_neutral_error_fallback():
    env = Environment(loader=FileSystemLoader(ROOT / 'app/templates'), autoescape=select_autoescape())
    template = env.from_string("{% from '_brand_media.html' import existing_logo %}{{ existing_logo(url, name, monogram) }}")
    page = template.render(url='/missing-logo.png', name="Driscoll's, Inc.", monogram='DR')
    assert 'alt="Driscoll&#39;s, Inc. logo"' in page
    assert 'data-brand-logo-fallback="DR"' in page
    assert 'data-brand-logo-style="company"' in page
    assert 'onerror=' not in page
