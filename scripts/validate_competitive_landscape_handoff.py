"""Offline integrity checks for the inventory and manual research handoff."""
from collections import Counter
import json
from pathlib import Path
import sys

from build_competitive_landscape_handoff import ROOT, SNAPSHOT, text_sha256
from competitive_landscape_prompt_contract import public_row


def validate(root=ROOT, snapshot=SNAPSHOT, *, check_inputs=True):
    errors = []
    load = lambda p: json.loads(p.read_text(encoding="utf-8"))
    inventory_path = snapshot / "commercial-entity-inventory.json"
    inventory = load(inventory_path)
    manifest = load(snapshot / "research-coverage-checklist.json")
    rubrics = load(snapshot / "capability-rubrics.json")
    if text_sha256(inventory_path) != manifest["inventory_sha256"]:
        errors.append("Inventory differs from prompt manifest; create an explicit new version or regenerate before handoff.")
    if check_inputs:
        for name, expected in inventory["input_hashes"].items():
            path = root / name
            if not path.is_file() or text_sha256(path) != expected:
                errors.append(f"Inventory input changed: {name}")
    expected_ids = {r["entity_id"] for r in inventory["entities"] if r["inclusion_status"] not in {"out_of_scope", "duplicate_candidate"}}
    ids = [eid for b in manifest["batches"] for eid in b["entity_ids"]]
    if set(ids) != expected_ids:
        errors.append(f"Batch coverage mismatch: missing={sorted(expected_ids-set(ids))}, extra={sorted(set(ids)-expected_ids)}")
    if any(n != 1 for n in Counter(ids).values()):
        errors.append("An entity is assigned to more than one profile batch.")
    index = {r["entity_id"]: r for r in inventory["entities"]}
    for batch in manifest["batches"]:
        path = root / batch["prompt_file"]
        if not path.is_file():
            errors.append(f"Missing prompt: {batch['batch_id']}")
            continue
        if text_sha256(path) != batch["prompt_sha256"]:
            errors.append(f"Prompt hash mismatch: {batch['batch_id']}")
        content = path.read_text(encoding="utf-8")
        if inventory["inventory_version"] not in content or rubrics["rubric_version"] not in content:
            errors.append(f"Missing version in {batch['batch_id']}")
        # Parse the public inventory block, not prose mentions; ensure no dropped
        # nodes, private fields, or silently modified IDs/known unknowns.
        try:
            public = json.loads(content.split("```json\n", 1)[1].split("\n```", 1)[0])
            expected = [public_row(index[eid]) for eid in batch["entity_ids"]]
            if public != expected:
                errors.append(f"Public inventory mismatch: {batch['batch_id']}")
        except (ValueError, IndexError):
            errors.append(f"Missing/invalid public inventory block: {batch['batch_id']}")
        for required in ["observation_id | entity_id", "original_url | publisher", "Jobs table:", "first_observed_date", "fact_claim_plan_interpretation"]:
            if required not in content:
                errors.append(f"Missing return-contract field {required!r} in {batch['batch_id']}")
    prompt_dirs = {Path(b["prompt_file"]).parent for b in manifest["batches"]}
    expected_files = {Path(b["prompt_file"]) for b in manifest["batches"]}
    for folder in prompt_dirs:
        for path in (root / folder).glob("B*.md"):
            if path.relative_to(root) not in expected_files:
                errors.append(f"Unlisted stale prompt: {path.relative_to(root)}")
    cap_ids = [c["capability_id"] for c in rubrics["capabilities"]]
    if len(cap_ids) != len(set(cap_ids)):
        errors.append("Duplicate capability IDs.")
    for cap in rubrics["capabilities"]:
        if [a["level"] for a in cap["anchors"]] != [1, 2, 3, 4, 5] or any(not a["requires"] for a in cap["anchors"]):
            errors.append(f"Invalid anchors: {cap['capability_id']}")
        if set(cap["unscored_states"]) != {"unknown", "not_applicable"}:
            errors.append(f"Unscored states conflated: {cap['capability_id']}")
    return errors


if __name__ == "__main__":
    failures = validate()
    print("\n".join(failures) if failures else "Handoff validated: input hashes, full entity coverage, public inventory, return fields, prompt hashes and rubric anchors.")
    sys.exit(bool(failures))
