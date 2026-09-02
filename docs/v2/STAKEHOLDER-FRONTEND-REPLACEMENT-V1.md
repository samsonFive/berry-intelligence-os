# Stakeholder Frontend Replacement V1

**Lane:** Presentation replacement for stakeholder surfaces. FastAPI, review-publish, and trust objects unchanged.

**Baseline:** `origin/v2/intelligence-os` @ `6029fc0`.

**Rendered:** 2026-09-01 on `127.0.0.1:18082` with session login. Viewports 1440, 1366, 768. Harness: `scripts/stakeholder_visual_qa.py`.

---

## What changed

A second shell exists:

| Shell | Base template | CSS | Audience |
|---|---|---|---|
| Stakeholder | `base_stakeholder.html` | `stakeholder.css` | Today, Search, Company, Variety, Markets, Watchlist, Reports |
| Analyst / ops | `base.html` + `_v2_sidebar.html` | `app.css` + `v2.css` | Review, Collection, Coverage, Live Intelligence, Brief |

Business logic is not forked. Routes and services are reused. Presentation composition lives in `app/services/stakeholder_ui.py` (humanize + Today lead selection).

---

## Navigation before / after

**Before:** 37 sidebar links. WORK / DECIDE / MONITOR / LIBRARY / SYSTEM. Morning Brief, Reading Queue, and Monitoring all showed the same 126.

**After (stakeholder):** Today · Companies · Varieties · Markets · Search · Watchlist · Reports · More.

More holds Landscape, Assessments, Signals, Strategic questions, Learn, and Analyst workspace. No queue badges on the stakeholder bar.

---

## Design system

One file: `app/static/stakeholder.css`.

- Max content width 1120px
- Paper background `#f4f1ea`, navy accent `#1c3554`
- Serif headlines / sans UI
- 4/8/12/16/24/32/48 spacing
- Article row, entity header, metadata line, trust color (not badge soup)
- Pills with visible text (min-height 32px) — this was the empty-circle bug
- 1099px collapses primary nav to Menu; 768 stacks lead columns

`app.css` is not loaded on stakeholder pages. `v2.css` remains only so included reader/timeline fragments do not break.

---

## Page before / after

| Surface | Before | After |
|---|---|---|
| Today | Empty apology, broken berry circles, ops queues as hero | Editorial lead + supporting list. If the window is empty, strongest trusted/current material with an honest date note |
| Company | Snake_case roles, four header buttons, badge pile | Identity header, humanized roles, watch + varieties + recent activity |
| Search | Planasa 4th, `651.8 ms` printed | Best-match default; exact company first; latency hidden |
| Variety | Regions overlapped Who is involved; empty role dashes | Regions in their own section; only filled roles; identity slugs humanized |
| Geography | Six count cards first | Developments first; coverage is one metadata line |
| Reports | Empty theater, “Interpret request” | Build a report + three example prompts |

---

## Demo paths (no narration)

| Path | Result |
|---|---|
| A Login → Today | **Conditional.** UI is a publication. Lead items are old trusted patents because the corpus is stale. Dates are honest. Builder should not need to say “ignore the circles / ignore the 126s.” |
| B Search Planasa → Company | **Pass.** First company is Plantas de Navarra, S.A. Company page answers who / what changed. |
| C Variety | **Pass** for identity. No overlap, no overflow, no `no_canonical_identity_match`. Deeper sections still reuse older cards. |
| D Europe | **Conditional.** Developments lead. Company/variety lists still look like captured-intelligence inventory. |
| E Reports | **Pass** as an entry point. Build a report is obvious. PDF still requires generating a draft. |

Moments that still need a sentence: “These dates are publication dates; collection is not current.” That is data, not a broken widget.

---

## Viewport QA

18 screenshots, 6 routes × 1440 / 1366 / 768.

Acceptance:

- No horizontal overflow
- Berry filter chips have visible labels (80px+ width)
- No `no_canonical_identity_match` / `genetics_licensor` / `elapsed_ms`
- Planasa company first
- Zero `.v2-count-action` badges on stakeholder pages
- 768 uses Menu; search input is not clipped

---

## Remaining defects

**P0 (broken stakeholder widgets):** none of the original red-team P0s remain on these surfaces.

**P1:** Today lead is patent-title-heavy because that is the newest trusted material. Company/variety deeper sections still include `_intelligence_card` / timeline chrome. Search state labels (“Trusted”) are still visible. Landscape was not redesigned.

**P2:** Watchlist copy still mentions monitoring. Company list cards are not restyled beyond the shell.

---

## Tests

Focused: `tests/test_stakeholder_frontend_v1.py` plus Today, dogfood, guided-analyst, v2-shell, remote-auth updates.

Do **not** treat substring tests as visual proof. Use `scripts/stakeholder_visual_qa.py` at 1440 and 1366.

Full pytest / `validate_records` / `build_static` / four CI checks are the PR gate, not the iteration loop.

---

## Direction held

Replace stakeholder presentation. Keep backend. Analyst/ops stay on the old shell.
