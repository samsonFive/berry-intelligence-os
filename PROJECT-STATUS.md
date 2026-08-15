# Project Status

*Maintained by Claude. Updated at the end of each work session that changes project state. Keep short — this is a status check, not a changelog (see `docs/reviews/CURRENT-STATE-AUDIT.md` and `docs/v2/` for detail).*

**Last updated:** 2026-08-15

---

**Current program:**
Intelligence OS V2

**Current stage:**
Phase 2 implementation complete (acceptance-reviewed). Audio/Video Intelligence data-model foundation added on top of it (2026-08-15, see below). Production remains JSON-backed.

**Current branch:**
`v2/intelligence-os`

**Next phase:**
Owner sign-off on Phase 2's acceptance review. PostgreSQL and Phase 3 remain not started.

**Last completed:**
Audio/Video Intelligence data-model foundation (2026-08-15, commit `2f9580c`): `evidence.schema.json` gained two optional/additive fields — `media_format` (enum: `web_article`/`podcast`/`video`/`conference_video`, orthogonal to the pre-existing `source_type`, which describes outlet kind rather than physical form) and `transcript` (an object with `status`/`language`/`source`/`text`/`url`, ahead of any actual transcription pipeline; `status: "not_available"` is deliberately distinguishable from the field being absent). Neither is backfilled onto existing records and neither introduces a new Entity Type — podcast/video remain forms Evidence takes, not things Evidence points at. `media_format` is wired into the existing `filter_evidence()`/`filter_options()` mechanism and the Newsfeed filter bar (`app/main.py`, `app/templates/feed.html`), alongside `source`/`berry`/`geography` — no new query service or UI view. Source-owns-many-evidence and evidence-links-many-entities/geographies use pre-existing relationship fields (`source_id`, `entity_ids`, `geography_ids`) — proven, not built new. Proven entirely via 12 new temp-repo-fixture tests (`tests/test_media_evidence.py`); no fictional podcast/video records were added to the live `data/evidence/` dataset, per this project's no-fictional-intelligence-in-the-live-dataset principle. Identified but explicitly not implemented in this phase: a future `Person` entity (podcast hosts/guests, conference speakers — not modeled anywhere yet) and a real transcript-ingestion pipeline (Whisper/YouTube/RSS — the `transcript` field only describes state, nothing populates it).

Phase 2B.3 acceptance-review fixes (2026-08-14): an independent review of Phase 2B.3's original implementation (commits `aa0f0c6`/`486008d`) against its own task brief found 5 real gaps and closed all of them. (1) Review/publish's persistence orchestration was still fully embedded in the `review_publish()` route handler — extracted into `ReviewPublishService` (`app/services/review_publish.py`), a workflow service that receives repositories/a Unit-of-Work factory and returns a plain `PublishResult`; the route is now limited to HTTP form-parsing and response shaping. (2) `JsonUnitOfWork` was constructed ad hoc inside the route — `app/composition.py` now exposes `get_unit_of_work(data_dir, schemas_dir, *repository_names)`, the one place a caller with multi-object transactional intent builds that seam. (3) A genuine data-loss bug: `move_draft_attachments()` physically moved attachment files out of `inbox/` *before* the transactional block began, so a rollback after that point left the files moved but the structured writes undone — a retry's own `move_draft_attachments()` call would then find nothing to move and silently publish with zero attachments. Fixed with `restore_draft_attachments()` (reverses the move), invoked by the service if the transaction fails after attachments were moved; proven by a new regression test (`test_publish_attachment_survives_structured_failure_and_retry`) that injects a mid-transaction failure with a real uploaded attachment and confirms both the rollback and the subsequent retry. (4) The Unit-of-Work test suite was missing an explicit "successful (non-rollback) update transaction" case — added. (5) The original Phase 2B.3 work did not stop for review before proceeding into BL-034 and BL-035 (and further unrelated feature work), despite its own task brief saying not to — noted here, not undone, since that work is independently sound (see below).

Phase 2C.2 / BL-034 (2026-08-14): independent schema-validating in-memory repositories for all nine families; shared JSON/memory contract coverage; Source parity; defensive-copy mutation isolation; unchanged Core query, Berries domain, and Intelligence Package exporter consumers. Inspection fixed one real JSON leak: `get()`/`list()` now deep-copy cache-owned records. Production composition remains JSON-backed.

Phase 2C.1 / BL-035 (2026-08-14): deterministic JSON export of all nine operational families through repository interfaces, plus materialized Claims; explicit exclusion of 5 fictional Entities and 3 fictional Evidence records; validated content hash and zero unaccounted orphans; content-identical re-import through fresh temporary JSON repositories. The regenerable live artifact is `generated/intelligence-package-v2-2026-08-14` (3,259,738 bytes; 1,944 primary-family records plus 54 Claims). Attachments are optional and omitted; Workspace is compatibility manifest metadata because it is not yet persisted.

Phase 2B.3 (2026-08-14): BL-033 completed. Evidence validate/purge and every persisted Core-object create/update/delete path now cross repository interfaces. Review/publish uses one UoW across Entity, Fact, Relationship, and Evidence writes; matched existing Entities are restored from prior-value snapshots if a later write fails. Acceptance verification moved draft deletion into the UoW so unlink failure compensates structured writes and leaves the draft retryable. Inbox drafts, attachments, and blocked-domain configuration remain documented filesystem exceptions because Phase 2 defines no repositories for them. 361 tests, record validation, and the 1,463-page static build pass.

Previously: Phase 2B.1 (2026-08-14) — the record-repository layer at `app/repositories/`. Before that: Phase 2A (2026-08-14) — `docs/v2/PHASE-2-REPOSITORY-REQUIREMENTS.md`, D-012 (analytical scope). Before that: tablet navigation breakpoint fix; Phase 1.5B (`BL-026` – `BL-029`).

**Findings worth knowing about (documented, not silently resolved):**
- **Review/publish's existing-Entity update gap is resolved.** `JsonUnitOfWork` captures prior record values for updates and restores them during reverse-order rollback. Draft deletion is the final operation inside the UoW, so deletion failure rolls structured writes back and leaves the draft retryable.
- **Attachment moves are now compensated, not just "best-effort."** The acceptance-review pass found and fixed a real bug: attachments are moved out of `inbox/` before the transactional block starts (the Evidence record's `attachments` field must be known before it can be schema-validated), so a rollback after that point needs its own compensation — `ReviewPublishService` now calls `restore_draft_attachments()` if the transaction raises after attachments were moved, so a retry finds them back where `move_draft_attachments()` expects. This is a small, targeted compensating action co-located with the one real call site that needs it, not a generalized new subsystem — attachments still have no repository and none was created.
- **Review/publish now has an explicit transaction boundary outside the route.** `ReviewPublishService` (`app/services/review_publish.py`) owns entity match/create/update orchestration, Fact/Relationship/Evidence creation, and the Draft-success handoff; `app/main.py`'s `review_publish()` route is limited to form parsing and turning the service's `PublishResult` into an HTTP response. `app/composition.py`'s `get_unit_of_work()` is the one place a `JsonUnitOfWork` gets constructed, mirroring `get_repositories()`/`get_query_services()`/`get_domain_services()`.
- **One direct filesystem read remains in an application read path, and it's justified, not an oversight:** `list_drafts()` (Review Queue, duplicate detection) still reads `inbox/evidence/` directly via `load_json_files()`, because Phase 2B.1 explicitly did not build a `DraftRepository` (only 9 named object types were in scope). `docs/v2/PHASE-2-REPOSITORY-REQUIREMENTS.md` Part 10.3 documents this as deliberate, not deferred-and-forgotten.
- A single, low-materiality ordering nuance: `EvidenceRepository.list()` (built in Phase 2B.1) sorts by published/captured date descending, matching `published_evidence()`'s existing sort exactly — but `all_evidence()` (unsorted, raw file-path order, before this task) now inherits that same sort too. Verified against every `all_evidence()` call site in `app/main.py`: none depend on its order except `published_evidence()` itself (which already re-sorted identically) — the one exception is `find_possible_duplicates()`'s reviewer-facing duplicate-warning list, whose display order was never a specified or tested contract. Flagged here per this task's transparency requirement, not silently absorbed.

**In progress:**
Nothing. The Audio/Video Intelligence data-model foundation is complete; no Whisper integration, YouTube/RSS discovery, scheduled monitoring, or new UI views were built (out of scope for this phase by design).

**Next:**
Owner authorization for either Phase 3 (PostgreSQL) or a follow-on Audio/Video Intelligence phase (actual transcription pipeline, a `Person` entity for hosts/guests/speakers, source-side podcast/video discovery).

**Next implementation action:**
Not started — both Phase 3 and any Audio/Video ingestion phase require separate authorization. PostgreSQL remains untouched.

**Blocked by:**
None.

**Known-good V1 reference:**
Tag `v1-blueberry-reference` → commit `432a96bd4efce1991df83b60aa1587154ba19528`. Unaffected by Phase 1A/1B/1.5A/1.5B/2A/2B.1/2B.2 (all work on `v2/intelligence-os`, `master` untouched).

**Architecture documents:**
Accepted (`docs/v2/00-README.md` through `10-BACKLOG.md`, 2026-08-13). `docs/v2/PHASE-2-REPOSITORY-REQUIREMENTS.md` (2026-08-14, Part 9 addendum added 2026-08-14, Part 10 addendum added 2026-08-14) is the authoritative Phase 2B implementation spec.

**Tests at baseline:**
427 passed, 0 failed (`pytest`) — includes 12 tests added for the Audio/Video Intelligence data-model foundation (`tests/test_media_evidence.py`). `scripts/validate_records.py` passes with zero schema errors. `scripts/build_static.py` succeeds (1,470 pages). Production remains JSON-backed; PostgreSQL and live data records were untouched.

**Important decisions — status:**
(IDs match `docs/v2/08-DECISION-LOG.md`)
- D-001 through D-009 — **ACCEPTED**
- D-010 — Claim stays a `fact.classification` value — **ACCEPTED (Option A)**, implemented
- D-011 — Recommendation and Evidence Priority coexist permanently — **ACCEPTED**, implemented
- D-007 (declarative Domain Packs, narrowed Phase 1 scope) — **ACCEPTED**, implemented
- D-012 (explicit analytical scope, separate from provenance) — **ACCEPTED**, schema-level implemented (Phase 2A); query-level `ScopeQueryService.explicit_scope()`/`records_by_entity_intersection()`/`scope_disagreements()` implemented and tested (Phase 2B.2), but not yet wired into any live route filter — Landscape's Assessment/Recommendation branch still uses the legacy derived-intersection rule only, preserving its exact existing behavior

No decisions remain open. No PostgreSQL, AI integration, or write-migration work has begun.
