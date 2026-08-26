# Analyst Dogfood Runbook

Practical guide for using Berry Intelligence OS day-to-day. No architecture knowledge required. If something here doesn't match what you see, check the "If something looks wrong" section before assuming you did something wrong.

---

## MORNING

**Where to start:** open **Today** (the landing page after login). It shows what's new since your last visit, developing Signals, and a "worth revisiting" list of older items you haven't acted on. It also carries a system freshness state (see below).

**What the counts mean:**
- **New since last visit** — Evidence/Assessments captured since you last opened Today. This is a real timestamp comparison, not a guess.
- **Developing Signals** — recently-active Signals, shown with their real canonical status (`proposed`, `active`, `confirmed`, etc.) — never upgraded just for appearing here.
- **Worth revisiting** — older un-acted items, sorted so the most relevant surface first. Not a deadline; nothing here expires.
- **Freshness banner** (CURRENT / DEGRADED) — a real operational read of Source collection health, not a vague indicator. When DEGRADED, it names which sources and why (blocked, overdue, yield-degraded) — never a bare "something's wrong."

**What to process first:**
1. Check the sidebar's pending-review count and open **Review Operations** (`/review-ops`) if it's non-zero — this is where Publication Review and Atomic Review both live, plus session history.
2. Skim Today's "New since last visit" — anything that changes your read on a watched Company/Variety/Geography/Question is worth a look now rather than later.
3. Check **My Watches** (`/watches`) once per morning — it is a separate page from Today by design (Today is corpus-wide activity; Watches is your personal shortlist). It tells you plainly which watched objects have genuinely new intelligence versus which are quiet.

---

## DURING THE DAY

**Publication Review** (`/review-ops`, or the classic `/review` queue): trusted Evidence starts here. A draft is either accepted (published), rejected, or left pending — nothing becomes canonical Evidence without this step. Use **Analyst Review Session** (session sizes 5/10/25) if you want a bounded, resumable batch instead of the raw queue — sessions are pure navigation state; they never publish/affirm/approve/reject anything themselves, and your progress is always re-derived from real canonical state, not a fragile local flag.

**Atomic Review**: proposed atomic Evidence extractions, when extraction is enabled and a batch is qualified, go through the same kind of session/queue flow as Publication Review. If you see an empty Atomic queue with a message like "Extraction remains disabled," that is the honest, correct state on this deployment right now — not a bug (see "Automatic collection" below).

**Watchlists**: from a Company, Variety, Geography, or Strategic Question page, use "Add to watchlist" / "Remove from watchlist." Watches never affect trust — they're a private shortlist only you see. A watch is marked "seen" only when you explicitly open it from **My Watches** (the "Open" link) — simply browsing to the object's own page, or Today, or anywhere else, never marks it seen.

**Lineage**: every Signal detail page shows which Assessments cite it (and their AI PROPOSED/REVIEWED state); every Assessment shows its supporting Signals/Evidence/Facts and any explicit counterevidence. Follow the links — the chain is Evidence → Signal → Assessment → Strategic Question, and every hop is a real link, never inferred.

**Strategic Questions** (`/strategic-questions`): each question organizes what's known (Facts + Evidence), what's believed (Assessments, with AI PROPOSED clearly marked), what's being watched (Signals), and — new this cycle — an explicit **Tensions / contradictions** section. That section only ever shows a real recorded counterevidence relationship or an accepted Evidence-to-Evidence "contradicts" link; if neither exists, it honestly says "No explicit counterevidence or contradiction recorded for this question yet." No disagreement is ever guessed from wording.

**Brief Packs**: compose a presentation at `/brief-pack`, or open a saved one from **Saved Brief Packs** (`/brief-packs`). A saved pack always renders *current* trusted intelligence when reopened — it is never a frozen snapshot, so a pack you saved last week can honestly look different today if the underlying intelligence changed. That's by design (a "LIVE BRIEF"), not corruption.

---

## IF SOMETHING LOOKS WRONG

**A Source shows degraded/blocked:** open `/sources` and check that Source's own freshness reason — it always names a concrete cause (e.g. "26 consecutive collection failures," "more than one grace cycle past cadence"). This is expected to happen for a handful of sources at any given time; it does not mean the system is broken. A single long-blocked source (currently Growing Produce, blocked via robots/access restrictions) is a known, accepted condition.

**A transcript/body shows retryable/unavailable:** this is a real acquisition-layer outcome (fetch failure, blocked access, unsupported format), not silently swallowed. It will show as an honest failure state on the item rather than a fabricated body.

**"No new collection today":** check whether automatic Source polling is enabled (see "Automatic collection" below). On this deployment, it is currently **off by design** — see that section before assuming something failed.

**An unexpected queue state** (a session you thought you finished still shows items, or vice versa): Review Session progress is always re-derived live from canonical review history on every page load — it is never based on a stale local flag. If a queue count looks wrong, reload the page; if it's still wrong after reload, that's worth flagging to the operator, since it would mean the underlying canonical state itself (not just a cached count) is unexpected.

**A health/login issue:** this genuinely requires operator escalation (see below) — do not try to fix it by re-deploying or restarting anything yourself.

---

## END OF DAY

- **Nothing you view needs explicit saving.** Reading Evidence, Signals, Assessments, Strategic Questions, or Today never mutates anything — pure viewing is always safe.
- **Watchlist "seen"** only changes when you click "Open" from My Watches on that specific object. It is not affected by having Today or any other page open in a tab, and it does not reset automatically overnight.
- **Brief Pack saves are explicit.** "Save changes" updates the pack you have open in place; "Save as new pack" always creates a separate copy and never touches the original. Nothing autosaves in the background.
- **Publication/Atomic Review decisions are final and canonical** the moment you make them (publish/reject) — there's no separate "confirm" step afterward, so review deliberately before deciding, but there's also nothing further to do once you have.

---

## OPERATOR ESCALATION

These genuinely require deployment/SSH/code-level work, not analyst action:

- The application itself is unreachable (health check failing, not just a slow page).
- You believe a canonical trust object (Evidence/Signal/Assessment/Strategic Question) was mutated incorrectly and need it restored from backup.
- You need automatic daily Source polling turned on or off (see below — this is a deployment configuration change, not a UI setting).
- A Source needs to be added, retired, or have its collection adapter fixed.
- You need a runtime backup restored, or want to verify what a specific backup contains.

---

## Automatic collection: current posture

**As of this writing, automatic Source polling is intentionally disabled** on this demo/authoring deployment (`ENABLE_SOURCE_POLLING=false`). This means new Publications are not being discovered automatically during the dogfood period — the corpus reflects whatever was collected before the freeze, plus anything discovered manually.

This is compatible with a five-day dogfood focused on the **analyst workspace** (review, lineage, Strategic Questions, Watchlists, Brief Packs) using the existing corpus, which is large enough (1,268+ published Evidence, 6 Signals, 6 Assessments, 9 Strategic Questions as of this report) to exercise every workflow end-to-end.

If daily automatic ingestion is wanted for the dogfood period, enabling it requires an operator to set `ENABLE_SOURCE_POLLING=true` in the deployment's environment and redeploy — this is a deliberate, reviewable configuration change, not something that happens automatically, and is not something an analyst-facing session should flip on silently. Re-enabling it would resume the existing per-Source cadence scheduler (already built and previously proven safe against duplicate/repeated runs) — no new collection code would be needed.

---

*This runbook describes operational behavior verified as of canonical `707b920` / production deployment on the same SHA.*
