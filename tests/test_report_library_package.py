"""The curated reports are included in application builds, not runtime datasets."""

from pathlib import Path

from app.services.report_library import get_finished_report


def test_regina_finished_report_is_packaged_for_private_download():
    repo = Path(__file__).resolve().parents[1]
    record = get_finished_report(repo / "reports", "regina-blackberry")
    assert record is not None
    assert record["title"] == "Regina blackberry"
    assert record["page_count"] == 4
    assert record["files"]["pdf"].read_bytes().startswith(b"%PDF")
    html = record["files"]["html"].read_text(encoding="utf-8")
    assert 'src="data:image/' in html
    assert 'target="_blank" rel="noopener noreferrer"' in html
    dockerfile = (repo / "Dockerfile").read_text(encoding="utf-8")
    assert "COPY reports/library.json reports/*.html /app/reports/" in dockerfile
    assert "COPY reports/downloads /app/reports/downloads" in dockerfile
