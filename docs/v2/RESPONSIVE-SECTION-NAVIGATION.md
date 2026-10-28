# Section navigation below the shared header — October 27, 2026

Section headings should remain visible after a link or filter jumps down a page.
At phone widths, the shared navigation wraps beyond several fixed scroll offsets.
The measured coverage example has a 133px header and a 100px section offset, which
hides its kicker and part of the title. This is existing TD-123, observed while
reviewing the independent performance draft; that draft retains identical HTML.

The shared shell now measures its actual header once and updates the value on
header resize, window resize, font readiness and restored-page display. A small
stylesheet loaded after page styles supplies the offset to existing page-section
selectors in Varieties/Coverage, Intelligence, company results/research, Landscape,
Learn, Digest subscriptions, Help and retained monitor/reading/operations sections.
Each selector retains its existing no-script/headerless fallback. No page layout,
content density, anchor destination or preference storage changes.

Specialized candidate alphabetical navigation and Workspace quick navigation keep
their existing combined header/bar measurements. Nested table rows, map table
region jumps and the Reader keep their own offsets. The shared script neither
sets the URL/hash nor calls scroll methods, preserving normal navigation/history
behavior. It measures before page-specific initial-hash handlers run.

This is independent of unmerged source/catalog, performance and personal-Digest
drafts. The current live base is `94a3b99b`. No source, identity, claim, photo, account
or user-data decision changes. All 31 accepted requirement IDs/descriptions/order
and the governing guide remain intact. The new script's wrap, resize, restored-page
and headerless checks and 59 affected shell/profile/candidate regressions pass.
Final static/browser/preservation/current-head CI and release review remain
before deployment.
