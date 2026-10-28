"""Run one offline preservation check without competing with the live app.

Linux/Docker operator tool. It never copies, mounts or replaces production data.
The supplied runtime must already be an isolated release copy. No credentials
or network access are passed through from the host.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess

RELEASES = Path("/opt/berry-platform-releases")
INFRASTRUCTURE = {"deploy-app-1", "deploy-caddy-1", "berry-mobile-review"}
MIN_AVAILABLE_KIB = 2 * 1024 * 1024
MIN_FREE_BYTES = 10 * 1024**3
CONFIGS = ("collection_pipelines.json", "source_collection_cadence.json", "source_universe.json")


class ReviewBlocked(RuntimeError):
    pass


def docker(*args: str) -> str:
    result = subprocess.run(["docker", *args], capture_output=True, text=True, timeout=30)
    if result.returncode:
        # Do not echo daemon diagnostics which may contain image credentials.
        raise ReviewBlocked("Docker operation failed: " + args[0])
    return result.stdout.strip()


def available_memory(text: str) -> int:
    match = re.search(r"^MemAvailable:\s+(\d+) kB$", text, re.MULTILINE)
    if not match:
        raise ReviewBlocked("Cannot determine available host memory")
    return int(match.group(1))


def host_budget(running: list[str], available_kib: int, free_bytes: int, healthy: str) -> None:
    if set(running) - INFRASTRUCTURE:
        raise ReviewBlocked("Another container is running; inspect it before starting a rehearsal")
    if not {"deploy-app-1", "deploy-caddy-1"}.issubset(running) or healthy != "healthy":
        raise ReviewBlocked("Production must be running and healthy first")
    if available_kib < MIN_AVAILABLE_KIB or free_bytes < MIN_FREE_BYTES:
        raise ReviewBlocked("Insufficient host headroom: require 2GiB available RAM and 10GiB free disk")


def isolated_runtime(value: Path, releases: Path = RELEASES) -> Path:
    runtime = value.resolve(strict=True)
    if runtime == releases.resolve() or not runtime.is_relative_to(releases.resolve()):
        raise ReviewBlocked("Runtime must be a release copy under /opt/berry-platform-releases")
    if not runtime.is_dir() or not (runtime / "inbox").is_dir() or not (runtime / "data").is_dir():
        raise ReviewBlocked("An existing isolated data/inbox runtime is required")
    # Reject nested symlinks, including files, so no runtime write escapes the copy.
    if value.is_symlink():
        raise ReviewBlocked("Runtime symlinks are not permitted")
    for item in runtime.rglob("*"):
        if item.is_symlink():
            raise ReviewBlocked("Runtime symlinks are not permitted")
        if item.is_file() and item.stat().st_nlink != 1:
            raise ReviewBlocked("Runtime hard links are not permitted")
    for name in CONFIGS:
        if not (runtime / "data/configuration" / name).is_file():
            raise ReviewBlocked("Isolated collection configuration is missing")
    return runtime


@contextmanager
def review_lock(path: str | Path = "/run/lock/berry-review.lock"):
    import fcntl
    fd = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise ReviewBlocked("Another bounded rehearsal owns the host review lock") from error
        yield
    finally:
        os.close(fd)


def create_args(name: str, image_id: str, runtime: Path) -> list[str]:
    if not re.fullmatch(r"berry-rehearsal-[a-z0-9][a-z0-9-]{0,63}", name):
        raise ReviewBlocked("Use a unique berry-rehearsal- name")
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", image_id):
        raise ReviewBlocked("A locally verified image ID is required")
    args = ["create", "-i", "--name", name, "--pull=never", "--network=none",
            "--restart=no", "--memory=1024m", "--memory-swap=1024m", "--cpus=1",
            "--pids-limit=256", "--user=1000:1000", "--read-only",
            "--tmpfs=/tmp:rw,nosuid,nodev,size=64m", "--entrypoint=python",
            "--label=berry.role=offline-rehearsal", "--mount", f"type=bind,source={runtime},target=/app/runtime"]
    for name in CONFIGS:
        args += ["--mount", f"type=bind,source={runtime}/data/configuration/{name},target=/app/seed/data/configuration/{name},readonly"]
    for setting in ("BIOS_REMOTE_INTERACTIVE=true", "BIOS_RUNTIME_DIR=/app/runtime",
                    "BIOS_REVIEW_USERNAME=fixture-release-review", "BIOS_REVIEW_PASSWORD=fixture-release-only",
                    "BIOS_SESSION_SECRET=fixture-only-session-secret-at-least-32-characters",
                    "BIOS_MODE=authoring", "ENABLE_SOURCE_POLLING=false",
                    "ENABLE_PERPLEXITY_PULSE=false", "BIOS_SOCIAL_MANUAL_COLLECTION=false"):
        args += ["-e", setting]
    return args + [image_id, "-"]


def execute(container_id: str, script: str, timeout: int) -> int:
    # Container ID comes only from our successful create, never a guessed name.
    try:
        result = subprocess.run(["docker", "start", "-a", "-i", container_id], input=script,
                                text=True, timeout=timeout)
        state = json.loads(docker("inspect", "--format", "{{json .State}}", container_id))
        if state.get("OOMKilled"):
            raise ReviewBlocked("Rehearsal exceeded its 1GiB cap; do not raise it on the production host")
        return result.returncode or int(state["ExitCode"])
    except subprocess.TimeoutExpired as error:
        raise ReviewBlocked("Rehearsal time limit exceeded") from error
    finally:
        # Remove the disposable container only; the bind-mounted copy survives.
        docker("rm", "-f", container_id)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True, help="Already-built local image; no pull")
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--script", type=Path, required=True, help="Python preservation check, not an app server")
    parser.add_argument("--name", required=True)
    parser.add_argument("--timeout", type=int, default=600, choices=range(1, 901), metavar="1..900")
    args = parser.parse_args()
    runtime = isolated_runtime(args.runtime)
    script = args.script.read_text(encoding="utf-8")
    if len(script.encode()) > 1024 * 1024:
        raise ReviewBlocked("Preservation script exceeds 1MiB")
    with review_lock():
        host_budget(docker("ps", "--format", "{{.Names}}").splitlines(),
                    available_memory(Path("/proc/meminfo").read_text()),
                    shutil.disk_usage(RELEASES).free,
                    docker("inspect", "--format", "{{.State.Health.Status}}", "deploy-app-1"))
        image_id = docker("image", "inspect", "--format", "{{.Id}}", args.image)
        container_id = docker(*create_args(args.name, image_id, runtime))
        if not re.fullmatch(r"[0-9a-f]{64}", container_id):
            raise ReviewBlocked("Docker did not return a valid created container ID")
        return execute(container_id, script, args.timeout)


if __name__ == "__main__":
    def interrupted(_signal, _frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, interrupted)
    try:
        raise SystemExit(main())
    except (ReviewBlocked, KeyboardInterrupt) as error:
        raise SystemExit(str(error) or "Rehearsal interrupted")
