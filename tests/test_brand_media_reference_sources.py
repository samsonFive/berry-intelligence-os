from app.services.brand_media import official_image_reference
from app.services.brand_media_reference_sources import SOURCE_PROOFS
import pytest

@pytest.mark.parametrize('reference', SOURCE_PROOFS)
def test_exact_verified_official_external_image_reference_is_eligible(reference):
    image, page = reference['image_url'], reference['source_page_url']
    assert official_image_reference(image, page) == image

@pytest.mark.parametrize('reference', SOURCE_PROOFS)
def test_verified_cdn_binding_does_not_admit_other_images_or_publishers(reference):
    image, page = reference['image_url'], reference['source_page_url']
    assert official_image_reference(image + '&unverified_variant=1', page) is None
    assert official_image_reference(image, 'https://unrelated.example.org/') is None
    assert official_image_reference(image, page.replace('.com', '.com.attacker.example')) is None

def test_cdn_reference_still_rejects_credential_and_private_network_destinations():
    page = SOURCE_PROOFS[0]['source_page_url']
    assert official_image_reference('https://user:password@cdn.prod.website-files.com/image.png', page) is None
    assert official_image_reference('https://127.0.0.1/image.png', page) is None
