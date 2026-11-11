# Portfolio grid display preferences

Source status: 14 targeted codec/adapter/grid-state checks and TypeScript pass.
No bundle build or mounted persistence result is claimed by this change.

`BerryDataGrid.tsx` uses the Community grid, semantic cultivar row IDs and stable
company-role column IDs. The identity and comparison-pin columns lead, remain
visible and frozen left; their visibility/pinning cannot be changed through the
column controls. The identity is first. Company focus and the explicit company
and cultivar comparison pins remain investigation actions, outside layout state.

`useAccountGridLayout.ts` connects W1's fixed `berry-portfolio-v1` account adapter.
It waits for both saved preferences and the grid, applies width/order/visibility,
ordered sorting, Community text filters and loaded-row quick filtering, then
enables debounced user saves. API, initialization, row-data and viewport events
do not autosave. Column definitions use `initialWidth`, so unrelated focus/pin
rerenders do not reset a restored width. A status says saved only after the server
acknowledges the optimistic write. New edits supersede older save-status receipts.

The Community Columns control provides native checkboxes, an enterable popup,
outside dismissal and Escape return to its summary. Quick filtering is explicitly
over loaded rows, and neither filter changes canonical scope or cohorts. Text
filters support two conditions; quick filtering is limited to 200 characters.
The adapter's storage/retained-column/filter/sort limits remain authoritative and
fail visibly without dropping prior preferences. More than 38 company columns
plus the two fixed columns shows an explicit cap rather than a truncated matrix.

A failed load never enables autosave. An unmapped older row remains stored and
shows a visible default/local-only fallback. A 409 keeps the current local display
and freezes writes. Only the explicit **Reload saved layout** action can retrieve
the saved baseline and re-enable saving; there is no automatic retry or overwrite.
Reload may replace this tab's unsaved display preferences. Responses from an older
load or save cannot override the status/readiness of a newer explicit reload.
Unmount and private-session transitions cancel timers and dispose the controller.

Mounted verification after the consolidated bundle must check:

1. Initial restore generates no POST. Change a width by dragging, move company
   columns, hide one with Columns, sort and set a column filter/quick filter. Wait
   for **Grid layout saved** before leaving or reloading.
2. Reload restores those preferences, with identity first and both fixed columns
   visible/frozen. Company/cultivar pins and the complete investigation URL remain
   unchanged. Focusing or pinning a row does not reset a resized column.
3. Scope changes that temporarily remove company columns retain their preferences
   when those same semantic columns return, subject to the explicit account caps.
4. Inject a layout-only 409: local display remains usable, further gestures make
   no POST, and explicit reload restores the saved version before saving resumes.
   A failed GET and an unmapped older schema must never produce an autosave.
5. Keyboard column controls, a narrow viewport and logout remain usable; no
   provider run is involved. Canonical domain records are not mocked or changed.
