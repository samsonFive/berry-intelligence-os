import json

import pytest

from app.services.brand_media_discovery import extract_candidates, public_reference, MAX_HTML_BYTES


PAGE = "https://berries.example/products/blueberries"


def html(value):
    return '<script type="application/ld+json">' + json.dumps(value) + '</script>'


def test_graph_logo_and_product_images_retain_declared_subjects_and_rights_gate():
    value = {"@graph": [
        {"@type": "Organization", "@id": "#company", "name": "Berry Parent", "logo": {"@id": "#logo"}},
        {"@type": "ImageObject", "@id": "#logo", "contentUrl": "/assets/wordmark.svg", "width": 400, "height": 90},
        {"@type": ["Thing", "https://schema.org/Product"], "@id": "#product", "name": "Berry Select 125g",
         "brand": {"@type": "Brand", "name": "Berry Select", "logo": "/assets/select.png"}, "sku": "BB125", "gtin13": "1234567890123",
         "image": ["/assets/front.jpg", {"@type": "ImageObject", "url": "https://cdn.example/back.jpg"}, "/assets/front.jpg"]},
    ]}
    rows = extract_candidates(html(value), verified_page_url=PAGE, expected_entity_name="Berry Parent")
    assert len(rows) == 4
    logos = [row for row in rows if row["asset_type"] == "logo"]
    assert {row["declared_subject_name"] for row in logos} == {"Berry Parent", "Berry Select"}
    company_logo = next(row for row in logos if row["entity_name_match"] == "exact")
    assert company_logo["width"] == 400
    assert company_logo["source_locator"] == "jsonld[0]/@graph/1/contentUrl"
    assert company_logo["schema_field_locator"] == "jsonld[0]/@graph/0/logo"
    packs = [row for row in rows if row["asset_type"] == "packaging_candidate"]
    assert len(packs) == 2
    assert all(row["declared_brand_name"] == "Berry Select" and row["declared_sku"] == "BB125" for row in packs)
    assert all(row["entity_name_match"] == "mismatch" for row in packs)
    assert all(row["identity_status"] == "unverified" and row["policy_status"] == "unresolved" for row in rows)
    assert not any(row[key] for row in rows for key in ("display_allowed", "cache_allowed", "export_allowed"))
    assert rows == extract_candidates(html(value), verified_page_url=PAGE, expected_entity_name="Berry Parent")


def test_name_comparison_does_not_infer_parent_brand_or_product_relationship():
    rows = extract_candidates(html([
        {"@type": "Brand", "name": "Berry", "logo": "/berry.png"},
        {"@type": "Brand", "name": "Berry Select", "logo": "/select.png"},
        {"@type": "Product", "name": "Fresh berries", "brand": "Berry", "image": "/pack.jpg"},
    ]), verified_page_url=PAGE, expected_entity_name="  BERRY  ")
    assert [row["entity_name_match"] for row in rows] == ["exact", "mismatch", "mismatch"]


@pytest.mark.parametrize("url", [
    "https://localhost/image.png", "https://metadata.google.internal/image", "https://169.254.169.254/image",
    "https://10.0.0.1/image", "https://[::1]/image", "https://127.1/image", "https://2130706433/image",
    "https://0x7f000001/image", "https://127.0.0.1./image", "https://user:pass@cdn.example/image",
    "https://cdn.example:8443/image", "file:///tmp/image", "data:image/png;base64,aaa", "javascript:alert(1)",
    "https://cdn.example/\nimage", "https://cdn.example\\@127.0.0.1/image", "https://example.local./image",
])
def test_unsafe_reference_is_rejected(url):
    with pytest.raises(ValueError):
        public_reference(url)
    rows = extract_candidates(html({"@type": "Product", "name": "Berries", "image": url}), verified_page_url=PAGE)
    assert rows == []


def test_ignores_open_graph_favicon_search_thumbnail_and_untyped_images():
    body = ('<link rel="icon" href="/icon.png"><meta property="og:image" content="/campaign.jpg">'
            '<img alt="logo" src="/loose-berries.jpg">' + html({"@type": "Recipe", "image": "/recipe.jpg"}))
    assert extract_candidates(body, verified_page_url=PAGE) == []


def test_duplicate_schema_subjects_do_not_share_ambiguous_image_id():
    rows = extract_candidates(html({"@graph": [
        {"@type": "Brand", "name": "Berry", "logo": {"@id": "#logo"}},
        {"@type": "ImageObject", "@id": "#logo", "url": "/one.png"},
        {"@type": "ImageObject", "@id": "#logo", "url": "/two.png"},
    ]}), verified_page_url=PAGE)
    assert rows == []


def test_malformed_script_does_not_abort_later_valid_script_and_no_external_context_fetch():
    body = '<script type>ignored</script><script type="application/ld+json">{invalid</script>' + html({
        "@context": "https://127.0.0.1/context", "@type": "Organization", "name": "Berry", "logo": "/logo.png",
    })
    rows = extract_candidates(body, verified_page_url=PAGE)
    assert len(rows) == 1 and rows[0]["source_locator"].startswith("jsonld[1]")


def test_oversize_html_fails_instead_of_parsing_unbounded_input():
    with pytest.raises(ValueError, match="bounded"):
        extract_candidates("x" * (MAX_HTML_BYTES + 1), verified_page_url=PAGE)


def test_distinct_subjects_can_refer_to_same_image_without_forced_identity_merge():
    rows = extract_candidates(html([
        {"@type": "Brand", "name": "Berry", "logo": "/logo.png"},
        {"@type": "Brand", "name": "Berry Select", "logo": "/logo.png"},
    ]), verified_page_url=PAGE)
    assert len(rows) == 2 and rows[0]["candidate_id"] != rows[1]["candidate_id"]
