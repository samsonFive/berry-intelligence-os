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
4. Scanner is `/work-queue`. Publication review is `/review?kind=publication`. Approve / Save / Reject have `+ Next` variants. AI suggestions are untrusted and visible with provenance.
5. `python scripts/collection_status.py` reports discovered / relevant / skipped / transcript-ready / enrichment-ready / publication-review-ready / trusted / extraction / atomic / retry / intervention counts.

`scripts/run_recent_batch.py` continues past per-item failures (YouTube anti-bot, missing captions, API errors). Do not treat one failed item as a batch abort. Do not report "0 failures" when transcript acquisition is blocked; review-ready without transcript is a valid state.

Plant-patent monitoring is a separate bounded collector, not part of `scripts/run_collection.py` (that runner is RSS/media discovery). Command: `python scripts/monitor_plant_patents.py`. Watchlist: `data/configuration/patent_watchlist.json`. State lives in gitignored `inbox/operations/patent_monitor/state.json`. Drafts go to `inbox/evidence/ev-patent-*.json` and use the existing `/review` Approve / Save / Reject gate.

Do not publish patent drafts as trusted intelligence automatically. `verification_state` stays `unverified` and `evidence_links[].status` stays `proposed` until a human decides. `source_authority=high` on a USPTO filing is not commercialization confidence (`information_confidence` remains `unknown` at ingest). Inventors are never auto-created as Entities.

Preferred discovery is USPTO Open Data Portal when `BIOS_USPTO_ODP_API_KEY` is set. Without a key, the monitor uses Google Patents public JSON search (`/xhr/query`). Google frequently returns HTTP 503; per-query failures are isolated and must not abort the run. Do not scrape LinkedIn or Patent Public Search HTML as a workaround.

Standard lint/test/build commands remain those in `README.md`: `pytest`, `python scripts/validate_records.py`, `python scripts/build_static.py`.

GitHub Pages deploys from `.github/workflows/deploy-pages.yml` on push to `v2/intelligence-os` or `master`. Public URL: `https://samsonfive.github.io/berry-intelligence-os/`. The static Scanner is a trusted published snapshot; it never includes `inbox/` drafts, untrusted enrichment, or the local review workbench.
