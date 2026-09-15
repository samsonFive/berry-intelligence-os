# Product Experience Roadmap V1 — Current-State Audit

**Audit basis:** integration checkpoint `031c9b6a80bd72ce3f271933d8a1ea302decb077`; source strategy `da8740cf10660831ecfa5287b15fdb9f6e6c53ee`.

## Status vocabulary

`production and deployed` means evidenced on the canonical product. `implemented on an unmerged branch` means code exists but is not deployed. `validated on an unmerged branch` means focused/browser/static evidence exists but is not deployed. `prototype in progress`, `planned`, `absent`, and `blocked` are used literally.

## Matrix

| Area | Status | Evidence and boundary | Next implication |
|---|---|---|---|
| Competitor landscape | validated on an unmerged branch | `/competitors`, 33/33 rows, filters, drill-down, mobile capture, and no overflow are evidenced by the integration checkpoint. | Release-gate the foundation before layering Today features. |
| Canonical 33-entry roster | validated on an unmerged branch | 33/33 represented; 25 maturity 1, eight maturity 2, zero current usable coverage in the isolated runtime. | Representation is not operational coverage. |
| Company ↔ genetics relationships | implemented on an unmerged branch | Three assertions remain Pending review; Ozblu is a brand; UC Davis is a breeding program. | Resolve all links through canonical IDs. |
| Source Health | production and deployed foundations; integration extension unmerged | Discovery and article-body outcomes are separate; successful discovery plus blocked body is representable. | Add telemetry after approved runs. |
| Acquisition outcomes | implemented on an unmerged branch | Durable readable, access, bot-wall, consent, empty, shell, parser, network, retryable, and manual states exist. | Expose these states in Today/Reader. |
| Content-honesty gates | validated on an unmerged branch | `reader_content()` and `usable_in_app` exclude consent, bot-wall, empty, shell, and other unusable captures. | Never weaken the gate for UX speed. |
| Today/newsfeed | production and deployed | `/today` is recency-first, publication-date-honest, filtered, paginated, and has archive/empty behavior. | Evolve it into a reading workspace incrementally. |
| In-app article reader | production and deployed | Full reader, fragment, shared offcanvas, paragraphs/transcripts, provenance, and original-source fallback exist. | Make Reader the default feed action. |
| Thumbs-up/down review | absent | Existing Keep/Promote/Dismiss actions are not a typed thumbs model. | Implement only after state semantics are approved. |
| Review queues | production and deployed | Publication, Source Fidelity, Atomic, claim-testing, and other queues retain separate workflows. | Thumbs must hand off, not replace them. |
| Source activation | prototype in progress / planned | Source strategy covers 33/33 and proposes a 12-entry first wave; no activation was performed by that branch. | Await Sol’s operator-authorized checkpoint. |
| Images/visual news cards | implemented in limited surfaces | Cards and safe image handling exist, but no shared visual-card contract spans feeds. | Add identity/fallback policy with Reader. |
| Query/filter persistence | validated on an unmerged branch in landscape; partial in Today | Landscape query state is preserved; Today has GET filters/pagination but no saved views. | Make reading URLs reproducible, then personalize. |
| Mobile behavior | validated on an unmerged branch for landscape | 390×844 landscape capture reports no horizontal overflow. | Add Today/Reader mobile acceptance. |
| Unified navigation/design | implemented with competing shells | Stakeholder and V2 shells coexist. | Converge via shared tokens, not rewrite. |
| Report/evidence promotion | production and deployed | Existing review routes publish/save/reject; report handoff is review-first. | Deep-link Reader actions into existing review. |
| Read/unread behavior | partial | Morning Brief and reading queue state exist; Today lacks a complete analyst state contract. | Add state after feed identity is stable. |
| Saved/starred behavior | partial | Saved Brief Packs and queue/save behavior exist; no unified Today model. | Reuse conventions and preserve URL state. |
| External navigation | implemented but overused for legacy/unreadable paths | Reader has an original-source link; Today is not fully Reader-first. | Make it secondary when readable content exists. |

## Honest maturity summary

The integration is a strong foundation candidate, not a complete monitoring product. The 33/33 result means canonical representation, not current readable coverage. The source strategy proves research coverage and candidate mechanisms, not activation. The Python 3.14 attempt was blocked by declared `pydantic-core`/PyO3 compatibility and is not compatibility evidence.

