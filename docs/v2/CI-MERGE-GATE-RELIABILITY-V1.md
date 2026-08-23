# CI / Merge Gate Reliability V1

**Status:** Implemented; GitHub run and branch-protection proof is recorded below before merge.

## Purpose

Pull requests to `v2/intelligence-os` previously showed no checks because the only repository workflow, `.github/workflows/deploy-pages.yml`, ran on pushes to `master` and `v2/intelligence-os` (plus manual dispatch). It had no `pull_request` trigger. GitHub branch protection and repository rulesets were also absent, so locally reported validation was informative but not an enforced merge gate.

This mission adds `.github/workflows/pr-validation.yml`. It validates the exact pull-request head SHA on every open, reopen, ready-for-review, and synchronize event. It has read-only repository permission, receives no application secrets, uses no deployment credentials, and never deploys. The existing Pages workflow remains the only deployment workflow.

## Required check contract

The protected canonical branch requires these stable check-run names:

- `Change scope`
- `Repository integrity`
- `Static public safety`
- `Python tests`

The workflow uses one concurrency group per pull request and cancels obsolete runs after a newer push. Every required job checks out the event's exact head SHA.

### Repository integrity

- Rejects whitespace errors in the base-to-head diff with `git diff --check`.
- Rejects unresolved merge markers.
- Runs canonical record/schema validation for every executable, configuration, schema, or data change.
- Adds a focused canonical-promotion regression run whenever trusted evidence/configuration, schemas, the promotion script, or the container entrypoint changes.

### Static public safety

- Exercises the trusted-static-snapshot tests.
- Plants unpublished draft, review-event, reviewer, analyst-queue, signal-candidate, and unpublished-proposal sentinels and proves none occur in generated HTML.
- Retains the focused checks that private reviewer dispositions and Commercial Position private rows do not enter the public model.
- Builds the complete static site and verifies its key output and Pagefind artifacts.

### Python tests

Every non-Markdown-only pull request runs the complete deterministic `pytest` suite. This is intentionally a full-suite gate: recent canonical Pages runs complete their combined test, record-validation, static-build, artifact, and deployment path in roughly four minutes, so a reduced default suite is not justified by current economics.

One previously environment-dependent test is now hermetic. `test_observations_runtime_without_inbox_is_honest` uses a temporary empty inbox instead of whichever mutable operator inbox happens to exist beside the checkout. The assertion continues to use real canonical records.

## Path policy

The only fast path is a change set containing one or more `.md` files and no other path. All four check contexts still report; repository hygiene runs, while dependency installation, tests, record validation, and static generation are skipped because Markdown is not a static-site build input in this repository.

Everything else is a full validation change, including GitHub Actions YAML, Python, templates, JavaScript/CSS, requirements, configuration, trusted data, and schemas. Data/promotion-sensitive paths additionally exercise `tests/test_sync_trusted_data.py`. There is no broad `paths-ignore` rule that could make a required context disappear.

Dependency downloads may access package registries on a cold runner; the validation itself must not call production services or application APIs. Python dependency caching is keyed by the checked-in requirements files. No runtime data, inbox, review history, session credential, or deployment secret is provided to PR jobs.

## Pages separation

`.github/workflows/deploy-pages.yml` remains push/manual only. It still runs full tests, record validation, and static generation before uploading and deploying the Pages artifact. PR validation cannot publish Pages and has only `contents: read`; the deploy workflow retains its narrowly required `pages: write` and `id-token: write` permissions.

## Operator merge procedure

1. Fetch `origin/v2/intelligence-os` and reconcile the PR head with the actual canonical head.
2. Wait for all four required contexts on the resulting head SHA. Local success does not substitute for GitHub checks.
3. If checks do not appear, diagnose trigger, Actions policy, and check-run state; do not waive the missing gate.
4. If canonical moves, rebase or merge canonical as appropriate, push the reconciled head, and wait for a fresh set of checks on that new SHA.
5. Merge only while the PR reports the required head checks successful and is current with canonical.

## GitHub proof

The final implementation PR, run URLs, head SHAs, durations, intentional red-gate proof, docs-only fast-path proof, branch-protection response, merge SHA, and post-merge Pages result are added here after they exist. This section is deliberately evidence-driven rather than pre-filled with expected results.

## Remaining limitations

- GitHub-hosted Actions depends on GitHub runner availability and on dependency registries for a cold cache.
- The leakage gate proves absence of known runtime sentinels and retains the builder's draft-ID/title scan; it is not a general information-flow proof for every future private field. New private runtime stores must add a sentinel fixture before merge.
- Required review count remains a repository governance choice separate from this reliability mission; the merge gate enforces machine checks without inventing a human-approval policy.
