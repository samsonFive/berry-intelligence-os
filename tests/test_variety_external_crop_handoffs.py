"""Collection handoffs preserve source scope and never make a trust decision."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from jinja2 import Environment, FileSystemLoader, select_autoescape

from app import main
from app.services.variety_external_coverage import (
    GDR_RUBUS_CROP_TAXA, collection_crop_scope, compare_baseline,
    external_coverage_view, load_external_baselines,
    prepare_blueberry_identity_lead, prepare_external_identity_lead,
)
from app.services.variety_universe.candidates import load_variety_candidates
from test_variety_external_coverage import analyze, grin

ROOT = Path(__file__).resolve().parents[1]


def handoff(baseline, *, name="Literal label", genus="Rubus", varieties=(), candidates=(), **overrides):
    return prepare_external_identity_lead(**{ "baselines": [baseline], "baseline_id": baseline["id"],
        "name": name, "genus": genus, "input_sha256": baseline["input_sha256"],
        "varieties": list(varieties), "candidates": list(candidates), **overrides})


@pytest.mark.parametrize("organism,berry", [
    ("Fragaria x ananassa", "berry-strawberry"), ("Fragaria vesca", "berry-strawberry"),
    ("Rubus idaeus", "berry-raspberry"), ("Rubus occidentalis", "berry-raspberry"),
    ("Rubus argutus", "berry-blackberry"), ("Rubus laciniatus", "berry-blackberry"),
    ("Rubus ulmifolius", "berry-blackberry"),
])
def test_checked_source_scope_creates_only_a_private_unreviewed_lead(tmp_path, organism, berry):
    baseline = analyze(tmp_path, [{"Unique Name": "PI 1", "Cultivar": "Literal label", "Organism": organism}], 1)
    original = deepcopy(baseline)
    candidate = handoff(baseline, genus=organism.split()[0])["candidate"]
    assert candidate["berry_id"] == berry and candidate["berry_ids"] == [berry]
    assert candidate["candidate_name"] == "Literal label" and candidate["status"] == "proposed"
    assert not candidate["human_gated"] and not candidate["auto_confirmed"]
    assert candidate["source_tier"] == "weak_noncanonical_lead" and not candidate["source_id"]
    assert not any(candidate[key] for key in ["aliases", "breeder_owner", "applicant", "deployment", "knowledge", "proposed_relationships"])
    assert not any(candidate["registration"].values())
    external = candidate["external_collection"]
    assert external["references"] == baseline["entries"][0]["references"]
    assert external["checked_on"] == "2026-10-07" and external["crop_scope"]["berry_id"] == berry
    if organism.startswith("Rubus"):
        assert external["crop_scope"]["checked_on"] == "2026-11-04"
        assert external["crop_scope"]["taxonomy"][0]["organism"] == organism
        assert external["crop_scope"]["taxonomy"][0]["url"].endswith("id=" + GDR_RUBUS_CROP_TAXA[organism][2])
    assert baseline == original


@pytest.mark.parametrize("organisms", [
    ["Rubus spp."], ["Rubus hybrid"], ["Rubus sp."], ["Rubus fruticosus"],
    ["Rubus crataegifolius"], ["Rubus neglectus"], ["Rubus trivialis"],
    ["Rubus idaeus", "Rubus hybrid"], ["Rubus idaeus", "Rubus argutus"],
    ["Rubus idaeus L."],  # Similar text is not the exact checked GDR label.
])
def test_unknown_or_mixed_taxonomy_never_infers_a_crop_from_a_familiar_name(tmp_path, organisms):
    baseline = analyze(tmp_path, [{"Unique Name": f"PI {i}", "Cultivar": "Bluecrop", "Organism": org}
                                  for i, org in enumerate(organisms)], len(organisms))
    original = deepcopy(baseline)
    assert not collection_crop_scope(baseline, baseline["entries"][0])["berry_id"]
    with pytest.raises(ValueError, match="crop needs checking"):
        handoff(baseline, name="Bluecrop")
    assert baseline == original


def test_all_references_must_agree_and_same_crop_species_can_coexist(tmp_path):
    baseline = analyze(tmp_path, [{"Unique Name": str(i), "Cultivar": "Literal label", "Organism": org}
        for i, org in enumerate(["Rubus idaeus", "Rubus occidentalis"])], 2)
    lead = handoff(baseline)["candidate"]
    assert lead["berry_id"] == "berry-raspberry" and len(lead["external_collection"]["crop_scope"]["taxonomy"]) == 2
    for refs in [[], [{**baseline["entries"][0]["references"][0], "organism": "Malus domestica"}]]:
        changed = deepcopy(baseline)
        changed["entries"][0]["references"] = refs
        assert not collection_crop_scope(changed, changed["entries"][0])["berry_id"]
        with pytest.raises(ValueError):
            handoff(changed)


def test_checked_taxa_separate_namesakes_but_unassigned_rubus_keeps_held_suggestions(tmp_path):
    baseline = analyze(tmp_path, [{"Unique Name": str(i), "Cultivar": name, "Organism": org}
        for i, (name, org) in enumerate([("Shared", "Rubus idaeus"), ("Unknown", "Rubus hybrid")])], 2)
    varieties = [{"id": f"{crop}-{name}", "name": name, "berry_ids": [f"berry-{crop}"]}
                 for crop in ["raspberry", "blackberry", "blueberry"] for name in ["Shared", "Unknown"]]
    reports = compare_baseline(baseline, varieties=varieties, candidates=[])["entries"]
    shared = next(row for row in reports if row["name"] == "Shared")
    unknown = next(row for row in reports if row["name"] == "Unknown")
    assert [row["id"] for row in shared["catalog_matches"]] == ["raspberry-Shared"]
    assert {row["id"] for row in unknown["catalog_matches"]} == {"raspberry-Unknown", "blackberry-Unknown"}
    assert not unknown["crop_scope"]["berry_id"]
    view = external_coverage_view(baselines=[baseline], varieties=varieties, candidates=[],
                                  filters={"external_status": "crop_scope_needed", "external_genus": "Rubus"})
    assert view["filtered_count"] == view["crop_scope_needed_count"] == 1
    assert view["entries"][0]["name"] == "Unknown" and view["entries"][0]["catalog_matches"]
    assert view["scope_counts"] == {"catalog_name_found": 2}  # Counts remain disjoint; crop holds are separate.


def test_genus_namesakes_have_distinct_stable_leads_and_no_implicit_genus(tmp_path):
    baseline = analyze(tmp_path, [{"Unique Name": str(i), "Cultivar": "Literal label", "Organism": org}
        for i, org in enumerate(["Fragaria vesca", "Rubus argutus"])], 2)
    strawberry, blackberry = [handoff(baseline, genus=genus)["candidate"] for genus in ["Fragaria", "Rubus"]]
    assert strawberry["id"] != blackberry["id"]
    assert [strawberry["berry_id"], blackberry["berry_id"]] == ["berry-strawberry", "berry-blackberry"]
    for genus in ["", "Vaccinium", "Unknown"]:
        with pytest.raises(ValueError):
            handoff(baseline, genus=genus)


@pytest.mark.parametrize("case", ["stale", "unknown_name", "unknown_source", "wrong_url", "wrong_reference", "duplicate"])
def test_stale_or_conflicting_inputs_fail_without_a_lead(tmp_path, case):
    baseline = analyze(tmp_path, [{"Unique Name": "PI 1", "Cultivar": "Literal label"}], 1)
    args = {}
    if case == "stale": args["input_sha256"] = "stale"
    elif case == "unknown_name": args["name"] = "Invented"
    elif case == "unknown_source": baseline["id"] = "unknown"
    elif case == "wrong_url": baseline["source_url"] = "https://wrong.example/"
    elif case == "wrong_reference": baseline["entries"][0]["references"][0]["organism"] = "Rubus idaeus x unknown"
    else: baseline["entries"].append(deepcopy(baseline["entries"][0]))
    original = deepcopy(baseline)
    with pytest.raises(ValueError):
        handoff(baseline, **args)
    assert baseline == original


def test_replay_preserves_renamed_rejected_and_rescoped_human_record_even_with_a_new_namesake(tmp_path):
    baseline = analyze(tmp_path, [{"Unique Name": "PI 1", "Cultivar": "Literal label"}], 1)
    candidate = handoff(baseline)["candidate"]
    candidate.update(candidate_name="User corrected", berry_id="berry-blackberry", status="rejected", human_gated=True,
                     review_notes="User decision", knowledge={"notes": "User edit"})
    others = [{"id": "another", "candidate_name": "Literal label", "berry_id": "berry-raspberry"}]
    original = deepcopy(candidate)
    plan = handoff(baseline, candidates=[*others, candidate])
    assert plan["candidate"] is None and plan["href"].endswith("#" + candidate["id"]) and "User+corrected" in plan["href"]
    assert candidate == original


def test_existing_names_redirect_without_choosing_between_multiple_identities(tmp_path):
    baseline = analyze(tmp_path, [{"Unique Name": "PI 1", "Cultivar": "Literal label"}], 1)
    varieties = [{"id": str(i), "name": "Literal label", "berry_ids": ["berry-raspberry"]} for i in range(2)]
    assert handoff(baseline, varieties=varieties[:1]) == {"candidate": None, "href": "/entities/variety/0"}
    result = handoff(baseline, varieties=varieties)
    assert result["candidate"] is None and result["href"].startswith("/varieties/coverage?")
    candidates = [{"id": str(i), "candidate_name": "Literal label", "berry_id": "berry-raspberry", "status": "rejected"} for i in range(2)]
    original = deepcopy(candidates)
    result = handoff(baseline, candidates=candidates)
    assert result["candidate"] is None and "berry=berry-raspberry" in result["href"] and "#" not in result["href"]
    assert candidates == original


def test_blueberry_existing_ids_and_edited_replay_remain_compatible(tmp_path):
    baseline = grin(tmp_path, [{"ACCESSION": "PI 1", "PLANT NAME": "Bluecrop"}])
    args = dict(baselines=[baseline], baseline_id=baseline["id"], name="Bluecrop", input_sha256=baseline["input_sha256"], varieties=[], candidates=[])
    old = prepare_blueberry_identity_lead(**args)
    for genus in ["", "Vaccinium"]:
        new = prepare_external_identity_lead(**args, genus=genus)
        without_stamp = lambda plan: {**plan, "candidate": {key: value for key, value in plan["candidate"].items() if key != "discovered_at"}}
        assert without_stamp(old) == without_stamp(new)
    seed = json.dumps([baseline["id"], "blueberry", "Bluecrop"], ensure_ascii=False, separators=(",", ":"))
    assert old["candidate"]["id"] == "vcand-" + hashlib.sha256(seed.encode()).hexdigest()[:12]
    for genus in ["Rubus", "Fragaria"]:
        with pytest.raises(ValueError): prepare_external_identity_lead(**args, genus=genus)
    baseline["source_url"] = "https://wrong.example/"
    with pytest.raises(ValueError): prepare_external_identity_lead(**args)


def test_newer_source_capture_does_not_rewrite_the_original_candidate_or_its_provenance(tmp_path):
    baseline = analyze(tmp_path, [{"Unique Name": "PI 1", "Cultivar": "Literal label"}], 1)
    retained = handoff(baseline)["candidate"]
    newer = deepcopy(baseline)
    newer.update(checked_on="2026-11-04", input_sha256="a" * 64)
    newer["entries"][0]["references"][0]["other_cultivar_labels"] = ["Conflicting label"]
    original = deepcopy(retained)
    replay = handoff(newer, candidates=[retained])
    assert replay["candidate"] is None and replay["href"].endswith("#" + retained["id"])
    assert retained == original and retained["external_collection"]["checked_on"] == "2026-10-07"


def test_real_capture_accounting_is_unchanged_and_every_hold_remains_visible():
    baselines = load_external_baselines(ROOT / "data")
    original = deepcopy(baselines)
    for baseline in baselines:
        result = compare_baseline(baseline, varieties=[], candidates=[])
        assert len(result["entries"]) == baseline["totals"]["genus_label_keys"]
        assert result["totals"] == baseline["totals"]
        assert [(row["name"], row["references"]) for row in result["entries"]] == [(row["name"], row["references"]) for row in baseline["entries"]]
    assert baselines == original
    for genus in ["Fragaria", "Rubus", "Vaccinium"]:
        view = external_coverage_view(baselines=baselines, varieties=[], candidates=[], filters={"external_genus": genus, "external_status": ""})
        assert view["filtered_count"] > 0
        assert any(row["crop_scope"]["berry_id"] for row in view["entries"])


def test_forms_keep_exact_genus_escape_source_text_and_never_offer_held_actions(tmp_path):
    baseline = analyze(tmp_path, [{"Unique Name": "PI 1", "Cultivar": '<script>Shared</script>'},
        {"Unique Name": "PI 2", "Cultivar": "Held", "Organism": "Rubus hybrid"}], 2)
    external = external_coverage_view(baselines=[baseline], varieties=[], candidates=[], filters={"external_status": ""})
    env = Environment(loader=FileSystemLoader(ROOT / "app/templates"), autoescape=select_autoescape())
    html = env.get_template("_variety_external_coverage.html").render(coverage={"external": external}, request=type("Request", (), {"query_params": {}})())
    assert '<script>Shared</script>' not in html and '&lt;script&gt;Shared&lt;/script&gt;' in html
    assert html.count('action="/varieties/external/identity-lead"') == 1
    assert 'name="genus" value="Rubus"' in html and 'Check crop in source' in html
    assert "crop checked 2026-11-04" in html and "Common Names" not in html


def test_post_is_additive_replay_preserves_bytes_and_requires_same_origin_and_authoring(monkeypatch, tmp_path):
    baseline = analyze(tmp_path, [{"Unique Name": "PI 1", "Cultivar": "Literal label", "Organism": "Rubus argutus"}], 1)
    import app.services.variety_external_coverage as coverage
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path / "inbox")
    monkeypatch.setattr(main, "AUTHORING_MODE", True)
    monkeypatch.setattr(coverage, "load_external_baselines", lambda data_dir: [baseline])
    monkeypatch.setattr(main, "variety_candidate_universe", lambda: ([], load_variety_candidates(main.INBOX_DIR), {}))
    client = TestClient(main.app)
    form = {"baseline_id": baseline["id"], "name": "Literal label", "genus": "Rubus", "input_sha256": baseline["input_sha256"]}
    for data, headers, status in [(form, {"origin": "https://wrong.example"}, 403), ({**form, "genus": ""}, {}, 422)]:
        assert client.post("/varieties/external/identity-lead", data=data, headers=headers, follow_redirects=False).status_code == status
        assert not list(main.INBOX_DIR.rglob("*.json"))
    first = client.post("/varieties/external/identity-lead", data=form, follow_redirects=False)
    assert first.status_code == 303
    files = list(main.INBOX_DIR.rglob("*.json")); assert len(files) == 1
    candidate = json.loads(files[0].read_bytes()); assert candidate["berry_id"] == "berry-blackberry"
    candidate.update(candidate_name="User correction", status="rejected", human_gated=True, review_notes="Keep")
    files[0].write_text(json.dumps(candidate), encoding="utf-8")
    before = files[0].read_bytes()
    again = client.post("/varieties/external/identity-lead", data=form, follow_redirects=False)
    assert again.status_code == 303 and files[0].read_bytes() == before
    assert len(list(main.INBOX_DIR.rglob("*.json"))) == 1
    monkeypatch.setattr(main, "AUTHORING_MODE", False)
    assert client.post("/varieties/external/identity-lead", data=form, follow_redirects=False).status_code == 403

