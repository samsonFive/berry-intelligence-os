"""Raw export preservation does not establish source support or a rating."""
from scripts.capture_competitive_web_returns import capture, inspect_csv


def test_csv_keeps_unknowns_dates_units_and_export_artifact():
    raw = b'observation_id,value_or_statement,unit_denominator_currency,period_start,\r\nB01-O001,Unknown,kg,2025-01-01,\r\n'
    report = inspect_csv(raw)
    assert report["batch_ids"] == ["B01"]
    assert report["column_count"] == 5
    assert report["headers"][-1] == ""
    assert report["warnings"]


def test_lowercase_metadata_and_wide_metadata_keep_batch():
    assert inspect_csv(b'field,value\nbatch_id,B02\n')["batch_ids"] == ["B02"]
    assert inspect_csv(b'batch_id,research_date\nB03,2026-10-30\n')["batch_ids"] == ["B03"]


def test_capture_is_idempotent_and_does_not_read_unrelated_csv(tmp_path):
    downloads, output = tmp_path / "downloads", tmp_path / "output"
    downloads.mkdir()
    (downloads / "observationid-entityid.csv").write_bytes(b'observation_id,value\nB01-O001,Unknown\n')
    (downloads / "unrelated-personal.csv").write_bytes(b'private,data\nsensitive,do-not-read\n')
    first = capture(downloads, output, since=0)
    second = capture(downloads, output, since=0)
    assert first["captured_files"] == 1
    assert second["captured_files"] == 0
    assert second["already_present"] == 1
    raw = list((output / "raw/B01").iterdir())
    assert len(raw) == 1 and b'Unknown' in raw[0].read_bytes()
    assert not list(output.rglob('*unrelated*'))


def test_ambiguous_or_empty_export_is_retained_for_resolution(tmp_path):
    downloads, output = tmp_path / "downloads", tmp_path / "output"
    downloads.mkdir()
    (downloads / "gapid-entityid.csv").write_bytes(b'gap_id,entity_id\n')
    summary = capture(downloads, output, since=0)
    assert summary["unresolved_files"] == 1
    assert list((output / "raw/unresolved").iterdir())
