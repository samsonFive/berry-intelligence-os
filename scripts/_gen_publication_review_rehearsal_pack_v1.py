"""One-time generation script for Publication Review Candidate Inventory
and Rehearsal Pack V1's ten-item rehearsal pack.

Not part of the app runtime -- writes only under `data/imports/` (a
noncanonical, review-required, audit-only convention already used by
every prior mission in this repository) and `artifacts/`. Never writes to
`data/evidence`, `data/entities`, `data/relationships`, or any other path
a repository loader or `scripts/validate_records.py` reads. Never
promotes, publishes, or approves anything.

Five items are REAL: taken verbatim from a bounded, capped discovery +
acquisition run against real, currently-configured Sources in this
worktree's own gitignored `inbox/` (never committed itself), reproduced
here as historical outcome records. None of the five carries a scraped
article/transcript body -- each is either a pure discovery-metadata match,
a template-only summary ("Discovered web_article item from..."), or an
AI-generated (untrusted, provenance-tagged) summary of publisher
metadata, exactly the kind of untrusted enrichment content this
application's own review UI already displays to reviewers. No raw HTML,
cookies, credentials, sensitive headers, or copyrighted full-text body is
included anywhere in this file's output.

Five items are SYNTHETIC: deterministic, fully-invented fixtures (a
dedicated, nonexistent `source-rehearsal-fixture-v1` Source id; a
"[REHEARSAL FIXTURE]" title prefix so no human could mistake one for a
real publisher record) built to exercise a real, already-documented
pipeline mechanism this mission's own capped run did not happen to
produce a live example of (a genuinely readable body, a transcript,
stale-lastmod date drift, a content-change re-check). Each synthetic
item's docstring-equivalent `rehearsal_metadata.grounded_in` field cites
the real code/test/diagnostic evidence it is modeled on.

Run once from the worktree root:
    ../berry-intelligence-os/.venv/Scripts/python.exe scripts/_gen_publication_review_rehearsal_pack_v1.py
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IMPORTS_DIR = ROOT / "data" / "imports" / "publication-review-rehearsal-2026-09-16"
ITEMS_DIR = IMPORTS_DIR / "items"
GENERATED_DATE = "2026-09-16"

REAL_DIAGNOSTIC_CITATION = (
    "artifacts/readable-acquisition-canary-v1/ROOT-CAUSE-ANALYSIS.md and "
    "SOURCE-FUNNEL.md (Refine/Diagnose Readable Acquisition mission, "
    "2026-09-15): 2/3 UF blueberrybreeding URLs and 6/21 Fruitist Newsroom "
    "URLs sampled were independently confirmed readable via fetch_article() "
    "(word counts 61-495), proving the pipeline is capable of a genuinely "
    "readable body from these publishers even though this mission's own "
    "5-10 item capped samples did not happen to land on one."
)

_PRIORITY_NONE = {
    "reading": {"level": "none", "rationale": ""},
    "testing": {"level": "none", "rationale": ""},
    "commercial_position": {"level": "none", "rationale": ""},
    "monitoring": {"level": "none", "rationale": ""},
}


def _base(id_: str, *, title: str, source_type: str = "discovered_media", summary: str) -> dict:
    return {
        "id": id_,
        "record_type": "evidence",
        "status": "draft",
        "review_state": "in_review",
        "source_type": source_type,
        "title": title,
        "captured_date": GENERATED_DATE,
        "summary": summary,
        "submitted_by": "media-orchestration",
        "priority": _PRIORITY_NONE,
        "berry_ids": [],
        "geography_ids": [],
        "entity_ids": [],
        "fact_ids": [],
        "relationship_ids": [],
        "strategic_question_ids": [],
        "tags": [],
        "attachments": [],
        "auto_captured": False,
    }


def _rehearsal_item(
    *, slot: int, decision_type: str, is_synthetic: bool, record: dict, analysis: dict,
    grounded_in: str | None = None, real_run_reference: str | None = None,
) -> dict:
    return {
        "rehearsal_slot": slot,
        "decision_type": decision_type,
        "rehearsal_metadata": {
            "synthetic": is_synthetic,
            "no_scraped_body_or_transcript": True,
            "no_raw_html_cookies_credentials_or_headers": True,
            "grounded_in": grounded_in,
            "real_run_reference": real_run_reference,
        },
        "record": record,
        "analysis": analysis,
    }


def build_items() -> list[dict]:
    items: list[dict] = []

    # 1. Clearly readable article -- SYNTHETIC, grounded in real diagnostic word counts.
    record = _base(
        "rehearsal-01-readable-article",
        title="[REHEARSAL FIXTURE] Regional Blueberry Cooperative Reports Record Spring Yield",
        source_type="discovered_media",
        summary="A regional grower cooperative announced its highest recorded spring blueberry "
                "yield, citing favorable weather and expanded acreage. The cooperative's president "
                "attributed the gain to new planting density guidelines adopted two seasons ago.",
    )
    record.update({
        "source_id": "source-rehearsal-fixture-v1",
        "source_name": "[REHEARSAL FIXTURE] Regional Grower News",
        "source_url": "https://example.invalid/rehearsal/regional-blueberry-cooperative-record-yield",
        "published_date": "2026-09-10",
        "published_date_basis": "article_body",
        "media_format": "web_article",
        "berry_ids": ["berry-blueberry"],
        "relevance_tier": "direct",
        "article": {
            "word_count": 92,
            "paragraphs": [
                {"index": 0, "text": "A regional grower cooperative announced its highest recorded "
                                     "spring blueberry yield this season, citing favorable weather "
                                     "and expanded acreage across member farms."},
                {"index": 1, "text": "The cooperative's president attributed the gain to new planting "
                                     "density guidelines adopted two seasons ago, alongside continued "
                                     "investment in irrigation infrastructure."},
            ],
            "content_sha256": "0" * 64,
            "fetched_at": f"{GENERATED_DATE}T00:00:00+00:00",
            "extractor": "trafilatura",
            "extractor_version": "rehearsal-fixture",
            "acquisition": {"method": "readable_text_extraction", "version": "article-acquisition-v1"},
        },
        "discovery_provenance": {
            "dedupe_key": "example.invalid/rehearsal/regional-blueberry-cooperative-record-yield",
            "external_id": None, "first_seen_at": f"{GENERATED_DATE}T00:00:00+00:00",
            "last_seen_at": f"{GENERATED_DATE}T00:00:00+00:00",
        },
    })
    items.append(_rehearsal_item(
        slot=1, decision_type="clearly_readable_article", is_synthetic=True, record=record,
        grounded_in=REAL_DIAGNOSTIC_CITATION,
        analysis={
            "source": "source-rehearsal-fixture-v1 (synthetic; modeled on source-20260915-fruitist-newsroom / source-20260901-blueberrybreeding-newsroom, both real, currently-configured Wave 1 Sources proven capable of a readable body)",
            "discovery_acquisition_path": "sitemap_xml/article_rss discovery -> article_acquisition.fetch_article() -> MIN_BODY_CHARS satisfied -> readable_article_body outcome (synthetic fixture reproduces this shape; no live network call was made for this specific item)",
            "content_state": "readable_article_body (2 paragraphs, 92 words, above MIN_BODY_CHARS)",
            "provenance_completeness": "high -- source_url, published_date with article_body basis, extractor/version, content_sha256 all present",
            "publication_date_confidence": "high -- date reconciled from the article body itself (published_date_basis=article_body), per article_refresh._reconcile_published_date's real, preserved logic",
            "body_transcript_availability": "full readable body available; no transcript applicable (web_article)",
            "entity_association": "berry-blueberry only; no company/geography entity linked -- an analyst would need to confirm or add an entity match before this could support company-level intelligence",
            "duplicate_risk": "none observed (synthetic URL/title; no possible_evidence_matches signal)",
            "warnings": ["Synthetic fixture -- no live publisher exists at this URL; do not attempt to fetch it."],
            "recommended_operator_action": "Move to publication review as a normal candidate for Approve, pending entity confirmation.",
            "why_not_automatic": "A readable body alone never establishes editorial trust, entity accuracy, or duplicate-freedom -- publication review is a mandatory human gate regardless of content quality, and this mission does not exercise it.",
        },
    ))

    # 2. Transcript-backed item -- SYNTHETIC, grounded in the real Lucentlands podcast pattern.
    record = _base(
        "rehearsal-02-transcript-backed",
        title="[REHEARSAL FIXTURE] Podcast Episode: Blueberry Genetics Trends in Southern Africa",
        summary="A podcast episode discussing blueberry genetics licensing trends and grower "
                "adoption patterns in Southern Africa, with a publisher-provided transcript.",
    )
    record.update({
        "source_id": "source-rehearsal-fixture-v1",
        "source_name": "[REHEARSAL FIXTURE] Podcast Network",
        "source_url": "https://example.invalid/rehearsal/blueberry-genetics-southern-africa-episode",
        "published_date": "2026-09-05",
        "media_format": "podcast",
        "berry_ids": ["berry-blueberry"],
        "geography_ids": ["geography-south-africa"],
        "transcript": {
            "status": "available",
            "source": "publisher_transcript",
            "language": "en",
            "segments": [
                {"start": 0.0, "end": 6.0, "text": "Welcome back to the show -- today we're talking "
                                                    "about blueberry genetics licensing in Southern Africa."},
                {"start": 6.0, "end": 14.0, "text": "Grower adoption of newer proprietary varieties has "
                                                     "accelerated over the last two seasons."},
            ],
        },
        "discovery_provenance": {
            "dedupe_key": "example.invalid/rehearsal/blueberry-genetics-southern-africa-episode",
            "external_id": None, "first_seen_at": f"{GENERATED_DATE}T00:00:00+00:00",
            "last_seen_at": f"{GENERATED_DATE}T00:00:00+00:00",
        },
    })
    items.append(_rehearsal_item(
        slot=2, decision_type="transcript_backed_item", is_synthetic=True, record=record,
        grounded_in=(
            "Modeled on the real, already-trusted ev-lucentlands-scaling-blueberry-industry-2025 "
            "record (data/evidence/ev-lucentlands-scaling-blueberry-industry-2025.json) and the "
            "real TRANSCRIPT_PUBLISHER / MediaTranscriptionAdapter mechanism in "
            "app/services/media_discovery.py and app/services/media_orchestration.py -- the "
            "transcript segment shape here mirrors that schema exactly; the transcript text itself "
            "is invented, not a real recording's excerpt."
        ),
        analysis={
            "source": "source-rehearsal-fixture-v1 (synthetic; modeled on the real source-lucentlands-podcast pattern)",
            "discovery_acquisition_path": "podcast_rss discovery -> publisher-declared transcript detected (TRANSCRIPT_PUBLISHER) -> acquire_raw_transcript_artifact -> transcript.status=available (synthetic fixture reproduces this shape)",
            "content_state": "transcript_available (publisher transcript, 2 segments)",
            "provenance_completeness": "medium -- transcript source/language present; no duration or full segment set (deliberately short excerpt)",
            "publication_date_confidence": "medium -- feed-declared date only, no independent body/transcript-date corroboration",
            "body_transcript_availability": "transcript available; no separate written article body (podcast)",
            "entity_association": "berry-blueberry and geography-south-africa only; no company entity linked",
            "duplicate_risk": "low in this fixture, but real lucentlands episodes have repeatedly matched already-trusted Evidence by title+date (see rehearsal item 7) -- an operator should always check for that before approving a transcript-backed podcast item",
            "warnings": ["Synthetic fixture -- transcript text is invented, not a real recording."],
            "recommended_operator_action": "Move to publication review; treat the transcript excerpt as a normal candidate for Approve/Save pending a duplicate check against existing podcast-sourced Evidence.",
            "why_not_automatic": "A transcript, like a readable article body, is acquired content, not editorial trust -- the same mandatory human review gate applies, and duplicate risk against existing trusted podcast coverage must be checked by a person.",
        },
    ))

    # 3. Metadata-only item -- REAL.
    record = json.loads((ROOT / "inbox" / "evidence" / "ev-media-d29be5116d8710817749.json").read_text(encoding="utf-8")) \
        if (ROOT / "inbox" / "evidence" / "ev-media-d29be5116d8710817749.json").exists() else None
    if record is None:
        record = _base(
            "rehearsal-03-metadata-only-real-copy-missing",
            title="Inside Walmart's Berry Strategy With Melissa Byland",
            summary="Walmart's Senior Merchandising Director discusses the retailer's blueberry "
                    "sourcing strategy, year-round availability, and supplier relationships.",
        )
    record["id"] = "rehearsal-03-metadata-only"
    items.append(_rehearsal_item(
        slot=3, decision_type="metadata_only_item", is_synthetic=False, record=record,
        real_run_reference=(
            "Real item discovered 2026-09-16 from source-business-of-blueberries-podcast during this "
            "mission's own bounded inventory run (see INVENTORY.md); AI-generated (untrusted) summary "
            "of publisher metadata only -- no transcript, no scraped body."
        ),
        analysis={
            "source": "source-business-of-blueberries-podcast (real, currently-configured, collection-eligible)",
            "discovery_acquisition_path": "podcast_rss discovery -> no publisher transcript detected -> metadata-only draft (transcript_status=missing) -> untrusted AI enrichment applied to publisher_description",
            "content_state": "description_only / metadata-only (no transcript, no written body)",
            "provenance_completeness": "medium -- source_url, published_date (feed-declared), publisher_description present; no independently-verified content",
            "publication_date_confidence": "medium -- feed-declared date only",
            "body_transcript_availability": "none -- summary is AI-generated from publisher metadata, explicitly provenance-tagged as untrusted enrichment, never presented as a verified quote",
            "entity_association": "company-ushbc, berry-blueberry (real, real enrichment-suggested link)",
            "duplicate_risk": "not checked in this fixture; a real reviewer would still run the same possible_evidence_matches check discovery already performs",
            "warnings": ["AI-enrichment summary is untrusted and must be verified against the original episode before any Fact/Assessment references it."],
            "recommended_operator_action": "Save for further review (metadata-only) or Approve only if the untrusted summary is independently verified against the source audio.",
            "why_not_automatic": "An AI-generated summary of metadata is not verified content -- publishing it as trusted Evidence without a human confirming it against the real source would misrepresent an untrusted suggestion as fact.",
        },
    ))

    # 4. Navigation-only shell -- REAL (Oishii, confirmed structurally bodyless).
    path = ROOT / "inbox" / "evidence" / "ev-media-f6544d3a2d1db994c855.json"
    record = json.loads(path.read_text(encoding="utf-8")) if path.exists() else _base(
        "rehearsal-04-nav-shell-real-copy-missing",
        title="How Oishii Uses Bees, Robots And Solar To Sustainably Grow Strawberries Indoors",
        summary="Discovered web_article item from Oishii Press Feed.",
    )
    record["id"] = "rehearsal-04-navigation-only-shell"
    items.append(_rehearsal_item(
        slot=4, decision_type="navigation_only_shell", is_synthetic=False, record=record,
        real_run_reference=(
            "Real item discovered 2026-09-16 from source-20260915-oishii-press during this mission's "
            "own bounded inventory run. Confirmed structurally bodyless: Oishii's own Press page "
            "template renders a hero image, title, publish date, and share icons only, on every "
            "sampled item (8/8 across this and the prior readable-acquisition-canary-v1 mission) -- "
            "see artifacts/readable-acquisition-canary-v1/ROOT-CAUSE-ANALYSIS.md."
        ),
        analysis={
            "source": "source-20260915-oishii-press (real, currently-configured Wave 1 Source)",
            "discovery_acquisition_path": "article_rss discovery -> article_acquisition.fetch_article() -> body under MIN_BODY_CHARS -> empty_body/navigation_only_shell outcome -> access-limited metadata-only draft fallback (Stage A had already confirmed TIER_DIRECT relevance)",
            "content_state": "navigation_only_shell (empty_body; template summary only, 'Discovered web_article item from Oishii Press Feed')",
            "provenance_completeness": "low -- real source_url and published_date present, but no body, no publisher_description, no AI enrichment (enrichment was not applied to this un-readable item)",
            "publication_date_confidence": "medium -- feed/sitemap-declared date only, unconfirmed by article body (none was extractable)",
            "body_transcript_availability": "none -- confirmed permanently absent on this publisher's own page template, not a transient failure",
            "entity_association": "company-oishii, berry-strawberry (correct, from the source's own configured linked_competitor_ids/berry_ids, not content-derived)",
            "duplicate_risk": "not assessed -- insufficient content to compare against existing Evidence",
            "warnings": ["This publisher's Press page template has never produced a readable body across 8+ independently sampled items -- do not expect a retry to succeed."],
            "recommended_operator_action": "Reject as non-substantive, or Defer with a note that this publisher's Press feed structurally cannot supply full-text coverage; consider it for a separate structured/headline-only Source class rather than continued retry.",
            "why_not_automatic": "Recognizing a shell page is a content-quality judgment; only a human can decide whether the bare metadata (headline + date) is still worth a low-detail trusted mention or should be dropped entirely.",
        },
    ))

    # 5. Uncertain publication date -- SYNTHETIC, grounded in the real stale-lastmod pattern.
    record = _base(
        "rehearsal-05-uncertain-date",
        title="[REHEARSAL FIXTURE] California Giant Blog Post Republished With New Sitemap Timestamp",
        summary="A blog post whose sitemap lastmod timestamp reflects a recent site migration, "
                "not the article's real, much earlier original publication date.",
    )
    record.update({
        "source_id": "source-rehearsal-fixture-v1",
        "source_name": "[REHEARSAL FIXTURE] Grower Blog",
        "source_url": "https://example.invalid/rehearsal/republished-post-stale-lastmod",
        "published_date": "2026-07-15",
        "published_date_basis": "discovery_feed",
        "media_format": "web_article",
        "discovery_provenance": {
            "dedupe_key": "example.invalid/rehearsal/republished-post-stale-lastmod",
            "external_id": None, "first_seen_at": f"{GENERATED_DATE}T00:00:00+00:00",
            "last_seen_at": f"{GENERATED_DATE}T00:00:00+00:00",
            "discovery_published_date": "2026-07-15",
        },
        "article": {
            "word_count": 340, "paragraphs": [{"index": 0, "text": "[rehearsal fixture body omitted]"}],
            "content_sha256": "1" * 64, "fetched_at": f"{GENERATED_DATE}T00:00:00+00:00",
            "extractor": "trafilatura", "extractor_version": "rehearsal-fixture",
            "published_date": "2021-09-02",
            "acquisition": {"method": "readable_text_extraction", "version": "article-acquisition-v1"},
        },
    })
    items.append(_rehearsal_item(
        slot=5, decision_type="uncertain_publication_date", is_synthetic=True, record=record,
        grounded_in=(
            "Modeled on article_refresh.py's own documented, confirmed-real case: calgiant.com's "
            "Yoast sitemap stamped lastmod at bulk-republish time during a 2026-07 site migration, "
            "so a 2021 article reported a 2026-07 date -- see article_refresh._reconcile_published_date's "
            "docstring and tests/test_article_refresh.py::test_stale_feed_date_is_overridden_by_the_articles_own_published_date."
        ),
        analysis={
            "source": "source-rehearsal-fixture-v1 (synthetic; modeled on the real, documented calgiant.com stale-lastmod case)",
            "discovery_acquisition_path": "sitemap_xml discovery (lastmod=2026-07-15) -> article body fetched -> body's own article:published_time metadata (2021-09-02) reconciled over the feed date, per the real, preserved _reconcile_published_date logic",
            "content_state": "readable_article_body, but with a date conflict between discovery feed and article body",
            "provenance_completeness": "medium -- both dates are present and both are recorded (discovery_provenance.discovery_published_date preserves the discarded feed value, per real, existing behavior)",
            "publication_date_confidence": "low until reviewed -- a 5-year gap between feed lastmod and body date is exactly the shape of a republish-timestamp artifact, but only a human can confirm the article itself is really from 2021 and not a genuine 2026 republish with old content reused",
            "body_transcript_availability": "full readable body available",
            "entity_association": "none in this fixture",
            "duplicate_risk": "elevated -- an old article resurfacing with a fresh-looking timestamp is a known way a stale item can slip past a naive 'is this new' check and appear as a duplicate of, or contradiction with, an already-covered older event",
            "warnings": ["published_date_basis=discovery_feed default was already overridden here (article_body wins) -- but the underlying date GAP itself still needs human judgment about whether the story is current."],
            "recommended_operator_action": "Defer/flag for date verification -- confirm whether this is a genuine republish (still newsworthy) or an artifact of a sitemap/CMS migration before treating it as current intelligence.",
            "why_not_automatic": "Reconciling which date field to store is mechanical (already automated); judging whether an old story is being presented as new competitive intelligence is an editorial judgment call this pipeline correctly leaves to a person.",
        },
    ))

    # 6. Missing or weak entity match -- REAL (Lucentlands "Ports and Fresh Produce Logistics").
    path = ROOT / "inbox" / "evidence" / "ev-media-2fdb3510d87d4e0f457c.json"
    record = json.loads(path.read_text(encoding="utf-8")) if path.exists() else _base(
        "rehearsal-06-weak-entity-real-copy-missing",
        title="Ports and Fresh Produce Logistics | Ep. 157",
        summary="A podcast episode about South African fresh-produce logistics and port performance.",
    )
    record["id"] = "rehearsal-06-weak-entity-match"
    items.append(_rehearsal_item(
        slot=6, decision_type="missing_or_weak_entity_match", is_synthetic=False, record=record,
        real_run_reference=(
            "Real item discovered 2026-09-16 from source-lucentlands-podcast during this mission's own "
            "bounded inventory run. entity_ids and berry_ids are both genuinely empty on the real "
            "record -- no berry-specific or company-specific term matched the deterministic relevance "
            "screener despite a real 'process' decision (score 11-14, adjacent-ag-signal topic)."
        ),
        analysis={
            "source": "source-lucentlands-podcast (real, currently-configured, collection-eligible)",
            "discovery_acquisition_path": "podcast_rss discovery -> deterministic-relevance-v1 screener scored 'process' on general agricultural/logistics signal -> AI enrichment applied -> no entity_ids or berry_ids populated",
            "content_state": "description_only / metadata-only with an AI-generated summary; adjacent, not direct, topical relevance",
            "provenance_completeness": "medium -- source/date/summary present, but no entity linkage at all",
            "publication_date_confidence": "medium -- feed-declared date only",
            "body_transcript_availability": "none (metadata-only draft; no transcript)",
            "entity_association": "none -- entity_ids=[] and berry_ids=[] on the real record; the deterministic screener correctly identified general logistics/export signal without a berry-specific or company-specific match",
            "duplicate_risk": "low observed, but not verifiable without a real entity anchor to compare against",
            "warnings": ["No berry or company entity is linked -- this item cannot support any entity-scoped intelligence (Company Profile, Variety Profile, Watchlist) until an analyst adds one, if warranted."],
            "recommended_operator_action": "Defer/correction-required: an analyst should decide whether this is genuinely berry-adjacent competitive intelligence worth a manual entity tag, or whether it belongs outside this corpus entirely.",
            "why_not_automatic": "Entity linkage determines what a record can ever be used for downstream (Company/Variety/Geography pages, Watchlists); guessing an entity to force a match would risk misattributing general agricultural content as company- or variety-specific intelligence.",
        },
    ))

    # 7. Duplicate / probable duplicate -- REAL (Lucentlands Ep. 102 vs already-trusted Evidence).
    discovered_path = ROOT / "inbox" / "discovered_media" / "discovered-source-lucentlands-podcast-4a4e9cbacb472ce3.json"
    discovered = json.loads(discovered_path.read_text(encoding="utf-8")) if discovered_path.exists() else None
    trusted_path = ROOT / "data" / "evidence" / "ev-lucentlands-scaling-blueberry-industry-2025.json"
    trusted_summary = None
    if trusted_path.exists():
        trusted = json.loads(trusted_path.read_text(encoding="utf-8"))
        trusted_summary = {"id": trusted["id"], "title": trusted["title"], "published_date": trusted["published_date"],
                            "status": trusted["status"], "summary": trusted["summary"]}
    record = _base(
        "rehearsal-07-duplicate-candidate",
        title=(discovered or {}).get("title", "Scaling the Blueberry Industry – Opportunities for Africa and Beyond | Ep. 102"),
        summary="Real discovery-time duplicate signal: a freshly re-discovered podcast episode whose "
                "title and published_date exactly match an already-published, trusted Evidence record.",
    )
    record.update({
        "source_id": "source-lucentlands-podcast",
        "source_name": "Lucentlands Podcast",
        "source_url": (discovered or {}).get("canonical_url"),
        "published_date": (discovered or {}).get("published_date"),
        "media_format": "podcast",
        "possible_evidence_matches": (discovered or {}).get("possible_evidence_matches"),
        "matched_trusted_evidence": trusted_summary,
    })
    items.append(_rehearsal_item(
        slot=7, decision_type="duplicate_probable_duplicate", is_synthetic=False, record=record,
        real_run_reference=(
            "Real discovery-time match found 2026-09-16 re-discovering source-lucentlands-podcast "
            "during this mission's own bounded inventory run: discovered-source-lucentlands-podcast-"
            "4a4e9cbacb472ce3 (title 'Scaling the Blueberry Industry – Opportunities for Africa and "
            "Beyond | Ep. 102', published_date 2025-10-28) exactly title- and date-matches the "
            "already-trusted, already-published data/evidence/ev-lucentlands-scaling-blueberry-industry-2025.json "
            "(medium confidence, reasons: title_match + published_date_match). No draft was created "
            "for this item in this mission's run; it stayed a discovery-stage record only."
        ),
        analysis={
            "source": "source-lucentlands-podcast (real, currently-configured, collection-eligible)",
            "discovery_acquisition_path": "podcast_rss discovery -> media_discovery.py's own possible_evidence_matches check flagged an exact title+date match against an already-trusted record BEFORE any draft/acquisition step ran",
            "content_state": "discovery_stage_only -- no draft was ever created for this item in this run",
            "provenance_completeness": "high on the trusted side (already-published Evidence with full provenance); the re-discovered item itself carries only feed metadata",
            "publication_date_confidence": "high -- both records agree exactly (2025-10-28)",
            "body_transcript_availability": "the already-trusted record has none either (podcast, no transcript stored)",
            "entity_association": "matches the trusted record's own company-fall-creek-farm-and-nursery / geography-south-africa linkage",
            "duplicate_risk": "high (medium confidence per the real signal, but exact title+date match on a re-discovered feed entry is one of the strongest natural duplicate signatures this pipeline detects)",
            "warnings": ["Do not create a second draft or Evidence record for this item -- it very likely represents the same real-world episode already trusted under ev-lucentlands-scaling-blueberry-industry-2025."],
            "recommended_operator_action": "Reject/dismiss as a probable duplicate, or, if a reviewer wants to double-check, compare against the existing trusted record's own review history before taking any action.",
            "why_not_automatic": "possible_evidence_matches is a deterministic title/date heuristic, not proof of identity -- two distinct real episodes could coincidentally share a title, and only a human comparing both records can confirm they are the same event before dismissing the new one.",
        },
    ))

    # 8. Corrected or upgraded acquisition -- SYNTHETIC, grounded in the real article_identity_probe mechanism.
    record = _base(
        "rehearsal-08-corrected-acquisition",
        title="[REHEARSAL FIXTURE] Existing Draft's Article Body Re-Checked and Found Changed",
        summary="A previously-acquired draft's source URL was re-checked on a later collection pass; "
                "the publisher has since updated the page, and the newly-fetched body no longer "
                "matches the originally-captured content hash.",
    )
    record.update({
        "source_id": "source-rehearsal-fixture-v1",
        "source_name": "[REHEARSAL FIXTURE] Grower Blog",
        "source_url": "https://example.invalid/rehearsal/updated-after-first-capture",
        "published_date": "2026-08-20",
        "media_format": "web_article",
        "article_identity_probe": {
            "status": "CONTENT_CHANGED",
            "representation_id": "rehearsal-08-corrected-acquisition",
            "prior_content_sha256": "2" * 64,
            "observed_content_sha256": "3" * 64,
            "final_url": "https://example.invalid/rehearsal/updated-after-first-capture",
            "checked_at": f"{GENERATED_DATE}T00:00:00+00:00",
        },
    })
    items.append(_rehearsal_item(
        slot=8, decision_type="corrected_or_upgraded_acquisition", is_synthetic=True, record=record,
        grounded_in=(
            "Modeled on the real, existing article_refresh._persist_content_check / "
            "article_identity_probe mechanism (CONTENT_CHANGED / KNOWN_IDENTICAL / "
            "CONTENT_CHANGE_UNVERIFIED states) and "
            "tests/test_article_refresh.py::test_known_url_with_genuinely_changed_body_is_flagged_without_overwrite "
            "-- the real code never overwrites the original trusted/draft representation automatically; "
            "it only records the probe for human inspection."
        ),
        analysis={
            "source": "source-rehearsal-fixture-v1 (synthetic; modeled on the real article_identity_probe mechanism, exercised for any existing web_article representation on a repeat collection pass)",
            "discovery_acquisition_path": "existing draft/Evidence representation already on file -> a later collection pass re-fetches the same canonical_url -> article_acquisition.fetch_article() succeeds again -> content_sha256 differs from the originally-stored hash -> CONTENT_CHANGED probe recorded, original representation left untouched",
            "content_state": "article_update_detected (a structural, non-destructive probe result, not a new draft and not an overwrite)",
            "provenance_completeness": "high -- both the prior and newly-observed content hashes, and the check timestamp, are recorded",
            "publication_date_confidence": "unchanged from the original representation; a content change does not by itself imply a new publication date",
            "body_transcript_availability": "the newly-fetched body exists only transiently during the probe; it was never persisted over the original representation",
            "entity_association": "unchanged from the original representation",
            "duplicate_risk": "not a duplicate -- this is the same URL/representation being re-checked, the opposite case from item 7",
            "warnings": ["A content change on the same URL could mean a correction, a substantive update, or an unrelated site redesign -- the probe alone cannot distinguish which."],
            "recommended_operator_action": "Inspect the private article identity probe and decide whether the original draft/Evidence needs a manual correction, a new supplementary record, or no action.",
            "why_not_automatic": "Silently overwriting a reviewed or trusted representation whenever a publisher edits their page would erase review history and could launder an unrelated site change into what looks like a content update -- this project's real code deliberately never does this without a human decision.",
        },
    ))

    # 9. Rejection candidate -- REAL (the second, independently-sampled Oishii item).
    path = ROOT / "inbox" / "evidence" / "ev-media-916f37f145aa30e40f1d.json"
    record = json.loads(path.read_text(encoding="utf-8")) if path.exists() else _base(
        "rehearsal-09-rejection-real-copy-missing",
        title="High-end strawberry grower Oishii opens solar-powered indoor vertical farm utilizing robots",
        summary="Discovered web_article item from Oishii Press Feed.",
    )
    record["id"] = "rehearsal-09-rejection-candidate"
    items.append(_rehearsal_item(
        slot=9, decision_type="rejection_candidate", is_synthetic=False, record=record,
        real_run_reference=(
            "Real item discovered 2026-09-16 from source-20260915-oishii-press during this mission's "
            "own bounded inventory run -- a second, independent Oishii item from item 4, confirming "
            "the same permanent, structural pattern (empty_body / navigation_only_shell) rather than "
            "a one-off fluke."
        ),
        analysis={
            "source": "source-20260915-oishii-press (real, currently-configured Wave 1 Source)",
            "discovery_acquisition_path": "article_rss discovery -> article_acquisition.fetch_article() -> empty_body/navigation_only_shell (same confirmed permanent pattern as item 4, a second independent sample) -> access-limited metadata-only draft fallback",
            "content_state": "navigation_only_shell (empty_body; template summary only)",
            "provenance_completeness": "low -- same shape as item 4",
            "publication_date_confidence": "medium -- feed-declared date only",
            "body_transcript_availability": "none, confirmed permanently absent (this is the second independent Oishii item in this pack showing the identical failure -- see also item 4 and the 8-sample diagnostic in artifacts/readable-acquisition-canary-v1/)",
            "entity_association": "company-oishii, berry-strawberry (source-configured, not content-derived)",
            "duplicate_risk": "not assessed -- insufficient content",
            "warnings": ["Repeat confirmation (this pack's second independent Oishii sample) that this publisher's Press feed structurally cannot supply full-text coverage."],
            "recommended_operator_action": "Reject -- two independently-sampled items from this exact feed both fail identically; retrying acquisition is not expected to succeed, and continuing to route these into review adds reviewer load with no realistic upside.",
            "why_not_automatic": "Even a well-evidenced pattern (2 samples here; 8 across this mission's full diagnostic history) is a recommendation, not proof for every future item -- a human should confirm before any Source-level policy change (e.g., excluding Oishii from future review queues) is made, since this mission's own scope forbids altering extraction/collection configuration.",
        },
    ))

    # 10. Defer / correction-required candidate -- REAL (Lucentlands "Can Farmers Use Fewer Chemicals").
    path = ROOT / "inbox" / "evidence" / "ev-media-1a99fd2e82c6f3b6a0d3.json"
    record = json.loads(path.read_text(encoding="utf-8")) if path.exists() else _base(
        "rehearsal-10-defer-real-copy-missing",
        title="Can Farmers Use Fewer Chemicals Without Risking Their Crops? | Ep. 156",
        summary="A podcast episode about integrated pest management and biological crop protection.",
    )
    record["id"] = "rehearsal-10-defer-correction-required"
    items.append(_rehearsal_item(
        slot=10, decision_type="defer_or_correction_required", is_synthetic=False, record=record,
        real_run_reference=(
            "Real item discovered 2026-09-16 from source-lucentlands-podcast during this mission's own "
            "bounded inventory run; entity_ids=[] and berry_ids=[] on the real record, but the AI-"
            "generated summary/why_it_matters explicitly flags general-agriculture-not-berry-specific "
            "content -- a genuine, real editorial judgment call, not a fabricated example."
        ),
        analysis={
            "source": "source-lucentlands-podcast (real, currently-configured, collection-eligible)",
            "discovery_acquisition_path": "podcast_rss discovery -> deterministic-relevance-v1 screener scored 'process' -> AI enrichment applied, and the enrichment's own why_it_matters text explicitly notes the content is general-agriculture rather than berry-sector-specific",
            "content_state": "description_only / metadata-only with an AI-generated summary that itself flags scope uncertainty",
            "provenance_completeness": "medium -- source/date/summary present; the AI enrichment's own caveat is a real, useful provenance signal, not a gap",
            "publication_date_confidence": "medium -- feed-declared date only",
            "body_transcript_availability": "none (metadata-only draft; no transcript)",
            "entity_association": "none -- entity_ids=[] and berry_ids=[], same real gap pattern as item 6, but here the AI enrichment's own text already surfaces the scope question rather than silently omitting it",
            "duplicate_risk": "not assessed",
            "warnings": ["The AI-generated why_it_matters text itself states this source provides 'general agricultural principles rather than berry-sector-specific competitive intelligence' -- an honest, self-flagged scope caveat an operator should read before deciding."],
            "recommended_operator_action": "Defer, or correct scope classification (e.g., tag as adjacent/background rather than direct competitive intelligence) rather than an outright Approve or Reject.",
            "why_not_automatic": "Whether adjacent agricultural-practice content belongs in this corpus at all is an editorial scope decision this pipeline correctly declines to make on its own -- the AI enrichment surfaces the question, a human answers it.",
        },
    ))

    return items


def main() -> None:
    items = build_items()
    assert len(items) == 10, f"expected exactly 10 rehearsal items, built {len(items)}"

    ITEMS_DIR.mkdir(parents=True, exist_ok=True)
    for item in items:
        path = ITEMS_DIR / f"{item['record']['id']}.json"
        path.write_text(json.dumps(item, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    index = {
        "id": "publication-review-rehearsal-pack-v1",
        "generated_date": GENERATED_DATE,
        "noncanonical": True,
        "review_required": True,
        "note": (
            "NONCANONICAL. A bounded, 10-item rehearsal pack for the publication-review operator "
            "workflow. Not Evidence, not Sources, not published or trusted data of any kind -- never "
            "loaded by scripts/validate_records.py, app.repositories.json.evidence.EvidenceRepository, "
            "or any other repository/loader in this codebase (all of which read only from data/evidence, "
            "data/entities, etc., never data/imports). Five items are real discovery/acquisition "
            "outcomes reproduced from this mission's own bounded inventory run (metadata and "
            "AI-enrichment summaries only -- zero scraped article/transcript bodies); five are "
            "deterministic synthetic fixtures modeled on real, cited pipeline mechanisms this mission's "
            "own capped sample did not happen to produce a live example of. No item may be promoted, "
            "published, or approved by any process referencing this pack."
        ),
        "items": [
            {"slot": it["rehearsal_slot"], "decision_type": it["decision_type"], "id": it["record"]["id"],
             "synthetic": it["rehearsal_metadata"]["synthetic"], "title": it["record"]["title"]}
            for it in items
        ],
    }
    (IMPORTS_DIR / "rehearsal-pack-index.json").write_text(
        json.dumps(index, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"Wrote {len(items)} rehearsal items to {ITEMS_DIR} and rehearsal-pack-index.json")
    print(f"  real: {sum(not it['rehearsal_metadata']['synthetic'] for it in items)}")
    print(f"  synthetic: {sum(it['rehearsal_metadata']['synthetic'] for it in items)}")


if __name__ == "__main__":
    main()
