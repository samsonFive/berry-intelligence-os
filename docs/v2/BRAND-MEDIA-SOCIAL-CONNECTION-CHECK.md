# Brand media: narrow social connection check

Checked November 11, 2026 against the retained local code, configuration,
provider ledgers, raw responses and social SQLite records, followed by an
authenticated read-only inspection of the current production container. No
provider request, purchase, production record change, deployment or new
subscription occurred. Dates below use America/Los_Angeles. A successful
historical retrieval is distinct from current provider availability.

## Connection result

The credentials column reports **current production container** credential
presence, yes/no only. Values were never printed. Existing private local
credential sources also contain Apify and SociaVault credentials, but neither
is injected into the current local shell, inspected local `deploy/.env` or
isolated preview. Credential presence is distinct from validation, enabled
collection, successful retrieval and production activation.

| Provider | Adapter exists | Credentials configured | Enabled environment | Last successful real run | Supported account/post/media retrieval | Specific blocker |
|---|---|---|---|---|---|---|
| Apify | Yes: bounded explicit jobs and shared intake | no | Historical manual local jobs; production has retained imported results, but no injected Apify token or scheduled collector | October 9, 11:21 PDT (`2026-10-09T18:21:16Z`): retained local matched Multiscan LinkedIn sample, five posts. Latest production Apify record capture is October 8, 00:17 PDT. | Facebook page posts; Instagram exact-tag posts, carousel image references and bounded known-parent comments; LinkedIn search/company/detail. X job path exists but Actor is blocked. No broad account-resolution or complete-history claim. | No production token. Fresh free-account, immutable build/schema, endpoint pricing and all-in allowance verification required before any new local launch. Historical mission reservations total $1.90 of $2; remaining conservative reservation $0.10. Media redisplay/retention rights unresolved. |
| SociaVault | Yes: allowlisted multi-platform transport, normalization and manual prepaid job | yes | Production manual prepaid collection enabled; scheduling disabled. Current local/preview configuration disabled. | October 21, 13:24 PDT (`2026-10-21T20:24:10Z`): completed manual batch, 193 observed raw returns; parent status `live` | Eight platforms demonstrated across retained trials; allowlisted LinkedIn company/post, Facebook page posts, Instagram post/hashtag/comments, and platform-specific search/detail/comment media references. Capabilities differ by endpoint; full carousel/history completeness is not established. | Old free trial reached its 42-attempt ceiling and 10-credit reserve. Production prepaid ledger last recorded 5,958 credits on October 21; no fresh provider/account call was made. Retention/redisplay and provider deletion refresh remain unresolved. |
| YouTube Data API v3 | Yes | no | Disabled/unscheduled | None found | Video metadata/thumbnails and sampled comments/replies; no video-byte or transcript permission inferred | `BIOS_SOCIAL_YOUTUBE_KEY` absent; enabled project/free quota not verified. |
| Bluesky AppView | Yes | no | Disabled/unscheduled; endpoint is keyless | None; earlier bounded keyword probe returned HTTP 403 | Search/posts, thread replies and image references | HTTP 403 cause/entitlement unestablished. No bypass attempted. |
| Bluesky Jetstream | Yes, bounded probe | no | Historical explicit local 30-second test only | October 7, 06:02 PDT: connected and received 1,691 frames, zero berry matches | Present-time events; no account/history or matching post-media retrieval demonstrated | No retained matching berry posts. Stream connectivity is not successful packaging retrieval. |
| Google News RSS bakeoff | Yes, supplementary title adapter | no | Historical manual trial | October 7 retained real title records; exact last request timestamp not recovered | Headlines and publisher URLs | Not social account/post or packaging-media retrieval. |

Other direct-platform rows in `docs/v2/social-source-access.json` remain
proposals/access matrices, not implemented native APIs. They must not be
reported as active connectors because a vendor can retrieve that platform.

## Production read-only verification

The existing SSH connection and dedicated operator key were used with
`BatchMode=yes` and `StrictHostKeyChecking=yes`. Default sandbox SSH was blocked
before remote execution; the authorized read-only inspection succeeded after
sandbox escalation. No mutating helper was run. The production container was
selected by matching its configured image against the existing
`/opt/berry-platform-releases/current.json`; exactly one running container
matched. Container configuration and SQLite were read without modification;
SQLite used `mode=ro`. No full environment, secret values, raw post content,
authenticated URLs or private host identifiers were emitted.

Verified production configuration:

- `SOCIAVAULT_API_KEY` present; `APIFY_TOKEN` and
  `BIOS_SOCIAL_YOUTUBE_KEY` absent.
- `BIOS_SOCIAL_MANUAL_COLLECTION=true`,
  `BIOS_SOCIAL_TRIAL_PREVIEW=false`, `ENABLE_SOURCE_POLLING=false`.
- Effective runtime pipeline `social_manual_prepaid`: enabled true, scheduled
  false. Original `social_intelligence`: enabled false, scheduled false.
- Latest completed manual parent job: started
  `2026-10-21T20:21:05Z`, completed `2026-10-21T20:24:10Z`, last success
  `2026-10-21T20:24:10Z`, status `live`, observed raw volume 193. A child
  Facebook page job has status `partial`, last success at the same time, volume
  three. The completed parent batch, rather than the child status alone,
  establishes the last completed run.
- Production ledger: 52 reservations, halted false, balance 5,958 last checked
  `2026-10-21T20:24:10Z`. This is historical stored account metadata, not a new
  entitlement or present balance verification.

Runtime evidence was read from
`/app/runtime/data/configuration/collection_pipelines.json`,
`/app/runtime/inbox/social/observations.sqlite3` and
`/app/runtime/inbox/social/manual-credit-ledger.json`. The code-default fallback
for the pipeline registry was `/app/data/configuration/collection_pipelines.json`;
the effective runtime file was present and used first.

## Reuse findings

Current production contains **631 retained live post identities and 396 media
references**. Acquisition methods are 382 manual prepaid SociaVault records,
233 bounded SociaVault pilot records, and 16 imported Apify records (Facebook
four, Instagram three, LinkedIn nine). These are retained records/reference
counts, not display-eligible pack counts, image-byte acquisition counts or a
claim that every URL remains available. The production store supplies a larger
retained-first starting point without new requests or deployment.

An additional read-only aggregate query verified that all **396 attachments
are `reference_only`**, and **zero have a stored `object_ref`**. Kinds are 267
images, 124 thumbnails and five video references. All have stored state
`available`; this is the retained ingestion state, not a fresh HTTP availability
or rights check. No media bytes were fetched or exported by this inspection.

Automatic approval review initially rejected the proposed SQLite copy because
production account/post/media metadata export was broader than the read-only
inspection authorization. No workaround was attempted. The user then explicitly
answered **"Approve the private snapshot copy"** for the isolated gitignored
inbox. The approved copy succeeded November 11 at 2:29 PM Los Angeles using a
read-only SQLite source, an in-memory backup and captured binary transport.
No remote files were written and no provider was called.

The verified private snapshot contains 631 live records and 396 references,
with zero stored live media objects; 64 fixture rows are excluded from real
reuse. Of the live records, 382 remain unexpired and 249 have expired; 221 media
references remain within source retention. SQLite integrity passed. Copy/hash receipts are
under `inbox/brand-media-production-retained-preview/` and remain gitignored.
Two-company reuse scanned all 631 records, skipped 249 expired records and
registered 18 image/thumbnail references: 15 exact historical official-account
matches and three proposed links. It excluded one video reference. The repeat
created zero records and the copied database hash remained unchanged. All 18
remain unclassified and display-ineligible. The user will identify an existing
media-use policy; none has been applied without its actual terms and scope.

The retained initial funded SociaVault SQLite has **205 unique live records**:
Facebook 6, Instagram 40, LinkedIn 38, Reddit 53 and X 68. These include noise and
unreadable/unqualified records; they are not 205 eligible packaging matches.
There are **118 media references** in those payloads. References do not establish
downloaded bytes, current availability or permission to display.

The retained matched Multiscan test is a concrete media-exposure gap: the five
post identities/texts match across providers; Apify supplied media references on
four posts where SociaVault company summaries supplied none. The existing
source/native-ID storage and collection receipts support combining those
references without a second provider-specific post. This is relevant reuse,
not proof that those images are berry packaging.

The retained Instagram exact-tag trial includes carousels with 7, 4 and 6 image
entries. It also includes irrelevant content and recipes. Reuse every retained
child reference when the post and usage basis qualify; do not assume a cover
image is the full carousel, or that a hashtag establishes an official account.

Existing cross-provider storage preserves media across sparse updates and
retains removal tombstones. Inspected Facebook CDN path variants deduplicate
without generic query stripping. Other signed URLs must not be collapsed by
guessing that they depict the same asset.

## Evidence locations

Code/configuration in this checkout:

- `app/services/social_intelligence/apify_jobs.py`: Actor allowlist, explicit
  enablement, durable reservations, immutable build and bounded execution.
- `app/services/social_intelligence/sociavault_pilot.py`: task allowlist,
  private credential loader, free-account/reserve guards and retained responses.
- `app/services/social_intelligence/manual_collection.py`: explicit operator
  flag, prepaid reservations, account reads, known Facebook pages, limits and
  manual jobs; a separate lane from the free trial.
- `app/services/social_intelligence/adapters.py`: actual direct Bluesky and
  YouTube paths; mock success must remain separate from a real run.
- `app/services/social_intelligence/provider_routing.py` and
  `docs/v2/SOCIAL-PROVIDER-ROUTING.md`: retained-first discovery and targeted
  LinkedIn detail route.
- `data/configuration/collection_pipelines.json`: both social lanes disabled and
  unscheduled in checked-in configuration.
- `deploy/docker-compose.yml`: manual collection defaults off; credentials are
  environment inputs, not checked-in values.
- `docs/v2/SOCIAL-MANUAL-PRODUCTION.md`: October 12 operator-purchased $29 pack,
  initial funded batch and limitations. The authorization is historical evidence;
  it does not authorize another purchase or top-up.

Private retained root on the operator's machine:
`C:/Users/Johnny/Downloads/sscanar/work/berry-intelligence-os/inbox/social-bakeoff/`.
It is absent from public Git and must stay private:

- `apify-2026-10-07/ledger.json`, `final-audit.json`,
  `linkedin-matched-multiscan-20261009-items.json`,
  `linkedin-matched-multiscan-20261009-normalized-import.json` and
  `instagram-exact-blueberries-items.json`.
- `sociavault-multiplatform-2026-10-07/ledger.json` and retained response JSON.
- `quality-audit-2026-10-08/active-provider-policy.json`: collection and scheduling
  disabled, SociaVault trial reserve reached, selected Apify Actor and cash cap.
- `production-initial-20261012/social/observations.sqlite3`:
  `observations`, `jobs`, `collection_receipts`, deletion and media tombstones.
  Parent job `social-manual-33973f555d6642898a441e99467b9a42` completed with 26
  successful request results. Its 215 raw returns became 205 unique records.
- `production-initial-20261012/social/manual-credit-ledger.json`: 26 durable
  reservations, historical balance 5,984, no halt, last balance check at
  `2026-10-13T00:44:08Z`.
- `stream-2026-10-07/jetstream.json` and supplementary `news-2026-10-07/`,
  `news-rest-2026-10-07/`, `news-repeat-2026-10-07/normalized.json`.

Only credential presence was inspected in the existing private credential file
and current production container; no credential value was copied into this
checkout or report. The read-only production follow-up supersedes the earlier
local-only uncertainty about current production flags and latest retained run.

## Official-site discovery without another provider

`app/services/brand_media_discovery.py` accepts bounded HTML and an already
verified official page URL. It extracts only schema Organization/Brand `logo`
and Product `image` references, supports JSON-LD graphs/ImageObjects, retains
declared subject names/brands/identifiers, and supplies stable candidate IDs.
Expected-name comparison uses only an exact normalized declared subject name;
it never treats parent-domain ownership or Product.brand as a subject match.
Open Graph, favicons, search thumbnails, general images and Recipe images are
not selected. Product images remain packaging candidates until their content
is inspected. A schema declaration does not verify identity or usage rights.

Every discovery candidate starts unverified with display/cache/export disabled
and unresolved policy. The shared media workflow must establish the intended
audience's actual usage basis and eligible delivery before rendering an image.
Policy sources and required credit must accompany approval; private login,
official origin, confidence and hotlinking do not grant rights.

This module performs no network calls. It reuses
`feed_first_reader.is_public_http_url` and the social intake `safe_url` guard,
with stricter HTTPS, port, hostname and control-character restrictions.
These are reference checks, not a DNS or connection-safety guarantee.

Existing `_bounded_public_response` in `feed_first_reader.py` provides manual
redirect validation, response size/time caps and no automatic redirect following.
It checks lexical hosts; a future brand-image downloader must additionally
validate resolved addresses and the actual connection on every redirect to
prevent DNS-to-private/rebinding access. No brand-image fetcher/proxy was added.
Any approved future acquisition should bound request count and refresh cadence,
respect source restrictions, validate content type/magic/size/dimensions, and
sanitize or rasterize SVG only where derivative permission is established.
