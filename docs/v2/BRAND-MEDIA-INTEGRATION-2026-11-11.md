# Brand and packaging media: isolated integration candidate

November 11, 2026. Branch `feature/brand-packaging-social-20261111`, based on
locally retained canonical `44f00b90` (#551). A fresh `git fetch origin` failed
in this environment; reconcile with current canonical before review/merge.
No production deployment, production record changes, subscriptions, provider
requests or incremental spending occurred.

The requested real packaging-image acceptance case is **blocked**, not passed.
The existing connectors work in historical receipts, but the retained cohort
contains reference URLs rather than permitted local image bytes. Its packaging
classification and display policy are unresolved. A working UI fixture is not
substituted for real packaging evidence.

## Connection and retained evidence

The [narrow connection report](BRAND-MEDIA-SOCIAL-CONNECTION-CHECK.md) distinguishes
implementation, credential presence, runtime enablement, actual retrieval and
current production activation. Apify and SociaVault were checked first;
implemented direct/supplementary connectors are also reported there. Existing
SSH provided authenticated read-only production inspection: SociaVault manual
collection is enabled and unscheduled; Apify has no production token. The latest
completed manual batch is October 21, 1:24 PM Los Angeles (193 raw returns).

Production currently retains 631 live social records and 396 media references
(267 images, 124 thumbnails, 5 videos). All 396 are `reference_only`; there are
zero stored objects. Stored availability is an ingestion flag, not a current
source-availability check. The production ledger's October 21 balance of 5,958
is historical, not fresh allowance verification. No provider request was made.

Automatic approval review initially rejected exporting the production SQLite
because its account/post/media metadata required explicit human export
authorization. The user subsequently answered **"Approve the private snapshot
copy"**. The approved copy succeeded November 11 at 2:29 PM Los Angeles through
the existing SSH connection: a read-only SQLite source was backed up in memory
and streamed directly into the isolated, gitignored local inbox. No remote
temporary file, production write, provider request or media-object copy occurred.

The 3,502,080-byte private snapshot passed SQLite integrity checking and contains
695 rows: the 631 live records / 396 references reported above and 64 fixture
rows excluded from real reuse. Of the live records, 382 remain unexpired and
249 are expired; 221 media references remain within source retention. Its SHA256 and copy scope
are retained in `inbox/brand-media-production-retained-preview/snapshot-receipt.json`.
Retained-first reuse scanned all 631 records with a 1,000-record bound for the
same two-company cohort. It skipped 249 expired records, created 18 unclassified
image/thumbnail mappings (15 exact account matches, three proposed links), and
excluded one video reference from image intake. A second pass reused all 18 and
created zero records. The source snapshot hash remained unchanged. Zero assets
are display eligible; no publication/collection dates or permissions were reset.
The private two-pass proof is `reuse-receipt.json` beside the copy receipt.

The user also chose to identify an existing media-use policy. Its name/link/file
and asset/display/storage/export scope are still pending. That choice does not
grant an unspecified policy or alter image permissions; all usage holds remain.

The earlier locally retained operator-funded SociaVault batch has 205 unique real posts and
118 media references: 74 images, 43 thumbnails, one video. None has stored bytes.
The source says: “Operator-funded public-source reference; no rehosting or
redistribution rights inferred.” Historical account/credit receipts are not fresh
entitlement evidence for another metered request. No calls were made.

The earlier browser proof uses an isolated SQLite backup of that retained batch; it does
not reingest duplicate posts or create another production collection pipeline.
Original publication/collection dates and IDs remain unchanged. Refresh scans
205 posts, creates 16 attachment mappings and matches 15 to the historically
verified exact Facebook account paths of Driscoll's and Fall Creek. One mapping
is a proposed existing entity link requiring identity review. A second pass
creates zero records. All 16 are unclassified; zero images are display eligible.
Logo attempts: 0. Classified packaging attempts: 0. These are retained-candidate
counts, not 16 packaging successes or a completed 20-brand enrichment cohort.

The Driscoll's case is `ev-social-db4a4837771a228cf42a5285`, native post
`1521898253313358`, account `DriscollsBerries`. It preserves all five carousel
references, published `2026-10-12T22:41:34Z`, collected
`2026-10-13T00:44:08.272022Z`. The caption does not establish packaging content.
Its 30-day source retention ends **November 11, 2026, 4:44 PM Los Angeles**.
Reading or refreshing the mapping never extends that deadline. Expired records
stay out of new mapping runs, galleries and the metadata-only source Reader.

## Shared contract and integration ownership

`app/services/brand_media.py` provides one private asset-reference model:

- `reuse_social(inbox, entities, accounts=..., entity_ids=..., limit=...)` reads
  the existing SQLite index in read-only mode and registers every retained image
  child. Exact preverified account identity can match automatically; caption
  keywords never classify a photograph. Stable IDs reuse the existing native
  source identity and Facebook CDN reference normalization.
- `entity_media(inbox, entity_ids)` returns an entity-ID map of `logo`,
  `packaging`, and `observations`. Only eligible local raster delivery references
  reach it. Official packs, retailer observations and consumer sightings retain
  separate source classes. Campaigns/profile pictures are excluded from packs.
- `inventory` and `operational_counts` supply the private review surface. Identity,
  image classification, policy, source state, retention and byte availability are
  separate gates. Counts can overlap (for example a matched image needing rights
  review). Source failures/corrupt indexes return clean empty gallery models.
- `decide` preserves analyst primary/rejection/classification/policy decisions
  through refresh and records private audit history. `authorized_upload` stores
  only explicitly storage-permitted rasters under their full content hash.
  Existing logo overrides retain priority. No trusted Evidence or relationship
  is created or rewritten.

Assets link existing entity and optional retail-observation/Evidence IDs.
They do not create another cultivar, supplier, origin, market or inventory model.
Social assets resolve the original post/media at read time; they do not copy post
text, signed CDN URLs or image bytes into the asset index. Deletion across modes,
durable media/URL tombstones, source restrictions and expiry invalidate delivery.

Current canonical template integration covers the default company/brand detail,
catalog detail, legacy dossier, company directory logos and Company Compare.
The shared macro is `app/templates/_brand_media.html`; contain-fit images,
mandatory visible credit, hover/focus detail, touch/keyboard inspection and
clean missing-image behavior live in `brand_media.css`/`.js`.

Source inspection uses the existing contextual Reader with the narrowly
validated `/api/social/{id}/reader?media=metadata-only` endpoint. This path
suppresses all image references and native embeds. Its failure fallback stays
metadata-only; a policy hold is never bypassed through the ordinary social view.
Opening/closing inspection preserves comparison IDs, scope, URL and focus.

`GET /api/brand-media/entities?ids=...` is the curated private integration seam
for 1–20 existing IDs. It preserves explicit Company/Brand/Retailer types and
returns only eligible image/caption/credit/source-inspection fields. It excludes
raw source image URLs, object hashes, full policy objects and analyst state.

The active experience-consolidation candidate has an unmerged React DetailHost
and `/api/investigations/v1` contract. Its owner was contacted; their
`docs/experience-consolidation/SHARED-INTEGRATION-NOTE.md` was read. That owner
retains its shared frontend/router/state/theme files. This branch changes none
of those working files. Port the bounded `entity_media` projection into their
curated detail/comparison API once a stable head is handed off. A Brand requires
an explicit detail-kind adapter; do not cast it as a Company. The new app's
Landscape logo/detail integration remains pending that coordinated integration.
No primary navigation entry was added.

## Repeatable operation

All mutations target an explicit isolated inbox. Retained reuse needs no API key:

```powershell
python scripts/enrich_brand_media.py --inbox PATH --reuse-social --entity company-driscolls --entity company-fall-creek-farm-and-nursery
```

Omit `--entity` for the bounded existing-corpus pass (default 500 posts, maximum
1,000). The CLI reuses the shared runtime collection lock. Single-entity Refresh
media and analyst classification/reject/primary controls are under the existing
profile's **Profile & links → Brand and packaging media**. That secondary
operational page also accepts an authorized raster and its policy/provenance.

`--official-html PAGE.html --verified-page-url URL --entity ID` extracts
Organization/Brand schema logos and Product-image candidates from already
acquired verified-page HTML. Exact subject locators, declared identities and
dimensions are retained; Product images remain unclassified. It performs no
network requests or JSON-LD context fetching, and starts with rights held.
This preserves an official-site route without requiring a logo-provider key.
Live official-site fetching/header/press-kit discovery and a real initial logo
cohort are still open; metadata extraction alone does not complete that track.

`--upload IMAGE --metadata METADATA.json` is the equivalent authorized intake
command. `--decision DECISION.json` applies a reviewer-attributed decision.
Remote image URLs remain source references. No arbitrary image proxy, download,
hotlink fallback, SVG delivery, thumbnail derivative or automatic use grant was
added. Existing reportlab/Pillow runtime support verifies raster structure,
format, content hash, maximum bytes and decoded dimensions before delivery.

Private `/api/brand-media?export=true` returns only export-eligible assets.
The image endpoint rechecks source policy/deletion/retention and serves with
private/no-store, nosniff and sandbox headers. No private media index is added
to public static output. Export=false is an application policy, not browser DRM.

## Verification and acceptance

The final affected regression run passed **195 tests**, including identity/parent-name
holds, carousel children, idempotence/overrides, deletion/tombstones, rights and
export, source expiry, metadata-only Reader, authorized logo presentation,
corrupt raster/CRC and decompression bounds, and 2 MB upload handling.
It covers the new media workflow, company directory/compare/tab preparation,
social routes/deletion/cross-provider behavior and remote authentication. The
preceding broader social/comparison/authentication regression passed **175
tests**. These tests use explicitly synthetic pixels and source rows. Two
existing dependency/deprecation warnings remain in the final run.

Record validation passed. Static build wrote **2,429 pages**, built its search
index and passed the unpublished-draft leakage check. A preliminary full-suite
run was stopped while final safety changes were still being made; it is **not
a full-suite pass**. A full exact-head suite and the repository CI merge gates
remain required before merge. This is an isolated candidate, not a release.
The final static build was repeated after the finished template changes and
again passed all 2,429 pages and the draft-leak check.

The offline gallery browser proof verifies contain fit, visible credits,
keyboard/next/Escape/focus, touch, 390 px layout and source inspection with scope
preserved. Its screenshots and continuous recording are explicitly synthetic
UI fixtures under `inbox/brand-media-ui-proof/`; they are not real packaging.
The retained-source proof script is `scripts/verify_retained_brand_media.py`.
Private raw posts, signed image references and videos remain gitignored.

The real retained-source browser proof under `inbox/retained-brand-media-proof/`
passed the actual company → Profile & links → media review → metadata-only
source Reader interaction. It verified the original post/date/account, all five
retained references, omitted gallery, neutral missing-logo fallback, scope on
close, zero browser errors, no mutations/external requests and unchanged copied
SQLite payloads/index. The screenshot and continuous recording demonstrate
that metadata path only; `real_packaging_e2e_success` is explicitly false.

Remaining acceptance blockers: verified image-content classification; an actual
display/storage policy and permitted bytes; an unexpired source or permitted
refresh; fresh free/authorized connector allowance before metered retrieval;
the real initial official-logo/packaging cohort; and stable new-app integration.
Do not report a real packaging end-to-end pass until those conditions are met.
