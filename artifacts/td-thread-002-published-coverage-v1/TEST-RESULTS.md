# Test results

Base SHA compared: `c0de14c88960c22fee97a51fef0c71ffe386bcf9`.

## Story Threads (`tests/test_story_threads.py`)

Exact base (before this change): **17 passed, 1 failed**.

This branch: **34 passed, 1 failed** (17 new cases). The single failure is inherited:

- `test_brief_review_soon_collapses_reprint_into_review_now_thread` — Hortifrut fixtures dated `2026-07-30` fall outside the 45-day pending-triage “review now” window as of 2026-09-16. Reproduced on the exact base. Not repaired here (calendar-sensitive; #255-class, not a matcher change).

New cases cover: two recent trusted reprints thread; unrelated trusted do not; co-mention insufficient; weak title insufficient; outside-window excluded from universe; pending/trusted id dedupe; stored `follows_up` still expands; canonical URL is one thread; stable ids/order; no trust mutation; bounded universe; `/threads` + `/intelligence` routes; static source-level prohibition; pending sentinel absent from static HTML.

## Adjacent suites (this branch)

| Suite | Result |
|---|---|
| Publication / Evidence / static-safety slice (`test_build_static`, `test_review_events`, `test_review_publish_duplicate`, `test_publication_review_source_fidelity`, `test_trusted_evidence_semantics_repair_v1`, selected private-row tests) | 42 passed |
| Global Search + Landscape (`test_global_search`, `test_landscape_v2`, `test_synthesis_views`) | 93 passed |
| `python scripts/validate_records.py` | All validated records passed |
| `python scripts/build_static.py` | 1628 pages; “Verified: no unpublished draft ids or titles appear in the output.” |

## Full suite vs exact base

This branch: **4 failed, 2638 passed** in 1065s.

Exact base (`c0de14c`, same four tests restashed to empty tree): **the same four tests fail**. None is introduced by this change.

| Failure | Class | Notes |
|---|---|---|
| `tests/test_intelligence_front_page_v1.py::test_front_page_route_smoke` | Inherited calendar / 14-day `/today` window | Expects `FRESH / UNREVIEWED` on a fixture that has aged out as of 2026-09-16. Repaired on unmerged PR #255; not copied here. |
| `tests/test_today.py::test_today_route_front_page_and_mobile_css` | Inherited calendar / 14-day `/today` window | Expects `REVIEWED EVIDENCE` in the same window. Same #255 class. |
| `tests/test_perplexity_semantic_pulse_v1.py::test_front_page_publication_classification_is_provider_agnostic` | Inherited (`now=None` / empty qualifying set) | Reproduced on exact base. |
| `tests/test_story_threads.py::test_brief_review_soon_collapses_reprint_into_review_now_thread` | Inherited 45-day pending-triage calendar | Hortifrut `2026-07-30` vs 2026-09-16. Reproduced on exact base. |

No Learner, competitor-intelligence, or publication-review files were changed to green this branch.
