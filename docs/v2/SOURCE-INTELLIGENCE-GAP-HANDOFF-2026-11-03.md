# Source intelligence gap — handoff and completion mission

User direction recorded November 3, 2026 (Pacific): assess and deploy what is ready, then hand off all unresolved work from the search/research mission and subsequent prompts. The user authorizes a scoped release of ready work; this does not approve untested media changes, paid purchases, automatic trust promotion, or a claim that search-quality acceptance passed.

## Start here

- Repository: `berry-intelligence-os-search-research-quality` in the shared `sscanar` workspace.
- Tested release candidate: `453097a40bb783cb73eafaf3931485d075935ba2`, PR [#411](https://github.com/samsonFive/berry-intelligence-os/pull/411).
- Exact-head [CI run 41750926715](https://github.com/samsonFive/berry-intelligence-os/actions/runs/41750926715): all four required checks passed; 6,609 tests passed, 11 skipped, two warnings.
- Read `AGENTS.md`, the canonical expansion build guide, debt register and coverage matrix. Do not rewrite the build guide or discard previous release histories.
- The local checkout is now `docs/source-intelligence-gap-handoff-20261103`, a documentation-only child of the merged release. These handoff documents are saved locally, not published as a second implementation release. Start follow-up code on an appropriate new feature branch from reconciled canonical; do not mistake this documentation head for the CI-tested candidate.
- Deployment result and preservation receipts: [verified interactive release #411](SEARCH-RESEARCH-RELEASE-411-2026-11-03.md), canonical merge `34eb23c3`. Do not infer deployed state from a merge, local preview, or candidate SHA alone.
- First release follow-up: inspect [GitHub Pages run 41789272772](https://github.com/samsonFive/berry-intelligence-os/actions/runs/41789272772). It was still running its independent full build/test workflow when the handoff was prepared. Interactive deployment is verified; static snapshot completion is not yet claimed. Diagnose a failure rather than rerunning or declaring success blindly.
- Private review packet: `inbox/search-quality-evaluation/mission-credit-free-final-review-2026-11-03.html` and its linked JSON. Preserve failed scores and frozen seals.
- Local preview: `http://127.0.0.1:8148`. Its data and inbox are isolated copies, not production. Do not upload that inbox as a release.
- An untested early mixed-media patch is preserved at `inbox/search-quality-evaluation/mixed-media-feed-wip.patch`. It changes three files only, has no health UI or real-item proof, and is NOT part of the tested candidate. Inspect before applying; it is a starting point, not an accepted implementation.
- Preserve the user's pre-existing untracked `artifacts/search-research-quality/report-preview.png`.

## Objective

Deliver one coherent source-to-intelligence experience across articles, industry blogs, videos, podcasts, conference recordings, breeder/company sources, scientific publications and registries. An analyst must see relevant recovered items in the main feed, understand missing coverage and content limitations, read/watch/listen, capture attributed excerpts, and follow items through review without mistaking metadata, provider snippets, transcripts or AI summaries for verified facts.

Search engines are discovery providers, not competing product destinations or original publishers. The user wants sources brought into the existing app/newsreader, without requiring a browser extension. No provider subscription or credit purchase is authorized. Use existing credentials only within verified allowances and explicit bounded jobs; do not silently spend from an unknown balance.

## Verified production audit before the release

Read-only audit on November 3 Pacific / November 4 UTC:

| Inventory | Observed |
| --- | --- |
| Registered sources | 278 |
| No discovery adapter | 185 (includes legitimate manual/reference entries) |
| Podcast feeds / YouTube feed sources | 8 / 4 |
| Article RSS / news-search RSS / sitemap sources | 35 / 35 / 6 |
| Discovered items | 4,427: 3,386 articles, 972 podcasts, 69 videos |
| Pending evidence files | 1,753: 1,622 articles, 18 podcasts, 10 videos, 103 without `media_format` |
| Accounts | johnny, Chris.H, Duncan.M, Julio.A, News_Viewer; all enabled |
| Provider environment presence | Exa, APITube, Perplexity and Firecrawl present; presence does not prove valid auth, remaining credit or invocation |

These are raw inventory counts, not unique events, relevant items, transcript-ready items, current items or trusted publications. No malformed files were encountered in that count. Local candidate source inventory differs: 281 registered, 95 collection-eligible, 182 without discovery configuration. Reconcile against fresh production after release; do not silently replace one denominator with the other.

Additional handoff probes (private receipts `inbox/search-quality-evaluation/media-production-handoff-audit.json` and `source-canary-handoff.json`): most podcast Sources' last successful collection was August 26; all four video Sources have failing/retryable state with last successes August 22. One uncadenced source is labelled CURRENT by existing semantics, which does not establish current items. All 28 spoken-media drafts lack an explicit `transcript.status` field; this is an unspecified state, not proof that no separate transcript artifact exists. The host's `bios-collection.timer` is active on a roughly 15-minute dispatcher; an active timer alone is demonstrably insufficient evidence of fresh spoken-media collection.

**Verified scheduling root cause:** the systemd service's `BIOS_COLLECTION_OPERATIONS_ARGS` selects `--pipeline news_workspace_refresh`. This overrides the broad enabled/scheduled registry: its routine dispatcher does not execute `article_news`, `spoken_media` or other lanes. The inspected production pipeline receipt folder has 0 spoken-media runs, 13 article-news runs (latest August 25), and 3,866 News-refresh runs (latest November 4 UTC, PARTIAL with one failure). The wrapper itself invokes `scripts/run_due_pipelines.py`; the narrowing is in the service environment. Receipt: `inbox/search-quality-evaluation/scheduler-handoff-audit.txt`. Retain the selector during the code-only release; changing it to all pipelines could unexpectedly activate paid/large jobs and overflow review. The next mission must propose and test an explicit safe lane allowlist, bounded source canaries and transcript budget before activation.

A bounded isolated local canary (three items per source, no paid calls/transcription/production mutation) recovered October 14, 22 and 30 Business of Blueberries episodes, and September 11 / October 2 / October 6 Fall Creek blog items. The existing Blueberries TV YouTube Atom URL returned HTTP 404. Do not call that video collector repaired. Podcast normalization also returned the same show-homepage `canonical_url` for all three distinct GUID-identified episodes. Investigate valid episode permalinks/enclosures and prevent URL-only downstream dedup from merging distinct episodes into one show; never invent an episode URL. These probes establish collection failures and a concrete identity risk, not feed integration success.

Corrections to earlier chat claims: Exa already has a labelled entry in local `keysz.txt` and is configured in production. Statements that a new key/account was required were premature. News_Viewer is already present in production; do not reset its password or create a duplicate.

## Diagnosed disconnects

1. Default `/today` calls `app/news_workspace_routes.py::news_page`, not the older `intelligence_feed` surface. `news_workspace.model` admits collected `web_article` records but excludes discovered podcasts/videos and legacy `industry_podcast` records. Published/pending sources reach the shared corpus through `personal_digest_routes.world` and `personal_digest.source_records`, then disappear at that selection gate. Do not repair only `/today?view=legacy`.
2. News refresh explicitly passes `enable_perplexity=False`, `enable_exa=False`, `enable_apitube=False`. Keys alone do not activate that lane. Broad metadata discovery is not a substitute for polling configured podcast/channel/blog feeds.
3. Generic media discovery/orchestration already exists. Reuse `media_discovery`, `media_orchestration`, `media_transcription`, source lifecycle/cadence/freshness, pipeline locks and status stores. Do not build a second intake queue or fabricate draft files outside their contracts.
4. Source configuration and runtime discovery health are different. Enabled/scheduled JSON does not establish a successful production timer run. Some manual references intentionally have no collector. Show that distinction.
5. Spoken-media scheduler configuration deliberately skips transcription. Initial spoken discovery is bounded (normally recent window/item cap); YouTube Atom feeds expose a limited recent window. Caption failures/anti-bot responses and untranscribed metadata must remain visible.
6. Blogs are unevenly covered. Existing examples include UF IFAS, UF blueberry breeding and Fall Creek; some industry newsletters are reference-only. The current specialist catalog is bounded and distinct from the complete source registry. Do not assume every registered source is included in News refresh.

## Work packages, in order

### A. Finish the mixed-media main feed

Extend the existing model and cards, retaining relevance, dates, berry/company/region/tag scope, read/saved state, review distinctions and pagination. Include articles, blogs, podcasts, video and conference video. Preserve format through metadata previews. Add an accessible All / Articles / Blogs / Videos-webinars / Podcasts filter. Define blog classification explicitly from reliable source metadata or actual publication paths; never classify the provider as the publisher or call every company page a blog.

Preserve media scope in all navigation that claims to retain feed scope: review lanes, pagination, tag links, source links, refresh, saved return and Map handoff. If Map cannot represent media, disclose that limitation and preserve the return URL rather than claiming identical scope. Existing source/publisher choices should not offer unrelated inventory as matching content.

Show a useful card without a transcript: original title/date, publisher, description, format, play/open-source link, and `description only` or actual transcript availability. Do not call a description an excerpt from the recording. Support the existing Reader with meaningful watch/listen/original actions and clear fallback. Do not require iframe playback when the publisher disallows it. Do not let an absent transcript hide the discovery.

Acceptance: real registered-source items from each supported format appear on default `/today` and the corresponding filter; unrelated software/medical/general-agriculture false positives remain excluded; trusted lane still requires its existing reviewed evidence support. Test date/region/berry/tag combinations, missing dates, archived/rejected drafts, duplicates, pagination and scope retention. Page load is read-only and makes zero network/model requests.

### B. Collection and source-health visibility

Surface source health from the main feed and collection settings, reusing current lifecycle, freshness and execution status services and `/sources`, `/collection-ops`, `/review-ops` where appropriate. For each source show configured format/adapter, enabled/reference/retired/operator-blocked state, cadence, last attempt, last useful/full success as applicable, latest recovered publication date/title, item/draft/transcript yield, and its feed contribution.

Explain missing contribution with inspectable reasons: never run, no adapter, quiet, stale, fetch failure, blocked, irrelevant, outside date/scope, pending draft not created, missing transcript, duplicate or rejected. Global source health and current-filter contribution must be labelled separately. Do not equate zero visible items with collector failure or a successful fetch with complete recall. Corrupt runtime records should degrade visibly without making all health rows fail. Never display credentials or token-bearing request URLs/errors.

Reconcile the 278-source production registry with the candidate registry and source universe. Audit the high-value missing blogger/newsletter/company/breeder, podcast, seminar and channel sources using verified public feeds or sitemaps. Reuse adapters; do not auto-onboard every discovered website. Record explicitly deferred/rejected sources and access restrictions. Audit registered-but-unused providers and per-feature routing, including Exa, APITube, Firecrawl and NewsCatcher, without assuming validity from a key.

Source onboarding also needs work: the current Add Source menu offers RSS/Atom, Google News terms and manual reference. A new generic RSS source defaults to `article_rss`, so it cannot explicitly create a podcast/YouTube collector from that UI. Existing adapter identity is retained on edits. Add a clear publication-format/adapter choice and verified channel/playlist/podcast feed handling, with relevant language/berry/region guidance, without silently reinterpreting existing sources or weakening URL validation.

### C. Reliable bounded media collection and transcription

Verify actual production timers, due decisions, locks, failure isolation and persistence, with a bounded manual run before changing cadence. Avoid flooding the existing review backlog. Establish discovery-to-draft conversion and exact identity dedup across media/news paths. Preserve human decisions and source history. Metadata should become visible without waiting for speech-to-text.

Transcription order: existing valid transcript; legitimate publisher transcript; available platform captions; local speech-to-text only when enabled and resource-budgeted. Respect blocked pages, unavailable captions, copyright/access restrictions, languages and recording length. Never bypass platform challenges or pretend description text is speech.

Add/verify durable queued/running/ready/partial/failed/deferred states, restart-safe retries, language/model provenance, timestamps/speaker/context where supported, time-based excerpt locators, and bounded CPU/memory/disk/time use. Produce one real podcast and one real video transcript with quality inspection where access permits; otherwise name the exact blocker and prove metadata/description fallback without claiming completion. Keep raw audio, private transcripts and runtime state outside git/static output. Source transcription does not qualify an LLM extractor or approve any claim.

### D. Research Reader and excerpt capture

The requested no-extension Research Reader is a proposal, not implemented. Extend the existing newsreader for accessible recovered URLs: clean attributed text, headings/tables, original link, back/forward link navigation, pop-out/expanded presentation, highlight/save, notes and variety/company/workspace/report destinations. Retain source version/hash, locator, capture date and distinction between page text, description, transcript, translated text and analyst notes. Reopen and locate the saved passage after restart; repeated saves must remain idempotent.

Reader/accessibility extraction does not bypass cross-origin restrictions or grant access to Google/other tabs. Full-web search wrapping is unresolved. Google Programmable Search is now restricted for new engines; do not promise ordinary Google inside an iframe. Exa/other supported APIs can populate our own result/reader UI. No extension or desktop-app installation has been requested. Do not proxy logged-in pages or bypass framing/paywall/access restrictions.

### E. Provider and retrieval quality

Exa public preview was tested on `blackberry floricane Ervin` and `blackberry floricane Mediterranean trial`; the latter led to a verified University of Lisbon abstract, handle `10400.5/3903`, describing trials and southwest Alentejo. Brave found Ervin but struggled with the regional query and initially changed `trial` to `trail`. These are exploratory spot checks, not a blind superiority result. Exa's advertised free allowance is not a verified balance on this existing account. Its adapter exists; audit auth/allowance, bounded routing, cost limits and capture provenance before in-app activation. Never embed or automate an undocumented public demo backend as production access.

Retain `BIOS_RESEARCH_CREDIT_FREE_ONLY=1` as the paid Perplexity research guard until deliberately changed. It is not a blanket guarantee that all other features/providers are free. Mwmbl/scientific/news/primary discovery and the private cross-query source cache remain available; respect their limits. The 161-source root and 20-source preview cache migrations were logically idempotent; production cache migration is not established by local execution. No evaluation/Google pool may seed application results.

The original measured quality mission remains NOT MET. Preserve both frozen comparisons:

| Cohort | App direct P@10 bounds | Google bounds | Dispositions |
| --- | --- | --- | --- |
| 24 queries, frozen `5d41cb5f` | 15.8–24.2% | 25.8–55.8% | 294 graded, 92 unassessable / 386 pairs |
| Six fresh queries, frozen `4420549e` | 5.0–8.3% | 18.3–53.3% | 55 graded, 23 unassessable / 78 pairs |

All packets have dispositions; inaccessible/metadata-only cases remain unassessable, not irrelevant. Final-code offline replay preserved the six new lists; it was not a new live blind run. Same-operator masked review is not independent human certification. Zero empty lists does not prove every query was answered. Final replay: 52 mechanically faithful quotations and seven saved-demo quote/context checks; this does not certify the semantic truth of every citation. Continue semantic verification where source access/context is incomplete.

All five previously credit-affected searches were re-executed with free sources, but exact Spain nursery/anthracnose and date-restricted greenhouse questions remained weak, and the claimed ABB Kenya licence remained unestablished. Do not infer the licence from membership or conclude absence from missing public evidence. Primary Fontana and Hudson River/Plantik announcements were recovered in consumed-case follow-ups, not new blind wins. Keep source access/partial text, old-versus-new development dates, geography and source-independence gaps explicit.

The user proposed changing the product goal from beating Google to integrating useful discovery providers. Define a new representative, sealed mixed-media/source-to-report evaluation and report it alongside the original failed target; do not retroactively relabel failure as success. Test multilingual Polish/Portuguese and historic backfill with real accessible examples, and measure time to useful evidence, relevant unique developments, quote fidelity, scope, attribution, latency and paid/free calls. Keep original cohorts untouched.

### F. Remaining variety and thread coverage

- Pending source details: 75 profiles / 261 attributed rows; 69 source-reported, three limited, three identity holds. These are not approved canonical traits. Candidate catalog: 504 records, only 31 with structured canonical traits; 473 lack them. Continue breeder/technical-sheet, trial/conditions, awards, news and patent/PVR depth. Audit missing information against original breeder sources, retaining conflicting performance statements and geography/time context.
- BK 6-13, Twilight and Zara remain held identities. User authorized promotion only for clear source-backed identities. Do not force aliases, ambiguous codes or queue-wide promotion. Clarify source-backed canonical identity versus approved traits/rights/growing footprints.
- Ervin introduction and later international licensing are separate events; source yield descriptions differ. Keep both attributed. Licensing does not establish sales or growing acreage everywhere.
- Confirm production availability of the released collection/default/language/backfill features and seeded pending profile imports. Startup sync is additive; existing runtime rows may intentionally diverge. Explicit promotion must follow the verified-backup/three-way contract; never replace production data from the worktree.
- Existing Keyword Monitoring CRUD, berry/region/language options, date/region repairs, historical backfill, variety full-text/source search, embedded entity research, breadcrumbs, alphabetical navigation, resizable/reorderable/remembered columns, recent-intelligence filter/sort, example exclusion and recoverable removal were implemented in the tested candidate. Regress them, do not list them as newly completed by this handoff.
- Verify saved analyst state across sessions/accounts and source-reader capture usability for the newly added formats. Broad claims that every variety has complete awards/news/patent information remain unproven.
- Browser follow-up: replacing the collection search text temporarily triggered the selection-to-Learn/workspace toolbars for the input's old word. Escape cleared them, and nothing was saved. Excerpt-selection controls should ignore text inputs/textarea/editable controls; include this regression in the new capture/reader work.
- News_Viewer is enabled in production, and an actual browser sign-in with the previously supplied credential succeeded during handoff preparation, landing on its first-login Guide. No password was changed or duplicate account created. Preserve all five existing accounts, onboarding timestamps and each analyst's private state.
- Original pre-change failure trace was not recovered as a historical production trace; old-app replay is a diagnostic reconstruction. Retain that limitation. Progressive results/event grouping have bounded implementation proofs, not exhaustive event recall or source independence certification.
- Perplexity's monthly credit refresh date and replenished balance were never verified. Do not promise a reset date, buy credits or make paid retries. The existing Exa key and its actual allowance must be checked before proposing new accounts. The current handoff does not request funding.

## Release and review gates

Before shipping any follow-up: focused meaningful tests, record validation, static-private leakage checks, real local browser review, and all four required GitHub checks on its exact final head. Never omit slow/full Linux tests because local Windows TestClient checks hang. Reconcile current canonical and preserve the guide verbatim.

Use the repository's `package_release_candidate.py` and `run_bounded_rehearsal.py`, a fresh verified private runtime backup/copy, no rehearsal network, one job, 1GiB/one-CPU limits, existing host headroom gate, account/database/settings/JSON preservation and retained rollback image/override. Do not stop an unrelated container, weaken auth, raise resource caps or erase release backups to pass a gate. Deployment can preserve old data while adding new seed records; report additions explicitly. Production activation of new recurring collection/transcription or paid routing needs a concrete bounded plan and remains separate from a code-only release.

## Definition of done for the next mission

1. Real articles, blogs, podcasts and videos flow from configured collectors to default feed and Reader with scope/media filters and no hidden format exclusion.
2. An analyst can explain why every sampled source has or lacks visible items, using real attempts, freshness, yield and exclusion reasons.
3. At least one real podcast and video completes the permitted transcription/capture/reopen workflow, with timestamps and quality inspection, or each inaccessible case remains explicitly open; no false completion from metadata alone.
4. Saved excerpts retain attribution/version/locator and analyst destination across restarts, without trust promotion or duplicate saves.
5. Credit and language/access constraints are enforced and tested. Provider activation is proven end to end rather than inferred from keys.
6. A fresh sealed evaluation demonstrates the agreed mixed-source analyst outcome; remaining Google/variety/source coverage is honestly reported. All required CI and release-preservation checks pass on the shipped revision.
7. Update this ledger, coverage matrix and debt register with exact receipts, deployed/undeployed boundaries, remaining holds and a concrete review point. Never declare all varieties or all public sources complete from a small sample.
