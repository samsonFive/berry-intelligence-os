# News-first startup preparation

The server currently prepares Variety Candidates, Morning Brief and publication
readiness before accepting even login and health requests. This candidate keeps
the existing read-only News preparation and lets those specialist workspaces
use their existing loaders when opened. Authentication validation, polling
opt-in, source freshness, human review and account boundaries are unchanged.
There is no new background job, collector, API call, source record or cache
expiry shortcut.

This follows the platform-only combination #455 (`99452430`): its ten runtime
files and statement destinations remain intact. The only additional runtime
file is `app/services/news_warmup.py`. Frozen catalog/Map #449 and source #457
are separate. #449 already has one unanswered scoped release question; this
work neither repeats that question nor grants any release approval. Live #443
remains `f76080d0`.

## Measured behavior and tradeoff

Two phase probes found approximately five seconds of pre-serving warm-up,
including roughly two to three seconds of unrelated variety matching. An
earlier preview trace at 30 seconds prompted investigation, but that delay did
not reproduce in the controlled probes. It is not a production timing claim.

A fresh-process comparison then exercised the real production lifespan and
authenticated ASGI routes against identical isolated public data, with external
connections forbidden. The first successful pair measured:

| Measurement | Frozen #455 helper | News-only helper |
|---|---:|---:|
| Application import | 3.46 s | 3.38 s |
| Lifespan preparation before serving | 6.25 s | 2.89 s |
| First authenticated News response | 0.77 s | 0.81 s |
| First Variety Candidates response | 1.15 s | 3.61 s |
| First Morning Brief response | 0.61 s | 0.89 s |
| Publication review response | 0.56 s | 0.66 s |

Specialist work moves to the first specialist visit; it does not disappear.
The intended benefit is earlier login/health/News availability. These local
Windows timings exclude real network latency and do not prove production or
physical-phone performance. Import and filesystem cache order can vary.

The full News models and all successful GET response bytes match, including
the Help page, both News lanes, scoped candidate list, Morning Brief and
publication review. All 2,982 public fixture data files remain unchanged and no
external connection is attempted. The fixture login is fictional; no real
account or human review decision is used. The original failed benchmark with
unsupported `window=all` is retained privately; the corrected probe uses the
existing empty-window all-dates contract, without changing product filters.

## Verification and remaining acceptance

Four added tests cover exact News inputs without specialist preparation, safe
optional failure, the real production startup branch after authentication
validation, and fail-closed missing credentials before directory writes. The
focused suite passes 89 tests in 48.14 seconds, spanning startup, Reader,
authentication, Personal Digest isolation, briefing and varieties. Records
validate. One existing ReportLab deprecation warning remains.

The focused run also exposed a test-fixture leak: the existing authentication
throttling test left its shared client IP blocked for later account fixtures.
The fixture now clears its limiter before and after each test. Runtime
throttling and its security assertions remain unchanged. The failed first run
and the passing rerun are retained privately.

Two baseline and three candidate fresh-process runs confirm the direction:
baseline preparation was 6.22–6.25 seconds, candidate preparation 1.87–2.89
seconds. First News responses were 0.77–0.87 and 0.67–0.85 seconds respectively.
The final matched pair explicitly tests Trusted and Unreviewed: all four full
typed News models and all eight successful GET bodies are byte-identical,
without dropping or masking fields. All five fixtures preserve their 2,982 data
files with no outbound connections. First candidate-list visits are slower,
2.42–3.61 seconds versus 1.15–1.16, as expected from on-demand work. These small
local samples are not a production percentile or a universal speed guarantee.

Current-head CI, native desktop/phone review and a
fresh bounded live-data preservation rehearsal still belong to this candidate.
It needs its own scoped approval before merge/deployment. Existing backups,
rollback and settings/data mounts must remain. TD-122 stays open for broader
performance; source/name/rights/photo decisions, independent recall and wider
Learn/statistics depth remain unfinished. All original 31 accepted requirement
definitions/order and the governing guide remain unchanged.
