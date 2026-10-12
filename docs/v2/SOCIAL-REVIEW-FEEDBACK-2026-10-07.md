# Social Listening review feedback — 2026-10-07

The user confirmed source links, translations, corporate filtering and overall appearance, requested All berries as the default, identified BlackBerry technology noise, and requested the missing Reddit picture.

## Result

- All berries is the default when no berry is specified or the selection is empty. Each source identity is counted once across views, exports and private context hooks. Explicit single-berry links remain scoped.
- Whole-post screening excludes BlackBerry phone, keyboard, device-model, iPhone, touchscreen and company-stock contexts. Explicit fruit language preserves actual blackberry posts; generic patents and technical growing discussions are not excluded. This is a bounded literal screen, not a demonstrated universal relevance classifier.
- One authorized SociaVault Reddit post/comments request returned the exact retained original post and one original image reference. Search summaries had omitted that attachment. The image rendered in the existing in-app lightbox. Gallery, preview and inline image references now normalize through the same media pipeline. No media was downloaded or rehosted.
- Full-post attachment supplements survive later search-summary replay; explicit removal tombstones still suppress them.

## Measurements and limits

HTTP 200; one request, one existing free credit; $0 spent. Account balance 11 remaining, 39 consumed from the initial 50; ten-credit reserve intact. Cumulative reserved attempts 41 include earlier zero-credit failures. Attempt limits and authenticated credit consumption are separately enforced. No other new source calls, subscription or ongoing collection.

Offline picture replay added zero new attachments. Current readable trial view: All berries 72 unique posts; blueberries 41, strawberries 12, raspberries 16, blackberries 15. Single-berry counts overlap. Four retained phone-related posts were excluded from the fruit view without deleting raw evidence. The 243-record raw live corpus remains private.

Validation: 106 focused tests passed, one existing dependency warning, 45.44 seconds. Added regressions cover whole-post technology noise, explicit fruit retention, combined-view identity/count/export/shareability, gallery/inline media, durable supplements/removal and credit/attempt caps. Synthetic rollout evaluation remains 246/246 fields across 33 cases in EN/ES/PT/ZH/JA; original blueberry remains 202/207, with five conservative sentiment disagreements. Independently graded live cases remain zero.

Official method: [SociaVault Reddit post/comments](https://docs.sociavault.com/api-reference/reddit/post-comments). The successful detail check proves this one attachment path, not exhaustive Reddit image coverage. Browser access to the original Reddit page encountered a humanity check; no CAPTCHA was solved or bypassed. Platform links may expire or become restricted; attachment removal controls remain available.

## Preview and rollback

Run `python scripts/preview_social_sociavault.py` with the retained private runtime, then open `http://127.0.0.1:18345/social?mode=live`. Default selection is All berries. The breakfast picture appears near the top; click it to enlarge inside the app. Existing corporate and consumer filters remain available.

No SQL migration. Private SQLite was backed up with SQLite's backup API before reprocessing unreviewed proposals under `social-literal-3`. Reviewed corrections remain preserved. Rollback restores the prior code and private backup; never publish the private database or raw responses. The one-request manifest and metadata-only receipt are under `benchmarks/social-bakeoff/reddit-picture-review-manifest.json` and `artifacts/social-all-berries/reddit-picture-review.json`.

Draft PR314 remains unmerged and undeployed. Broader unmet checks in SOCIAL-ACCEPTANCE-AUDIT.md remain open; functional user feedback does not qualify independent accuracy, rights, unattended monitoring or automatic downstream assembly.
