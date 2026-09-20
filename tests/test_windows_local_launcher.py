"""Windows local launcher keeps the external-browser handoff executable."""

from pathlib import Path


def test_windows_launcher_waits_for_server_and_opens_external_browser():
    source = Path("scripts/run_local.ps1").read_text(encoding="utf-8")
    assert 'if ($hostName -eq "0.0.0.0") { "127.0.0.1" }' in source
    assert '$appUrl = "http://${browserHost}:${port}/today"' in source
    assert "Invoke-WebRequest -Uri $url" in source
    assert "Start-Process $url" in source
    assert "BIOS_NO_BROWSER" in source
    assert "uvicorn app.main:app --reload" in source


def test_local_run_docs_include_pull_and_one_command_launch():
    source = Path("docs/LOCAL-FEED-FIRST.md").read_text(encoding="utf-8")
    assert "git pull --ff-only origin cursor/monday-tracked-companies-80ac" in source
    assert r".\scripts\run_local.ps1" in source
    assert "opens `/today` in your normal external browser" in source
