"""Fresh repository inventory semantics, independent of the traversal implementation."""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from app.repositories.base import StorageError
from app.repositories.json.base import JsonRecordRepository
from app.repositories.json.entities import EntityRepository


def write(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")


def reference(folder: Path):
    """Use the actual platform's pathlib pattern matching and Path ordering."""
    paths = sorted(folder.rglob("*.json"))
    signature = tuple((str(path), path.stat().st_mtime_ns, path.stat().st_size) for path in paths)
    return paths, signature


def test_inventory_matches_pathlib_order_hidden_nested_and_platform_extension_case(tmp_path: Path):
    folder = tmp_path / "records"
    for name in ("a-first.json", "Z-last.json", ".json", ".hidden.json", ".hidden/nested.json",
                 "nested/deeper/record.json", "uppercase.JSON", "mixed.JsOn", "ignored.json.bak", "ignored.txt"):
        write(folder / name, {"id": name, "name": name, "nested": {"values": [name]}})
    paths, signature = reference(folder)
    expected = [(path, json.loads(path.read_text(encoding="utf-8"))) for path in paths]
    repo = JsonRecordRepository(folder)
    assert repo._load_all_with_paths() == expected
    assert repo._cache[0] == signature
    assert repo.list() == [record for _, record in expected]
    assert folder / ".hidden/nested.json" in paths
    # Windows matches JSON/JsOn case-insensitively; POSIX does not. Neither
    # behavior is replaced by a universal extension-lowercasing assumption.
    for name in ("uppercase.JSON", "mixed.JsOn"):
        assert (repo.get(name) is not None) == (folder / name in paths)
    assert repo.get("ignored.json.bak") is None


def test_sorted_duplicate_paths_preserve_get_first_and_reader_index_last_winner(tmp_path: Path):
    folder = tmp_path / "entities"
    for name in ("a-first.json", "Z-last.json", ".hidden/duplicate.json"):
        write(folder / name, {"id": "company-duplicate", "entity_type": "company", "name": name,
                              "aliases": ["Alias " + name]})
    paths, signature = reference(folder)
    expected = [json.loads(path.read_text(encoding="utf-8")) for path in paths]
    repo = EntityRepository(data_dir=tmp_path)
    assert repo.list() == expected
    assert repo.get("company-duplicate") == expected[0]
    assert repo.reader_index(include_workspace=True)["company-duplicate"] == expected[-1]
    assert repo._cache[0] == signature


def test_warm_signature_reuses_parsed_cache_but_public_reads_are_mutation_isolated(tmp_path: Path):
    folder = tmp_path / "records"
    path = folder / "one.json"
    record = {"id": "one", "name": "Original", "nested": {"values": ["retained"]}}
    write(path, record)
    repo = JsonRecordRepository(folder)
    pairs = repo._load_all_with_paths()
    assert repo._load_all_with_paths() is pairs
    listed = repo.list()
    listed[0]["nested"]["values"].append("caller mutation")
    returned = repo.get("one")
    returned["name"] = "caller rename"
    assert repo.get("one") == record
    # Rewriting identical bytes with identical metadata keeps the exact existing
    # signature contract: no TTL, forced reparse, or body-based cache key.
    previous = path.stat()
    write(path, record)
    os.utime(path, ns=(previous.st_atime_ns, previous.st_mtime_ns))
    assert repo._load_all_with_paths() is pairs


def test_external_json_edit_invalidates_by_mtime_when_size_is_unchanged(tmp_path: Path):
    folder = tmp_path / "records"
    path = folder / "one.json"
    before = {"id": "one", "name": "Old", "aliases": ["Old"]}
    after = {"id": "one", "name": "New", "aliases": ["New"]}
    write(path, before)
    repo = JsonRecordRepository(folder)
    assert repo.get("one") == before
    pairs, previous = repo._load_all_with_paths(), path.stat()
    write(path, after)
    assert path.stat().st_size == previous.st_size
    os.utime(path, ns=(previous.st_atime_ns, previous.st_mtime_ns + 1_000_000_000))
    assert path.stat().st_mtime_ns != previous.st_mtime_ns
    assert repo.get("one") == after
    assert repo._load_all_with_paths() is not pairs


def test_external_add_delete_and_size_edit_invalidate_get_and_list_without_ttl(tmp_path: Path):
    folder = tmp_path / "records"
    path = folder / "one.json"
    write(path, {"id": "one", "name": "Old"})
    repo = JsonRecordRepository(folder)
    assert repo.list() == [{"id": "one", "name": "Old"}]
    previous = path.stat()
    changed = {"id": "one", "name": "Longer edited name", "aliases": ["Added alias"]}
    write(path, changed)
    os.utime(path, ns=(previous.st_atime_ns, previous.st_mtime_ns))
    assert path.stat().st_mtime_ns == previous.st_mtime_ns
    assert path.stat().st_size != previous.st_size
    assert repo.get("one") == changed
    added = folder / ".nested/new.json"
    write(added, {"id": "two", "name": "Added"})
    assert repo.get("two") == {"id": "two", "name": "Added"}
    assert len(repo.list()) == 2
    added.unlink()
    assert repo.get("two") is None
    assert repo.list() == [changed]
    path.unlink()
    assert repo.get("one") is None
    assert repo.list() == []


def test_json_named_directory_is_not_silently_removed_from_inventory(tmp_path: Path):
    folder = tmp_path / "records"
    write(folder / "one.json", {"id": "one"})
    repo = JsonRecordRepository(folder)
    assert repo.list() == [{"id": "one"}]
    cached = repo._cache
    directory = folder / "00-directory.json"
    write(directory / "child.json", {"id": "child"})
    paths, _ = reference(folder)
    assert directory in paths
    with pytest.raises(StorageError) as caught:
        repo.list()
    assert str(directory) in str(caught.value)
    assert repo._cache is cached, "a failed read cannot replace the last valid cache"
    (directory / "child.json").unlink()
    directory.rmdir()
    assert repo.list() == [{"id": "one"}]


def symlink(link: Path, target: Path, *, directory=False) -> None:
    try:
        link.symlink_to(target, target_is_directory=directory)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"This platform/account cannot create the required symlink: {exc}")


def test_file_symlink_follows_target_bytes_and_fresh_target_metadata(tmp_path: Path):
    folder = tmp_path / "records"
    folder.mkdir()
    target = tmp_path / "outside.payload"
    write(target, {"id": "linked", "name": "Original"})
    link = folder / "linked.json"
    symlink(link, target)
    paths, signature = reference(folder)
    repo = JsonRecordRepository(folder)
    assert [path for path, _ in repo._load_all_with_paths()] == paths == [link]
    assert repo._cache[0] == signature
    assert repo.get("linked") == {"id": "linked", "name": "Original"}
    previous = target.stat()
    write(target, {"id": "linked", "name": "A longer target edit"})
    os.utime(target, ns=(previous.st_atime_ns, previous.st_mtime_ns))
    assert repo.get("linked") == {"id": "linked", "name": "A longer target edit"}


def test_directory_symlink_is_not_recursed_like_an_ordinary_subdirectory(tmp_path: Path):
    folder = tmp_path / "records"
    write(folder / "local.json", {"id": "local"})
    target = tmp_path / "outside"
    write(target / "external.json", {"id": "external"})
    symlink(folder / "linked-directory", target, directory=True)
    paths, signature = reference(folder)
    assert paths == [folder / "local.json"]
    repo = JsonRecordRepository(folder)
    assert repo.list() == [{"id": "local"}]
    assert repo._cache[0] == signature


def test_inventory_does_not_call_path_stat_for_every_record(tmp_path: Path, monkeypatch):
    folder = tmp_path / "records"
    for index in range(12):
        write(folder / "nested" / f"{index:02d}.json", {"id": str(index)})
    expected_paths, expected_signature = reference(folder)
    original = Path.stat
    calls = []

    def track(path, *args, **kwargs):
        calls.append(path)
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", track)
    repo = JsonRecordRepository(folder)
    assert [path for path, _ in repo._load_all_with_paths()] == expected_paths
    assert repo._cache[0] == expected_signature
    assert all(path == folder for path in calls), "record metadata should come from fresh DirEntry.stat, not Path.stat"
    assert len(calls) <= 1, "at most the folder.exists probe may call Path.stat"
