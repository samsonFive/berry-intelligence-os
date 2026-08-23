# CI / Merge Gate Reliability V1

**Status:** GitHub-proven in PR #95; canonical branch protection enabled.

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

PR [#95](https://github.com/samsonFive/berry-intelligence-os/pull/95) attached all four contexts to implementation head `2f493c9a2657e19e9a3d108afe39fb63093a2f8f`; the prior PRs audited for this mission had empty `statusCheckRollup` arrays. [Run 32616187135](https://github.com/samsonFive/berry-intelligence-os/actions/runs/32616187135) passed in 2m49s wall-clock:

- Change scope: 5s.
- Repository integrity: 27s; record validation passed.
- Static public safety: 1m13s; 14 focused tests passed, 1,527 pages built, and the unpublished-draft scan passed.
- Python tests: 2m41s job duration; 1,260 passed and 2 platform skips in 2m06s of test time.

Intentional failure head `d11eb49569f4fda31dae84ad633775af197c7d7a` added an unresolved-marker fixture. [Run 32616355047](https://github.com/samsonFive/berry-intelligence-os/actions/runs/32616355047) made `Repository integrity` fail in 4s with exit code 2. The repair push removed the fixture; per-PR concurrency cancelled the obsolete run, including its still-running/pending work. Fresh [run 32616410878](https://github.com/samsonFive/berry-intelligence-os/actions/runs/32616410878) attached to repaired head `d8e53fb4265391b61b3e2a8e1738f9e98da1a837` and passed all four checks again (4s / 27s / 1m12s / 2m31s respectively). No result from the prior head was treated as current.

Branch protection was then enabled on `v2/intelligence-os`. The live API response reports `strict: true`, admin enforcement enabled, pull requests required with zero newly invented approval-count requirement, force pushes/deletions disabled, and exactly the four GitHub Actions contexts listed above (GitHub Actions app id `15368`) required.

Temporary PR [#96](https://github.com/samsonFive/berry-intelligence-os/pull/96) tested the genuine fast path as a one-file Markdown-only diff against the implementation branch. [Run 32616798032](https://github.com/samsonFive/berry-intelligence-os/actions/runs/32616798032) retained and passed all four contexts in 4-6s. Step-level results prove Python setup, dependency installation, tests, record validation, promotion tests, static generation, and artifact checks were skipped. The proof PR was closed without merge and its remote branch deleted.

The implementation merge SHA and post-merge Pages result are recorded in the mission handoff because they necessarily occur after this version of the document is committed.

## Stale production freeze audit

The optional read-only VPS audit found `/opt/berry-intelligence-os/DEMO-FREEZE.txt` is an untracked 393-byte artifact dated 2026-08-18. It names old canonical `ed5977ad` and old PR constraints, while the production checkout was already at later `f9eb920d`; it is stale advisory text, not an active scheduler or deployment control. The adjacent untracked `demo-runtime.tar.gz` was not opened, changed, or deleted. Neither artifact is a CI blocker; cleanup remains an explicit operator decision because the archive may be non-regenerable.

## Remaining limitations

- GitHub-hosted Actions depends on GitHub runner availability and on dependency registries for a cold cache.
- The leakage gate proves absence of known runtime sentinels and retains the builder's draft-ID/title scan; it is not a general information-flow proof for every future private field. New private runtime stores must add a sentinel fixture before merge.
- Required review count remains a repository governance choice separate from this reliability mission; the merge gate enforces machine checks without inventing a human-approval policy.
