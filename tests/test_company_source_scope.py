"""Preserve canonical mention recall across company News, Map and Digest scope."""
from copy import deepcopy
from datetime import UTC, date, datetime

import pytest

from app.services import company_source_scope as scope, feed_first, news_workspace, personal_digest


ENTITIES = {
    "company-nursery": {"id": "company-nursery", "entity_type": "company", "name": "Heritage Nursery", "aliases": ["Heritage Berries"]},
    "company-other": {"id": "company-other", "entity_type": "company", "name": "Other Nursery"},
    "company-seed": {"id": "company-seed", "entity_type": "company", "name": "Provisional Nursery", "canonical": False},
}


def article(key="ev-mentioned", **changes):
    row = {"id": key, "title": "Heritage Berries announces blueberry nursery expansion", "summary": "More blueberry plants for growers.",
           "source_name": "Berry Journal", "source_url": "https://example.org/" + key, "source_type": "trade_press",
           "status": "published", "published_date": "2026-09-30", "berry_ids": ["berry-blueberry"], "entity_ids": []}
    return {**row, **changes}


def state():
    result = feed_first.empty_state()
    result["company_lists"] = {"list-nurseries": {"name": "Nurseries", "company_ids": ["company-nursery"]}}
    result["entity_favorites"] = {"company-nursery": True}
    result["entity_tiers"] = {"company-nursery": "tier1"}
    return result


def news(rows, params, personal=None, facts=None):
    return news_workspace.model(records={r["id"]: r for r in rows}, entities=ENTITIES,
        relationships=[], facts=facts or [], state=personal or state(), params=params,
        now=datetime(2026, 10, 1, tzinfo=UTC))


@pytest.mark.parametrize("filters", [{"company": "company-nursery"}, {"list": "list-nurseries"},
                                    {"tier": "tier1"}, {"favorites": "1"}])
def test_scoped_news_recalls_original_reviewed_alias_without_rewriting(filters):
    row = article(article={"paragraphs": [{"text": "PRIVATE BODY"}]}, transcript="PRIVATE TRANSCRIPT")
    original, personal = deepcopy(row), state()
    previous = deepcopy(personal)
    model = news([row], filters, personal)
    assert model["matching_ids"] == [row["id"]]
    card = model["cards"][0]
    assert card["company_mentions"] == [{"id": "company-nursery", "name": "Heritage Nursery", "alias": "Heritage Berries", "field": "title"}]
    assert card["entities"] == [] and card["source_reviewed"] and not card["trusted"]
    assert "PRIVATE BODY" not in str(model) and "PRIVATE TRANSCRIPT" not in str(model)
    assert row == original and personal == previous


@pytest.mark.parametrize("changes", [{"status": "in_review"}, {"live": True}, {"trust_state": "LIVE"}, {"submitted_by": "auto"}])
def test_unreviewed_name_only_does_not_receive_company_association(changes):
    assert news([article(**changes)], {"company": "company-nursery"})["matching"] == 0
    # Existing explicit associations remain available in the raw lane.
    assert news([article(entity_ids=["company-nursery"], **changes)], {"company": "company-nursery"})["matching"] == 1


def test_direct_links_deduplicate_mentions_and_trusted_still_requires_active_statement():
    row = article(entity_ids=["company-nursery"])
    assert news([row], {"company": "company-nursery"})["cards"][0]["company_mentions"] == []
    recalled = article()
    assert news([recalled], {"company": "company-nursery", "view": "trusted"})["matching"] == 0
    model = news([recalled], {"company": "company-nursery", "view": "trusted"},
                 facts=[{"id": "fact-original", "status": "active", "evidence_ids": [recalled["id"]]}])
    assert model["matching"] == 1 and model["cards"][0]["trusted"]
    assert recalled["entity_ids"] == []


def test_recalled_news_keeps_newest_first_and_real_date_crop_scope():
    rows = [article("ev-old", published_date="2026-08-01"), article("ev-new"),
            article("ev-other-crop", berry_ids=["berry-strawberry"])]
    assert news(rows[:2], {"company": "company-nursery"})["matching_ids"] == ["ev-new", "ev-old"]
    assert news(rows, {"company": "company-nursery", "window": "7d", "berry": "blueberry"})["matching_ids"] == ["ev-new"]


def test_provisional_subjects_short_aliases_and_body_only_mentions_are_not_resolved():
    assert news([article(title="Provisional Nursery expands blueberry production")], {"company": "company-seed"})["matching"] == 0
    linked, mentions = scope.links(article(title="Blueberry programme", summary="", article={"body": "Heritage Berries"}), list(ENTITIES.values()))
    assert linked == set() and mentions == []
    assert scope.links(article(title="AB blueberry nursery expansion"), [{"id": "company-ab", "entity_type": "company", "name": "AB"}]) == (set(), [])


def test_digest_only_explicit_subscription_admits_older_reviewed_mentions():
    row, personal = article(), state()
    original = deepcopy(row)
    def build():
        return personal_digest.digest_model(records={row["id"]: row}, entities=ENTITIES, state=personal,
            reading={"reading": {}}, params={"list": "list-nurseries", "favorites": "1", "tier": "tier1"}, today=date(2026, 10, 1))
    assert build()["matching"] == 0
    personal["digest_subscriptions"] = ["list-nurseries"]
    snapshot = deepcopy(personal)
    model = build()
    assert model["matching"] == 1
    assert model["cards"][0]["origins"] == [{"key": "list-nurseries", "label": "Nurseries"}]
    assert model["cards"][0]["company_mentions"][0]["alias"] == "Heritage Berries"
    assert row == original and personal == snapshot
    row["status"] = "in_review"
    assert build()["matching"] == 0
    personal["company_lists"]["list-nurseries"]["archived"] = True
    assert scope.candidates(ENTITIES, personal, {"list": "list-nurseries"}, subscribed=True) == []


def test_real_canonical_news_recalls_sanlucar_without_changing_source_records():
    import json
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    company = json.loads((root / "data/entities/companies/company-sanlucar.json").read_text(encoding="utf-8"))
    files = {path: path.read_bytes() for path in (root / "data/evidence").glob("*.json")}
    records = {row["id"]: row for raw in files.values() if (row := json.loads(raw)).get("status") == "published"}
    model = news_workspace.model(records=records, entities={company["id"]: company}, relationships=[], facts=[],
        state=feed_first.empty_state(), params={"company": company["id"]}, now=datetime(2026, 10, 5, tzinfo=UTC))
    assert any(card["company_mentions"] for card in model["cards"])
    assert all(path.read_bytes() == raw for path, raw in files.items())


@pytest.mark.parametrize("changes", [{"live": True}, {"trust_state": "LIVE"}, {"submitted_by": "auto"}])
def test_saved_live_or_automatic_source_is_not_labeled_reviewed_in_digest(changes):
    row, personal = article(**changes), state()
    personal["decisions"][row["id"]] = {"saved": True}
    model = personal_digest.digest_model(records={row["id"]: row}, entities=ENTITIES,
        state=personal, reading={"reading": {}}, params={}, today=date(2026, 10, 1))
    assert model["matching"] == 1 and model["cards"][0]["origins"] == [{"key": "saved", "label": "Saved by you"}]
    assert not model["cards"][0]["trusted"]
