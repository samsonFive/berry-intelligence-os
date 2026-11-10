import json
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

from app.services.global_berry_coverage import BASELINE, CROPS, FOLLOWUPS, REGIONS, ROLES, public_coverage

DATA = Path(__file__).resolve().parents[1] / "data"


def test_public_baseline_covers_every_crop_and_macroregion_with_explicit_gaps():
    baseline = public_coverage(DATA)
    assert len(baseline["cells"]) == len(CROPS) * len(REGIONS) * len(ROLES)
    assert {(row["crop"], row["region"]) for row in baseline["observations"]} == {
        (crop, region) for crop in CROPS for region in REGIONS
    }
    assert all(baseline["counts"].values())
    for cell in baseline["cells"]:
        assert cell["next_source"].startswith("https://")
        assert cell["next_step"]
        assert bool(cell["actors"]) == (cell["state"] == "evidenced")


def test_public_observations_trace_to_original_sources_and_existing_ids():
    baseline = public_coverage(DATA)
    observation_ids = set()
    entity_ids = {path.stem for path in (DATA / "entities").glob("*/*.json")}
    for row in baseline["observations"]:
        assert row["id"] not in observation_ids
        observation_ids.add(row["id"])
        assert urlsplit(row["source_url"]).scheme == "https"
        assert row["source_name"]
        assert date.fromisoformat(row["verification_date"]) <= date.fromisoformat(baseline["as_of"])
        if row["source_date"]:
            assert date.fromisoformat(row["source_date"]) <= date.fromisoformat(row["verification_date"])
        if row["entity_id"]:
            assert row["entity_id"] in entity_ids
        if metric := row.get("metric"):
            assert metric["units"] and metric["scope"] and metric["qualifier"]


def test_filter_retains_searched_gap_with_followup_and_does_not_invent_evidence(tmp_path):
    missing_baseline = public_coverage(tmp_path, crop="blackberry", region="mea", role="rights")
    assert missing_baseline["cells"][0]["state"] == "unresearched"
    baseline_path = tmp_path / BASELINE
    baseline_path.parent.mkdir(parents=True)
    baseline_path.write_bytes((DATA / BASELINE).read_bytes())
    for region in ("mea", "latin-america", "asia-pacific"):
        selected = public_coverage(tmp_path, crop="blackberry", region=region, role="rights")
        assert selected["observations"] == []
        assert len(selected["cells"]) == 1
        cell = selected["cells"][0]
        assert cell["state"] == "searched_gap"
        assert cell["latest_dated_evidence"] is None


def test_checked_milestones_distinguish_registry_stages_and_source_dates():
    japanese = public_coverage(DATA, crop="strawberry", region="asia-pacific", role="rights")
    assert [(row["stage"], row["identifier"], row["date"]) for row in japanese["milestones"]] == [
        ("Registered denomination", "25605", "2017-02-08"),
        ("Application published", "28844", "2014-07-14"),
        ("Application filed", "28844", "2014-01-10"),
    ]
    raspberry = public_coverage(DATA, crop="raspberry", region="north-america")
    assert [(row["kind"], row["date_label"], row["date"]) for row in raspberry["milestones"]] == [
        ("ip", "Grant issued", "2026-08-18"),
        ("commercial", "Source published", "2026-05-20"),
    ]


def test_followups_extend_existing_coverage_and_respect_crop_region_and_role(tmp_path):
    baseline_bytes = (DATA / BASELINE).read_bytes()
    baseline_path = tmp_path / BASELINE
    baseline_path.parent.mkdir(parents=True)
    baseline_path.write_bytes(baseline_bytes)
    base = public_coverage(tmp_path)
    followup_bytes = (DATA / FOLLOWUPS).read_bytes()
    (tmp_path / FOLLOWUPS).write_bytes(followup_bytes)
    followups = json.loads(followup_bytes)
    extended = public_coverage(tmp_path)
    assert baseline_path.read_bytes() == baseline_bytes
    assert extended["observations"] == base["observations"] + followups["observations"]
    assert len(extended["milestones"]) == len(base["milestones"]) + len(followups["milestones"])

    morocco = public_coverage(tmp_path, crop="blueberry", region="mea", role="rights")
    observed = next(row for row in morocco["milestones"] if row["identifier"] == "FC13-122")
    assert observed["date_label"] == "Register snapshot as of"
    assert observed["date"] == "2026-06-22"
    assert observed["sources"][0]["published_date"] is None

    south_africa = public_coverage(tmp_path, crop="strawberry", region="mea", role="rights")
    assert south_africa["observations"][0]["entity_id"] is None
    assert south_africa["milestones"][0]["date"] == ""

    japan = public_coverage(tmp_path, crop="strawberry", region="asia-pacific", role="propagation")
    suppliers = [row for row in japan["observations"] if row["country"] == "Japan"]
    assert len(suppliers) == 3
    assert all(row["entity_id"] is None for row in suppliers)
    assert {row["kind"] for row in japan["milestones"]} == {"licensing"}

    italy = public_coverage(tmp_path, crop="raspberry", region="europe", role="propagation")
    qvi = next(row for row in italy["milestones"] if row["id"] == "italy-masaf-easyrose-qvi-25a06708")
    assert qvi["kind"] == "regulatory"
    assert qvi["date"] == qvi["sources"][0]["published_date"] == "2025-12-18"
    assert qvi not in public_coverage(tmp_path, crop="raspberry", region="europe", role="rights")["milestones"]

    argentina = public_coverage(tmp_path, crop="strawberry", region="latin-america", role="propagation")
    nursery_rows = [row for row in argentina["observations"] if row["country"] == "Argentina"]
    assert {row["entity_name"] for row in nursery_rows} == {"Kleppe S.A.", "Vivero Altus"}
    assert all(row["entity_id"] is None for row in nursery_rows)
    assert argentina["milestones"][0]["date"] == "2026-02-18"

    northern_europe = public_coverage(tmp_path, crop="strawberry", region="europe", role="marketing")
    bayer = next(row for row in northern_europe["milestones"] if row["identifier"] == "EM2836")
    assert bayer["places"] == ["United Kingdom", "Germany", "Benelux"]
    assert bayer["date_label"] == "Announced"

    european_rights = public_coverage(tmp_path, crop="strawberry", region="europe", role="rights")
    dalicia = next(row for row in european_rights["milestones"] if row["id"] == "cpvo-dalicia-grant-69689-2025-06-02")
    assert dalicia["places"] == ["European Union"]
    assert dalicia["date"] == "2025-06-02"
    assert dalicia["sources"][0]["published_date"] == "2025-08-15"

    blackberry = public_coverage(tmp_path, crop="blackberry", region="europe", role="propagation")
    acquisition = next(row for row in blackberry["milestones"] if row["kind"] == "ownership")
    assert acquisition["date"] == "2026-06-10"
    assert acquisition["date_label"] == "Company release dated"
    assert acquisition["existing_evidence_id"] == "ev-20260806173541-de69-fall-creek-acquires-berryplant-berrytech"
    raspberry = public_coverage(tmp_path, crop="raspberry", region="europe", role="propagation")
    easy_rose = next(row for row in raspberry["milestones"] if row["kind"] == "licensing")
    assert easy_rose["date"] == "2026-10-01"
    assert easy_rose["jurisdiction"] == ""
    assert easy_rose not in blackberry["milestones"]

    growing = public_coverage(tmp_path, crop="blackberry", region="asia-pacific", role="growing")
    youwei = next(row for row in growing["observations"] if row["id"] == "bk-ap-jiangsu-youwei-blackberry-growing")
    assert youwei["entity_id"] is None
    assert youwei["source_date"] == "2025-06-27"
    assert youwei["metric"]["value"] == 1000
    assert youwei["metric"]["qualifier"].startswith("Strict lower bound")

    rights = public_coverage(tmp_path, crop="blackberry", region="asia-pacific", role="rights")
    baima = next(row for row in rights["milestones"] if row["id"] == "cnipa-baima-blackberry-gi-640-2025-07-16")
    assert baima["kind"] == "regulatory"
    assert baima["date"] == "2025-07-16"
    assert baima["sources"][0]["published_date"] == "2025-08-13"
    assert baima not in growing["milestones"]

    blueberry = public_coverage(tmp_path, crop="blueberry", region="north-america", role="rights")
    patent = next(row for row in blueberry["milestones"] if row["id"] == "uspto-fall-creek-fce18-015-pp37387-2026-04-28")
    patent_observation = next(row for row in blueberry["observations"] if row["id"] == "bl-na-fall-creek-fce18-015-us-plant-patent")
    assert patent["date_label"] == "Grant issued"
    assert patent["date"] == patent_observation["source_date"] == "2026-04-28"
    assert patent["identifier"] == "PP37,387 P3 · Application 19/063,460"
    assert patent["entity_ids"] == [patent_observation["entity_id"]] == ["company-fall-creek-farm-and-nursery"]
    assert patent["places"] == ["United States"]
    assert patent["jurisdiction"] == "US"
    assert patent not in rights["milestones"]

    blackberry_rights = public_coverage(tmp_path, crop="blackberry", region="north-america", role="rights")
    agv = next(row for row in blackberry_rights["milestones"] if row["kind"] == "ip")
    assert agv["id"] == "uspto-pp37457-agv-22-blackberry-grant-2026-06-09"
    assert agv["date"] == agv["sources"][0]["published_date"] == "2026-06-09"
    assert agv["jurisdiction"] == "US"
    assert agv["entity_ids"] == []

    raspberry_rights = public_coverage(tmp_path, crop="raspberry", region="north-america", role="rights")
    crimson = next(row for row in raspberry_rights["milestones"] if row["kind"] == "ip")
    assert crimson["id"] == "uspto-pp37595-crimson-beauty-raspberry-grant-2026-08-18"
    assert crimson["date"] == crimson["sources"][0]["published_date"] == "2026-08-18"
    assert crimson["jurisdiction"] == "US"
    assert crimson["entity_ids"] == ["variety-crimson-beauty-ee9138c1", "breeding_program-cornell-berry"]


def test_blackberry_rights_checks_resolve_regional_gaps_and_keep_legal_stages_separate():
    checks = (
        ("latin-america", "Mexico", None, "2025-10-06", [
            ("MX", "Transfer registered", "2025-08-06"),
            ("MX", "Title issued", "2024-08-23"),
        ]),
        ("mea", "Morocco", "company-driscolls", None, [
            ("MA", "Register snapshot as of", "2026-06-22"),
        ]),
        ("asia-pacific", "Australia", "company-driscolls", "2025-12-10", [
            ("AU", "Grant issued", "2025-11-19"),
        ]),
    )
    for region, country, entity_id, source_date, stages in checks:
        coverage = public_coverage(DATA, crop="blackberry", region=region, role="rights")
        assert coverage["counts"] == {"evidenced": 1, "searched_gap": 0, "unresearched": 0}
        assert [(row["country"], row["entity_id"], row["source_date"]) for row in coverage["observations"]] == [
            (country, entity_id, source_date),
        ]
        milestones = [row for row in coverage["milestones"] if row["kind"] == "ip"]
        assert [(row["jurisdiction"], row["date_label"], row["date"]) for row in milestones] == stages
        assert all(row["sources"][0]["published_date"] == source_date for row in milestones)


def test_cpvo_blueberry_grants_have_individual_certificates_and_applications():
    europe = public_coverage(DATA, crop="blueberry", region="europe", role="rights")
    observation = next(row for row in europe["observations"] if row["id"] == "bl-eu-fv-blueberry-cpvo-grants")
    assert observation["entity_name"] == "FV B.V."
    assert observation["entity_id"] is None
    assert europe["cells"][0]["state"] == "evidenced"

    grants = sorted((row for row in europe["milestones"] if row["id"].startswith("cpvo-fv190")),
                    key=lambda row: row["id"])
    assert [row["identifier"] for row in grants] == [
        "71461 · Application 2020/0959",
        "71462 · Application 2020/0960",
        "71463 · Application 2020/0961",
        "71464 · Application 2020/0962",
        "71465 · Application 2020/0963",
        "71466 · Application 2020/0964",
        "71467 · Application 2020/0965",
        "71468 · Application 2021/0121",
    ]
    for index, grant in enumerate(grants, start=1):
        assert f"FV190{index}" in grant["title"]
        assert grant["kind"] == "ip"
        assert grant["date"] == "2026-02-16"
        assert grant["jurisdiction"] == "EU"
        assert grant["entity_ids"] == []
        assert grant["sources"][0]["published_date"] == "2026-04-15"
