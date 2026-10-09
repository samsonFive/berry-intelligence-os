# Pending articles connect to variety review

Active publication drafts with available original article text now contribute
names to private variety identity review. Their article links open the original
text and image in the existing Reader. Saving a selected pending story keeps it
in Personal Digest without approving the publication or the variety.

This is domain-depth and reliability work under CAT-01/CAT-02/TD-116. It uses
the existing publication, article-acquisition, Reader, identity-candidate and
personal-state stores. No provider, scraper, domain schema or public corpus was
added. The accepted Glasshouse shell remains intact.

## Real source and the miss it exposed

The operator-selected [Italian Berry G-Viva article](https://italianberry.it/en/news/g-viva-g-berries-raspberry)
was staged under the existing `source-news-search-italian-berry` Source and
processed by `process_discovered_article`, with no AI completer. Its public
publisher date is August 29, 2026. The private isolated preview produced:

| Observation | Actual result |
|---|---|
| Original acquisition | Successful; 35 paragraph-indexed paragraphs, 1,506 words |
| Publication | `ev-media-08d1f773f7c106898ae0`, still `draft` / `in_review` |
| First article-name check | Zero names: the existing patterns missed the single-name declaration |
| Corrected check | One explicit source name, G‑Viva, scoped to Raspberry |
| Repeated pipeline pass | Staging unchanged; same pending publication; no body reacquisition |
| Native Reader | Original text and image, Unreviewed label, publisher link and variety-review link |
| Native Personal Digest | Saving the story shows its image, Unreviewed label and Saved by you origin |
| Catalog result | One additional private candidate key; no approved new Variety |

The added recognizer accepts bounded variety/cultivar naming declarations such
as “will be called,” with exactly one crop in that paragraph. It preserves
Unicode hyphens and rejects ambiguous-crop, speculative and negated cases.
It does not scan arbitrary capitalized prose. The article's selection code is
not automatically equated to its commercial name, and its production, trait,
territory, breeder and rights claims remain unapproved.

Original text and runtime files remain under ignored
`inbox/european-portfolio-followup/apg-preview-runtime/inbox`. They are not
committed, published or assumed present in a production or cloud runtime.
The selected URL was manually supplied from an existing source reference;
this proves acquisition and integration, not automatic discovery recall.

## Current counts and their limits

The opt-in private audit now checks 1,270 known source identities: 1,269
published sources and this pending publication. Two have readable original
text in the isolated workspace: the prior reviewed Hortifrut capture and
this unreviewed stored article. One uses a private Reader capture.

- **103 source-named identities / 32 catalog matches / 71 discoveries** before
  private human identity decisions, versus 102 / 32 / 70 before this source.
- **739 combined candidate keys**, versus 738 before this source.
- **64 canonical Variety records unchanged**, including their existing statuses.
- Published canonical article-body coverage remains **0 / 1,269**. A private
  capture and pending draft do not change that denominator or approve bodies.
- The prior 347 portfolio source sections, 1,064 occurrences and 112 photo
  references are unchanged. Those source observations are not a complete
  portfolio census or a current-rights audit.

The audit emits names, IDs, URLs and review metadata rather than original
article bodies. Its default published-summary-only mode remains separate.
Private outputs remain restricted to inbox locations, excluding public build,
canonical data and artifact folders.

## Preserved gates and selected-source behavior

- Active publication drafts are normalized to Unreviewed in the private
  derived view. An inbox status cannot approve a source.
- Rejected/archived publications, including terminal `review_state`, do not
  contribute bodies. A same-ID older cache cannot resurrect them.
- Canonical published prose wins over any same-ID pending version. A pending
  body is used alongside retained news only when its original URL matches.
- Atomic proposals are not publication articles. Orphan or mismatched Reader
  captures remain excluded, with the existing body and capture size bounds.
- The selected Reader resolves one pending draft, rather than loading the
  publication backlog or rebuilding the candidate universe. Its standalone
  personal page also skips legacy navigation's unnecessary draft scan.
- GET discovery and selected reading do not persist candidates or acquire
  text. Existing explicit capture and **Keep discoveries for review** POSTs
  remain separate actions. Replay preserves prior human decisions and notes.
- Only personally saved or queued pending IDs are added to Digest here.
  Merely opening an article does not add the whole publication backlog.
- Saving, feedback and reading progress keep their existing independent
  state stores; none publishes the source, confirms identity or creates Facts.
- Public/static views do not load pending article inputs or private captures.

The pending presentation names the publisher already present in the configured
Source label, removing its “Site-restricted news search” prefix without
rewriting the stored source. The company-reference caveat now appears on its
own line instead of running directly into the company link.

## Verification

- Final expanded run: **157 tests passed**, one existing ReportLab warning,
  **140.96 seconds**. Covers article-name discovery, candidate decisions,
  selected Reader, Digest, corpus reconciliation, portfolios and company views.
- The final publisher-label and spacing cleanup passes **82 overlapping
  focused tests**, one existing warning, **42.21 seconds**. These runs must
  not be added as unique tests.
- One new no-backlog test exposed the standalone personal Reader's inherited
  nav scan. The production path was fixed; the no-scan assertion was retained.
- Record validation passed. All **2,771 original data JSON files** and the
  canonical expansion guide were preserved. No backend/domain schemas,
  Atomic qualification markers or publication/identity decisions were changed.
- Native desktop review verified the automatic name link, selected source,
  individual Unreviewed provenance and untouched human review controls.
- Native 390px phone review showed original article imagery and saving into
  Digest. Actual client and scroll widths were both **375px**. Alphabetical G
  navigation preserved the name/crop scope and `#candidate-results` anchor.
  A browser observation timed out during navigation; the same live tab then
  verified the completed jump. The viewport was reset and temporary tab closed.
- Browser Reader-position autosave and the intentional isolated saved-story
  mark occurred normally. No publication or identity approval form was submitted.
- Parent [draft #367](https://github.com/samsonFive/berry-intelligence-os/pull/367)
  passes all four checks on `e494eb9ba3dda1c9cd0364270bc4016301228c95`:
  **4,418 passed / 11 skipped / two warnings / 486.63s**. Run 37882948181,
  Python job 113666573480; watcher 68964 completed with exit 0 and was consumed.
  This child requires full CI on its own pushed head.

Native screenshots, retained privately:

- `inbox/european-portfolio-followup/pending-article-candidate-desktop.png`
- `inbox/european-portfolio-followup/pending-article-reader-mobile.png`
- `inbox/european-portfolio-followup/pending-article-candidate-mobile.png`

## Remaining goal scope

CAT-01/CAT-02/TD-116 remain open. Acquisition across the existing published
corpus, complete current/historical portfolios, image-only and other unsupported
declarations, independent human-reviewed real recall, current rights, profile
depth and human catalog authoring remain incomplete. Article Q&A/heading
structure still needs retention through the general article pipeline; the
current indexed-paragraph artifact does not preserve the publisher's full layout.
Pending-pipeline coverage in News and subscribed Digest lists needs a separate
coherent inventory review beyond this selected saved-story flow.

The accepted redesign and visual explainer remain delivered; the combined
release stack still needs an integrated review and tested release packet.
No merge, deployment or rollout beyond the blueberry Landscape checkpoint is
authorized by this review. No user input is needed for the next safe work.
