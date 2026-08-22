from app.services.acquisition_state import acquisition_signature, version_state


def test_changed_acquisition_signature_invalidates_seen_index_but_retains_history():
    old = acquisition_signature("trade", 1, {"query": "old"})
    new = acquisition_signature("trade", 2, {"query": "new"})
    state = {"acquisition_signature": old, "seen": ["x"], "runs": [{"at": "then"}]}
    result = version_state(state, signature=new, seen_key="seen")
    assert result["seen"] == []
    assert result["runs"] == [{"at": "then"}]
    assert result["superseded_signatures"] == [old]
    assert result["acquisition_signature"] == new
