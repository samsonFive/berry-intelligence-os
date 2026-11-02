"""Validation-branch-only network guard; never part of a platform release.

Checks Python's main-process TCP connect boundary. It does not claim to
intercept OS DNS resolution or independent child-process networking.
"""
from collections import Counter
import ipaddress
import json
import os
from pathlib import Path
import socket

import pytest

for _key in ("PERPLEXITY_API_KEY", "ANTHROPIC_API_KEY", "OPENAI_API_KEY",
             "FIRECRAWL_API_KEY", "APIFY_API_TOKEN", "YOUTUBE_API_KEY"):
    os.environ[_key] = ""
for _key in ("BIOS_RUNTIME_DIR", "BIOS_DATA_DIR", "BIOS_INBOX_DIR", "BIOS_BASIC_AUTH",
             "BIOS_REVIEW_USERNAME", "BIOS_REVIEW_PASSWORD", "BIOS_SESSION_SECRET"):
    os.environ.pop(_key, None)
os.environ.update(ENABLE_SOURCE_POLLING="false", ENABLE_PERPLEXITY_PULSE="false",
                  BIOS_SOCIAL_MANUAL_COLLECTION="false")

_connect = socket.socket.connect
_connect_ex = socket.socket.connect_ex
_blocked: list[str] = []


def _allowed(sock, address):
    if getattr(sock, "family", None) == getattr(socket, "AF_UNIX", None):
        return True
    if not isinstance(address, tuple) or not address:
        return False
    host = str(address[0]).split("%", 1)[0]
    if host in {"localhost", "0.0.0.0"}:
        return True
    try:
        parsed = ipaddress.ip_address(host)
        return parsed.is_loopback or bool(
            getattr(parsed, "ipv4_mapped", None) and parsed.ipv4_mapped.is_loopback
        )
    except ValueError:
        return False


def _refuse():
    _blocked.append(os.environ.get("PYTEST_CURRENT_TEST", "collection or background worker"))
    raise AssertionError("External connection refused during closeout validation")


def _guarded_connect(sock, address):
    if not _allowed(sock, address):
        _refuse()
    return _connect(sock, address)


def _guarded_connect_ex(sock, address):
    if not _allowed(sock, address):
        _refuse()
    return _connect_ex(sock, address)


socket.socket.connect = _guarded_connect
socket.socket.connect_ex = _guarded_connect_ex


def pytest_sessionfinish(session, exitstatus):
    counts = dict(sorted(Counter(_blocked).items()))
    result = {"test_exitstatus": int(exitstatus),
              "external_connect_attempts_in_main_process": len(_blocked),
              "attempts_by_test": counts, "real_provider_keys_cleared": True,
              "validation_only": True, "production_changed": False}
    folder = Path("inbox/closeout-offline-ci")
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    reporter = session.config.pluginmanager.getplugin("terminalreporter")
    if reporter:
        reporter.write_sep("=", "Closeout external connection attempts: " + str(len(_blocked)))
        if counts:
            reporter.write_line(json.dumps(counts, sort_keys=True))
    if _blocked:
        session.exitstatus = pytest.ExitCode.TESTS_FAILED
