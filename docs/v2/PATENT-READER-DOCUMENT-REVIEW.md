# Patent documents in the shared Reader

A real FC11-164 patent opened from the variety profile's Rights / IP section
captured a legal-event note instead of the description and claim. The original
public document contained all three main sections. Its body uses custom headings,
description divs, nested lists and tables; selecting ordinary HTML paragraphs
missed those sections.

The existing direct capture now recognizes Google Patents document sections on
the exact publisher host and `/patent/` path. It retains plain text, section and
subsection headings, nested-list labels and bounded table cells/spans. It ignores
site metadata, legal-event chrome and active HTML. The shared Article view keeps
the publisher action and separates source claims from reviewed facts. Abstract,
Description and Claims controls jump within the reader and focus the heading.
The original document remains available in its own tab.

Existing captures are retained until an explicit **Reload source text**. If that
refresh fails, the same-source successful capture remains available with a
failure message. A changed source URL cannot inherit a previous document. Existing
stored article paragraphs and user edits retain precedence over reader captures.

## Boundaries

- The existing 800 KB, four-second and five-redirect transport limits remain.
  Every destination passes the existing public-URL check; unsuccessful responses
  and access restrictions are not treated as documents.
- Document projection is limited to 240 blocks, 40,000 characters and 4,000
  characters per block, with at most 24 cells/spans per row. Limits are disclosed
  as partial capture; even an untruncated document is not called verified/full.
- Publisher HTML never executes in the reader. Templates escape text; only known
  roles and bounded integer spans reach rendering. No scripts or dynamic page
  execution are needed to acquire these semantic source sections.
- Captures and preview projections remain in ignored private runtime storage.
  GET does not acquire or write source text. Readonly/static output does not read
  document blocks or expose acquisition/reload controls.
- Reading is not publication, identity, Atomic Evidence or rights review. No
  inferred current legal status, ownership, trait, growing footprint or canonical
  addition is made. Patent figures are not approved variety-gallery photographs.

## Validation and limits

Deterministic fictional fixtures exercise original section structure, a table
nested inside a description paragraph, nested labels, claims, safe fallback,
source boundaries, block limits, escaped HTML, readonly exclusion, preservation
of existing text, explicit refresh and failed-refresh preservation. Normal CI
does not fetch a live patent.

Native acceptance uses the existing FC11-164 profile and its original source:
[USPP34903P2](https://patents.google.com/patent/USPP34903P2/en). The source body and
browser proof stay private. Full source completeness, legal interpretation and
other registry/PDF formats remain unverified. Catalog remains 64 and portfolio
counts remain 537 occurrences / 51 sections / 448 derived candidate keys before
private decisions; 55 initial company checks and seven follow-ups remain.

The unchanged synthetic recall fixture improves to 60/64 in parent draft #334,
with four body-only misses. It is not a global coverage score or independently
reviewed model qualification. This reader repair does not scan bodies for new
variety names or approve those misses. CAT-01/CAT-02/TD-116 stay open. This is draft
work within the blueberry checkpoint; no merge/deploy/other-berry rollout.
