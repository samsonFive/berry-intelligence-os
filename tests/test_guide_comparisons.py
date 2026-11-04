"""Help links must respect private availability and remain pure reads."""
from fastapi.testclient import TestClient
import pytest

from app import main


@pytest.mark.parametrize('authoring', [True, False])
def test_guide_comparison_availability_does_not_read_or_write_research(tmp_path, monkeypatch, authoring):
    monkeypatch.setattr(main, 'AUTHORING_MODE', authoring)
    monkeypatch.setattr(main, 'INBOX_DIR', tmp_path)
    monkeypatch.setenv('BIOS_REMOTE_INTERACTIVE', 'false')
    from app import competitive_routes

    def forbidden(*args, **kwargs):
        raise AssertionError('Help must not load competitive research or create a store')

    monkeypatch.setattr(competitive_routes, 'Store', forbidden)
    marker = tmp_path / 'retained-note.json'
    marker.write_text('{"note":"Keep my original wording"}', encoding='utf-8')
    before = {str(p.relative_to(tmp_path)): p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}
    page = TestClient(main.app).get('/guide')
    assert page.status_code == 200
    assert ('href="/competitive-evaluation"' in page.text) is authoring
    assert ('href="/competitive-evaluation?view=saved"' in page.text) is authoring
    assert ('href="/coverage/archive"' in page.text) is authoring
    assert ('id="global-watchlist-guide"' in page.text) is authoring
    assert ('href="#global-watchlist-guide"' in page.text) is authoring
    assert ('id="watchlist-briefing"' in page.text) is authoring
    assert ('href="/global-watchlist"' in page.text) is authoring
    if authoring:
        assert 'Unknown means there is not enough comparable evidence' in page.text
        assert 'The saved comparison stays fixed when news refreshes.' in page.text
        assert 'Imported berry-specific tiers keep their source and scope' in page.text
        assert 'Opening or exporting a Watchlist does not collect fresh news or verify its claims.' in page.text
    assert {str(p.relative_to(tmp_path)): p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()} == before
