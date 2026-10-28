# Newsfeed Tags

News now filters the complete accessible retained source collection by stable tag IDs before pagination. Tag restrictions combine with search, publisher, berries, geography, dates, companies and existing review scope. All is the new-account default; Any returns the union once per source ID. An empty selection includes untagged news. Clear tags retains every other filter; Reset clears the broader scope.

Selections and the explicit mode are private, durable preferences keyed by the signed-in session account. The single-user local workspace uses `local-analyst`. Explicit URL selections override remembered selections, including `tag=`. Reader navigation and pagination carry the same scope. JavaScript saves preferences through a same-origin POST; native forms still filter without JavaScript. Legacy `topic=gene-editing` and `topic=advanced-breeding` resolve to their existing IDs and retain their adjacent-crop scope. New `tag=` links use effective flat assignments.

Article tags share the compact styling of the source and berry labels. Clicking a tag opens a shared slide-out panel with its supporting text and article assignment controls. A matching `+` button opens the same panel to add tags. An explicit **Filter news by this tag** action remains inside the panel. Assignments update the card in place; closing the panel refreshes an actively tag-filtered feed when needed. Escape closes the panel and returns focus to the card.

## Runtime migration and backfill

The additive runtime database is `inbox/news_workspace/tags.sqlite3`. It is private and must remain on the existing persistent inbox mount. No canonical Evidence, source claim, Fact, entity identity, review status or production runtime is replaced. Back up the inbox using the existing release procedure before deploying. Preserve this database on rollback to retain corrections and account preferences.

Run from the deployed checkout, using that runtime's configured directories:

```powershell
python scripts/backfill_news_tags.py --inbox C:\path\to\runtime\inbox --data C:\path\to\runtime\data
```

With the normal environment configuration, omit both overrides. The first interactive Tags visit also queues initial classification. `Recheck stored articles` retries an interrupted job. Tag creation commits immediately and queues the same worker. The worker hydrates only stored sources and exact-source Reader captures; it never crawls or starts research. Set `BIOS_NEWS_TAG_CLASSIFIER=semantic` to use the existing configured non-trusted enrichment provider/model (Haiku by default) for subject classification. A key alone does not activate paid calls. The default `rules` mode remains available offline. Semantic work uses up to 12 text chunks per call, 6,000 characters per chunk and 48,000 characters per source; each pass is capped at 100 calls. `python scripts/backfill_news_tags.py --until-complete --max-passes 10` resumes bounded passes. Completed decisions and chunks are cached by content, provider/model, classifier and definition version. Every returned supporting passage must occur in its supplied source chunk; missing, malformed or unsupported decisions fail the batch without erasing prior assignments. Restarting reruns the scan but skips unchanged decisions. Errors retain prior assignments, disclose incomplete results and allow retry.

Incoming live bundles, source draft writes and newly recovered Reader bodies use the same cached classifier after source persistence; semantic calls run on a background worker, outside the source write and SQLite transaction. Classification failure records an error without failing acquisition. For bulk canonical imports outside those application write paths, run the backfill command after the import.

Automatic decisions store source/tag IDs, classifier and definition version, timestamp and supporting text. Manual additions/removals have independent rows with actor/time and an audit event. They take precedence over background completion. Restore automatic assignment clears that override. Renaming preserves identity and matching vocabulary; changing the description increments the definition version and rechecks automatic decisions. Tag creation and corrections require no provider availability. In semantic mode, provider failure is visible and retryable; it never silently replaces semantic decisions with rules or empty assignments.

## Local acceptance evidence

The original nine-tag pass evaluated **1,269 real stored sources**, producing **11,421 article/tag decisions** and **946 positive automatic assignments**. These are corpus evaluation totals, not filtered News counts:

The final local text-coverage audit found **0 stored full bodies** in this checkout's accessible corpus; all 1,269 sources have metadata and/or excerpts only. This materially limits classification recall. The worker supports stored bodies and exact-source Reader captures when they exist, but did not fetch missing text to improve these figures. These figures describe the earlier local rules-mode audit, before production semantic classification.

| Tag | Automatic matches |
|---|---:|
| Advanced Breeding | 3 |
| AgTech | 4 |
| Corporate | 130 |
| Gene Editing | 2 |
| Genetics | 299 |
| Markets | 379 |
| Retail | 54 |
| Sustainability | 22 |
| Weather | 53 |

Browser walkthrough on the real local dataset: no tags showed 783 eligible stories; Markets showed 291; Markets + Retail / All showed 5; Any showed 310; Clear tags restored 783. Name-only Labor creation added its chip immediately, did not change the current selection and backfilled 15 eligible News stories. These counts describe the checked local snapshot, not production coverage. A 390px viewport showed wrapped checkbox chips, a scrollable tag list and accessible controls. The local preview is `/today` on loopback port 8717.

The service tests cover all nine positive/negative classification cases, nonliteral Markets matching, ordinary breeding excluded from Gene Editing, three-tag intersection, pre-pagination selection, empty selection, filter composition, Unicode/whitespace duplicate races, account separation, explicit clear persistence, idempotent retry, durable manual overrides, late background completion, restore automatic assignment, definition changes and failed classification retaining prior assignments. Route tests cover old topic URLs, account restore, creation/backfill, assignment explanations and same-origin/access guards.

Earlier focused validation: **103 passed** across News Tags, News workspace, Gene Editing, living workspaces and Research Desk. Record validation passed. The static public-safety build produced **1,794 pages**, built Pagefind and verified that no unpublished draft IDs/titles leaked. The repository-wide suite was attempted but encountered a Windows native access violation inside Jinja's optimizer; no full-suite or required GitHub-check success is claimed here. Linux CI remains required before merge.

## Classification limits

Semantic mode classifies each flat tag definition independently, including nonliteral wording. It uses the existing authorized provider configuration without web search or tools. Each article must have an explicit complete response, including negative decisions. Supporting passages, classifier/definition versions and timestamps remain private. Chunk caches allow long-body runs to resume without repeating completed provider calls. An SQLite lease prevents concurrent workers from duplicating work; changed source fingerprints prevent old in-flight results from overwriting newer content. Automatic results remain relevance metadata and never change source review, claims, Facts or trust.

Rules mode extends the existing deterministic terminology classifier and remains the offline default. Gene Editing and Advanced Breeding reuse the agricultural sentence/context rules. Custom tags use names, descriptive terms and supported aliases. Both modes are limited by stored text coverage; neither fetches missing bodies. Model decisions can still omit or over-assign subjects, so supporting passages and durable corrections remain necessary.

Living workspace inventories expose the same tag IDs and their feeds consume the same effective assignments. Explicit `tag_mode=all` in a workspace feed requires every chosen topic ID. Existing workspace facet mode remains compatible. Research these tags passes stable IDs and All/Any into stored Research Desk source selection and follow-ups. Its question-intent vocabulary remains separate. Fresh-source research requires starting a new question: unclassified web results cannot silently bypass the saved tag restriction. Existing explicit report source selection is retained.

Production deployment and merge follow existing authorization and required CI checks. Local runtime assignments and test-created Labor remain private runtime data, never committed fixtures or public static output.
