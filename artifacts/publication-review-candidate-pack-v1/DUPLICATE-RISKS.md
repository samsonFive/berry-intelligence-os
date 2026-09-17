# Duplicate risks

## 1. Confirmed real duplicate signal (rehearsal item 7)

`discovered-source-lucentlands-podcast-4a4e9cbacb472ce3` (title "Scaling
the Blueberry Industry – Opportunities for Africa and Beyond | Ep. 102",
published_date `2025-10-28`) — discovered fresh by this mission's own
bounded run on 2026-09-16 — exactly matches the already-published, trusted
`data/evidence/ev-lucentlands-scaling-blueberry-industry-2025.json` on
both title and published_date. `media_discovery.py`'s own
`possible_evidence_matches` mechanism flagged it automatically, at
discovery time, before any acquisition attempt: `reasons:
["title_match", "published_date_match"]`, `confidence: "medium"`.

**No draft was created for this item.** It never advanced past the
discovery stage in this run because it was not among the top-N most
recent items selected for acquisition in this bounded pass — meaning the
match signal is visible only in the raw discovery-staging record
(`inbox/discovered_media/`), not in anything a reviewer would see in the
review queue today. This is itself worth noting: **the duplicate-match
signal currently only reaches an operator if the matched item happens to
also be selected for full processing** — a genuinely duplicate item that
never gets acquired leaves its match flag stranded in a staging file no
UI surfaces.

## 2. Mechanism review — how duplicate detection actually works today

- **Discovery-time**: `possible_evidence_matches` (title + published_date
  heuristics, `confidence: low/medium/high`) — checked once per
  newly-discovered item against already-published trusted Evidence only
  (not against other pending drafts).
- **Body-time**: `article_acquisition.repeated_body_conflict()` — rejects
  the *third* distinct publication URL sharing an identical
  `content_sha256`, i.e. catches syndication/reprint chains, not simple
  title matches. Two matching bodies are treated as a legitimate reprint
  pair, not a duplicate.
- **Human-time**: `rejection_category="duplicate"` on the real
  `/review/{id}/reject` action — the actual terminal decision an operator
  makes; nothing upstream auto-resolves a match.

None of these three mechanisms cross-checks *pending drafts against each
other* — only pending-vs-trusted (discovery-time) and
pending-vs-pending-by-identical-body (repeated_body_conflict). Two
distinct drafts describing the same real-world event through different
wording (e.g., two different podcasts covering the same announcement)
would not be caught by either mechanism and would rely entirely on a
human reviewer noticing.

## 3. Duplicate risk across this mission's own rehearsal pack itself

Checked directly: no two of the 10 rehearsal items share a title,
canonical URL, or `content_sha256`. Item 7's `matched_trusted_evidence`
field intentionally references the same real trusted record its sibling
discovery match points at (`ev-lucentlands-scaling-blueberry-industry-2025`)
— this is the pack's own designed duplicate-risk teaching example, not an
accidental collision. No other cross-references exist between the 10
items.

## 4. Recommendation for a future mission (not built here)

Surfacing `possible_evidence_matches` (and, ideally, a pending-vs-pending
equivalent) directly in the publication-review UI itself — not just in
the discovery-staging JSON — would close the gap in §1. Out of this
mission's scope (no production UI changes permitted).
