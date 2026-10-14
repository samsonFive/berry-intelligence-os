# News, reader, performance and analyst accounts

The October 14 continuation authorizes completing and releasing the everyday
News fixes and adding Julio.A to the same live instance. Chris.H and Julio.A
have been provisioned additively; plaintext passwords are never committed.
This mission does not release the separate variety-catalog research drafts.

## Resulting workflow

- Clicking **News** explicitly starts public-news collection, then displays the
  newest results automatically. The page consumes the refresh marker so the
  resulting reload cannot start another collection. **Refresh news** also takes
  one click and preserves berry, country, date and review filters, resetting
  pagination/story selection. Failed and partial collection stay visible.
- Clicking a story immediately opens the existing shared Reader. If useful
  source text is missing, its JavaScript automatically calls the capture POST;
  another content-loading click is unnecessary. Cached useful text appears
  directly. Loading, failure, a clearly labeled synopsis, retry and publisher
  links remain usable. Late retrieval cannot replace another story. Retrieval
  never publishes or confirms source claims.
- Consent, Accept All/Reject All, ad-blocker and first-visit notices are omitted
  at display time wherever they occur, including mixed or old saved text.
  Source reporting about consent controls remains readable. Known dialog
  containers are excluded during HTML parsing. Original Evidence, source
  history and analyst wording remain unchanged on disk.
  Old captures ending at Google News/consent/account hosts are rejected even
  when marked successful or written in an unrecognized language.
- Direct publisher links remain visible above the article. Locally decodable
  Google wrappers resolve directly. Other wrappers may resolve through one
  recorded publisher page and at most one publisher-declared RSS/Atom feed,
  requiring a unique exact-headline article link on
  that publisher's domain. No article URL is guessed or a homepage substituted
  as article text. A restriction or unresolved link produces an honest fallback.
- Concurrent opens share a bounded capture. A recent failed automatic capture
  has a 60-second cooldown; explicit retry bypasses it. Successful cached text
  is reused only for the matching source, and a failed reload preserves useful
  earlier capture text. Capture reads and network responses are bounded.

## Performance

Unchanged pending metadata is privately cached under a 16 MB budget and checked
against exact file identity, size, modification and change timestamps. Changed
records, removals and review states are read again. Relevance decisions are
cached by actual source text/URL/date and current company/variety names; trust,
filters, marks and entity assignments remain current.

Selected reading/capture no longer builds the whole feed or checks every
source's thumbnail. News refresh publishes its collected stories without
waiting for thumbnail downloads or live translation/model calls. Existing
cached translations still apply. The authenticated live server warms the
read-only News metadata/relevance caches during startup, moving the first
request's cold computation before users are served. Warm-up performs no
collection, trust decisions or persistence and cannot prevent server startup.

On an isolated copy of the live runtime (3,264 sources; 1,493 matching News
stories), baseline and candidate produced identical matching IDs and order:

| Route | Baseline | Candidate |
| --- | ---: | ---: |
| News, warm | 2.96–3.05 s | 0.60–0.73 s |
| Selected reader shell | 0.25–0.33 s | 0.20–0.27 s |
| Help | 0.09 s | 0.06 s |

These are backend measurements on the same private snapshot, not a promise
about arbitrary networks or publisher response times. The initial cold News
computation is roughly three seconds and is addressed by startup warming.
The release receipt must record final live timings and health verification.

## Accounts and runtime preservation

Accounts use the existing private `inbox/auth/users.sqlite3`, compatible with
the first Chris.H release. The additive `enabled` column preserves salted
scrypt password hashes and first-login timestamps. No JSON account store
replaces production accounts. Existing operator authentication remains.
Each user's first successful login opens `/guide`; subsequent logins honor
the safe destination. Incorrect passwords never consume onboarding. Disabled
accounts lose access; duplicate creation and unreadable stores fail safely.

The analyst workspace remains shared. Roles, tenant isolation and per-user
digests/preferences are separate product work. Account data, candidate runtime
copies, browser fixtures, backups and receipts remain private. Deployment uses
the current persistent runtime mounts and a verified backup/rollback; it never
uploads local intelligence or overwrites production review state.

## Validation and remaining limits

The affected regression tests cover old account-schema migration, concurrent
first login/capture, original-source preservation, malformed captures, Google
and publisher resolution, shared-reader filtering, automatic loading/fallback,
read-only warming and authentication. JavaScript scenarios cover one-click
refresh, bounded status polling, automatic retrieval, duplicate prevention,
stale-story cancellation and failure fallback. Browser review uses explicitly
labeled synthetic stories and demonstrates both automatic clean-text retrieval
and consent-only fallback. Canonical record validation passes.

Required current-head CI remains the merge gate: Change scope, Repository
integrity, Static public safety and Python tests. Full live verification follows
the image switch and checks account preservation, first-login behavior, health,
real reader capture, one-click collection and before/after page timings.

Paywalls, publisher outages and unresolved wrapper identities can still prevent
capture. Those pages expose source links and a clear unavailable-text state.
Mobile/network performance, long-term corpus scaling and wider route contention
remain measurable follow-up work; they are not hidden by freshness or trust labels.
