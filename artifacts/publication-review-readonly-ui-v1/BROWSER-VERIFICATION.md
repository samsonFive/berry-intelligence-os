# Browser verification — Publication Review read-only UI v1

## Environment

- Route: `/review-ops/publications`
- Rehearsal flag: `BIOS_PUBLICATION_REVIEW_REHEARSAL_UI=1` (verification only)
- Viewports: desktop 1440×900, tablet 834×1112, mobile 390×844

## Checks

- Queue + workspace render with pending count and filters
- Ten rehearsal states reachable via draft URLs
- Decision controls present but `disabled` / `data-enabled=false`
- `data-decisions-enabled=false` root attribute
- `data-pagefind-ignore` on private panels
- No decision POST occurs from UI controls
- Desktop / tablet / mobile screenshots + walkthrough video captured

## Safety

DECISION MUTATIONS CONNECTED: NO
REHEARSAL FIXTURES SHIPPED AS LIVE DATA: 0
