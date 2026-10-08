# Apify measured trial — October 7, 2026

Four actual authenticated jobs completed on a verified FREE, non-paying account with $5 included credit and a $5 monthly limit. Cash spent **$0**; settled account credit usage **$0.0623138386**; active jobs **0**. No purchase, merge, deployment or ongoing collection.

| Task / pinned build | Returned | Demonstrated capability | Settled run charge |
|---|---:|---|---:|
| Facebook Fall Creek public page / `apify/facebook-posts-scraper` 0.0.398 | 5 | Distinct IDs, dates, text, source URLs, author fields and media references; current Fruit Attraction posts overlap earlier SociaVault sample | $0.03600 |
| Instagram hashtag discovery / `apify/instagram-scraper` 0.0.803 | 1 | Unexpected tag metadata only; **zero usable posts**, despite job success | $0.00270 |
| LinkedIn blueberry search / `harvestapi/linkedin-post-search` 0.0.114 | 5 | Four text records and one article preview without article body; five distinct IDs/URLs; two post-image records, one video reference and a separate article cover | $0.01005 |
| Instagram exact blueberry hashtag URL / `apify/instagram-scraper` 0.0.803 | 5 | Dated posts with author handles and image references; three carousels with 7, 4 and 6 image entries | $0.01350 |

Charges total $0.06225; account usage is slightly higher. Early terminal responses reported incomplete charges; a later read confirmed settled values. Use the account total for the trial budget.

Assistant inspection, not independent accuracy qualification: Instagram has four blueberry food/use/trade posts and one irrelevant nail-art hashtag result. One relevant post is Vietnamese and requires translation before display. LinkedIn has three directly relevant product/supply/use text posts, one primarily about sea buckthorn with blueberry comparisons, and one blueberry article preview whose body was not retrieved. Profile-authored trade marketing occurs alongside company authors; author type alone cannot determine corporate/consumer intent. Health/nutrition claims were not validated.

LinkedIn includes relative-age-derived timestamps and returned results were not strictly chronological despite requested date order. Preserve estimated-date provenance and sort locally. UTC October 8 corresponds here to the operator's October 7 evening. No fake precise publication dates.

Media references were retrieved; loading, playback, expiry, redisplay permission and deletion propagation were not tested. No comment objects returned; counts do not demonstrate comments. Repeat identities, pagination, complete history, five-language accuracy, X/TikTok/Reddit and China coverage remain untested in this Apify sample.

Inputs were validated against fetched build schemas. Each job pinned its build number, verified executed build ID, used a 90-second timeout and $0.10 maximum total charge, limited permissions and disabled auto-restart. A locked atomic ledger reserved before launch and retained run IDs. A second invocation skipped existing cases rather than resubmitting. Fresh Free-account, usage and active-job guards preceded every new job; trial ceiling $1. Secrets stayed private in authorization headers. No platform passwords or cookies were used.

Private receipts: gitignored `inbox/social-bakeoff/apify-2026-10-07/` holds ledger, inputs/pricing/builds, run receipts, datasets and final audit. Execution/audit scripts reside in the operator's `outputs/social-blueberry/` folder. **This private trial does not implement the production Apify connector.** Samples have not been imported into the current preview or trusted evidence.

Primary sources: [run API and charge/build controls](https://docs.apify.com/api/v2/actors-runs-post), [account limits](https://docs.apify.com/api/v2/users-me-limits-get), [Facebook Actor](https://apify.com/apify/facebook-posts-scraper), [Instagram Actor](https://apify.com/apify/instagram-scraper), [LinkedIn Actor](https://apify.com/harvestapi/linkedin-post-search). Exact charges were measured and current pricing metadata was inspected; marketplace headlines were not substituted.

**Recommendation: continue free tests before buying.** Apify is a promising targeted supplement for LinkedIn corporate discovery and Instagram carousels. SociaVault has broader demonstrated platform coverage from earlier trials. Different inputs/times mean this is not a controlled comparison of recall or recurring cost. No further account signup is needed for the next Apify checks.

## Follow-up: comments and image availability

A fifth bounded job used the same LinkedIn Actor with `scrapeComments=true`, `maxComments=2`, and three requested posts. It returned three posts with empty comment arrays/IDs; settled run charge $0.00605, zero comment events. **Comment collection remains unproven**, rather than classified as broken or successful. Search results changed between runs; a stable known post with independently observed comments is needed next. The account aggregate was still catching up on the latest read ($0.0623688642); do not treat that transient value as the settled five-job total. Five measured run charges sum to $0.06830, cash remains $0, and no active jobs remain.

Headers-only availability checks of five Instagram cover images and two LinkedIn post images all returned HTTP200 with `image/jpeg`; zero media bytes were downloaded/stored. This demonstrates current reference accessibility, **not** rendered carousel completeness, playback, long-term expiry or redisplay rights. Receipts are private `media-head-probe.json`. The repeat script also skipped all four existing cases, demonstrating that this trial ledger avoids duplicate submissions; this is not a production connector restart test.

## Shared intake validation

`apify_intake.apify_post` now maps the three inspected post schemas through the existing strict intake model. Private actual-response audit: Facebook 5 accepted/8 image references; Instagram exact hashtag 5 accepted/19 references; initial tag record rejected; LinkedIn initial search 4 accepted/2 references and article-only record rejected; follow-up 3 accepted. These are schema counts, **not** relevance or translation approval. Nothing was imported into the workspace. LinkedIn relative date estimates remain in raw private receipts and are not mapped as precise publication timestamps; date-basis modeling remains a continuation item. Video and article-body mapping remain incomplete.

Offline validation: **31 passed**, including carousel/native identity and author provenance, media parent linkage, avatar/placeholder exclusion, metadata/article rejection, source-domain checks, estimated-date handling and existing budget guards. No live calls in tests.

### Estimated-date contract follow-up

The intake now adds backward-compatible `publication_date_basis` (`source` default, `estimated` alternative). LinkedIn provider dates are retained for sorting/filtering with `estimated` provenance, labeled **estimated date** in the post table/reader and downstream context. This supersedes the earlier unmapped-date limitation above; precision remains unverified. Existing payloads default to source-provided dates. No SQLite structural migration is required; payload validation supplies the default. Rollback: revert this optional field and its producer/renderers together; preserve private receipts before reverting. No trusted evidence or unrelated schemas were changed.

Intake, bake-off and evidence regressions: **98 passed**. Real samples have not been imported; screening, translation and cross-provider preservation need verification before preview changes.

Workspace routes, presentation and saved profiles: **34 passed**, with one existing Starlette/AnyIO deprecation warning. Total affected checks **132 passed**; `git diff --check` clean.

## Cross-provider storage follow-up

The existing source/mode/native-ID identity combines matching posts without creating provider-specific copies. A sparse response from a different acquisition method now preserves previously captured attachments, with exact-URL deduplication and the existing 30-attachment bound. Content-free collection receipts retain method, query/build version and collection time across updates/restarts. Apify image IDs use URL fingerprints to avoid position collisions with other providers.

Private SQLite adds `collection_receipts` and `media_url_tombstones` with idempotent creation; no trusted corpus migration. Explicit media removals retain an exact-URL hash so replay under another provider's attachment ID cannot resurrect that reference. Existing ID tombstones and whole-post deletion continue to govern. Alternate signed URLs for the same removed image and provider-varying native post IDs still need reconciliation; do not claim universal cross-provider deletion or deduplication. Rollback can leave these additive tables in place, but reverting loses the new receipt/preservation/alias protections. No destructive rollback or preview import performed.

Validation: **108 passed**, covering storage, intake, workspace routes and saved profiles, with one existing Starlette/AnyIO deprecation warning. New checks exercise sparse provider updates, one-post identity across restart, receipt deduplication, original-ID removal replay and same-URL/different-ID removal replay. No network or paid calls in tests.

### Actual retained-sample combination

An isolated offline database combined the existing 243 live SociaVault records with 17 schema-valid Apify rows (16 distinct post identities). Three Facebook post identities matched existing records; 13 identities were new. Combined count **256**, unchanged after replay. These are unfiltered schema counts: irrelevant/unttranslated samples are included privately and not approved for display. Collection times/queries differ, so 13 additions do not measure comparative recall.

Matching posts retained both provider receipts and prior media through replay. One five-reference post became ten references because the providers supplied different signed/size URLs for apparently overlapping photos; exact-URL deduplication does not establish visual-asset deduplication. Stable attachment identities/image variants remain open before preview import.

The first actual replay exposed loss after a second sparse response. Storage now checks acquisition history, preserving earlier attachments on repeated updates after provider switching. The regression specifically checks that second update. **69 storage/evidence checks passed**, and the repeated actual sample audit passed. Raw records and the combined database remain private; the original preview is unchanged. Failed first audit retained separately for diagnosis. No new source requests or credit usage.

### Facebook signed-photo variants

Inspected duplicate photo references had identical Facebook CDN file paths with different query signatures/sizes. Only Facebook-source references on `*.fbcdn.net`, `/v/` paths and image extensions now share that path identity. Other hosts retain exact-URL identity; no generic query stripping or visual-similarity claim. Matching incoming photos retain the established attachment ID so review locators are stable. Removal hashes use this inspected reference identity, with legacy exact-URL hashes still recognized.

Actual isolated replay now retains **5 photos instead of 10 URL variants** on the overlapping five-photo post, preserving 256 combined records and both provider receipts. **71 storage/evidence tests passed**, including refreshed-signature removal and distinct-query behavior on other hosts. Existing tombstones created before this change only protect their recorded exact URL unless the original attachment ID matches; unknown historical signed variants remain a limitation. No media downloads, preview import, spending, merge or deployment.

Next: matched source comparisons, comments/replies, media loading/expiry, repeat/pagination and multilingual samples; then schema-specific normalization through existing intake, with estimated dates, article-only handling, author provenance, translation/quarantine and incidental-hashtag screening. Corporate and consumer views remain separate. Recurring monitoring, retention/removal permission and independent evaluation are unresolved; collection stays disabled.
