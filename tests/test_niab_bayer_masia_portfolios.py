"""Bounded source histories must not collapse breeding, branding and ownership."""
from copy import deepcopy
from pathlib import Path

from fastapi.testclient import TestClient

from app import main
from app.services import variety_photos as photos
from app.services.company_variety_discoveries import company_variety_discoveries
from app.services.variety_portfolio_coverage import load_portfolio_observations, reconcile_portfolios

DATA = Path(__file__).resolve().parents[1] / "data"
PREFIXES = ("portfolio-masia-", "portfolio-niab-", "portfolio-bayer-", "portfolio-g-berries-")


def sources():
    return [row for row in load_portfolio_observations(DATA) if row["id"].startswith(PREFIXES)]


def reconcile(candidates=()):
    return reconcile_portfolios(sources=sources(), varieties=[], entities=[], candidates=list(candidates))


def test_repeated_propagators_and_crop_headings_do_not_create_identities():
    observed = sources()
    before = deepcopy(observed)
    rows, candidates = reconcile()
    assert len(rows) == 12 and sum(len(row["names"]) for row in rows) == 44
    assert len(candidates) == 31
    table = next(row for row in rows if row["id"] == "portfolio-niab-legacy-strawberry-table")
    assert len(table["names"]) == 10 and table["capture_reference"]["propagator_rows"] == 56
    assert table["capture_reference"]["repeated_variety_rows"] == 46
    crops = next(row for row in rows if row["id"] == "portfolio-masia-other-berry-crop-headings")
    assert not crops["names"] and len(crops["accounting_view"]["exclusions"]) == 3
    assert all(not row["accounting_view"]["issues"] for row in rows)
    assert not {"Arándanos", "Frambuesas", "Moras", "STR14", "Kweli", "Imara"} & {row["candidate_name"] for row in candidates}
    assert observed == before


def test_company_context_keeps_transferred_strawberries_separate_from_raspberries():
    rows, _ = reconcile()
    bayer = company_variety_discoveries(entity_id="company-bayer", sources=rows)
    niab = company_variety_discoveries(entity_id="company-niab", sources=rows)
    assert len(bayer["rows"]) == 7 and len(niab["rows"]) == 23
    assert all(row["berry_id"] == "berry-strawberry" for row in bayer["rows"])
    assert not {"Alice", "Florence", "Malling Bella", "Malling Charm"} & {row["name"] for row in bayer["rows"]}
    centenary = next(row for row in bayer["rows"] if row["name"] == "Malling Centenary")
    assert len(centenary["sources"]) == 2 and not centenary["code"]
    assert any("Historical breeding" in note for note in centenary["notes"])
    bella = next(row for row in niab["rows"] if row["name"] == "Malling™ Bella®")
    assert any("trademark" in note for note in bella["notes"])


def test_conditional_baya_code_survives_later_reference_without_registry_promotion():
    rows, candidates = reconcile()
    index = next(row for row in rows if row["id"] == "portfolio-bayer-uk-strawberry-index")
    assert all(not name.get("breeder_code") for name in index["names"])
    release = next(row for row in rows if row["id"] == "portfolio-bayer-baya-solara-release")
    assert release["published_date"] == "2026-01-05"
    assert release["names"][0]["breeder_code"] == "EM2836"
    baya = next(row for row in candidates if row["candidate_name"] == "Baya Solara")
    assert not baya["aliases"] and not baya["proposed_relationships"]
    assert not baya["registration"]["official_registry_source"] and not baya["registration"]["status"]
    company = company_variety_discoveries(entity_id="company-bayer", sources=rows)
    displayed = next(row for row in company["rows"] if row["name"] == "Baya Solara")
    assert displayed["code"] == "EM2836" and len(displayed["sources"]) == 2
    assert any("Subject to approval" in note for note in displayed["notes"])


def test_historical_names_and_partial_capture_remain_honest():
    rows, candidates = reconcile()
    historical = next(row for row in rows if row["id"] == "portfolio-masia-2019-strawberry-release")
    assert historical["published_date"] == "2019-02-26"
    assert any(row["candidate_name"] == "Selene" for row in historical["names"])
    current = next(row for row in rows if row["id"] == "portfolio-masia-current-strawberries")
    assert not current.get("published_date") and not any(row["candidate_name"] == "Selene" for row in current["names"])
    assert not any(row["candidate_name"] == "Leya" for row in candidates)
    pdf = next(row for row in rows if row["id"] == "portfolio-niab-bella-technical-text")
    assert pdf["needs_follow_up"] and pdf["capture_reference"]["pages_visually_checked"] == 0
    failed = next(row for row in rows if row["id"] == "portfolio-g-berries-retrieval-gap")
    # A later original-browser recovery supersedes the active failed capture;
    # the historical timeout remains in the dated original manifest.
    assert failed["needs_follow_up"] and failed["capture_status"] == "partial" and not failed["names"]
    assert failed["capture_reference"]["body_read"] and "timeout recovered" in failed["limitations"]
    assert not pdf.get("published_date")


def test_exact_photos_remain_held_and_shared_asset_is_withheld():
    _, candidates = reconcile()
    held = [photo for candidate in candidates for photo in photos.source_photos(candidate, candidate=True)]
    assert len(held) == 5
    assert {photo["named_variety"] for photo in held} == {"Leticia", "Leyre", "Shyra", "Chelsea", "Malling Bella"}
    assert all(photo["reuse"] == "unknown" and not photo["license_url"] for photo in held)
    assert not any("palmeritas@2x" in photo["image_url"] for photo in held)
    assert all("Photographer not credited" in photo["credit"] for photo in held)
    assert all(not photos.gallery(candidate, sourced=photos.source_photos(candidate, candidate=True), authoring=False) for candidate in candidates)


def test_new_sources_preserve_human_rejection_and_user_notes():
    human = {"id":"human-selene", "candidate_name":"Selene", "berry_id":"berry-strawberry",
             "status":"rejected", "identity_state":"rejected", "human_gated":True,
             "review_notes":"Keep the prior decision", "knowledge":{"notes":"User edit"}, "photos":[{"user_edit":"retained"}]}
    before = deepcopy(human)
    rows, candidates = reconcile([human])
    saved = next(row for row in candidates if row["id"] == human["id"])
    assert saved["status"] == "rejected" and saved["human_gated"]
    assert saved["review_notes"] == human["review_notes"] and saved["knowledge"] == human["knowledge"]
    assert saved["photos"] == human["photos"] and human == before
    company = company_variety_discoveries(entity_id="company-masia-ciscar", sources=rows)
    assert not any(row["name"] == "Selene" for row in company["rows"])


def test_private_preview_has_no_eager_photo_load_writes_or_public_override(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path)
    monkeypatch.setattr(main, "AUTHORING_MODE", True)
    client = TestClient(main.app)
    page = client.get("/varieties/candidates", params={"q":"Leyre", "source":"portfolio-masia-current-strawberries"})
    image = "https://www.masiaciscar.es/wp-content/uploads/2025/07/masia_freson_leyre@2x.webp"
    assert page.status_code == 200 and "Ignore permission" in page.text and "Permission unconfirmed" in page.text
    assert 'data-image-url="'+image+'"' in page.text and 'src="'+image+'"' not in page.text
    monkeypatch.setattr(main, "AUTHORING_MODE", False)
    public = client.get("/varieties/candidates", params={"q":"Leyre"})
    assert image not in public.text and "Ignore permission" not in public.text
    assert not list(tmp_path.rglob("*.json"))
