# Next agent — run Linux validation against Wave 2

Read `AGENTS.md`, `docs/v2/LINUX-VALIDATION-WORKFLOW-V1.md`, and this checkpoint first.

When the Wave 2 branch has a reviewed checkpoint and exact SHA:

1. Open GitHub Actions → **Linux validation**.
2. Select the workflow ref containing this workflow.
3. Enter the Wave 2 full SHA in `ref`.
4. Run `focused` first; inspect the recorded checkout SHA, test summary, record validation, static build, and public artifact checks.
5. If focused passes, run `full` once for the same SHA.
6. Download failure logs if needed. Classify every failure using the workflow guide; do not repair code in the validation mission.
7. Compare against a baseline run on the exact prior integration SHA using the same mode and workflow revision.

Do not run collection, model calls, publication, approval, deployment, or import ignored canary data. Treat a missing/unfinished Wave 2 checkpoint as pending, not as a validation target.

