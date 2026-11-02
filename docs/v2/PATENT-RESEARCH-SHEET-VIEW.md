# Patent research spreadsheet view

`/varieties/research/sheet` is the authenticated, read-only companion to the
research profiles. It projects the original 340 source rows into the same
fourteen columns, A–N, without collapsing repeated varieties. Original row
numbers sit in a separate gutter and are not silently inserted into the
clipboard's starting-sheet columns.

Both requested workflows are included:

- Isolate missing commercial roles, blanks with a source-supported proposal,
  unresolved blanks, identity/transcription issues, and prior database coverage.
  Crop, text and original-row-range filters combine with those selections.
- Choose any visible rows/columns, drag or Shift-click cell rectangles, extend
  selections with Shift+arrows, and copy with buttons or Ctrl/Cmd+C. Column presets
  retain A–N, focus on variety/commercial roles/sources, or include research notes.

The default cell mode fills only originally blank Commercial Entity cells with
unreviewed research proposals. It never replaces an originally populated cell
or fills a held identity conflict. Starting-sheet-only mode restores the exact
original values. All values and proposals remain separate in memory; the page
does not edit the import, canonical catalog, reviewed facts or the user's file.

Clipboard text is tab-separated with correct quoting for multiline cells,
tabs and quotes. The HTML clipboard format also retains cell boundaries.
Formula-looking text is escaped as a literal. Headers are optional; direct
Commercial Entity paste blocks always omit headers and show their exact K-cell
destination. Original cell addresses are shown only for contiguous source rows
and original columns. Filtered/discontiguous selections are explicitly compacted
and never labelled as one aligned starting-sheet range.

The role-block action divides selected records into contiguous original-row
blocks. This avoids shifting a proposal from source row 193 into row 77 merely
because two matching varieties were shown together. A row-mapped TSV download
always includes source row numbers, review status and source URLs. Source and
transcription notes are available by clicking a row number.

No new backend/domain schema, trusted role edge, publication decision, monitor
or stored user preference is created. Source sheet JSON is read once per request;
profile dossiers are joined in one pass without per-row footprint/catalog scans.
The route is private, no-store and noindex, and is not generated into the public
static snapshot.

Closeout packets can retain several separately sourced commercial parties per
variety, including their roles, territories and reported cooperation. Rights-only
leads stay outside the supplier fill proposal. Each dossier can retain its search
checks, conclusion and remaining evidence gap. A later immutable import replaces
the earlier dossier by research key; a newly resolved identity removes the older
unresolved application lead. No historical import is rewritten.

The role view also exposes rights/programme leads and the closeout outcome.
Those leads never populate the Commercial Entity fill proposal. Separate filters
isolate unresolved rows with a qualified lead and unresolved rows with none.
Application-specific row holds prevent a supplier for a supported variety from
being pasted into a neighbouring, misidentified source row. Explicitly superseded
private candidates are hidden after a sourced identity correction; their immutable
historical import remains intact and trusted catalog entities cannot be superseded.

Validation: 19 import/sheet tests passed. Real-data browser checks cover all
340 source rows, the 64 proposals for blank cells, exact A–N and K clipboard
values, original-mode blanks, paste addresses, 33 contiguous role blocks, TSV
row/provenance retention and the 412-pixel layout. Required current-head CI and
the normal backed-up live-release process gate deployment.
