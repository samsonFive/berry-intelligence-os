# Variety title discovery: precision correction

October 7, 2026. Draft slice stacked on catalog review handoff #320. Hortifrut
exposed missed names; the broader audit also found false names.

## Observed problem and correction

The actual candidate browser audit found five misleading observations from
stored headlines: `two new`, `new Sentinel`, `bursts onto the scene`,
`from Mexico coming next`, and `BluGenix with five`. Global case-insensitive
regular expressions made uppercase name boundaries accept lowercase prose.
Launch wording is now case-insensitive separately from the name boundary.
Count/connective phrases are rejected only in title guessing. Lowercase `new`
can be a descriptor; capitalized `New Hanover` remains a name. Structured and
explicitly declared names retain their existing discovery paths.

The BluGenix summary still yields Bounty, Breeze, Cascade, Delight and Eterna,
with its original source URL. Sentinel now matches the existing catalog entry.
No article, Entity, Fact, Relationship, operator decision, alias or URL was edited.

## Measured scope

| Measure | Parent #320 | Correction |
| --- | ---: | ---: |
| Published sources scanned | 1,269 | 1,269 |
| Source/name observations | 99 | 95 |
| Exact catalog matches | 31 | 32 |
| Stored-source candidate observations | 68 | 63 |
| Combined candidate keys before private state | 341 | 336 |
| Catalog entries | 64 | 64 |

Four prose/brand observations disappear and malformed Sentinel becomes a
catalog match. Observations, deduplicated candidate keys and canonical records
are different denominators. Saved decisions remain visible even when transient
discovery no longer proposes the name; their bytes and history are preserved.

The catalog still has 57 active, six unverified and one historical entry.
Coverage no longer labels all entries “Trusted Varieties.” Check each profile's
status and sources. Secondary tables gain readable spacing and contained phone
scrolling. Primary checks remain 381 name occurrences / 25 exact matches / 356
occurrence review needs across 32 sections. Fifteen of 77 registry rows have
some checks; 62 still need initial primary checks. These are sampled checks.

## Diagnostics and acceptance

`benchmarks/variety-title-precision-v1.json` has five exact stored counterexample
headlines, four invented Title Case negatives and five invented positive controls.
Expected outcomes are written separately from output. On this same 14-case
fixture, unchanged parent discovery detects 3/6 expected names, returns ten
unexpected names and passes 3/14 cases. The correction detects 5/6, returns zero
unexpected names and passes 13/14. Before/after reports are retained under
`artifacts/variety-title-precision/` with fixture digest and explicit scope.

Synthetic `Royal Ruby F1` remains a miss: the existing parentage/selection-code
guard rejects it. The original 24-case diagnostic still detects 50/64 expected
occurrences with zero unexpected names and 14 table/Spanish/Polish/body-only
misses. Neither fixture is independently human-verified, a random sample,
live acquisition proof, global recall/precision, or extractor qualification.

100 related discovery, recall, portfolio, navigation and catalog-handoff checks
passed / one existing ReportLab warning / 64.87 seconds. Records and whitespace
validated. Native browser review verified the absent transient `two new`
candidate, updated counts and keyboard disclosure. Observed table overflow was
fixed: at a 390-pixel viewport the document is 375 pixels, and wide tables scroll
internally. Desktop/phone proof is ignored under `inbox/title-precision/`.
Browser review made no POSTs or real identity/source/claim decisions. Exact-head
CI belongs in the draft PR description.

Parent #320 head `8dbebe527b857f145afbb8c1e3a4c50cd122933a` passed all four
required checks, run `37610037362`: 4,016 passed / 11 skipped / two warnings /
449.94 seconds. This verifies its review handoff, not catalog growth.

## Remaining work

CAT-01/CAT-02 and TD-116 stay open: remaining primary portfolios; actual
table/multilingual/full-text acquisition; independently scored names/aliases;
historical/public-domain varieties; separately cited rights, traits, pictures
and growing regions; dated refresh evidence; comparison with external resources
before any web-leading claim. A queue of guesses is not a comprehensive catalog.
Identity, publication and claim gates stay human; user edits are preserved.
No schema, canonical data, registry importer, expansion guide, merge,
deployment or other-berry Landscape rollout changes.
