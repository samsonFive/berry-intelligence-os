# Design System — Foundation

## Reference

The visual reference is stored at `assets/platform-visual-language.png`.

## Visual objectives

The interface should feel like a professional intelligence workstation: authoritative, calm, structured, and traceable. It should support dense information without appearing cluttered.

## Application shell

- Persistent dark navy left navigation.
- White and very light neutral page backgrounds.
- Primary work area organized into cards, tables, and split panes.
- Top-level search remains globally available.
- Current module is visibly highlighted.

## Core semantic colors

Exact tokens should be finalized during implementation, but usage is fixed:

- Navy: navigation, authority, framing.
- Purple: platform identity, intelligence objects, active controls.
- Blue: reading and informational priority.
- Green: testing relevance, positive support, strengthening signals.
- Orange: commercial-position attention and medium-risk escalation.
- Red: invalid, rejected, disputed, or destructive actions only.
- Gray: metadata, neutral status, archived or unavailable states.

## Canonical object representations

### Evidence card

Contains source-type badge, headline, summary, date, linked entities, geography, priority chips, why-it-matters rationale, and provenance action.

### Fact card

Compact declarative statement with fact/claim classification, confidence, supporting evidence count, reviewer, and supersession status.

### Entity card

Name, type, role, geography, aliases, related-record counts, freshness, and confidence summary.

### Relationship row

Subject → relationship verb → object, with supporting evidence and effective dates.

### Signal card

Title, direction, strength, confidence, supporting evidence count, affected entities/geographies, first seen, last updated, and linked strategic questions.

### Recommendation card

Recommended action, decision owner, rationale, priority, due/review date, and supporting evidence chain.

## Priority dimensions

All four dimensions use consistent chips everywhere:

- Reading
- Testing
- Commercial Position
- Monitoring

Each has `none`, `low`, `medium`, and `high`, plus a rationale.

## Trust display

Entity, signal, and intelligence-product pages should summarize:

- evidence count;
- independent source count;
- geographic breadth;
- last reviewed date;
- confidence level;
- conflicting or counter-evidence status.

## Interaction principles

- Preserve context during review.
- Use progressive disclosure for deep provenance.
- Clicking a badge filters or opens the linked object.
- Generated intelligence must always offer a route back to source evidence.
- Never use color as the sole status indicator.
