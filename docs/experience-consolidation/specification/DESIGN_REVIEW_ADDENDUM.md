# Berry OS — Design review and experience acceptance addendum

## Status and basis

Design-collaborator recommendations for the existing Revision 2
consolidation plan. This is not authorization to start coding, install
dependencies, call providers, change data, or deploy. It does not claim
that the proposed architecture has been implemented or runtime-tested.

Read alongside the four files in berry-os-experience-consolidation.zip:
- BERRY_OS_EXPERIENCE_CONSOLIDATION_PROPOSAL.md
- FRONTEND_CONTRACTS.md
- COORDINATED_AGENT_WORKSTREAMS.md
- STATE_CONTRACT_NOTES.md

Visual observations refer to the earlier design-handoff screenshots,
not a newly inspected production deployment.

The recommendations below refine experience and visual acceptance;
they do not replace the agent's implementation contracts or re-audit
the repository.

## 1. Accept the investigation-centered structure

Use Landscape · Briefing · Workspaces · Learn as the proposed primary
destinations. Revision 2 identifies Learn as an existing educational
workflow and records a requirement to retain it at top level. Do not
remove it merely to meet an arbitrary three-destination target.

Landscape unifies industry investigation: actor selection, company
detail, portfolios, variety detail, geographic lenses, relationships,
comparisons, and supporting developments.

Briefing supports discovery and reading.

Workspaces supports authored analysis, reusable investigations,
and outputs.

Learn retains its educational identity.

Review, catalog curation, monitoring setup, collection health, and
administration remain deliberate secondary workflows. A contextual
Follow action can remain beside a company, but following must not become
comparison membership or evidence of commercial presence. Opening
evidence must not approve it.

The product boundary follows user intent and persistence/trust effects,
not the number of existing routes. Keep deep links and advanced tools
even when their entry points cease to dominate navigation.

## 2. The target is a richer investigation, not a shorter menu

One investigation retains its scope, selected subjects, analytical
representation, detail history, and return context. A company, variety,
geography, or source is something the user investigates within that
context—not necessarily a new place the user must visit.

Do not satisfy consolidation with new navigation labels wrapped around
unchanged pages. Do not replace a long table with a large collection
of generic cards and call that a dashboard. Do not embed whole legacy
pages in iframes or stacked drawers.

The landing experience must make a useful industry relationship or
comparison understandable before the first click. The interaction
then deepens that understanding.

## 3. Refine the three-module Landscape composition

Keep Revision 2's three complementary modules, with one clear hierarchy:

SCOPE READOUT

Two or three short findings grounded in the selected data. Lead with
named actors, activities, or relationships—not evidence counts,
missing-field messages, or unsupported strategic conclusions.

These describe the applied scope. A focused company does not silently
redefine the scope summary.

MAIN ANALYTICAL FIELD

This is the visual center of the report. Use compact, aligned
company/portfolio bands or another data-supported composition that
makes actual relationships visible at rest.

Where supported, show company → program → variety with the correct
role. A source-named cultivar remains visibly distinct from an approved
portfolio relationship. Do not invent links to make a diagram attractive.

An intentional matrix is preferable when it communicates the actual
relationships more clearly.

RELEVANT DEVELOPMENTS

A bounded, subordinate set of existing visual news cards. Its relevance
follows the current scope, focal entity, or comparison cohort under an
explicit precedence rule.

Preserve access to a full Briefing, but do not place an unfiltered
general newsfeed underneath every analysis.

Connections, Portfolio, Geography, and Comparison replace the main
analytical field. They do not duplicate the entire page or reset the
investigation. Sensory demonstration has its own clearly labeled state
rather than adding a second dashboard below the first.

Use a compact scope bar and one organized command area. Put advanced
filter, layout, and operational controls behind appropriate actions
rather than showing multiple stacked toolbars above the intelligence.

## 4. Interaction behavior must make the information work together

APPLY SCOPE
Update only modules that support those filters; retain clear geographic
and date meanings.

HOVER/FOCUS AN ITEM
Show relevant support/context without changing scope, comparison
membership, history, or initiating research.

SELECT A COMPANY
Highlight its actual connections, open its populated detail, and update
entity-relevant developments; keep other actors available.

PIN A COMPANY OR VARIETY
Change the appropriate comparison cohort only; focus and membership
remain independent.

SELECT A LINKED VARIETY
Open variety detail with a return path to its company/relationship;
do not infer growing locations from company geography.

CHANGE ANALYTICAL VIEW
Replace the main representation while preserving scope, cohorts,
and applicable detail.

OPEN EVIDENCE
Use the coordinated detail area, retain the parent relationship/entity,
and restore it on close.

INSPECT AN OUTSIDE-SCOPE ENTITY
Show that detail without silently adding it to the underlying landscape.

USE A COPILOT COMMAND
Apply the same validated actions and render the same domain components
used by direct controls.

SAVE INVESTIGATION
Retain selectors and view state that reopen current authorized records;
do not imply a dated snapshot.

The package already defines the technical state distinctions. The
design must make those distinctions feel natural, without exposing
internal schema terminology.

## 5. One contextual area, not competing drawers

Company detail, variety detail, relationship evidence, source reading,
and Copilot output must share a coordinated layout allocation.

Do not squeeze the analytical field between a permanent chat sidebar,
a company drawer, and a second evidence drawer.

At desktop widths, opening detail may resize the analytical area while
preserving its readability. At narrower widths, switch deliberately to
a focused detail state with a clear return action.

Expanded dossiers and readers remain available when depth requires space.

Reader ancestry and company → variety → evidence return paths should
preserve relevant scroll and focus. Repeated source inspection should
not force users to reconstruct their comparison.

## 6. Preserve the user's progressive-detail principle

SHOW THE INTELLIGENCE.
HOVER FOR CONTEXT.
CLICK TO INVESTIGATE.

The company name, variety name, relationship, map cell, or score itself
is the interaction target. Do not replace verbose annotations with a
separate information icon beside every field.

Sources, dates, excerpts, methodology, confidence, review history, and
performance context belong in enterable previews and persistent detail.

Keyboard and touch have equivalent access. Empty profile sections and
repeated missing-data messages do not belong in presentation mode.

Keep short distinctions visible when they materially change meaning:
breeder versus licensee; planned versus operating; source-named versus
established relationship; disputed versus settled; synthetic versus
measured.

These are the information, not optional footnotes. Prefer concise
role/activity labels to repeated warning prose.

A comparison's missing observation remains a quiet dash or null with
an accessible explanation, never zero. Coverage and completeness
diagnostics remain accessible in an intentional research/review workflow.

## 7. Visual acceptance: agricultural editorial, not a software skin

Use warm white/ivory reading surfaces, dark botanical text, selective
sage/forest accents, and restrained berry colors.

Do not make every section the same pale green. Color should organize
categories, selection, and relevant distinctions—not compete with
the data.

The earlier screenshots show repeated tinted panels, dense table
toolbars, and similar emphasis across controls and content. Address
that hierarchy directly.

Make important company/variety names and findings readable; reduce the
visual weight of configuration controls and secondary metadata.

Use meaningful permitted fruit, growing, and company imagery where it
helps—especially existing news cards.

Do not add large decorative agricultural heroes or invent cultivar
photography. Editorial typography and comfortable spacing should
coexist with precise analytical density.

AG Grid and Copilot-rendered components must consume the same tokens
and interaction primitives as the rest of the application. Stock
vendor themes do not define Berry OS.

## 8. Keep the tools subordinate to the experience

Revision 2 proposes one React application, controlled CopilotKit, and
AG Grid Community. This addendum neither independently verifies those
integrations nor replaces their stated implementation-proof requirements.

GRID

Use it for the expanded portfolio matrix and other demanding analytical
tables. The default Landscape must not become the same spreadsheet
with a new grid engine. Preserve small semantic tables where appropriate.

COPILOT

Use it as a way to operate the investigation or assemble approved
components, not as a permanent chat feed that competes with the report.

A request to compare two companies should produce the shared comparison
state. Factual values and evidence resolve through the existing
authorized data services, not model-invented component properties.

Normal exploration must remain complete without a provider call.

SDK integration and visual quality are separate acceptance questions;
passing one does not establish the other.

## 9. Sensory demonstration should answer a clear question

Keep the separate synthetic fixture and fictitious specimen identities
proposed in Revision 2.

Use a 1–9 scale with most scores between 4 and 7.

Do not attach synthetic scores in a way that implies measured rankings
of actual commercial varieties.

Begin with a readable comparison of the synthetic specimens—such as
a labeled dot plot with a visible 1–9 axis—and an optional distribution
view.

Introduce additional sensory dimensions only when the synthetic schema
deliberately defines them. Do not reinterpret acidity intensity,
sweetness intensity, and liking as interchangeable measurements.

One prominent synthetic-data label per self-contained panel, with
fuller context on hover, is sufficient for the default view.

Standalone outputs carry their own label.

The demo stays outside canonical facts, ordinary search, coverage
counts, and standard exports; an explicit labeled annex remains separate.

## 10. Strengthen acceptance before scaling implementation

Add a VISUAL AND INTERACTION CHECKPOINT alongside the engineering gates.

Once implementation is separately authorized, validate one populated
end-to-end slice before copying patterns across all routes.

The package's proposed rehearsal is Blueberry / Chile–China–Peru with
Fall Creek and Costa.

Re-check the current authorized records before using it; the planning
package and prior screenshots are not proof of current production data.

Do not manufacture records or strengthen claims to keep the rehearsal
intact.

The checkpoint should show:

1. INITIAL LANDSCAPE
Meaningful scoped intelligence and relationships, not a directory or
wall of KPIs.

2. COMPANY SELECTED
Connected data, relevant developments, and contextual detail clearly
respond together.

3. COMPARISON
Pinned subjects remain, useful portfolio/role/geography differences
are readable, and provenance is unobtrusive but accessible.

4. EVIDENCE
The source opens and closes without losing scope, cohort, lens,
parent detail, or focus.

5. SYNTHETIC SENSORY STATE
Visually coherent with the same application, unmistakably separate
from measured intelligence.

Capture a short continuous interaction recording as well as desktop
screenshots. Review a narrower layout and keyboard/touch-equivalent
detail behavior.

A set of attractive isolated components is not evidence of a coherent
investigation.

Keep implementation ownership and state/API contracts from the existing
plan. Return design or behavior defects to their owners; do not let
parallel agents independently alter shared theme, panel, or selection
logic.

## Decision back to the agent

Accept the four-destination information architecture and
investigation-centered consolidation as the design direction.

Keep the revised technical plan's explicit feasibility and authorization
boundaries.

Refine the default analytical composition and add the visual/interaction
checkpoint above; another broad audit is unnecessary.

Success is not fewer menu entries or a larger feature count.

Success is that the user can understand a richer business question,
inspect its support, compare relevant subjects, and preserve the result
without losing their place.