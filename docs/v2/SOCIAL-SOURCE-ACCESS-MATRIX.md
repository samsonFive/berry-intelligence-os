# Social source-access matrix — 2026-10-07

The [zero-spend vendor comparison](SOCIAL-MONITORING-BAKEOFF.md) adds current Apify Actor/SociaVault/enterprise feasibility, official setup links and isolated test measurements. Two saved public Bluesky Jetstream samples connected but yielded no blueberry posts; keyword search remains HTTP403-blocked. News RSS returned93unique titles, not consumer-social evidence. These tests do not upgrade the15platform production-coverage statuses below or establish vendor permission.

No subscriptions, paid collection, trials or access applications were activated. Only Bluesky and YouTube have implemented automated paths. Imported/manual samples never count as live access. Primary-page fetch failures remain visible.

## instagram — stale

- **Implemented:** False
- **Methods:** Proposed official Instagram Platform account/hashtag methods; authorized exports/manual supported by common intake
- **Auth:** Meta app, eligible professional account, access token and approved permissions; exact current scopes need revalidation
- **Capabilities:** Current hashtag/search/comments/media limits unverified; do not claim broad consumer keyword listening
- **History:** Current historical limits unverified
- **Quotas costs:** No current quota/price assertion; developer console and accessible documentation required
- **Retention deletion:** Current Meta terms/deletion requirements must be reviewed before enabling storage
- **Blocker:** No app/token/approved permissions provisioned; primary pages HTTP 429 during research
- **Verification:** attempted current primary docs; blocked HTTP 429
- **Official documentation:** [Source 1](https://developers.facebook.com/docs/instagram-platform/), [Source 2](https://developers.facebook.com/docs/instagram-platform/instagram-api-with-facebook-login/hashtag-search/)

## facebook — stale

- **Implemented:** False
- **Methods:** Proposed Pages API; authorized exports/manual
- **Auth:** Meta app/page token and permission review required
- **Capabilities:** Page posts/comments/media scope needs current review; private groups excluded
- **History:** No full-history or public-conversation coverage claimed
- **Quotas costs:** Quota/pricing not verified
- **Retention deletion:** Review Meta platform terms/deletion requirements before collection
- **Blocker:** No page token/access review; documentation HTTP 429
- **Verification:** attempted current primary docs; blocked HTTP 429
- **Official documentation:** [Source 1](https://developers.facebook.com/docs/pages-api/)

## threads — stale

- **Implemented:** False
- **Methods:** Proposed Threads API keyword search; authorized exports/manual
- **Auth:** Meta app, token and current approved scope required
- **Capabilities:** Keyword search/replies/media access not established in this environment
- **History:** No historical completeness claimed
- **Quotas costs:** Quota/pricing not verified
- **Retention deletion:** Current platform terms/deletion obligations not verified
- **Blocker:** No credentials; primary docs HTTP 429
- **Verification:** attempted current primary docs; blocked HTTP 429
- **Official documentation:** [Source 1](https://developers.facebook.com/docs/threads/), [Source 2](https://developers.facebook.com/docs/threads/keyword-search/)

## tiktok — access-pending

- **Implemented:** False
- **Methods:** Proposed Research API or specifically licensed authorized feed; Display API is not broad listening
- **Auth:** Approved research project/client token with research.data.basic; personal funding alone does not confer eligibility
- **Capabilities:** Research video query and comments; described archived search data; no image/video download permission inferred
- **History:** Search archive delays; new videos may take 48h, metrics longer
- **Quotas costs:** FAQ: 1000 requests / 100000 records per day; 100 records per video/comment request; no subscription activated
- **Retention deletion:** Research terms/security and compliance status checks need operator review before retention
- **Blocker:** No approved project. User independently builds on personal resources; eligible affiliation/public-interest purpose unestablished
- **Verification:** read current primary documentation
- **Official documentation:** [Source 1](https://developers.tiktok.com/products/research-api/), [Source 2](https://developers.tiktok.com/docs/en/research-api-faq), [Source 3](https://developers.tiktok.com/docs/en/research-api-specs-query-video-comments)

## x — setup-required

- **Implemented:** False
- **Methods:** Proposed X API v2 search; authorized import/manual
- **Auth:** Developer app bearer token and funded credits; paid use explicitly disabled
- **Capabilities:** Post search with media expansions/conversation IDs; scope/history depends endpoint and entitlement
- **History:** Recent vs archive endpoint entitlements must be confirmed
- **Quotas costs:** Current public pricing: post read $0.005/resource, user read $0.010/resource; rates may change. No purchase or call made
- **Retention deletion:** Developer terms and deletion/compliance processing required before collection
- **Blocker:** No token/approved paid collection budget. Do not activate credits or auto-recharge
- **Verification:** read current primary documentation
- **Official documentation:** [Source 1](https://docs.x.com/x-api/getting-started/pricing), [Source 2](https://docs.x.com/x-api/posts/search/introduction), [Source 3](https://developer.x.com/en/developer-terms/agreement-and-policy)

## reddit — access-pending

- **Implemented:** False
- **Methods:** Proposed approved Data API OAuth; authorized export/manual only
- **Auth:** Reddit approval and permitted use agreement; OAuth app credential
- **Capabilities:** Posts/search/comments and permitted attached media require approval; no scraping fallback
- **History:** Listing/search history is not complete archive
- **Quotas costs:** No current approved quota/price provisioned; separate agreement may be needed
- **Retention deletion:** Honor removal and termination deletion requirements; no model training permission inferred
- **Blocker:** No approved app/use; commercial eligibility cannot be inferred from personal funding
- **Verification:** read current primary documentation
- **Official documentation:** [Source 1](https://redditinc.com/policies/developer-terms), [Source 2](https://redditinc.com/policies/data-api-terms)

## youtube — setup-required

- **Implemented:** True
- **Methods:** Implemented Data API v3 search.list + bounded commentThreads.list paths; mock transport verified
- **Auth:** BIOS_SOCIAL_YOUTUBE_KEY in server environment; existing Google project with Data API enabled
- **Capabilities:** Public video metadata/thumbnails, sampled comments/replies. Caption download needs authorization; no automatic transcripts/video bytes
- **History:** Published-date search/pages; not complete archive; commentThreads may omit replies
- **Quotas costs:** Current overview: default 100 search calls/day plus 10000 units/day for other endpoints; commentThreads.list 1 unit. Console authoritative; no paid collection
- **Retention deletion:** Refresh or delete stored API data within 30 days; no restricted media rehosting; privacy/YouTube terms requirements before live operation
- **Blocker:** Key not provisioned; live criterion unmet; privacy/terms and retention operations must be accepted
- **Verification:** read current primary documentation
- **Official documentation:** [Source 1](https://developers.google.com/youtube/v3/getting-started), [Source 2](https://developers.google.com/youtube/v3/docs/commentThreads/list), [Source 3](https://developers.google.com/youtube/terms/developer-policies)

## bluesky — access-pending

- **Implemented:** True
- **Methods:** Implemented public AppView searchPosts + getPostThread paths; mock transport verified
- **Auth:** Public AppView GET documented without credentials; actual service/network returned HTTP 403 here
- **Capabilities:** Search post text, language tags, image references, reply thread images; video analysis unsupported
- **History:** Cursor/recent search; complete archive not guaranteed
- **Quotas costs:** AppView limits depend service; no universal numeric search quota/cost asserted; pilot ≤12 requests/run
- **Retention deletion:** References by default; configurable 30-day local expiry and deletion propagation; maintain applicable platform/content rights
- **Blocker:** Bounded search probe HTTP 403 on 2026-10-07 UTC; cause/entitlement unestablished, no bypass attempted
- **Verification:** read current primary documentation
- **Official documentation:** [Source 1](https://docs.bsky.app/docs/api/app-bsky-feed-search-posts), [Source 2](https://github.com/bluesky-social/atproto/blob/main/lexicons/app/bsky/feed/searchPosts.json), [Source 3](https://docs.bsky.app/docs/advanced-guides/rate-limits)

## linkedin — access-pending

- **Implemented:** False
- **Methods:** Proposed Community Management; authorized export/manual
- **Auth:** Vetted app, organization/page authorization, versioned access and restricted scopes
- **Capabilities:** Authorized organization posts/comments and image/video asset references; no arbitrary public consumer keyword search established
- **History:** Authorized object history only; no global archive claim
- **Quotas costs:** Development overview reports 500 app / 100 member requests; exact applicable interval/console quotas need confirmation. No public subscription price asserted
- **Retention deletion:** Marketing API terms restrict member data; deletion/retention policy must be confirmed before enabled storage
- **Blocker:** No vetted legal organization/business email/app authorization; independent personal project eligibility unestablished
- **Verification:** read current primary documentation
- **Official documentation:** [Source 1](https://learn.microsoft.com/en-us/linkedin/marketing/community-management/community-management-overview?view=li-lms-2026-06), [Source 2](https://learn.microsoft.com/en-us/linkedin/marketing/community-management-app-review?view=li-lms-2026-05), [Source 3](https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/comments-api?view=li-lms-2026-06)

## pinterest — setup-required

- **Implemented:** False
- **Methods:** Proposed authorized v5 pin/board APIs; authorized export/manual
- **Auth:** OAuth app with trial then approved standard access
- **Capabilities:** Authenticated pin/board data and media; broad keyword listening/comments access not established
- **History:** No global historical coverage claimed
- **Quotas costs:** Trial/standard rate limits differ; exact numeric quota and price not confirmed
- **Retention deletion:** Terms and pin deletion/retention obligations need review; no scraping/media rehosting
- **Blocker:** No app/token or standard access; search-pins page inaccessible in research
- **Verification:** read current primary documentation
- **Official documentation:** [Source 1](https://developers.pinterest.com/docs/key-concepts/access-tiers/), [Source 2](https://developers.pinterest.com/docs/api/v5/pins-list/)

## weibo — setup-required

- **Implemented:** False
- **Methods:** Proposed official open-platform CLI/API; authorized import/manual. No CLI installed
- **Auth:** Verified developer authentication and service entitlement/credits
- **Capabilities:** Official CLI advertises search, comments and trends; exact read methods and media rights require provisioned entitlement
- **History:** Official guide warns page/cursor is not a snapshot; long text not guaranteed
- **Quotas costs:** Developer-certified 7-day trial described; production credit packs/service list in console. No activation, numeric rates not verified
- **Retention deletion:** Current service terms/retention and removal feed unverified; do not collect until resolved
- **Blocker:** No verified account/token/entitlement. Trial activation and purchasing prohibited in this task
- **Verification:** read current primary documentation
- **Official documentation:** [Source 1](https://open.weibo.com/cli), [Source 2](https://open.weibo.com/cli/quickstart)

## douyin — access-pending

- **Implemented:** False
- **Methods:** Proposed Douyin Open Platform authorized interfaces; authorized export/manual
- **Auth:** Approved application and scoped user authorization
- **Capabilities:** Official catalog describes authorized account/video/comment capabilities; no general consumer keyword listening established
- **History:** Authorization-dependent; archive depth unverified
- **Quotas costs:** Exact quotas/costs depend interface and entitlement; no public numeric assertion
- **Retention deletion:** Current data-use/retention and deletion requirements need Chinese-language review before collection
- **Blocker:** No approved app/scopes; authorized account API is not global listening
- **Verification:** read current primary documentation
- **Official documentation:** [Source 1](https://developer.open-douyin.com/docs/resource/zh-CN/dop/develop/openapi/list), [Source 2](https://developer.open-douyin.com/docs/resource/zh-CN/interaction/develop/server/live-room-scope/data-open/data-open-desc)

## red — unsupported

- **Implemented:** False
- **Methods:** Authorized exports/manual; no confirmed broad public listening API
- **Auth:** Merchant/service partner authorization for documented commerce APIs
- **Capabilities:** Official portal concerns commerce/services; public note search/comments/media listening not verified
- **History:** Not established
- **Quotas costs:** No quota/price invented
- **Retention deletion:** Retention rights and deletion obligations for any authorized export must be recorded
- **Blocker:** No approved data feed or documented public listening method; primary documentation shell did not expose API detail
- **Verification:** read current primary documentation
- **Official documentation:** [Source 1](https://open.xiaohongshu.com/document/developer/file/1), [Source 2](https://open.xiaohongshu.com/document/api?apiId=29896&apiNavigationId=250&apiParentNavigationId=21&gatewayId=165&gatewayVersionId=2804&id=92)

## bilibili — unsupported

- **Implemented:** False
- **Methods:** Authorized exports/manual; proposed Open Platform only within approved scope
- **Auth:** Verified identity/application plus user authorization and scoped permissions
- **Capabilities:** Official documented creator archive capability; broad public video/comment/transcript search not established
- **History:** No historical listening claim
- **Quotas costs:** No applicable public quota/price confirmed
- **Retention deletion:** Confirm source/content rights and deletion constraints before storage
- **Blocker:** No approved app; creator upload/edit capability does not prove read/listening rights
- **Verification:** read current primary documentation
- **Official documentation:** [Source 1](https://open.bilibili.com/doc/main), [Source 2](https://open.bilibili.com/doc/4/ddfbe54d-b4ab-340e-c698-933b9a3c619c)

## forums-retail — setup-required

- **Implemented:** False
- **Methods:** Authorized site-specific Discourse/RSS/API exports and manual URL capture
- **Auth:** Per-site API key/permission or allowed public feed; none configured
- **Capabilities:** Discourse topic/post JSON supports discussion and attachments; retailer reviews require their own permission, no blanket adapter
- **History:** Site-specific retention/archive
- **Quotas costs:** Site-specific quotas/licensing; no universal costs
- **Retention deletion:** Each publisher terms/removal policy required; common expiry does not establish permission
- **Blocker:** No authorized target forum/retailer feed configured; discovery via search engine is supplementary only
- **Verification:** read current primary documentation
- **Official documentation:** [Source 1](https://docs.discourse.org/)


## October 7 follow-up: translation-first UI and actual SociaVault trial

The [multi-platform measured trial](SOCIAL-SOCIAVAULT-MULTIPLATFORM-TRIAL.md) supersedes earlier statements that no SociaVault key/account or live social sample was available. Actual bounded discovery returned content from six platforms; 24 one-time free credits consumed, 26 remaining, $0 paid. LinkedIn is blocked and two TikTok responses exceeded the byte ceiling. Original images can be loaded explicitly; translation-first text keeps original wording on hover/focus/tap. Production scheduling, source-specific retention/redisplay permission, independent accuracy/global coverage, automatic dossier/briefing assembly and published dependency retraction remain unproven or unmet. The isolated preview is localhost18345; public git contains counts/manifests and invented demo screenshots, not real raw posts. No merge/deployment occurred.


## Visual reader and successful LinkedIn follow-up — October7

See [the current reader/LinkedIn report](SOCIAL-VISUAL-READER-LINKEDIN.md): public company retrieval, two independently located named-variety posts and broader undated keyword search all succeeded.21 retained rows added19 unique records; total isolated records171. Four additional free credits used; total28 consumed,22 remaining,$0 paid. Earlier404 failures remain recorded with unresolved cause. Public native LinkedIn embedding rendered without a LinkedIn login. The reader now leads with native video players/photos and compact supporting detail. No ongoing collection, rights/accuracy qualification, merge or deploy.


October7 Social continuation: Facebook public company pages and X company searches now demonstrated via bounded vendor follow-up (six Facebook posts,20 retained X posts;$0,18 free credits remain). Source language/translation controls hide unreadable records; Facebook groups/comments/general keyword search and independent qualification remain unmet. See [current measured report](SOCIAL-VISUAL-READER-LINKEDIN.md).
