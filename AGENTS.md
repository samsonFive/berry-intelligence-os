# Berry Intelligence OS

Local-first, evidence-based competitive intelligence for berry crops.

## Cursor Cloud specific instructions

Canonical branch is `v2/intelligence-os`. Do not commit to it directly.

### Local vs cloud runtime

Cloud agents do not automatically see an operator's local `inbox/` runtime. `inbox/` is gitignored. Drafts, discovered media, transcripts, and collection run artifacts exist only on the machine that created them unless they were copied into a snapshot or explicitly provisioned.

Do not assume cloud agents can replay a previous batch, open a local review-ready draft, or inspect Whisper output from another environment.

Secrets such as `PERPLEXITY_API_KEY` are unavailable in cloud unless explicitly provisioned for that environment. Never print or persist secrets.

### Trust gates

Publication review and Atomic Evidence review remain mandatory human gates. Haiku (`anthropic/claude-haiku-4-5`) may be used for **non-trusted** publication enrichment only. It is not extraction-qualified. Never auto-qualify a model and never fall back to an unqualified extractor.

Duplicate publish of an already-trusted publication id is not a 500: identical identity returns already-published success; conflicting identity returns a 409 review page and does not overwrite trusted data.

### Operating path

1. Discover: `python scripts/discover_media.py --source <source-id>` or `scripts/run_recent_batch.py`
2. Relevance screening is cheap metadata triage stored on the discovered item. Clearly irrelevant items should not be Whispered.
3. `scripts/process_discovered_media.py --item <id> --relevance-gate --enrich --max-tier 2` creates/reviews drafts without Whisper. `--max-tier 3` enables local speech-to-text.
4. Intelligence feed is `/work-queue`. The daily starting view is `/brief` (Morning Brief). Opening an item uses `/intelligence/{id}` (read → promote in place). Pending cards can also be judged in the feed: `j`/`k` move, `Enter`/`o` open the reader, `a` promote, `s` save, `r` reject. Those actions POST the existing `/review/{id}/publish|save|reject` paths; they do not skip publication review. In `work_queue.html`, pending form fields live on `item.review_values` — do not use `item.values` (Jinja treats that as `dict.values`). Company/entity **Recent intelligence** uses the same reader in the live app; the public static snapshot still links trusted items to `/evidence/{id}` and never includes pending drafts. Advanced publication review remains `/review?kind=publication` and `/review/{id}`. Approve / Save / Reject have `+ Next` variants on the advanced form. AI suggestions are untrusted and visible with provenance. Feed ranking consumes stored `relevance_tier` (`adjacent` ranks below direct / unscreened spoken) and existing card `relevance_band` — do not invent a second relevance model.
5. `python scripts/collection_status.py` reports discovered / relevant / skipped / transcript-ready / enrichment-ready / publication-review-ready / trusted / extraction / atomic / retry / intervention counts.

`scripts/run_recent_batch.py` continues past per-item failures (YouTube anti-bot, missing captions, API errors). Do not treat one failed item as a batch abort. Do not report "0 failures" when transcript acquisition is blocked; review-ready without transcript is a valid state.

Standard lint/test/build commands remain those in `README.md`: `pytest`, `python scripts/validate_records.py`, `python scripts/build_static.py`.

GitHub Pages deploys from `.github/workflows/deploy-pages.yml` on push to `v2/intelligence-os` or `master`. Public URL: `https://samsonfive.github.io/berry-intelligence-os/`. The static Scanner is a trusted published snapshot; it never includes `inbox/` drafts, untrusted enrichment, or the local review workbench.

Remote interactive review (Scanner, publication review, Approve/Save/Reject) is the Docker deployment in `deploy/`, documented in `docs/07-static-deployment/REMOTE-INTERACTIVE-DEMO.md`. It uses `BIOS_REMOTE_INTERACTIVE` plus **application-session login at `/login`**. Browser HTTP Basic Auth is **not** the default UX. `BIOS_SESSION_SECRET` is required in remote session mode (must not be the review password). `BIOS_BASIC_AUTH` remains optional/emergency only and must stay off in front of `/login`. Do not expose an unauthenticated localhost app. Do not commit `demo-runtime/` or `deploy/.env`.

In this Cloud Agent VM, `docker` usually needs `sudo` (the `ubuntu` user is not in the `docker` group). Host port 8000 is often already taken by a leftover local uvicorn; set `BIOS_APP_PORT` (for example `18000`) instead of killing that process by name. VPS compose binds the app to `127.0.0.1` by default so Docker does not publish 8000 on the public interface. `docker compose config` interpolates `BIOS_REVIEW_PASSWORD` and `BIOS_SESSION_SECRET` into rendered YAML — do not paste that output.

Remote interactive login is `GET /login`. Unauthenticated `/work-queue` redirects there. The session cookie is Secure only when the request is HTTPS or `X-Forwarded-Proto: https` (Caddy does this). Do not enable `BIOS_BASIC_AUTH` in front of `/login`. Remote interactive mode fails closed without `BIOS_REVIEW_USERNAME`, `BIOS_REVIEW_PASSWORD`, and `BIOS_SESSION_SECRET`.

### Visual system

Do not begin a V2 reskin unless explicitly asked. Current-state audit: `docs/v2/UI-UX-V2-DESIGN-READINESS.md`. Landscape remains blueberry-hardcoded (`/landscapes/berries/blueberry` in nav and route). At `max-width: 834px` the sidebar is hidden with no replacement nav. The stack is FastAPI + Jinja + `app/static/app.css`; a React/Vue admin kit is not a drop-in.

### Analyst workspace

Nav purple pills (`.nav-action`) are **action counts** with a resolution workflow. Grey `.nav-inventory` figures are catalogs, not uncleared work.

Morning Brief (`/brief`) is the daily starting point after login. It ranks existing intelligence; it does not create a second store and does not mark items read or trusted when viewed. Last-seen lives in `inbox/analyst_queue_state.json` under `meta.brief` (`last_seen_at` plus a compact `source_states` snapshot used only to detect source failure/recovery). **New** (activity after last visit) and **Important** (high-value unresolved regardless of age) are separate sections.

Watch “Because” copy names the primary subject (title / alias / newsroom identity), not a co-mentioned company. Co-mentions use “mentions watched X”. Primary watch match ranks above mention match; a company primary watch ranks above a geography primary watch so Mexico/Canada headlines do not bury company-specific intelligence.

Pending drafts are triaged on `/brief#pending-triage` into Review now / Review soon / Adjacent / Likely ignore / Older backlog using stored `relevance_tier`, berry-direct, reading priority, source `monitoring_priority`, primary subject, watch-match quality, recency, and duplicate-title warnings. This is not a second AI score. Untrusted entity suggestions come from `app/services/draft_attribution.py` (canonical name, aliases, legal names, newsroom `linked_competitor_ids`) and are not written onto trusted `entity_ids`. Dismiss uses `analyst_queue_state.json` `pending` and keeps the draft file; Reject/Promote/Save still POST the existing `/review/{id}` routes. Bulk dismiss requires explicit selection and never publishes or auto-rejects.

Related pending/current items may be presented as a **developing story / story thread** (`app/services/story_threads.py`, `/threads/{id}`). That is organizational grouping only — not a Fact, Assessment, Position, Signal, or trusted conclusion. There is no “trust thread” action. Membership is conservative (canonical URL, exact normalized title, stored `evidence_links` that are actually same-event, or same primary company/variety plus strong title/date evidence). Same-company mention is not enough. Generic patent-monitor “assignee already linked” corroboration does not merge unrelated filings with trade articles. Patents participate as generic Evidence when deterministic edges exist; do not add patent-specific UI. Dismiss redundant coverage uses the existing pending-dismiss path and preserves the file. Review Soon strip counts remain raw item counts; the bucket heading also shows distinct stories after compression.

| Surface | Count meaning | Resolution |
|---|---|---|
| Morning Brief | new-since-last + important unresolved this cycle | Reader → Mark read / Keep / Dismiss / Promote |
| Reading Queue | unread + saved items still to consume | Mark read / Keep / Dismiss / Promote. Show completed. Bulk mark visible top-priority unread/saved. Buckets: top / saved / adjacent / backlog. |
| Publication review | Review now pending drafts (action). Remaining pending is inventory. | existing Approve / Save / Reject; triage Dismiss keeps history |
| Claim testing | tagged evidence still `needs_testing` | Pass / Fail / Defer (Reopen from completed). This is claim verification, not `scripts/qualify_extraction_model.py`. |
| Watches | **active** monitors only | Pause (1d) / Snooze (7d) / Resume / Stop. Stopped stays auditable. |
| Alerts "N new" | proposed signals not yet confirmed/dismissed | Confirm / Dismiss on the alert. Catalog at `/signals` is inventory. |
| Commercial positions | tagged evidence (inventory) | not a queue; no Clear. Position proposals (Accept / Edit / Reject) are separate. |

Workflow state lives in `inbox/analyst_queue_state.json` (runtime, gitignored). Do not mutate trusted `data/evidence/*.json` `priority.*` fields to dequeue. Dismiss/Stop/Pass/Reject never delete source history. Reading state is independent of trust state.

Brief ranking is deterministic: direct > adjacent (stored `relevance_tier`), high reading priority, **primary** watch match (company ≫ variety ≫ geography; co-mentions are weaker and labeled “mention”), recency relative to last brief and calendar date, current `web_article` drafts, company/variety linkage, source `monitoring_priority`, unread vs already read. Do not invent an opaque AI score. Consume Claude’s article sources and source-health states; do not add ingestion adapters.

A larger object-model rewrite is still open: first-class Position objects do not exist; three monitoring concepts still coexist (evidence `priority.monitoring`, Source `monitoring_priority`, Signal `status`); model qualification stays in scripts. Do not flatten those into one object type without an explicit IA migration.

Untrusted Signal candidates live in `inbox/signal_candidates/` (`app/services/signal_candidates.py`). Presentation is `app/services/signal_review.py`, Morning Brief **Emerging signals**, `/signals/review`, and `/signals/candidates/{id}`. Candidate identity is opaque: persist and route by the actual `id`, never by `(entity_id, pattern_type)`. Multiple live candidates may share a company and pattern after id fingerprinting. Consume `load_candidates`, `independence_report`, and `apply_review_decision`; do not regenerate candidates or rewrite confidence to improve triage metrics. `persist_candidates()` never overwrites a reviewed file — persist a human decision with `persist_reviewed_candidate`, which refuses to create a missing id. After generation, `archive_candidates_absent_from()` moves ids that are no longer in the generated set to `inbox/signal_candidate_audit/` so live Morning Brief / company / watch counts reflect the current set; prior decisions stay on the original id and are never copied onto a regenerated id. Stale `/signals/candidates/{id}` links return 410 when an audit record exists, otherwise 404. Evidence quality is a generic overlay. Prefer Claude’s calibrated candidate stamp: an explicit `evidence_quality` field when present, otherwise the spoken-media `does_not_prove` caveat from `signal_candidates.py`. Fall back to supporting Evidence `transcript.status` / spoken `media_format` only when the candidate was not stamped. Full vs Limited source evidence is not a podcast-only branch. Confirming a candidate does **not** write `data/signals/`. Static `build_static.py` must pass `include_signal_candidates=False`. Do not lock ranking copy to a frozen candidate count. Developing stories (`/threads/{id}`) are organizational only; they may support a Signal but are not Signals. There is no “trust thread” action. A confirmed Signal Candidate is not a trusted Signal and does not create an Assessment.
