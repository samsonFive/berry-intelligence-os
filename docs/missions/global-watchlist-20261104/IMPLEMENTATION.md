# Global Watchlist implementation

## Reuse / extend / consolidate map

- Canonical corpus: `app/main.py` repository loaders and `schemas/entity.schema.json`, `relationship.schema.json`, `evidence.schema.json`. Preserve IDs and evidence URLs; no new entity or variety schema.
- Tiers: `app/services/competitor_registry.py`, `data/imports/competitor-registry-2026-09-15/{snapshot,reconciliation-matrix}.json`. Original spreadsheet screenshot transcription, explicitly unreviewed. Preserve per-berry assignments, regions, source date, and transcription caveat. Do not imply independent verification.
- Profiles and portfolios: `app/templates/_company_profile.html`, `app/services/company_workspace.py`, `competitor_profile.py`. Link from the unified experience to canonical deep profiles; retain roles, rights versus adoption, and empty states.
- Assessments and research: `app/competitive_routes.py`, `app/services/competitive_evaluation.py`, `data/imports/competitive-landscape-2026-10-30-v1/capability-rubrics.json`. Reuse scoped, versioned automatic/reviewed assessments. No new score or threat methodology.
- Persistence and permissions: `app/services/living_workspaces.py` SQLite objects/history transactions; `app/personal_digest_routes.py::require_edit`, remote session middleware. Groups and notes are explicitly shared within the protected workspace, with actor attribution; no individual privacy claim.
- Following: existing `app/services/watchlist.py` store; maintain compatibility with My Watches.
- Consolidate `/competitors` into `/global-watchlist`, preserving query state and company selection. Existing `/landscapes` remains a supporting executive synthesis link. The new sidebar entry is Global Watchlist.
- News: published records only, canonical IDs only, explicit syndication/URL grouping retaining each source. No live-connection claim or source-count confidence boost.
- Same-development grouping reuses `app/services/story_threads.py`; it never creates entity associations. Explicit syndication remains distinct from independent corroboration.
- Corrections: `app/services/association_corrections.py` applies versioned workspace overlays to the shared private `RequestCorpus`. `entity_alias_recall.py` and `company_source_scope.py` respect exclusions rather than recalling a rejected association through text. Source readers expose the correction audit. Public/CLI corpus construction defaults to no private overlay; original canonical records and claim trust remain unchanged.
- PDF: ReportLab already pinned in runtime/web requirements. Reuse report typography and footer conventions; export the same filtered projection, with captured/publication dates, provenance and limitations.

## Storage migration

The existing SQLite `objects` and `history` tables support additive kinds. New kinds use the `global_watchlist_` namespace, with a `schema_version` field; no destructive migration is necessary. Groups are workspace scoped, independently versioned, and use optimistic concurrency. Deletes are tombstones. Filters never write membership. Notes and corrections are private workspace data and are never registered with the static builder.
