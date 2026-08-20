# UI / UX V2 Design Readiness

**Status:** Audit only. No reskin. No CSS implementation authorized by this document.  
**Date:** 2026-08-20  
**Against:** `origin/v2/intelligence-os` at `9b6ca42` (PR #41 merged).  
**Stack:** FastAPI + Jinja2 + one CSS file (`app/static/app.css`) + almost no JS.  
**Related:** `docs/02-design-system/DESIGN-SYSTEM.md` (foundation intent), `docs/v2/PHASE-1-5-VISUAL-REVIEW.md` (2026-08-13 landscape/entity review). Claude owns a parallel multi-berry portability audit.

The product workflows are increasingly coherent. The visual system is not. Objects, queues, and trust states multiplied faster than the component language.

---

## Current UI assessment

The live analyst product is a **server-rendered intelligence workstation**, not a marketing site and not a generic admin CRUD app. Daily work starts at Morning Brief, moves through Feed / Reader / Pending Triage / Signal Review, and lands on Company, Landscape, Watches, and authored Assessments.

What works:

- Navy / light-canvas / purple identity is recognizable and restrained.
- Copy on many pages already distinguishes object types in prose (“not a conclusion”, “does not prove”, “untrusted until you promote”).
- Action vs inventory counts exist in CSS (`.nav-action` vs `.nav-inventory`) and are documented in `AGENTS.md`.
- Keyboard triage on Feed is a real workstation behavior.
- Honest empty states and coverage disclaimers are better than typical dashboards.

What failed to keep up:

- ~20 primary nav links, blueberry-centered, with Signal Review buried inside `/signals*`.
- Almost every semantic distinction is a **pill**.
- Two card families (`.card` left-border by source type vs `.intel-card` left-border by trust) plus Brief/Landscape one-offs.
- Mobile: sidebar `display:none` at ≤834px with **no hamburger**.
- Landscape is still `/landscapes/berries/blueberry` in route and nav label.
- Feed is labeled **Feed** in nav and **Scanner** on the page. Newsfeed (`/`) still exists as a second stream.

Frontend architecture remains extractable HTML/CSS. A commercial admin kit can accelerate **chrome**. It cannot replace Intelligence OS semantics.

---

## 1. Screen inventory

Authenticated surfaces from `app/main.py` + `app/templates/`. Nav in `app/templates/base.html`.

| Screen | Route | Analyst job | Primary action | Secondary | Density | Repeated | Unique | Visual issues | Admin feel | Mobile | Shared-pattern opportunity |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Login | `/login` | Authenticate | Sign in | none | low | form fields | motif + standalone shell | duplicate CSS in template + `app.css` | low (best “product” screen) | ok | keep custom; do not kit-replace |
| Morning Brief | `/brief` | Start the day: what changed, what is still important, what can wait | Open item / thread / signal | Promote / Dismiss / Reject from triage | high | `.brief-item`, badges, delta tiles | delta strip, pending buckets, emerging-signal cards | 5 right-aligned metric lines + 6 delta tiles; purple action metrics mixed with inventory | medium (ops dashboard at top) | no nav | PageHeader + IntelligenceCard + StoryCard + SignalCard + DecisionBar |
| Feed / Scanner | `/work-queue` | Scan and decide trust | Read / Promote | Save, Reject, Open source, filters, keyboard | high | `.intel-card`, chips, action buttons | scanner KPI strip, keyboard current-card | page title ≠ nav label; 5 giant KPI tiles; stacked actions | high (Scanner + tiles) | no nav | IntelligenceCard + DecisionBar; drop or demote KPI strip |
| Reader | `/intelligence/{id}` | Consume source, then decide | Promote / Save / Reject | Open original, entity chips, claims | high (spoken transcripts) | trust badge, chips | two-column reader, locators, patent dl, AI panel | “Back to feed” is a primary purple CTA; decision lives in the side column | medium | stacks to 1 col | EvidenceCard + DecisionBar + SourceChip |
| Story thread | `/threads/{id}` | See related coverage without treating it as a conclusion | Open primary / member | Dismiss redundant | medium | badges, timeline | “not a conclusion” disclaimer, supporting-signal links | timeline, related coverage, and trust-status lists repeat the same members | low | no nav | StoryCard + Timeline + EvidenceChain |
| Reading Queue | `/queues/reading` | Finish unread/saved | Mark read / Promote | Bulk mark, Keep, Dismiss | high | queue table, filters | buckets (top/saved/adjacent/backlog) | table + card hybrids; stacked buttons | medium | tables overflow | DataTable + FilterBar + DecisionBar |
| Pending triage | `/brief#pending-triage` | Rank untrusted drafts | Open thread / Read | Dismiss, Reject, bulk dismiss | high | brief-item, developing-story badge | bucket counts | story cards still look like generic brief items | medium | no nav | StoryCard vs IntelligenceCard must differ |
| Publications | `/review?kind=publication` | Human trust gate | Review / Approve | Save, Reject, + Next, filters | high | publication-card, scanner strip | workbench filters, keyboard | filter bar is an admin console; 10+ selects | **high** | cramped | FilterBar (collapsed) + IntelligenceCard |
| Claims review | `/review?kind=atomic` | Approve atomic evidence | Approve one claim | Reject, parent context | high | workbench | atomic-specific | same workbench chrome as publications | **high** | cramped | keep custom; system/admin |
| Signal catalog | `/signals` | Browse trusted patterns | Open signal | New Signal, Review candidates | low | `.card` + `.badge-signal` | none | catalog cards look like entity cards | medium | ok | SignalCard (trusted variant) |
| Signal Review | `/signals/review` | Decide on untrusted candidates | Review candidate | Open company | high | `_signal_card.html` | bucket strip + limited-evidence overlay | not in nav (active-state shares `/signals*`); cards are brief-items with extra pills | medium | no nav | SignalCard + ConfidenceIndicator + EvidenceQuality |
| Signal candidate | `/signals/candidates/{id}` | Inspect one candidate | Confirm / Defer / Dismiss | Company, evidence list | medium | badges, does-not-prove | independence notes, opaque id | Confirm/Dismiss look like generic approve/reject | medium | no nav | DecisionBar + EvidenceChain |
| Trusted signal | `/signals/{id}` | Read a published pattern | none / watch | evidence links | medium | object-detail | lineage | strength/status both pills | low | ok | SignalCard detail |
| Assessments list/detail/new | `/assessments*` | Read or author interpretation | Open / Create | none | medium | table vs card mix | “not a fact” eyebrow | list is a table; landscape uses assessment cards | medium | table overflow | AssessmentCard |
| Recommendations | `/recommendations*` | Read or decide a proposed action | Accept / Edit / Reject | Create | medium | similar to assessments | proposal-decision | same purple CTA as everything else | medium | ok | AssessmentCard sibling (ActionCard) |
| Landscape | `/landscapes/berries/blueberry` | Market picture for one crop | Drill region / lens | jump nav | **very high** | tables, KPI tiles, badges | sticky filter + jump nav, public/internal lenses | **Blueberry hardcoded**; giant census tiles; prototype “protected enrichment” copy | high (census dashboard) | tables clip | berry ContextSelector; demote KPI tiles |
| Companies / varieties / geos | `/entities/{type}` `{id}` | Entity recall | Open entity | follow intelligence | medium–high | detail-card, trust-summary, badges | open signals, trait table, attributes dl | raw ids in attributes (Phase 1.5); blueberry listed as a field not a context | medium | ok | EntityChip + WatchIndicator + OpenSignals |
| Watches | `/queues/monitoring` | Maintain monitors | Pause / Snooze / Stop | Confirm/Dismiss alerts | medium | queue list | alerts spliced onto same page | Alerts is a hash, not a route; Confirm stacked vertically | medium | ok | WatchIndicator + DecisionBar |
| Alerts | `/queues/monitoring#alerts` | Clear proposed-signal decisions | Confirm / Dismiss | View | low | action buttons | none | same page as watches; competing jobs | medium | ok | merge into Signal Review or a dedicated Action inbox |
| Source health | `/sources` | Know if collection is alive | Check now / add source | filters, toggle, delete | high | filters, cards | coverage/stale/failing line, polling banner | titled Sources vs nav “Source health”; admin filters | **high** | card wrap | SourceHealthIndicator + FilterBar |
| Commercial positions | `/queues/commercial_position` | Inventory tagged evidence | none (not a queue) | Accept/Edit/Reject proposals | medium | queue template reused | proposals vs tagged list | queue chrome on an inventory page | medium | ok | don’t use queue template |
| Claim testing | `/queues/testing` | Pass/Fail/Defer claims | Pass / Fail | Defer, Reopen | medium | queue table | testing semantics | lives under System only in authoring mode | medium | ok | system/admin |
| Strategic questions | `/strategic-questions*` | Frame what we are answering | Open | none | low | list | none | catalog, not daily work | low | ok | Intelligence catalog |
| Newsfeed | `/` | Browse captured items | Open | search `?q=` | medium | `.card` source-type borders | region filters | **duplicates Feed** with older card language | high | no nav | retire or fold into Feed trusted filter |
| Intake | `/intake*` | Manual capture | Submit draft | attachments | medium | forms | not in primary nav | hidden system tool | **high** | forms stack | system/admin |
| Search | `/?q=` or static `/search/` | Find entity or article | Open result | none | medium | two implementations | Pagefind vs Python | live vs static ranking diverge | medium | search bar dominates topbar | keep search; unify ranking later |
| Trusted evidence | `/evidence/{id}` | Public/static evidence view | none | validate/purge (authoring) | medium | card | static snapshot path | company recent-intel still sometimes thinks in `/evidence/` for static | low | ok | EvidenceCard |

---

## 2. Visual language audit

Tokens are **hardcoded hex**, not a scale. Font: Inter / system-ui. Text `#14213d`, canvas `#f5f7fb`, sidebar `#08234d`, accent `#6d50c7`, links `#3d5c94`.

| Element | Current | Inconsistency |
|---|---|---|
| Typography | H1 30px, body ~14–16, eyebrows 12px/800/0.08em purple | Same H1 for Brief and 80-char legal entity names; ISO timestamps in prose; no type ramp |
| Spacing | Page padding 32px, cards 18px | 16px on mobile for some regions only; Brief/Landscape/Reader each invent section padding |
| Card hierarchy | `.card` 10px radius + source left-border; `.intel-card` 14px + trust left-border; `.brief-item` 10px | Three families. Landscape adds more. Source-type color ≠ trust color |
| Badges | Default purple `.badge`; trust, object-type, limited-evidence, public/locked, status-active | Default badge is purple for **anything**. Emerging, Proposed, Watched, Direct berry all read as the same object |
| Status colors | Green trusted/active; amber attention; red disputed/reject; purple pending | Purple also means brand, CTA, nav action, why-it-matters, timeline dots |
| Action buttons | `.button-link` purple fill; `.action-approve` green; `.action-reject` red; filter buttons `#173d70`; raw `<button>` in headings | Promote and Read both green. Back-to-feed is the same CTA as New Signal. Sign out is an underline |
| Tables | `.queue-table`, `.brief-table`, `.trait-table` | Landscape competitive-field still wraps badges into row height (Phase 1.5) |
| Filters | `.filters` labeled selects; `.intel-filters` pill links; `.filter-chip` landscape | Three filter languages |
| Tabs | None as a component. Landscape jump-nav buttons fake tabs | No selected-tab token shared with Feed filters |
| Navigation | 240px navy, groups, action/inventory | 20+ links; `/signals*` all active together; Intake missing; Alerts is a hash |
| Alerts / banners | success / error / warning | Does-not-prove is a **box**, banners are another box; both red/amber |
| Confidence | `badge-muted` “Confidence Medium” or assessment table cell | Strength, status, and confidence are interchangeable pills |
| Trust | left-border + `.intel-trust-*` | Pending purple border competes with brand purple |
| Evidence | `.evidence-quality-full/limited` kickers | Stronger than badges — keep; not used on Feed cards |
| Pending | `.intel-card-pending`, “Pending” pill, AI-assisted pill | Often **three** pending labels on one card |
| Source attribution | grey `.draft-meta` line | Sometimes a chip, sometimes a sentence, sometimes only in the kicker |
| Empty states | italic `.empty-state` | Honest copy, weak visual (looks like a caption) |
| Timelines | `.activity-timeline` purple dots | Story thread also lists the same items in three other sections |

**Mobile:** `@media (max-width: 834px)` hides `.sidebar` entirely. Comment cites Phase 1.5 “MUST FIX BEFORE PHASE 2”. Still unfixed. Search remains; primary nav does not.

---

## 3. Information semantics (must not all be pills)

| Meaning | Job | Current look | V2 treatment |
|---|---|---|---|
| **ACTION** | Needs an analyst decision | Purple nav pill + green/red buttons | **Count + verb** in a compact action chip (not a catalog number). Decision controls live in a DecisionBar, not a rainbow of same-sized pills |
| **INVENTORY** | Reference / count | Grey nav text; some pages still shout the number | Quiet numeric text. Never purple. Never a badge |
| **TRUSTED INTELLIGENCE** | Human-published | Green left-border + TRUSTED pill | Calm confirmed mark (left rail or stamp). No extra “trusted” pill if the rail already says it |
| **PENDING / UNTRUSTED** | Not yet a conclusion | Purple border + Pending + AI-assisted | Single **Untrusted** state. AI provenance is a footnote, not a peer badge |
| **DEVELOPING STORY** | Organizational grouping | `Developing story` + `Not a conclusion` pills on a brief-item | **Thread shape**: connected timeline stub, stacked sources, no trust CTA. Accent distinct from Signal (recommend cool slate, not purple) |
| **EMERGING SIGNAL** | Untrusted pattern | `badge-signal` + Proposed + Confidence + Direct berry | **Pattern mark** (direction/strength as a small meter, not a word pill). Always show independence + does-not-prove |
| **CONFIRMED SIGNAL** | Reviewed candidate, still not `data/signals/` | Green “Confirmed” as if published | **Confirmed candidate** ≠ **Published signal**. Use a two-step mark: “Analyst confirmed” vs “In catalog” |
| **ASSESSMENT** | Human interpretation | Blue `.badge-assessment`, sometimes “AI PROPOSED” | Document metaphor (quoted view + confidence meter + “would change our view”). AI-proposed is a watermark, not a peer of REVIEWED |
| **WARNING / DOES NOT PROVE** | Bound the claim | Red box with kicker | Keep the **box**, never a pill. Highest visual severity after disputed |
| **SOURCE HEALTH** | Collection vitality | Banner + “0 current · 22 stale” sentence + priority pills on cards | Traffic-light **indicator** (current / due / stale / failing), not a badge on every card |

Do not encode berry, watch-match, and relevance as the same badge component as trust.

---

## 4. Core product shell (recommend, do not implement)

```
┌─────────────┬──────────────────────────────────────────────┐
│ Brand       │ Context: [Global ▾] [Berry ▾] [Entity search]│
│             │                         Analyst · Sign out   │
│ WORK        │ PageHeader: eyebrow · title · one primary    │
│  Brief      │ DecisionBar or FilterBar (contextual)        │
│  Feed       ├──────────────────────────────────────────────┤
│  Reading    │ Page body                                    │
│             │                                              │
│ DECIDE      │                                              │
│  Signals    │                                              │
│  (review    │                                              │
│   default)  │                                              │
│  Review     │                                              │
│             │                                              │
│ MONITOR     │                                              │
│  Watches    │                                              │
│  Sources    │                                              │
│             │                                              │
│ LIBRARY     │                                              │
│  Landscape  │                                              │
│  Companies  │                                              │
│  Assessments│                                              │
│             │                                              │
│ SYSTEM ▾    │ Intake, Claim testing, Claims, Publications  │
│             │ advanced, Strategic questions                │
└─────────────┴──────────────────────────────────────────────┘
```

Requirements:

- **Global navigation** ≤ 10 visible items. System/admin behind a disclosure.
- **PageHeader** is the only H1 + one primary action. Metrics move into the page, not the header right-rail as five competing action lines.
- **ContextSelector**: Global | Berry | Company | Geography. Not a blueberry-named nav item.
- **Berry selector** is first-class. Empty/global is valid.
- **Company/entity context** can pin a company across Brief/Feed/Signals.
- **Search** stays global; placeholder must not assume one crop.
- **Notifications / action counts** only on WORK + DECIDE items, using ACTION semantics.
- **Analyst identity** stays top-right; Sign out is not a primary button.
- **System/admin separation** is visual (muted group), not just a heading.

Mobile: persistent bottom or top app nav, or a hamburger that reveals the same groups. Hiding the sidebar with no replacement is not a responsive strategy.

---

## 5. Multi-berry requirements

`BERRIES` in `app/main.py` already lists strawberry, blueberry, raspberry, blackberry identically. The UI does not.

Hardcoded blueberry today:

- Nav label and route `/landscapes/berries/blueberry`
- Static build emits only that landscape
- Morning Brief copy: “direct blueberry intelligence”
- Company pages list berries as a metadata field, not as a switchable context

V2 contexts (orthogonal, combinable):

| Context | Meaning | Must not do |
|---|---|---|
| GLOBAL | All berries | Hide crop identity; show it as a chip on items |
| BERRY-SPECIFIC | One crop | Name the crop in the shell, not in every page title |
| COMPANY | One company across berries | Do not assume Costa = blueberry only |
| GEOGRAPHY | One region across berries | Mexico is not a blueberry filter |
| SIGNALS | Patterns across berries | Candidate cards must show berry chips, not a blueberry theme |

Do not use blueberry color, icon, or word as the product brand. Berry chips are data, like EntityChip.

Wait for Claude’s portability audit before locking a theme that bakes in a single-crop IA.

---

## 6. Key page hierarchy (wireframe in words)

### Morning Brief

1. Context (berry/global) + last-check sentence  
2. **Action strip** (only ACTION counts: review now, failing sources, emerging to review)  
3. Since last brief (compact, hide zero groups)  
4. Emerging signals (SignalCard, max bounded set)  
5. Important unresolved  
6. Pending triage (StoryCard / IntelligenceCard by type)  
7. Source health one-liner (link out)  

Inventory (reading-queue size, watch count) is footer or secondary, not header chrome.

### Live Intelligence (Feed)

1. PageHeader “Feed” (stop calling it Scanner in the H1)  
2. FilterBar (type / trust / berry)  
3. Stream of IntelligenceCards  
4. Keyboard status + DecisionBar on the current card  

Scanner KPI tiles are optional, collapsed, or removed. They make the product feel like an ops monitor.

### Reader

1. Trust + source + date as a stamp, not five pills  
2. Body / transcript / patent  
3. Sticky DecisionBar (Read original, Promote, Save, Dismiss, Reject)  
4. Side: entities, claims, evidence quality, does-not-prove  

“Back to feed” is a text link, not the primary purple button.

### Story Thread

1. Developing-story identity (never a Promote-thread control)  
2. What happened (primary source only)  
3. Timeline (the only member list)  
4. Optional “may support signals” (SignalCard stubs)  
5. Entities  

Delete redundant “related coverage” and “trust status per item” lists if the timeline already shows them.

### Signal Review

1. Clarify **candidates, not catalog** in the header  
2. Bucket strip (Review now / soon / weak / deferred)  
3. SignalCards with independence + evidence quality  
4. Limited evidence as overlay icon, not a duplicate list unless needed  

Nav should land here when the action count is “N emerging”.

### Company Profile

1. Identity + berry chips + watch control  
2. **Open questions**: emerging / confirmed-candidate / published signals  
3. Recent intelligence (same Reader links)  
4. Network / varieties  
5. Assessments touching this entity  
6. Facts / evidence  

Trust-summary census tiles (evidence/sources/updated) stay small and secondary.

### Landscape

1. Berry ContextSelector (required; blueberry is one value)  
2. Region + lens  
3. Executive readout (assessments, not KPI census)  
4. What we think  
5. Actors / pressure / regions  
6. Coverage limitations  

Move 484 Evidence / 140 Sources style tiles below the fold or into a coverage section. They invite “this is the whole market.”

### Watch / Monitoring

1. Separate **Watches** (inventory of monitors) from **Alerts** (ACTION)  
2. Alerts should deep-link to Signal Review or a DecisionBar row  
3. Source health is adjacent, not a sibling of Landscape  

---

## 7. Component system

| Proposed | Conceptual today | State |
|---|---|---|
| AppShell | `.shell` + `.sidebar` + `.main` | exists; no mobile nav; no context row |
| Sidebar/Nav | `base.html` nav | exists; too long; blueberry hardcoded |
| PageHeader | `.page-heading` + `.eyebrow` | exists; overloaded with metrics/CTAs |
| ContextSelector | Landscape scope label only | **missing** |
| IntelligenceCard | `.intel-card` + `_brief_item` | duplicated with `.card` and `.brief-item` |
| EvidenceCard | reader body + `/evidence/` | ad hoc |
| StoryCard | `_story_thread_card.html` | exists; still looks like brief-item |
| SignalCard | `_signal_card.html` | exists; too many peer pills |
| AssessmentCard | landscape + list table | **split** (table vs card vs landscape row) |
| StatusBadge | `.badge` | overused; default purple |
| ConfidenceIndicator | muted badge / table cell | **missing as a component** |
| SourceChip | `.draft-meta` | not a chip |
| EntityChip | `.intel-chip` | exists; good |
| BerryChip | metadata text / muted badge | **missing** |
| Timeline | `.activity-timeline` | exists; reused poorly |
| EvidenceChain | independence lists, evidence_ids | ad hoc per page |
| DecisionBar | `_pending_decision_actions.html` + feed actions | exists; stacked, duplicated, too many peers |
| EmptyState | `.empty-state` | exists; italic-only |
| DataTable | `.queue-table` / `.brief-table` | exists |
| FilterBar | `.filters` / `.intel-filters` / `.filter-chip` | **three** |
| WatchIndicator | watch badges / queue | ad hoc |
| SourceHealthIndicator | coverage sentence + banners | ad hoc |

---

## 8. Envato / template evaluation checklist

A candidate **MUST**:

- Yield plain HTML + CSS (or CSS variables) usable from Jinja `{% extends %}`  
- Not require a React/Vue/Angular rewrite  
- Provide a responsive sidebar **with a replacement nav under ~900px**  
- Support dense tables + cards on one canvas  
- Include timeline, tabs, badges, search, filters, accessible forms  
- Dark navy + light content is fine; dark/light toggle is optional  
- License that allows modification and app embedding (regular or extended as required)  
- Small, modern CSS (no jQuery UI, no Bootstrap 3, no Moment.js)  
- Aesthetic: research / intelligence / editorial — Bloomberg/FT/Palantir-calm, not crypto

**Red flags:**

- Crypto / NFT / gaming dashboard look  
- Glassmorphism, mesh gradients, neon  
- Giant KPI tiles as the default home  
- Animation-heavy page transitions  
- Bootstrap version conflicts (we have **no** Bootstrap today — do not add one unless the kit is CSS-only and isolated)  
- Tightly coupled SPA (Vue CLI starter, Next.js admin, Angular Material)  
- Inaccessible custom selects that break Jinja forms  
- Huge vendor JS bundle  
- Markup that cannot be extracted without the vendor’s JS runtime  

---

## 9. Redesign sequence (based on actual coupling)

1. **Tokens + AppShell + mobile nav + ContextSelector** — every page inherits this; blueberry nav is a portability blocker  
2. **Semantic components** (StatusBadge, DecisionBar, BerryChip, ConfidenceIndicator) — stop the pill collapse  
3. **Morning Brief** — daily start; currently the densest mix of objects  
4. **Feed rename + IntelligenceCard + keyboard DecisionBar** — core loop  
5. **Reader** — same DecisionBar; drop purple “Back to feed”  
6. **Signal Review + SignalCard** — already the right IA; needs visual distinction from stories  
7. **Company Profile** — multi-berry and entity context live here  
8. **Story Thread + Timeline** — remove redundant lists  
9. **Reading / Pending queues** — after cards exist, tables become simpler  
10. **Watches vs Alerts vs Source health** — split ACTION from inventory  
11. **Landscape** — after berry context exists; heaviest page; last among analyst surfaces  
12. **Catalog + system/admin** (Assessments, Recommendations, Intake, advanced Publications, Claim testing)

Do **not** reskin Landscape first. It would freeze blueberry as the product.

---

## What can safely be themed

- AppShell grid, sidebar background, topbar, search field  
- Type ramp, spacing scale, radius, shadows  
- DataTable, FilterBar, form controls, banners, empty-state chrome  
- Login card layout (keep motif or replace with a quieter panel)

## What must remain custom

- Trust / pending / confirmed-candidate / published-signal distinctions  
- Does-not-prove and evidence-quality treatments  
- Story vs Signal vs Assessment vs Recommendation  
- Opaque signal-candidate identity and independence/reprint rules  
- Feed keyboard triage  
- DecisionBar verbs mapped to existing POST routes (never a kit “CRUD toolbar”)  
- Static-build vs live-authoring differences  
- Berry as data, not as skin

---

## Direct answers

1. **Is the current frontend compatible with a commercial HTML/admin UI kit?**  
   **Yes, if and only if** it is HTML/CSS extractable. The app is Jinja layouts + `app.css`. A React/Vue kit is incompatible without a strategic rewrite we should not do.

2. **Would a kit materially accelerate the redesign?**  
   **Yes for shell, tables, forms, responsive nav.** **No for intelligence semantics.** Expect 20–30% of visual work in chrome, 70–80% still custom cards and states.

3. **Which parts could be reused directly?**  
   Sidebar/topbar structure, grid, buttons, inputs, tables, tabs, dropdowns, modal/drawer if accessible. Possibly login layout.

4. **Which Intelligence OS components must remain custom?**  
   IntelligenceCard, StoryCard, SignalCard, AssessmentCard, DecisionBar, EvidenceChain, ConfidenceIndicator, SourceHealthIndicator, Does-not-prove, BerryChip, WatchIndicator, Feed keyboard current-card.

5. **Should we select a theme before or after Claude’s multi-berry audit?**  
   **After.** Theme selection will bias IA (single-crop dashboards, KPI homes). We already know blueberry is hardcoded; Claude’s audit should tell us how deep that goes in data and copy before we buy a shell.

6. **Top five visual problems today**  
   1. Everything is a purple/grey pill  
   2. Nav is an unprioritized inventory, blueberry-centered, Signal Review hidden  
   3. Mobile nav is missing  
   4. Scanner KPI tiles + Landscape census tiles make an intelligence product look like an admin dashboard  
   5. Three card systems and three filter systems

7. **What should the ideal product feel like?**  
   A **calm intelligence workbench**: editorial density, obvious trust, few actions, crop as context not costume. More like a well-made research terminal than a SaaS analytics theme. The analyst always knows: *is this a decision, a count, a story, a signal, or a conclusion?*

---

## Screenshot index (live app, 2026-08-20)

Captured against `http://127.0.0.1:18111` on this revision, with `/workspace/inbox` runtime data.

| File | Screen |
|---|---|
| `v2_audit_01_login.png` | Login |
| `v2_audit_02_morning_brief_top.png` | Morning Brief |
| `v2_audit_04_morning_brief_pending_triage.png` | Pending draft triage |
| `v2_audit_06_live_intelligence_feed.png` | Feed / Scanner |
| `v2_audit_07_reading_queue.png` | Reading Queue |
| `v2_audit_08_watches.png` | Watches + alerts |
| `v2_audit_10_signals_catalog.png` | Trusted signal catalog |
| `v2_audit_11_signal_review.png` | Signal Review |
| `v2_audit_12_landscape_top.png` | Blueberry Landscape |
| `v2_audit_15_company_profile_top.png` / `v2_audit_29_company_costa_top.png` | Company |
| `v2_audit_17_source_health.png` | Source health |
| `v2_audit_18_assessments.png` | Assessments |
| `v2_audit_20_publication_review.png` | Publication review |
| `v2_audit_21_newsfeed.png` | Newsfeed (legacy stream) |
| `v2_audit_22_intelligence_reader.png` | Reader |
| `v2_audit_23_story_thread.png` | Story thread |
| `v2_audit_24_signal_candidate_detail.png` | Signal candidate |
| `v2_audit_27_brief_mobile_no_nav.png` | Mobile Brief: sidebar gone |
