# Intelligence OS — Technical Debt Register (V2)

**Status:** Live ledger. Every known, unresolved bug/limitation surfaced by an agent report gets an entry here — the point is that expansion decisions stop depending on what someone happens to remember from a prior session's transcript. Add an entry the moment a real limitation is found, even if fixing it is out of scope for the current mission. Update `Status`/`Resolved in` in place when it's actually fixed; do not delete a resolved entry, so the register stays a real history, not just a current-open list.

**Fields:** ID · Severity (Low/Medium/High) · Impact (states the concrete failure scenario, which also carries the entry's Evidence — a real observed case, not a hypothetical) · Owner lane (also this entry's Area) · Status (Open/Monitoring/Resolved/Won't-fix) · Resolved in (PR/SHA, once applicable) · Regression test. This is a compatible subset of `INTELLIGENCE-EXPANSION-BUILD-GUIDE.md` Section 15's suggested schema (which also names Area, Evidence, Compounding risk, Fix class, and Introduced/observed as separate columns) — folded together here rather than split into more columns because every entry so far has a short enough real-world description that splitting Impact/Evidence/Compounding-risk into three fields would repeat itself. Split them out for a future entry if that stops being true.

Ranked within each lane by severity, highest first. Lanes are grouped, not prioritized against each other — a Low item in one lane isn't "less important" than a Medium in another, just smaller in isolated blast radius.

**Debt rules** (per the build guide): a production bug discovered during a mission is registered here if not fixed immediately. A known issue mentioned in a completion report is registered unless intentionally accepted (and noted as such). No "we'll remember this later." Critical/high debt that threatens trust, data loss, deployment reproducibility, or source correctness blocks feature expansion until resolved; Medium/Low debt can be scheduled, but must stay visible here, not just in a prior session's transcript.

---

## UI / presentation lane (Cursor)

### TD-UI-001 — Morning Brief global nav cost

**Severity:** Medium · **Impact:** Normal HTML page loads can still trigger Morning Brief's own work when the nav cache is cold — the API-path version of this was already fixed, but a hidden multi-second computation can still ride through the application shell on an ordinary page render, degrading perceived performance for anyone, not just Brief visitors.

**Description:** the nav renders a Brief-derived action count on every page. When that cache is cold, computing it re-runs Brief-equivalent work inline in the request path instead of failing cheap or deferring.

**Fix direction:** a generic caching/precompute solution for anything the global nav shell depends on, not a Brief-specific patch — the same pattern would recur for any other nav-embedded computation.

**Owner lane:** UI (Cursor) · **Status:** Open · **Resolved in:** — · **Regression test:** —

---

### TD-UI-002 — Company assessment berry scope

**Severity:** Medium · **Impact:** A Strawberry-filtered company page can surface company-wide Bottom Line assessments that mention blueberry, because Assessment records have no berry-scope field to filter on. This may be entirely correct for a genuinely corporate-level assessment (an assessment about the company's overall strategy legitimately spans berries) — the debt is the *absence of explicit semantics*, not necessarily the current display.

**Description:** `schemas/assessment.schema.json` has no `berry_ids`/scope field (see `app/queries/scope.py`'s D-012 note: Assessment/Recommendation use `market_ids`, not yet consistently populated for berry scope). A berry-filtered view can't currently distinguish "this assessment is about the company across all berries" from "this assessment happens to mention blueberry in passing and should be filtered out of a Strawberry view."

**Fix direction:** decide and document the real semantics first (is an Assessment berry-scoped by default, or explicitly cross-berry unless scoped?), then make the schema/UI agree — not a UI-only fix, since the underlying data has no scope signal to filter on yet.

**Owner lane:** UI (Cursor) + domain model (schema) · **Status:** Open · **Resolved in:** — · **Regression test:** —

---

### TD-UI-003 — Compact view semantic duplication

**Severity:** Low · **Impact:** "PENDING" plus a separate Patent/kind label duplicate the same underlying status information in the compact card view — confusing, not incorrect. Easy cleanup.

**Owner lane:** UI (Cursor) · **Status:** Open · **Resolved in:** — · **Regression test:** —

---

### TD-UI-004 — Legacy landscape context copy

**Severity:** Low · **Impact:** A Strawberry Landscape page can still display old "Berries / Blueberry / Global" breadcrumb copy — an unmigrated-page issue from before the multi-berry portability audit generalized the Landscape route. Now that the app genuinely supports four berries (real content on all four, not just the route), blueberry-specific presentation leakage should be treated as debt rather than a cosmetic footnote — it's exactly the class of hidden coupling the portability audit was built to catch, just missed on this one page.

**Owner lane:** UI (Cursor) · **Status:** Open · **Resolved in:** — · **Regression test:** —

---

## Story Threads / matching lane

### TD-THREAD-001 — Company-primary vs. variety-primary false separation *(resolved)*

**Severity:** Medium · **Impact:** Real related coverage (a company-led headline and a variety-led headline about the same event) failed to thread, because `_strong_event_edge()` requires exact `primary_subject` equality and headline phrasing routinely sends the two articles' primary subjects to different entity types. Observed in real Strawberry (RedSayra/Planasa) and Raspberry (Malaika/TSBC) data.

**Description:** see `docs/v2/` mission report (Story Thread Subject-Attribution Robustness, 2026-08-20) for the full root-cause trace.

**Fix:** added `_cross_subject_event_edge()` to `app/services/story_threads.py` — a conservative, additional edge that fires only when the same company AND the same named variety are each independently confirmed on both sides, plus date proximity. Does not loosen `_strong_event_edge`.

**Owner lane:** Story Threads / matching · **Status:** Resolved · **Resolved in:** branch `feature/story-thread-subject-attribution` (PR/SHA recorded once merged — see PROJECT-STATUS.md for the current value) · **Regression test:** `tests/test_story_threads.py` — 6 new cases, real observed data (Malaika, RedSayra, Chambers/Cornell, Planasa/Blue Manila/Blue Maldiva).

---

### TD-THREAD-002 — Live thread routes only ever see pending drafts plus one seed

**Severity:** Low-Medium · **Impact:** `/threads/{id}` and the entity "Recent Intelligence" panel build their threading `universe` from `list_pending_drafts()` plus, at most, the one currently-viewed record if it's published. A cluster of several already-*trusted*, already-published articles about the same event is never assembled into a thread by the live app, even though `group_story_threads()` itself would happily group them if given the full set. Found while auditing the primary-subject pipeline for TD-THREAD-001 — a real, generic boundary, not specific to any one route.

**Description:** `app/main.py`'s `story_thread_reader()` and `_intelligence_page_context()` both build `universe` this way. Every cross-berry Story Thread test performed in the portability/vertical missions had to manually assemble a broader record set (all trusted Evidence + all pending drafts) to observe real multi-source clustering — the production routes never do this themselves.

**Fix direction:** decide deliberately whether trusted-only clusters should ever surface as threads in the live UI (a real product decision, not just a bug fix — Cursor owns this call), then, if yes, extend `universe` assembly to include recently-published trusted Evidence, not just pending drafts.

**Owner lane:** Story Threads / route wiring (Cursor for the product decision; either lane for the mechanical extension) · **Status:** Open · **Resolved in:** — · **Regression test:** —

---

## Acquisition / dedup lane

### TD-ACQ-001 — Duplicate detection misses same article via Google-News-redirect URL vs. publisher's direct RSS

**Severity:** Medium · **Impact:** The same real article, discovered twice — once via a Google-News-redirect-URL alert feed (different URL, title carries a "- Source Name" suffix) and once via the publisher's own direct RSS feed (canonical URL, no suffix) — is not recognized as a duplicate by the existing title+URL dedup, producing a real duplicate draft each time the source is re-polled. Documented and handled as untracked-inbox cleanup (not a code fix) in an earlier session; recurred and was cleaned up again during both the Strawberry and Raspberry Vertical V1 missions (same deterministic draft id both times — `ev-media-cec61845f15d790fd055`), confirming it's a stable, repeatable gap, not a one-off.

**Description:** `app/services/article_dedup.py`'s existing rule (normalized canonical URL, then conservative normalized-title + same-source + same-date — deliberately never title-similarity alone, per an earlier session's explicit finding that fuzzy matching is too risky) can't catch this pair without loosening in a way that was already evaluated and rejected.

**Fix direction:** unresolved by design — the safe fix would need a narrower, still-conservative signal (e.g., a normalized-title-minus-suffix comparison scoped only to a small known set of "- Source Name"-style suffixes) rather than general fuzzy matching. Worth a dedicated look before the next source-heavy acquisition mission, since it will keep recurring on every re-poll of an already-seen article.

**Owner lane:** Acquisition / dedup · **Status:** Open (known, accepted, cleaned up manually each time it appears) · **Resolved in:** — · **Regression test:** —

---

### TD-ACQ-002 — Growing Produce – Berries feed returns 403

**Severity:** Low · **Impact:** One real, previously-working discoverable source (`source-20260819-growing-produce-berries`) returned HTTP 403 during a real ingestion run in the Strawberry Vertical V1 mission (2026-08-20). Not scraped around, per the project's standing no-brittle-scraping discipline.

**Fix direction:** re-check periodically; if persistent, mark the source's discovery block inactive rather than let every future ingestion run silently fail against it.

**Owner lane:** Source health · **Status:** Open (monitor) · **Resolved in:** — · **Regression test:** —

---

### TD-ACQ-003 — NARBA raspberry/blackberry association feed is real but empty

**Severity:** Low · **Impact:** none currently (correctly not onboarded).

**Description:** `raspberryblackberry.com/feed/` is a live-verified, well-formed RSS 2.0 feed with zero `<item>` entries as of 2026-08-20 (checked during the Raspberry Vertical V1 mission). A real, structurally sound source with nothing to discover yet.

**Fix direction:** re-check before/during the Blackberry depth work — if NARBA starts publishing, it's a real, high-value raspberry+blackberry-specific source worth onboarding immediately.

**Owner lane:** Source health · **Status:** Monitoring · **Resolved in:** — · **Regression test:** —

---

### TD-ACQ-004 — Non-English relevance coverage verified for Spanish/Italian only

**Severity:** Medium · **Impact:** `app/services/relevance_screen.py`'s `berry_identity` category had zero non-English terms of any kind until the Strawberry Vertical V1 mission added Spanish and Italian species names (fresa/fragola, arándano/mirtillo, frambuesa/lampone, mora). Real sources in the registry publish in other languages too (Polish, Dutch, Portuguese content is already visible in captured Evidence titles — "Time for Polish strawberries," "Dutch berry grower adds another 18 ha") that have never been explicitly tested the way Spanish/Italian were.

**Fix direction:** the Raspberry mission proved the existing Spanish/Italian fix transfers to a second berry with zero further work — the same explicit-test-don't-assume discipline should be applied before onboarding a Polish- or Dutch-language source specifically, rather than assuming the pattern holds a third time.

**Owner lane:** Relevance / acquisition · **Status:** Open · **Resolved in:** — · **Regression test:** —

---

## Domain model / entity resolution lane

### TD-ENT-001 — Domain-pack relationship-predicate spec is wider than the enforced schema

**Severity:** Low · **Impact:** `domain-packs/berries/taxonomies/relationship-predicates.json` declares 16 predicates (the 10 v1 predicates plus 6 documented extensions: `exhibits_claimed_trait`, `protects`, `markets`, `offers`, `administers_license_for`, `subsidiary_of`), but `schemas/relationship.schema.json`'s actual enum only accepts the original 10 — confirmed by a real validation failure when the Raspberry Vertical V1 mission tried to use `administers_license_for` for a genetics-representation relationship (Global Plant Genetics representing James Hutton Ltd) and had to fall back to the less-precise `licenses`.

**Fix direction:** either extend the live schema's enum to match the documented spec (if the 6 extensions are genuinely intended to be usable), or correct the domain-pack spec to describe only what's actually enforced. A real, small drift between planning documentation and enforced schema — worth resolving deliberately rather than leaving every future agent to rediscover it by hitting the same validation error.

**Owner lane:** Domain model / schema · **Status:** Open · **Resolved in:** — · **Regression test:** —

---

### TD-ENT-002 — "Allberry B.V." vs. "Advanced Berry Breeding B.V." unresolved patent assignee

**Severity:** Low · **Impact:** Two real raspberry plant-patent drafts ("ABB 135"/"ABB 136") are assigned to "Allberry B.V.", not "Advanced Berry Breeding B.V." — the same "ABB" cultivar-naming convention and inventor (Niels Arts) as ABB's confirmed real varieties suggest they're plausibly the same company (a rename, rebrand, or holding-company structure), but this was deliberately left unconfirmed and unlinked rather than force-aliased on circumstantial evidence.

**Fix direction:** a real corporate-registry lookup (Netherlands KVK or similar) would resolve this definitively. Left open rather than guessed.

**Owner lane:** Entity resolution / patents · **Status:** Open · **Resolved in:** — · **Regression test:** —

---

### TD-ENT-003 — No USDA entity despite real USDA-ARS patent assignees appearing in the corpus

**Severity:** Low · **Impact:** at least one real raspberry patent (Finnberry) is assigned to "The United States Of America, As Represented By The Secretary Of Agriculture" — the standard USDA-ARS plant-patent assignee format — with no corresponding entity in the graph, so it stays permanently unresolved rather than temporarily unresolved.

**Fix direction:** a single real `company-usda-ars` (or `breeding_program-usda-ars`) entity, with that exact string as an alias, would resolve this and any future USDA-assigned filing across all four berries at once — a small, generic, high-leverage addition whenever a session has room for it.

**Owner lane:** Entity resolution / patents · **Status:** Open · **Resolved in:** — · **Regression test:** —

---

## Human review backlog lane

### TD-REVIEW-001 — Real, valuable variety content sitting in untrusted drafts

**Severity:** Low (this is backlog, not a bug) · **Impact:** several real, current, independently-sourced variety announcements have been discovered by live ingestion but correctly not promoted to trusted entities, since a trusted entity should never be grounded in an untrusted draft alone: **Elyson** and **Rossetta** (Nova Siri Genetics, strawberry), **Pink Hudson** (Planasa, raspberry — real International Taste Institute score, 90.7 pts/Three Stars), and **Demoiselle** (Planasa, strawberry — real SIVAL Innovation Gold Award). All four are staged in `inbox/evidence/` as real, review-ready drafts.

**Fix direction:** none needed architecturally — this is exactly what the human publication-review gate is for. Listed here so a future session doesn't have to re-discover these through another ingestion run; a reviewer promoting them directly would unlock real, already-verified variety depth for two verticals at once.

**Owner lane:** Human review (publication queue) · **Status:** Open (awaiting reviewer action, not code) · **Resolved in:** — · **Regression test:** —

---

## Test infrastructure lane

### TD-TEST-001 — One test hardcodes a Linux-only path

**Severity:** Low · **Impact:** `tests/test_morning_brief.py::test_real_reading_queue_morning_workload_is_smaller_than_unresolved` writes to `/opt/cursor/artifacts/morning_brief_workload.json`, which doesn't exist on a Windows dev machine — fails identically against unmodified canonical, confirmed repeatedly across many sessions. Not a product bug.

**Fix direction:** make the artifact path configurable (an env var or a `tmp_path`-relative default) so the test is portable across dev environments, rather than permanently Linux-only.

**Owner lane:** Test infrastructure · **Status:** Open (known, safe to ignore on Windows dev machines) · **Resolved in:** — · **Regression test:** n/a (this entry describes a test itself)

---

## Adding a new entry

Copy the format above: an ID in the right lane's prefix (`TD-UI-`, `TD-THREAD-`, `TD-ACQ-`, `TD-ENT-`, `TD-REVIEW-`, `TD-TEST-`, or a new lane prefix if none fits), Severity, Impact stated as a concrete failure scenario (not just "this could be better"), a fix direction if one is known, Owner lane, Status, and Resolved-in/Regression-test once applicable. An entry with no concrete impact scenario isn't ready to add yet — keep investigating instead of registering a vague feeling.
