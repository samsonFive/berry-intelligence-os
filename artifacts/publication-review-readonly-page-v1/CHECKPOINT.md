# Publication Review Read-only Page V1 — checkpoint (2026-09-16)

Branch: `feature/publication-review-readonly-page-v1` in
`C:/Users/Johnny/Downloads/sscanar/berry-intelligence-os-publication-review-readonly-page-v1`,
based exactly on `2100d2ae9a5752695d4d37bbbe84d5a467ac8336`
(`feature/publication-review-durable-read-model-v1`). No merge, push
(beyond this branch), PR, or canonical/live data mutation performed.

## Origin

Informal, user-initiated side task (not a formal mission spec): while
waiting on Orchestrator credits, the user asked what to work on next and
picked "wire the just-built read model into a genuinely read-only HTTP
page" over the alternative I offered (fixing the documented
`classify_source_body()` key-name bug). Confirmed with the two-word
reply "read only page".

## What was built

1. **`app/main.py`** — five new imports
   (`publication_review_domain.REVIEW_STATES`,
   `publication_review_query.get_detail`/`list_queue`/`status_summary`,
   `publication_review_repository.DurableReviewRepository`/
   `resolve_review_state_dir`) and one new route,
   `GET /review-ops/publications`
   (`publication_review_readonly_page`). The handler only ever calls the
   existing, already-tested read functions from
   `app/services/publication_review_query.py` — it never imports or
   calls `PublicationReviewCommandService`, never writes to the durable
   repository, and never touches `data/evidence/`.
2. **`app/templates/publication_review_readonly.html`** — a new
   template, written from scratch using only already-existing, already-
   merged CSS classes (the same `page-heading`/`v2-company-section`/
   `balanced-card-grid`/`card`/`badge`/`table-wrap`/`empty-state`
   convention as `collection_ops.html`). It contains **no `<form>`, no
   `<button>`, and no reference to a decision-command endpoint** —
   filters and pagination are plain `<a href="?...">` GET links, and
   `permitted_commands` is rendered as inert text, never a control.
   Deliberately does NOT copy or adapt anything from Grok's frozen,
   unmerged `feature/publication-review-readonly-ui-v1` branch
   (`d19ee0a`) — built independently, per the standing instruction not
   to merge or modify that reference.
3. **`tests/test_publication_review_readonly_page.py`** — 6 focused
   tests (see below).
4. This checkpoint.

Nothing else was created or modified.

## Verification

- New route tests: **6 passed** —
  empty-store rendering, populated queue+detail rendering, no decision-
  control markup anywhere in the page's own content, no full-acquired-
  body leakage (a unique tail marker beyond the 500-char excerpt bound
  never appears in the response), GET issues zero mutation to the
  durable repository (version/updated_at unchanged across two GETs),
  and state filtering actually filters.
- Existing publication-review domain/repository/command/crash-recovery/
  migration/static-safety/query suites: **208 passed, 9 skipped**
  (intentional), 0 failed — unaffected.
- `tests/test_collection_ops.py`: unaffected (used purely as the
  route/template convention reference).
- `scripts/validate_records.py`: all validated records passed.
- Full project test suite: run in background; see follow-up note if
  this checkpoint predates its completion.

## Bug fixed during implementation

The template initially wrote `{% for item in queue.items %}` against
the `queue` context variable, which is a plain `dict` (from
`QueuePage.as_dict()`). Jinja2 resolves `foo.items` as `getattr` before
falling back to `foo['items']`, so `queue.items` silently returned
`dict.items` (a bound method), raising
`TypeError: 'builtin_function_or_method' object is not iterable` at
render time. Fixed by using bracket access (`queue['items']`) for the
two places this collision applied. `summary.by_state.items()` was left
as attribute+call syntax since `by_state` is a genuine, non-colliding
key holding a real dict, where calling `.items()` is the intended
`dict.items()` method call, not a lookup.

## Required statements

**READ-ONLY PAGE ADDED: YES**
**DECISION CONTROLS PRESENT: NO**
**CANONICAL/LIVE DATA MUTATED: 0**
**FULL ARTICLE BODY LEAKAGE: 0**
**FROZEN BRANCHES MODIFIED: NO** (`cf6d193` command-service branch and
Grok's `d19ee0a` UI reference were neither read nor touched by this
task — this task built only on `2100d2a`, the durable read-model
branch, and never needed to re-inspect either frozen branch since the
read model's own contract was already fully documented)

## How to view it

Start the app and open `/review-ops/publications` (optionally
`?state=pending_review` or `?selected=<draft_id>`). With no durable
review-state store configured, it shows an honest empty queue rather
than inventing backlog.

## What is deliberately NOT done here

- No decision/command invocation, form, or button of any kind.
- No authentication/authorization change.
- No canonical mutation, no new persistence.
- No merge of, or commit onto, `feature/publication-review-readonly-ui-v1`
  (`d19ee0a`) or `feature/publication-review-command-service-v1` (`cf6d193`).
- No PR, force-push, or deployment.
