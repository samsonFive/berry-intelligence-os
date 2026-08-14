# Project Status

*Maintained by Claude. Updated at the end of each work session that changes project state. Keep short — this is a status check, not a changelog (see `docs/reviews/CURRENT-STATE-AUDIT.md` and `docs/v2/` for detail).*

**Last updated:** 2026-08-14

---

**Current program:**
Intelligence OS V2

**Current stage:**
Phase 2B.1 complete — the record-repository foundation slice of Phase 2B (`BL-030`, `BL-030-source`, `BL-030-uow`, `BL-034a`). A real, tested JSON repository layer now exists at `app/repositories/`, implementing the contracts `docs/v2/PHASE-2-REPOSITORY-REQUIREMENTS.md` specified in Phase 2A — but it is **not yet wired into the running application**: `app/main.py` is untouched, no route reads or writes through it, and runtime behavior is unchanged. This slice proves the seam works before anything is moved onto it, per its own explicit mandate.

**Current branch:**
`v2/intelligence-os`

**Next phase:**
Phase 2B.2 — Core query services and read-path migration (`docs/v2/10-BACKLOG.md` BL-030a, BL-030b, BL-032, BL-034, BL-035) — not started, pending owner authorization.

**Last completed:**
Phase 2B.1 (2026-08-14): a record-repository layer at `app/repositories/` — `base.py` (backend-agnostic `RecordRepository` contract shape plus `RecordNotFound`/`DuplicateRecord`/`InvalidRecord`/`StorageError`/`ReferentialIntegrityError`/`TransactionError`), `json/base.py` (shared JSON mechanics: deterministic mtime-signature caching, schema validation before write, duplicate-id rejection, safe record-id path handling), and nine concrete repositories (`entities`, `evidence`, `facts`, `relationships`, `signals`, `assessments`, `recommendations`, `strategic_questions`, `sources`). `JsonSourceRepository` fully hides Source's whole-collection-rewrite storage behind the identical logical `get`/`list`/`create`/`update`/`delete` shape every other repository presents — proven by 13 dedicated tests using only temporary fixture data, never the live 120-source registry. `unit_of_work.py` defines the transaction-boundary seam Phase 2A identified as necessary (review/publish's multi-object write) without migrating that workflow: `JsonUnitOfWork` performs best-effort, reverse-order compensation (delete what this same unit of work created) on failure, documented explicitly as *not* a real database transaction. 128 new tests (`tests/repositories/`) — a 109-test shared contract suite parametrized across all 8 one-file-per-record repositories, 13 Source-specific tests, 6 Unit-of-Work tests — all passing, written to be reusable unchanged against a future second backend. Implementation surfaced 4 documented refinements (Entity's nested-folder read/write split, duplicate-check cost at current scale, Strategic Questions' zero real write usage, Source's schema-less nature) recorded in `docs/v2/PHASE-2-REPOSITORY-REQUIREMENTS.md` Part 9 — none of them changed the Phase 2A architecture.

Previously: Phase 2A (2026-08-14) — `docs/v2/PHASE-2-REPOSITORY-REQUIREMENTS.md`, D-012 (analytical scope). Before that: tablet navigation breakpoint fix; Phase 1.5B (`BL-026` – `BL-029`).

**Findings worth knowing about (documented, not silently resolved):**
- **No application route has been migrated.** `app/main.py`, every template, and every static asset are byte-identical to before this task (`git diff --stat` empty for all three). The repository layer exists and is fully tested in isolation; nothing in the running application calls it yet. This is by design, not an oversight — Phase 2B.1's whole mandate was proving the seam before moving anything onto it.
- The Unit-of-Work seam is genuinely weaker than a database transaction, and says so in its own docstring rather than implying otherwise: no staging/atomic-replace, no write-ahead log, and `update()`/`delete()` calls made through it are not compensated on rollback (only `create()` is, since review/publish — the one real multi-object pattern — is create-only). This is a deliberate "least complex implementation that preserves existing behavior without a false guarantee," not a shortcut taken under time pressure.
- `DuplicateRecord` rejection on `create()` is genuinely new behavior, not a preserved one — today's `save_X()` functions in `app/main.py` silently overwrite a same-id file with no detection at all. The repository layer closes this gap for the first time; nothing in the live application benefits from it yet since nothing calls the repository layer.
- Every repository's class docstring states plainly which operations the live application actually exercises today (e.g. Strategic Questions: get/list only, confirmed by re-reading every route — no create/update/delete route exists at all) versus which are uniform, currently-unused base-class mechanics (kept because they're free to implement once, shared, and a future PostgreSQL backend supports them trivially regardless) — an explicit, honest mapping rather than silently implementing a full CRUD surface everywhere and leaving it unstated which parts are real.

**In progress:**
Nothing. Phase 2B.1 is complete and fully verified.

**Next:**
Owner authorization to begin Phase 2B.2 (query services and read-path migration), scoped by `docs/v2/PHASE-2-REPOSITORY-REQUIREMENTS.md` Part 3.3 and `docs/v2/10-BACKLOG.md`.

**Next implementation action:**
Not started — pending owner authorization. Phase 2B.2: implement query services (`app/queries/`) and Berries domain services (`app/services/berries/`) on top of the now-complete record-repository layer, then begin migrating read-path routes (starting with evidence/entity) onto the new layers.

**Blocked by:**
None.

**Known-good V1 reference:**
Tag `v1-blueberry-reference` → commit `432a96bd4efce1991df83b60aa1587154ba19528`. Unaffected by Phase 1A/1B/1.5A/1.5B/2A/2B.1 (all work on `v2/intelligence-os`, `master` untouched).

**Architecture documents:**
Accepted (`docs/v2/00-README.md` through `10-BACKLOG.md`, 2026-08-13). `docs/v2/PHASE-2-REPOSITORY-REQUIREMENTS.md` (2026-08-14, Part 9 addendum added 2026-08-14) is the authoritative Phase 2B implementation spec.

**Tests at baseline:**
333 passed, 0 failed (`pytest -q`) — 205 as of Phase 2A + 128 new repository tests (`tests/repositories/`: 109 contract-suite + 13 Source-specific + 6 Unit-of-Work). `scripts/validate_records.py` passes with zero schema errors (no schema files touched this phase). `scripts/build_static.py` succeeds (1,463 pages, unchanged). No route, template, or `app/main.py` code changed; no PostgreSQL work; no AI integration; no Collector execution code; the live 120-source registry and the full 1,882-record live dataset were never written to by any test (all repository tests use `tmp_path`). Runtime application behavior is unchanged.

**Important decisions — status:**
(IDs match `docs/v2/08-DECISION-LOG.md`)
- D-001 through D-009 — **ACCEPTED**
- D-010 — Claim stays a `fact.classification` value — **ACCEPTED (Option A)**, implemented
- D-011 — Recommendation and Evidence Priority coexist permanently — **ACCEPTED**, implemented
- D-007 (declarative Domain Packs, narrowed Phase 1 scope) — **ACCEPTED**, implemented
- D-012 (explicit analytical scope, separate from provenance) — **ACCEPTED**, schema-level implemented (Phase 2A); repository-level `scope_disagreements()`/scope-aware `list()` filters remain Phase 2B.2 work, not built in Phase 2B.1 (the record-repository layer's generic `list(**filters)` supports simple field equality only, sufficient for today's one real filter need — Evidence `status` — but not yet scope-aware)

No decisions remain open. No PostgreSQL, AI integration, or route-migration work has begun.
