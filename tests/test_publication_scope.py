"""Reviewing a private source cannot publish its content or dependent graph."""
from copy import deepcopy
import json
from types import SimpleNamespace

import pytest

from app.repositories.base import StorageError
from app.services.publication_scope import public_repositories


class RawRepository:
    def __init__(self, rows=()):
        self.rows = deepcopy(list(rows))
        self.list_calls = 0

    def list(self, **filters):
        self.list_calls += 1
        return deepcopy([row for row in self.rows if all(row.get(key) == value for key, value in filters.items())])

    def get(self, key):
        raise AssertionError("Projection must not recurse through raw get()")


def repositories(**families):
    names = ("entities", "evidence", "facts", "relationships", "signals", "assessments", "recommendations", "strategic_questions", "sources")
    return SimpleNamespace(**{name: RawRepository(families.get(name, [])) for name in names})


@pytest.mark.parametrize("review_state", ["rejected", "archived", "withdrawn", "deleted", {"invalid": True}])
def test_terminal_or_malformed_review_state_cannot_enter_public_projection(review_state):
    raw = repositories(evidence=[{"id": "ev-terminal", "status": "published", "publication_scope": "public",
                                  "review_state": review_state}],
                       facts=[{"id": "fact-terminal", "evidence_ids": ["ev-terminal"]}])
    view = public_repositories(raw)
    assert not view.evidence.list() and not view.facts.list()
    assert raw.evidence.rows[0]["review_state"] == review_state


def test_private_reviewed_source_and_transitive_mixed_support_stay_private():
    raw = repositories(
        evidence=[{"id": "ev-public", "status": "published"},
                  {"id": "ev-private", "status": "published", "publication_scope": "private", "reviewed_by": "Analyst", "article": "PRIVATE_BODY"},
                  {"id": "ev-pending", "status": "draft"}],
        facts=[{"id": "fact-private", "evidence_ids": ["ev-private"]},
               {"id": "fact-mixed", "evidence_ids": ["ev-public", "ev-private"]},
               {"id": "fact-public", "evidence_ids": ["ev-public"]}],
        signals=[{"id": "signal-private", "fact_ids": ["fact-private"]}],
        assessments=[{"id": "assessment-private", "signal_ids": ["signal-private"]}],
        recommendations=[{"id": "recommendation-private", "assessment_ids": ["assessment-private"]}],
        relationships=[{"id": "rel-private", "subject_id": "company-public", "object_id": "company-private", "evidence_ids": ["ev-public"]}],
        entities=[{"id": "company-public"}, {"id": "company-private", "publication_scope": "private"}],
    )
    view = public_repositories(raw)
    assert view.public_view and public_repositories(view) is view
    assert [row["id"] for row in view.evidence.list()] == ["ev-public"]
    assert view.evidence.get("ev-private") is None and view.evidence.get("ev-pending") is None
    assert [row["id"] for row in view.facts.list()] == ["fact-public"]
    assert not view.signals.list() and not view.assessments.list() and not view.recommendations.list()
    assert not view.relationships.list() and view.entities.get("company-private") is None
    assert raw.evidence.rows[1]["article"] == "PRIVATE_BODY"


def test_public_entity_and_source_keep_content_but_strip_private_backlinks_and_link_objects():
    public_source = {"id": "ev-public", "status": "published", "title": "Public source",
                     "article": {"paragraphs": [{"text": "Unchanged public source wording."}]},
                     "parent_evidence_id": "ev-private", "fact_ids": ["fact-public", "fact-private"],
                     "evidence_links": [{"target_evidence_id": "ev-private", "notes": "Private relationship explanation"},
                                        {"target_evidence_id": "ev-other", "status": "supports"}]}
    public_entity = {"id": "company-public", "name": "Public company", "evidence_ids": ["ev-public", "ev-private"],
                     "fact_ids": ["fact-private"], "attributes": {"public_note": "Public detail", "source": {"id": "ev-private", "text": "Private explanation"},
                     "links": [{"href": "/intelligence/ev-private", "label": "Private source"}], "by_id": {"ev-private": "Private detail"}},
                     "internal_note": "Supporting detail is ev-private.",
                     "private_href": "/evidence/ev-private.json"}
    raw = repositories(entities=[public_entity], evidence=[public_source, {"id": "ev-other", "status": "published"},
                       {"id": "ev-private", "status": "published", "publication_scope": "private"}],
                       facts=[{"id": "fact-private", "evidence_ids": ["ev-private"]}, {"id": "fact-public", "evidence_ids": ["ev-public"]}])
    original = deepcopy((raw.entities.rows, raw.evidence.rows))
    view = public_repositories(raw)
    entity, evidence = view.entities.get("company-public"), view.evidence.get("ev-public")
    assert entity["evidence_ids"] == ["ev-public"] and entity["fact_ids"] == []
    assert entity["attributes"]["public_note"] == "Public detail"
    assert evidence["article"] == public_source["article"]
    assert evidence["evidence_links"] == [{"target_evidence_id": "ev-other", "status": "supports"}]
    exported = json.dumps([entity, evidence])
    assert "ev-private" not in exported and "fact-private" not in exported
    assert "Private explanation" not in exported and "Private relationship explanation" not in exported
    assert (raw.entities.rows, raw.evidence.rows) == original


def test_snapshot_reads_each_raw_family_once_then_get_list_are_copied_readonly():
    raw = repositories(evidence=[{"id": "ev-one", "status": "published", "publication_scope": "public", "tags": ["original"]}])
    view = public_repositories(raw)
    for _ in range(3):
        view.evidence.list(status="published")[0]["tags"].append("local")
        view.evidence.get("ev-one")["tags"].append("local")
    assert view.evidence.get("ev-one")["tags"] == ["original"]
    assert all(getattr(raw, name).list_calls == 1 for name in vars(raw))
    for operation in (view.evidence.create, view.evidence.update, view.evidence.delete, view.evidence.create_many):
        with pytest.raises(StorageError, match="read-only"):
            operation({"id": "new"})


def test_private_attribute_sibling_is_removed_without_dropping_public_detail():
    attributes = {
        "public_note": "Visible company detail", "private_link": "/intelligence/ev-private",
        "nested": {"public_detail": "Visible nested detail", "private_note": "See ev-private"},
        "source": {"target_evidence_id": "ev-private", "label": "Private source explanation"},
        "links": [{"destination": "/intelligence/ev-private", "label": "Private list entry"},
                  {"destination": "/intelligence/ev-public", "label": "Public list entry"}],
    }
    raw = repositories(
        entities=[{"id": "company-public", "attributes": attributes}],
        evidence=[{"id": "ev-private", "status": "published", "publication_scope": "private"},
                  {"id": "ev-public", "status": "published"}],
    )
    public = public_repositories(raw).entities.get("company-public")["attributes"]
    assert public == {
        "public_note": "Visible company detail", "nested": {"public_detail": "Visible nested detail"},
        "links": [{"destination": "/intelligence/ev-public", "label": "Public list entry"}],
    }
    assert raw.entities.rows[0]["attributes"] == attributes


def test_missing_scope_preserves_legacy_public_objects_but_invalid_scope_fails_closed():
    raw = repositories(evidence=[{"id": "ev-legacy", "status": "published"}, {"id": "ev-unknown-scope", "status": "published", "publication_scope": "unknown"}],
                       strategic_questions=[{"id": "sq-legacy"}, {"id": "sq-private", "publication_scope": "private"}],
                       entities=[{"id": "entity-legacy"}])
    view = public_repositories(raw)
    assert view.evidence.get("ev-legacy") is not None and view.evidence.get("ev-unknown-scope") is None
    assert view.strategic_questions.get("sq-legacy") is not None and view.strategic_questions.get("sq-private") is None
    assert view.entities.get("entity-legacy") is not None
