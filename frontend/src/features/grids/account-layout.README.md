# Account grid layout adapter

`layout-codec.ts` and `account-layout.ts` are a display-preference foundation.
They do not read or dispatch investigation context, cohorts or canonical data.
They reuse the existing session-scoped `GET/POST /api/ui/sheets/{view_key}` and
its optimistic revision. No account identifier or alternate API destination is
accepted from the browser.

## Integration contract

1. Build a catalog with `await createColumnCatalog(columnSpecs)`. Pass the
   actual semantic AG Grid `colId`, default/min/max widths and `lockedVisible`
   for the leading identity/pin columns. Locked columns remain visible and lead
   the saved order. A catalog supports 1–40 unique columns.
2. Create `new AccountGridLayouts({viewKey:'berry-portfolio-v1',catalog})` using a
   fixed new namespace. Do not reuse a legacy title/index-hash view key.
3. `await controller.load()` returns `{status,revision,snapshot,writable,
   retainedUnknownColumns,notice?}`. Status is `default`, `restored`, or
   `legacy-unmapped`. Apply the snapshot after AG Grid is ready, with change
   handlers suppressed during restoration. Never autosave a failed load.
4. A snapshot is `{columns:[{colId,width,hide}],sort:[{colId,sort}],filterModel,
   quickFilter}`. Columns must include every current catalog column in order.
   Map ordered sort entries to AG Grid's `sortIndex`. Apply semantic IDs to
   AG Grid; the storage hashes are internal to this adapter. Debounce user
   changes and call `save(snapshot)`. Saves are serialized with the last
   confirmed server revision and capture their input before queuing.
5. `getState()` returns `{status,revision,conflict}`. A 409 sets `conflict:true`
   and blocks all queued/future saves. Keep the local display and show the
   conflict. Only an explicit `load()` reloads the saved layout and clears that
   flag. There is no automatic conflict retry, forced overwrite or reset.
6. Call `dispose()` on unmount/catalog replacement. The controller also disposes
   and clears its private baseline on `berry:session-transition`. In-flight or
   delayed responses cannot restore it after logout. Session errors optionally
   invoke `onSessionRequired` and emit the same session event.

The module has no React/AG Grid imports. The caller owns visible status, retry,
column visibility controls, restoration gating and grid event wiring. Changing
the column catalog requires a fresh controller/load; canonical filter/scope and
comparison actions remain with `InvestigationProvider`.

## Storage, limits and legacy behavior

Versioned SHA-256 hashes of semantic column IDs become `c-` plus 32 hex digits,
valid for both backend column keys and bounded filter-map keys. Current-column
lookup maps them back to semantic IDs; duplicate IDs or current hash collisions
fail before a request. Header labels and current column order do not affect
identity. Account layout namespaces remain stable when scope adds/removes
company columns.

The wire shape is unchanged: `{revision,widths,order,hidden,filters}`. Widths are
integer 48–1200 within the column's own bounds; each column collection is capped
at 40. `filters` has at most 25 string entries, keys at most 40 characters and
values at most 400. Reserved entries are `schema`, `sort` and `quick`, leaving
at most 22 active column filters. Only bounded Community text/number/date
filters with up to two combined conditions are supported; no row/body payload,
Set Filter model or arbitrary extra filter fields are serialized. Quick filter
is at most 200 characters, sort at most five columns, request UTF-8 at most
20,000 bytes. Limits fail explicitly and preserve the prior saved row.

Saved hash keys for temporarily absent columns are retained in the server
baseline and merged into subsequent saves, within those caps. Their widths,
visibility, filter and sort return only when the same current semantic ID maps
back. New current order leads retained absent columns; active sorts lead
retained absent sorts. They are never applied to another current column.

Existing title/index-hash layouts remain in their original namespaces. An old
or unknown schema encountered at a requested key returns defaults with
`legacy-unmapped`, `writable:false` and an explicit notice. The adapter does not
guess title correspondence or overwrite that row. A new semantic namespace is
the fallback until a separate migration can prove every legacy correspondence.

`frontend/tests/grid-layout.test.mjs` verifies key stability/collisions, round
trips, unknown-column retention, legacy preservation, backend caps/UTF-8 size,
serialized optimistic writes, 409 freeze/reload, and session races without any
account API write or provider request.
