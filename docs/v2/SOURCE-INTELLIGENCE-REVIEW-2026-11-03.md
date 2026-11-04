# Source intelligence continuation — implementation review

Status: undeployed candidate on `feature/source-intelligence-gap-v1`. No recurring lane or paid routing activation. This checkpoint does not close the full mission or the original failed retrieval-quality target.

## Inherited state verified

The live image exactly matches release #411 (`sha256:d8601b96c419977ad778cacac8abb62484c61b883622a6183b49adbca8882c66`), HTTPS health returns 200, the runtime registry contains 281 Sources and `BIOS_RESEARCH_CREDIT_FREE_ONLY=1`. The active timer still selects only `--pipeline news_workspace_refresh`. The independent Pages workflow 41789272772 succeeded at canonical `34eb23c3`. Private receipt: `inbox/search-quality-evaluation/inherited-state-verification.json`.

## Candidate behavior

- Default News admits existing podcast, video/conference-video and blog publications through the existing relevance, date, geography, berry, company, tag and trust gates. No discovery is performed by GET. Rejected/archived publications and saved-passage projections cannot masquerade as original feed publications.
- All / Articles / Blogs / Videos-webinars / Podcasts filtering retains scope in review-lane, pagination, tag, source-health and refresh navigation. Blog classification uses explicit publication type or actual blog path segments. Map discloses its narrower geography representation and retains the News return URL. Publisher options come from eligible scoped content.
- The News-linked health view separates global execution/freshness/lifecycle from current-filter contribution. It includes last attempt/success, latest dated discovery, retained discovery/publication counts, declared transcript states and specific selection exclusions. Corrupt runtime rows degrade visibly. No raw provider exception/request URL is rendered. Collection settings links to this view and permits explicit podcast/YouTube feed adapters without reinterpreting existing Sources.
- Spoken recording identity uses discovery/GUID lineage. Shared show homepages and advisory title matches cannot collapse distinct episodes. Legacy recording matches require exact URL, title, date and source together. Podcast audio actions use the publisher-declared enclosure while the original source URL stays intact.
- Selected private Reader loads existing normalized transcripts with lineage/version checks, shows timed segments and provenance, or explicitly displays recording descriptions. No automatic article fetch is triggered for spoken media. Workspace snapshots preserve content kind, transcript version and timing; repeated wording remains unresolved unless its exact position or unique archived wording supports a locator. Saving remains unreviewed.
- The dispatcher accepts repeated explicit pipeline selectors. Collection supports source allowlists and `--no-model-enrichment`. These are controls, not production activation. An explicit caption-job CLI persists queued/running/ready/partial/failed/deferred status with a 1–300-second timeout, one shared collection lease, no paid APIs, no audio download and no speech-to-text. GET never queues it.

## Real-source receipts and limits

A fresh isolated canary capped persistence at two items for each of five registered Sources. Business of Blueberries recovered October 30 and October 22 episodes; Fall Creek recovered October 6 and October 2 blog items. Separate GUIDs produced separate drafts despite identical show-homepage URLs. The sampled Blueberries TV, Chilean committee and Arkansas YouTube Atom endpoints all returned 404. No repair or fresh-video recall is claimed.

Two relevant retained production video discoveries were read without mutation and copied into the isolated canary: the August 21 Redagrícola interview and July 14 Blueberries Trujillo seminar recap. These test existing video visibility, not fresh collection. Production has one normalized transcript artifact; that raw count is not transcript quality or coverage. Receipts: `source-gap-canary.json`, `source-gap-inherited-media.json` under private `inbox/search-quality-evaluation/`.

One real podcast publisher-transcript attempt and one retained video caption attempt remained deferred. The podcast feed declares no transcript; YouTube returned a sign-in/anti-bot challenge. No cookies, challenge bypass, external speech service, model extraction, credit purchase or local STT was used. Caption inspection now retains a safe access-failure category rather than losing it in a generic fallback. Private `source-gap-caption-attempt.json` and `.log` retain the actual attempt and latency. Metadata/description fallback is usable; real podcast **and** video transcription/quality acceptance remains open.

Initial browser review confirms real podcast cards, distinct declared audio URLs and the shared Reader's description-only fallback. Additional final-head UI/HTTP checks, exact-head Linux CI and bounded offline preservation must be recorded before release review is ready. Local focused checks currently include 49 feed/scheduler/identity/capture tests, four onboarding checks and 84 transcription/caption portability checks. Windows TestClient route checks are reserved for the required full Linux suite; those tests are not waived.

## Proposed activation for separate review

Keep the present production selector until approval. First propose only `news_workspace_refresh` plus a bounded spoken-media lane whose runner uses `--source-allowlist source-business-of-blueberries-podcast --skip-transcription --max-transcriptions 0 --max-items 2 --max-discoveries 2 --no-model-enrichment --json-summary`. Retain the existing daily/source cadence and shared lock. A separately approved article lane can start with Fall Creek only under the same item/discovery limits and deterministic enrichment. Do not enable all registry lanes or all Sources.

Before activation, require a bounded manual production canary, verified due decisions, stable GUID dedup on a second run, backlog/draft yield review and a rollback to the prior selector. Transcription stays manual, caption-only and time-limited until a separate recording-length/CPU/memory/disk/model budget is reviewed. No proposed recurring job has been activated.

## Remaining acceptance gates

Full exact-head CI, validation/static-private checks and production-copy preservation are pending. Fresh video feed repair, real timed transcript quality and capture/reopen proof for both media classes, accessible-page Reader navigation, provider allowance/auth checks, representative sealed analyst-outcome evaluation and the broader source/variety ledger remain open. Existing failed Google comparisons, identity holds and canonical trait/right/footprint review gates remain unchanged. Existing Exa credential presence is not verified allowance; no provider trial is activated from an unknown balance.

Private runtime data, transcripts, account databases, snapshots and receipts stay outside git/static output. The user's existing untracked report-preview image is preserved. Review code release and recurring activation separately; neither is authorized by this checkpoint.
