from copy import deepcopy
from html.parser import HTMLParser

from app.main import templates
from app.services.entity_dossier import PILOT_QUESTIONS, build_dossier


ENTITY = {
    "id": "company-review-fixture",
    "entity_type": "company",
    "name": "Berry_Profile & Co",
    "status": "active",
    "roles": ["grower", "marketer", "breeding_joint_venture_partner", "genetics_licensee"],
}


class Content(HTMLParser):
    """Keep ancestry so tests distinguish default content from collapsed details."""

    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.text = []
        self.nodes = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        node = (tag, dict(attrs))
        self.nodes.append((node, list(self.stack)))
        if tag not in {"br", "hr", "img", "input", "link", "meta"}:
            self.stack.append(node)

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index][0] == tag:
                del self.stack[index:]
                break

    def handle_data(self, data):
        if data.strip():
            self.text.append((data.strip(), list(self.stack)))


def _dossier(state=None, entity=None):
    return build_dossier(entity_id=ENTITY["id"], entity=deepcopy(entity or ENTITY), profile={},
                         state=state or {"statements": {}})


def _render(dossier):
    return templates.env.get_template("_company_dossier_sections.html").render(
        dossier=dossier, name=ENTITY["name"], entity=ENTITY, profile={},
        status="active", official_website="", crops=["raspberry"], aliases=[],
        verification_label="Unverified", is_registry=False, growing_profile=None,
        entity_id=ENTITY["id"], watches=[],
    )


def _closed_details(ancestors):
    return any(tag == "details" and "open" not in attrs for tag, attrs in ancestors)


def test_friendly_profile_labels_preserve_raw_answers_and_registry():
    entity_before = deepcopy(ENTITY)
    registry_before = deepcopy(PILOT_QUESTIONS)
    dossier = _dossier()
    questions = {row["id"]: row for row in dossier["questions"]}
    roles = questions["entity.activity.berry_roles"]
    assert roles["answer"] == ", ".join(ENTITY["roles"])
    assert roles["display_answer"] == "grower, marketer, breeding joint venture partner, genetics licensee"
    assert roles["answer_basis"] == "profile" and roles["answer_state"] == "answered"
    assert questions["entity.identity.canonical_name"]["display_answer"] == "Berry_Profile & Co"
    assert dossier["statements"] == []
    assert dossier["assessment"]["state"] == "insufficient_evidence"
    assert ENTITY == entity_before and PILOT_QUESTIONS == registry_before

    content = Content(_render(dossier))
    assert any(text == roles["display_answer"] and not _closed_details(path) for text, path in content.text)
    assert all(_closed_details(path) for text, path in content.text if "breeding_joint_venture_partner" in text)
    assert any(text == "Company profile · not a reviewed statement" for text, _ in content.text)
    for question in PILOT_QUESTIONS:
        assert any(text == question["question"] and not _closed_details(path) for text, path in content.text)
        assert any(text == question["id"] and _closed_details(path) for text, path in content.text)
    controls = [attrs["data-launch-gap-research"] for (tag, attrs), _ in content.nodes
                if tag == "button" and "data-launch-gap-research" in attrs]
    assert controls == [row["id"] for row in dossier["questions"]
                        if row["answer_state"] in {"not_yet_researched", "unknown", "stale", "conflicting"}]


def test_exact_reviewed_text_and_provenance_survive_presentation():
    statement = {
        "id": "statement-review-fixture", "entity_ids": [ENTITY["id"]],
        "statement_type": "quantity", "statement_state": "trusted_analyst",
        "trust_state": "trusted_analyst", "canonical_fact_id": "fact-review-fixture",
        "feed_item_id": "ev-review-fixture", "origin": "reader_evidence_lens",
        "statement_text": "14_million plants & no universal yield claim.",
        "supporting_passages": ["Publisher's 14_million plants & <trial> wording."],
        "confirmed_at": "2026-11-03", "updated_at": "2026-11-03",
    }
    pending = {**statement, "id": "pending", "statement_state": "pending_confirmation",
               "trust_state": "pending_confirmation", "canonical_fact_id": None,
               "statement_text": "UNREVIEWED MUST NOT BECOME AN ANSWER"}
    state = {"statements": {"ev-review-fixture": [statement, pending]}}
    original = deepcopy(state)
    # Scale is applicable to breeder/nursery archetypes; preserve that existing gate.
    dossier = _dossier(state, {**ENTITY, "roles": ["breeder", "nursery"]})
    assert dossier["statements"] == [statement]
    question = next(row for row in dossier["questions"] if row["id"] == "entity.performance.plants_sold")
    assert question["display_answer"] == statement["statement_text"]
    assert question["answer_basis"] == "reviewed_statement"
    html = _render(dossier)
    content = Content(html)
    assert any(text == statement["statement_text"] and not _closed_details(path) for text, path in content.text)
    assert any(text == statement["supporting_passages"][0] and _closed_details(path) for text, path in content.text)
    assert all(_closed_details(path) for text, path in content.text if "fact-review-fixture" in text)
    assert "UNREVIEWED MUST NOT BECOME AN ANSWER" not in html
    assert 'href="/today?item=ev-review-fixture"' in html
    assert state == original


def test_question_metadata_and_assessment_details_are_closed_but_gates_remain_visible():
    dossier = _dossier()
    content = Content(_render(dossier))
    assert all("open" not in attrs for (tag, attrs), _ in content.nodes if tag == "details")
    assert any(text == "No approved competitive assessment" and not _closed_details(path) for text, path in content.text)
    assert any(text == dossier["assessment"]["conclusion"] and _closed_details(path) for text, path in content.text)
    assert any(text == "0/3 confirmed statements" and not _closed_details(path) for text, path in content.text)
    for key in ["Wave", "Registry question", "Section", "Priority"]:
        assert all(_closed_details(path) for text, path in content.text if text == key)
