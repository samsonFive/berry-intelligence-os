import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from scripts import run_bounded_rehearsal as review


def test_budget_refuses_parallel_or_unhealthy_production():
    running = ["deploy-app-1", "deploy-caddy-1", "berry-mobile-review"]
    review.host_budget(running, review.MIN_AVAILABLE_KIB, review.MIN_FREE_BYTES, "healthy")
    for names, memory, disk, health in [
        (running + ["old-unbounded-preview"], review.MIN_AVAILABLE_KIB, review.MIN_FREE_BYTES, "healthy"),
        (running, review.MIN_AVAILABLE_KIB - 1, review.MIN_FREE_BYTES, "healthy"),
        (running, review.MIN_AVAILABLE_KIB, review.MIN_FREE_BYTES - 1, "healthy"),
        (running, review.MIN_AVAILABLE_KIB, review.MIN_FREE_BYTES, "starting"),
        (["deploy-caddy-1"], review.MIN_AVAILABLE_KIB, review.MIN_FREE_BYTES, "healthy"),
    ]:
        with pytest.raises(review.ReviewBlocked):
            review.host_budget(names, memory, disk, health)


def test_memory_unknown_fails_closed():
    assert review.available_memory("MemAvailable:    2345678 kB\n") == 2345678
    with pytest.raises(review.ReviewBlocked):
        review.available_memory("MemFree: 9999999 kB\n")


def test_runtime_cannot_escape_release_copy(tmp_path):
    releases = tmp_path / "releases"
    runtime = releases / "test/runtime"
    (runtime / "inbox").mkdir(parents=True)
    config = runtime / "data/configuration"
    config.mkdir(parents=True)
    for name in review.CONFIGS:
        (config / name).write_text("{}")
    assert review.isolated_runtime(runtime, releases) == runtime.resolve()
    with pytest.raises(review.ReviewBlocked):
        review.isolated_runtime(tmp_path, releases)
    (config / review.CONFIGS[0]).unlink()
    with pytest.raises(review.ReviewBlocked):
        review.isolated_runtime(runtime, releases)


@pytest.mark.skipif(sys.platform == "win32", reason="Linux host lock and symlink behavior")
def test_runtime_symlink_and_overlapping_lock_are_rejected(tmp_path):
    runtime = tmp_path / "release/runtime"
    (runtime / "inbox").mkdir(parents=True)
    (runtime / "data").mkdir()
    (runtime / "inbox/linked").symlink_to(tmp_path)
    with pytest.raises(review.ReviewBlocked, match="symlinks"):
        review.isolated_runtime(runtime, tmp_path / "release")
    (runtime / "inbox/linked").unlink()
    (runtime / "inbox/original.json").write_text("{}")
    os.link(runtime / "inbox/original.json", runtime / "inbox/hard-linked.json")
    with pytest.raises(review.ReviewBlocked, match="hard links"):
        review.isolated_runtime(runtime, tmp_path / "release")
    lock = tmp_path / "review.lock"
    with review.review_lock(lock):
        with pytest.raises(review.ReviewBlocked, match="review lock"):
            with review.review_lock(lock):
                pytest.fail("Second launcher acquired an already held lock")


def test_container_is_offline_bounded_and_has_no_production_mounts():
    image = "sha256:" + "a" * 64
    args = review.create_args("berry-rehearsal-example", image, Path("/opt/berry-platform-releases/test/runtime"))
    for option in ["--pull=never", "--network=none", "--restart=no", "--memory=1024m",
                   "--memory-swap=1024m", "--cpus=1", "--pids-limit=256", "--read-only", "--user=1000:1000"]:
        assert option in args
    assert args[-2:] == [image, "-"]
    assert not any("demo-runtime" in arg or "--privileged" in arg or "--env-file" in arg for arg in args)
    for name in ["deploy-app-1", "berry-rehearsal-x;touch-bad"]:
        with pytest.raises(review.ReviewBlocked):
            review.create_args(name, image, Path("/copy"))


@pytest.mark.parametrize("failure", ["timeout", "oom", "exit"])
def test_cleanup_uses_created_id_on_timeout_oom_and_failed_script(monkeypatch, failure):
    calls = []
    container = "c" * 64
    def run(args, **kwargs):
        assert args == ["docker", "start", "-a", "-i", container]
        if failure == "timeout":
            raise subprocess.TimeoutExpired(args, 10)
        return subprocess.CompletedProcess(args, 0)
    def docker(*args):
        calls.append(args)
        return json.dumps({"OOMKilled": failure == "oom", "ExitCode": 4})
    monkeypatch.setattr(review.subprocess, "run", run)
    monkeypatch.setattr(review, "docker", docker)
    if failure == "exit":
        assert review.execute(container, "print('fixture')", 10) == 4
    else:
        with pytest.raises(review.ReviewBlocked):
            review.execute(container, "print('fixture')", 10)
    assert calls[-1] == ("rm", "-f", container)
