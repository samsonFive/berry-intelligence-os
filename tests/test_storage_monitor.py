from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import stat
from types import SimpleNamespace

import pytest

from app.services import storage_monitor as monitor


NOW = datetime(2026, 11, 16, 12, tzinfo=timezone.utc)


def config(tmp_path, **changes):
    lock = tmp_path / "release.lock"
    if not lock.exists():
        lock.write_bytes(b"")
    value = {
        "paths": [{"id": "production", "path": str(tmp_path)}],
        "release_locks": [str(lock)],
        "state_dir": str(tmp_path / "private"),
        "status_file": str(tmp_path / "storage" / "status.json"),
        "status_uid": os.getuid() if hasattr(os, "getuid") else 0,
        "status_gid": os.getgid() if hasattr(os, "getgid") else 0,
        **changes,
    }
    return monitor.parse_config({"monitor": value})


def snapshot(cfg, *, free=30_000_000_000, inode_free=1000, at=NOW):
    level, reasons = monitor.classify_measurement(120_000_000_000, free, 1000, inode_free, cfg)
    return {"format_version": 1, "generated_at": at.isoformat(timespec="seconds"), "level": level,
            "disks": [{"target": "production", "total_bytes": 120_000_000_000, "available_bytes": free,
                       "total_inodes": 1000, "available_inodes": inode_free, "level": level, "reasons": reasons}],
            "thresholds": {"reserve_free_bytes": cfg.reserve_free_bytes}, "stale_after_seconds": 900}


@contextmanager
def free_locks(_paths):
    yield True


def apply(cfg, value, monkeypatch, *, sender=lambda *_: True, journal=lambda *_: None):
    monkeypatch.setattr(monitor, "release_locks", free_locks)
    return monitor.run_monitor(cfg, apply=True, sampler=lambda *_args, **_kwargs: value, sender=sender, journal=journal)


@pytest.mark.parametrize(("free", "inodes", "expected", "reason"), [
    (30_000_000_000, 1000, "healthy", None),
    (20_000_000_000, 1000, "healthy", None),
    (19_999_999_999, 1000, "warning", "low_disk_space"),
    (12_000_000_000, 1000, "warning", "low_disk_space"),
    (11_999_999_999, 1000, "critical", "low_disk_space"),
    (monitor.HARD_FLOOR_BYTES - 1, 1000, "critical", "below_deployment_reserve"),
    (30_000_000_000, 49, "warning", "low_inodes"),
    (30_000_000_000, 19, "critical", "low_inodes"),
])
def test_disk_and_inode_limits_are_independent(tmp_path, free, inodes, expected, reason):
    level, reasons = monitor.classify_measurement(120_000_000_000, free, 1000, inodes, config(tmp_path))
    assert level == expected
    assert reasons == ([] if reason is None else [reason])


@pytest.mark.parametrize("changes", [
    {"reserve_free_bytes": monitor.HARD_FLOOR_BYTES - 1},
    {"warning_free_bytes": 10_000_000_000},
    {"critical_inode_percent": 5},
    {"retry_seconds": True},
    {"unknown_typo": 123},
    {"status_file": "/opt/berry-intelligence-os/demo-runtime/data/configuration/source_universe.json"},
    {"notification": {"kind": "webhook", "url": "http://example.test/token"}},
    {"notification": {"kind": "webhook", "url": "https://name:secret@example.test/token"}},
    {"notification": {"kind": "smtp", "host": "smtp.example.test", "ssl": False, "starttls": False}},
    {"notification": {"kind": "none", "url": "secret"}},
])
def test_invalid_policy_is_refused_without_echoing_values(tmp_path, changes):
    with pytest.raises(monitor.StorageMonitorError) as error:
        config(tmp_path, **changes)
    assert "secret" not in str(error.value)
    assert "example.test" not in str(error.value)


def test_dry_run_cannot_write_or_notify(tmp_path):
    cfg = config(tmp_path)
    result = monitor.run_monitor(cfg, sampler=lambda *_args, **_kwargs: snapshot(cfg, free=10_000_000_000), sender=lambda *_: pytest.fail("delivery on dryrun"), journal=lambda *_: pytest.fail("journal on dryrun"))
    assert result["status"] == "DRY_RUN" and result["event_due"]["level"] == "critical"
    assert result["writes"] is result["notification_sent"] is False
    assert not cfg.state_dir.exists() and not cfg.status_file.exists()


def test_sampling_counts_available_blocks_not_reserved_free_blocks_and_deduplicates_devices(tmp_path, monkeypatch):
    child = tmp_path / "same-filesystem"
    child.mkdir()
    cfg = config(tmp_path, paths=[{"id": "production", "path": str(tmp_path)}, {"id": "runtime", "path": str(child)}])
    monkeypatch.setattr(monitor.os, "statvfs", lambda _path: SimpleNamespace(f_blocks=100_000_000, f_frsize=4096, f_bavail=2_000_000, f_bfree=10_000_000, f_files=1000, f_favail=1000), raising=False)
    value = monitor.sample(cfg, now=NOW)
    assert len(value["disks"]) == 1
    assert value["disks"][0]["available_bytes"] == 8_192_000_000
    assert value["level"] == "critical" and value["issues"][0]["code"] == "below_deployment_reserve"


def test_state_changes_reminders_escalation_and_recovery(tmp_path):
    cfg = config(tmp_path)
    state, event = monitor.advance_state(None, snapshot(cfg), cfg)
    assert event is None
    state, event = monitor.advance_state(state, snapshot(cfg, free=15_000_000_000, at=NOW + timedelta(minutes=5)), cfg)
    assert event["level"] == "warning" and event["kind"] == "escalation"
    state.update(pending_event=None, last_delivered_at=event["at"])
    state, event = monitor.advance_state(state, snapshot(cfg, free=14_000_000_000, at=NOW + timedelta(hours=1)), cfg)
    assert event is None  # A different free-byte value alone is not a new alert.
    state, event = monitor.advance_state(state, snapshot(cfg, free=14_000_000_000, at=NOW + timedelta(hours=7)), cfg)
    assert event["kind"] == "reminder"
    state.update(pending_event=None, last_delivered_at=event["at"])
    state, event = monitor.advance_state(state, snapshot(cfg, free=10_000_000_000, at=NOW + timedelta(hours=8)), cfg)
    assert event["kind"] == "escalation" and event["level"] == "critical"
    state, event = monitor.advance_state(state, snapshot(cfg, at=NOW + timedelta(hours=9)), cfg)
    assert event["kind"] == "recovery" and event["level"] == "healthy"


def test_notification_failure_retries_same_event_without_false_success(tmp_path, monkeypatch):
    cfg = config(tmp_path, notification={"kind": "webhook", "url": "https://notify.example.test/private-token"})
    seen, journaled = [], []
    def fail(event, _transport):
        seen.append(event["id"])
        return False
    first = apply(cfg, snapshot(cfg, free=10_000_000_000), monkeypatch, sender=fail, journal=journaled.append)
    state = json.loads((cfg.state_dir / "monitor-state.json").read_text())
    assert first["notification_sent"] is False and state["delivery_state"] == "failed"
    assert "last_delivered_at" not in state
    apply(cfg, snapshot(cfg, free=10_000_000_000, at=NOW + timedelta(seconds=60)), monkeypatch, sender=lambda *_: pytest.fail("early retry"))
    result = apply(cfg, snapshot(cfg, free=10_000_000_000, at=NOW + timedelta(seconds=301)), monkeypatch, sender=lambda event, _cfg: seen.append(event["id"]) or True, journal=journaled.append)
    assert seen[0] == seen[1] and len(journaled) == 1
    assert result["notification_sent"] is True
    final = json.loads((cfg.state_dir / "monitor-state.json").read_text())
    assert final["pending_event"] is None and final["delivery_state"] == "delivered"
    public = cfg.status_file.read_text()
    assert "private-token" not in public and "notify.example.test" not in public


def test_apply_writes_private_state_and_service_readable_status(tmp_path, monkeypatch):
    cfg = config(tmp_path)
    journaled = []
    result = apply(cfg, snapshot(cfg, free=10_000_000_000), monkeypatch, journal=journaled.append)
    assert result["status"] == "SAMPLED" and len(journaled) == 1
    assert result["sample"]["delivery"]["state"] == "journaled"
    assert result["sample"]["events"][0]["id"] == result["sample"]["last_event"]["id"]
    assert result["notification_sent"] is False  # No external transport configured.
    if os.name == "posix":
        assert stat.S_IMODE(cfg.state_dir.stat().st_mode) == 0o700
        assert stat.S_IMODE((cfg.state_dir / "monitor-state.json").stat().st_mode) == 0o600
        assert stat.S_IMODE(cfg.status_file.parent.stat().st_mode) == 0o2750
        assert stat.S_IMODE(cfg.status_file.stat().st_mode) == 0o640
        assert cfg.status_file.stat().st_uid == cfg.status_uid


def test_busy_release_does_not_sample_write_or_notify(tmp_path, monkeypatch):
    cfg = config(tmp_path)
    @contextmanager
    def busy(_paths):
        yield False
    monkeypatch.setattr(monitor, "release_locks", busy)
    result = monitor.run_monitor(cfg, apply=True, sampler=lambda *_args, **_kwargs: pytest.fail("sample while release busy"), sender=lambda *_: pytest.fail("notification while busy"))
    assert result == {"status": "SKIPPED_RELEASE_BUSY", "writes": False, "notification_sent": False}
    assert not cfg.state_dir.exists() and not cfg.status_file.exists()


@pytest.mark.skipif(os.name != "posix", reason="Host uses Linux flock")
def test_actual_nonblocking_flock_skips_an_owned_release(tmp_path):
    import fcntl
    cfg = config(tmp_path)
    with cfg.release_locks[0].open("r+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        result = monitor.run_monitor(cfg, apply=True, sampler=lambda *_args, **_kwargs: pytest.fail("locked sample"))
    assert result["status"] == "SKIPPED_RELEASE_BUSY" and not cfg.status_file.exists()


def test_public_reader_distinguishes_stale_missing_and_invalid_without_echoing_private_fields(tmp_path, monkeypatch):
    cfg = config(tmp_path)
    assert monitor.read_public_status(cfg.status_file, now=NOW) == {"state": "unconfigured"}
    apply(cfg, snapshot(cfg), monkeypatch)
    assert monitor.read_public_status(cfg.status_file, now=NOW)["state"] == "fresh"
    stale = monitor.read_public_status(cfg.status_file, now=NOW + timedelta(minutes=16))
    assert stale["state"] == "stale" and stale["age_seconds"] == 960
    body = json.loads(cfg.status_file.read_text())
    body["unexpected_credentials"] = "private-token"
    cfg.status_file.write_text(json.dumps(body))
    assert "private-token" not in json.dumps(monitor.read_public_status(cfg.status_file, now=NOW))
    cfg.status_file.write_text("invalid json")
    assert monitor.read_public_status(cfg.status_file, now=NOW) == {"state": "invalid"}


def test_event_history_is_bounded_and_preserves_missed_recovery(tmp_path):
    cfg = config(tmp_path)
    state = None
    for i in range(30):
        state, event = monitor.advance_state(state, snapshot(cfg, free=10_000_000_000 if i % 2 == 0 else 30_000_000_000, at=NOW + timedelta(minutes=i * 5)), cfg)
        state.update(pending_event=None, last_delivered_at=event["at"])
    assert len(state["events"]) == 12
    assert any(e["kind"] == "recovery" for e in state["events"])
    assert len({e["id"] for e in state["events"]}) == 12


def test_public_reader_sanitizes_nested_events_and_refuses_unknown_issue_codes(tmp_path, monkeypatch):
    cfg = config(tmp_path)
    apply(cfg, snapshot(cfg, free=10_000_000_000), monkeypatch)
    body = json.loads(cfg.status_file.read_text())
    body["events"][0]["unexpected_credential"] = "private-token"
    body["events"][0]["disks"][0]["unexpected_credential"] = "private-token"
    cfg.status_file.write_text(json.dumps(body))
    public = monitor.read_public_status(cfg.status_file, now=NOW)
    assert public["state"] == "fresh" and len(public["events"]) == 1
    assert public["issues"] == [{"target": "production", "level": "critical", "code": "low_disk_space"}]
    assert "private-token" not in json.dumps(public)
    body["disks"][0]["reasons"] = ["private-token"]
    cfg.status_file.write_text(json.dumps(body))
    assert monitor.read_public_status(cfg.status_file, now=NOW) == {"state": "invalid"}


def test_corrupt_private_delivery_timestamp_is_not_exposed(tmp_path):
    cfg = config(tmp_path)
    with pytest.raises(monitor.StorageMonitorError, match="timestamp_invalid"):
        monitor.advance_state({"format_version": 1, "last_level": "healthy", "last_delivered_at": "private-token"}, snapshot(cfg), cfg)


def test_webhook_delivery_refuses_redirects_and_does_not_echo_endpoint(tmp_path, monkeypatch):
    cfg = config(tmp_path, notification={"kind": "webhook", "url": "https://notify.example.test/private-token"})
    handlers = []
    class RedirectingEndpoint:
        def open(self, request, timeout):
            assert timeout == 10 and request.get_method() == "POST"
            assert request.headers["X-berry-event-id"] == "a" * 32
            raise monitor.urllib.error.HTTPError(request.full_url, 302, "redirect", {}, None)
    def opener(handler):
        handlers.append(handler)
        return RedirectingEndpoint()
    monkeypatch.setattr(monitor.urllib.request, "build_opener", opener)
    assert monitor.deliver({"id": "a" * 32, "level": "critical"}, cfg.notification) is False
    assert len(handlers) == 1 and handlers[0].redirect_request(None, None, None, None, None, "https://other.example.test") is None


def test_smtp_delivery_requires_verified_tls_and_keeps_credentials_out_of_message(tmp_path, monkeypatch):
    cfg = config(tmp_path, notification={"kind": "smtp", "host": "smtp.example.test", "starttls": True, "ssl": False, "username": "monitor-user", "password": "private-token", "sender": "monitor@example.test", "recipients": ["operator@example.test"]})
    calls = []
    class SMTP:
        def __init__(self, host, port, **kwargs):
            assert (host, port, kwargs["timeout"]) == ("smtp.example.test", 587, 10)
        def __enter__(self):return self
        def __exit__(self, *args):return False
        def starttls(self, *, context):calls.append(("tls", context.verify_mode))
        def login(self, username, password):calls.append(("login", username, password))
        def send_message(self, message):
            calls.append(("message", message.as_string()))
    monkeypatch.setattr(monitor.smtplib, "SMTP", SMTP)
    assert monitor.deliver({"id": "a" * 32, "level": "critical"}, cfg.notification) is True
    assert calls[0][0] == "tls" and calls[0][1] == monitor.ssl.CERT_REQUIRED
    assert calls[1] == ("login", "monitor-user", "private-token")
    assert "private-token" not in calls[2][1] and "monitor-user" not in calls[2][1]


def test_symlink_status_is_refused_and_target_survives(tmp_path, monkeypatch):
    cfg = config(tmp_path)
    cfg.status_file.parent.mkdir()
    target = tmp_path / "unrelated.json"
    target.write_text("preserve me")
    try:
        cfg.status_file.symlink_to(target)
    except OSError:
        pytest.skip("Symlink creation unavailable")
    with pytest.raises(monitor.StorageMonitorError, match="symlink_refused"):
        apply(cfg, snapshot(cfg), monkeypatch)
    assert target.read_text() == "preserve me"


def test_unexpected_existing_directory_permissions_are_not_changed(tmp_path, monkeypatch):
    if os.name != "posix":
        pytest.skip("POSIX owner/mode contract")
    cfg = config(tmp_path)
    cfg.state_dir.mkdir(mode=0o755)
    with pytest.raises(monitor.StorageMonitorError, match="directory_owner_mode_invalid"):
        apply(cfg, snapshot(cfg), monkeypatch)
    assert stat.S_IMODE(cfg.state_dir.stat().st_mode) == 0o755


def test_root_private_config_is_required_on_linux(tmp_path):
    if os.name != "posix":
        pytest.skip("Linux private configuration permissions")
    path = tmp_path / "policy.json"
    path.write_text(json.dumps({"monitor": {"notification": {"kind": "none"}}}))
    path.chmod(0o644)
    with pytest.raises(monitor.StorageMonitorError, match="configuration_must_be_root_private"):
        monitor.load_config(path)
