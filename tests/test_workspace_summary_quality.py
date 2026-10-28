from copy import deepcopy
import json
from types import SimpleNamespace

import pytest

from app.services import workspace_summary_quality as quality
from app.services.living_workspaces import model_narrative


FACT = "The issuer announced strawberry field trials planned for 2026."


def fixture():
    refs = {"capture": {"number": 1, "item_id": "capture", "source_id": "archive", "title": "Release", "url": "https://example.org"}}
    rows = [{"section": section, "text": FACT, "source_ids": ["capture"]}
            for section in ("The picture", "Key developments", "Key developments", "Why it matters", "What to watch", "What to watch")]
    return rows, refs


def checks(rows, quote=FACT, supported=True):
    return {"checks": [{"paragraph": i, "supported": supported, "evidence": [{"source_id": "capture", "quote": quote}]}
                       for i in range(len(rows))]}


@pytest.mark.parametrize("change", [
    lambda rows: rows.append(deepcopy(rows[-1])),
    lambda rows: rows[0].update(section="Analyst questions"),
    lambda rows: rows[0].update(text="Which regulatory pathways will establish commercial berry products?"),
    lambda rows: rows[0].update(text="Could licensing lower costs and accelerate commercialization"),
    lambda rows: rows[0].update(text="Can a license establish berry sales\uff1f"),
    lambda rows: rows[0].update(text="The issuer announced trials. Which markets will adopt them"),
    lambda rows: rows[0].update(text="An extra heading\n\n## Unsupported section"),
    lambda rows: rows[0].update(source_ids=["outside-page"]),
    lambda rows: rows[0].update(text="Research " * 56),
    lambda rows: [row.update(text="Research " * 49) for row in rows],
])
def test_invalid_shape_questions_scope_and_length_are_rejected(change):
    rows, refs = fixture()
    change(rows)
    with pytest.raises(quality.SummaryQualityError):
        quality.validate_rows(rows, refs)


def test_valid_compact_source_cited_sections_and_landscape_scope():
    rows, refs = fixture()
    quality.validate_rows(rows, refs)
    refs["landscape"] = {"number": 2, "kind": "landscape"}
    with pytest.raises(quality.SummaryQualityError):
        quality.validate_rows(rows, refs)
    rows[2]["source_ids"].append("landscape")
    quality.validate_rows(rows, refs)
    assert len(quality.render(rows, refs).split()) <= 300


@pytest.mark.parametrize("bad", ["unsupported", "invented_quote", "title_only", "missing_paragraph", "duplicate_paragraph", "uncited_source"])
def test_citation_labels_alone_do_not_pass_source_support(bad):
    rows, _ = fixture()
    packet = [{"id": "capture", "quote": FACT, "statement": "", "note": "", "source_title": "Official clearance pathway"}]
    result = checks(rows)
    if bad == "unsupported":
        rows[0]["text"] = "The product has clearance in every market."
        result["checks"][0]["supported"] = False
    elif bad == "invented_quote":
        result["checks"][0]["evidence"][0]["quote"] = "The company obtained global regulatory clearance."
    elif bad == "title_only":
        result["checks"][0]["evidence"][0]["quote"] = packet[0]["source_title"]
    elif bad == "missing_paragraph":
        result["checks"].pop()
    elif bad == "duplicate_paragraph":
        result["checks"][-1]["paragraph"] = 0
    else:
        result["checks"][0]["evidence"][0]["source_id"] = "outside-page"
    with pytest.raises(quality.SummaryQualityError):
        quality.check_support(rows, packet, lambda *args, **kwargs: SimpleNamespace(parsed=result))


def test_one_automatic_repair_then_checked_summary_and_no_model_trust_promotion():
    rows, refs = fixture()
    items = {"capture": {"nature": "source_statement", "kind": "article", "quote": FACT, "text": FACT, "note": ""}}
    block = {"text": "Original source digest", "citations": list(refs.values())}
    calls = []
    def complete(prompt, **kwargs):
        calls.append(prompt)
        if "checks" in kwargs["schema"]["properties"]:
            return SimpleNamespace(parsed=checks(rows), provider="test", model="test")
        result = deepcopy(rows)
        if len(calls) == 1:
            result[-1]["text"] = "Which unsupported regulatory pathway should we speculate about?"
        return SimpleNamespace(parsed={"sentences": result}, provider="test", model="test")
    result = model_narrative(block, items, sources={"archive": {"id": "archive", "text": FACT, "availability": "body_available"}}, completer=complete)
    assert len(calls) == 3
    assert "previous draft failed quality checks" in calls[1]
    assert json.loads(calls[1].split("\n", 1)[1])[0]["saved_article_text"] == FACT
    assert result["quality_checks"]["policy"] == quality.POLICY
    assert result["supporting_digest"] == "Original source digest"
    assert "regulatory pathway" not in result["text"]
    assert items["capture"]["nature"] == "source_statement"
    assert "verification_state" not in items["capture"]


def test_persistent_unsupported_claim_does_not_become_an_ai_summary():
    rows, refs = fixture()
    items = {"capture": {"nature": "source_statement", "kind": "article", "quote": FACT, "text": FACT, "note": ""}}
    block = {"text": "Original source digest", "citations": list(refs.values())}
    calls = []
    def complete(prompt, **kwargs):
        calls.append(prompt)
        parsed = checks(rows, supported=False) if "checks" in kwargs["schema"]["properties"] else {"sentences": rows}
        return SimpleNamespace(parsed=parsed, provider="test", model="test")
    result = model_narrative(block, items, sources={}, completer=complete)
    assert len(calls) == 4
    assert result["text"] == "Original source digest"
    assert "quality_checks" not in result and "method" not in result
    assert "unsupported claims" in result["generation_notice"]
