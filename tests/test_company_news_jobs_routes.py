from copy import deepcopy
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app.main as main
import app.company_news_routes as routes
from app.services.report_builder import company_news as core, company_news_jobs as jobs, reports_store


ENTITIES = [{"id": "company-orchard-labs", "name": "Orchard Labs", "entity_type": "company", "aliases": [], "berry_ids": ["berry-strawberry"]}]


def snapshot(names=None):
    return core.create_review(names or ["Orchard Labs"], entities=ENTITIES,
        from_date="2025-07-01", through_date="2026-10-31", as_of="2026-11-01", berry_id="berry-strawberry", source_scope="archive")


def populated():
    value = snapshot()
    key = value["companies"][0]["key"]
    value["companies"][0].update(disposition="has_findings", archive_status="complete", web_status="not_requested")
    value["sources"] = [{"id": "source-one", "title": "A reported launch", "url": "https://example.org/launch", "source_url": "https://example.org/launch",
        "published_date": "2026-01-03", "publication_date_basis": "publisher", "origin": "archive", "trust_class": "PUBLISHED EVIDENCE",
        "excerpt": "Orchard Labs announced a strawberry cultivar.", "capture_status": "stored", "eligibility": "dated_finding", "company_keys": [key]}]
    value["entries"] = [{"id": "cne-one", "company_key": key, "company_id": ENTITIES[0]["id"], "headline": "Reported cultivar launch",
        "published_date": "2026-01-03", "event_date": "", "summary": "A source-attributed announcement.", "news_angle": "Market access",
        "qualification": "Performance is company-reported.", "source_ids": ["source-one"], "entry_type": "development", "included": True,
        "review_status": "unreviewed", "edits": {}}]
    value.update(status="complete", completed_company_count=1)
    return value


def partially_populated():
    value = populated()
    value["companies"].append(snapshot(["Second company"])["companies"][0])
    value["status"] = "in_progress"
    return value


def report(inbox, value=None):
    return reports_store.create_report(inbox, title="Saved company review", report_type=jobs.REPORT_TYPE,
        scope={"report_type": jobs.REPORT_TYPE, "company_news_review": value or populated(), "version": 1}, sections=[])


@pytest.fixture
def web(monkeypatch, tmp_path):
    inbox = tmp_path / "inbox"
    data = tmp_path / "data"
    data.mkdir()
    monkeypatch.setattr(main, "INBOX_DIR", inbox)
    monkeypatch.setattr(main, "DATA_DIR", data)
    monkeypatch.setattr(main, "AUTHORING_MODE", True)
    monkeypatch.setenv("BIOS_REMOTE_INTERACTIVE", "false")
    monkeypatch.delenv("BIOS_BASIC_AUTH", raising=False)
    monkeypatch.setattr(main, "living_catalog", lambda: ENTITIES)
    monkeypatch.setattr(main, "all_evidence", lambda: [])
    monkeypatch.setattr(main, "_social_eligible_outputs", lambda rows: rows)
    calls = []
    monkeypatch.setattr(jobs, "run_review", lambda *args, **kwargs: calls.append(args))
    return inbox, calls, TestClient(main.app)


def test_preset_get_is_read_only_and_has_fixed_dates_roster_and_list(web):
    inbox, calls, client = web
    response = client.get("/reports/new?report_type=company_news_review")
    assert response.status_code == 200
    assert 'action="/reports/new/company-news"' in response.text
    for name in ("roster", "from_date", "through_date", "company_list_id", "source_scope"):
        assert f'name="{name}"' in response.text
    assert not calls and not inbox.exists()


def test_create_retains_full_requested_roster_and_queues_only_on_post(web):
    inbox, calls, client = web
    names = ["Orchard Labs", *[f"Unresolved Company {i}" for i in range(26)]]
    response = client.post("/reports/new/company-news", data={"title": "Cohort review", "roster": "\n".join(names),
        "from_date": "2025-07-01", "through_date": "2026-10-31", "berry": "berry-strawberry", "source_scope": "archive"}, follow_redirects=False)
    assert response.status_code == 303 and len(calls) == 1
    record = reports_store.list_reports(inbox)[0]
    assert [r["requested_name"] for r in record["scope"]["company_news_review"]["companies"]] == names
    assert len(record["scope"]["company_news_review"]["companies"]) == 27
    assert record["company_news_job"]["state"] == "queued"


def test_invalid_dates_create_no_report_or_job(web):
    inbox, calls, client = web
    response = client.post("/reports/new/company-news", data={"roster": "Orchard Labs", "from_date": "2026-10-31", "through_date": "2025-07-01", "source_scope": "combined"})
    assert response.status_code == 422 and not calls
    assert not reports_store.list_reports(inbox)


def test_saved_list_does_not_drop_an_unresolved_member(web, monkeypatch):
    inbox, calls, client = web
    monkeypatch.setattr(routes.feed_first, "load_state", lambda _: {"company_lists": {"list-one": {"name": "Saved cohort", "company_ids": ["company-orchard-labs", "company-unresolved"]}}})
    response = client.post("/reports/new/company-news", data={"company_list_id": "list-one", "roster": "Additional company", "from_date": "2025-07-01", "through_date": "2026-10-31", "source_scope": "archive"}, follow_redirects=False)
    assert response.status_code == 303
    requested = [r["requested_name"] for r in reports_store.list_reports(inbox)[0]["scope"]["company_news_review"]["companies"]]
    assert requested == ["Orchard Labs", "company-unresolved", "Additional company"]


def test_native_workspace_and_exports_use_saved_edits_without_research(web, monkeypatch):
    inbox, calls, client = web
    record = report(inbox)
    jobs.edit_entry(inbox, record["id"], "cne-one", changes={"headline": "Analyst headline", "summary": "Analyst summary"}, included=True, review_status="reviewed", expected_revision=0)
    before = (inbox / "reports" / (record["id"] + ".json")).read_bytes()
    monkeypatch.setattr(main, "_build_packet_and_coverage", lambda *_a, **_k: pytest.fail("Saved company review must not re-research"))
    response = client.get(f"/reports/{record['id']}?company={record['scope']['company_news_review']['companies'][0]['key']}")
    assert response.status_code == 200 and "Analyst headline" in response.text and "<iframe" not in response.text
    assert 'id="cne-one"' in response.text
    xlsx = client.get(f"/reports/{record['id']}/export.xlsx")
    pdf = client.get(f"/reports/{record['id']}/export.pdf")
    assert xlsx.status_code == pdf.status_code == 200
    assert xlsx.content.startswith(b"PK") and pdf.content.startswith(b"%PDF")
    assert xlsx.headers["cache-control"] == "private, no-store"
    assert before == (inbox / "reports" / (record["id"] + ".json")).read_bytes() and not calls


def test_stale_entry_edits_and_date_widening_are_rejected(tmp_path):
    record = report(tmp_path)
    jobs.edit_entry(tmp_path, record["id"], "cne-one", changes={"headline": "New headline"}, included=True, review_status="reviewed", expected_revision=0)
    with pytest.raises(jobs.ReviewBusy):
        jobs.edit_entry(tmp_path, record["id"], "cne-one", changes={"headline": "Stale"}, included=True, review_status="reviewed", expected_revision=0)
    for stamp in ("2024-01-01", "", "20260103"):
        with pytest.raises(ValueError):
            jobs.edit_entry(tmp_path, record["id"], "cne-one", changes={"published_date": stamp}, included=True, review_status="reviewed", expected_revision=1)


def test_checkpoint_preserves_analyst_changes_made_during_research(tmp_path):
    record = report(tmp_path, partially_populated())
    token = jobs.queue_review(tmp_path, record["id"])
    worker_snapshot = deepcopy(record["scope"]["company_news_review"])
    jobs.edit_entry(tmp_path, record["id"], "cne-one", changes={"headline": "Edit while worker runs"}, included=False, review_status="reviewed", expected_revision=0)
    jobs.checkpoint(tmp_path, record["id"], worker_snapshot, token)
    saved = jobs.load_review(tmp_path, record["id"])["scope"]["company_news_review"]["entries"][0]
    assert core.effective_entry(saved)["headline"] == "Edit while worker runs"
    assert saved["included"] is False and saved["review_status"] == "reviewed" and saved["edit_revision"] == 1


def test_real_kernel_lease_prevents_duplicate_worker_and_get_progress_has_no_writes(tmp_path):
    record = report(tmp_path, partially_populated())
    token = jobs.queue_review(tmp_path, record["id"])
    with jobs._lease(tmp_path, "run-" + record["id"]):
        assert jobs.worker_active(tmp_path, record["id"])
        with pytest.raises(jobs.ReviewBusy):
            jobs.queue_review(tmp_path, record["id"])
    before = {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    progress = jobs.progress(tmp_path, jobs.load_review(tmp_path, record["id"]))
    assert progress["worker_active"] is False and "token" not in progress
    assert before == {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}


def test_pause_resume_saves_each_company_and_never_repeats_finished(tmp_path):
    value = snapshot(["Orchard Labs", "Second company", "Third company"])
    record = report(tmp_path, value)
    seen = []
    def research(current, key, **_kwargs):
        current = deepcopy(current)
        seen.append(key)
        row = next(r for r in current["companies"] if r["key"] == key)
        row.update(disposition="no_qualifying_findings", archive_status="complete", web_status="not_requested")
        if len(seen) == 1:
            jobs.pause_review(tmp_path, record["id"])
        return current
    token = jobs.queue_review(tmp_path, record["id"])
    jobs.run_review(tmp_path, record["id"], token, world=lambda: (ENTITIES, [], tmp_path), research=research)
    assert jobs.load_review(tmp_path, record["id"])["company_news_job"]["state"] == "paused" and len(seen) == 1
    token = jobs.queue_review(tmp_path, record["id"])
    jobs.run_review(tmp_path, record["id"], token, world=lambda: (ENTITIES, [], tmp_path), research=research)
    assert len(seen) == len(set(seen)) == 3
    assert jobs.load_review(tmp_path, record["id"])["company_news_job"]["state"] == "complete"


def test_refresh_creates_new_version_and_leaves_previous_report_unchanged(web):
    inbox, calls, client = web
    old = report(inbox)
    path = inbox / "reports" / (old["id"] + ".json")
    before = path.read_bytes()
    response = client.post(f"/reports/{old['id']}/company-news/refresh", follow_redirects=False)
    assert response.status_code == 303 and path.read_bytes() == before
    new = next(r for r in reports_store.list_reports(inbox) if r["id"] != old["id"])
    assert new["scope"]["version"] == 2 and new["scope"]["parent_report_id"] == old["id"]
    assert new["scope"]["company_news_review"]["entries"] == [] and len(calls) == 1


def test_cross_site_requests_cannot_start_research(web):
    inbox, calls, client = web
    response = client.post("/reports/new/company-news", headers={"Origin": "https://other.example"}, data={"roster": "Orchard Labs"})
    assert response.status_code == 403 and not calls and not reports_store.list_reports(inbox)


@pytest.mark.parametrize("suffix", ["", "/export.pdf", "/export.xlsx", "/company-news/progress"])
def test_company_reports_inherit_private_login_boundary(web, monkeypatch, suffix):
    inbox, _, client = web
    record = report(inbox)
    monkeypatch.setenv("BIOS_REMOTE_INTERACTIVE", "true")
    monkeypatch.setenv("BIOS_REVIEW_USERNAME", "fixture-reader")
    monkeypatch.setenv("BIOS_REVIEW_PASSWORD", "fixture-password")
    monkeypatch.setenv("BIOS_SESSION_SECRET", "fixture-secret-that-is-at-least-thirty-two-characters")
    response = client.get(f"/reports/{record['id']}{suffix}", follow_redirects=False)
    assert response.status_code == 302 and "/login" in response.headers["location"]


def test_report_ids_cannot_escape_the_store(tmp_path):
    for value in ("../secret", "rp-test/../../secret", "C:/secret", "rp-" + "x" * 16):
        with pytest.raises(ValueError):
            jobs.load_review(tmp_path, value)


def test_completed_review_cannot_silently_research_again(tmp_path):
    record = report(tmp_path)
    with pytest.raises(ValueError, match="new version"):
        jobs.queue_review(tmp_path, record["id"])


def test_queued_worker_lost_after_restart_is_resumable_without_get_writes(tmp_path):
    record = report(tmp_path, snapshot())
    jobs.queue_review(tmp_path, record["id"])
    def stale(row, _snapshot):
        row["company_news_job"]["queued_at"] = "2000-01-01T00:00:00+00:00"
    record = jobs.mutate_review(tmp_path, record["id"], stale)
    path = tmp_path / "reports" / (record["id"] + ".json")
    before = path.read_bytes()
    assert jobs.progress(tmp_path, record)["state"] == "interrupted"
    assert path.read_bytes() == before
    jobs.queue_review(tmp_path, record["id"])
    assert jobs.load_review(tmp_path, record["id"])["company_news_job"]["state"] == "queued"


def test_inspected_lead_can_be_included_only_after_explicit_report_review(tmp_path):
    value = populated()
    value["sources"][0].update(source_version="a" * 64, eligibility="editorial_verification")
    value["entries"][0].update(entry_type="lead", included=False, summary="")
    record = report(tmp_path, value)
    with pytest.raises(ValueError, match="explicit report review"):
        jobs.edit_entry(tmp_path, record["id"], "cne-one", changes={"summary": "An analyst-verified source statement."}, included=True, review_status="unreviewed", expected_revision=0)
    before_source = deepcopy(value["sources"])
    jobs.edit_entry(tmp_path, record["id"], "cne-one", changes={"summary": "An analyst-verified source statement.", "event_date": "Planned 2026/27 season"}, included=True, review_status="reviewed", expected_revision=0)
    saved = jobs.load_review(tmp_path, record["id"])["scope"]["company_news_review"]
    assert saved["entries"][0]["manual_qualification"]["kind"] == "report_only"
    assert saved["entries"][0]["entry_type"] == "lead" and saved["sources"] == before_source
    assert core.effective_entry(saved["entries"][0])["event_date"] == "Planned 2026/27 season"


@pytest.mark.parametrize("eligibility", ["metadata_only", "blocked", "scope_unverified", "identity_unresolved"])
def test_hard_held_leads_cannot_be_included_by_report_review(tmp_path, eligibility):
    value = populated()
    value["sources"][0].update(source_version="a" * 64, eligibility=eligibility)
    value["entries"][0].update(entry_type="lead", included=False)
    record = report(tmp_path, value)
    with pytest.raises(ValueError):
        jobs.edit_entry(tmp_path, record["id"], "cne-one", changes={"summary": "Typed assertion"}, included=True, review_status="reviewed", expected_revision=0)


def test_validation_errors_keep_entered_text_in_editor(web):
    inbox, _, client = web
    record = report(inbox)
    response = client.post(f"/reports/{record['id']}/company-news/entry/cne-one", data={
        "headline": "Keep this draft headline", "summary": "Keep this draft text", "published_date": "2020-01-01",
        "included": "true", "review_status": "reviewed", "edit_revision": "0"})
    assert response.status_code == 422 and response.headers["content-type"].startswith("text/html")
    assert "Keep this draft headline" in response.text and "Keep this draft text" in response.text
    assert jobs.load_review(inbox, record["id"])["scope"]["company_news_review"]["entries"][0]["edits"] == {}


def test_stale_edit_keeps_old_token_and_requires_explicit_reload(web):
    inbox, _, client = web
    record = report(inbox)
    jobs.edit_entry(inbox, record["id"], "cne-one", changes={"headline": "Already saved"}, included=True, review_status="reviewed", expected_revision=0)
    response = client.post(f"/reports/{record['id']}/company-news/entry/cne-one", data={
        "headline": "My stale draft", "summary": "Do not lose this", "published_date": "2026-01-03",
        "included": "true", "review_status": "reviewed", "edit_revision": "0"})
    assert response.status_code == 409 and "My stale draft" in response.text
    assert 'name="edit_revision" value="0"' in response.text
    assert core.effective_entry(jobs.load_review(inbox, record["id"])["scope"]["company_news_review"]["entries"][0])["headline"] == "Already saved"


@pytest.mark.parametrize("suffix", ["", "/export.pdf", "/export.xlsx"])
def test_new_source_quote_hold_blocks_old_snapshot_outputs(web, monkeypatch, suffix):
    inbox, _, client = web
    record = report(inbox)
    import app.services.research_source_holds as holds
    monkeypatch.setattr(holds, "source_quote_hold", lambda source: {"reason": "A newly identified quote problem"} if source.get("id") == "source-one" else None)
    response = client.get(f"/reports/{record['id']}{suffix}")
    assert response.status_code == 409 and "requires verification" in response.text


def test_duplicate_same_token_worker_does_not_change_active_job_state(tmp_path):
    record = report(tmp_path, snapshot())
    token = jobs.queue_review(tmp_path, record["id"])
    def running(row, _snapshot):
        row["company_news_job"]["state"] = "running"
    jobs.mutate_review(tmp_path, record["id"], running)
    with jobs._lease(tmp_path, "run-" + record["id"]):
        jobs.run_review(tmp_path, record["id"], token, world=lambda: pytest.fail("Duplicate worker must not load sources"))
    assert jobs.load_review(tmp_path, record["id"])["company_news_job"]["state"] == "running"


def test_company_review_rejects_generic_gap_research_without_provider_call(web, monkeypatch):
    inbox, _, client = web
    record = report(inbox)
    monkeypatch.setattr(main, "_build_packet_and_coverage", lambda *_a, **_k: pytest.fail("Company review must use its checkpointed research workflow"))
    response = client.post(f"/reports/{record['id']}/research-gaps", data={"gap_keys": ["company"]})
    assert response.status_code == 422 and "company review research controls" in response.text


def test_excluded_out_of_window_lead_keeps_its_real_date_during_review(tmp_path):
    value = populated()
    value["sources"][0].update(source_version="a" * 64, eligibility="date_outside_window")
    value["entries"][0].update(entry_type="lead", included=False, published_date="2025-06-01")
    record = report(tmp_path, value)
    jobs.edit_entry(tmp_path, record["id"], "cne-one", changes={"summary": "Retained for background only."},
        included=False, review_status="reviewed", expected_revision=0)
    saved = jobs.load_review(tmp_path, record["id"])["scope"]["company_news_review"]["entries"][0]
    assert core.effective_entry(saved)["published_date"] == "2025-06-01"
    with pytest.raises(ValueError, match="saved review window"):
        jobs.edit_entry(tmp_path, record["id"], "cne-one", changes={}, included=True, review_status="reviewed", expected_revision=1)


def test_unverified_directory_identity_cannot_be_qualified_by_report_review(tmp_path):
    value = populated()
    value["companies"][0]["identity_verification_required"] = True
    value["sources"][0].update(source_version="a" * 64, eligibility="dated_finding")
    value["entries"][0].update(entry_type="lead", included=False)
    record = report(tmp_path, value)
    assert not jobs.can_qualify_lead(value, value["entries"][0])
    with pytest.raises(ValueError):
        jobs.edit_entry(tmp_path, record["id"], "cne-one", changes={}, included=True, review_status="reviewed", expected_revision=0)
