import hashlib
import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker
import pytest

from app.composition import get_repositories, get_unit_of_work
from app.services.berry_landscape_intake import PRIVATE_FOLDER, reconcile
from app.services.living_workspaces import Store
from app.services.review_publish import PublishRequest, ReviewPublishService


SCHEMAS = Path(__file__).resolve().parents[1] / "schemas"


def _write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def _source(name, slug):
    return {"url": f"https://{slug}.example/deal", "name": name, "published_date": "2026-11-01"}


def _row(key, sources, **extra):
    return {"event_key": key, "status": "verified", "title": "Berry collaboration",
            "summary": "The parties announced collaboration.", "sources": sources,
            "berry_ids": ["berry-blueberry", "berry-raspberry"], "entity_ids": ["company-grower"],
            "event_type": "partnership", **extra}


def _fixture(tmp_path):
    raw = b"original vendor export\n"
    (tmp_path / "raw.csv").write_bytes(raw)
    original = _source("Party A", "a")
    data, inbox, packet = tmp_path / "data", tmp_path / "inbox", tmp_path / "packet.json"
    _write(data / "entities/companies/company-grower.json", {"id": "company-grower", "entity_type": "company",
           "record_type": "entity", "name": "Fixture Grower", "status": "active"})
    _write(data / "evidence/ev-existing.json", {"id": "ev-existing", "source_url": original["url"], "status": "published",
           "record_type": "evidence", "title": "Original collaboration", "summary": "Announced partnership",
           "source_type": "company_press_release", "source_name": "Party A", "published_date": "2026-11-01",
           "captured_date": "2026-11-01"})
    payload = {
        "batch_id": "sample-run", "run": {"provider": "newscatcher", "run_id": "original-run-id",
            "date": "2026-11-09", "prompt": "Public-only prompt\n", "credits_used": 1000,
            "raw_export": "raw.csv", "raw_sha256": hashlib.sha256(raw).hexdigest()},
        "events": [
            _row("deal-announcement", [{**original, "url": original["url"] + "?utm_source=abc"}, _source("Party B", "b")]),
            _row("deal-closing", [_source("Party C", "c")], prior_event_key="deal-announcement",
                 event_date="2026-10-30", announcement_date="2026-10-28", effective_date="2026-11-04",
                 event_type="regulatory"),
            _row("unresolved-identity", [_source("Party D", "d")], entity_ids=["company-unknown"]),
            {"event_key": "unverified-claim", "status": "unverified", "reason": "Terms unclear", "follow_up": "Find contract"},
            {"event_key": "irrelevant", "status": "excluded", "reason": "Wrong crop"},
        ],
    }
    _write(packet, payload)
    return data, inbox, packet, payload, raw


def test_intake_preview_stage_replay_and_rollback(tmp_path):
    data, inbox, packet, _, raw = _fixture(tmp_path)
    original = (data / "evidence/ev-existing.json").read_bytes()

    def run(mode="dry_run"):
        return reconcile(packet, data_dir=data, inbox_dir=inbox, mode=mode)

    preview = run()
    assert preview["counts"] == {"inserts": 1, "evidence_additions": 1, "duplicates": 1,
                                 "unresolved_matches": 1, "unverified": 1, "exclusions": 1}
    assert not inbox.exists()
    result = run("apply")
    assert result["mode"] == "applied"
    assert result["counts"] == preview["counts"]
    assert result["run"]["prompt"] == "Public-only prompt\n"
    workspace_id = result["workspace"]["href"].split("/")[-1]
    workspace = Store(inbox).get(workspace_id)
    assert len(workspace["blocks"]) == 3
    assert "Find contract" in workspace["blocks"][-1]["text"]
    ledger_dir = inbox / PRIVATE_FOLDER / "sample-run"
    assert (ledger_dir / "raw-export").read_bytes() == raw

    schema_path = SCHEMAS / "evidence.schema.json"
    validator = Draft202012Validator(json.loads(schema_path.read_text(encoding="utf-8")), format_checker=FormatChecker())
    drafts = [json.loads(path.read_text(encoding="utf-8")) for path in (inbox / "evidence").glob("*.json")]
    assert len(drafts) == 2
    for draft in drafts:
        validator.validate(draft)
        assert draft["status"] == "draft"
        assert draft["berry_ids"] == ["berry-blueberry", "berry-raspberry"]
        assert draft["fact_ids"] == draft["relationship_ids"] == []
    assert {draft["event_type"] for draft in drafts} == {"partnership", "regulatory"}
    assert {draft["evidence_links"][0]["predicate"] for draft in drafts} == {"corroborates", "follows_up"}
    assert all(draft["evidence_links"][0]["status"] == "proposed" for draft in drafts)
    assert run("apply")["counts"] == {**preview["counts"], "inserts": 0, "evidence_additions": 0, "duplicates": 3}
    assert (data / "evidence/ev-existing.json").read_bytes() == original

    rollback = run("rollback")
    assert len(rollback["removed_drafts"]) == 2
    assert not list((inbox / "evidence").glob("*.json"))
    assert len(list((ledger_dir / "rolled-back").glob("*.json"))) == 2
    assert Store(inbox).get(workspace_id)["landscape_batch_rolled_back"] is True
    assert run("rollback")["removed_drafts"] == []
    with pytest.raises(ValueError, match="was rolled back"):
        run("apply")


def test_reconciliation_protects_reviewed_changes_and_run_identity(tmp_path):
    data, inbox, packet, payload, _ = _fixture(tmp_path)
    result = reconcile(packet, data_dir=data, inbox_dir=inbox, mode="apply")
    draft_id = next(row["draft_id"] for row in result["outcomes"] if row["outcome"] == "inserts")
    draft_path = inbox / "evidence" / f"{draft_id}.json"
    draft = json.loads(draft_path.read_text(encoding="utf-8"))
    draft["summary"] = "Human edit after import"
    _write(draft_path, draft)
    payload["batch_id"] = "relabelled-run"
    other_packet = tmp_path / "other.json"
    _write(other_packet, payload)
    with pytest.raises(ValueError, match="Run already recorded"):
        reconcile(other_packet, data_dir=data, inbox_dir=inbox)
    rollback = reconcile(packet, data_dir=data, inbox_dir=inbox, mode="rollback")
    assert rollback["protected_drafts"] == [draft_id]
    assert json.loads(draft_path.read_text(encoding="utf-8"))["summary"] == "Human edit after import"
    (tmp_path / "raw.csv").write_bytes(b"changed export")
    with pytest.raises(ValueError, match="SHA-256"):
        reconcile(packet, data_dir=data, inbox_dir=inbox)


@pytest.mark.parametrize(("outcome", "event_key", "event_type"), [
    ("evidence_additions", "deal-announcement", "partnership"),
    ("inserts", "deal-closing", "regulatory"),
])
def test_publication_review_keeps_proposed_links_and_event_identity(tmp_path, outcome, event_key, event_type):
    data, inbox, packet, _, _ = _fixture(tmp_path)
    result = reconcile(packet, data_dir=data, inbox_dir=inbox, mode="apply")
    draft_id = next(row["draft_id"] for row in result["outcomes"] if row["outcome"] == outcome)
    path = inbox / "evidence" / f"{draft_id}.json"
    draft = json.loads(path.read_text(encoding="utf-8"))
    service = ReviewPublishService(
        repositories=get_repositories(data, SCHEMAS),
        unit_of_work_factory=lambda: get_unit_of_work(data, SCHEMAS, "entities", "facts", "relationships", "evidence"),
        get_validator=lambda schema: Draft202012Validator(json.loads((SCHEMAS / schema).read_text(encoding="utf-8"))),
        unique_entity_id=lambda *args: pytest.fail("Existing entity should resolve"),
        append_unique=lambda values, key: list(dict.fromkeys([*values, key])),
        move_draft_attachments=lambda *args: [], restore_draft_attachments=lambda *args: None,
        delete_draft=lambda key: path.unlink(), review_events_inbox=inbox,
    )
    reviewed = service.publish(PublishRequest(
        draft=draft, draft_id=draft_id,
        **{key: draft[key] for key in ("title", "summary", "source_type", "source_name", "source_url",
                                      "published_date", "captured_date", "tags", "priority")},
        why_it_matters="", reviewer="fixture reviewer", selected_berries=draft["berry_ids"],
        all_entity_names_by_type={"company": ["Fixture Grower"]}, facts_input=[],
        relationships_input=[], strategic_question_text=[],
    ))
    assert reviewed.ok, reviewed.schema_errors
    record = json.loads((data / "evidence" / f"{draft_id}.json").read_text(encoding="utf-8"))
    assert record["landscape_event_key"] == event_key
    assert record["event_type"] == event_type
    assert record["published_date"] == "2026-11-01"
    if event_type == "regulatory":
        assert record["event_date"] == "2026-10-30"
        assert record["announcement_date"] == "2026-10-28"
        assert record["effective_date"] == "2026-11-04"
        assert record["prior_event_key"] == "deal-announcement"
    assert record["evidence_links"] == draft["evidence_links"]
    assert record["evidence_links"][0]["status"] == "proposed"
    assert record["fact_ids"] == record["relationship_ids"] == []
    assert draft_id in reconcile(packet, data_dir=data, inbox_dir=inbox, mode="rollback")["protected_drafts"]
