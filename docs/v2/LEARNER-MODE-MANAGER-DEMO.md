# Learner Mode V1 + Landscape V2 — Manager Demo Script

First bounded implementations of Workstream K (Learner Mode, `docs/v2/feature-requests/LEARNER-MODE.md`) and the executive Landscape synthesis layer (Landscape V2). Both are real V1/V2 features, not prototypes — small, honest, deployed slices, not the full roadmaps. Combined demo stays under ~5 minutes.

## Suggested combined flow

Learner Mode explains the concepts; Landscape shows where those concepts and competitive developments actually appear across the market. Run the Learner Mode path first, then transition: "Now let's see where this shows up across the actual competitive landscape."

## 3-minute demo path (Learner Mode)

1. **Open the app** at `https://intel.johnnyaceii.com`. Point out the new **Learn** entry in the sidebar (Library group).
2. **Click Learn.** Show the two knowledge categories (Taste & Consumer Science, Plant Biology & Agronomy) and the search box.
3. **Search "firmness."** Click into the **Firmness** result.
4. **Walk the concept page top to bottom:** what it is, why it matters, how it's evaluated, what affects it, and the highlighted "When you see this in intelligence" box — this is the analyst-caution section, not a textbook summary.
5. **Scroll to "Related berry intelligence."** Point out the real trusted Fact rows (e.g. Blue Ribbon, SEKOYA Grande) each linked back to their own Variety profile — this is real trusted intelligence, not fabricated.
6. **Navigate to a real Variety Intelligence page** — e.g. `/entities/variety/variety-sekoya-grande`. Scroll to the Variety Intelligence section and click **Explain this** next to the "Fruit firmness" trait chip.
7. **Land back on the Firmness concept page** — the round trip: intelligence → education → back to intelligence.

Second flow if time allows: search **"double cropping"** from Learn home, open it, and show the "Regional production practice" knowledge-class label and the caution that it's never universal across regions.

## Talking points (3–5)

- "This connects unfamiliar terms in our intelligence directly to plain-language explanations, without ever confusing education with competitive claims."
- "Every concept page is labeled by knowledge class — foundational biology, regional production practice, or dated consumer research — so an analyst knows how stable or how caveated each piece of knowledge is."
- "Related intelligence only ever shows real, already-trusted Facts — this isn't a chatbot summarizing anything, it's a deterministic link to Fact-level evidence we already trust."
- "Explain this is a one-click bridge from a trait we're tracking in Variety Intelligence straight into the concept that explains it."
- "This is a foundation — nine strong starter concepts today, with the architecture ready to expand to the other three pillars (pest/disease, harvest technology, and eventually a Landscape-level view) without any redesign."

## What is real today

- 10 fully-written concept pages (Flavor, Firmness, Shelf life, Bloom, Fruit size/caliber, Texture, Color, Precocity, Double cropping, Winter production), each sourced from a mix of the repository's own trait vocabulary and reputable university-extension / peer-reviewed sources.
- Deterministic search and category browse on the Learn home page.
- "Related berry intelligence" pulling real trusted Facts, using the same trait-tagged recall mechanism Variety Intelligence V2 already relies on.
- "Explain this" links from Variety Intelligence trait chips into the matching concept page, currently wired for Firmness, Flavor/eating-quality, Shelf life, and Fruit size (any trait a concept declares).
- Public static publish: Learn home and all 10 concept pages are included in the GitHub Pages build (a small, finite, enumerable content set, unlike the live-only Compare features).
- Clear knowledge-class + provenance labeling throughout; no Fact/Signal/Assessment badge is ever applied to educational content.

## What comes next for Learner Mode (do not imply this is done tonight)

- Additional pillars: Pest/Disease & Process, Harvest Technology & AgTech.
- Broader "Explain this" coverage beyond Variety Intelligence's trait chips.
- Visual content (diagrams/photos/video) with source/license metadata — Pillar 5 of the governance doc, explicitly out of scope for this slice.
- AI-assisted, non-deterministic "Explain this" — this V1 is intentionally 100% deterministic with no runtime model dependency.
- Update-cadence/freshness review tooling for the "current technical guidance" and "consumer/sensory observations" knowledge classes.

## 2-minute demo path (Landscape V2, optional second act)

1. **Open Landscape** from the sidebar (Library group) while in Global berry context — lands on the new **all-berries overview** at `/landscapes`.
2. **Point out the executive readout** (companies/varieties/evidence/signals across all four berries) and the **coverage caveat**: "Captured intelligence coverage, not market activity."
3. **Scroll the Berries grid.** Note Blueberry's much deeper coverage next to Blackberry/Raspberry's thinner numbers — say explicitly: "Blackberry isn't less competitively active — our trusted evidence there is thinner. That's a data-capture gap, not a market read."
4. **Open Blueberry's full Landscape** (click the card). Show Actors to Watch ("shown because of recent trusted activity," never "top competitor"), then scroll to **Where Competition Is Concentrating** and click **Explain this** on the "Firmness / Shelf Life" theme — lands on the Learner Mode Firmness page, closing the loop back to the earlier demo.
5. **Show the "Compare this berry's most-covered varieties" link** into the existing Variety Compare workspace.

## What is real today (Landscape V2)

- A genuinely new cross-berry `/landscapes` executive overview (companies/varieties/evidence/signals per berry, Actors to Watch, Recent Moves), alongside the existing, proven per-berry `/landscapes/berries/{slug}` pages.
- Evidence Coverage promoted to a first-class, prominently-worded section (not buried in a collapsed panel) with explicit "coverage ≠ market activity" framing.
- Real Explain-this links from Landscape's competitive-theme cards into matching Learner Mode concepts (Flavor, Firmness/Shelf Life, Fruit size) — only where a real mapping exists.
- A real Variety Compare deep-link per berry, pre-selecting the most-evidenced varieties.
- No competitive-strength, threat, momentum, or innovation score anywhere — every number is a labeled coverage indicator.
- Response caching so warm requests are fast (~350-650ms); the very first request after a data change is still several seconds (see known limitations).

## What comes next for Landscape (do not imply this is done tonight)

- Company Compare integration (Company Compare V1 itself has not yet merged to canonical).
- Real server-side geography and time-window filters (today's region filter is client-side over an already-fully-loaded dataset).
- Faster cold-cache performance for the very first request after a data change.
- Activity-type taxonomy beyond the existing trait-derived competitive themes.
