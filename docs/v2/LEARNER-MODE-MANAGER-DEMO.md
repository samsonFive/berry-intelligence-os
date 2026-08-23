# Learner Mode + Landscape + Executive Readout — Manager Demo Script

First bounded implementations of Workstream K (Learner Mode, `docs/v2/feature-requests/LEARNER-MODE.md`), the executive Landscape synthesis layer (Landscape V2), and the Executive Intelligence Readout (V1). All three are real, deployed V1/V2 features, not prototypes. Combined demo stays under ~5 minutes.

## Ideal manager path

**LANDSCAPE → EXECUTIVE READOUT → drill into evidence → LEARNER MODE**

1. **Landscape** (`/landscapes`) shows what the captured competitive environment looks like -- companies, varieties, evidence, signals per berry.
2. **Executive Readout** (`/readout`) is the "what would I say upward" layer -- the most important trusted developments and real analyst interpretations, with an honest "what to be cautious about" section. Use **Presentation mode** (top of the page) here for a clean, chrome-free screen-share view.
3. **Drill into evidence** -- click through any item (Evidence, Signal, or Assessment) to see the real trusted source behind it.
4. **Learner Mode** (`/learn`) closes the loop -- explains the underlying concept (e.g. Firmness) that showed up in the Readout/Landscape.

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

## 2-minute demo path (Executive Readout V1, the "communicate upward" layer)

1. **Open Executive Readout** (`/readout`) from the sidebar (Library group).
2. **Point out the header stats**, then **What changed** -- real, dated trusted Evidence/Signals/Assessments from the last 14 days, each keeping its real trust-class badge.
3. **Scroll to "What do our analyst assessments say."** Show that each row is a real Assessment (REVIEWED or AI PROPOSED, clearly labeled) with real rationale and a real "would change our view" caveat -- say explicitly: "If we had no assessment on a topic, this would say 'No analyst assessment captured' -- nothing here is invented."
4. **Scroll to "What to be cautious about."** Read the coverage caveat aloud: "Captured intelligence coverage, not market activity."
5. **Click Presentation mode** (top of the page) to show the clean, chrome-free screen-share view -- this is the intended state for an actual executive screen-share.

## What is real today (Executive Readout V1)

- Real corpus-wide "What changed" (14-day window over Evidence/Signal/Assessment dates) -- distinct from Morning Brief's per-analyst state and Landscape's berry-scoped moves.
- Real Assessments and Signals, never fabricated -- honest "No analyst assessment captured" / "No confirmed or proposed Signal captured" when none exist.
- Reuses Landscape's own cross-berry Actors to Watch rather than a second implementation.
- A working, self-contained presentation/screen-share mode (`?present=1`) -- no base template changes.
- Response caching (shared with Landscape) keeps warm requests around 250-650ms.

## What comes next for Executive Readout (do not imply this is done tonight)

- A user-configurable "what changed" time window (today's 14 days is fixed).
- Fact-level items in "What changed" once Fact date-field population (TD-088/TD-089) improves enough to be reliable.
- Export/print-to-PDF for the presentation-mode view.
