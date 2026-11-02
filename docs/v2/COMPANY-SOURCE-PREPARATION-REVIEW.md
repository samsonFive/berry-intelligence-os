# Company source-name preparation

A combined live-data rehearsal recorded a 10.11-second first request for
Splendor's varieties tab. A follow-up profile on the isolated copy showed that
`company_source_varieties()` builds the complete candidate universe without
the request-scoped identity lookup already used by Coverage and the directory.
The profile includes instrumentation overhead; it is a diagnosis, not a page
speed benchmark.

The company helper now enters that existing preparation scope while building
the same universe. It retains all articles, portfolio sources, candidates,
canonical varieties and saved human decisions. There is no company-only
shortcut, reduced result set, changed matcher or persistent identity-result
cache. Unsupported input still uses the original matcher. Public company views
return before entering the private discovery path.

The original resolver still decides every match. The temporary index supplies
a conservative set of relevant catalog rows in original order, checks catalog
freshness and is discarded when the scope exits. The regression compares the
complete company model with the unprepared reference before and after a
canonical rename and an in-place alias edit. Human rejections remain closed and
all input records remain unchanged.

All 348 affected identity, company, snapshot and coverage-work regressions pass
with no attempted external connections. The complete composition's assertions
also pass (5,998 tests), but its network guard correctly refuses 36 attempted
connections. The trace attributes all of them to three tests: two official-source
attribution tests omitted their thumbnail mocks, and an Industry Pulse route test
mocked an obsolete call boundary.

The thumbnail fixtures retain collection and image enrichment. The Pulse test
now injects its existing in-memory discovery provider while exercising the real
newsroom cycle, and asserts that the injected provider was actually used. It
still checks that no trusted Evidence is written. All 111 tests across the five
affected feed/discovery modules pass with no attempted external connections.
No existing assertion or network guard is weakened.

Four fresh server-copy processes run in baseline/candidate/candidate/baseline
order. All 24 complete business contexts and unnormalized HTML responses match
for Splendor, Hortifrut and ABZ. Only the framework Request object is excluded.
The copied five accounts, four databases and 10,385 existing JSON records remain
unchanged. No provider request, human decision or production change is made.

The bounded sample shows Splendor's first company request at a median
9.45 → 8.78 seconds and its repeat at 1.93 → 1.81 seconds. Other company results
are nearly flat or slightly slower: Hortifrut repeat is 2.05 → 2.15 seconds,
and ABZ repeat is 2.01 → 2.01 seconds. Host variation remains material. This is
a modest preparation improvement, not a resolution of general app performance
or a production/device percentile claim. Cold loads remain a release limitation.

The repaired complete-suite offline check and revised exact-head CI, native check and
current-live preservation remain required before the revised release review.
Approval of the earlier `cefe0453` head does not approve a different release
head or overwrite the newer live patent-research work.
