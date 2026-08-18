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
4. Intelligence feed is `/work-queue`. Opening an item uses `/intelligence/{id}` (read → promote in place). Pending cards can also be judged in the feed: `j`/`k` move, `Enter`/`o` open the reader, `a` promote, `s` save, `r` reject. Those actions POST the existing `/review/{id}/publish|save|reject` paths; they do not skip publication review. In `work_queue.html`, pending form fields live on `item.review_values` — do not use `item.values` (Jinja treats that as `dict.values`). Company/entity **Recent intelligence** uses the same reader in the live app; the public static snapshot still links trusted items to `/evidence/{id}` and never includes pending drafts. Advanced publication review remains `/review?kind=publication` and `/review/{id}`. Approve / Save / Reject have `+ Next` variants on the advanced form. AI suggestions are untrusted and visible with provenance. Feed ranking consumes stored `relevance_tier` (`adjacent` ranks below direct / unscreened spoken) and existing card `relevance_band` — do not invent a second relevance model.
5. `python scripts/collection_status.py` reports discovered / relevant / skipped / transcript-ready / enrichment-ready / publication-review-ready / trusted / extraction / atomic / retry / intervention counts.

`scripts/run_recent_batch.py` continues past per-item failures (YouTube anti-bot, missing captions, API errors). Do not treat one failed item as a batch abort. Do not report "0 failures" when transcript acquisition is blocked; review-ready without transcript is a valid state.

Standard lint/test/build commands remain those in `README.md`: `pytest`, `python scripts/validate_records.py`, `python scripts/build_static.py`.

GitHub Pages deploys from `.github/workflows/deploy-pages.yml` on push to `v2/intelligence-os` or `master`. Public URL: `https://samsonfive.github.io/berry-intelligence-os/`. The static Scanner is a trusted published snapshot; it never includes `inbox/` drafts, untrusted enrichment, or the local review workbench.

Remote interactive review (Scanner, publication review, Approve/Save/Reject) is the Docker deployment in `deploy/`, documented in `docs/07-static-deployment/REMOTE-INTERACTIVE-DEMO.md`. It uses `BIOS_REMOTE_INTERACTIVE` plus **application-session login at `/login`**. Browser HTTP Basic Auth is **not** the default UX. `BIOS_SESSION_SECRET` is required in remote session mode (must not be the review password). `BIOS_BASIC_AUTH` remains optional/emergency only and must stay off in front of `/login`. Do not expose an unauthenticated localhost app. Do not commit `demo-runtime/` or `deploy/.env`.

In this Cloud Agent VM, `docker` usually needs `sudo` (the `ubuntu` user is not in the `docker` group). Host port 8000 is often already taken by a leftover local uvicorn; set `BIOS_APP_PORT` (for example `18000`) instead of killing that process by name. VPS compose binds the app to `127.0.0.1` by default so Docker does not publish 8000 on the public interface. `docker compose config` interpolates `BIOS_REVIEW_PASSWORD` and `BIOS_SESSION_SECRET` into rendered YAML — do not paste that output.

Remote interactive login is `GET /login`. Unauthenticated `/work-queue` redirects there. The session cookie is Secure only when the request is HTTPS or `X-Forwarded-Proto: https` (Caddy does this). Do not enable `BIOS_BASIC_AUTH` in front of `/login`. Remote interactive mode fails closed without `BIOS_REVIEW_USERNAME`, `BIOS_REVIEW_PASSWORD`, and `BIOS_SESSION_SECRET`.

Live VPS access for this product is the dedicated `cursor` account (groups `docker` and `biosdeploy`, passwordless sudo). Use `ssh -i ~/.ssh/bios_vps_cursor_deploy -o IdentitiesOnly=yes cursor@212.227.236.188`. Do not generate another deploy key unless that exact private key is proven not to match `/home/cursor/.ssh/authorized_keys`. Repo at `/opt/berry-intelligence-os` is `root:biosdeploy`; `git fetch`/`git merge` as `cursor` may need `sudo git` so `.git/objects` stays writable. Never disable Johnny/root, never commit `deploy/.env`, and never print session secrets or API keys. Compose: `sudo docker compose --env-file deploy/.env -f deploy/docker-compose.yml --profile tls up -d --build`. App stays on `127.0.0.1:8000`; Caddy owns 80/443.

### Queue and count semantics

Nav purple pills (`.nav-action`) are **action counts** with a resolution workflow. Grey `.nav-inventory` figures are catalogs, not uncleared work.

| Surface | Count meaning | Resolution |
|---|---|---|
| Reading Queue | unread + saved items still to consume | Mark read / Keep / Dismiss / Promote. Show completed. Bulk mark visible unread/saved. |
| Publication review | pending drafts + unvalidated auto-capture | existing Approve / Save / Reject |
| Claim testing | tagged evidence still `needs_testing` | Pass / Fail / Defer (Reopen from completed). This is claim verification, not `scripts/qualify_extraction_model.py`. |
| Watches | **active** monitors only | Pause (1d) / Snooze (7d) / Resume / Stop. Stopped stays auditable. |
| Signals "N new" | proposed signals not yet confirmed/dismissed | Confirm / Dismiss on the alert. Catalog at `/signals` is inventory. |
| Commercial positions | tagged evidence (inventory) | not a queue; no Clear. Position proposals (Accept / Edit / Reject) are separate. |

Workflow state lives in `inbox/analyst_queue_state.json` (runtime, gitignored). Do not mutate trusted `data/evidence/*.json` `priority.*` fields to dequeue. Dismiss/Stop/Pass/Reject never delete source history.

A larger navigation rewrite is still open: first-class Position objects do not exist; three monitoring concepts still coexist (evidence `priority.monitoring`, Source `monitoring_priority`, Signal `status`); model qualification stays in scripts. Do not flatten those into one object type without an explicit IA migration.
