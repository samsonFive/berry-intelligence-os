# Component Catalog — Product Visual System V1

Prototype contracts for surfaces that should later converge on one visual language.
**This does not implement production migration.**

Legend for adoption:
- **Owner** = recommended production owner when wiring
- **Adopt now** = high-value first surfaces
- **Can wait** = lower urgency

---

## App shell

| Field | Detail |
|---|---|
| Purpose | Persistent orientation: brand, primary nav, content canvas |
| Variants | Expanded rail · collapsed icon rail (future) · stacked mobile nav |
| Content hierarchy | Brand → primary destinations → utility/prototype note |
| Interactive states | Current page, hover, focus-visible |
| Accessibility | Landmark `aside`/`nav`; skip link; `aria-current` |
| Mobile | Rail stacks above content; 2-column quick links |
| Owner | AppShell / layout templates |
| Adopt now | `/today`, Landscape |
| Can wait | Legacy static report shells |

## Page header

| Field | Detail |
|---|---|
| Purpose | Name the job of the page without dashboard chrome |
| Variants | Standard · compact (embedded mini-shell) |
| Hierarchy | Eyebrow → title (display) → one lede sentence |
| States | Static; optional as-of meta |
| A11y | Single `h1` per view |
| Mobile | Title clamps; lede wraps |
| Owner | Page templates |
| Adopt now | Briefing, Landscape, profiles |
| Can wait | Dense ops tools |

## Typography

| Field | Detail |
|---|---|
| Purpose | Editorial hierarchy for intelligence reading |
| Variants | Display / page / section / card / body / meta / label / mono |
| Hierarchy | Fraunces for titles; Source Sans 3 for UI/body |
| States | n/a |
| A11y | Rem-based sizes; avoid low-contrast muted-on-canvas |
| Mobile | Clamp display sizes |
| Owner | Shared tokens |
| Adopt now | Briefing + Trust + Landscape prototypes → production tokens |
| Can wait | Keep mono for diagnostics only |

## Buttons & links

| Field | Detail |
|---|---|
| Purpose | Commitment vs navigation vs quiet secondary |
| Variants | Primary · secondary · ghost · danger · disabled · text link · original-source secondary |
| Hierarchy | One primary per region |
| States | Hover, focus-visible, pressed, disabled |
| A11y | Min 44px; clear names; focus ring |
| Mobile | Full wrap; no hover-only affordances |
| Owner | Shared UI kit |
| Adopt now | Briefing card actions, reader |
| Can wait | Rare admin tools |

## Filters & active chips

| Field | Detail |
|---|---|
| Purpose | Scope the feed without becoming a control panel |
| Variants | Toggle chips · active chip with clear |
| Hierarchy | Sticky bar above content |
| States | `aria-pressed`, clear action |
| A11y | Toolbar role; announced changes |
| Mobile | Wrap; horizontal scroll avoided |
| Owner | Briefing / Landscape filter bars |
| Adopt now | `/today`, Landscape |
| Can wait | Multi-facet advanced search |

## Feed card

| Field | Detail |
|---|---|
| Purpose | One intelligence item in a reading stream |
| Variants | Readable lead · attention/unreadable · focused |
| Hierarchy | Media → source/status → title → dates → observed → actions |
| States | Focus inset accent; attention styling |
| A11y | Heading per card; separate original-source from trust |
| Mobile | Stack media above text |
| Owner | `_briefing_card` / news cards |
| Adopt now | Daily Briefing |
| Can wait | Archive density modes |

## Competitor card

| Field | Detail |
|---|---|
| Purpose | Entity-centric compare entry |
| Variants | Active competitor summary |
| Hierarchy | Badges → name → context → short body → actions |
| States | Default / hover / focus |
| A11y | Card title as heading |
| Mobile | Single column |
| Owner | Landscape cards |
| Adopt now | Competitor Landscape |
| Can wait | Multi-compare matrices |

## Profile summary

| Field | Detail |
|---|---|
| Purpose | Company/entity identity at a glance |
| Variants | Company · non-company entity |
| Hierarchy | Identity mark → type eyebrow → name → meta → status → summary |
| States | Static + linked actions |
| A11y | Clear entity type in text |
| Mobile | Stack identity |
| Owner | Profile templates |
| Adopt now | Company profiles linked from Briefing |
| Can wait | Deep dossier tabs |

## Source Health row

| Field | Detail |
|---|---|
| Purpose | Operational source condition without tile dashboards |
| Variants | Healthy · Degraded · Blocked · Watching |
| Hierarchy | Status badge (text+dot) → source name → meta |
| States | As listed; not color-only |
| A11y | Status text required |
| Mobile | Stack meta |
| Owner | Source Health pages |
| Adopt now | Source Health list |
| Can wait | Charts/sparklines |

## Trust controls

| Field | Detail |
|---|---|
| Purpose | Rapid analyst feedback on feed + reader |
| Variants | Up / Down / History · reason chips · undo toast |
| Hierarchy | Controls below content; state badges nearby |
| States | Pressed, loading, blocked, pending, excluded |
| A11y | Group label; `aria-pressed`; live announcements; undo focus |
| Mobile | 44px targets; chips wrap |
| Owner | Trust Feedback production slice (after Sol domain) |
| Adopt now | Prototype contract ready; wire after Briefing visual pass |
| Can wait | Bulk review expansion |

## Drawer / lightbox

| Field | Detail |
|---|---|
| Purpose | In-app reader without losing feed context |
| Variants | Reader drawer · future lightbox for media |
| Hierarchy | Title header → meta → body → trust strip |
| States | Open/close; Esc; backdrop |
| A11y | `role=dialog`, focus move/restore |
| Mobile | Full-viewport width |
| Owner | Briefing reader |
| Adopt now | `/today?reader=` |
| Can wait | Media lightbox |

## Table

| Field | Detail |
|---|---|
| Purpose | Dense reviewable rows without spreadsheet feel |
| Variants | Compact data table |
| Hierarchy | Column headers · status badge · row action |
| States | Focus within controls |
| A11y | Captions; `scope` on headers |
| Mobile | Horizontal scroll contained in wrap |
| Owner | Review / ops tables |
| Adopt now | Small review tables |
| Can wait | Export-heavy grids |

## Review queue

| Field | Detail |
|---|---|
| Purpose | Smallest useful approval queue |
| Variants | Publication review list |
| Hierarchy | Count → ordered items → approve/skip/reject |
| States | Current item emphasis |
| A11y | Ordered list; clear button names |
| Mobile | Stack actions |
| Owner | Publication review |
| Adopt now | After trust promote → Evidence review |
| Can wait | Multi-queue dashboards |

## Badges & status labels

| Field | Detail |
|---|---|
| Purpose | State at a glance with text + dot |
| Variants | ok · pending · warn · danger · info · excluded |
| Hierarchy | Secondary to titles |
| States | Static |
| A11y | Never color alone |
| Mobile | Wrap |
| Owner | Shared |
| Adopt now | All primary surfaces |
| Can wait | Decorative chips |

## Alerts & undo toasts

| Field | Detail |
|---|---|
| Purpose | Restrained confirmation and blocking explanation |
| Variants | Info alert · warn alert · navy undo toast |
| Hierarchy | Message → optional Undo |
| States | Auto-dismiss; focus on Undo |
| A11y | `aria-live` |
| Mobile | Fixed bottom, full usable width |
| Owner | Shared |
| Adopt now | Trust + Briefing |
| Can wait | Multi-toast stacks |

## System states (loading/empty/incomplete/blocked/error)

| Field | Detail |
|---|---|
| Purpose | Honest system feedback |
| Variants | Skeleton · empty · incomplete · blocked · error |
| Hierarchy | Short explanation; next action if any |
| States | As named |
| A11y | Announce loading/errors |
| Mobile | Full width cards |
| Owner | Shared |
| Adopt now | Briefing empty What Changed; attention |
| Can wait | Fancy empty illustrations |

## Imagery slot

| Field | Detail |
|---|---|
| Purpose | Honest media representation |
| Variants | Article image · identity · empty · unavailable · non-company · AV marker |
| Hierarchy | Media supporting title — never fake photos |
| States | Broken remote → unavailable treatment |
| A11y | Decorative slots `aria-hidden` or labeled |
| Mobile | Full width |
| Owner | Cards / profiles |
| Adopt now | Briefing cards |
| Can wait | Rich media galleries |
