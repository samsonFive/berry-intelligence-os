# Technical Architecture

## Architecture style

Local-first, file-backed web application with a generated read-only publication layer.

## Authoritative data

Versioned JSON files are authoritative. SQLite or another local database may later be used as a generated index, but it must be rebuildable and never become the only source of truth.

## Initial stack

- Python 3.12+
- FastAPI
- Jinja templates
- vanilla JavaScript for V1 interactions
- JSON Schema validation
- optional SQLite FTS index in a later milestone
- Git for history and distribution

## Runtime modes

### Authoring mode

Runs locally and permits intake, review, editing, validation, and publication.

### Read-only mode

Serves only published records and generated pages.

### Static-build mode

Generates deployable HTML and assets from published JSON.

## Trust boundaries

- `inbox/` or draft records are untrusted.
- `data/` published records are trusted.
- generated indexes and pages are derived.
- future web submissions must never write directly into trusted published data.

## Initial API boundaries

- `GET /api/feed`
- `GET /api/evidence/{id}`
- `GET /api/entities/{type}/{id}`
- `GET /api/search`
- `POST /api/intake` — local authoring mode only
- `POST /api/review/{id}/publish` — local authoring mode only

## Page routes (Milestone 1)

- `GET /` — newsfeed, accepts `q`, `berry`, `source`, `priority` (`dimension:level`) query params combined with AND logic.
- `GET /evidence/{id}` — evidence detail page.
- `GET /entities/{entity_type}` — listing page for one entity type.
- `GET /entities/{entity_type}/{entity_id}` — entity detail page. A single template renders every entity type (company, variety, retailer, etc.) so no entity type is privileged in the UI layer, consistent with ADR-0004.

## Intake and the inbox (Milestone 2)

- Draft evidence created through intake is written to `inbox/evidence/{id}.json` and uploaded attachments to `inbox/attachments/{id}/`, not into `data/`. This makes the untrusted/trusted boundary a physical directory split rather than only a `status` field, matching the trust-boundary rule above and the capture flow described in `README.md`.
- Draft records reuse the evidence `id` shape (`ev-<timestamp>-<slug>`) but are not required to satisfy `evidence.schema.json` (in particular `priority` is `null` until reviewer assignment in Milestone 3). `scripts/validate_records.py` intentionally does not scan `inbox/`.
- The HTML intake form posts to `POST /intake` (not `/api/intake`) because it is a multipart form submission that redirects back to a rendered page (POST/redirect/GET), not a JSON API call. `POST /api/intake` remains reserved for a future programmatic/JSON intake path with the same underlying write logic.
- `GET /intake`, `GET /intake/{id}`, and `GET /intake/{id}/attachments/{filename}` render the intake form and let a submitter review what was captured, including original attachments — satisfying "original submission is preserved" without yet building the Milestone 3 review/structure workspace.
- Write endpoints check `AUTHORING_MODE` (from the `BIOS_MODE` environment variable, default `authoring`) and return `403` when not in authoring mode, giving the "Runtime modes" section above a concrete enforcement point.

## Review, structure, and publish (Milestone 3)

- `schemas/fact.schema.json` and `schemas/relationship.schema.json` were added; `scripts/validate_records.py` now also validates `data/facts` and `data/relationships`. Every fact requires `reviewer`, `confidence`, `status`, `created_at`, and at least one `evidence_ids` entry, matching the PRD's trust requirements (section 9). Every relationship requires at least one `evidence_ids` entry.
- `GET /review` and `GET /review/{draft_id}` render the split-pane review workspace (original submission vs. proposed structured record); `POST /review/{draft_id}/publish` performs entity match-or-create, writes proposed facts and relationships, and publishes the evidence record — all gated by `evidence.schema.json` validation before anything is written, so a failed publish leaves no orphaned entity/fact/relationship files. Like `/intake`, this is a form endpoint under `/review/...` rather than `/api/review/{id}/publish`, for the same POST/redirect/GET reason noted above; `/api/review/{id}/publish` remains reserved for a future JSON path.
- The published evidence keeps the same `id` it was assigned at intake (`ev-...`); fact and relationship ids are derived from it (`fact-<suffix>-N`, `rel-<suffix>-N`). Draft ids now include a short random suffix (`ev-<timestamp>-<random>-<slug>`) so two same-title submissions in the same second can't collide.
- Entity matching is by case-insensitive exact name + entity type against `data/entities/`. No match creates a new entity with `status: unverified` — a reviewer upgrades its status later; this is the "entity matching and creation" behavior, not fuzzy/AI matching (that is Milestone 6).
- Every proposed fact for one evidence item is linked to every entity the reviewer attached to that item (there is no per-fact entity picker in this v1 form); relationships must reference two of those same linked entity names.
- Duplicate detection (`find_possible_duplicates`) is a normalized-title exact/substring match against both published evidence and other pending drafts — intentionally simple and disclosed as such, not semantic similarity.
- Publishing moves any intake attachments from `inbox/attachments/{draft_id}/` to `data/attachments/{evidence_id}/`, served at `GET /evidence/{id}/attachments/{filename}`, so uploaded files survive the untrusted → trusted transition instead of being orphaned when the draft is deleted.
- New entity folders under `data/entities/` follow the existing irregular-plural convention (`company` → `companies`, `variety` → `varieties`, `geography` → `geographies`, `person` → `people`, `berry` → `berries`), defaulting to `+s` otherwise.

## Analyst workflow (Milestone 4)

- `schemas/strategic-question.schema.json` and `schemas/signal.schema.json` were added; `scripts/validate_records.py` now also validates `data/strategic-questions` and `data/signals`. A signal requires `evidence_ids` (at least one) so every signal keeps the "Published lineage" chain (`DOMAIN-MODEL.md`) traceable back to evidence, even when it is also supported by facts.
- `GET /work-queue` is the PRD's "Home / analyst cockpit" module (new evidence, drafts awaiting review, unresolved entity matches, high-priority items, recent signals) — deliberately kept separate from `GET /` (Newsfeed), since the PRD lists them as two distinct primary modules.
- `GET /queues/{dimension}` (`reading`/`testing`/`commercial_position`/`monitoring`) replaces the Milestone 1 `/?priority=dim:high` filter shortcut with a dedicated table view. A queue includes any item at `low`/`medium`/`high` for that dimension (not `high` only), sorted highest-priority-first and newest-first within a level, so the sidebar counts reflect everything needing attention rather than only the most urgent slice.
- Strategic questions are read/link-only in this milestone (`GET /strategic-questions`, `GET /strategic-questions/{id}`) — creating or editing one is out of scope; they're currently seeded like other sample data and linked to evidence during `/review/.../publish`.
- Signals are analyst-authored, not evidence-derived like facts/relationships: `GET /signals/new` and `POST /signals` let a reviewer cite existing published evidence/fact/entity ids directly (validated to exist) rather than reusing the intake→review pipeline, because a signal is a cross-cutting pattern observed *after* evidence exists, not something produced while reviewing one evidence item. AI-assisted signal clustering remains Milestone 6.
- `POST /signals` is gated by `AUTHORING_MODE` like the other write endpoints.

## Static publication (Milestone 5)

See `docs/07-static-deployment/STATIC-DEPLOYMENT.md` for the full deployment guide. Key decisions:

- `scripts/build_static.py` renders the same Jinja templates the live app uses (imported directly from `app.main`, not duplicated) into `generated/`, reading only `data/` — it never opens `inbox/`. This keeps the static build reproducible from, and only from, trusted records, and guarantees the live and static views can't visually drift apart.
- Every internal link is rewritten to be relative to the file containing it (depth computed per output file), rather than using a single configured `<base href>` prefix. This makes the output deployable at any host and any subpath with zero build-time configuration — no `--base-path` flag to get wrong.
- A new `static_build` template flag (default falsy, so it never affects the live app unless a route explicitly sets it) suppresses UI that can't function without a server: the global search box and the newsfeed's filter form. Shipping a form that silently does nothing on a static host was judged worse than omitting it with an explanatory note.
- The already-existing `authoring_mode` flag (previously only passed by some routes) is now passed consistently by every page-rendering route, so the "Review Queue" nav item — meaningless without a write-capable backend — is correctly hidden whenever a page is rendered with `authoring_mode=False`, in both the read-only live mode and the static build.
- Draft-exclusion is enforced twice: structurally (the generator's data access only touches `published_evidence()` / `all_entities()` / etc., which read `data/`, never `inbox/`) and by an explicit post-build scan (`validate_no_drafts_leaked()`) that greps every generated HTML file for any id or title belonging to a still-unpublished draft and fails the build if one is found. `tests/test_build_static.py` exercises both the happy path and a deliberately-forced leak to confirm the scan actually catches violations.

## Filter completeness fix

The PRD's V1 success criteria (section 10) require filtering by "berry, competitor, source, geography, event type, and priority." Competitor and geography filtering did not exist through Milestone 5 — geography wasn't even a field on evidence. Fixed:

- `evidence.schema.json` gained an optional `geography_ids` array (backward compatible; existing records without it remain valid). Geography is modeled as an entity (`entity_type: "geography"`), consistent with how companies/varieties/retailers already work, rather than a free-text field — this makes geography pages, entity matching, and relationship linking fall out of the existing entity infrastructure for free.
- The review/publish workflow gained a "Geographies" field alongside Companies/Varieties/Retailers, using the same match-or-create logic; `geography_ids` on the published record is derived as the subset of `entity_ids` whose entity is type `geography`, so no separate linking step was needed.
- The newsfeed gained Competitor and Geography filter dropdowns. "Competitor" filters by `entity_ids` restricted to `entity_type: "company"` in `filter_options()` — the underlying `filter_evidence(entity=...)` support was actually one line, since entity linking already existed; what was missing was the UI and the options list.
- "Event type" from the same PRD sentence remains unimplemented: there is no `event_type` field anywhere in the data model, and no evidence in the sample data suggests one — adding it now would mean designing a new taxonomy with nothing to validate it against, which is a decision better made against real captured data.

## Automated source monitoring

The PRD's Deferred list (section 5) explicitly excludes "automatic web scraping" and "real-time alerts" from V1. This feature reopens that decision at the user's explicit request, with a scope narrower than either: RSS/Atom polling only (no general scraping), and evidence lands as `published` immediately rather than through the review queue — a deliberate deviation from "AI proposes, human approves" (WELCOME.md principle 5) for this one ingestion path, chosen and confirmed directly by the user after being shown the review-queue alternative. Mitigated by making auto-captured items visually distinct and one-click reversible rather than indistinguishable from reviewed evidence.

- `data/configuration/sources.json` holds user-managed sources (`type: "rss"` or `"keyword"`, plus label/value/enabled). A keyword source has no separate search backend — it's rewritten to a Google News RSS query URL (`google_news_rss_url()`) at fetch time, so both source types share one fetch path (`fetch_source_entries()` → `feedparser.parse()`).
- A background `asyncio` task (`source_polling_loop()`, started from the FastAPI `lifespan` context manager) checks all enabled sources every 15 minutes, offloading the blocking `httpx`/`feedparser` work via `asyncio.to_thread` so a slow feed can't stall the event loop. The task is guarded by `"pytest" not in sys.modules` — it must never make real network calls during a test run; tests instead call `check_source()`/`check_all_sources()` directly with `httpx.get` monkeypatched.
- Dedup is by `source_url`, checked against every existing evidence record (`existing_evidence_source_urls()`) — not a per-source seen-list — so a URL already captured any other way (manual intake, bulk import, another source) is never re-created.
- **`SOURCE_MAX_NEW_ITEMS_PER_CHECK = 20`**: found by actually running a live keyword source against real Google News RSS during verification, which wrote 100 items in one check. Uncapped, the very first check of any reasonably broad source floods the feed. Items past the cap aren't lost — they're still "new" (not yet in `existing_evidence_source_urls()`) and get picked up on a later cycle, so a large backlog trickles in over several checks instead of arriving as one flood.
- Auto-captured evidence carries `auto_captured: true` and `validated: false` (both new optional `evidence.schema.json` fields, backward compatible). Every card/detail page for such a record shows an "AUTO-CAPTURED — UNVALIDATED" banner with one-click **Validate** (`POST /evidence/{id}/validate`, sets `validated: true`) and **Purge** (`POST /evidence/{id}/purge`, hard-deletes the file) actions. Purge refuses to run on any record where `auto_captured` isn't true, so it can't be used to silently remove manually-authored or imported evidence.
- New dependencies: `feedparser` (RSS/Atom parsing) and `httpx` (the fetch client — previously only a transitive test dependency via `TestClient`, now also used in production code, so pinned explicitly in `requirements.txt`).

## Region filtering across the app

Filtering by Region, Berry, Company, and variety name/code was requested for every list page, not just the newsfeed (which already had berry/competitor/geography). "Region" (Americas / Europe / Oceania / Middle East & Africa) didn't exist in the data model at all before this.

- `REGION_LOOKUP` is a fixed default table mapping geography name → region, confirmed with the user as "recommended default, must stay correctable." A per-geography override lives at `attributes.filter_region` — deliberately **not** `attributes.region`, because real imported geography entities already carry their own `attributes.region` in a different taxonomy (e.g. Australia: `"Asia-Pacific"`; Chile/Mexico/Peru: `"Latin America"`) for the package's own purposes. The first implementation used the obvious key name, `geography_region()` silently treated that pre-existing data as if it were a user correction, and Australia's derived region came back "Asia-Pacific" instead of "Oceania" — caught by checking a real page (`/entities/variety/variety-bonita`) after building, not by reasoning about the code. A geography not in the lookup and without an override (e.g. China) is left unclassified rather than guessed into the wrong bucket.
- Region is never stored on non-geography entities. `entity_regions()` derives it: the union of regions from every geography linked to evidence that also links the entity. A variety reported on in Portugal and Australia shows both regions automatically — there's no field to keep in sync as more evidence comes in.
- **Geography can be linked to evidence two ways**: the dedicated `geography_ids` array, or just as one of the general `entity_ids` (a geography is still an entity). The imported blueberry package predates the `geography_ids` field, so all 121 of its evidence records use only the second form — 54 of them link a geography this way with `geography_ids` empty. The first implementation of both `evidence_regions()` and the newsfeed's existing "Geography" filter checked only `geography_ids`, so region filtering initially returned almost nothing against real data (1 of 42 varieties for "Europe"). Fixed by checking both conventions everywhere geography linkage is read: `evidence_regions()`, the plain `geography` filter in `filter_evidence()`, and the geography dropdown's options in `filter_options()`. After the fix, the same query returned 12 of 42.
- "Company" filtering (on any entity-list page, not just companies) uses the actual relationship graph — `related_entity_ids()` collects every entity connected to the given one via any relationship, in either direction — rather than a weaker "appears in the same evidence record" heuristic. This was a real design choice, not the default: co-occurrence in evidence is noisier (two unrelated entities can appear in the same article), while `develops`/`owns`/`licenses`/etc. relationships already encode the actual connection for exactly this purpose.
- Variety "code" search rides the existing text-search convention (`filter_entities()`'s `q` parameter also matches `attributes.selection_code` and `attributes.patent_number`, not just name/aliases/description) rather than a separate dedicated field or endpoint.
- Scope of this pass: newsfeed and every `/entities/{type}` listing got full filtering (q/berry/region/company as applicable); priority queues got region only. Strategic questions and signals listings were deliberately left unfiltered — small, low-traffic lists (8 and typically 0-few items) — flagged as a scope cut rather than silently left incomplete.
- Found and fixed in the same pass, not filtering-related but blocking verification of it: `scripts/build_static.py` calls `base.html`'s `queue_counts()`/`pending_review_count()` Jinja globals on every single page render, and both re-read `data/` from disk uncached on every call. At the current record volume (~300+ generated pages) this made a full static build hang for minutes instead of completing. Fixed by computing both once at the top of `build()` and overriding the globals with the precomputed values for the duration of that build — safe there specifically because nothing in `data/` changes mid-build, which is not true of the live server, so the live app's routes were left as they were. The live app pays a real, now-measured ~0.3s/page cost from the same globals; not fixed here since it's outside what was asked, but worth knowing before it's mistaken for a network issue.

## Rebuild guarantee

Deleting `generated/` must not destroy knowledge. Running a rebuild command must recreate indexes and published pages from schemas, configuration, and trusted data.
