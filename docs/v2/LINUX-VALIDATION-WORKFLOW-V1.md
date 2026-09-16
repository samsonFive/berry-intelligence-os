# Linux Validation Workflow V1

## Purpose

`.github/workflows/linux-validation.yml` is a manual/reusable validation workflow for an arbitrary branch, tag, or commit. It is designed to replace unreliable Windows-local validation for this repository’s Python 3.12 contract.

It uses `ubuntu-latest`, `actions/setup-python@v5` with Python 3.12, the declared `requirements-dev.txt` dependency set, and CI’s existing Pagefind installation convention. It has `contents: read` only and no deployment environment, write permission, credential, or secret reference.

## Modes

### Focused

Runs the integrated competitor/acquisition/company focused tests, record validation, static-public safety tests, the trusted static build, and required public artifact checks.

### Full

Runs every focused step and then:

```bash
python -m pytest -vv --tb=short --durations=50 -p no:cacheprovider --basetemp "$RUNNER_TEMP/berry-validation-pytest-${GITHUB_RUN_ID}/full"
```

The full job has a 90-minute timeout, based on the previous long-running suite behavior. Pytest logs preserve node IDs, short tracebacks, warnings, and the 50 slowest tests.

## Operator instructions

1. Open GitHub Actions and select **Linux validation**.
2. Select **Run workflow**.
3. Use the branch containing this workflow in the workflow-ref selector.
4. Enter the branch/tag/SHA to validate in `ref`. Prefer a full SHA for a frozen checkpoint. If blank, the selected workflow ref is checked out.
5. Select `focused` for fast gates or `full` for the complete deterministic suite.
6. Confirm the run’s checkout SHA in the environment log before using the result.
7. On failure or cancellation, download `linux-validation-logs-<run_id>` and inspect `failure-summary.log`, the complete pytest log, record-validation log, static-build log, and environment/package log.

The workflow is also reusable through `workflow_call`; a trusted caller supplies `mode` and `ref` as inputs. Inputs are validated as data: the ref is passed to `actions/checkout`, and the mode is checked against `focused|full` before shell execution. No input is concatenated into a command.

## Safety contract

- `contents: read` is the only workflow permission.
- `ENABLE_SOURCE_POLLING=false` and `BIOS_MODE=readonly` are explicit safety settings.
- No `PERPLEXITY_API_KEY`, extraction key, or other secret is read or passed.
- No collection CLI, model API, publication, approval, deployment, or Pages action is present.
- Pytest state uses `$RUNNER_TEMP` basetemp directories and disables the cache provider for the full suite.
- Logs are outside the checkout. Generated sites are checked only for required files and are never uploaded.
- The workflow does not copy or import `inbox/`, canary records, analyst state, or runtime artifacts.
- Concurrency cancels redundant validation for the same ref/mode pair.

## Failure classification guide

Classify only from evidence in the logs:

| Class | Indicators | Action |
|---|---|---|
| Regression | Assertion/test failure on the target ref, reproducible in an isolated rerun | Report node ID and shortest traceback; do not repair in validation. |
| Mutable-data/isolation issue | Failure changes with runtime state, shared files, or concurrent writes | Rerun with clean runtime/basetemp; document the state boundary. |
| Dependency/environment | Install failure, missing executable, runner/tool failure, or package resolution error | Preserve package/environment log; do not silently substitute versions. |
| Python 3.12 incompatibility | Declared package or application fails specifically under 3.12 | Report exact package/runtime error and stop release claims. |
| Static-public safety failure | Private ID/title/body, missing required artifact, or build leak check fails | Treat as a release blocker until reviewed. |
| Known limitation | Existing documented behavior with matching checkpoint evidence | Link the governing document and avoid calling it a regression. |
| Indeterminate | Timeout, cancellation, infrastructure outage, or incomplete log without reproducible failure | Preserve logs and rerun before comparison. |

Never classify a failure as pre-existing or integration-specific without the same node and materially equivalent baseline evidence.

## Validation boundaries

This workflow validates a checked-out ref in an ephemeral Linux runner. It is not a collection runner and does not prove live source recall, deployment state, current market activity, or model qualification. A successful run proves only the tests and build gates executed by the selected mode for the recorded SHA.

