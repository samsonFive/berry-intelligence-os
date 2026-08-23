# Berry Intelligence OS

Local-first, evidence-based competitive intelligence for berry crops.

**Expansion phase:** Before planning new acquisition, domain-depth, variety, alternative-data, or UI V2 work, read `docs/v2/INTELLIGENCE-EXPANSION-BUILD-GUIDE.md`. Unresolved platform debt must be recorded in `docs/v2/TECHNICAL-DEBT-REGISTER.md`; source/domain expansion should update `docs/v2/INTELLIGENCE-COVERAGE-MATRIX.md`. Variety backbone (Workstream C) is `docs/v2/VARIETY-INTELLIGENCE-BACKBONE.md`. Trade is `docs/v2/TRADE-INTELLIGENCE-V1.md`. Weather is `docs/v2/WEATHER-CLIMATE-CONTEXT-V1.md`. Do not alter Variety backend/domain schemas, CPVO registry, `variety_footprint`, `commercial_observation`, Trade/Customs (`trade_observation`, Comtrade adapter), or Weather (`weather_observation`, NASA POWER adapter) unless a genuine blocker is found.

**Learner Mode (Workstream K, requirements only, not implemented):** Any agent working on agronomy, plant biology, IPM, harvest/agtech, sensory/flavor science, or visual learning content must read `docs/v2/feature-requests/LEARNER-MODE.md` and `docs/v2/INTELLIGENCE-EXPANSION-BUILD-GUIDE.md` section 12a first. Learner Mode is explanatory knowledge, not a trust shortcut into Signals or Assessments.

## Cursor Cloud specific instructions

Canonical branch is `v2/intelligence-os`. Do not commit to it directly.

Feature branches can fall behind later governance (expansion guide, `PROJECT-STATUS.md`, `AGENTS.md` pointer). Rebase onto `origin/v2/intelligence-os` before merge. Preserve the canonical expansion guide verbatim. Reconcile `TECHNICAL-DEBT-REGISTER.md` and `INTELLIGENCE-COVERAGE-MATRIX.md` — do not reopen resolved UI-lane items (TD-001..004) and do not replace evidence-class counts with withdrawn drafts that marked keyword-news as `NONE`.

### Local vs cloud runtime

Cloud agents do not automatically see an operator's local `inbox/` runtime. `inbox/` is gitignored. Drafts, discovered media, transcripts, and collection run artifacts exist only on the machine that created them unless they were copied into a snapshot or explicitly provisioned.

Do not assume cloud agents can replay a previous batch, open a local review-ready draft, or inspect Whisper output from another environment.

Secrets such as `PERPLEXITY_API_KEY` are unavailable in cloud unless explicitly provisioned for that environment. Never print or persist secrets.

### Python venv

The default Cloud Agent image has Python 3.12 but not `ensurepip`. `python3 -m venv .venv` fails on a from-scratch build until `python3.12-venv` is installed. `.cursor/environment.json` `install` does that with apt, then creates `.venv` and installs `requirements-dev.txt` plus `pagefind` / `pagefind_bin`. A `.venv` without working pip is deleted and recreated. Use `.venv/bin/python` rather than system Python. Do not drop the apt step.

### Trust gates

Publication review and Atomic Evidence review remain mandatory human gates. Haiku (`anthropic/claude-haiku-4-5`) may be used for **non-trusted** publication enrichment only. It is not extraction-qualified. Never auto-qualify a model and never fall back to an unqualified extractor.

Duplicate publish of an already-trusted publication id is not a 500: identical identity returns already-published success; conflicting identity returns a 409 review page and does not overwrite trusted data.

### Operating path

1. Discover: `python scripts/discover_media.py --source <source-id>` or `scripts/run_recent_batch.py`
2. Relevance screening is cheap metadata triage stored on the discovered item. Clearly irrelevant items should not be Whispered.
3. `scripts/process_discovered_media.py --item <id> --relevance-gate --enrich --max-tier 2` creates/reviews drafts without Whisper. `--max-tier 3` enables local speech-to-text.
4. Intelligence feed is `/work-queue` (Live Intelligence). The daily starting view is `/brief` (Morning Brief). Feed `Enter`/`o` opens the slide-over Reader when the V2 overlay is present; `/intelligence/{id}` remains the full reader. Pending cards can also be judged in the feed: `j`/`k` move, `a` promote, `s` keep/save, `r` dismiss/reject. Those actions POST the existing `/review/{id}/publish|save|reject` paths; they do not skip publication review. In `work_queue.html`, pending form fields live on `item.review_values` — do not use `item.values` (Jinja treats that as `dict.values`). Company/entity **Recent intelligence** uses the same reader in the live app; the public static snapshot still links trusted items to `/evidence/{id}` and never includes pending drafts. Advanced publication review remains `/review?kind=publication` and `/review/{id}`. Approve / Save / Reject have `+ Next` variants on the advanced form. AI suggestions are untrusted and visible with provenance. Feed ranking consumes stored `relevance_tier` (`adjacent` ranks below direct / unscreened spoken) and existing card `relevance_band` — do not invent a second relevance model.
5. `python scripts/collection_status.py` reports discovered / relevant / skipped / transcript-ready / enrichment-ready / publication-review-ready / trusted / extraction / atomic / retry / intervention counts.

`scripts/run_recent_batch.py` continues past per-item failures (YouTube anti-bot, missing captions, API errors). Do not treat one failed item as a batch abort. Do not report "0 failures" when transcript acquisition is blocked; review-ready without transcript is a valid state.

Standard lint/test/build commands remain those in `README.md`: `pytest`, `python scripts/validate_records.py`, `python scripts/build_static.py`.

GitHub Pages deploys from `.github/workflows/deploy-pages.yml` on push to `v2/intelligence-os` or `master`. Public URL: `https://samsonfive.github.io/berry-intelligence-os/`. The static Scanner is a trusted published snapshot; it never includes `inbox/` drafts, untrusted enrichment, or the local review workbench.

Remote interactive review (Scanner, publication review, Approve/Save/Reject) is the Docker deployment in `deploy/`, documented in `docs/07-static-deployment/REMOTE-INTERACTIVE-DEMO.md`. It uses `BIOS_REMOTE_INTERACTIVE` plus **application-session login at `/login`**. Browser HTTP Basic Auth is **not** the default UX. `BIOS_SESSION_SECRET` is required in remote session mode (must not be the review password). `BIOS_BASIC_AUTH` remains optional/emergency only and must stay off in front of `/login`. Do not expose an unauthenticated localhost app. Do not commit `demo-runtime/` or `deploy/.env`.

In this Cloud Agent VM, `docker` usually needs `sudo` (the `ubuntu` user is not in the `docker` group). Host port 8000 is often already taken by a leftover local uvicorn; set `BIOS_APP_PORT` (for example `18000`) instead of killing that process by name. VPS compose binds the app to `127.0.0.1` by default so Docker does not publish 8000 on the public interface. `docker compose config` interpolates `BIOS_REVIEW_PASSWORD` and `BIOS_SESSION_SECRET` into rendered YAML — do not paste that output.

Remote interactive login is `GET /login`. Unauthenticated `/work-queue` redirects there. The session cookie is Secure only when the request is HTTPS or `X-Forwarded-Proto: https` (Caddy does this). Do not enable `BIOS_BASIC_AUTH` in front of `/login`. Remote interactive mode fails closed without `BIOS_REVIEW_USERNAME`, `BIOS_REVIEW_PASSWORD`, and `BIOS_SESSION_SECRET`.

### V2 shell (approved)

V2 product direction is **approved**. Do not reopen AppShell, context bar, Compact vs Grid, ReaderOffcanvas, or Company Profile.

Migrated V2 surfaces: Morning Brief, Live Intelligence Grid/Compact, ReaderOffcanvas, Signal Review, Company Profile, Pending Review (`/pending`), Reading Queue, Assessments, **Monitor** — Watches + Alerts (`/queues/monitoring`), Source Health (`/sources`), **Variety Intelligence** (`/entities/variety`, `/entities/variety/{id}`, `?view=compete`, `?view=observations`), **Global Intelligence Search** (`#v2SearchOffcanvas`, `/search`, `/api/search/global`), **Claim Testing** (`/queues/testing`, `/queues/testing/{id}`), **Commercial Positions** (`/queues/commercial_position`).

Do **not** migrate Landscape, Sources inventory-config admin, or admin/system except global regression fixes. Landscape waits until Trade / Retail / Registry workstreams in `docs/v2/INTELLIGENCE-EXPANSION-BUILD-GUIDE.md` settle (Workstreams D, E, G, H). Stop after Commercial Positions V2: do not begin Landscape, AI/RAG/vector search, a Trade/Weather UI, Learner Mode, or admin in the same change. You may link Landscape ↔ Varieties; do not redesign Landscape.

**Claim Testing ≠ Learner Mode.** `/queues/testing` verifies concrete source claims on tagged published Evidence (`priority.testing.level != none`) with analyst dispositions in `inbox/analyst_queue_state.json` (`needs_testing` / `pass` / `fail` / `defer`). A Claim is not a Fact; Pass is not a Fact; reprints clustered by `source_independence` are not independent corroboration. Supporting vs contradicting Evidence is only what stored `evidence_links` already record — do not invent counts. Trial/geography/variety scope on the record must not be presented as a universal trait. Reuse ReaderOffcanvas and Company / Variety / Geography profiles; do not duplicate them. Testing review state (dispositions, reviewer, history) must not leak into static/public output. Learner Mode (Workstream K) remains unbuilt explanatory knowledge — do not add glossary, agronomy lessons, or “Explain this” content here.

**Commercial Positions ≠ Position objects.** `/queues/commercial_position` is tagged published Evidence (`priority.commercial_position.level != none`), grouped by company for scanning. It is an intelligence inventory, not a queue and not a competitive score. Tag priority is not truth confidence. Facts, Signals, and Assessments stay labeled as themselves. Trade / commercial observations are context (`does_not_prove`, `berry_code_purity` stay visible). Do not invent a Position schema here. Position proposals remain Recommendation Accept/Edit/Reject. Link Claim Testing when the same Evidence is also testing-tagged; do not duplicate adjudication. Blackberry thinness is shown from stored tags, not filled. Static output is published-only (no proposed Signals, no `ai_proposed` Assessments).

**Watches are inventory / monitoring intent**, not Alerts and not KPI tiles. They answer what is being watched, why, what changed recently, and whether there is new actionable activity. Supported watch-match entity types remain `company`, `variety`, `geography`, `person` — do not invent types. Pause/remove/resume overlay `inbox/analyst_queue_state.json`; never mutate trusted Evidence `priority.*` to dequeue.

**Alerts are action.** Derive them from existing stores (proposed Signals, watch-matched Signal Candidates, new watch activity, failing/blocked Source Health). Do not create a parallel Watch/Alert intelligence store. Confirm/Dismiss on proposed Signals is the existing alert workflow and does not change Signal JSON status. A Watch never confirms a Signal. Alerts deep-link into existing decision surfaces (Pending, Signal Review, Reader, Assessment, Source Health) — do not duplicate those workflows inside Alerts.

**Source Health ≠ coverage/recall.** `/sources` is operational collection health (healthy / quiet / due / stale / failing / blocked / not configured for discovery). Quiet means a successful check found nothing new. Failing means collection errored. Blocked means publisher rejection. Manual means no discovery adapter. Never present source count, item volume, or health buckets as intelligence recall. The Coverage Matrix (`docs/v2/INTELLIGENCE-COVERAGE-MATRIX.md`) remains the authoritative maturity record. Source class chips come from existing `entity_types` / type metadata — do not hard-code recall-mission source ids.

Watch recent intelligence reuses `#v2ReaderOffcanvas` (`data-open-reader` / `[data-intel-card]`). Do not invent a Watch-specific article modal. Open Signal Candidates deep-link to `/signals/review` or `/signals/candidates/{id}`.

`/queues/monitoring` must not call `build_morning_brief`, `annotate_feed_semantics` / Story Thread grouping, or `list_discovered_items`. Source Health may scan discovered items for last-item dates; Watch/Alert pages use per-source discovery JSON only for failing/blocked alerts. `/queues/testing` and `/queues/commercial_position` must not call `build_morning_brief`, Story Thread grouping, Global Search indexing, `list_discovered_items`, `variety_footprint`, or relevance screening.

Bootstrap 5.3 is vendored at `app/static/vendor/bootstrap/` for offcanvas/collapse/grid conventions only. Do not import Mirbal, Mooli, or chart/calendar vendor bundles. Nav action counts use `.v2-count-action` (not purple inventory pills). Berry context is a selector, not a per-crop theme; unmigrated Landscape in Library still follows the selected berry (`/entities/berry` when Global). Desktop hamburger collapses the persistent sidebar into an accessible icon rail (`title` + `aria-label` + action counts); below 1100px it opens `#v2NavOffcanvas`.

Feed overlay is `#v2ReaderOffcanvas` and is shared with Company Recent Intelligence, Pending Review, Reading Queue, Watch recent intelligence, Variety recent intelligence / commercial observations, Global Search intelligence hits, Claim Testing, and Commercial Positions. Do not invent a Testing-specific article modal. `j`/`k` while it is open load adjacent `[data-intel-card]` items into the same pane. Escape closes it and returns focus to the triggering control. Compact is throughput mode (SOURCE · TIME / headline / metadata / marks; actions on hover, keyboard-current, or focus). Status marks and record type stay distinct: do not repeat `kind_label` in the compact footer. Do not invent a Variety-specific reader modal.

**Global Search is navigation, not a trust layer.** `#v2SearchOffcanvas` (click, `/`, Ctrl/Cmd+K) and `/search` group Companies / Varieties / Geographies / Sources / Intelligence / Story Threads / Signals / Assessments. Alias matches resolve to the canonical entity — do not create duplicate Company or Variety rows per alias. Result state must stay visible: Trusted, Pending, Story, Emerging signal, Confirmed signal, Assessment. Pending must never look trusted because it matched. Live `/api/search/global` may include inbox drafts and signal candidates when `include_private=1`; static/Pagefind search may only index published `data/` pages. Do not write a private/inbox search index into `generated/`. Do not call `build_morning_brief`, full Story Thread grouping of the published feed, `variety_footprint` per hit, or collection scans on the search path. Berry context prefers in-scope hits and keeps unmatched objects under **Also in Global** unless the analyst turns that off. Source hits go to Source Health (`/sources#source-{id}`), which is still collection health, not recall. Do not build embeddings, vector DB, RAG, or conversational Q&A in this surface.

Variety index uses one-pass `build_variety_indexes()` and must not call `variety_footprint` once per card. Detail may call `variety_footprint` once. `/entities/variety` must not call `build_morning_brief`, Story Thread grouping of the whole feed, or `list_discovered_items`. Global berry context filters the generic `/entities/variety` route; do not add berry-specific Variety routes. Commercial observations are Evidence (draft = pending review), never Facts. Aliases and commercial names belong on one Variety entity — do not create duplicate pages per alias. Breeder (`develops`), owner / rights holder (`owns`), licensee (`licenses`), and marketer (`markets`) stay distinct; do not flatten them to “Company.” Unnamed `variety_entity_id: null` is a first-class listing state (TD-022). IP∩observation overlap is currently empty (TD-023) — show that, do not hide it. The 18 UK Open Food Facts drafts live in gitignored `inbox/` and may be absent in Cloud Agent runtimes; do not fabricate them into `data/`.

Trade (`trade_observation`) and Weather (`weather_observation`) are Evidence drafts on the existing Evidence schema, not Facts and not V2 product surfaces. Do not persist derived trade/weather conclusions or auto-promote them to Signals. Raspberry/blackberry are not separable at HS-6 (TD-024); blueberry/cranberry share 081040. NASA POWER production regions are config centroids, not farm coordinates (TD-030/TD-037). Do not start a Trade/Weather UI.

Derived intelligence calculations must not silently run on unrelated synchronous page paths. Overlay `/api/intelligence/{id}/reader` skips Morning Brief entirely. HTML nav badges use cheap repository/state counts (`work_counts`, open pending, emerging candidate statuses, new-since-last-seen) plus the folder-signature `_NAV_WORK_CACHE`. Do **not** call `build_morning_brief` to paint nav badges. `/brief` stays `mode="full"`. `/pending` uses `mode="pending"` (pending ranking + story threads). `/queues/reading` may use `mode="nav"` for its own page buckets. Do not cache trust/review state beyond that signature; a publish/dismiss/read must recompute counts.

Active technical debt belongs in `docs/v2/TECHNICAL-DEBT-REGISTER.md`. Source or domain expansion updates `docs/v2/INTELLIGENCE-COVERAGE-MATRIX.md` with proven counts only — never fabricate coverage.

Pending Review is a **decision workspace**, not a Feed clone: Review now / Review soon / Adjacent / Likely ignore / Older backlog. Bulk dismiss requires explicit selection and never publishes or auto-rejects. Advanced publication form remains `/review?kind=publication`.

Reading state remains in `inbox/analyst_queue_state.json` and is independent of trust. Do not create another reading-state store.

Assessment is analyst interpretation of Facts. Signal ≠ Assessment. Signal Candidate ≠ Signal. Confirming a candidate does **not** create an Assessment. Berry scope is stored `market_ids` only; absent `market_ids` means undeclared / company-wide, not “every berry.” Do not infer berry from title, rationale, or company names, and do not hide unscoped Bottom Line rows.

### Analyst workspace

Nav purple pills (`.nav-action`) are **action counts** with a resolution workflow. Grey `.nav-inventory` figures are catalogs, not uncleared work.

Morning Brief (`/brief`) is the daily starting point after login. It ranks existing intelligence; it does not create a second store and does not mark items read or trusted when viewed. Last-seen lives in `inbox/analyst_queue_state.json` under `meta.brief` (`last_seen_at` plus a compact `source_states` snapshot used only to detect source failure/recovery). **New** (activity after last visit) and **Important** (high-value unresolved regardless of age) are separate sections.

Watch “Because” copy names the primary subject (title / alias / newsroom identity), not a co-mentioned company. Co-mentions use “mentions watched X”. Primary watch match ranks above mention match; a company primary watch ranks above a geography primary watch so Mexico/Canada headlines do not bury company-specific intelligence.

Pending drafts are triaged on `/pending` (and still summarized on `/brief#pending-triage`) into Review now / Review soon / Adjacent / Likely ignore / Older backlog using stored `relevance_tier`, berry-direct, reading priority, source `monitoring_priority`, primary subject, watch-match quality, recency, and duplicate-title warnings. This is not a second AI score. Untrusted entity suggestions come from `app/services/draft_attribution.py` (canonical name, aliases, legal names, newsroom `linked_competitor_ids`) and are not written onto trusted `entity_ids`. Dismiss uses `analyst_queue_state.json` `pending` and keeps the draft file; Reject/Promote/Save still POST the existing `/review/{id}` routes. Bulk dismiss requires explicit selection and never publishes or auto-rejects.

Related pending/current items may be presented as a **developing story / story thread** (`app/services/story_threads.py`, `/threads/{id}`). That is organizational grouping only — not a Fact, Assessment, Position, Signal, or trusted conclusion. There is no “trust thread” action. Membership is conservative (canonical URL, exact normalized title, stored `evidence_links` that are actually same-event, or same primary company/variety plus strong title/date evidence). Same-company mention is not enough. Generic patent-monitor “assignee already linked” corroboration does not merge unrelated filings with trade articles. Patents participate as generic Evidence when deterministic edges exist; do not add patent-specific UI. Dismiss redundant coverage uses the existing pending-dismiss path and preserves the file. Review Soon strip counts remain raw item counts; the bucket heading also shows distinct stories after compression.

| Surface | Count meaning | Resolution |
|---|---|---|
| Morning Brief | new-since-last + important unresolved this cycle | Reader → Mark read / Keep / Dismiss / Promote |
| Reading Queue | unread + saved items still to consume | Mark read / Keep / Dismiss / Promote. Show completed. Bulk mark visible top-priority unread/saved. Buckets: top / saved / adjacent / backlog. |
| Publication review | Review now pending drafts (action). Remaining pending is inventory. | existing Approve / Save / Reject; triage Dismiss keeps history |
| Claim testing | tagged evidence still `needs_testing` | Pass / Fail / Defer (Reopen from completed). This is claim verification, not `scripts/qualify_extraction_model.py`. |
| Watches | **active** monitors only (inventory, not a queue) | Pause (1d) / Remove watch / Resume. Stopped stays auditable. Recent intelligence opens ReaderOffcanvas. |
| Alerts "N new" | proposed signals not yet confirmed/dismissed (action). Other alert groups deep-link; they are not a second inbox. | Confirm / Dismiss on proposed Signals. Candidates → Signal Review. Activity → Reader. Failing sources → Source Health. Catalog at `/signals` is inventory. |
| Commercial positions | tagged evidence (inventory) | not a queue; no Clear. Company grouping is a view, not a Position object. Position proposals (Accept / Edit / Reject) are separate. |

Workflow state lives in `inbox/analyst_queue_state.json` (runtime, gitignored). Do not mutate trusted `data/evidence/*.json` `priority.*` fields to dequeue. Dismiss/Stop/Pass/Reject never delete source history. Reading state is independent of trust state.

Brief ranking is deterministic: direct > adjacent (stored `relevance_tier`), high reading priority, **primary** watch match (company ≫ variety ≫ geography; co-mentions are weaker and labeled “mention”), recency relative to last brief and calendar date, current `web_article` drafts, company/variety linkage, source `monitoring_priority`, unread vs already read. Do not invent an opaque AI score. Consume Claude’s article sources and source-health states; do not add ingestion adapters.

A larger object-model rewrite is still open: first-class Position objects do not exist; three monitoring concepts still coexist (evidence `priority.monitoring`, Source `monitoring_priority`, Signal `status`); model qualification stays in scripts. Do not flatten those into one object type without an explicit IA migration.

### Mutable runtime integrity

`inbox/` is runtime state; never solve cross-worktree visibility by committing
untrusted drafts. Production `data/` and `inbox/` must remain on persistent
mounts and be backed up before deployment. New acquisition pipelines must
register enabled/scheduled cadence and health state in
`data/configuration/collection_pipelines.json`, use the shared runtime lock,
and version idempotency state when acquisition meaning changes. Cross-pipeline
dedup may use deterministic identity only; never fuzzy-merge claims or trust.

Untrusted Signal candidates live in `inbox/signal_candidates/` (`app/services/signal_candidates.py`). Presentation is `app/services/signal_review.py`, Morning Brief **Emerging signals**, `/signals/review`, and `/signals/candidates/{id}`. Candidate identity is opaque: persist and route by the actual `id`, never by `(entity_id, pattern_type)`. Multiple live candidates may share a company and pattern after id fingerprinting. Consume `load_candidates`, `independence_report`, and `apply_review_decision`; do not regenerate candidates or rewrite confidence to improve triage metrics. `persist_candidates()` never overwrites a reviewed file — persist a human decision with `persist_reviewed_candidate`, which refuses to create a missing id. After generation, `archive_candidates_absent_from()` moves ids that are no longer in the generated set to `inbox/signal_candidate_audit/` so live Morning Brief / company / watch counts reflect the current set; prior decisions stay on the original id and are never copied onto a regenerated id. Stale `/signals/candidates/{id}` links return 410 when an audit record exists, otherwise 404. Evidence quality is a generic overlay. Prefer Claude’s calibrated candidate stamp: an explicit `evidence_quality` field when present, otherwise the spoken-media `does_not_prove` caveat from `signal_candidates.py`. Fall back to supporting Evidence `transcript.status` / spoken `media_format` only when the candidate was not stamped. Full vs Limited source evidence is not a podcast-only branch. Confirming a candidate does **not** write `data/signals/`. Static `build_static.py` must pass `include_signal_candidates=False`. Do not lock ranking copy to a frozen candidate count. Developing stories (`/threads/{id}`) are organizational only; they may support a Signal but are not Signals. There is no “trust thread” action. A confirmed Signal Candidate is not a trusted Signal and does not create an Assessment.
