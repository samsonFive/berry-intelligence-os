import hashlib
import subprocess
import tarfile

import pytest

from scripts.package_release_candidate import DOCKER_PATHS, package


def git(repo, *args):
    return subprocess.check_output(["git", "-c", f"safe.directory={repo.as_posix()}", "-C", str(repo), *args])


def fixture_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init")
    git(repo, "config", "user.email", "release-test@example.invalid")
    git(repo, "config", "user.name", "Release fixture")
    git(repo, "config", "core.autocrlf", "true")
    for name in DOCKER_PATHS:
        path = repo / name
        if name not in {"Dockerfile", "requirements-web.txt", "docker-entrypoint.sh"}:
            path.mkdir()
            path = path / "fixture.txt"
        path.write_bytes(b"#!/bin/sh\nexit 0\n" if name == "docker-entrypoint.sh" else b"committed fixture\n")
    (repo / "inbox").mkdir()
    (repo / "inbox" / "private.txt").write_text("Private runtime must stay out")
    git(repo, "add", ".")
    git(repo, "update-index", "--chmod=+x", "docker-entrypoint.sh")
    git(repo, "commit", "-m", "Fixture")
    return repo


def test_windows_configuration_preserves_commit_bytes_and_modes(tmp_path):
    repo = fixture_repo(tmp_path)
    (repo / "app" / "fixture.txt").write_bytes(b"uncommitted operator edit\r\n")
    output = tmp_path / "candidate.tar.gz"
    result = package(repo, "HEAD", output)
    assert result["head"] == git(repo, "rev-parse", "HEAD").decode().strip()
    assert result["sha256"] == hashlib.sha256(output.read_bytes()).hexdigest()
    assert result["verified_files"] == len(DOCKER_PATHS)
    with tarfile.open(output) as tar:
        assert not any(name.startswith("inbox/") for name in tar.getnames())
        assert tar.extractfile("app/fixture.txt").read() == b"committed fixture\n"
        assert tar.extractfile("docker-entrypoint.sh").read() == b"#!/bin/sh\nexit 0\n"
        assert tar.getmember("docker-entrypoint.sh").mode & 0o111


def test_existing_release_package_is_preserved(tmp_path):
    repo = fixture_repo(tmp_path)
    output = tmp_path / "candidate.tar.gz"
    output.write_bytes(b"existing release")
    with pytest.raises(ValueError, match="never overwritten"):
        package(repo, "HEAD", output)
    assert output.read_bytes() == b"existing release"
