# Berry Intelligence OS

Local-first, evidence-based competitive intelligence for berry crops.

## Cursor Cloud specific instructions

Canonical branch is `v2/intelligence-os`. Do not commit to it directly.

Publication review and Atomic Evidence review remain mandatory human gates. Haiku (`anthropic/claude-haiku-4-5`) may be used for **non-trusted** publication enrichment only. It is not extraction-qualified. Never auto-qualify a model and never fall back to an unqualified extractor.

Duplicate publish of an already-trusted publication id is not a 500: identical identity returns already-published success; conflicting identity returns a 409 review page and does not overwrite trusted data.

Operational throughput path for recent spoken-word items:

1. `python scripts/discover_media.py --source <source-id>` (or `scripts/run_recent_batch.py`)
2. Relevance screening is cheap metadata triage stored on the discovered item. Clearly irrelevant items should not be Whispered.
3. `scripts/process_discovered_media.py --item <id> --relevance-gate --enrich --max-tier 2` creates/reviews drafts without Whisper. `--max-tier 3` enables local speech-to-text.
4. Human publication review is at `/review`. Approve / Save / Reject have `+ Next` variants. AI suggestions are untrusted and visible with provenance.
5. `python scripts/collection_status.py` reports discovered / relevant / skipped / transcript-ready / enrichment-ready / publication-review-ready / trusted / extraction / atomic / retry / intervention counts.

`scripts/run_recent_batch.py` continues past per-item failures (YouTube anti-bot, missing captions, API errors). Do not treat one failed item as a batch abort.

Standard lint/test/build commands remain those in `README.md` / `package` scripts: `pytest`, `python scripts/validate_records.py`, `python scripts/build_static.py`.
