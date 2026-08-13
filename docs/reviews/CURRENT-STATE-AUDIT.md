# Berry Intelligence OS — Current-State Audit

**Audit date:** 2026-08-13
**Auditor:** Claude (Sonnet 5), read-only inspection — no code, data, or docs were modified as part of this audit.
**Scope:** Everything in the working tree at commit `b7013a1`, branch `master`.

This is a factual, current-state report. It does not propose a roadmap or make recommendations beyond what Sections 16 asks for explicitly. Every claim below is grounded in a command run, a file read, or a page rendered during this audit — not in prior planning documents.

---

## 1. Repository identity

| | |
|---|---|
| Repository name | `berry-intelligence-os` |
| Current branch | `master` |
| Current commit | `b7013a160e7510bc2c1dbd3aa6fd0a0effd88257` — "Unify the review queue: one in-app place for everything awaiting review" (2026-08-13) |
| Git status | Clean except two pre-existing, unrelated untracked files: `.claude/scheduled_tasks.lock` and `blueberry-public-pilot-2026-08-03.zip` (a zip of the import package discussed in Section 6; not tracked, not referenced by any code) |
| Uncommitted changes | None in tracked files |
| Total commits in history | 32, spanning 2026-08-04 to 2026-08-13 (9 days) |
| Primary runtime/framework | Python 3 + FastAPI 0.116.1, server-rendered with Jinja2 3.1.6, uvicorn 0.35.0 as the ASGI server |
| Python version requirement | **Not pinned anywhere in the repo** — no `runtime.txt`, no `.python-version`, no `requires-python` in `pyproject.toml`. CI (`deploy-pages.yml`) uses `python-version: "3.12"`. The local dev venv used for this audit runs 3.13.7. Nothing has been observed to break across that range, but the requirement is implicit, not declared. |
| Major dependencies | `fastapi`, `uvicorn[standard]`, `jinja2`, `pydantic`, `jsonschema`, `python-multipart`, `feedparser` (RSS parsing), `httpx` (HTTP client for source polling), `openpyxl` (Excel review export/import), `playwright` (headless-browser summary resolution script). Dev-only: `pytest` (in `requirements-dev.txt`, not `requirements.txt`). |
| Deployment approach (as documented) | Static site generation (`scripts/build_static.py`) → GitHub Pages, via `.github/workflows/deploy-pages.yml` on every push to `master`. No server-hosted deployment is documented or configured. |
| Does the app run successfully? | **Yes**, verified directly in this audit: `uvicorn app.main:app` starts cleanly, the newsfeed, entity pages, search, sources, and review queue all render and are interactive. `pytest -q` passes 122/122. `scripts/validate_records.py` passes with zero schema errors across all 1,882 live JSON records. The static build (`scripts/build_static.py`) completes and produces 1,452 pages with a working Pagefind search index. |

---

## 2. Current architecture

**As actually implemented**, not as originally planned:

- **Application framework**: a single FastAPI app (`app/main.py`, 2,512 lines — all routes, business logic, and data-access functions in one file; no `app/routers/`, `app/models/`, or `app/services/` split exists).
- **Routing structure**: 31 routes total (23 `GET`, 8 `POST`), all defined with `@app.get`/`@app.post` decorators directly on the module-level `app` object. See the full route list in Section 4.
- **Data storage model**: flat-file JSON. No database of any kind (no SQLite, no Postgres, no ORM). Every record is one `.json` file, one file per record, in a folder named after its type under `data/`. `load_json_files()` reads every file in a directory into a list on each call, with a stat-based cache (mtime+size fingerprint per folder) added this session so repeated reads within a request cycle don't re-parse unchanged folders from disk.
- **JSON/file structure**: `data/entities/{type}/entity-id.json`, `data/evidence/ev-id.json` (flat, ~1,263 files in one directory), `data/facts/fact-id.json`, `data/relationships/rel-id.json`, `data/strategic-questions/sq-id.json`, `data/signals/` (empty), `data/configuration/sources.json` (one file, a JSON array of all monitored sources) and `blocked_domains.json`.
- **Indexes or derived data**: none at the application layer — every list/filter/sort operation scans the relevant folder fresh (cache aside) on every request. The only real index is the static build's Pagefind search index (`generated/pagefind/`), which only exists for the static deployment, not the live app (the live app's search is a linear substring/typo-tolerant scan implemented in Python — see below).
- **Templates/frontend approach**: server-rendered Jinja2 templates (`app/templates/*.html`, 18 files), no client-side framework, no build step, no JS bundler. The only JavaScript is two small hand-written files: `app.static/search-core.js` (shared search-ranking logic, ES module) and inline `<script type="module">` blocks in `base.html`/`search.html` for the search UI.
- **Static assets**: one CSS file (`app/static/app.css`, hand-written, no preprocessor/framework) and the one JS module above. No image assets, no icon font, no external CDN dependency in the live app (the static build's search UI does load Pagefind's own JS/CSS from the same-origin `generated/pagefind/` folder it wrote).
- **Search implementation**: two entirely separate implementations that must be kept in sync by hand:
  1. **Live app** (`/api/search`, and the plain query-param search on the newsfeed): a Python function scanning `all_evidence()`/`all_entities()` in memory with substring and typo-tolerant matching.
  2. **Static build**: [Pagefind](https://pagefind.app), a client-side WASM search engine that indexes the generated HTML at build time. Two UI surfaces (header dropdown, full `/search/` page) both call a shared `mergedSearch()` function that runs three Pagefind queries (entity-filtered, evidence-filtered+date-sorted, unfiltered fallback) and merges them — this ranking logic exists only in the static-build JS, has no equivalent in the live dev-mode app, and cannot be unit-tested by `pytest` (there is no JS test runner in this repo).
- **Import pipeline**: two unrelated pipelines that both write into `data/`:
  1. **Human intake** (`/intake` → `inbox/` draft → `/review/{id}` → `/review/{id}/publish`), for one record at a time, with a full structuring UI (entities, facts, relationships, priority).
  2. **Automated source polling** (`scripts/build_static.py`-adjacent `check_source()` in `app/main.py`, gated behind `ENABLE_SOURCE_POLLING` env var, off by default), which writes evidence directly into `data/evidence/` as `status: published`, `auto_captured: true`, `validated: false`, bypassing the intake/review-and-structure workflow entirely — validation for these is a binary Validate/Purge decision, not the fact/relationship extraction the intake pipeline offers.
  There is a third, one-off pathway used exactly once in this repo's history: `data/imports/blueberry-public-pilot-2026-08-03/scripts/import_package.py`, a standalone script (not wired into the live app or CI) with its own `--dry-run`/`--apply`/`--approve` gates. See Section 6.
- **Validation pipeline**: `scripts/validate_records.py`, a standalone script (also run in CI) that loads every JSON Schema in `schemas/` and validates every file in the corresponding `data/` folder with `jsonschema`'s `Draft202012Validator`. It is schema-conformance only — it does not check referential integrity (e.g., that a `fact.evidence_ids` entry actually points to an existing evidence file) and does not check business rules beyond what JSON Schema itself expresses.
- **Test structure**: 4 files under `tests/`, 1,879 lines total, 122 tests, using FastAPI's `TestClient` and `pytest`'s `monkeypatch`/`tmp_path` fixtures to isolate each test's data directory. No separate unit-test layer for pure functions vs. integration tests for routes — most tests exercise routes end-to-end through the HTTP client.
- **Database usage**: none.
- **External APIs / SaaS dependencies**: Google News RSS/search (polled for `news_search`-type sources and by the one-off `resolve_real_summaries.py` script, via a headless Chromium browser through Playwright — not an API, screen-scraping a public page), arbitrary publisher RSS feeds (for `rss`-type sources), and GitHub Pages (deployment target only, not a runtime dependency). No paid SaaS, no API keys required to run the app.

### Architecture diagram (text)

```
                     ┌─────────────────────────┐
                     │   data/  (flat JSON)     │
                     │  entities/ evidence/     │
                     │  facts/ relationships/   │
                     │  strategic-questions/    │
                     │  signals/ (empty)        │
                     │  configuration/          │
                     └───────────▲──────────────┘
                                 │ read/write (no DB, no cache layer
                                 │ beyond an in-process mtime cache)
        ┌────────────────────────┴─────────────────────────┐
        │                  app/main.py                       │
        │   FastAPI app — 31 routes, all business logic       │
        │   (intake, review, publish, source polling,         │
        │    priority queues, search, entity/evidence pages)  │
        └───────┬───────────────────────────────┬────────────┘
                │ renders                         │ polls (opt-in)
        ┌───────▼────────┐                ┌──────▼─────────────┐
        │ app/templates/  │                │ Google News RSS /   │
        │ 18 Jinja2 .html │                │ publisher RSS feeds │
        │ + app.css + one │                │ (source registry in │
        │ JS module       │                │  data/configuration)│
        └────────┬────────┘                └──────────────────────┘
                 │ served live via uvicorn
                 │
        ┌────────▼─────────────────────────────────┐
        │        Local browser (dev/authoring)       │
        └─────────────────────────────────────────────┘

  ── separately, on push to master ──

        ┌─────────────────────────┐
        │  scripts/build_static.py │  reads data/ only (never inbox/)
        └────────────┬─────────────┘
                      │ renders same Jinja2 templates, statically
        ┌─────────────▼─────────────┐
        │   generated/  (1,452 pages)│
        │   + Pagefind search index  │
        └────────────┬────────────────┘
                      │ actions/upload-pages-artifact
        ┌─────────────▼─────────────┐
        │      GitHub Pages          │  ← read-only public deployment
        └─────────────────────────────┘
```

---

## 3. Repository tree

```
app/
├── main.py                 2,512 lines — every route, every data-access function
├── static/
│   ├── app.css              hand-written CSS, no framework
│   └── search-core.js       shared search-ranking module (used by static build only)
└── templates/                18 Jinja2 templates, listed in Section 4

data/                         the trusted, authoritative dataset — this IS the database
├── configuration/            sources.json (120 monitored sources), blocked_domains.json
├── entities/                 162 files across 9 type-subfolders (see Section 6)
├── evidence/                 1,263 flat .json files, no subfolders
├── facts/                    186 flat .json files
├── relationships/            204 flat .json files
├── strategic-questions/      9 flat .json files
├── signals/                  0 files — empty directory
└── imports/
    └── blueberry-public-pilot-2026-08-03/   the import package, see Section 6
        ├── entities/ evidence/ facts/ relationships/ signals/ strategic-questions/
        ├── scripts/           import_package.py, validate_package.py, build_reports.py
        └── *.md, manifest.json, source-coverage.csv   extensive self-documentation

schemas/                       6 JSON Schema files, one per record type (no signal-import
                                schema mismatch — signal.schema.json exists and validates
                                cleanly against an empty folder)

scripts/                       6 operational scripts, all standalone (invoked manually or
                                from CI), none imported by app/main.py at runtime
├── validate_records.py        schema conformance, run in CI
├── build_static.py            static site generator, run in CI
├── export_for_review.py       bulk review -> .xlsx (openpyxl)
├── apply_review_decisions.py  .xlsx -> validate/purge decisions applied back
└── resolve_real_summaries.py  Playwright-based real-article-summary backfill

tests/                         4 files, 122 tests, 1,879 lines
├── test_app.py                the bulk of coverage — routes, templates, business logic
├── test_build_static.py       static-build-specific behavior
├── test_resolve_real_summaries.py
└── test_review_scripts.py     export/apply-decisions round-trip

docs/                          13 files across 8 numbered folders + decisions/ + reviews/
                                (product vision, PRD, design system, domain model,
                                architecture notes, build guide, ADRs) — see Section 13
                                for how accurately these track the current code

generated/                     build output of scripts/build_static.py — gitignored,
                                fully disposable, not part of the repository's real state

inbox/                         intake drafts before publish — currently empty (0 drafts)

review/                        working files for the Excel bulk-review tool — a
                                completed .xlsx from an earlier review pass, plus its
                                Excel lock file; gitignored except the one tracked
                                spreadsheet
```

---

## 4. Implemented product features

For each feature: route/entry point, status, and the most important limitation observed directly.

| Feature | Route(s) | Status | Key limitation |
|---|---|---|---|
| Homepage / Newsfeed | `GET /` | **Complete** | Filters (search, berry, source, priority, competitor, geography, region) all functional; disabled entirely in the static build ("Filtering and search require the local app") |
| Evidence index/detail | `GET /evidence/{id}`, feed cards | **Complete** | Renders facts, relationships, linked entities, attachments, provenance; disputed status renders as plain text with no visual emphasis (Section 7) |
| Companies (Competitors) | `GET /entities/company`, `/entities/company/{id}` | **Complete**, has sidebar nav | — |
| Varieties | `GET /entities/variety`, `/entities/variety/{id}` | **Complete**, has sidebar nav | — |
| Patents | `GET /entities/patent/{id}` | **Functional but rough** | Works identically to any other entity type via the generic template, but **no sidebar nav link exists** — only reachable via search or an inbound link from another page |
| Breeding programs | `GET /entities/breeding_program/{id}` | **Functional but rough** | Same as patents — no nav entry point |
| Brands | `GET /entities/brand/{id}` | **Functional but rough** | Same — no nav entry point |
| Geographies | `GET /entities/geography/{id}` | **Functional but rough** | Same — no nav entry point, despite geography being a first-class filter dimension elsewhere in the app |
| Traits | `GET /entities/trait/{id}` | **Functional but rough** | Same — no nav entry point; trait-to-variety linkage is not a structured relationship (Section 5) |
| Strategic questions | `GET /strategic-questions`, `/strategic-questions/{id}` | **Complete**, has sidebar nav | Shows linked evidence per question; no visible answer/synthesis field beyond the question's own description |
| Signals | `GET /signals`, `/signals/new`, `POST /signals`, `/signals/{id}` | **Complete UI, empty in practice** | Full create/list/detail flow exists and works; `data/signals/` has 0 records, and 6 proposed signals from the import package were never applied (Section 6) |
| Search (live app) | `/api/search`, newsfeed `?q=` | **Functional but rough** | Substring/typo-tolerant, no ranking sophistication; entirely separate implementation from the static build's search (Section 2) |
| Search (static build) | `/search/` + header dropdown | **Complete**, actively tuned this session | Two rounds of ranking work this session (alias/heading weight fix, then entity-first/date-sorted structural filtering); both search surfaces now share logic and rank identically |
| Filters | newsfeed, entity lists, sources, priority queues | **Complete** | Query-param based, server-rendered, no saved-filter/view concept |
| Review queue | `GET /review`, `POST /evidence/{id}/validate`, `/purge` | **Complete**, unified this session | As of this session's last change, shows both intake drafts and unvalidated auto-captured evidence in one page with inline actions. **`/work-queue`'s own "Awaiting review" card was not updated to match** — it still only counts intake drafts, so the two overview pages now disagree with each other on backlog size (verified directly: `work_queue()` in `app/main.py` still calls only `list_drafts()`) |
| Intake | `GET/POST /intake` | **Complete** | All 4 pathways implemented (article/URL, note/observation, upload report, standalone fact); currently 0 drafts in `inbox/` to exercise against |
| Manual article/note submission | part of `/intake` | **Complete** | — |
| File import (upload) | part of `/intake`, `uploaded_report` type | **Functional but rough** | Attachment upload works and stores under `data/attachments/{evidence_id}/`; no file-type/size validation observed beyond FastAPI's `UploadFile` defaults |
| Approval/publishing workflow | `/review/{id}/publish` | **Complete** for intake drafts | Entirely separate mechanism from auto-captured evidence's validate/purge (Section 5's fact/claim distinction section) |
| Reading / Testing / Commercial-position / Monitoring priority | `/queues/{dimension}` | **Functional but rough** | Fully implemented as an evidence-level filter+sort view. **Verified directly: 100% of the 1,139 auto-captured evidence records have priority level "none" on all four dimensions; only the 124 manually-curated/imported records carry any priority assessment at all.** The queues do not scale with the growing auto-capture pipeline. |
| Source registry | `/sources`, full CRUD + check-now/mark-checked/toggle/delete | **Complete** | Polling itself is off by default (`ENABLE_SOURCE_POLLING`); 120 sources registered, only 1 is a live-polled RSS feed, 33 are keyword/Google-News-search sources, 86 are manual reference sources never polled |
| Workspaces | — | **Not implemented** | No concept of a workspace, project, or saved view exists anywhere in the code |
| Timelines | entity "Recent activity" section | **Functional** | A genuine merged chronological feed of evidence + facts + relationships per entity (`entity_activity()`), but only items with a real date qualify — roughly half of imported reference-type evidence has no `published_date` and is excluded from this view, remaining visible only in the separate Facts/Linked Evidence lists below it |
| Maps | — | **Not implemented** | No mapping/geospatial library, no SVG map, confirmed via search across `app/` |
| Exports | `scripts/export_for_review.py` | **Functional but rough, admin-only** | Produces an `.xlsx` of the unvalidated backlog for offline bulk review; not a general-purpose data export for end users, and not reachable via any UI route — command-line only |
| User/auth features | — | **Not implemented** | No login, no session, no per-user identity, no permissions model. `AUTHORING_MODE` is a single global on/off switch via the `BIOS_MODE` env var, not authentication |

---

## 5. Current domain model

Six schemas exist in `schemas/`, all JSON Schema Draft 2020-12, all enforced by `scripts/validate_records.py`.

### `entity` (`entity.schema.json`)
- **Required**: `id`, `record_type`, `entity_type`, `name`, `status`
- **Key optional**: `aliases`, `description`, `roles`, `berry_ids`, `evidence_ids`, `fact_ids`, `relationship_ids`, `attributes` (a free-form key/value bag — the only fully unstructured field in the model)
- **Statuses**: `active`, `inactive`, `historical`, `unverified`
- **Back-references**: `evidence_ids`/`fact_ids`/`relationship_ids` are stored on the entity itself and populated at write time — there is no query-time join; a broken back-reference would silently show as missing content, not an error, since nothing currently checks referential integrity
- **Displayed**: full detail page (`entity.html`) with Status/Roles/Berries/Regions, aliases (search-weighted), Description, Attributes, a merged "Recent activity" timeline (evidence+facts+relationships), a "Trust summary" (evidence count / independent source count / last-updated date), a Facts list, and a Linked Evidence list
- **Known limitation**: 9 entity types exist in the data (`berry`, `brand`, `breeding_program`, `company`, `geography`, `patent`, `retailer`, `trait`, `variety`); only 2 (`company`, `variety`) have a sidebar navigation entry point

### `evidence` (`evidence.schema.json`)
- **Required**: `id`, `record_type`, `status`, `source_type`, `title`, `captured_date`, `summary`, `submitted_by`, `priority`
- **Key optional**: `source_url`, `published_date`, `why_it_matters`, `entity_ids`, `tags`, `auto_captured`, `validated`, `source_id`, `origin_domain`, `auto_tagged`
- **Statuses**: schema allows more, but **100% of the 1,263 live records currently have `status: "published"`** — `draft`/`in_review` exist in the workflow conceptually (the import package's own tooling uses them as an intermediate state) but no record is currently sitting in either state
- **Relationships/back-references**: `entity_ids`, `fact_ids`, `relationship_ids`, `strategic_question_ids` — all populated at write time, same no-integrity-check caveat as entities
- **Displayed**: full detail page with Source/Published/Captured/Status/Berries/Geography metadata, Summary, Why it matters, Priority (all 4 dimensions with rationale), Linked entities, Facts, Relationships, Attachments, Provenance (source URL link)
- **Known limitation**: the `validated` boolean is a completely separate approval concept from `status`, and only applies to `auto_captured` records — a record with `auto_captured: false` (e.g., every manually-authored or imported record) can have `validated` absent/`None` forever without that meaning anything is wrong with it. This is a real source of confusion: the same word ("unvalidated"/review count) means two different things depending on how a record entered the system.

### `fact` (`fact.schema.json`)
- **Required**: `id`, `record_type`, `statement`, `classification`, `confidence`, `status`, `reviewer`, `created_at`, `evidence_ids`
- **Key optional**: `event_date` (added this session, backfilled where extractable — the real-world date a development happened, vs. `created_at`, when the fact was authored in this system), `entity_ids`, `supersedes`
- **`classification` enum**: `["fact", "claim"]` — **this is the FACT vs. CLAIM distinction**, and it is real and enforced by schema, not just a naming convention. Verified counts in live data: 132 `fact`, 54 `claim`.
- **`confidence` enum**: `["low", "medium", "high"]` — a separate axis from classification. Verified counts: 106 high, 63 medium, 17 low.
- **`status` enum**: `["active", "disputed", "superseded", "withdrawn"]` — **this is where "disputed" lives**. Verified: 176 active, 10 disputed, 0 superseded, 0 withdrawn in live data.
- **Displayed**: classification and confidence render as badges (`FACT`/`CLAIM`, `HIGH CONFIDENCE`/etc.) on both entity and evidence pages; `status` renders too, but only as plain trailing text ("Reviewed by X on Y · disputed") with **no distinct color, icon, or badge** — a disputed fact is typographically identical to an active one except for that one word.

### `relationship` (`relationship.schema.json`)
- **Required**: `id`, `record_type`, `subject_id`, `predicate`, `object_id`, `status`, `evidence_ids`
- **Key optional**: `effective_date`, `notes`
- **`predicate` enum**: `owns`, `develops`, `licenses`, `distributes`, `grows`, `trials`, `sells`, `carries`, `partners_with`, `operates_in`. Verified live distribution: `develops` 57, `operates_in` 51, `owns` 48, `sells` 12, `licenses` 11, `partners_with` 10, `trials` 7, `carries` 7, `grows` 1.
- **`status` enum**: `active`, `historical`, `disputed`. Verified: 201 active, 2 disputed, 1 historical.
- **No `confidence` field exists on this schema at all.** Where confidence is expressed for a relationship (observed directly in live data, e.g. Agrovision's "partners_with Fall Creek Farm & Nursery"), it is written as free text inside `notes` (literally the string `"confidence=low; ..."`), not a structured, queryable field.
- **Displayed**: relationships appear on the *evidence* detail page's "Relationships" section, and are folded into each *entity's* merged "Recent activity" timeline (via `entity_activity()`) — there is no dedicated, standalone "Relationships" section on an entity page.
- **Known limitation**: no `has_trait`-style predicate exists, so a variety's trait provenance (e.g., "chilling requirement: 300 hours, per USPP024636") is not a structured, queryable relationship — only discoverable by reading fact statement text or the trait entity's own `evidence_ids`/`fact_ids` list (which shows *what evidence mentions this trait generally*, not *which specific variety it was measured on*).

### `strategic-question` (`strategic-question.schema.json`)
- **Required**: `id`, `record_type`, `title`, `status`
- **Key optional**: `description`, `berry_ids`, `evidence_ids`
- **Displayed**: list + detail page showing linked evidence, grouped by source type. No separate "answer" or "synthesis" field — the question's `description` and its linked evidence are the entirety of what's shown.

### `signal` (`signal.schema.json`)
- **Required**: `id`, `record_type`, `title`, `direction`, `strength`, `confidence`, `status`, `evidence_ids`, `first_seen`, `last_updated`, `reviewer`
- **Key optional**: `description`, `fact_ids`, `entity_ids`, `strategic_question_ids`
- A distinct record type, not a `classification` value on facts — signals are their own thing with their own `direction`/`strength`/`confidence` axes.
- **Currently 0 live signal records exist.** The route, form, and detail template are fully built and functional (verified: creating a signal via `POST /signals` works), but nothing has ever been published through it, and the 6 signals proposed in the blueberry import package were never applied (Section 6).

### FACT / CLAIM / ASSESSMENT / SIGNAL / RECOMMENDATION — does the code distinguish these?

| Concept | Distinguished how | Evidence |
|---|---|---|
| FACT | `fact.classification == "fact"` | Schema-enforced enum, 132 live records |
| CLAIM | `fact.classification == "claim"` | Schema-enforced enum, 54 live records |
| ASSESSMENT | **Not a distinct concept anywhere in the schema or code.** The closest equivalents are a fact's `confidence` level or an evidence item's `priority` rationale, but neither is labeled or modeled as an "assessment" | — |
| SIGNAL | Separate record type (`schemas/signal.schema.json`), own route, own template | Fully built, currently empty (0 live records) |
| RECOMMENDATION | **Not implemented anywhere.** No schema, no route, no field. `priority-actions.md` inside the (unapplied) import package proposes 16 recommended actions, but this exists only as a markdown document in `data/imports/`, never as structured, queryable data in the live model | — |

---

## 6. Blueberry dataset state

### Live counts (verified directly, this audit)

| | Count |
|---|---|
| Entities total | 162 |
| — companies | 34 |
| — varieties | 42 |
| — patents | 38 |
| — breeding programs | 9 |
| — brands | 8 |
| — geographies | 18 |
| — traits | 10 |
| — retailers | 2 |
| — berries | 1 |
| Evidence total | 1,263 |
| — published | 1,263 (100%) |
| — validated | 1,139 |
| — unvalidated | 124 (all pre-date the `validated` field — see below) |
| — auto-captured | 1,139 |
| Facts | 186 (132 fact / 54 claim) |
| Relationships | 204 |
| Strategic questions | 9 |
| Signals | **0** |
| Disputed facts | 10 |
| Unverified entities | 16 |

There is no "in-review evidence" currently — the schema and the import tooling both support that state, but zero records are sitting in it right now (all 1,263 are `published`).

### Is `blueberry-public-pilot-2026-08-03` staged, applied, approved, or partially imported?

**Verified by diffing every file in `data/imports/blueberry-public-pilot-2026-08-03/` against the live `data/` tree, filename-by-filename, and confirming content matches:**

| Record type | In import package | Applied to live `data/` | Result |
|---|---|---|---|
| Entities | 155 | 155 / 155 (100%) | **Fully applied.** Live `data/entities` has 7 additional records not from this import — pre-existing placeholder/demo entities from the original Milestone 0 seed data (`company-example-genetics`, `variety-example-blue`, etc.) |
| Evidence | 121 | 121 / 121 (100%) | **Fully applied**, but with a status discrepancy: the package's own `manifest.json` declares `"evidence_status_on_import": "in_review"`; every one of these 121 records is currently `status: "published"` in live data. The import tool's own `--approve` step (which flips `in_review` → `published`) was run — confirmed by git history (`git log`: `import_package.py` implied by commits `cde1fbb` stage → `8d4d88e` import → `2e5d9ed` UI review → `1772d38` publish). |
| Facts | 186 | 186 / 186 (100%) | **Fully applied**, byte-identical except for the `event_date` field added by later feature work this session (confirmed via direct diff of one sample file) |
| Relationships | 204 | 204 / 204 (100%) | **Fully applied**, zero diff either direction |
| Strategic questions | 8 | 8 / 8 (100%) | **Fully applied.** Live has 1 additional pre-existing question (`sq-premium-flavor.json`) |
| **Signals** | **6** | **0 / 6 (0%)** | **Never applied.** `data/signals/` is empty. The package's own `README.md` explains why at the time: *"Six proposed signals. All `status: 'proposed'`, none confirmed. **Not importable** - no signal schema exists in the repository (limitation L-7)"*. That was true when the package was generated (2026-08-04) against a zip snapshot with no `.git` directory; the live repo's `schemas/signal.schema.json` has existed since the very first commit that day, but nobody has gone back to apply these 6 records since the schema/route became available. |

**Bottom line for Section 6: applied, not partial, except for signals, which are 0% applied.** The evidence status field (`in_review` per the package's manifest vs. `published` in live data) is a documented discrepancy worth naming precisely, though it appears to reflect the import tool's own intended `--approve` gate having been run deliberately, not an accident.

### The "124 unvalidated" evidence, precisely

Of the 124 evidence records with no `validated` field: **121 are this import package's evidence** (all `auto_captured: false`, so they were never subject to the auto-capture validate/purge gate at all), and **3 are the original Milestone-0 seed/demo records** (`ev-sample-patent-published.json`, `ev-sample-retail-placement.json`, `ev-sample-variety-launch.json`). None of these 124 are part of any live review backlog — they are simply evidence that predates the `validated` field's purpose (gating auto-captured content) and were never meant to carry it.

### Research-package data not visible in the UI despite existing in JSON

- **The 6 unapplied signals** — exist only under `data/imports/.../signals/`, not reachable by any route.
- **`priority-actions.md`, `next-research-waves.md`, `coverage-gaps.md`, `conflicting-claims.md`, `proposed-schema-enhancements.md`** and the rest of the package's markdown documentation — rich, structured analysis (16 recommended actions with success tests, documented schema-enhancement proposals P-1 through P-11, documented limitations L-1 through L-10) that exists only as prose in `data/imports/`, invisible to any end user of the running app, static or live.
- **`source-coverage.csv`** — every source the research pass consulted, tiered, with what it supports — not reflected in the live `data/configuration/sources.json` registry (which has its own, separately-built 120-source list).

---

## 7. Data rendering audit

**EVIDENCE SOURCE TIER**
Stored: yes (informally — as a plain string inside the evidence `tags` array, e.g. `"tier-1"`, not a dedicated schema field)
Rendered: yes, but generically
Where rendered: as an undifferentiated tag badge alongside unrelated tags like `"negative-evidence"` or `"scope-correction"` (`feed.html`, `evidence.html`)
Problem: no visual or structural distinction between a source-tier tag and any other tag; a reader can't filter or sort by tier, and a `tier-1` tag looks identical to a `scope-correction` tag

**SOURCE RELIABILITY** (the monitored-source registry's own reliability signal)
Stored: yes — `monitoring_priority` (high/medium/low) on each source in `data/configuration/sources.json`
Rendered: yes
Where rendered: `/sources` page (filter + display), and (added this session) used to sort the auto-captured section of `/review`
Problem: none observed — this is a genuinely well-connected field

**FACT CONFIDENCE**
Stored: yes — `fact.confidence` (low/medium/high)
Rendered: yes
Where rendered: badge on entity and evidence detail pages
Problem: none

**FACT/CLAIM DISTINCTION**
Stored: yes — `fact.classification`
Rendered: yes
Where rendered: badge (`FACT`/`CLAIM`) on entity and evidence detail pages
Problem: none — this is one of the more completely-realized parts of the data model

**RELATIONSHIP CONFIDENCE**
Stored: **no** — no `confidence` field exists on the relationship schema at all
Rendered: partially — where present, it's free text inside `notes` (e.g. `"confidence=low; Inferred only from..."`), rendered as part of that note, not as a structured badge
Problem: not a real field; can't be filtered, sorted, or validated; entirely dependent on whoever wrote the note following the convention

**TRAIT PROVENANCE**
Stored: partially — a trait entity lists which evidence/facts mention it in general, but no relationship predicate links a specific trait value to a specific variety
Rendered: only indirectly, by reading fact statement prose
Problem: "which varieties have trait X, per which source" is not a queryable structure

**DISPUTED STATUS** (facts)
Stored: yes — `fact.status == "disputed"` (10 live records)
Rendered: yes, but with **no visual distinction** — plain trailing text, same typography as `active`
Where rendered: entity.html and evidence.html fact lists (`· disputed`)
Problem: a reader has to read every word of small print to notice a fact is disputed; nothing draws the eye

**DISPUTED STATUS** (relationships)
Stored: yes — `relationship.status == "disputed"` (2 live records)
Rendered: **no** — the relationship display template (`evidence.html`) prints `subject predicate object` and an optional effective date only; `status` is never interpolated
Problem: a disputed relationship is currently indistinguishable from an active one anywhere it's shown

**UNVERIFIED STATUS** (entities)
Stored: yes — `entity.status == "unverified"` (16 live records)
Rendered: yes, with distinct color — `.badge-status-unverified{color:#8a5a10;background:#fdefd9}`
Where rendered: entity detail page Status badge, and (separately) the Work Queue's "Unresolved entity matches" card
Problem: none — this is a well-implemented case, worth noting as a positive example

**STRATEGIC-QUESTION LINKS**
Stored: yes — `evidence.strategic_question_ids`, `strategic_question.evidence_ids`
Rendered: yes, both directions (evidence page shows linked questions is NOT directly rendered as a section — verified: evidence.html has no strategic-question display; only the strategic-question's own detail page shows its linked evidence)
Problem: the link only renders in one direction (question → evidence), not the reverse (evidence → question)

**PRIORITY RATIONALE**
Stored: yes — each of the 4 priority dimensions carries a `level` and a free-text `rationale`
Rendered: yes, on the evidence detail page
Problem: none structurally, but see Section 6/9 — 0 of the 1,139 auto-captured records have any priority set, so this rich display only ever appears for the 124 manually-curated records

**SIGNAL SUPPORT**
Stored: n/a — 0 live signals exist
Rendered: the UI to render one is fully built (`signal_detail.html`) but has never been exercised against real data
Problem: unverifiable at scale; only manually tested by this audit's own dry-run of `POST /signals`

**GEOGRAPHY RELATIONSHIPS**
Stored: yes — via `operates_in` relationships (51 live records) and `evidence.geography_ids`
Rendered: yes — in the merged entity activity timeline and as filter tags on newsfeed cards
Problem: no dedicated "Geography" rollup view exists (no map, no per-geography company list beyond filtering the newsfeed/entity list by that geography)

**PATENT LINKS**
Stored: yes — patents are first-class entities (38 live), linked via `entity_ids` on evidence and via `owns`/`licenses`/`develops` relationships
Rendered: yes, on the individual patent's own entity page and wherever it's cross-referenced
Problem: patents have no sidebar nav entry point (Section 4/9) — reachable only by search or inbound link

---

## 8. Real user workflows

### Workflow A — a user finds an article and wants to add it

1. Click "Add Intelligence" (top of Newsfeed) → `GET /intake`.
2. Choose one of 4 pathways: Article/URL, Note/Observation, Upload Report, Standalone Fact.
3. Fill in the form (title, source URL, summary, why it matters, suggested competitors/varieties as free text) → `POST /intake`.
4. This writes a draft into `inbox/evidence/` — **not yet visible anywhere in the newsfeed or search.**
5. The draft now appears in `/review` (the unified review queue, alongside auto-captured evidence). Opening it (`GET /review/{id}`) shows the original submission next to a full structuring form: entity match/create, proposed facts, proposed relationships, priority levels with rationale per dimension, duplicate-title warning if one is detected.
6. Submitting that form (`POST /review/{id}/publish`) writes the evidence record (and any facts/relationships) into `data/`, deletes the draft, and the item is now live in the newsfeed and search.

**Where it currently stops for a real user**: nowhere structurally — this workflow is fully implemented end-to-end and was directly exercised by this audit's own test suite (`test_review_queue_and_form_render`, `test_review_flags_possible_duplicate_title`, etc.). The main friction point is that the structuring step (step 5) requires a human who understands the domain model to fill in facts/relationships/priority correctly — there is no assisted extraction (Section 4, Milestone 6/AI-assisted enrichment is not built).

### Workflow B — a user wants to understand a competitor

1. Sidebar → "Competitors" → `GET /entities/company` → filterable list (search, berry, region, company cross-filter).
2. Click into a company (e.g., `company-agrovision`, directly verified in this audit) → `GET /entities/company/{id}`.
3. What they see: Status/Roles/Berries/Regions, aliases, a merged **Recent activity** timeline mixing evidence articles, facts, claims, and relationships (owns/licenses/operates_in/partners_with) chronologically, a Description, an Attributes table (headquarters, ownership, founding year — including a *documented, disputed* founding-year discrepancy shown as `null` value plus an explanatory note), a Trust summary (evidence count / source count / last updated), a Facts list with classification+confidence badges, and a Linked Evidence list.
4. **What they can NOT see directly on that page**: the company's varieties, patents, or breeding-program relationships as a *dedicated grouped section* — those only surface if a relationship or piece of evidence happens to mention them in the merged timeline or linked-evidence list. There is no "Portfolio" or "Varieties licensed" rollup.
5. Signals: none exist to show (Section 6), so this is currently a dead end regardless of implementation status.
6. Strategic questions: not linked from the company page at all — a user would have to separately browse `/strategic-questions` and look for mentions.

### Workflow C — a product leader wants to understand blueberry globally

- **What currently works**: the newsfeed filtered to `berry=blueberry` shows every published item; entity list pages filtered the same way show all 34 companies / 42 varieties / 18 geographies etc. tagged to blueberry; the priority queues show what's been flagged reading/testing/commercial/monitoring — **but only for the 124 manually-curated items**, since (verified directly, Section 4) 0 of the 1,139 auto-captured items have any priority set. Strategic questions give a curated set of 9 standing research questions with their linked evidence.
- **What's missing**: no cross-berry rollup (the product only has blueberry data right now, so this is untested in practice), no dashboard/summary view synthesizing "what changed this week across the whole berry," no map, no aggregate charts of any kind (competitor count by region, variety count by trait, etc.) — every view is a filtered list of individual records, never a rollup or visualization.

### Workflow D — an analyst wants to review and publish imported evidence

Two genuinely different implemented workflows exist depending on how the evidence arrived:

- **Intake drafts** (Workflow A's pathway): reviewed one at a time via the full structuring form at `/review/{id}`, publish is a deliberate, structured action.
- **Auto-captured evidence**: reviewed via a binary Validate/Purge/Purge-and-block-domain decision, either one record at a time (newsfeed card banner) or, as of this session, in a unified list at `/review` sorted by source monitoring priority, with inline action buttons that keep the reviewer on the review page after each action. Bulk review beyond that (dozens+ at once) requires leaving the app for `scripts/export_for_review.py` → edit an `.xlsx` → `scripts/apply_review_decisions.py`, both command-line only.
- **A one-off, third pathway** was used exactly once: the blueberry import package's own `import_package.py --dry-run/--apply/--approve` script (Section 6), never wired into the live app.

### Workflow E — a user wants to determine which varieties deserve testing

**Does the platform currently support this meaningfully? Verified directly: not really, no.**

- `/queues/testing` shows evidence items with `priority.testing.level != "none"`, sorted high→low then newest-first, each showing its linked entity names.
- This is an **evidence-centric** list, not a **variety-centric** ranking. There is no "Varieties, ranked by testing priority" view — a user has to scan the Testing Queue's evidence items and manually note which varieties are mentioned in each.
- Only 65 evidence records (all from the 124 manually-curated set) have any testing-priority level at all; the 1,139 auto-captured records — which is to say, 91% of all evidence in the system — have never been assessed on this dimension and contribute nothing to this queue.

---

## 9. UI / UX audit

- **Navigation**: fixed left sidebar, present on every page, consistent across the app. Links: Newsfeed, Work Queue, Competitors, Varieties, Strategic Questions, Signals, Sources (authoring only), a divider, Review Queue (authoring only, count badge), Reading/Testing/Commercial Position/Monitoring queues (each with a count badge).
- **Page shell**: consistent `<aside class="sidebar">` + `<main class="main">` two-column grid across every page (`base.html`), with a shared top bar containing global search. No page deviates from this shell.
- **Visual hierarchy**: consistent eyebrow-label + `<h1>` page-heading pattern at the top of every page, consistent card system (`.card`, `.cockpit-card`) for list items.
- **Density**: newsfeed and entity pages are dense — an entity like `company-agrovision` renders a long, single-scroll page mixing a chronological timeline, facts, and linked evidence with no in-page section navigation or collapsing; verified directly, this page's full text extraction ran to well over 100 lines.
- **Card system**: the same `.card` markup is deliberately reused across the newsfeed and the new auto-captured section of the review queue (this session's own change) — a genuine consistency win, verified in the template source.
- **Typography**: Inter font family throughout, consistent badge/heading scale (`app.css`), no typographic inconsistency observed between pages.
- **Responsive behavior**: **not evaluated at width — this audit did not resize the viewport.** The CSS uses relative units (`min(680px,80%)`) in a few places but there is no documented mobile-specific layout, and the fixed two-column sidebar grid has no observed collapse behavior for narrow viewports.
- **Design-language consistency with the approved mockup**: `entity_activity()`'s own docstring states its "Recent activity" panel is "the 'what's new with company X' view the original approved mockup showed (assets/platform-visual-language.png, panel 4) but was never actually built" until this session implemented it — direct evidence that at least one major approved-design element was missing for most of this project's life and has only recently been added.
- **Strongest screen**: the individual entity detail page (e.g., `company-agrovision`) — richest, most complete expression of the domain model (facts with classification/confidence, disputed status visible if you read closely, a real merged timeline, provenance counts).
- **Weakest screen**: the Signals list/detail pages — fully built, but with 0 live data to render, so their real quality is untested; closely followed by the Work Queue, whose "Awaiting review" card is now visibly wrong (undercounts) relative to the newer, more complete `/review` page.
- **Areas that still look like developer scaffolding**: the plain HTML `<dl>`-based Attributes tables on entity pages; the newsfeed's `NONE`/`NONE`/`NONE`/`NONE` priority badges on every auto-captured card (functionally correct, but visually noisy — four gray "none" badges on the large majority of cards); the empty `data/signals/` directory backing a fully-built but never-populated feature.

### Ten most important UX issues observed

1. **7 of 9 entity types have no sidebar navigation entry point** (patents, geographies, traits, breeding programs, brands, retailers, berries) despite 86 entities across those types existing in live data — only reachable via search or an inbound link.
2. **The priority queues (reading/testing/commercial/monitoring) are silently empty for 91% of all evidence** — a user browsing "Testing Queue" has no on-page indication that auto-captured content was never assessed and simply isn't there.
3. **Disputed status (both facts and relationships) has no visual distinction** — a disputed fact reads identically to an active one except for one word in small trailing text; disputed relationships don't render their status at all.
4. **Two overview pages (`/work-queue` and `/review`) now disagree** on how many items are awaiting review, since only `/review` was updated this session to count auto-captured evidence.
5. **Relationship confidence is not a real field** — where it appears, it's a hand-written convention inside a free-text `notes` field, invisible to any filter/sort/badge.
6. **Every auto-captured newsfeed card shows four "NONE" priority badges**, since none of them have ever been assessed — visually repetitive noise across the large majority of the feed.
7. **Entity pages have no relationship-specific section** — relationships are only visible interleaved into the general activity timeline, making it hard to answer "who does this company partner with" at a glance without reading the whole timeline.
8. **No cross-reference from evidence to the strategic questions it supports** — the link only renders in one direction (question → evidence).
9. **Signals are a fully-built, zero-content feature** — impossible to assess real UX quality without live data, and the 6 ready-made proposed signals from the import package were never applied to give it substance.
10. **No in-page section navigation on long entity pages** — a page like `company-agrovision`'s runs to a very long single scroll (timeline + description + attributes + facts + linked evidence) with no jump-links or collapsing sections.

---

## 10. Code quality audit

| Dimension | Score (1-10) | Justification |
|---|---|---|
| Architecture clarity | 6 | The overall shape (FastAPI + Jinja2 + flat JSON, no DB) is simple and consistent, and well-documented in `ARCHITECTURE.md`. But `app/main.py` is a single 2,512-line file holding every route, every data-access function, and business logic together — no separation into routers/services/models. |
| Maintainability | 6 | Extensive inline comments explain *why*, not *what*, and generally do so well (a real strength). But the single-file structure and the two independent search implementations (Section 2) are a maintenance burden already visible in this session's own work (the entity-first/date-sort ranking logic had to be hand-synced between the dropdown and full-results page, and was actually out of sync until fixed this session). |
| Schema design | 7 | JSON Schema with `Draft202012Validator` and `FormatChecker`, real enums for classification/confidence/status, genuine FACT/CLAIM distinction. Weaknesses: no `confidence` on relationships, `attributes` is a fully unstructured free-form bag, no referential-integrity checking anywhere (a dangling `evidence_id` reference would silently fail, not error). |
| Separation of concerns | 5 | Route handlers in `app/main.py` mix HTTP concerns, business logic, and direct file I/O in the same functions throughout; no service layer. |
| Code organization | 5 | Flat `app/main.py`; templates are organized sensibly (`app/templates/`, one file per page type); scripts are appropriately separated as standalone CLI tools. |
| Test coverage | 7 | 122 tests, real integration coverage through `TestClient` for nearly every route observed in this audit, tests for edge cases (open-redirect guard, domain-blocking exceptions, priority-sort ordering). Weakness: no coverage at all for the static build's JS search-ranking logic (`search-core.js`), since there's no JS test runner in the repo — that logic's correctness currently rests entirely on manual browser verification. |
| Error handling | 6 | Routes use `HTTPException` appropriately for 403/404/400 cases; the auto-capture pipeline has genuinely sophisticated, well-documented crash/retry/circuit-breaker logic (`resolve_real_summaries.py`). Weakness: no top-level error page/handler observed, and file I/O throughout assumes the filesystem is always writable and available. |
| Portability | 6 | No OS-specific code observed; runs on Windows (this audit's own environment) without issue. Weakness: Python version is undeclared (Section 1), and the static-site generator assumes a POSIX-like `pathlib` usage that has worked here but isn't explicitly tested cross-platform in CI (CI only runs on `ubuntu-latest`). |
| Documentation | 8 | Unusually thorough for a project this size: a full PRD, vision doc, domain model, architecture decision records, a detailed `ARCHITECTURE.md` that narrates *why* each past decision was made (not just what exists), and a build guide with explicit milestones. See Section 13 for how current it is. |
| Readiness for additional berries | 4 | The schema and code are explicitly berry-agnostic (`berry_ids` arrays everywhere, `VISION.md`'s vendor-neutrality principle), but every existing entity, fact, relationship, and source in `data/` is blueberry-only — there is zero raspberry/strawberry/blackberry data to prove the model actually generalizes in practice, and the source registry (120 sources) was built entirely around blueberry-relevant trade press and keyword searches. |

**Obvious technical debt**: the single-file `app/main.py`; two independently-maintained search implementations; the `/work-queue` vs `/review` count discrepancy (Section 4) introduced by this session's own incomplete rollout.

**Duplicated logic**: card-rendering markup is intentionally duplicated between `feed.html` and `review_queue.html` (a template-inheritance opportunity not taken, though the duplication is small and was a deliberate choice this session for speed, per its own commit message).

**Hardcoded assumptions**: `REGION_LOOKUP` in `app/main.py` is an explicit, non-exhaustive dict mapping specific country names to regions, with a documented rationale for staying non-exhaustive; `PRIORITY_DIMENSIONS`, `PRIORITY_LEVELS`, `SOURCE_PRIORITY_RANK` are all Python constants, not data-driven — changing them requires a code change and redeploy, not a config edit.

**Blueberry-specific code that should be berry-agnostic**: none of the *code* is blueberry-specific (verified — no hardcoded "blueberry" string found gating any route or business-logic branch); the blueberry-specificity is entirely in the *data* (Section above).

**Fragile areas**: the two-search-implementation split (Section 2); the `validated`/`status` dual-approval-concept confusion (Section 5/6); referential integrity between JSON files is entirely convention-based, with no automated check that a `fact.evidence_ids` entry resolves to a real file.

**Weak generated-code areas**: none observed that stood out as distinctly weaker than the surrounding code — the codebase reads as consistently authored (single voice/style throughout, including comments), not as a patchwork of differently-sourced fragments.

**Unexpectedly strong areas**: the source-polling crash/retry/circuit-breaker logic in `resolve_real_summaries.py` (domain-aware circuit breaker, two-layered crash recovery, retry-before-declaring-block policy) is meaningfully more sophisticated engineering than the rest of the app's CRUD-heavy code, and is thoroughly explained in `ARCHITECTURE.md`; the test suite's use of `monkeypatch`+`tmp_path` for full isolation per test is clean and consistently applied.

---

## 11. Test and validation status

All checks below were run directly during this audit, non-destructively, against the current working tree.

| Check | Command | Result |
|---|---|---|
| Full test suite | `pytest -q` | **122 passed, 0 failed**, 144 warnings (all the same pre-existing `feedparser` deprecation warning, unrelated to test correctness), ~4 minutes wall time |
| Schema/record validation | `python scripts/validate_records.py` | **"All validated records passed."** — zero schema errors across all `data/entities`, `data/evidence`, `data/facts`, `data/relationships`, `data/strategic-questions`, `data/signals` |
| Static build | `python scripts/build_static.py` | **Succeeds** — 1,452 pages written to `generated/`, Pagefind search index built, the build's own "no unpublished draft leaked into output" self-check passes |
| Live app smoke test | manual navigation via browser during this audit | Newsfeed, entity detail (`company-agrovision`, `company-hortifrut`), Sources, Review Queue, and static-build Search all render and are interactive; no errors observed |
| Import-package validation | not re-run (the package's own `validate_package.py` is a one-off script tied to the package's own generation process, not part of this repo's ongoing CI) | not applicable to ongoing validation |

Nothing failed. No repairs were made or needed to be made.

---

## 12. Deployment readiness

**Path: local repository → Git → GitHub → hosted application**

- **What's automated**: on every push to `master`, `.github/workflows/deploy-pages.yml` installs dependencies, **runs `pytest -q`** (added this session — previously it did not), runs `scripts/validate_records.py`, runs `scripts/build_static.py`, and uploads the result to GitHub Pages via `actions/deploy-pages@v4`. This is a complete, working pipeline — verified by reading the actual workflow file and confirming it matches what was just tested manually (Section 11).
- **What's manual**: everything upstream of `git push` — authoring, review, publishing, source registry curation, and (per Section 6) the one-off import-package application all happen locally, by a human, before anything reaches Git.
- **Environment variables required**: `BIOS_MODE` (defaults to `"authoring"`; set to anything else to run read-only), `ENABLE_SOURCE_POLLING` (defaults off — polling never runs unless explicitly enabled). No secrets, API keys, or credentials are required to run the app or the CI pipeline.
- **Stateless or writable storage?** The **live/authoring app is not stateless** — it reads and writes directly to the local filesystem (`data/`, `inbox/`) on nearly every authoring action (publish, validate, purge, add source, etc.). The **static build is fully stateless** by design — `generated/` is disposable and fully reproducible from `data/` (the repo's own documented "Rebuild guarantee").
- **Can it currently be hosted as a static site?** **Yes**, and this is the only hosting path actually implemented and exercised — GitHub Pages, verified live at the deployed URL referenced elsewhere in this project's history.
- **Does read-only deployment work?** **Yes** — `static_build=True` context disables the filter forms, disables authoring actions, and the CI pipeline itself proves the read-only artifact builds cleanly on every push.
- **What would be needed for a future remote submission capability** (i.e., letting someone submit intelligence to a hosted instance, not just browse it)? Per `README.md`'s own stated V1 operating model ("Later add a secure hosted submission pathway without changing the trusted data model") and `ADR-0003`, this is an explicitly deferred, not-yet-designed capability. Concretely, based on what exists today, it would require at minimum: a real database or writable persistent storage behind the hosted instance (the current flat-file model has no concurrency/locking story for multiple simultaneous writers), some authentication/authorization layer (none exists today, Section 4), and a decision about how a hosted "untrusted intake" queue reconciles with the local-first "trusted `data/`" model that the whole current architecture is built around.

---

## 13. Documentation truth audit

| Document | Accuracy assessment |
|---|---|
| `docs/04-technical-architecture/ARCHITECTURE.md` | **Accurately reflects the code** — and unusually so: it's written as a running narrative of decisions actually made, with dates, root causes, and even documented mistakes (e.g., the search-ranking regression this session found and fixed is described in detail, including *why* the earlier fix caused it). This is the most trustworthy document in the repo relative to current code. |
| `docs/05-development-roadmap/BUILD-GUIDE.md` | **Accurately reflects completed work through Milestone 5**; Milestone 6 ("AI-assisted enrichment... suggested summaries, entity extraction, fact proposals, duplicate suggestions, priority recommendations, signal clustering") is explicitly **not started** — verified directly, no AI/LLM integration exists anywhere in `app/` or `scripts/` (confirmed via search for `anthropic`/`openai`/`llm` across the codebase). |
| `docs/01-prd/PRD.md` | **Partially aspirational relative to actual code.** Its "V1 scope — Deferred" section explicitly lists "automatic web scraping" and "autonomous publishing" as deferred — but automatic web scraping (source polling / `check_source()`) has since been built. It is not fully autonomous publishing (auto-captured items still require a human validate/purge decision), so the PRD isn't flatly wrong, but the document has not been updated to reflect that this line moved. |
| `docs/00-product-vision/VISION.md` | Its "north-star outcome" (understand competitive landscape, emerging threats, category evolution, what deserves reading/testing/commercial/monitoring, "why the platform reached a conclusion") is **aspirational relative to current implementation** in specific, verifiable ways: there is no synthesized "why" explanation anywhere in the UI beyond individual fact/priority rationale text, and (Section 8, Workflow C) there is no category-evolution rollup view. |
| `docs/03-information-architecture/DOMAIN-MODEL.md` | Not deeply cross-checked line-by-line in this audit, but its existence alongside the more detailed `schemas/*.json` (which are authoritative and validated in CI) means any drift between the two would favor the schema as ground truth. |
| `docs/07-static-deployment/STATIC-DEPLOYMENT.md` | **Accurate**, verified directly against `scripts/build_static.py`'s actual behavior (relative-link rewriting, Pagefind integration, draft-exclusion self-check) — one minor omission: it describes copying `app.css` but doesn't mention `search-core.js`, added this session; the code itself does copy it correctly. |
| `data/imports/blueberry-public-pilot-2026-08-03/README.md` and its sibling docs | **Extremely accurate and self-aware** about its own limitations (documents its own signal-import gap, its own schema-conformance self-test, its own rejected sources) — the strongest self-documentation of any single artifact in the repo. |
| `WELCOME.md` | Not read in full during this audit; referenced by `import_package.py`'s own comments as the source of the "AI proposes; a human approves" principle, which is consistent with what was observed in the actual import tooling's three-gate design. |

**Obsolete documents**: none identified as fully obsolete — even the oldest docs (`VISION.md`, `PRD.md`) remain the honest statement of intent the team is still building toward, just not yet fully realized.

**Contradictory architectural statements**: none found between `ARCHITECTURE.md` and the code. The one real contradiction found is data-level, not architectural: the import package manifest's `evidence_status_on_import: "in_review"` vs. the live `status: "published"` on those same records (Section 6) — a process-execution discrepancy, not a documentation error, since the import tool's own `--approve` step exists precisely to make that transition.

**Features described but not implemented**: Milestone 6 (AI-assisted enrichment, `BUILD-GUIDE.md`); the "secure hosted submission pathway" (`README.md`).

**Features implemented but not documented**: the unified Review Queue and the `redirect_to` allowlist pattern on validate/purge (both from this session) are documented in `ARCHITECTURE.md` already; the `/work-queue` vs. `/review` count discrepancy this created is **not** documented anywhere, including in `ARCHITECTURE.md`'s own account of that change.

---

## 14. Biggest gaps between vision and implementation

Ranked by strategic importance (impact on the product's stated purpose), not by how hard each would be to close.

1. **No synthesized "why" or rollup view exists anywhere.** `VISION.md`'s north-star explicitly promises understanding "why the platform reached a conclusion" and "how each berry category is evolving globally" — today the platform only ever shows individual records (evidence, facts, entities) in filtered lists; there is no aggregation, summary, or narrative synthesis layer at any level.
2. **The priority-queue system — one of the PRD's core pillars — doesn't scale with the platform's dominant data source.** 91% of all evidence (the auto-captured majority) has zero priority assessment on any of the four dimensions; the queues that are supposed to tell an analyst "what deserves reading, testing, commercial review, or monitoring" only ever reflect the 9% of evidence that was manually curated.
3. **Milestone 6 (AI-assisted enrichment) is entirely unstarted**, despite being the mechanism the build guide itself identifies as necessary to close gap #2 (suggested summaries, fact proposals, priority recommendations, duplicate suggestions).
4. **Six ready-made, human-reviewable signals sit unused in `data/imports/`**, and the signals feature — a full, working part of the product — has zero real data to prove it out, despite the import package having done the work to propose exactly this.
5. **Two competing "is this trustworthy" gates exist with no shared vocabulary** (`status` for intake/import-approved evidence, `validated` for auto-captured evidence only) — this doesn't just complicate the codebase (Section 10), it directly undermines the evidence-first trust model that is the platform's core identity (`ADR-0002`).
6. **7 of 9 entity types (86 entities) have no navigation path** — geographies, patents, breeding programs, traits, brands, and retailers are functionally invisible to a user who doesn't already know to search for them, despite being first-class, fully-modeled parts of the domain.
7. **Relationship confidence is unstructured**, undermining the "evidence-first, confidence-graded" premise for exactly the record type (relationships) that expresses the competitive-landscape connections `VISION.md` cares most about.
8. **Disputed status has no visual weight** anywhere it's shown — a platform whose stated identity is "trustworthy evidence system" currently makes disputed claims and relationships look identical to settled ones.
9. **No cross-berry proof point exists.** The architecture is designed to be berry-agnostic, but 100% of real data is blueberry-only, so the "foundation for raspberry/strawberry/blackberry expansion" claim (Section 15's rating category) is currently a design intention, not a demonstrated capability.
10. **The single-user, no-auth, filesystem-writable architecture has no defined path to the "hosted team submission" future** the README itself flags as deferred — every writable-state operation in the current code assumes a lone local operator, with no concurrency, locking, or identity model to build on when that changes.

---

## 15. Current-state rating

| As a... | Rating (1-10) | Justification |
|---|---|---|
| **1. Working software prototype** | 8 | It runs, all 122 tests pass, schema validation passes, the static build deploys successfully, and this audit directly exercised the live app end-to-end without hitting an error. Not a 9-10 because of the undeclared Python version and the two-search-implementation maintenance risk. |
| **2. Competitive-intelligence tool** | 6 | The domain model (entities, evidence, facts, relationships, strategic questions) is genuinely well-suited to the job, and one real competitor deep-dive (Agrovision/Fruitist) demonstrates it can hold rich, well-sourced, dated, conflict-aware intelligence. Held back from higher by the total absence of any rollup/synthesis view and by 7 of 9 entity types being unreachable via navigation. |
| **3. Trustworthy evidence system** | 6 | Real FACT/CLAIM distinction, real confidence levels, real disputed-status tracking, real evidence-to-fact-to-entity provenance chains — the underlying data model earns real trust. The score is capped by the *rendering* gap: disputed status has no visual weight, relationship confidence isn't structured, and evidence source tier is just an undifferentiated tag. The trust is in the data; the UI doesn't yet make it legible. |
| **4. Product-leader decision-support tool** | 4 | The stated north-star (understand the competitive landscape, category evolution, "why") is not yet realized: no dashboards, no rollups, no synthesized narrative, and the priority queues that were meant to say "what deserves your attention" only cover 9% of the data. A product leader can currently *research* effectively (Workflow B works well) but cannot get a *summary* of anything without reading individual records. |
| **5. Maintainable long-term platform** | 6 | Strong documentation culture, real test coverage, clean data model, well-explained architectural decisions. Held back by the monolithic `app/main.py`, the duplicated/unsynced search-ranking logic across two implementations, and the fact that this very audit found a fresh two-page-disagreement bug (`/work-queue` vs `/review`) introduced in the most recent commit — a sign that even careful, well-documented changes in this codebase can leave siblings out of sync because there's no structural mechanism (shared component, single source of truth) preventing it. |
| **6. Foundation for raspberry/strawberry/blackberry expansion** | 5 | The schema, routes, and templates contain zero blueberry-specific code — genuinely berry-agnostic by design, verified directly. But every single one of 1,263 evidence records, 162 entities, and 120 sources is blueberry-specific, and the source-monitoring registry was hand-built entirely around blueberry-relevant trade press. Expansion to a second berry is architecturally unblocked but has never been attempted, so the claim is unproven in practice. |

None of these scores were inflated; each is capped by a specific, cited, verified limitation rather than a general impression.

---

## 16. Recommended freeze point

*(Observation only, per the audit's scope — no roadmap proposed.)*

**What should be preserved:**
- The core JSON-file + JSON-Schema data model and its FACT/CLAIM/confidence/disputed vocabulary — it is the single strongest asset in the repository and is already doing real work (10 disputed facts, 16 unverified entities, a genuinely useful merged activity timeline).
- The static-publication pipeline and its "Rebuild guarantee" — `generated/` being fully disposable and reproducible from `data/` is a real architectural strength worth protecting from any change that would introduce hidden state.
- `ARCHITECTURE.md`'s narrative-documentation practice — it is the reason this audit was able to verify claims quickly and accurately; any team continuing this project should keep writing it this way.

**What should not be touched yet:**
- The single-`app/main.py` structure, until there's a concrete reason (a second developer, a feature that genuinely needs a service boundary) — splitting it prematurely risks losing the current, verified-working coherence for a refactor with no immediate payoff.
- The blueberry-only dataset — it's a real, deep, well-sourced dataset; expanding to a second berry before addressing the rollup/synthesis gap (Section 14, #1) would multiply the "lots of records, no way to see the big picture" problem rather than solve it.

**What is safe to rethink:**
- The two-track "is this trustworthy" vocabulary (`status` vs. `validated`) — since it's already confusing (Section 5/6) and only 124 records currently depend on the distinction, this is a comparatively cheap, high-clarity fix window before more data makes it more entrenched.
- Whether `/work-queue` should exist as a separate page from `/review` at all, now that `/review` has grown into the more complete of the two.
- Entity-type navigation (Section 9, issue #1) — a low-risk, high-visibility fix.

**What is currently blocking further progress**, in the sense of "the next meaningful step depends on this being decided first":
- Whether Milestone 6 (AI-assisted enrichment) is actually the intended next investment, given it's the mechanism that would close the single largest gap (Section 14, #1 and #2) — this is a product decision, not an engineering one, and nothing else in the roadmap obviously supersedes it in priority given what this audit found.
- Whether a second berry is added before or after the rollup/synthesis and entity-navigation gaps are closed — doing it before will make an already-partial browsing experience proportionally harder to navigate.

**Decisions that should be made before more coding begins:**
- Reconcile the `status`/`validated` dual-gate model into one vocabulary, or explicitly document why both should remain separate, before either concept grows further via new data.
- Decide whether the 6 unapplied signals and the rest of the import package's unused analysis (`priority-actions.md`, `coverage-gaps.md`, etc.) should be applied as-is, revised, or discarded — they represent real, already-done analytical work currently at risk of going stale unreferenced in `data/imports/`.
