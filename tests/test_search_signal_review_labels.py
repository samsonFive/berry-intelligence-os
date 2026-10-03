"""Search must report a Signal's stored status without inventing confirmation."""
from copy import deepcopy

import pytest

from app.services.global_search import SearchPools, search_global


@pytest.mark.parametrize("status,label", [
    ("proposed", "Proposed signal"), ("active", "Active signal"),
    ("watch", "Signal being watched"), ("monitoring", "Signal being monitored"),
    ("confirmed", "Confirmed signal"), ("resolved", "Resolved signal"),
    ("refuted", "Refuted signal"), ("retired", "Retired signal"),
    ("disputed", "Disputed signal"), ("deferred", "Deferred signal"),
    ("dismissed", "Dismissed signal"), (None, "Signal · review status not recorded"),
    ("emerging", "Signal · review status not recorded"),
    ("legacy-unknown", "Signal · review status not recorded"),
])
def test_search_signal_label_preserves_actual_status_and_source_record(status, label):
    signal = {"id": "sig-review-label", "title": "Orchard expansion pattern", "status": status}
    original = deepcopy(signal)
    result = search_global("Orchard expansion pattern", SearchPools(signals=[signal]), include_private=False)
    group = next(item for item in result["groups"] if item["id"] == "signals")
    row = group["in_context"][0]
    assert row["state_label"] == label
    assert row["href"] == "/signals/sig-review-label"
    assert (row["state"] == "confirmed_signal") == (status == "confirmed")
    assert signal == original
    if status == "legacy-unknown":
        assert row["subtitle"] == "Unrecognized status: legacy-unknown"


def test_confirmed_candidate_still_does_not_become_a_trusted_signal_in_search():
    candidate = {"id": "sigcand-label", "title": "Orchard expansion pattern", "status": "confirmed"}
    pools = SearchPools(signal_candidates=[candidate])
    assert not search_global("Orchard expansion pattern", pools, include_private=False)["result_count"]
    result = search_global("Orchard expansion pattern", pools, include_private=True)
    group = next(item for item in result["groups"] if item["id"] == "signals")
    assert group["in_context"][0]["state"] == "emerging_signal"
    assert group["in_context"][0]["href"] == "/signals/candidates/sigcand-label"


def test_reviewed_candidate_card_keeps_its_trust_boundary_visible():
    from app import main

    html = main.templates.env.get_template("_signal_card.html").render(
        item={"status": "confirmed", "confidence_label": "Low", "status_label": "Confirmed",
              "href": "/signals/candidates/sigcand-label", "label": "Orchard expansion pattern"},
        authoring_mode=False, static_build=False,
    )
    assert "Reviewed pattern" in html
    assert "Confirmed signal" not in html
    assert "Confirm does not publish a trusted Signal" in html
