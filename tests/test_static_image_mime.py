"""Release thumbnails are served as images on hosts without a MIME database."""
import pytest
from fastapi.testclient import TestClient

from app import main


@pytest.mark.parametrize('crop', ['blueberry-orchard', 'blackberry-quality', 'raspberry-harvest', 'strawberry-growing'])
def test_news_image_delivery_has_webp_content_type_and_valid_body(crop):
    response = TestClient(main.app).get('/static/news-images/' + crop + '.webp')
    assert response.status_code == 200
    assert response.headers['content-type'] == 'image/webp'
    assert response.content[:4] == b'RIFF' and response.content[8:12] == b'WEBP'
