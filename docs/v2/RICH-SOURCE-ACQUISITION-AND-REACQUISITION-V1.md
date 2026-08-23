# Rich Source Acquisition + Selective Historical Reacquisition V1

## Trust and scope

This work improves source material only. It does not qualify a model, enable
extraction, create Atomic Evidence, affirm Source Fidelity, add a Source, or
change Evidence trust. Current-page reacquisition is always a private artifact
pending the existing Source Fidelity Review workflow; it never overwrites the
trusted Evidence record or its review history.

## Forward acquisition audit

The working written path is `discover_source()` ->
`process_discovered_article()` -> `fetch_article()` ->
`MediaOrchestrationService.prepare_publication_draft()` -> Publication Review
-> `ReviewPublishService.publish()`.

Successful acquisition already carried normalized `article.paragraphs`,
`content_sha256`, word count, extractor/version/fetch time, author, and final
URL on the draft. Publication Review already displayed those paragraphs, and
the publish transaction already deep-copied and normalized the entire article
object into trusted Evidence. This mission proves that behavior in regression
coverage and adds extracted title, publication date, and language to the same
artifact. It also adds a deterministic `source_completeness` classification:
`FULL_ARTICLE`, `FULL_TRANSCRIPT`, `STRUCTURED_REGISTRY`,
`THIN_DESCRIPTION`, or `NO_CONTENT`. This is completeness metadata, not a
trust state.

For spoken media, the normalized transcript remains private under the runtime
inbox. When it exists before Publication Review, the publication draft now
carries a body-free durable `source_artifact` reference: transcript id, content
hash, language, `discovered_item_id` lineage contract, and private-runtime
storage declaration. That reference survives publication. The transcript body
does not enter static output or trusted Evidence merely because it was
captured.

Successful full articles and captured transcript references therefore cannot
silently collapse to summary-only during normal publication. Structured
registry records remain valid without an article body. A genuinely thin record
is still publishable, but Publication Review labels it `THIN DESCRIPTION` and
shows: **“Full source content was not captured. Review the original source
before publishing.”** Publishing that visibly warned candidate records
`operator_accepted_thin: true`; it does not invent a new review or trust state.

## Failure and body-quality behavior

Failure reasons are explicit and normalized (`PAYWALL`, `ROBOTS`,
`EMPTY_BODY`, `INTERSTITIAL`, `SCRIPT_RENDERED`, `REMOVED`, `TIMEOUT`,
`UNSUPPORTED_MEDIA`, `TRANSCRIPT_UNAVAILABLE`, and narrower transport/HTTP
classes). Thin fallback drafts retain the concrete reason. Only timeout,
transport, HTTP, and redirect failures reuse the existing bounded retry policy.
Permanent/structural failures are operator items; there is no second retry
engine.

Existing wall detection, minimum body length, and readable-text extraction
remain in force. The forward path now also rejects the third identical body
hash across distinct publication URLs, allowing a possible two-outlet reprint
pair but stopping a mass shared wrapper/interstitial from becoming rich source
material.

Source Health currently derives FAILING/BLOCKED from per-source discovery
state, not per-item article-body outcomes. Item failures remain visible in
collection status and retry/intervention state. Wiring aggregated item-body
failure rates into Source Health would change that surface's semantics and was
documented rather than added here.

## Google News repeated-body root cause

The production recovery manifest proves 65 distinct Google News publication
URLs shared one 1,356-character extraction-source hash. Read-only inspection of
one preserved candidate proves the acquisition began at a
`news.google.com/rss/articles/...` wrapper and ended at
`https://consent.google.com/ml?...`, with no author, 12 extracted paragraphs,
213 words, and trafilatura provenance. It was Google consent-page content,
not 65 publisher articles, not a cache collision, and not a legitimate
reprint. No conflicted body was attached.

The forward fix rejects a Google News wrapper that remains on Google News as
`SCRIPT_RENDERED`, rejects a redirect to `consent.google.com` as
`INTERSTITIAL`, recognizes Google consent text before extraction, and retains
the independent repeated-body safety gate. Publisher URL resolution must occur
before readable-article acquisition.

## Historical selective reacquisition

`scripts/reacquire_sources.py` is dry-run by default:

```text
python scripts/reacquire_sources.py --status
python scripts/reacquire_sources.py --priority high --limit 10
python scripts/reacquire_sources.py --ids EVIDENCE_ID --limit 1
python scripts/reacquire_sources.py --manifest
```

Network acquisition requires `--execute`, a limit of at most 25, and either an
explicit id set or priority filter. No bulk execution mode exists. Execution
captures a separate current-page artifact and deterministically compares
canonical/final URL, title, date, original-summary overlap, publisher identity,
author metadata, and a historical hash when one exists. Outcomes are
`EXACT_STABLE_SOURCE`, `LIKELY_SAME_ARTICLE_CHANGED_FORMATTING`,
`CONTENT_CHANGED`, `URL_REDIRECTED`, `PAYWALLED`, `REMOVED`, `UNAVAILABLE`, or
`AMBIGUOUS`. Every successful capture remains `pending` in Source Fidelity
Review. No reacquisition was executed in this mission.

Priority ordering exposes each component and points: confirmed Signal and
Assessment references, linked Companies/Varieties, multi-object use,
caneberry gaps, berry breadth, recentness, URL presence, and actual source-type
metadata. The points are operational ordering support, not hidden importance
truth and not a prediction of analyst decisions.

## Current inventory and pilots

The freshly fetched canonical corpus differs from the earlier 1,268-record
premise: it contains 1,266 trusted Evidence records, 36 extraction-ready
structured registry records, 1,225 thin records, two deterministic duplicates,
and three unsupported fixtures. Historic Recovery's combined-location result
remains a separate measurement: two articles plus one transcript are known
recoveries, 65 Google consent-body candidates are conflicts, and 1,159 records
had no known historic artifact at that audit point.

Across the current 1,225 thin records:

- berry metadata: 29 Blackberry, 26 Raspberry, 232 Strawberry, 446 Blueberry,
  194 multi-berry, and 298 untagged;
- source types: 43 company newsroom, 22 trade press, 10 academic, one spoken,
  and 1,149 other (mostly legacy Google News wrappers);
- expected availability: 43 high, 44 medium, and 1,138 low;
- 260 score HIGH on strategic/caneberry reasons, but only 34 are both HIGH and
  carry a publisher URL with HIGH/MEDIUM expected availability;
- those 34 realistic high-priority candidates are 33 Blueberry and one
  Blackberry; by source type, 23 company newsroom, seven trade press, two
  academic, and two other.

This is the honest caneberry gap. The current corpus has 26 Raspberry-tagged
thin records, but their surviving URLs are low-availability Google News
wrappers, so none is labeled realistically executable without a separate
publisher-URL resolution step. Blackberry has 29 thin records and exactly one
realistic candidate: `ev-hortweek-driscolls-victoria-award` (trade press;
Company + Variety links; medium availability/paywall risk). Strawberry has
many thin records but no strategically HIGH + HIGH/MEDIUM-availability item;
the pilot deliberately includes a medium-priority company-newsroom candidate
for crop diversity rather than fabricating a high-priority one.

Private body-free manifests are written to:

- `inbox/operations/source-reacquisition/REACQUISITION-PILOT-10.json`
- `inbox/operations/source-reacquisition/REACQUISITION-PILOT-25.json`

Pilot 10 begins with Victoria/HortWeek, a Strawberry company-newsroom item,
then the highest-priority Blueberry mix across industry association, company
newsroom, trade press, academic, and other publisher pages. The planning-only
range is 4-7 possible ready additions for 10 attempts. Pilot 25 is 10-18.
Those ranges apply source-availability assumptions only (HIGH 50-80%, MEDIUM
20-60%); they do not predict Source Fidelity Review affirmation.

## Readiness impact

- Current: 36 ready.
- After the three known historic recoveries, if separately staged and affirmed:
  39.
- After pilot 10, if the known recoveries were affirmed and the planning range
  held: roughly 43-46.
- After pilot 25 on the same assumptions: roughly 49-57.

No defensible 30-day forward corpus number exists from current evidence. The
older cadence baseline estimates 25-35 review-eligible candidates per month,
but that includes spoken and metadata-only candidates and is not a measured
full-body acquisition success rate. Forward prevention now retains every
successful rich acquisition; it cannot promise that paywalls, robots, consent
walls, or unsupported media will become rich.

The path from roughly 39 to hundreds is therefore not a 1,159-URL refetch. It
is: keep source-rich forward acquisition as the default, resolve Google News
publisher URLs before article acquisition, favor direct publisher feeds and
newsrooms, run small diverse reacquisition batches, measure real outcome yield
by source type, and send every current-page comparison through Source Fidelity
Review.
