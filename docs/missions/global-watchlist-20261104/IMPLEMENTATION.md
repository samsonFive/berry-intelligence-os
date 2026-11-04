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


## Four seeded custom Watchlist landscapes

The original Global Watchlist release is live at https://intel.johnnyaceii.com/global-watchlist (canonical `ae22ea07`, tested `ce2b3bc1`). Its HTTPS browser verification covered 244 organizations, the shared sheet/Reader, alphabet navigation, a ten-page Planasa PDF and mobile overflow, with zero JavaScript errors. The release preserved 4,551 substantive data files, saved private state and the account/workspace databases. The deployment manifest changes deliberately with the revision; it is not an intelligence record. Release metadata and rollback remain recorded on the host.

The requested follow-up adds Global Blueberry Landscape, Global Blackberry Landscape, Global Strawberry Landscape and Global Raspberry Landscape as starter saved scopes. Each selects one berry and leaves geography unrestricted. They recompute against current captured records, not frozen organization lists. Scoped PDFs name the selected saved landscape. Monitoring groups, follows, canonical intelligence and tier review states are unchanged.

The existing private `landscape_views.json` store holds the selections and history. A backward-compatible `surface: watchlist` marker routes these views to Global Watchlist; their existing overview kind remains readable by prior app images. Normal authoring startup seeds only absent defaults. Repeated startup preserves edits, custom names, archives and existing views. Users can save, update, copy, archive and restore scopes with revision checks and existing same-origin protection. Existing Workspaces links resolve these same current scopes.

Validation: 77 related Watchlist, Landscape, Workspaces and Reader-return checks pass. Browser verification exercised all four global scopes and their PDF buttons, custom-copy persistence, archive/restore and phone layout with zero JavaScript errors. Screenshots and `default-landscapes-visual-results.json` use the committed local snapshot (166 organizations); the live corpus is larger. Fresh exact-head hosted CI and coordinated release checks remain required for the seeded-landscapes follow-up; it is not yet deployed.
