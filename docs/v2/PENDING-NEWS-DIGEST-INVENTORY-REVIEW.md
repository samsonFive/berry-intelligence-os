# Captured news in News and Personal Digest

October 8, 2026. Product/UI and source-inventory follow-up to draft #369.

## Result

A newly captured, active publication can now appear in Unreviewed News before
it is saved. A subscribed company list includes matching pending stories in
Personal Digest. Creating a list does not subscribe it; opening a reader or
giving Useful/Not relevant feedback does not save or enqueue the story.
Existing explicit reading priorities and personal saves remain independent.

News admits the article pipeline's `discovered_media` records only when their
stored `media_format` is `web_article`. The real article pipeline uses this
combination; the old News source-type allowlist silently excluded it. Audio,
video, PDF and unspecified discovered-media formats are not newly admitted.
The existing berry relevance, publication-date and scope filters still apply.
Digest accepts both crop names and the berry IDs carried by News/Map filters.

Unreviewed stays unreviewed. News Trusted still requires a reviewed publication
and active supporting statements. Company-list membership, subscriptions,
personal feedback and reading state cannot approve a publication or a claim.

## Metadata and source integrity

Feed browsing reads an explicit metadata projection with one safe image URL.
It never constructs or retains pending article/transcript body objects, never
calls the full pending-draft listing or selected-draft loader, and never runs
acquisition. The streaming parser validates the complete JSON, so it still
reads body bytes and transient scalar events; this is not a claim that body
bytes are skipped. Files over 16 MB and projected metadata over 256 KB are
unavailable, with a short Review Operations notice rather than raw exceptions.
Symlinks, malformed files and filename/record identity mismatches are excluded.
Metadata is read fresh, so operator edits and review decisions appear next time.

`ijson==3.5.1` is pinned in both full and web-runtime requirements. Its event
parser avoids constructing the omitted source objects. See the
[primary parser documentation](https://github.com/ICRAR/ijson) and
[versioned package release](https://pypi.org/project/ijson/3.5.1/).

Canonical published metadata and original prose win over a pending version of
the same ID. A different source URL cannot lend metadata or text to an existing
cached identity. Rejected/archived publication status or review state suppresses
older retained previews; personal saved marks remain as unavailable-source
entries. The personal full and overlay readers now stop with 404 instead of
falling back to the legacy loader and resurfacing a withdrawn source. Legacy
non-personal review routes keep their established behavior.

Public mode never opens the private pending inventory. No canonical data,
publication decisions, source fidelity decisions, identity decisions or domain
schemas are written by these views.

## Real browser evidence

Native browser review used this task's existing isolated localhost runtime and
the actual pending Italian Berry story, “G-Viva: the new primocane raspberry
yielding 28 t/ha,” published August 29, 2026. Its original source is
[Italian Berry](https://italianberry.it/en/news/g-viva-g-berries-raspberry).
The publisher's raspberry image loaded in both News and Digest. The original
35-paragraph article remained readable in the slide-out reader and the separate
publisher action remained available. The draft's SHA-256 remains
`deb45f2e3836c96e5f3fb13abaf9dc15c86930f1a0a9cb495f347a033cf822e4`.
It remains draft / in_review, with no publication or extraction action.

The isolated preview's old saved mark was removed. The article remained in News
but was absent from Digest. Creating “G-Berries review” left it absent;
subscribing added it with that inclusion reason and an unpressed Save action.
Unsubscribing removed it; resubscribing restored it. All personal changes were
limited to this task's ignored preview runtime, not production analyst data.
Phone review measured client/scroll width 375/375 pixels and a loaded image.

Screenshots and private proof files remain under ignored
`inbox/european-portfolio-followup/`: `pending-news-desktop.png`,
`pending-news-mobile.png`, `pending-digest-reader.png`.

## Verification and remaining scope

The expanded reader, article-pipeline, News, Digest, company-scope and variety
regressions passed: 165 tests, 27 existing deprecation warnings, 44.64 seconds.
Final overlapping carried-filter, fresh-edit and publication-safety verification
passed: 119 tests, one existing warning, 47.12 seconds. The country checks first
needed real geography fixtures; the berry check found a genuine Digest query
mismatch, fixed in the production normalization without weakening assertions.
Record validation and preservation
of all 2,771 original data JSON files and the canonical expansion guide passed.
The full static build passed: 1,755 pages, Pagefind search, and unpublished
ID/title exclusion. Draft #370 passes all four checks on `69c044718fefc92595f437c50d15d5f49bbcd7eb`: 4,487 passed / 11 skipped / two warnings / 750.46 seconds. Run 37891895321, Python job 113694490209; watch 26769 consumed with terminal success.

Parent #369 passes all four checks on `267389e4bf45828a7f1a282c7f17ac1a0378bb90`:
4,452 passed / 11 skipped / two warnings / 797.24 seconds. Run 37888500290,
Python job 113683959991; watch 24224 consumed with terminal success.

This fixes admission and reading continuity for already captured publications.
It does not acquire the historical corpus, fill unknown company associations,
prove completeness, approve claims or silently migrate existing source bodies.
CAT-01/CAT-02/TD-116, complete current/historical portfolios, independent human
recall, rights/profile depth, catalog authoring and integrated release review
remain open. No merge, deployment or other-berry Landscape rollout.
