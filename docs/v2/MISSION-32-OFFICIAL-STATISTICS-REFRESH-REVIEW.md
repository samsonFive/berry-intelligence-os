# Mission 32 — Official statistics refresh and review

Map Explorer now links to a native review workspace for an explicit Eurostat refresh. It checks annual strawberry figures for Germany, Spain, Netherlands and Portugal using the existing keyless, bounded agency adapter. Source captures and comparison results remain private until the analyst selects country references to use. No page load or progress check calls a provider. USDA references and other country/crop gaps are retained.

## Workflow and preservation

Check latest official figures → compare current/new values, units, period, source update/check dates and qualifications → select reviewed countries → save → return to the originating map or snapshot scope. Nothing is preselected. Successful checks do not automatically update references. The supported scope is explicit; this is not a globally complete production dataset or a Perplexity population workflow.

The comparison uses outlined country cards, paired current/new panels and prominent values. Completed capture instructions fold away; source definitions and history remain minimized. Native controls work by keyboard. Human reference selection does not approve a source statement, Fact, identity or model. Original URLs, units, zero cells, source flags and missing-value distinctions stay intact. No yield is inferred, and incompatible categories/countries are never summed.

Accepted references are an ignored private runtime overlay. Map and snapshot composition/PDF share it in authoring mode; read-only/public output never loads the overlay or its jobs/history. Existing published reference JSON and canonical records are unchanged. Unselected countries/sources remain untouched. Each source capture is retained separately; saved history keeps complete prior/new overlay values, actor and time.

Requests reuse an active check or an identical request token. Failed checks retain the prior figures and show a neutral retry message without provider details. An interrupted request can be replaced explicitly after five minutes; its late result cannot supersede the new check. Stale review revisions and older captures cannot overwrite newer saved references. Damaged state fails closed before a mutation, with a reload/recovery message rather than silent replacement. Serialization follows the existing single-worker operator runtime; distributed/per-account isolation is not claimed.

## Verification

Initial review/Map/snapshot checks: 72 passed / one existing ReportLab warning in 6.08 seconds. Broader static, public/private, report and Guide acceptance: 113 passed / one warning in 24.02 seconds. Adding actual private/public snapshot PDF checks and compact layout brought the run to 114 passed / one warning in 21.26 seconds. Final older-reference and unselected-country preservation checks: **116 passed / one existing warning in 21.48 seconds**. Exact pushed-head CI remains required.

The real browser workflow made one explicit agency capture, which returned four countries and eight area/production figures. It retained the 2025 annual period and original September 28 source update; the check date was October 4. One Portugal reference was selected in an isolated ignored preview, returning to the same country/berry map scope. Its check date carried into snapshot composition. Canonical references and user runtimes were untouched. Source controls expanded/collapsed by Enter; at 390px document width was 375px. Desktop, phone and snapshot screenshots were saved and visually inspected. The temporary viewport was reset.

Canonical records validated; the governing expansion guide is unchanged. Deterministic tests use fixtures and never call the live agency or paid provider. Original source payload and isolated accepted overlay remain ignored.

## Remaining release work

Wider national/FAOSTAT and other-berry coverage and research-assisted population remain visible work. This slice delivers reviewable refresh for the supported official dataset without manufacturing broader coverage. Retained-route/older-PR parity, deeper specialist consistency and combined canonical release/backup/rollback acceptance remain. No merge or deployment before final human review.
