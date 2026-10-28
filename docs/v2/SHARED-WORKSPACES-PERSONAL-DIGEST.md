# Shared research and personal reading — October 27, 2026

The user explicitly clarified the account boundary: Workspaces are universal,
collaborative research for signed-in analysts. Only layout settings and Personal
Digest are personal to an account. Do not introduce per-user Workspace ownership,
private research libraries, private company lists or private favorites/tiers.
Public anonymous access is not part of this instruction; application login and
all source, publication, identity and claim-review gates remain intact.

| Shared across analysts | Personal to the signed-in account |
| --- | --- |
| Workspace pages, captured references, notes, edits and history | Workspace view, column order/widths and other existing layout settings |
| Companies, favorites, tiers and company lists | Saved stories and read/unread state |
| Source feedback and research/review decisions | Reading queue progress, priority and Reader position |
| Landscape selections, research and reports | Which shared company lists populate Personal Digest |

Workspace sharing and per-account layout settings already exist in released
#408. This change scopes Digest state to the authenticated account across the
Digest, News/Reader save controls and the reading workflow. Existing JSON stores
remain authoritative; account buckets are added to those files rather than
introducing a second reading-state store. Other accounts' buckets are never
returned by the read-model services. Navigation counts include account identity
in their cache key. Personal reading audit events have account-scoped paths;
shared publication and other human-review histories keep their existing scope.

Identity comes from the validated application login, not request parameters,
page authorship or browser-local storage. Context is reset after each request;
existing serialized writes and atomic replacement preserve other accounts'
data. Single-analyst local operation keeps its existing behavior.

## Legacy continuity

Older shared saves, progress and subscriptions remain stored unchanged. The
configured original analyst retains that legacy Digest view; other accounts
start with an empty personal view. This is an access-continuity rule, not a
claim about who authored historical actions. An account's subsequent edits are
stored in its account bucket. Legacy source-level reading priorities do not
automatically populate another account's queue. Shared list definitions,
company marks, source feedback and review decisions remain available to everyone.
No existing accounts, source records or user research are replaced or deleted.

## Review evidence and remaining gates

The final affected run passes 76 deterministic tests. Ordinary fixture logins
prove shared Workspace viewing/editing and separate layouts, saved stories,
reading progress, Reader locations and subscriptions. Additional checks cover
legacy preservation, personal event visibility, cache separation and concurrent
account writes and fail-closed preservation of unreadable existing stores. Existing Digest/authentication/review-event/Workspace regressions
are included. Fixtures do not use Chris.H or change any real onboarding flag.

The visual guide now explains thirteen sections, including Workspaces, and the
shared-versus-personal boundary. Browser review with two ordinary fixture logins
on separate origins confirms shared list visibility, independent subscriptions
and save marks, and completing a story for one account while it stays unread for
the other. Both accounts see the same updated Workspace title. Cards versus Grid
stays account-specific and survives reopening. Digest and guide at a measured
412-pixel viewport have no horizontal page overflow; this is responsive emulation,
not physical-phone testing. Screenshots and review state are retained in ignored
`inbox/account-scope-review/`. The QA preview uses fictional accounts/source and
the public seed catalog; no production accounts or records are used.

Complete current-head CI, isolated production-runtime preservation and final
release review remain required. This is an unreleased implementation; no
production account or data migration has run.

The feed/Reader regression group passes 46 tests. All seven static-public checks
pass after updating the expected guide section count from twelve to thirteen;
the public card does not expose a live Workspace link or private material.
Canonical record validation and the whitespace check pass.
