"""Existing breeding programs can open source varieties without a company dossier."""
from fastapi.testclient import TestClient
from app import main


def test_program_varieties_without_company_backbone_remain_read_only(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path)
    monkeypatch.setattr(main, "AUTHORING_MODE", True)
    page = TestClient(main.app).get("/entities/breeding_program/breeding_program-university-of-georgia-blueberry?tab=varieties")
    assert page.status_code == 200
    assert 'aria-current="page">Varieties' in page.text
    assert "Varieties named in sources" in page.text and "Blue Suede" in page.text
    assert "Reviewed variety links · 0" in page.text
    assert not list(tmp_path.iterdir())
