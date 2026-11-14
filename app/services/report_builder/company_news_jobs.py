"""Resumable company research inside the existing private report record.

Only explicit POST actions schedule work. Kernel leases prevent duplicate
workers; short state leases preserve analyst edits at every checkpoint.
"""
from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from datetime import UTC, date, datetime
import os
from pathlib import Path
import re
import secrets
import time
from typing import Any

from app.services.analyst_state_io import atomic_json
from app.services.report_builder import reports_store

REPORT_TYPE = "company_news_review"
_ID = re.compile(r"rp-[a-f0-9]{16}\Z")
BATCH_SECONDS = 20 * 60


class ReviewBusy(ValueError):
    pass


def _now():
    return datetime.now(UTC).isoformat(timespec="seconds")


def _check_id(report_id):
    if not isinstance(report_id, str) or not _ID.fullmatch(report_id):
        raise ValueError("Choose an existing company news report")


@contextmanager
def _lease(inbox, name, *, create=True, blocking=False):
    folder = reports_store.reports_dir(inbox) / ".company-news-locks"
    if create:
        folder.mkdir(parents=True, exist_ok=True)
    path = folder / (name + ".lock")
    if path.is_symlink() or folder.is_symlink():
        raise ReviewBusy("Report lock is unavailable")
    if not create and not path.exists():
        yield
        return
    descriptor = os.open(path, os.O_RDWR | (os.O_CREAT if create else 0) | getattr(os, "O_NOFOLLOW", 0), 0o600)
    locked = False
    try:
        if os.name == "nt":
            import msvcrt
            if not create and os.fstat(descriptor).st_size == 0:
                yield
                return
            if create and os.fstat(descriptor).st_size == 0:
                os.write(descriptor, b"0")
            os.lseek(descriptor, 0, os.SEEK_SET)
            try:
                msvcrt.locking(descriptor, msvcrt.LK_LOCK if blocking else msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                raise ReviewBusy("This report is already being updated") from exc
        else:
            import fcntl
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB))
            except BlockingIOError as exc:
                raise ReviewBusy("This report is already being updated") from exc
        locked = True
        yield
    finally:
        if locked:
            if os.name == "nt":
                import msvcrt
                os.lseek(descriptor, 0, os.SEEK_SET)
                msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def load_review(inbox, report_id):
    _check_id(report_id)
    record = reports_store.load_report(inbox, report_id)
    if not record or record.get("report_type") != REPORT_TYPE:
        raise ValueError("Company news report not found")
    if not isinstance((record.get("scope") or {}).get("company_news_review"), dict):
        raise ValueError("Company news review data is unavailable")
    return record


def mutate_review(inbox, report_id, action):
    _check_id(report_id)
    with _lease(inbox, "state-" + report_id, blocking=True):
        record = load_review(inbox, report_id)
        action(record, record["scope"]["company_news_review"])
        record["updated_at"] = _now()
        record["revision"] = int(record.get("revision", 0)) + 1
        atomic_json(reports_store.reports_dir(inbox) / (report_id + ".json"), record)
        return record


def worker_active(inbox, report_id):
    _check_id(report_id)
    try:
        with _lease(inbox, "run-" + report_id, create=False):
            return False
    except ReviewBusy:
        return True


def queue_review(inbox, report_id):
    _check_id(report_id)
    token = secrets.token_hex(12)

    def queue(record, snapshot):
        if record.get("status") == "archived":
            raise ValueError("An archived review cannot run research")
        from app.services.report_builder.company_news import next_company_key
        if next_company_key(snapshot) is None:
            raise ValueError("All companies have been attempted. Refresh as a new version to research again.")
        record["company_news_job"] = {"state": "queued", "token": token,
            "queued_at": _now(), "cancel_requested": False,
            "message": "Research queued; each company is saved as it finishes."}
    # Checking and queuing under the same kernel lease closes the gap between
    # two POSTs and a worker starting. An active worker can never be superseded.
    with _lease(inbox, "run-" + report_id):
        mutate_review(inbox, report_id, queue)
    return token


def pause_review(inbox, report_id):
    def pause(record, snapshot):
        job = record.setdefault("company_news_job", {})
        job["cancel_requested"] = True
        if job.get("state") not in {"running", "queued"}:
            job["state"] = "paused"
        job["message"] = "Pause requested. The current company will finish before research stops."
    return mutate_review(inbox, report_id, pause)


def checkpoint(inbox, report_id, snapshot, token):
    def save(record, previous):
        if record.get("company_news_job", {}).get("token") != token:
            raise ReviewBusy("This research batch has been superseded")
        latest = {row["id"]: row for row in previous.get("entries", [])}
        saved = deepcopy(snapshot)
        for entry in saved.get("entries", []):
            old = latest.get(entry.get("id"))
            if old:
                for key in ("edits", "included", "review_status", "edit_revision", "edited_at", "manual_qualification"):
                    if key in old:
                        entry[key] = deepcopy(old[key])
        record["scope"]["company_news_review"] = saved
        job = record["company_news_job"]
        job["heartbeat_at"] = _now()
        job["current_company"] = None
    return mutate_review(inbox, report_id, save)


def run_review(inbox, report_id, token, *, world, research=None, max_seconds=BATCH_SECONDS):
    """One explicitly requested batch, resumable after pause/restart/budget.

    The batch budget is checked between bounded company operations. No worker
    retries a finished company or replaces a prior report version.
    """
    from app.services.report_builder import company_news
    research = research or company_news.research_one_company
    try:
        with _lease(inbox, "run-" + report_id), _lease(inbox, "research-worker"):
            record = load_review(inbox, report_id)
            if record.get("company_news_job", {}).get("token") != token:
                return
            def start(row, snapshot):
                row["company_news_job"].update(state="running", started_at=_now(), heartbeat_at=_now(), message="Searching platform sources first, then public gaps.")
            mutate_review(inbox, report_id, start)
            started = time.monotonic()
            world_data = world()
            entities, archive, data_dir = world_data[:3]
            if len(world_data) > 3:
                context = world_data[3]
                def preparation(row, snapshot):
                    snapshot.update({key: context[key] for key in ("excluded_source_urls", "archive_index_unavailable") if key in context})
                mutate_review(inbox, report_id, preparation)
            archive = company_news.prepare_archive_records(archive, inbox)
            while True:
                record = load_review(inbox, report_id)
                job = record.get("company_news_job", {})
                if job.get("token") != token:
                    return
                snapshot = record["scope"]["company_news_review"]
                key = company_news.next_company_key(snapshot)
                if job.get("cancel_requested") or record.get("status") == "archived":
                    state, message = "paused", "Research paused; completed companies and edits are saved."
                    break
                if key is None:
                    state, message = "complete", "Research batch finished. Review findings and coverage before sharing."
                    break
                if time.monotonic() - started >= max_seconds:
                    state, message = "paused", "Batch time budget reached; resume to research the remaining companies."
                    break
                def current(row, _snapshot):
                    row["company_news_job"].update(current_company=key, heartbeat_at=_now())
                mutate_review(inbox, report_id, current)
                updated = research(snapshot, key, entities=entities, archive_records=archive, inbox_dir=inbox, data_dir=data_dir)
                checkpoint(inbox, report_id, updated, token)
            def finish(row, _snapshot):
                row["company_news_job"].update(state=state, message=message, completed_at=_now(), current_company=None)
            mutate_review(inbox, report_id, finish)
    except ReviewBusy:
        if worker_active(inbox, report_id):
            return
        # Another batch owns the runtime. Never steal its lease or retry it.
        def waiting(row, _snapshot):
            if row.get("company_news_job", {}).get("token") == token:
                row["company_news_job"].update(state="waiting", message="Another review is running. Resume this review when it finishes.")
        mutate_review(inbox, report_id, waiting)
    except Exception:
        # Provider/reader errors must not expose credentials or raw responses.
        def failed(row, _snapshot):
            if row.get("company_news_job", {}).get("token") == token:
                row["company_news_job"].update(state="interrupted", current_company=None,
                    message="Research stopped unexpectedly. Completed findings are saved; resume the remaining companies.")
        mutate_review(inbox, report_id, failed)


def progress(inbox, record):
    snapshot = record["scope"]["company_news_review"]
    companies = snapshot.get("companies", [])
    job = deepcopy(record.get("company_news_job") or {})
    active = worker_active(inbox, record["id"])
    if job.get("state") == "running" and not active:
        job.update(state="interrupted", message="The worker stopped. Resume to continue with saved progress.")
    if job.get("state") == "queued" and not active:
        try:
            age = (datetime.now(UTC) - datetime.fromisoformat(job["queued_at"])).total_seconds()
        except (ValueError, KeyError, TypeError):
            age = 31
        if age > 30:
            job.update(state="interrupted", message="The queued worker did not start. Resume to continue with saved progress.")
    job.pop("token", None)
    return {**job, "worker_active": active, "total": len(companies), "snapshot_status": snapshot.get("status"),
        "finished": sum(row.get("disposition") != "pending" for row in companies),
        "companies": [{key: row.get(key) for key in ("key", "requested_name", "canonical_name", "resolution", "disposition", "archive_status", "web_status")} for row in companies],
        "entry_count": len(snapshot.get("entries", [])), "included_count": sum(bool(row.get("included")) for row in snapshot.get("entries", []))}


def can_qualify_lead(snapshot, entry):
    allowed = {"dated_finding", "background", "editorial_verification", "undated", "date_outside_window"}
    sources = {row["id"]: row for row in snapshot.get("sources", [])}
    references = entry.get("source_ids") or []
    company = next((row for row in snapshot.get("companies", []) if row.get("key") == entry.get("company_key")), {})
    identity_ready = bool(company and company.get("resolution") == "resolved" and not company.get("identity_verification_required"))
    return bool(identity_ready and entry.get("company_id") and references and all(
        key in sources and sources[key].get("excerpt") and sources[key].get("source_version")
        and sources[key].get("eligibility") in allowed for key in references))


def edit_entry(inbox, report_id, entry_id, *, changes, included, review_status, expected_revision):
    allowed = {"headline", "summary", "news_angle", "qualification", "published_date", "event_date"}
    if set(changes) - allowed or any(not isinstance(v, str) or len(v) > 6000 for v in changes.values()):
        raise ValueError("Use the supported report text fields (up to 6,000 characters each)")
    if review_status not in {"unreviewed", "reviewed"}:
        raise ValueError("Choose a report review state")
    def edit(record, snapshot):
        entry = next((row for row in snapshot.get("entries", []) if row.get("id") == entry_id), None)
        if entry is None:
            raise ValueError("Development not found")
        if int(entry.get("edit_revision", 0)) != expected_revision:
            raise ReviewBusy("This development changed. Reload it before saving your edit.")
        from app.services.report_builder.company_news import effective_entry
        merged = {**entry, "edits": {**entry.get("edits", {}), **changes}}
        candidate = effective_entry(merged)
        value = candidate.get("published_date")
        if value:
            try:
                parsed = date.fromisoformat(value)
            except ValueError as exc:
                raise ValueError("Publication date must be YYYY-MM-DD") from exc
            if value != parsed.isoformat():
                raise ValueError("Publication date must be YYYY-MM-DD")
            if included and not snapshot["from_date"] <= parsed.isoformat() <= snapshot["through_date"]:
                raise ValueError("Publication date must stay inside the saved review window")
        if included and not value:
            raise ValueError("An included development needs a verified publication date")
        if included and not candidate.get("headline", "").strip():
            raise ValueError("An included development needs a headline")
        event = candidate.get("event_date", "")
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", event):
            try:
                date.fromisoformat(event)
            except ValueError as exc:
                raise ValueError("Use a valid event date or describe the qualified event timing") from exc
        if included and entry.get("entry_type") != "development":
            if review_status != "reviewed" or not candidate.get("summary", "").strip() or not can_qualify_lead(snapshot, entry):
                raise ValueError("A reporting lead needs an inspected source, resolved identity, publication date, summary and explicit report review before inclusion")
            entry["manual_qualification"] = {"kind": "report_only", "qualified_at": _now(),
                "note": "Analyst included this reporting lead after source review; canonical source trust is unchanged."}
        elif entry.get("entry_type") != "development":
            entry.pop("manual_qualification", None)
        entry["edits"] = merged["edits"]
        entry.update(included=bool(included), review_status=review_status,
            edit_revision=int(entry.get("edit_revision", 0)) + 1, edited_at=_now())
    return mutate_review(inbox, report_id, edit)
