# Rehearsal pack index

Location: `data/imports/publication-review-rehearsal-2026-09-16/items/*.json`
(one file per item) plus `data/imports/publication-review-rehearsal-2026-09-16/rehearsal-pack-index.json`
(machine-readable index, same content as this table). Generator:
`scripts/_gen_publication_review_rehearsal_pack_v1.py` (kept, non-runtime,
re-runnable, deterministic — re-running it reproduces byte-identical
output).

**10 items. 6 real, 4 synthetic.** Every item carries a
`rehearsal_metadata` block declaring `synthetic: true/false` and either
`real_run_reference` (for real items: which of this mission's own bounded
run's outputs it reproduces) or `grounded_in` (for synthetic items: the
real, cited code/test/diagnostic evidence the fixture is modeled on).

| Slot | Decision type (mission's own list) | Real or synthetic | Item id | Title |
|---:|---|---|---|---|
| 1 | Clearly readable article | **Synthetic** — grounded in real diagnostic word counts (61-495) from `artifacts/readable-acquisition-canary-v1/` | `rehearsal-01-readable-article` | [REHEARSAL FIXTURE] Regional Blueberry Cooperative Reports Record Spring Yield |
| 2 | Transcript-backed item | **Synthetic** — grounded in the real `ev-lucentlands-scaling-blueberry-industry-2025` trusted record and the real `TRANSCRIPT_PUBLISHER` mechanism | `rehearsal-02-transcript-backed` | [REHEARSAL FIXTURE] Podcast Episode: Blueberry Genetics Trends in Southern Africa |
| 3 | Metadata-only item | **Real** — discovered 2026-09-16, `source-business-of-blueberries-podcast` | `rehearsal-03-metadata-only` | Inside Walmart's Berry Strategy With Melissa Byland |
| 4 | Navigation-only shell | **Real** — discovered 2026-09-16, `source-20260915-oishii-press` | `rehearsal-04-navigation-only-shell` | How Oishii Uses Bees, Robots And Solar To Sustainably Grow Strawberries Indoors |
| 5 | Uncertain publication date | **Synthetic** — grounded in the real, documented calgiant.com stale-sitemap-lastmod case (`article_refresh._reconcile_published_date`) | `rehearsal-05-uncertain-date` | [REHEARSAL FIXTURE] California Giant Blog Post Republished With New Sitemap Timestamp |
| 6 | Missing or weak entity match | **Real** — discovered 2026-09-16, `source-lucentlands-podcast` | `rehearsal-06-weak-entity-match` | Ports and Fresh Produce Logistics \| Ep. 157 |
| 7 | Duplicate / probable duplicate | **Real** — discovery-time match found 2026-09-16, `source-lucentlands-podcast` vs already-trusted `ev-lucentlands-scaling-blueberry-industry-2025` | `rehearsal-07-duplicate-candidate` | Scaling the Blueberry Industry – Opportunities for Africa and Beyond \| Ep. 102 |
| 8 | Corrected or upgraded acquisition | **Synthetic** — grounded in the real `article_identity_probe`/`CONTENT_CHANGED` mechanism | `rehearsal-08-corrected-acquisition` | [REHEARSAL FIXTURE] Existing Draft's Article Body Re-Checked and Found Changed |
| 9 | Rejection candidate | **Real** — discovered 2026-09-16, `source-20260915-oishii-press` (second, independent Oishii sample) | `rehearsal-09-rejection-candidate` | High-end strawberry grower Oishii opens solar-powered indoor vertical farm utilizing robots |
| 10 | Defer / correction-required candidate | **Real** — discovered 2026-09-16, `source-lucentlands-podcast` | `rehearsal-10-defer-correction-required` | Can Farmers Use Fewer Chemicals Without Risking Their Crops? \| Ep. 156 |

## Why 6 real / 4 synthetic rather than an even split

The mission brief's own preference order — "Prefer existing
repository-compatible records. If live examples cannot safely be
committed, create deterministic synthetic fixtures" — was followed
literally per slot, not forced to a 5/5 ratio. Real, safely-committable
examples existed for 6 of the 10 required decision types in this
mission's own bounded run (including a genuinely valuable, real
discovery-time duplicate match this mission did not expect to find). The
remaining 4 types (a genuinely readable body, a transcript, a stale-date
conflict, a content-change re-check) either require content this mission
declined to commit for copyright-safety reasons (a real scraped readable
body/transcript) or a mechanism the bounded run did not happen to trigger
live (a repeat-visit content-change probe) — each was built as a
deterministic synthetic fixture instead, explicitly cited to the real
mechanism it represents.

## What every item explicitly does NOT contain

- No raw HTML.
- No cookies, credentials, or sensitive request/response headers.
- No copyrighted full-text article or transcript body (synthetic bodies
  are short, invented excerpts under 100 words; real items carry only
  discovery metadata, a template-only placeholder summary, or an
  AI-generated, provenance-tagged, untrusted summary of publisher
  metadata — the same class of content the real review UI already shows
  reviewers today).
- No uncontrolled external payload — every synthetic `source_url` points
  at `example.invalid` (RFC 2606 reserved, guaranteed non-resolving); no
  process in this codebase will ever fetch it.

Verified directly: `grep -l "<html\|<body\|<script\|Set-Cookie\|Authorization:\|api_key\|password"` across every rehearsal file returns no matches.
