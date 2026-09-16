# Item decision matrix

Full required-analysis fields for every rehearsal item: source, discovery/acquisition path, content state, provenance completeness, publication-date confidence, body/transcript availability, entity association, duplicate risk, warnings, recommended operator action, and why that recommendation is not an automatic decision.

See REHEARSAL-PACK-INDEX.md for which items are real vs. synthetic, and the individual JSON files under data/imports/publication-review-rehearsal-2026-09-16/items/ for the full record each analysis describes.

## Slot 1 - clearly_readable_article
- **source**: source-rehearsal-fixture-v1 (synthetic; modeled on source-20260915-fruitist-newsroom / source-20260901-blueberrybreeding-newsroom, both real, currently-configured Wave 1 Sources proven capable of a readable body)
- **discovery_acquisition_path**: sitemap_xml/article_rss discovery -> article_acquisition.fetch_article() -> MIN_BODY_CHARS satisfied -> readable_article_body outcome (synthetic fixture reproduces this shape; no live network call was made for this specific item)
- **content_state**: readable_article_body (2 paragraphs, 92 words, above MIN_BODY_CHARS)
- **provenance_completeness**: high -- source_url, published_date with article_body basis, extractor/version, content_sha256 all present
- **publication_date_confidence**: high -- date reconciled from the article body itself (published_date_basis=article_body), per article_refresh._reconcile_published_date's real, preserved logic
- **body_transcript_availability**: full readable body available; no transcript applicable (web_article)
- **entity_association**: berry-blueberry only; no company/geography entity linked -- an analyst would need to confirm or add an entity match before this could support company-level intelligence
- **duplicate_risk**: none observed (synthetic URL/title; no possible_evidence_matches signal)
- **warnings**: ['Synthetic fixture -- no live publisher exists at this URL; do not attempt to fetch it.']
- **recommended_operator_action**: Move to publication review as a normal candidate for Approve, pending entity confirmation.
- **why_not_automatic**: A readable body alone never establishes editorial trust, entity accuracy, or duplicate-freedom -- publication review is a mandatory human gate regardless of content quality, and this mission does not exercise it.

## Slot 2 - transcript_backed_item
- **source**: source-rehearsal-fixture-v1 (synthetic; modeled on the real source-lucentlands-podcast pattern)
- **discovery_acquisition_path**: podcast_rss discovery -> publisher-declared transcript detected (TRANSCRIPT_PUBLISHER) -> acquire_raw_transcript_artifact -> transcript.status=available (synthetic fixture reproduces this shape)
- **content_state**: transcript_available (publisher transcript, 2 segments)
- **provenance_completeness**: medium -- transcript source/language present; no duration or full segment set (deliberately short excerpt)
- **publication_date_confidence**: medium -- feed-declared date only, no independent body/transcript-date corroboration
- **body_transcript_availability**: transcript available; no separate written article body (podcast)
- **entity_association**: berry-blueberry and geography-south-africa only; no company entity linked
- **duplicate_risk**: low in this fixture, but real lucentlands episodes have repeatedly matched already-trusted Evidence by title+date (see rehearsal item 7) -- an operator should always check for that before approving a transcript-backed podcast item
- **warnings**: ['Synthetic fixture -- transcript text is invented, not a real recording.']
- **recommended_operator_action**: Move to publication review; treat the transcript excerpt as a normal candidate for Approve/Save pending a duplicate check against existing podcast-sourced Evidence.
- **why_not_automatic**: A transcript, like a readable article body, is acquired content, not editorial trust -- the same mandatory human review gate applies, and duplicate risk against existing trusted podcast coverage must be checked by a person.

## Slot 3 - metadata_only_item
- **source**: source-business-of-blueberries-podcast (real, currently-configured, collection-eligible)
- **discovery_acquisition_path**: podcast_rss discovery -> no publisher transcript detected -> metadata-only draft (transcript_status=missing) -> untrusted AI enrichment applied to publisher_description
- **content_state**: description_only / metadata-only (no transcript, no written body)
- **provenance_completeness**: medium -- source_url, published_date (feed-declared), publisher_description present; no independently-verified content
- **publication_date_confidence**: medium -- feed-declared date only
- **body_transcript_availability**: none -- summary is AI-generated from publisher metadata, explicitly provenance-tagged as untrusted enrichment, never presented as a verified quote
- **entity_association**: company-ushbc, berry-blueberry (real, real enrichment-suggested link)
- **duplicate_risk**: not checked in this fixture; a real reviewer would still run the same possible_evidence_matches check discovery already performs
- **warnings**: ['AI-enrichment summary is untrusted and must be verified against the original episode before any Fact/Assessment references it.']
- **recommended_operator_action**: Save for further review (metadata-only) or Approve only if the untrusted summary is independently verified against the source audio.
- **why_not_automatic**: An AI-generated summary of metadata is not verified content -- publishing it as trusted Evidence without a human confirming it against the real source would misrepresent an untrusted suggestion as fact.

## Slot 4 - navigation_only_shell
- **source**: source-20260915-oishii-press (real, currently-configured Wave 1 Source)
- **discovery_acquisition_path**: article_rss discovery -> article_acquisition.fetch_article() -> body under MIN_BODY_CHARS -> empty_body/navigation_only_shell outcome -> access-limited metadata-only draft fallback (Stage A had already confirmed TIER_DIRECT relevance)
- **content_state**: navigation_only_shell (empty_body; template summary only, 'Discovered web_article item from Oishii Press Feed')
- **provenance_completeness**: low -- real source_url and published_date present, but no body, no publisher_description, no AI enrichment (enrichment was not applied to this un-readable item)
- **publication_date_confidence**: medium -- feed/sitemap-declared date only, unconfirmed by article body (none was extractable)
- **body_transcript_availability**: none -- confirmed permanently absent on this publisher's own page template, not a transient failure
- **entity_association**: company-oishii, berry-strawberry (correct, from the source's own configured linked_competitor_ids/berry_ids, not content-derived)
- **duplicate_risk**: not assessed -- insufficient content to compare against existing Evidence
- **warnings**: ["This publisher's Press page template has never produced a readable body across 8+ independently sampled items -- do not expect a retry to succeed."]
- **recommended_operator_action**: Reject as non-substantive, or Defer with a note that this publisher's Press feed structurally cannot supply full-text coverage; consider it for a separate structured/headline-only Source class rather than continued retry.
- **why_not_automatic**: Recognizing a shell page is a content-quality judgment; only a human can decide whether the bare metadata (headline + date) is still worth a low-detail trusted mention or should be dropped entirely.

## Slot 5 - uncertain_publication_date
- **source**: source-rehearsal-fixture-v1 (synthetic; modeled on the real, documented calgiant.com stale-lastmod case)
- **discovery_acquisition_path**: sitemap_xml discovery (lastmod=2026-07-15) -> article body fetched -> body's own article:published_time metadata (2021-09-02) reconciled over the feed date, per the real, preserved _reconcile_published_date logic
- **content_state**: readable_article_body, but with a date conflict between discovery feed and article body
- **provenance_completeness**: medium -- both dates are present and both are recorded (discovery_provenance.discovery_published_date preserves the discarded feed value, per real, existing behavior)
- **publication_date_confidence**: low until reviewed -- a 5-year gap between feed lastmod and body date is exactly the shape of a republish-timestamp artifact, but only a human can confirm the article itself is really from 2021 and not a genuine 2026 republish with old content reused
- **body_transcript_availability**: full readable body available
- **entity_association**: none in this fixture
- **duplicate_risk**: elevated -- an old article resurfacing with a fresh-looking timestamp is a known way a stale item can slip past a naive 'is this new' check and appear as a duplicate of, or contradiction with, an already-covered older event
- **warnings**: ['published_date_basis=discovery_feed default was already overridden here (article_body wins) -- but the underlying date GAP itself still needs human judgment about whether the story is current.']
- **recommended_operator_action**: Defer/flag for date verification -- confirm whether this is a genuine republish (still newsworthy) or an artifact of a sitemap/CMS migration before treating it as current intelligence.
- **why_not_automatic**: Reconciling which date field to store is mechanical (already automated); judging whether an old story is being presented as new competitive intelligence is an editorial judgment call this pipeline correctly leaves to a person.

## Slot 6 - missing_or_weak_entity_match
- **source**: source-lucentlands-podcast (real, currently-configured, collection-eligible)
- **discovery_acquisition_path**: podcast_rss discovery -> deterministic-relevance-v1 screener scored 'process' on general agricultural/logistics signal -> AI enrichment applied -> no entity_ids or berry_ids populated
- **content_state**: description_only / metadata-only with an AI-generated summary; adjacent, not direct, topical relevance
- **provenance_completeness**: medium -- source/date/summary present, but no entity linkage at all
- **publication_date_confidence**: medium -- feed-declared date only
- **body_transcript_availability**: none (metadata-only draft; no transcript)
- **entity_association**: none -- entity_ids=[] and berry_ids=[] on the real record; the deterministic screener correctly identified general logistics/export signal without a berry-specific or company-specific match
- **duplicate_risk**: low observed, but not verifiable without a real entity anchor to compare against
- **warnings**: ['No berry or company entity is linked -- this item cannot support any entity-scoped intelligence (Company Profile, Variety Profile, Watchlist) until an analyst adds one, if warranted.']
- **recommended_operator_action**: Defer/correction-required: an analyst should decide whether this is genuinely berry-adjacent competitive intelligence worth a manual entity tag, or whether it belongs outside this corpus entirely.
- **why_not_automatic**: Entity linkage determines what a record can ever be used for downstream (Company/Variety/Geography pages, Watchlists); guessing an entity to force a match would risk misattributing general agricultural content as company- or variety-specific intelligence.

## Slot 7 - duplicate_probable_duplicate
- **source**: source-lucentlands-podcast (real, currently-configured, collection-eligible)
- **discovery_acquisition_path**: podcast_rss discovery -> media_discovery.py's own possible_evidence_matches check flagged an exact title+date match against an already-trusted record BEFORE any draft/acquisition step ran
- **content_state**: discovery_stage_only -- no draft was ever created for this item in this run
- **provenance_completeness**: high on the trusted side (already-published Evidence with full provenance); the re-discovered item itself carries only feed metadata
- **publication_date_confidence**: high -- both records agree exactly (2025-10-28)
- **body_transcript_availability**: the already-trusted record has none either (podcast, no transcript stored)
- **entity_association**: matches the trusted record's own company-fall-creek-farm-and-nursery / geography-south-africa linkage
- **duplicate_risk**: high (medium confidence per the real signal, but exact title+date match on a re-discovered feed entry is one of the strongest natural duplicate signatures this pipeline detects)
- **warnings**: ['Do not create a second draft or Evidence record for this item -- it very likely represents the same real-world episode already trusted under ev-lucentlands-scaling-blueberry-industry-2025.']
- **recommended_operator_action**: Reject/dismiss as a probable duplicate, or, if a reviewer wants to double-check, compare against the existing trusted record's own review history before taking any action.
- **why_not_automatic**: possible_evidence_matches is a deterministic title/date heuristic, not proof of identity -- two distinct real episodes could coincidentally share a title, and only a human comparing both records can confirm they are the same event before dismissing the new one.

## Slot 8 - corrected_or_upgraded_acquisition
- **source**: source-rehearsal-fixture-v1 (synthetic; modeled on the real article_identity_probe mechanism, exercised for any existing web_article representation on a repeat collection pass)
- **discovery_acquisition_path**: existing draft/Evidence representation already on file -> a later collection pass re-fetches the same canonical_url -> article_acquisition.fetch_article() succeeds again -> content_sha256 differs from the originally-stored hash -> CONTENT_CHANGED probe recorded, original representation left untouched
- **content_state**: article_update_detected (a structural, non-destructive probe result, not a new draft and not an overwrite)
- **provenance_completeness**: high -- both the prior and newly-observed content hashes, and the check timestamp, are recorded
- **publication_date_confidence**: unchanged from the original representation; a content change does not by itself imply a new publication date
- **body_transcript_availability**: the newly-fetched body exists only transiently during the probe; it was never persisted over the original representation
- **entity_association**: unchanged from the original representation
- **duplicate_risk**: not a duplicate -- this is the same URL/representation being re-checked, the opposite case from item 7
- **warnings**: ['A content change on the same URL could mean a correction, a substantive update, or an unrelated site redesign -- the probe alone cannot distinguish which.']
- **recommended_operator_action**: Inspect the private article identity probe and decide whether the original draft/Evidence needs a manual correction, a new supplementary record, or no action.
- **why_not_automatic**: Silently overwriting a reviewed or trusted representation whenever a publisher edits their page would erase review history and could launder an unrelated site change into what looks like a content update -- this project's real code deliberately never does this without a human decision.

## Slot 9 - rejection_candidate
- **source**: source-20260915-oishii-press (real, currently-configured Wave 1 Source)
- **discovery_acquisition_path**: article_rss discovery -> article_acquisition.fetch_article() -> empty_body/navigation_only_shell (same confirmed permanent pattern as item 4, a second independent sample) -> access-limited metadata-only draft fallback
- **content_state**: navigation_only_shell (empty_body; template summary only)
- **provenance_completeness**: low -- same shape as item 4
- **publication_date_confidence**: medium -- feed-declared date only
- **body_transcript_availability**: none, confirmed permanently absent (this is the second independent Oishii item in this pack showing the identical failure -- see also item 4 and the 8-sample diagnostic in artifacts/readable-acquisition-canary-v1/)
- **entity_association**: company-oishii, berry-strawberry (source-configured, not content-derived)
- **duplicate_risk**: not assessed -- insufficient content
- **warnings**: ["Repeat confirmation (this pack's second independent Oishii sample) that this publisher's Press feed structurally cannot supply full-text coverage."]
- **recommended_operator_action**: Reject -- two independently-sampled items from this exact feed both fail identically; retrying acquisition is not expected to succeed, and continuing to route these into review adds reviewer load with no realistic upside.
- **why_not_automatic**: Even a well-evidenced pattern (2 samples here; 8 across this mission's full diagnostic history) is a recommendation, not proof for every future item -- a human should confirm before any Source-level policy change (e.g., excluding Oishii from future review queues) is made, since this mission's own scope forbids altering extraction/collection configuration.

## Slot 10 - defer_or_correction_required
- **source**: source-lucentlands-podcast (real, currently-configured, collection-eligible)
- **discovery_acquisition_path**: podcast_rss discovery -> deterministic-relevance-v1 screener scored 'process' -> AI enrichment applied, and the enrichment's own why_it_matters text explicitly notes the content is general-agriculture rather than berry-sector-specific
- **content_state**: description_only / metadata-only with an AI-generated summary that itself flags scope uncertainty
- **provenance_completeness**: medium -- source/date/summary present; the AI enrichment's own caveat is a real, useful provenance signal, not a gap
- **publication_date_confidence**: medium -- feed-declared date only
- **body_transcript_availability**: none (metadata-only draft; no transcript)
- **entity_association**: none -- entity_ids=[] and berry_ids=[], same real gap pattern as item 6, but here the AI enrichment's own text already surfaces the scope question rather than silently omitting it
- **duplicate_risk**: not assessed
- **warnings**: ["The AI-generated why_it_matters text itself states this source provides 'general agricultural principles rather than berry-sector-specific competitive intelligence' -- an honest, self-flagged scope caveat an operator should read before deciding."]
- **recommended_operator_action**: Defer, or correct scope classification (e.g., tag as adjacent/background rather than direct competitive intelligence) rather than an outright Approve or Reject.
- **why_not_automatic**: Whether adjacent agricultural-practice content belongs in this corpus at all is an editorial scope decision this pipeline correctly declines to make on its own -- the AI enrichment surfaces the question, a human answers it.
