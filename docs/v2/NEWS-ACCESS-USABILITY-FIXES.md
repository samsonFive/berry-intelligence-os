# Analyst access and everyday News fixes

The October 13 user feedback asks for an additional analyst, Help on first
login, fresh news in one click, real source text instead of Google consent
boilerplate, clear publisher navigation, and a faster application.

This release is independent of the variety catalog/source research drafts.
Platform PR #398 is already released; catalog PR #400 remains a separate draft.
The new changes need their own current-head CI and release approval.

## Delivered in this candidate

- Additional analyst logins preserve the existing environment-based operator
  login. Passwords use salted scrypt hashes in the private runtime. New accounts
  open `/guide` on their first successful sign-in; later sign-ins honor the
  safe requested destination. Incorrect passwords do not consume onboarding.
  Account creation refuses duplicate usernames and unreadable existing stores.
  Disabled additional accounts lose authenticated access on their next request.
- One **Refresh news** click collects news and automatically displays the
  updated feed. Berry, country, date and review filters remain selected; page
  and story selection reset so the newest matching news is shown first.
  Failure stays visible, without an automatic reload or false success.
  A transient unavailable status is retried within a bounded ten-minute window,
  rather than being reported as a completed refresh.
- Reader capture decodes locally resolvable Google News links, checks each
  network redirect, and rejects unresolved Google/consent pages. Expanded
  consent detection also protects previously stored bodies and capture files
  at display time, without rewriting source or review history.
- A visible source link sits beside the Reader actions. An exact matching
  capture may provide the final publisher URL. Unresolved wrappers are labeled
  **Open source link**; a separately recorded publisher website is offered
  where available. No guessed article URL is substituted. When original text
  is unavailable, the available summary remains readable and clearly labeled.
- Unchanged pending metadata is cached privately with a 16 MB serialized-metadata budget.
  Every file is rechecked for identity, size, modification and change timestamps.
  Edits, rejections, deletions and new files appear on the next read. Relevance
  decisions are cached by exact input text/URL/date and current company/variety
  names. Trust, filters, marks and entity assignments are still evaluated anew.

## Validation and practical limits

Read-only production probes measured News at 2.675/2.735 seconds; Companies at
0.281 seconds and Help at 0.072 seconds. Profiling found repeated pending-file
parsing and relevance regex work in the News data path.

On the existing isolated local release copy, 1,270 source records produced the
same 784 matching stories and identical displayed IDs/order before and after:

| Data path | Before, warmed | Candidate, cold | Candidate, warmed |
| --- | ---: | ---: | ---: |
| Metadata | 0.771 s | 0.403 s | 0.396 s |
| Metadata plus feed model | 2.630 s | 1.861 s | 0.478 s |

This is a local data-path comparison, not a production page-load guarantee.
The final affected Python suite, including capture bounds and source-to-variety
checks, passed 199 checks. Full CI initially exposed two regressions: malformed
capture passages and malformed URL decoding. Both now fail safely as unavailable
content; the complete required suite must pass on the corrected head.
Four JavaScript refresh
scenarios passed. Native isolated browser review confirms a newly captured,
relevant story appears after one click, with its berry scope retained, and
Google consent text is excluded from the Reader. Fixtures explicitly identify
themselves; they are not production news. Record validation passed.
The production-side candidate benchmark was rejected by automatic approval
review; no candidate code was executed in the live container. Private receipts,
browser fixtures, screenshots and credentials stay under ignored `inbox/`.

The existing analyst workspace remains shared. Separate private digests,
per-user preferences, roles, administrative user management and multiple-worker
write coordination belong in a dedicated multi-user mission. These logins do
not imply tenant isolation. The supplied new account is staged privately and
must be installed additively in production after release approval.

An unresolved Google wrapper, paywall or access restriction may still prevent
full-text capture. The Reader reports that limitation and offers recorded
source/publisher links; it never presents boilerplate as the original article.
A separate acquisition mission should address reliable publisher identity and
capture coverage. A wider performance mission should measure cold/warm route
budgets, mobile/network latency, background-job contention and large-corpus
scaling; the measured immediate News bottlenecks are addressed here.
