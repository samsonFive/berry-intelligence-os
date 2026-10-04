import copy
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import main
from app.services import market_statistics_reference as reference
from app.services.global_explorer import IntelligenceQuery, snapshot_model
from app.services.report_builder import pdf_export
from app.services.report_builder.pdf_export import render_report_pdf
from scripts.capture_map_statistics import capture


def fixture():
    categories = {"freq": ["A"], "crops": ["S0000"], "strucpro": ["AR_THS_HA", "HPRD_HUMD_EU_THS_T", "YLD_HUMD_EU_T_HA"], "geo": ["PT"], "time": ["2025", "2026"]}
    return {"id": list(categories), "size": [len(v) for v in categories.values()],
            "dimension": {k: {"category": {"index": {c: i for i, c in enumerate(codes)}, "label": {c: c for c in codes}}} for k, codes in categories.items()},
            "value": {"0": 0, "2": 10.83}, "status": {"2": "p"}, "updated": "2026-09-28T23:00:00+0200"}


STAMP = "2026-10-03T03:00:00+00:00"


def test_initial_references_reproduce_the_original_official_capture():
    root = Path(__file__).resolve().parents[1]
    original = json.loads((root / "data/imports/map-market-references-2026-10-03/eurostat-strawberries.json").read_text(encoding="utf-8"))
    stored = json.loads((root / "data/configuration/market_statistics_reference.json").read_text(encoding="utf-8"))["groups"]
    actual = [g for g in stored if g["source"] == "Eurostat"]
    assert actual == reference.eurostat_groups(original["payload"], captured_at=original["captured_at"])
    assert len(actual) == 4 and sum(len(g["metrics"]) for g in actual) == 8


def test_sparse_latest_period_retains_zero_flag_and_no_inferred_yield():
    payload = fixture()
    before = copy.deepcopy(payload)
    groups = reference.eurostat_groups(payload, captured_at=STAMP)
    assert payload == before
    group = groups[0]
    assert group["period"] == "2025 calendar year" and group["country_id"] == "geography-portugal"
    assert [m["value"] for m in group["metrics"]] == [0, 10.83]
    assert group["metrics"][1]["source_flag"] == "p"
    assert "Yield" not in [m["label"] for m in group["metrics"]]
    assert group["published_date"] == "Not supplied" and group["source_updated_at"] == payload["updated"]
    assert "time=2025" in group["source_url"]


@pytest.mark.parametrize("change", ["mixed", "geo", "nan", "negative", "years", "dimension", "empty", "cell"])
def test_out_of_scope_bad_or_empty_capture_cannot_replace_reference(change, tmp_path):
    payload = fixture()
    if change == "mixed": payload["dimension"]["crops"]["category"]["index"] = {"F3000": 0}
    if change == "geo": payload["dimension"]["geo"]["category"]["index"] = {"EU27_2020": 0}
    if change == "nan": payload["value"]["2"] = float("nan")
    if change == "negative": payload["value"]["2"] = -10
    if change == "years": payload["dimension"]["time"]["category"]["index"] = {"2001": 0, "2026": 1}
    if change == "dimension": payload["size"] = [1]
    if change == "empty": payload["value"] = {}
    if change == "cell": payload["value"] = {"999": 10}
    prior = tmp_path / "old.json"
    prior.write_text("original operator capture")
    with pytest.raises(ValueError):
        capture(output_dir=tmp_path, fetch=lambda **kw: payload, now=datetime.fromisoformat(STAMP))
    assert list(tmp_path.iterdir()) == [prior] and prior.read_text() == "original operator capture"


def test_confidential_cell_is_omitted_without_reclassifying_other_figures():
    payload = fixture()
    payload["status"]["2"] = "c"
    group = reference.eurostat_groups(payload, captured_at=STAMP)[0]
    assert [m["label"] for m in group["metrics"]] == ["Area"]


def test_recapture_keeps_each_original_payload_and_existing_files(tmp_path):
    calls = []
    def fetch(**kw):
        calls.append(kw)
        return fixture()
    first, groups = capture(output_dir=tmp_path, fetch=fetch, now=datetime.fromisoformat(STAMP))
    original = first.read_bytes()
    second, _ = capture(output_dir=tmp_path, fetch=fetch, now=datetime.fromisoformat(STAMP))
    assert first != second and first.read_bytes() == original
    assert json.loads(second.read_text())["payload"] == fixture()
    assert calls[0] == {"crops": ["S0000"], "geos": list(reference.GEOS), "since_year": 2023}
    identified = reference.identified_groups(groups)
    revised = copy.deepcopy(groups)
    revised[0]["metrics"][0]["value"] = 99
    assert identified[0]["metrics"][0]["id"] == reference.identified_groups(revised)[0]["metrics"][0]["id"]
    assert reference.flag_label("p") == "Provisional" and reference.flag_label("x") == "Source flag: x"


ENTITIES = {"geography-spain": {"id": "geography-spain", "name": "Spain", "entity_type": "geography"},
            "geography-portugal": {"id": "geography-portugal", "name": "Portugal", "entity_type": "geography"}}
BERRIES = {"berry-strawberry": "Strawberry"}


def captured_pdf_text(monkeypatch):
    texts = []
    original = pdf_export.Paragraph
    def paragraph(text, style, **kwargs):
        texts.append(text)
        return original(text, style, **kwargs)
    monkeypatch.setattr(pdf_export, "Paragraph", paragraph)
    return texts


def test_selected_figures_are_source_linked_in_snapshot_and_readable_pdf(monkeypatch):
    texts = captured_pdf_text(monkeypatch)
    query = IntelligenceQuery(("geography-spain", "geography-portugal"), berry_ids=("berry-strawberry",))
    model = snapshot_model(query, [], ENTITIES, [], BERRIES, ["statistics"])
    assert len(model["statistics"]["groups"]) == 2
    group = next(g for g in model["metric_options"] if g["country"] == "Spain")
    production = next(m for m in group["metrics"] if m["label"] == "Harvested production")
    selected = snapshot_model(query, [], ENTITIES, [], BERRIES, ["statistics"], metric_ids=[production["id"]])
    assert selected["statistics"]["groups"][0]["metrics"] == [production]
    assert len(selected["packet"]["source_trace"]) == 1
    assert "geo=ES" in selected["packet"]["source_trace"][0]["source_url"]
    content = render_report_pdf(selected["report"], selected["packet"], selected["coverage"])
    assert content.startswith(b"%PDF")
    text = "\n".join(texts)
    assert "332.05" in text and "1000 t" in text and "2025 calendar year" in text and "reporting framework" in text
    assert "Source updated 2026-09-28" in text and "7.04" not in text and "market-ref-" not in text
    assert "geography-spain" not in text and "Working report; analyst review required" in text
    assert not snapshot_model(query, [], ENTITIES, [], BERRIES, ["statistics"], metric_ids=[])["packet"]["source_trace"]
    assert not snapshot_model(query, [], ENTITIES, [], BERRIES, ["overview"])["packet"]["source_trace"]
    with pytest.raises(ValueError, match="no longer available"):
        snapshot_model(query, [], ENTITIES, [], BERRIES, ["statistics"], metric_ids=["missing"])


def test_snapshot_composition_and_pdf_have_identical_metric_scope(monkeypatch):
    texts = captured_pdf_text(monkeypatch)
    monkeypatch.setattr(main, "entity_index", lambda: ENTITIES)
    monkeypatch.setattr(main, "published_evidence", lambda: [])
    monkeypatch.setattr(main, "all_relationships", lambda: [])
    monkeypatch.setattr(main, "all_facts", lambda: [])
    monkeypatch.setattr(main, "AUTHORING_MODE", False)
    client = TestClient(main.app)
    query = IntelligenceQuery(("geography-spain",), berry_ids=("berry-strawberry",))
    model = snapshot_model(query, [], ENTITIES, [], BERRIES, ["statistics"])
    mid = model["metric_options"][0]["metrics"][0]["id"]
    params = {**query.params(), "sections": "statistics", "metrics": mid}
    page = client.get("/explorer/snapshot", params=params)
    assert page.status_code == 200 and 'data-metric="' + mid in page.text and "Definitions &amp; source notes" not in page.text
    assert "Definitions & source notes" in page.text and "332.05" in page.text  # remaining option is visible for selection
    pdf = client.get("/explorer/snapshot.pdf", params=params)
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    text = " ".join(texts)
    assert "7.04" in text and "332.05" not in text
    assert client.get("/explorer/snapshot.pdf", params={**params, "metrics": "missing"}).status_code == 422
    assert client.get("/explorer/snapshot", params={**params, "metrics": "missing"}).status_code == 422
