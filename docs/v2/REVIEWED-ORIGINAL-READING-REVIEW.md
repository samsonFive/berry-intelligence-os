# Accepted original articles: reader and variety discovery

An article copy already accepted in Source Fidelity could support separately
authorized extraction, but remained disconnected from normal reading and the
private variety-name audit. This change makes that same accepted article
available in the selected private reader and checks its named varieties for
identity-review leads. Accepting source text still does not approve its claims
or add a canonical variety.

## Reading and review boundaries

`reviewed_original_for_reading()` resolves only the selected published source's
existing recovery artifact. Existing stored article text, including user edits,
stays authoritative. Pending publications and Atomic Evidence do not use this
fallback. The source ID, publication identity, normalized URL, schema version,
recorded reviewer and review date must match; the article payload must retain
its recorded SHA-256 and contain usable original text. A summary is not used
as the original article. Missing, pending, rejected or investigation-only copies
do not supply text. Invalid or changed accepted copies produce a short private
notice linking back to the existing source-text review.

The original metadata and recovery artifact are not rewritten on read. Private
personal and legacy full/fragment readers share this fallback; private variety
discovery uses it before an unreviewed Reader refresh. Feed metadata, public
readers and static output do not resolve these private recovery bodies. There
is no acquisition on GET, extraction run, qualification marker, human decision
or canonical identity migration. Review changes take effect on the next read.

The accepted text retains its paragraphs and publisher heading hints. Source
details remain collapsed; the original article and publisher action remain
primary. The Source Fidelity consequences panel explains reading and discovery
alongside the existing separately authorized extraction boundary.

## Verification

- Expanded source review, readers, pending inventory, discovery and static
  regressions: **193 passed**, one existing warning, 44.95 seconds.
- Final overlapping source-review POST and public-reader checks: **52 passed**,
  one existing warning, 15.07 seconds. Acceptance without the confirmation is
  refused without changing the pending copy; accepted text appears and rejected
  text disappears. No facts, canonical edits or qualification markers result.
- Record validation passed. All **2,771 original data JSON files** and the
  canonical expansion guide remain unchanged.
- Static build: **1,755 pages**, Pagefind complete, unpublished IDs/titles
  excluded. The first sandboxed build failed at Pagefind output with Access
  denied; the verified workspace-output rerun completed. That first run is not
  reported as a passing build.
- Native browser acceptance used **fictional isolated data only**: pending text
  unavailable → explicit test acceptance → original paragraphs and headings
  readable → rejection → body unavailable on the next read. The positive test
  preview was restored afterward. No real source was accepted. Phone review
  measured client/scroll width **375/375 px**, body **15 px**, section headings
  **20 px**. Private screenshots are `reviewed-original-native-desktop.png`
  and `reviewed-original-native-phone.png` under ignored
  `inbox/european-portfolio-followup/`.

The fixture server initially lacked a seed import in its isolated data snapshot
and returned HTTP 500. Copying only missing baseline files into that isolated
snapshot resolved it; no fixture review state or real analyst data was reset.
The real pending Italian Berry reader still shows its original article and
image; its source remains draft/in_review with SHA-256
`deb45f2e3836c96e5f3fb13abaf9dc15c86930f1a0a9cb495f347a033cf822e4`.

## Actual coverage and remaining work

This local workspace has no accessible affirmed recovery artifacts. Its real
private audit remains **1,270 known sources / 2 readable sources / 103 named
identities / 32 catalog matches / 71 discoveries awaiting review**. The two
readable sources are one reviewed Hortifrut capture and one unreviewed Italian
Berry article. **64 canonical varieties remain unchanged.** Fictional browser
and automated examples are not real corpus additions or human recall evidence.
Historical production recovery counts are not claims about this local snapshot.

Parent draft [#370](https://github.com/samsonFive/berry-intelligence-os/pull/370)
passes all four checks on `69c044718fefc92595f437c50d15d5f49bbcd7eb`:
**4,487 passed / 11 skipped / two warnings / 750.46 seconds**. Run 37891895321,
Python job 113694490209; watch 26769 consumed with terminal success.
Draft [#371](https://github.com/samsonFive/berry-intelligence-os/pull/371)
passes all four checks on `c87d366856866675927ea29e183e5dbfa6e4590c`: **4,506
passed / 11 skipped / two warnings / 733.78 seconds**, run 37895614737,
Python job 113706219567. Watch 7224 was consumed with terminal success.

CAT-01/CAT-02/TD-116 remain open. Original corpus acquisition, complete current
and historical portfolios, independently human-qualified recall, rights/profile
depth and attributed photos, human catalog authoring and integrated release
review remain required. This restores an existing approved source-copy path;
it does not establish web completeness. No merge, deployment or other-berry
Landscape rollout is authorized by these checks.
