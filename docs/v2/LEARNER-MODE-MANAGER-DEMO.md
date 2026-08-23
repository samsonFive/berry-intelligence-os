# Learner Mode V1 — Manager Demo Script

First bounded implementation of Workstream K (`docs/v2/feature-requests/LEARNER-MODE.md`). This is a real V1 feature, not a prototype — a small, honest, deployed vertical slice, not the full Learner Mode roadmap.

## 3-minute demo path

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

## What comes next (do not imply this is done tonight)

- Additional pillars: Pest/Disease & Process, Harvest Technology & AgTech.
- Broader "Explain this" coverage beyond Variety Intelligence's trait chips.
- Visual content (diagrams/photos/video) with source/license metadata — Pillar 5 of the governance doc, explicitly out of scope for this slice.
- AI-assisted, non-deterministic "Explain this" — this V1 is intentionally 100% deterministic with no runtime model dependency.
- Update-cadence/freshness review tooling for the "current technical guidance" and "consumer/sensory observations" knowledge classes.
