"""Package an exact committed Docker candidate without runtime files or checkout EOL conversion."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tarfile
import tempfile

DOCKER_PATHS = ("Dockerfile", "app", "schemas", "scripts", "benchmarks", "data",
                "requirements-web.txt", "docker-entrypoint.sh")


def package(repo: Path, ref: str, output: Path) -> dict:
    repo = repo.resolve()
    output = output.resolve()
    if output.exists():
        raise ValueError("Choose a new output path; existing packages are never overwritten")
    git = ["git", "-c", f"safe.directory={repo.as_posix()}", "-C", str(repo)]
    head = subprocess.check_output([*git, "rev-parse", "--verify", f"{ref}^{{commit}}"], text=True).strip()
    object_format = subprocess.check_output([*git, "rev-parse", "--show-object-format"], text=True).strip()
    tree = {}
    for entry in subprocess.check_output([*git, "ls-tree", "-rz", head]).split(b"\0"):
        if entry:
            meta, name = entry.split(b"\t", 1)
            mode, kind, oid = meta.decode().split()
            tree[name.decode()] = (mode, kind, oid)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="berry-release-") as temporary:
        archive = Path(temporary) / "candidate.tar.gz"
        # Git archive applies core.autocrlf even though the input is a commit.
        # Disable it explicitly: a Windows-produced shell script must still be executable on Linux.
        subprocess.run([*git, "-c", "core.autocrlf=false", "archive", "--format=tar.gz",
                        f"--output={archive}", head, *DOCKER_PATHS], check=True)
        verified = 0
        with tarfile.open(archive, "r:gz") as tar:
            for member in tar.getmembers():
                if member.isdir():
                    continue
                if not member.isfile():
                    raise ValueError(f"Unsupported package member: {member.name}")
                body = tar.extractfile(member).read()
                mode, kind, oid = tree[member.name]
                digest = hashlib.new(object_format, b"blob " + str(len(body)).encode() + b"\0" + body).hexdigest()
                if kind != "blob" or digest != oid:
                    raise ValueError(f"Archive differs from committed bytes: {member.name}")
                if bool(member.mode & 0o111) != (mode == "100755"):
                    raise ValueError(f"Archive executable mode differs: {member.name}")
                verified += 1
        body = archive.read_bytes()
        # Exclusive creation avoids a race overwriting a prior release package.
        with output.open("xb") as handle:
            handle.write(body)
    return {"head": head, "sha256": hashlib.sha256(body).hexdigest(),
            "verified_files": verified, "bytes": len(body), "output": str(output)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--ref", default="HEAD")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(package(args.repo, args.ref, args.output), indent=2))


if __name__ == "__main__":
    main()
