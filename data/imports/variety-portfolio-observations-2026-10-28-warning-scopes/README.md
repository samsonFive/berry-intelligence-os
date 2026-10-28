# Warning placement for four retained source sections

This overlay adds explicit name scopes to existing warnings. It contains no
replacement source records. Source URLs, capture hashes, checked dates, names,
warning text and unreviewed states remain intact. It adds no source captures
or name occurrences and supplies no human decisions.

- The 2024 raspberry register's Lewis note applies to its Bonnie Lewis entry.
  The addenda contains neither named Lewis entry, so it retains that warning as
  wider source context rather than assigning it to BC92915 or other names.
- The shared 2024 and 2025 ABB announcements' conflicting-code warnings apply
  to their literal Baridi entries. Malaika and Zawadi keep those notes available
  within source context without displaying them as their own code conflicts.

`review_warning_scopes` maps an existing warning message to exact literal
`candidate_names` from that section. An empty list explicitly means wider
source context only. No scope means the warning remains prominent for every
entry, preserving the conservative existing behavior. Invalid, duplicate or
unknown mappings fail validation rather than silently hiding a warning.

Each `warning_scope_overlays` entry names its source and the SHA-256 fingerprint
of the exact original source record. A changed record or operator correction
does not receive the older placement overlay: its own notes stay prominent.
Formatting and dictionary key order do not change the fingerprint. An unknown
source, malformed fingerprint or invalid matching scope fails validation.

Whole-source coverage continues to show all warnings and follow-up needs.
Relevant candidate warnings remain prominent. Other-entry notes start collapsed
beside their original source reference, with claim links and dates still visible.
Catalog identities, relationships, rights, permissions and operator decisions
are unchanged.
