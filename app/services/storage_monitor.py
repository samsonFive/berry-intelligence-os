"""Bounded host storage sampling and alert state; no cleanup or research calls.

The host operator installs this module with scripts/storage_monitor.py. Policy
and delivery credentials stay in a root-private configuration file. The public
status contains only measurements and delivery state, never notification config.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from email.message import EmailMessage
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import smtplib
import ssl
import stat
from typing import Any, Callable
import urllib.error
import urllib.parse
import urllib.request


UTC = timezone.utc
FORMAT_VERSION = 1
MAX_JSON_BYTES = 128 * 1024
HARD_FLOOR_BYTES = 8 * 1024**3
DEFAULT_RELEASE_LOCKS = (
    "/run/lock/berry-review.lock",
    "/opt/berry-platform-releases/brand-media-release.lock",
    "/opt/berry-platform-releases/watchlist524-release.lock",
)
LEVELS = {"healthy": 0, "warning": 1, "critical": 2}
ISSUE_CODES = {"low_disk_space", "below_deployment_reserve", "low_inodes"}
EVENT_KINDS = {"initial", "change", "escalation", "reminder", "recovery"}


class StorageMonitorError(ValueError):
    """Messages are fixed codes; never echo credentials or untrusted config."""


def need(condition: Any, code: str) -> None:
    if not condition:
        raise StorageMonitorError(code)


def _instant(value: datetime | None = None) -> datetime:
    result = value or datetime.now(UTC)
    need(result.tzinfo is not None, "timezone_required")
    return result.astimezone(UTC)


def _at(value: str) -> datetime:
    try:
        return _instant(datetime.fromisoformat(value))
    except (TypeError, ValueError):
        raise StorageMonitorError("timestamp_invalid") from None


def _absolute(value: str | Path) -> Path:
    path = Path(value)
    need(path.is_absolute() and ".." not in path.parts, "absolute_path_required")
    return path


def _safe(path: Path, *, missing: bool = False, directory: bool = False) -> None:
    for node in reversed([path, *path.parents]):
        try:
            info = node.lstat()
        except FileNotFoundError:
            need(missing, "path_missing")
            continue
        need(not stat.S_ISLNK(info.st_mode) and not getattr(node, "is_junction", lambda: False)(), "symlink_refused")
        need(stat.S_ISDIR(info.st_mode) if node != path or directory else stat.S_ISREG(info.st_mode), "path_type_invalid")


def _read_json(path: Path, *, missing: bool = False) -> dict[str, Any] | None:
    _safe(path, missing=missing)
    if not path.exists():
        return None
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    with os.fdopen(fd, "rb") as handle:
        before = os.fstat(handle.fileno())
        need(stat.S_ISREG(before.st_mode) and before.st_size <= MAX_JSON_BYTES, "json_file_bound_or_type")
        body = handle.read(MAX_JSON_BYTES + 1)
        after = os.fstat(handle.fileno())
        need((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns), "json_changed_while_reading")
    try:
        value = json.loads(body)
    except (UnicodeError, ValueError):
        raise StorageMonitorError("json_invalid") from None
    need(isinstance(value, dict), "json_object_required")
    return value


def _positive(value: Any, code: str, *, minimum: int = 1, maximum: int = 2**63 - 1) -> int:
    need(type(value) is int and minimum <= value <= maximum, code)
    return value


def _public_disk(row: Any) -> dict[str, Any]:
    need(isinstance(row, dict) and row.get("level") in LEVELS and re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", str(row.get("target", ""))), "public_status_invalid")
    total, available = row.get("total_bytes"), row.get("available_bytes")
    need(type(total) is int and total > 0 and type(available) is int and 0 <= available <= total, "public_status_invalid")
    inodes, inode_free = row.get("total_inodes"), row.get("available_inodes")
    need((inodes is None and inode_free is None) or (type(inodes) is int and inodes > 0 and type(inode_free) is int and 0 <= inode_free <= inodes), "public_status_invalid")
    reasons = row.get("reasons")
    need(isinstance(reasons, list) and all(reason in ISSUE_CODES for reason in reasons), "public_status_invalid")
    return {"target": row["target"], "total_bytes": total, "available_bytes": available, "available_percent": round(available * 100 / total, 2), "total_inodes": inodes, "available_inodes": inode_free, "available_inode_percent": round(inode_free * 100 / inodes, 2) if inodes else None, "level": row["level"], "reasons": reasons}


def _public_event(value: Any) -> dict[str, Any]:
    need(isinstance(value, dict) and re.fullmatch(r"[a-f0-9]{32}", str(value.get("id", ""))), "event_invalid")
    need(value.get("level") in LEVELS and value.get("previous_level") in {*LEVELS, None} and value.get("kind") in EVENT_KINDS, "event_invalid")
    _at(value.get("at"))
    disks = value.get("disks")
    need(isinstance(disks, list) and 1 <= len(disks) <= 8, "event_invalid")
    reserve = _positive(value.get("reserve_free_bytes"), "event_invalid", minimum=HARD_FLOOR_BYTES)
    result = {"id": value["id"], "at": value["at"], "level": value["level"], "previous_level": value.get("previous_level"), "kind": value["kind"], "disks": [_public_disk(d) for d in disks], "reserve_free_bytes": reserve}
    if value.get("journaled") is True:
        result["journaled"] = True
    return result


def _mail_address(value: Any) -> str:
    need(isinstance(value, str) and len(value) <= 254 and re.fullmatch(r"[^\s<>@]+@[^\s<>@]+", value), "mail_address_invalid")
    return value


def _notification(value: Any) -> dict[str, Any]:
    need(isinstance(value, dict), "notification_object_required")
    kind = value.get("kind", "none")
    need(kind in {"none", "webhook", "smtp"}, "notification_kind_invalid")
    if kind == "none":
        need(set(value) <= {"kind"}, "disabled_notification_has_options")
        return {"kind": "none"}
    timeout = _positive(value.get("timeout_seconds", 10), "notification_timeout_invalid", maximum=20)
    if kind == "webhook":
        need(set(value) <= {"kind", "url", "timeout_seconds"}, "notification_options_invalid")
        url = value.get("url")
        need(isinstance(url, str) and len(url) <= 4096 and not any(ord(c) < 32 for c in url), "webhook_url_invalid")
        try:
            parts = urllib.parse.urlsplit(url)
            valid = parts.scheme == "https" and bool(parts.hostname) and parts.username is None and parts.password is None and parts.port in {None, 443} and not parts.fragment
        except ValueError:
            valid = False
        need(valid, "webhook_https_required")
        return {"kind": kind, "url": url, "timeout_seconds": timeout}
    need(set(value) <= {"kind", "host", "port", "ssl", "starttls", "username", "password", "sender", "recipients", "timeout_seconds"}, "notification_options_invalid")
    host = value.get("host")
    need(isinstance(host, str) and re.fullmatch(r"[A-Za-z0-9.-]{1,253}", host), "smtp_host_invalid")
    use_ssl, starttls = value.get("ssl", False), value.get("starttls", True)
    need(type(use_ssl) is bool and type(starttls) is bool and use_ssl != starttls, "smtp_verified_tls_required")
    username, password = value.get("username", ""), value.get("password", "")
    need(isinstance(username, str) and isinstance(password, str) and bool(username) == bool(password), "smtp_credentials_invalid")
    recipients = value.get("recipients")
    need(isinstance(recipients, list) and 1 <= len(recipients) <= 5, "smtp_recipients_invalid")
    return {"kind": kind, "host": host, "port": _positive(value.get("port", 465 if use_ssl else 587), "smtp_port_invalid", maximum=65535), "ssl": use_ssl, "starttls": starttls, "username": username, "password": password, "sender": _mail_address(value.get("sender")), "recipients": [_mail_address(r) for r in recipients], "timeout_seconds": timeout}


@dataclass(frozen=True)
class MonitorConfig:
    paths: tuple[tuple[str, Path], ...]
    state_dir: Path
    status_file: Path
    release_locks: tuple[Path, ...]
    warning_free_bytes: int
    critical_free_bytes: int
    reserve_free_bytes: int
    warning_inode_percent: int
    critical_inode_percent: int
    reminder_seconds: int
    retry_seconds: int
    stale_after_seconds: int
    status_uid: int
    status_gid: int
    notification: dict[str, Any]


def parse_config(payload: dict[str, Any]) -> MonitorConfig:
    value = payload.get("monitor", payload)
    need(isinstance(value, dict), "monitor_object_required")
    allowed = {"paths", "state_dir", "status_file", "release_locks", "warning_free_bytes", "critical_free_bytes", "reserve_free_bytes", "warning_inode_percent", "critical_inode_percent", "reminder_seconds", "retry_seconds", "stale_after_seconds", "status_uid", "status_gid", "notification"}
    need(set(value) <= allowed, "monitor_options_invalid")
    rows = value.get("paths", [{"id": "production", "path": "/"}])
    need(isinstance(rows, list) and 1 <= len(rows) <= 8, "monitor_paths_invalid")
    paths = []
    for row in rows:
        need(isinstance(row, dict) and set(row) == {"id", "path"}, "monitor_path_invalid")
        need(isinstance(row["id"], str) and re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", row["id"]), "monitor_target_id_invalid")
        paths.append((row["id"], _absolute(row["path"])))
    need(len({name for name, _ in paths}) == len(paths), "monitor_target_duplicate")
    locks = value.get("release_locks", list(DEFAULT_RELEASE_LOCKS))
    need(isinstance(locks, list) and 1 <= len(locks) <= 8, "release_locks_invalid")
    lock_paths = tuple(_absolute(p) for p in locks)
    need(len(set(lock_paths)) == len(lock_paths), "release_lock_duplicate")
    warning = _positive(value.get("warning_free_bytes", 20_000_000_000), "warning_bytes_invalid")
    critical = _positive(value.get("critical_free_bytes", 12_000_000_000), "critical_bytes_invalid")
    reserve = _positive(value.get("reserve_free_bytes", HARD_FLOOR_BYTES), "reserve_bytes_invalid", minimum=HARD_FLOOR_BYTES)
    inode_warning = _positive(value.get("warning_inode_percent", 5), "warning_inodes_invalid", maximum=99)
    inode_critical = _positive(value.get("critical_inode_percent", 2), "critical_inodes_invalid", maximum=99)
    need(warning > critical > reserve and inode_warning > inode_critical, "threshold_order_invalid")
    state_dir = _absolute(value.get("state_dir", "/var/lib/berry-storage-controls"))
    status_file = _absolute(value.get("status_file", "/opt/berry-intelligence-os/demo-runtime/inbox/operations/storage/status.json"))
    need(status_file.name == "status.json" and status_file.parent.name == "storage", "dedicated_storage_status_path_required")
    need(status_file != state_dir / "monitor-state.json" and not status_file.is_relative_to(state_dir), "public_private_state_overlap")
    return MonitorConfig(tuple(paths), state_dir, status_file, lock_paths, warning, critical, reserve, inode_warning, inode_critical, _positive(value.get("reminder_seconds", 21600), "reminder_invalid", minimum=300, maximum=604800), _positive(value.get("retry_seconds", 300), "retry_invalid", minimum=60, maximum=86400), _positive(value.get("stale_after_seconds", 900), "stale_after_invalid", minimum=300, maximum=86400), _positive(value.get("status_uid", 1000), "status_uid_invalid", minimum=0, maximum=2**31 - 1), _positive(value.get("status_gid", 1000), "status_gid_invalid", minimum=0, maximum=2**31 - 1), _notification(value.get("notification", {"kind": "none"})))


def load_config(path: Path) -> MonitorConfig:
    path = _absolute(path)
    _safe(path)
    info = path.stat()
    if os.name == "posix":
        need(info.st_uid == 0 and not stat.S_IMODE(info.st_mode) & 0o077, "configuration_must_be_root_private")
    return parse_config(_read_json(path) or {})


def classify_measurement(total_bytes: int, available_bytes: int, total_inodes: int | None, available_inodes: int | None, config: MonitorConfig) -> tuple[str, list[str]]:
    need(type(total_bytes) is int and total_bytes > 0 and type(available_bytes) is int and 0 <= available_bytes <= total_bytes, "disk_measurement_invalid")
    reasons, level = [], "healthy"
    if available_bytes < config.reserve_free_bytes:
        reasons.append("below_deployment_reserve")
        level = "critical"
    elif available_bytes < config.critical_free_bytes:
        reasons.append("low_disk_space")
        level = "critical"
    elif available_bytes < config.warning_free_bytes:
        reasons.append("low_disk_space")
        level = "warning"
    if total_inodes is not None or available_inodes is not None:
        need(type(total_inodes) is int and total_inodes > 0 and type(available_inodes) is int and 0 <= available_inodes <= total_inodes, "inode_measurement_invalid")
        percentage = available_inodes * 100 / total_inodes
        if percentage < config.critical_inode_percent:
            reasons.append("low_inodes")
            level = "critical"
        elif percentage < config.warning_inode_percent:
            reasons.append("low_inodes")
            if level == "healthy":
                level = "warning"
    return level, reasons


def sample(config: MonitorConfig, *, now: datetime | None = None) -> dict[str, Any]:
    disks, devices = [], set()
    for name, path in config.paths:
        _safe(path, directory=True)
        device = path.stat().st_dev
        if device in devices:
            continue
        devices.add(device)
        fs = os.statvfs(path)
        total, available = fs.f_blocks * fs.f_frsize, fs.f_bavail * fs.f_frsize
        total_inodes, available_inodes = (fs.f_files, fs.f_favail) if fs.f_files else (None, None)
        level, reasons = classify_measurement(total, available, total_inodes, available_inodes, config)
        disks.append({"target": name, "total_bytes": total, "available_bytes": available, "available_percent": round(available * 100 / total, 2), "total_inodes": total_inodes, "available_inodes": available_inodes, "available_inode_percent": round(available_inodes * 100 / total_inodes, 2) if total_inodes else None, "level": level, "reasons": reasons})
    return {"format_version": FORMAT_VERSION, "generated_at": _instant(now).isoformat(timespec="seconds"), "level": max((d["level"] for d in disks), key=LEVELS.__getitem__), "disks": disks, "issues": [{"target": d["target"], "level": d["level"], "code": reason} for d in disks for reason in d["reasons"]], "thresholds": {"warning_free_bytes": config.warning_free_bytes, "critical_free_bytes": config.critical_free_bytes, "reserve_free_bytes": config.reserve_free_bytes, "warning_inode_percent": config.warning_inode_percent, "critical_inode_percent": config.critical_inode_percent}, "stale_after_seconds": config.stale_after_seconds}


def advance_state(previous: dict[str, Any] | None, snapshot: dict[str, Any], config: MonitorConfig) -> tuple[dict[str, Any], dict[str, Any] | None]:
    instant = _at(snapshot["generated_at"])
    need(snapshot.get("format_version") == FORMAT_VERSION and snapshot.get("level") in LEVELS and isinstance(snapshot.get("disks"), list) and bool(snapshot["disks"]), "snapshot_invalid")
    for disk in snapshot["disks"]:
        need(disk.get("level") in LEVELS and isinstance(disk.get("target"), str) and isinstance(disk.get("reasons"), list), "snapshot_invalid")
    signature = hashlib.sha256(json.dumps([(d["target"], d["level"], d["reasons"]) for d in snapshot["disks"]], sort_keys=True).encode()).hexdigest()
    state = dict(previous or {"format_version": FORMAT_VERSION})
    need(state.get("format_version") == FORMAT_VERSION and state.get("last_level", "healthy") in LEVELS, "monitor_state_invalid")
    need(state.get("delivery_state", "not_due") in {"not_due", "journaled", "delivered", "failed"}, "monitor_state_invalid")
    for timestamp in ("last_delivered_at", "next_retry_at"):
        if state.get(timestamp) is not None:
            _at(state[timestamp])
    old_level, level = state.get("last_level"), snapshot["level"]
    event = None
    pending = state.get("pending_event")
    if pending is not None:
        pending = _public_event(pending)
        state["pending_event"] = pending
    changed = old_level is not None and (old_level != level or state.get("last_signature") != signature)
    last_delivered = state.get("last_delivered_at")
    reminder = level != "healthy" and last_delivered is not None and (instant - _at(last_delivered)).total_seconds() >= config.reminder_seconds
    if changed or (old_level is None and level != "healthy") or (pending is None and reminder):
        kind = "recovery" if level == "healthy" and old_level != "healthy" else "escalation" if old_level is not None and LEVELS[level] > LEVELS[old_level] else "reminder" if reminder and not changed else "change" if old_level is not None else "initial"
        event = {"id": hashlib.sha256((snapshot["generated_at"] + ":" + signature + ":" + kind).encode()).hexdigest()[:32], "at": snapshot["generated_at"], "level": level, "previous_level": old_level, "kind": kind, "disks": snapshot["disks"], "reserve_free_bytes": config.reserve_free_bytes}
        state["pending_event"] = event
        state["next_retry_at"] = snapshot["generated_at"]
    elif pending is not None and instant >= _at(state.get("next_retry_at", pending["at"])):
        event = pending
    state.update({"last_level": level, "last_signature": signature, "last_observed_at": snapshot["generated_at"]})
    history = state.get("events", [])
    need(isinstance(history, list) and len(history) <= 12, "event_history_invalid")
    history = [_public_event(e) for e in history]
    if event is not None and not any(e["id"] == event["id"] for e in history):
        history = [*history, dict(event)][-12:]
    state["events"] = history
    return state, event


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def deliver(event: dict[str, Any], notification: dict[str, Any]) -> bool:
    """Delivery config never enters status/receipts; redirects cannot leak tokens."""
    kind = notification["kind"]
    if kind == "none":
        return True  # Host journal delivery remains enabled; external push is off.
    try:
        if kind == "webhook":
            request = urllib.request.Request(notification["url"], data=json.dumps(event, separators=(",", ":")).encode(), headers={"Content-Type": "application/json", "X-Berry-Event-ID": event["id"]}, method="POST")
            with urllib.request.build_opener(_NoRedirect()).open(request, timeout=notification["timeout_seconds"]) as response:
                return 200 <= response.status < 300
        message = EmailMessage()
        message["From"] = notification["sender"]
        message["To"] = ", ".join(notification["recipients"])
        message["Subject"] = "Berry storage: " + event["level"]
        message["Message-ID"] = "<berry-storage-" + event["id"] + "@localhost>"
        message.set_content(json.dumps(event, indent=2))
        context = ssl.create_default_context()
        smtp_type = smtplib.SMTP_SSL if notification["ssl"] else smtplib.SMTP
        kwargs = {"timeout": notification["timeout_seconds"]}
        if notification["ssl"]:
            kwargs["context"] = context
        with smtp_type(notification["host"], notification["port"], **kwargs) as smtp:
            if notification["starttls"]:
                smtp.starttls(context=context)
            if notification["username"]:
                smtp.login(notification["username"], notification["password"])
            smtp.send_message(message)
        return True
    except (OSError, ValueError, smtplib.SMTPException, urllib.error.URLError):
        return False


def journal_event(event: dict[str, Any]) -> None:
    import syslog as _syslog
    priority = _syslog.LOG_ERR if event["level"] == "critical" else _syslog.LOG_WARNING if event["level"] == "warning" else _syslog.LOG_NOTICE
    _syslog.openlog("berry-storage-monitor")
    _syslog.syslog(priority, json.dumps({"event": "storage_alert", **event}, separators=(",", ":")))


@contextmanager
def release_locks(paths: tuple[Path, ...]):
    import fcntl
    handles = []
    acquired = False
    try:
        try:
            for path in paths:
                _safe(path)
                fd = os.open(path, os.O_RDWR | os.O_NOFOLLOW)
                handles.append(fd)
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            acquired = True
        except BlockingIOError:
            pass
        yield acquired
    finally:
        for fd in reversed(handles):
            os.close(fd)


def _directory(path: Path, *, uid: int, gid: int, mode: int) -> None:
    _safe(path, missing=True, directory=True)
    _safe(path.parent, directory=True)
    if os.name == "posix":
        parent = os.open(path.anchor, os.O_RDONLY | os.O_DIRECTORY)
        try:
            for component in path.parent.parts[1:]:
                child = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
                os.close(parent)
                parent = child
            created = False
            try:
                os.mkdir(path.name, mode=0o700, dir_fd=parent)
                created = True
            except FileExistsError:
                pass
            fd = os.open(path.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
            try:
                if created:
                    os.fchown(fd, uid, gid)
                    os.fchmod(fd, mode)
                    os.fsync(parent)
                info = os.fstat(fd)
                need((info.st_uid, info.st_gid, stat.S_IMODE(info.st_mode)) == (uid, gid, mode), "directory_owner_mode_invalid")
            finally:
                os.close(fd)
        finally:
            os.close(parent)
        return
    created = not path.exists()
    path.mkdir(exist_ok=True, mode=mode)
    _safe(path, directory=True)
    if created:
        if hasattr(os, "chown"):
            os.chown(path, uid, gid, follow_symlinks=False)
        path.chmod(mode)
    if os.name == "posix":
        info = path.stat()
        need((info.st_uid, info.st_gid, stat.S_IMODE(info.st_mode)) == (uid, gid, mode), "directory_owner_mode_invalid")


def atomic_json(path: Path, value: dict[str, Any], *, uid: int, gid: int, mode: int) -> None:
    """Atomic bounded writes; a directory descriptor confines the final rename."""
    body = (json.dumps(value, sort_keys=True, indent=2) + "\n").encode()
    need(len(body) <= MAX_JSON_BYTES, "state_exceeds_bound")
    _safe(path, missing=True)
    name = ".storage-monitor-" + secrets.token_hex(8)
    if os.name == "posix":
        # Open each component without following links, including intermediate
        # ancestors that may be writable by the application service account.
        parent = os.open(path.anchor, os.O_RDONLY | os.O_DIRECTORY)
        try:
            for component in path.parent.parts[1:]:
                child = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
                os.close(parent)
                parent = child
            try:
                info = os.stat(path.name, dir_fd=parent, follow_symlinks=False)
                need(stat.S_ISREG(info.st_mode), "state_target_not_regular")
                need((info.st_uid, info.st_gid, stat.S_IMODE(info.st_mode)) == (uid, gid, mode), "state_target_owner_mode_invalid")
            except FileNotFoundError:
                pass
            fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode, dir_fd=parent)
            try:
                with os.fdopen(fd, "wb") as handle:
                    handle.write(body)
                    os.fchown(handle.fileno(), uid, gid)
                    os.fchmod(handle.fileno(), mode)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(name, path.name, src_dir_fd=parent, dst_dir_fd=parent)
                os.fsync(parent)
            finally:
                try:
                    os.unlink(name, dir_fd=parent)
                except FileNotFoundError:
                    pass
        finally:
            os.close(parent)
    else:  # Portable local tests; the production CLI refuses apply on Windows.
        temporary = path.parent / name
        try:
            with temporary.open("xb") as handle:
                handle.write(body)
                handle.flush()
                os.fsync(handle.fileno())
            _safe(path, missing=True)
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)


def run_monitor(config: MonitorConfig, *, apply: bool = False, now: datetime | None = None, sampler: Callable = sample, sender: Callable = deliver, journal: Callable = journal_event) -> dict[str, Any]:
    def check() -> dict[str, Any]:
        snapshot = sampler(config, now=now)
        previous = _read_json(config.state_dir / "monitor-state.json", missing=True)
        state, event = advance_state(previous, snapshot, config)
        if not apply:
            return {"status": "DRY_RUN", "sample": snapshot, "event_due": event, "notification_kind": config.notification["kind"], "writes": False, "notification_sent": False}
        _safe(config.status_file, missing=True)
        private_uid = os.geteuid() if hasattr(os, "geteuid") else 0
        private_gid = os.getegid() if hasattr(os, "getegid") else 0
        _directory(config.state_dir, uid=private_uid, gid=private_gid, mode=0o700)
        _directory(config.status_file.parent, uid=config.status_uid, gid=config.status_gid, mode=0o2750)
        # Save pending delivery before attempting it. A failed notification does
        # not become success, and a retry uses the same event id.
        atomic_json(config.state_dir / "monitor-state.json", state, uid=private_uid, gid=private_gid, mode=0o600)
        delivered = False
        if event is not None:
            if not event.get("journaled"):
                journal(event)
                event["journaled"] = True
            delivered = bool(sender(event, config.notification))
            if delivered:
                state.update({"last_delivered_at": snapshot["generated_at"], "last_event": event, "pending_event": None, "delivery_state": "journaled" if config.notification["kind"] == "none" else "delivered"})
                state.pop("next_retry_at", None)
            else:
                from datetime import timedelta
                state.update({"pending_event": event, "next_retry_at": (_at(snapshot["generated_at"]) + timedelta(seconds=config.retry_seconds)).isoformat(timespec="seconds"), "delivery_state": "failed"})
            atomic_json(config.state_dir / "monitor-state.json", state, uid=private_uid, gid=private_gid, mode=0o600)
        public = {**snapshot, "delivery": {"kind": config.notification["kind"], "state": state.get("delivery_state", "not_due"), "last_delivered_at": state.get("last_delivered_at"), "pending_event_id": (state.get("pending_event") or {}).get("id"), "next_retry_at": state.get("next_retry_at")}, "last_event": _public_event(state["last_event"]) if state.get("last_event") else None, "events": state["events"]}
        atomic_json(config.status_file, public, uid=config.status_uid, gid=config.status_gid, mode=0o640)
        return {"status": "SAMPLED", "sample": public, "event_due": event is not None, "notification_sent": delivered and config.notification["kind"] != "none", "writes": True}
    if not apply:
        return check()
    with release_locks(config.release_locks) as acquired:
        if not acquired:
            return {"status": "SKIPPED_RELEASE_BUSY", "writes": False, "notification_sent": False}
        return check()


def read_public_status(path: Path, *, now: datetime | None = None, maximum_age_seconds: int = 900) -> dict[str, Any]:
    """Safe optional consumer for an ops UI or Codex's private SSH status read."""
    try:
        value = _read_json(path, missing=True)
        if value is None:
            return {"state": "unconfigured"}
        need(value.get("format_version") == FORMAT_VERSION and value.get("level") in LEVELS and isinstance(value.get("disks"), list) and 1 <= len(value["disks"]) <= 8, "public_status_invalid")
        age = (_instant(now) - _at(value["generated_at"])).total_seconds()
        need(age >= -60, "public_status_from_future")
        # Return only known safe fields; arbitrary extra JSON never leaks into
        # a UI or alert response even if a local operator added private fields.
        disks = [_public_disk(row) for row in value["disks"]]
        history = value.get("events", [])
        need(isinstance(history, list) and len(history) <= 12, "public_status_invalid")
        return {"state": "stale" if age > maximum_age_seconds else "fresh", "format_version": FORMAT_VERSION, "generated_at": value["generated_at"], "age_seconds": max(0, int(age)), "level": value["level"], "disks": disks, "issues": [{"target": d["target"], "level": d["level"], "code": r} for d in disks for r in d["reasons"]], "events": [_public_event(e) for e in history], "last_event": _public_event(value["last_event"]) if value.get("last_event") else None}
    except (OSError, StorageMonitorError, TypeError, KeyError):
        return {"state": "invalid"}
