"""Measurement-only diagnostic on committed public seed, never production data.

Run explicitly on the temporary CI branch. All four usual checks still run.
Fresh Python processes share only authenticated derived artifacts; no HTTP server,
provider request, production snapshot, real account or review decision is used.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import statistics
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
CHECKED_SOURCE = "0cec711590f97653d9e5a5f368fb822b232537fe"
BASE = "3ffe5bade1fb58616bcc9863aa6afe0109b7bb60"
BRANCH = "perf/public-private-model-probe-20261104"
RUNTIME_FILES = ("app/main.py", "app/services/presentation_memo.py",
    "app/services/derived_model_scope.py", "app/services/derived_model_store.py",
    "scripts/prepare_private_read_models.py")


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def inventory():
    files = {str(path.relative_to(ROOT)).replace("\\", "/"): path
        for folder in (ROOT / "data", ROOT / "schemas")
        for path in folder.rglob("*.json")}
    tracked = {name for name in git("ls-files", "data", "schemas").decode().splitlines()
               if name.endswith(".json")}
    assert set(files) == tracked, "Untracked or missing data is not a public-seed measurement"
    assert len(files) == 2942, "The diagnostic's pinned seed scope changed"
    return {name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in files.items()}


def enforce_budget():
    assert os.name == "posix" and sys.platform == "linux", "Linux-only bounded diagnostic"
    import resource
    assert shutil.disk_usage(ROOT).free >= 10 * 1024**3, "Keep the 10GiB headroom guard"
    available = int(next(line.split()[1] for line in Path("/proc/meminfo").read_text().splitlines()
                         if line.startswith("MemAvailable:"))) * 1024
    assert available >= 2 * 1024**3, "Keep the 2GiB available-memory guard"
    allowed = os.sched_getaffinity(0)
    os.sched_setaffinity(0, {min(allowed)})
    assert len(os.sched_getaffinity(0)) == 1
    _, hard = resource.getrlimit(resource.RLIMIT_AS)
    cap = 1024**3 if hard == resource.RLIM_INFINITY else min(hard, 1024**3)
    resource.setrlimit(resource.RLIMIT_AS, (cap, cap))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--public-seed-only", action="store_true", required=True)
    parser.parse_args(argv)
    assert os.environ.get("GITHUB_ACTIONS") == "true"
    assert os.environ.get("GITHUB_EVENT_NAME") == "workflow_dispatch"
    assert os.environ.get("GITHUB_REF_NAME") == BRANCH
    # The ordinary Actions checkout pins the exact SHA, so a detached HEAD is
    # expected. Bind that SHA plus the dispatch ref rather than a local branch.
    assert git("rev-parse", "HEAD").decode().strip() == os.environ.get("GITHUB_SHA")
    assert not git("diff", "--name-only", CHECKED_SOURCE, "--", "app", "schemas", "data")
    assert not git("diff", "--name-only", CHECKED_SOURCE, "--", "scripts/prepare_private_read_models.py")
    source_hashes = {}
    for name in RUNTIME_FILES:
        checked = git("show", CHECKED_SOURCE + ":" + name)
        assert (ROOT / name).read_bytes() == checked, name
        source_hashes[name] = hashlib.sha256(checked).hexdigest()
    before = inventory()
    enforce_budget()
    start = time.perf_counter()
    runs = []
    with tempfile.TemporaryDirectory(prefix="berry-public-model-probe-") as temporary:
        home = Path(temporary)
        inbox, artifacts, baseline = (home / name for name in ("inbox", "artifacts", "baseline"))
        for folder in (inbox, artifacts, baseline):
            folder.mkdir(mode=0o700)
        for name in RUNTIME_FILES[:2]:
            target = baseline / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(git("show", BASE + ":" + name))
        (home / "public-seed-only.json").write_text(json.dumps({"repo": str(ROOT),
            "checked_source": CHECKED_SOURCE, "purpose": "public-seed-measurement-only"}))
        env = {key: value for key, value in os.environ.items()
               if not key.startswith("BIOS_") and not key.endswith(("_API_KEY", "_API_TOKEN"))}
        env.update(BIOS_PUBLIC_PROBE_HOME=str(home), BIOS_PUBLIC_PROBE_REPO=str(ROOT),
            BIOS_PUBLIC_PROBE_INBOX=str(inbox), BIOS_PUBLIC_PROBE_ARTIFACT_ROOT=str(artifacts),
            BIOS_PUBLIC_PROBE_BASELINE=str(baseline), PYTHONDONTWRITEBYTECODE="1",
            PYTHONHASHSEED="0", PYTHONIOENCODING="utf-8")
        # Seed creation, unchanged-worker reuse, then a fresh worker in which an
        # earlier capture remains present and a newer update arrives. Alternate
        # the final variant order across replicates; never roll back source state
        # to manufacture a hit after capture. Nothing is written to the seed.
        for order in ("company", "candidates"):
            for replicate in ("0", "1"):
                updated_order = ("baseline", "candidate") if replicate == "0" else ("candidate", "baseline")
                sequence = [("baseline", "initial"), ("candidate", "initial"),
                            ("candidate", "reuse"), ("baseline", "reuse")]
                sequence.extend((variant, "updated") for variant in updated_order)
                for variant, phase in sequence:
                    assert time.perf_counter() - start < 480, "Bound the whole diagnostic"
                    child_start = time.perf_counter()
                    result = subprocess.run([sys.executable, str(ROOT / "scripts/private_model_public_worker.py"),
                        variant, order, phase, replicate], cwd=ROOT, env=env,
                        capture_output=True, text=True, timeout=90)
                    assert result.returncode == 0, "Public diagnostic worker failed: " + result.stderr[-1800:]
                    row = json.loads(result.stdout.splitlines()[-1])
                    assert (row["variant"], row["order"], row["phase"], row["replicate"]) == (variant, order, phase, replicate)
                    row["diagnostic_process_wall_seconds"] = time.perf_counter() - child_start
                    assert row["fictional_fresh_news_exercised"] == (phase == "updated")
                    for _, counts in row["actual_scope_counts"]:
                        assert counts["writes"] == 0, "Ordinary readers must not write"
                    if variant == "candidate" and phase != "updated":
                        assert sum(counts["artifact_hits"] for step, counts in row["actual_scope_counts"]
                                   if step != "fresh_news") >= 2, "Prepared reads did not exercise native artifacts"
                    if variant == "candidate" and phase == "updated":
                        assert row["earlier_article_retained_in_fresh_worker"]
                        assert sum(counts["artifact_hits"] for _, counts in row["actual_scope_counts"]) == 0, "Stale source artifacts were reused"
                        assert sum(counts["calculations"] for step, counts in row["actual_scope_counts"]
                                   if step == "fresh_news") >= 1, "New source did not invalidate the model"
                    runs.append(row)
        assert not any(path.is_file() for path in inbox.rglob("*")), "Private source/review data was written"
    assert inventory() == before, "Committed source/schema files changed"
    summaries = []
    for order in ("company", "candidates"):
        group = [row for row in runs if row["order"] == order]
        phase_summaries = []
        for phase in ("initial", "reuse", "updated"):
            phase_rows = [row for row in group if row["phase"] == phase]
            assert all(row["outputs"] == phase_rows[0]["outputs"] for row in phase_rows), "Complete outputs differ: " + order + "/" + phase
            phase_summaries.append({"phase": phase, **{variant: statistics.median(
                row["charged_total_seconds"] for row in phase_rows if row["variant"] == variant)
                for variant in ("baseline", "candidate")}})
        pairs = {variant: [sum(row["charged_total_seconds"] for row in group
                    if row["variant"] == variant and row["replicate"] == replicate)
                for replicate in ("0", "1")] for variant in ("baseline", "candidate")}
        summaries.append({"order": order,
            "baseline_three_worker_workflow_median_seconds": statistics.median(pairs["baseline"]),
            "candidate_preparation_plus_three_worker_workflow_median_seconds": statistics.median(pairs["candidate"]),
            "baseline_totals": pairs["baseline"], "candidate_totals": pairs["candidate"],
            "phases": phase_summaries})
    output = {"kind": "public_seed_private_model_diagnostic", "checked_at": datetime.now(timezone.utc).isoformat(),
        "head": git("rev-parse", "HEAD").decode().strip(), "checked_runtime_head": CHECKED_SOURCE,
        "baseline_head": BASE, "runtime_source_sha256": source_hashes,
        "public_json_files_preserved": len(before), "fresh_processes": len(runs),
        "complete_response_comparisons": len(runs) * 3, "all_complete_typed_models_context_HTML_match": True,
        "actual_preparation_process_startup_charged": True, "reader_artifacts_unchanged": True,
        "one_cpu": True, "address_space_limit_bytes": 1024**3,
        "source_data": "Committed public seed only, empty disposable inbox, synthetic in-memory article update.",
        "limits": "Architecture diagnostic only. Fresh Python workers on a warm CI filesystem; no production data/accounts, network server or VPS latency/preservation acceptance. Typed comparison controls generated materialization times, advancing ten minutes on article update. CLI preparation includes its complete process startup; request figures time handlers. Diagnostic process wall figures additionally include imports and verification work, not user request latency.",
        "summaries": summaries, "runs": runs, "production_changed": False,
        "provider_requests": 0, "network_connections": "Blocked in worker and explicit preparation command"}
    print("PUBLIC_MODEL_DIAGNOSTIC=" + json.dumps(output, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
