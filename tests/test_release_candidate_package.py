import hashlib
from pathlib import Path
import shlex
import subprocess
import tarfile

import pytest

from scripts.package_release_candidate import DOCKER_PATHS, OPTIONAL_BUILD_PATHS, package


def git(repo, *args):
    return subprocess.check_output(["git", "-c", f"safe.directory={repo.as_posix()}", "-C", str(repo), *args])


def fixture_repo(tmp_path, *, legacy=False):
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init")
    git(repo, "config", "user.email", "release-test@example.invalid")
    git(repo, "config", "user.name", "Release fixture")
    git(repo, "config", "core.autocrlf", "true")
    for name in DOCKER_PATHS:
        if legacy and name in OPTIONAL_BUILD_PATHS:
            continue
        path = repo / name
        if name not in {"Dockerfile", ".dockerignore", "requirements-web.txt", "docker-entrypoint.sh", "docs/v2/social-source-access.json"}:
            path.mkdir(parents=True)
            path = path / "fixture.txt"
        path.parent.mkdir(parents=True, exist_ok=True)
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
    (repo / "deploy" / ".env").write_text("UNCOMMITTED_PRIVATE_RUNTIME_SECRET")
    output = tmp_path / "candidate.tar.gz"
    result = package(repo, "HEAD", output)
    assert result["head"] == git(repo, "rev-parse", "HEAD").decode().strip()
    assert result["sha256"] == hashlib.sha256(output.read_bytes()).hexdigest()
    assert result["verified_files"] == len(DOCKER_PATHS)
    with tarfile.open(output) as tar:
        assert not any(name.startswith("inbox/") for name in tar.getnames())
        assert "deploy/.env" not in tar.getnames()
        assert tar.extractfile("app/fixture.txt").read() == b"committed fixture\n"
        assert tar.extractfile("docker-entrypoint.sh").read() == b"#!/bin/sh\nexit 0\n"
        assert tar.getmember("docker-entrypoint.sh").mode & 0o111


def context_copy_sources(dockerfile):
    for line in dockerfile.splitlines():
        if not line.startswith("COPY "):
            continue
        parts = shlex.split(line)
        # These files are produced inside another build stage, not supplied by
        # the release archive. All actual context sources remain checked below.
        if any(part.startswith("--from=") for part in parts[1:]):
            continue
        yield from (part.rstrip("/") for part in parts[1:-1] if not part.startswith("--"))


def test_every_current_docker_copy_input_is_in_release_package(tmp_path):
    repo = fixture_repo(tmp_path)
    source = Path(__file__).resolve().parents[1]
    dockerfiles = {name: (source / name).read_text() for name in ("Dockerfile", "copilot-runtime/Dockerfile")}
    for name, dockerfile in dockerfiles.items():
        (repo / name).write_text(dockerfile)
        for name in context_copy_sources(dockerfile):
            path = repo / name
            if not path.exists():
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("committed build input\n")
    git(repo, "add", ".")
    git(repo, "commit", "-m", "Current Docker build contract")
    output = tmp_path / "current-docker-candidate.tar.gz"
    package(repo, "HEAD", output)
    with tarfile.open(output) as tar:
        names = tar.getnames()
        for dockerfile in dockerfiles.values():
            for source in context_copy_sources(dockerfile):
                assert source in names or any(name.startswith(source + "/") for name in names), source
        assert ".dockerignore" in names
        assert "deploy/fixture.txt" in names
        assert tar.extractfile("docs/v2/social-source-access.json").read() == b"committed fixture\n"
        assert not any(name.startswith("inbox/") for name in names)


def test_releases_before_frontend_and_runtime_remain_packageable(tmp_path):
    repo = fixture_repo(tmp_path, legacy=True)
    output = tmp_path / "legacy-candidate.tar.gz"
    package(repo, "HEAD", output)
    with tarfile.open(output) as tar:
        assert "Dockerfile" in tar.getnames()
        assert "app/fixture.txt" in tar.getnames()
        assert not any(name.startswith(("frontend/", "copilot-runtime/", "inbox/")) for name in tar.getnames())


def test_existing_release_package_is_preserved(tmp_path):
    repo = fixture_repo(tmp_path)
    output = tmp_path / "candidate.tar.gz"
    output.write_bytes(b"existing release")
    with pytest.raises(ValueError, match="never overwritten"):
        package(repo, "HEAD", output)
    assert output.read_bytes() == b"existing release"
