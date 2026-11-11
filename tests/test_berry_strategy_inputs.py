"""Private input approval, snapshot freshness and company-framework boundaries."""

from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest

from app.services import berry_strategy_inputs as inputs, berry_strategy_review as strategy, living_workspaces as living


@pytest.fixture
def entities():
    return {"company-fixture": {"id": "company-fixture", "entity_type": "company", "name": "Fixture Nursery"},
            "retailer-fixture": {"id": "retailer-fixture", "entity_type": "retailer", "name": "Fixture Retailer"},
            "variety-fixture": {"id": "variety-fixture", "entity_type": "variety", "name": "Fixture Berry"}}


@pytest.fixture
def payload():
    return {"entity_id": "company-fixture", "crop": "raspberry", "region": "europe", "title": "Private trial capability",
            "statement": "Private capability sentinel", "category": "capability", "reference": "Private reference sentinel",
            "observed_date": "2026-10-31", "source_url": "https://example.org/public-context",
            "vrio": {"valuable": {"judgment": "yes", "rationale": "Private rationale sentinel"}}}


@pytest.fixture
def store(tmp_path):
    return living.Store(tmp_path)


def approved(store, payload, entities, *, token="fixture-create"):
    draft = inputs.save_input(store, payload, "Analyst", entities, token=token)
    return inputs.decide_input(store, draft["id"], "Reviewer", entities, draft["version"], "approve", token=token + "-approve")


def snapshot(store, *, crop="raspberry", region="europe", focal="company-fixture", opportunities=()):
    model = {"filters": {"crop": crop, "region": region}, "coverage": {"observations": [{
        "id": "public-fixture", "title": "Public trial notice", "source_url": "https://example.org/notice",
        "summary": "A supplier described a trial window.", "source_date": "2026-10-01", "crop": crop, "region": region,
    }]}}
    return strategy.snapshot_for(model, opportunities=opportunities,
                                 analyst_inputs=inputs.scoped_inputs(store, model["filters"]), focal=focal)


def test_input_versions_retry_and_edit_revoke_approval(store, payload, entities):
    draft = inputs.save_input(store, payload, "Analyst", entities, token="create-retry")
    assert inputs.save_input(store, payload, "Analyst", entities, token="create-retry") == draft
    assert draft["state"] == "draft" and not inputs.scoped_inputs(store, {})
    assert set(draft["vrio"]) == set(inputs.VRIO_FIELDS)
    with pytest.raises(living.Conflict):
        inputs.save_input(store, {**payload, "title": "Different"}, "Analyst", entities, token="create-retry")
    with pytest.raises(living.Conflict):
        inputs.save_input(store, payload, "Other analyst", entities, token="create-retry")
    decision = inputs.decide_input(store, draft["id"], "Reviewer", entities, 1, "approve", token="approve-retry")
    assert decision["state"] == "approved" and decision["approved_by"] == "Reviewer"
    assert inputs.decide_input(store, draft["id"], "Reviewer", entities, 1, "approve", token="approve-retry") == decision
    changed = inputs.save_input(store, {**decision, "statement": "Corrected internal observation"}, "Analyst", entities,
                                expected=2, token="edit-retry-token")
    assert changed["id"] == draft["id"] and changed["version"] == 3 and changed["state"] == "draft"
    assert "approved_at" not in changed and "approved_by" not in changed
    assert changed["created_at"] == draft["created_at"] and changed["created_by"] == "Analyst"
    assert not inputs.scoped_inputs(store, {})
    assert [row["version"] for row in store.history(draft["id"])] == [3, 2, 1]


def test_withdrawal_keeps_history_and_requires_new_draft(store, payload, entities):
    row = approved(store, payload, entities)
    removed = inputs.decide_input(store, row["id"], "Reviewer", entities, 2, "withdraw", token="withdraw-retry")
    assert removed["state"] == "withdrawn" and not inputs.scoped_inputs(store, {})
    assert inputs.decide_input(store, row["id"], "Reviewer", entities, 2, "withdraw", token="withdraw-retry") == removed
    with pytest.raises(living.Conflict):
        inputs.save_input(store, row, "Analyst", entities, expected=2, token="stale-edit-token")
    with pytest.raises(ValueError, match="Save a draft"):
        inputs.decide_input(store, row["id"], "Reviewer", entities, 3, "approve", token="withdrawn-approve")
    restored = inputs.save_input(store, removed, "Analyst", entities, expected=3, token="restore-input-token")
    assert restored["state"] == "draft" and "withdrawn_at" not in restored


@pytest.mark.parametrize("change", [
    {"entity_id": "missing"}, {"entity_id": "variety-fixture"}, {"crop": "cranberry"}, {"region": "unknown"},
    {"category": "advantage"}, {"title": ""}, {"statement": ""}, {"reference": ""}, {"observed_date": "2026-02-30"},
    {"observed_date": "20261031"}, {"source_url": "file:///private"}, {"source_url": "https://user:pass@example.org/"},
    {"vrio": {"rare": {"judgment": "yes", "rationale": ""}}}, {"vrio": {"valuable": {"judgment": "certain"}}},
])
def test_input_validation_fails_before_writes(store, payload, entities, change):
    with pytest.raises(ValueError):
        inputs.save_input(store, {**payload, **change}, "Analyst", entities, token="invalid-input-token")
    assert not store.rows(inputs.KIND)


def test_approval_revalidates_allowed_entity_and_full_content(store, payload, entities):
    draft = inputs.save_input(store, payload, "Analyst", entities, token="validation-draft")
    with pytest.raises(ValueError, match="existing company"):
        inputs.decide_input(store, draft["id"], "Reviewer", {}, 1, "approve", token="removed-entity-token")
    with store.transaction() as db:
        malformed = store.put(db, inputs.KIND, {**draft, "reference": ""}, "Imported legacy draft", expected=1)
    with pytest.raises(ValueError, match="Reference is required"):
        inputs.decide_input(store, draft["id"], "Reviewer", entities, malformed["version"], "approve", token="missing-ref-token")


def test_inputs_follow_entity_crop_and_region_scope(store, payload, entities):
    specific = approved(store, payload, entities)
    broad = approved(store, {**payload, "crop": "", "region": ""}, entities, token="broad-create")
    other = approved(store, {**payload, "entity_id": "retailer-fixture", "crop": "blueberry", "region": "asia-pacific"},
                     entities, token="other-create")
    assert len(inputs.scoped_inputs(store, {})) == 3
    assert {row["id"] for row in inputs.scoped_inputs(store, {"crop": "raspberry", "region": "europe"})} == {specific["id"], broad["id"]}
    assert [row["id"] for row in inputs.scoped_inputs(store, {"crop": "raspberry", "region": "asia-pacific"})] == [broad["id"]]
    assert [row["id"] for row in inputs.scoped_inputs(store, {}, ["retailer-fixture"])] == [other["id"]]
    assert not inputs.scoped_inputs(store, {}, [])
    assert len(snapshot(store)["analyst_inputs"]) == 2
    assert "analyst_inputs" not in snapshot(store, focal="")
    assert not strategy.prepare(snapshot(store, focal=""))["frameworks"]["vrio"]["entries"]


@pytest.mark.parametrize("scope, included", [
    ({"start": "2026-10-31", "end": "2026-10-31"}, True), ({"start": "2026-11-01"}, False),
    ({"end": "2026-10-30"}, False), ({"q": "CAPABILITY SENTINEL"}, True), ({"q": "unmatched"}, False),
    ({"event_type": "ownership"}, False), ({"role": "propagation"}, False),
])
def test_input_date_search_and_record_type_filters_are_shared_by_snapshot(store, payload, entities, scope, included):
    row = approved(store, payload, entities)
    selected = inputs.scoped_inputs(store, scope)
    assert bool(selected) is included
    basis = strategy.snapshot_for({"filters": scope, "coverage": {}}, analyst_inputs=[row], focal="company-fixture")
    assert bool(basis.get("analyst_inputs")) is included
    review = strategy.prepare(basis, focal="company-fixture")
    strategy.save_draft(store, review, "Analyst", 0)


def test_concurrent_create_retry_and_conflicting_edits_are_atomic(store, payload, entities):
    with ThreadPoolExecutor(max_workers=2) as pool:
        rows = list(pool.map(lambda _: inputs.save_input(store, payload, "Analyst", entities, token="parallel-create"), range(2)))
    assert rows[0] == rows[1] and len(store.rows(inputs.KIND)) == 1
    assert len(store.history(rows[0]["id"])) == 1

    def edit(number):
        try:
            return inputs.save_input(store, {**payload, "id": rows[0]["id"], "title": f"Edit {number}"}, "Analyst", entities,
                                     expected=1, token=f"parallel-edit-{number}")
        except living.Conflict:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(edit, range(2)))
    assert sum(row is not None for row in results) == 1 and len(store.history(rows[0]["id"])) == 2


def test_private_inputs_fill_local_frameworks_but_never_enter_model(store, payload, entities):
    row = approved(store, payload, entities)
    basis = snapshot(store)
    assert basis["sources"][row["id"]]["record_href"].endswith("?version=2")
    assert basis["sources"][row["id"]]["public_for_model"] is False

    def completion(prompt, **kwargs):
        for private in (row["id"], "Private capability sentinel", "Private reference sentinel", "Private rationale sentinel",
                        "company-fixture", "https://example.org/public-context"):
            assert private not in prompt
        return SimpleNamespace(provider="fixture", model="fixture", parsed={"assessments": [{
            "framework": "porter", "text": "Check commercial access.", "limits": "Terms require confirmation.",
            "source_ids": ["public-fixture"], "contrary_ids": [], "confidence": "Low",
        }]})

    review = strategy.prepare(basis, focal="company-fixture", completer=completion)
    assert review["method"].startswith("Public-source model draft")
    vrio = review["frameworks"]["vrio"]["entries"]
    assert len(vrio) == 1 and vrio[0]["source_ids"] == [row["id"]]
    assert vrio[0]["vrio"]["valuable"]["rationale"] == "Private rationale sentinel"
    assert vrio[0]["vrio"]["rare"]["judgment"] == "unknown" and vrio[0]["text"] == row["statement"]
    assert review["frameworks"]["swot_tows"]["entries"][0]["kind"] == "Approved analyst input"
    assert "Internal capability recorded" in review["frameworks"]["swot_tows"]["entries"][0]["text"]
    assert all("Private capability sentinel" not in entry["text"] for entry in review["frameworks"]["value_chain"]["entries"])
    with pytest.raises(ValueError, match="focal organization differs"):
        strategy.prepare(basis, focal="retailer-fixture")


@pytest.mark.parametrize("category", ["strength", "weakness"])
def test_explicit_strength_and_weakness_labels_do_not_supply_vrio_capabilities(store, payload, entities, category):
    row = approved(store, {**payload, "category": category}, entities)
    basis = snapshot(store)
    review = strategy.save_draft(store, strategy.prepare(basis, focal="company-fixture"), "Analyst", 0)
    assert f"Analyst-recorded {category}" in review["frameworks"]["swot_tows"]["entries"][0]["text"]
    assert not review["frameworks"]["vrio"]["entries"]
    with pytest.raises(ValueError, match="approved internal inputs"):
        strategy.record_decision(store, basis, "Analyst", 1, "correct", "Assign a capability judgment.", "vrio", [row["id"]], focal="company-fixture")
    corrected = strategy.record_decision(store, basis, "Analyst", 1, "correct", "Retain the recorded scope.", "swot_tows", [row["id"]], focal="company-fixture")
    assert corrected["corrections"][0]["framework"] == "swot_tows"


def test_all_affirmative_vrio_answers_remain_attributed_analyst_judgments(store, payload, entities):
    judgments = {field: {"judgment": "yes", "rationale": f"Analyst rationale for {field}."} for field in inputs.VRIO_FIELDS}
    approved(store, {**payload, "vrio": judgments}, entities)
    review = strategy.prepare(snapshot(store), focal="company-fixture")
    entry = review["frameworks"]["vrio"]["entries"][0]
    assert entry["vrio"] == judgments and entry["kind"] == "Approved analyst VRIO judgments"
    assert entry["confidence"] == "Analyst judgment" and entry["text"] == payload["statement"]
    assert "sustained advantage" not in entry["text"].lower()


def test_tows_uses_cited_same_scope_opportunity_without_promoting_capability_to_strength(store, payload, entities):
    row = approved(store, payload, entities)
    opportunity = {"id": "fixture-opportunity", "crop": "raspberry", "region": "europe", "roles": ["propagation"],
                   "title": "Bounded nursery pilot", "risk": "Delivery has not been tested.", "frameworks": [],
                   "scores": {"access": [1, "Fixture rationale"]}, "next_step": "Compare delivery outcomes.", "entity_ids": ["company-fixture"],
                   "sources": [["fixture-circular", "Public circular", "https://example.org/circular", "2026-10-01", "A trial window was disclosed.", ["propagation"]]]}
    review = strategy.prepare(snapshot(store, opportunities=[opportunity]), focal="company-fixture")
    entries = review["frameworks"]["swot_tows"]["entries"]
    hypothesis = next(entry for entry in entries if entry["kind"] == "TOWS hypothesis")
    assert hypothesis["source_ids"] == [row["id"], "fixture-circular"] and hypothesis["confidence"] == "Low"
    assert "strength" not in entries[0]["text"].lower()
    wrong = {**opportunity, "crop": "blueberry"}
    global_review = strategy.prepare(snapshot(store, crop="", region="", opportunities=[wrong]), focal="company-fixture")
    assert not any(entry["kind"] == "TOWS hypothesis" for entry in global_review["frameworks"]["swot_tows"]["entries"])


def test_changed_inputs_block_refresh_and_decisions_even_with_old_snapshot(store, payload, entities):
    row = approved(store, payload, entities)
    basis = snapshot(store)
    review = strategy.save_draft(store, strategy.prepare(basis, focal="company-fixture"), "Analyst", 0)
    with pytest.raises(living.Conflict, match="focal organization changed"):
        strategy.record_decision(store, basis, "Reviewer", review["version"], "approve", "", focal="retailer-fixture")
    inputs.decide_input(store, row["id"], "Reviewer", entities, 2, "withdraw", token="input-withdrawal")
    with pytest.raises(living.Conflict, match="analyst inputs changed"):
        strategy.record_decision(store, basis, "Reviewer", review["version"], "approve", "", focal="company-fixture")
    with pytest.raises(living.Conflict, match="analyst inputs changed"):
        strategy.save_draft(store, strategy.prepare(basis, focal="company-fixture"), "Analyst", review["version"])
    assert living.digest(snapshot(store)) != review["basis"]
    assert store.get(review["id"])["state"] == "draft"


def test_company_corrections_require_relevant_approved_input(store, payload, entities):
    row = approved(store, payload, entities)
    basis = snapshot(store)
    review = strategy.save_draft(store, strategy.prepare(basis, focal="company-fixture"), "Analyst", 0)
    with pytest.raises(ValueError, match="approved internal inputs"):
        strategy.record_decision(store, basis, "Analyst", 1, "correct", "Check this claim.", "vrio", ["public-fixture"], focal="company-fixture")
    corrected = strategy.record_decision(store, basis, "Analyst", 1, "correct", "Keep rarity unknown.", "vrio", [row["id"]], focal="company-fixture")
    approved_review = strategy.record_decision(store, basis, "Reviewer", corrected["version"], "approve", "", focal="company-fixture")
    assert approved_review["state"] == "approved" and len(approved_review["corrections"]) == 1


def test_legacy_snapshots_and_reviews_keep_existing_lineage_without_inputs(store):
    model = {"filters": {"crop": "raspberry", "region": "europe"}, "coverage": {}}
    basis = strategy.snapshot_for(model)
    assert basis == {"scope": {"crop": "raspberry", "region": "europe", "role": "", "event_type": "", "start": "", "end": "", "q": ""},
                     "sources": {}, "priorities": [], "cutoff": "", "gaps": [], "coverage_as_of": None}
    legacy = snapshot(store)
    assert "focal" not in legacy and "analyst_inputs" not in legacy
    draft = strategy.save_draft(store, strategy.prepare(legacy, focal="company-fixture"), "Analyst", 0)
    same = strategy.snapshot_for({"filters": legacy["scope"], "coverage": {"observations": [{
        "id": "public-fixture", "title": "Public trial notice", "source_url": "https://example.org/notice",
        "summary": "A supplier described a trial window.", "source_date": "2026-10-01", "crop": "raspberry", "region": "europe",
    }]}}, focal="company-fixture")
    assert same == legacy
    approved_review = strategy.record_decision(store, same, "Reviewer", draft["version"], "approve", "")
    assert approved_review["state"] == "approved" and approved_review["id"] == strategy.scope_key(legacy["scope"])
    assert not approved_review["frameworks"]["swot_tows"]["entries"] and not approved_review["frameworks"]["vrio"]["entries"]
