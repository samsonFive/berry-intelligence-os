# Linux Validation Workflow V1 — Checkpoint

Date: 2026-09-15  
Branch: `infra/linux-validation-v1`  
Base: `031c9b6a80bd72ce3f271933d8a1ea302decb077`  
Scope: CI workflow and documentation only.

## Deliverables

- `.github/workflows/linux-validation.yml`
- `docs/v2/LINUX-VALIDATION-WORKFLOW-V1.md`
- `artifacts/linux-validation-v1/CHECKPOINT.md`
- `artifacts/linux-validation-v1/NEXT-AGENT-PROMPT.md`

## Contract

The workflow supports manual `workflow_dispatch` and reusable `workflow_call`, accepts a selected ref and `focused`/`full` mode, uses Linux/Python 3.12, installs only declared dependencies plus Pagefind, and uploads bounded logs only on failure or cancellation.

It has `contents: read`, no secrets or deployment permissions, explicit polling/read-only safety settings, isolated pytest state, no live collection/model calls, and no runtime/canary-data import.

## Validation status

No application tests were run locally and the workflow was not triggered. YAML/static inspection, command-path review, and documentation diff checks are the local validation scope.

