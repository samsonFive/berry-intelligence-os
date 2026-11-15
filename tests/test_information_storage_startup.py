"""Container restarts must not recreate split storage after activation."""
import json
from pathlib import Path
import subprocess
import sys

import pytest

from app.services import information_storage as storage
from scripts.prepare_information_storage import prepare_runtime_information

ROOT = Path(__file__).resolve().parents[1]


def activate(data, inbox):
    records = data / "information/records"
    records.mkdir(parents=True)
    storage.atomic_json(data / "information/store.json", {
        "version": 1, "state": "active", "data_dir": str(data.resolve()),
        "inbox_dir": str(inbox.resolve()), "store_root": str((data / "information").resolve()),
    })
    storage.atomic_json(inbox / storage.BINDING_NAME, {
        "version": 1, "inbox_dir": str(inbox.resolve()),
        "store_root": str((data / "information").resolve()),
    })
    return records.resolve()


def test_legacy_startup_keeps_intake_path_without_activating(tmp_path):
    data, inbox = tmp_path / "data", tmp_path / "inbox"
    assert prepare_runtime_information(data, inbox) == inbox / "evidence"
    assert (inbox / "evidence").is_dir()
    assert not (data / "information").exists()
    assert not (inbox / storage.BINDING_NAME).exists()


def test_active_startup_uses_shared_records_without_recreating_either_legacy_folder(tmp_path):
    data, inbox = tmp_path / "data", tmp_path / "elsewhere/inbox"
    records = activate(data, inbox)
    source = records / "private-source.json"
    source.write_text(json.dumps({"id": "private-source", "publication_scope": "private"}), encoding="utf-8")
    before = source.read_bytes()
    assert prepare_runtime_information(data, inbox) == records
    assert source.read_bytes() == before
    assert not (data / "evidence").exists()
    assert not (inbox / "evidence").exists()


@pytest.mark.parametrize("failure", ["missing_binding", "missing_marker", "transition", "incomplete_records", "wrong_inbox"])
def test_partial_or_mismatched_activation_blocks_startup_without_legacy_fallback(tmp_path, failure):
    data, inbox = tmp_path / "data", tmp_path / "inbox"
    activate(data, inbox)
    if failure == "missing_binding":
        (inbox / storage.BINDING_NAME).unlink()
    elif failure == "missing_marker":
        (data / "information/store.json").unlink()
    elif failure == "transition":
        storage.atomic_json(data / storage.TRANSITION_NAME, {"migration_id": "interrupted"})
    elif failure == "incomplete_records":
        (data / "information/store.json").unlink()
        (inbox / storage.BINDING_NAME).unlink()
    else:
        inbox = tmp_path / "different-inbox"
    with pytest.raises(storage.InformationStorageError):
        prepare_runtime_information(data, inbox)
    assert not (data / "evidence").exists()
    assert not (inbox / "evidence").exists()


def test_cli_blocks_partial_activation_and_module_invocation_resolves_imports(tmp_path):
    data, inbox = tmp_path / "data", tmp_path / "inbox"
    activate(data, inbox)
    (inbox / storage.BINDING_NAME).unlink()
    result = subprocess.run([
        sys.executable, "-m", "scripts.prepare_information_storage",
        "--data-dir", str(data), "--inbox-dir", str(inbox),
    ], cwd=ROOT, capture_output=True, text=True, check=False)
    assert result.returncode == 2
    assert "Information storage startup blocked" in result.stderr
    assert "ModuleNotFoundError" not in result.stderr
    assert not (inbox / "evidence").exists()


def test_entrypoint_checks_storage_after_sync_before_launching_application():
    entrypoint = (ROOT / "docker-entrypoint.sh").read_text(encoding="utf-8")
    assert entrypoint.index("-m scripts.sync_trusted_data") < entrypoint.index("-m scripts.prepare_information_storage")
    assert entrypoint.index("-m scripts.prepare_information_storage") < entrypoint.index('exec gosu berry "$@"')
    assert '"$INBOX_DIR/evidence"' not in entrypoint
    check = entrypoint.split("-m scripts.prepare_information_storage", 1)[1].split("mkdir -p", 1)[0]
    assert "||" not in check


def test_private_source_storage_and_migration_material_are_gitignored():
    private_paths = [
        "data/information/records/private.json", "data/information/history/source/old.json",
        "custom/customer-data/information/assets/source/private.pdf", "data/.information-store-transition.json",
        "data/.information-store.lock", "custom-inbox/.information-store.json",
        "data/.information-stage-fixture/records/private.json",
        "data/.information-rolled-back-fixture/records/private.json",
        "information-migration-backups/run/sources/data/evidence/source.json",
        "custom-backups/information-0123456789abcdefabcd/sources/data/evidence/source.json",
        "custom-backups/run/PLAN.private.json",
    ]
    result = subprocess.run(["git", "check-ignore", "--no-index", "--stdin", "-z"], cwd=ROOT,
                            input=("\0".join(private_paths) + "\0").encode(), capture_output=True, check=False)
    assert result.returncode == 0, result.stderr
    assert set(result.stdout.decode().strip("\0").split("\0")) == set(private_paths)
    public = subprocess.run(["git", "check-ignore", "--no-index", "data/evidence/example.json"],
                            cwd=ROOT, capture_output=True, text=True, check=False)
    assert public.returncode == 1
