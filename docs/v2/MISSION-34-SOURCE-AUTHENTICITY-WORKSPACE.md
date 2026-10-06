# Mission 34 — Source authenticity in Operations

The recovered-source queue and comparison now use the approved Glasshouse top navigation and Operations workspace. They keep their existing URLs, filters, article/transcript readers, original wording, reviewer identity, review-session returns, per-source decisions and private audit events. No canonical record or protected schema changes.

## What the analyst sees

- A clear source-authenticity purpose, pending count and compact filters; matching labels use everyday language rather than internal enum codes.
- Distinct Original published source and Recovered copy panels, larger headings, outlined paper surfaces, warnings above the comparison and readable full recovered text. Article content stays expanded.
- Publication metadata, capture diagnostics, identity matching and extraction consequences are collapsed initially. Technical fingerprints remain accessible for investigation.
- Separate capture and review dates in the queue. Reviewing a recovered copy does not change its capture date or the original article's publication date.
- Accept, Reject and Investigate remain individual source decisions. Acceptance requires an explicit checkbox. The page asks for a reviewer only when neither the signed-in session nor configured local reviewer supplies one; server-side validation remains mandatory.
- Global search and the shared Reader remain available. Search retains its original API, result categories, published/private labels and navigation; the visible instructions and result count now omit internal vocabulary and processing timings. Its three shell script versions are refreshed.

## Functional repairs found during actual review

The prior Accept + Next button had duplicate `name`/`value` attributes. The handler also tried to find the next item after the current decision removed it from a filtered queue. The repaired native form submits both decision and advance, with its own confirmation; the handler resolves the next filtered neighbor before changing only the selected source. Review-session return behavior takes precedence as before. Reject and Investigate + Next use the same explicit form.

The detail's generic `berries` context collided with the app context processor and displayed all raw berry IDs. A source-specific field now displays only the source's recorded berry scope, with readable names. No berry inference is added.

Keyboard review shortcuts ignore focused links, buttons, disclosures, editable fields, modifiers, held-key repeats and open overlays. Native Enter toggles disclosures. Phone review found inherited full-width checkboxes causing horizontal overflow; explicit checkbox sizing corrects it without hiding content. Search uses the actual shared shell identifiers and usable overlay dimensions, result grouping and visible close control.

## Evidence

127 focused source authenticity, publication body fidelity, review session/Operations, shell, visual guide, private/public safety and global-search tests passed (one existing ReportLab warning, 31.26 seconds). After the final date-label change, all 25 source-authenticity tests passed again (one warning, 4.19 seconds). Record validation and whitespace integrity passed. Tests prove no GET decisions/body copying onto queue projections, acceptance confirmation, mandatory reviewer identity, unchanged canonical records, exactly one decision event and untouched neighboring sources for all three advance actions.

Actual native browser review at `127.0.0.1:18328` used three explicitly fictional records in an isolated ignored data/inbox directory. It proved the checkbox gate, identified acceptance advancing to the next pending source, All history retaining the accepted copy, separate capture/review dates, keyboard disclosure/shortcut safety and three stored-record search results. No genuine source authenticity decision was performed.

At the tested 390-pixel phone viewport, document and client widths both measured 375 pixels after scrollbar allocation. Both panels stack, all three recovered paragraphs remain present, and all four secondary disclosures start collapsed. The temporary viewport was reset.

Actual reviewed screenshots:

- [Desktop comparison](../../artifacts/design-sprint/source-authenticity-desktop.png)
- [Phone comparison](../../artifacts/design-sprint/source-authenticity-mobile.png)
- [Phone article reading](../../artifacts/design-sprint/source-authenticity-mobile-reader.png)
- [Decision history](../../artifacts/design-sprint/source-authenticity-history.png)
- [Search](../../artifacts/design-sprint/source-authenticity-search.png)

## Release boundaries

Accepting the recovered copy does not publish/unpublish its source, approve statements, create verified facts, authorize extraction or qualify a model. Source trust, statement trust and source authenticity remain separate human gates. Source bodies, review state and audit events stay private; public build tests retain their existing leakage fixtures. No browsing acquisition/provider call, recurring job activation, merge or deployment occurs.

This migrates two verified live legacy-shell templates. The rest of the retained specialist-route inventory, broader country/berry reference population, older-PR functional parity, combined Guide acceptance and canonical release/backup/rollback review remain required. Exact-head required CI will be recorded on the pushed draft; local proof does not replace it.
