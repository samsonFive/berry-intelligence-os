/** Private display preferences only; semantic grid IDs never become backend column keys. */
export const LAYOUT_SCHEMA = "berry-grid-semantic-v1";
const LEGAL_KEY = /^[a-z0-9-]{1,80}$/;
const COLUMN_KEY = /^c-[a-f0-9]{32}$/;
const META = new Set(["schema", "sort", "quick", "view"]);
export class GridLayoutError extends Error {
  readonly kind: "invalid" | "conflict" | "session" | "network" | "unloaded" | "disposed" | "migration";
  constructor(message: string, kind: GridLayoutError["kind"] = "invalid") { super(message); this.name = "GridLayoutError"; this.kind = kind; }
}
export interface LayoutColumn { colId: string; defaultWidth?: number; minWidth?: number; maxWidth?: number; lockedVisible?: boolean; defaultHidden?: boolean; restoreAfter?: string }
export interface CatalogColumn { colId: string; key: string; defaultWidth: number; minWidth: number; maxWidth: number; lockedVisible: boolean; defaultHidden?: boolean; restoreAfter?: string }
export interface ColumnCatalog { columns: readonly CatalogColumn[]; byId: ReadonlyMap<string, CatalogColumn>; byKey: ReadonlyMap<string, CatalogColumn> }
export interface GridLayoutSnapshot {
  columns: Array<{ colId: string; width: number; hide: boolean }>;
  sort: Array<{ colId: string; sort: "asc" | "desc" }>;
  filterModel: Record<string, Record<string, unknown>>;
  quickFilter: string;
  view?: "grid" | "cards";
}
export interface SheetLayout { revision: number; widths: Record<string, number>; order: string[]; hidden: string[]; filters: Record<string, string> }
export interface LoadedGridLayout {
  status: "default" | "restored" | "legacy-unmapped"; revision: number; snapshot: GridLayoutSnapshot; writable: boolean;
  retainedUnknownColumns: number; notice?: string;
}
function fail(message: string): never { throw new GridLayoutError(message); }
const object = (value: unknown): value is Record<string, unknown> => Boolean(value && typeof value === "object" && !Array.isArray(value)
  && [Object.prototype, null].includes(Object.getPrototypeOf(value)));
const keys = (value: unknown, limit: number): string[] => object(value) && Object.keys(value).length <= limit ? Object.keys(value) : fail("The saved grid layout exceeds its supported dimensions.");
const list = (value: unknown): string[] => Array.isArray(value) && value.length <= 40 && value.every(item => typeof item === "string" && LEGAL_KEY.test(item))
  && new Set(value).size === value.length ? value : fail("The saved column order or visibility is invalid.");
const width = (value: number, column: CatalogColumn) => Math.min(column.maxWidth, Math.max(column.minWidth, Math.round(value)));

export async function createColumnCatalog(columns: readonly LayoutColumn[], digest?: (text: string) => Promise<string>): Promise<ColumnCatalog> {
  if (!columns.length || columns.length > 40) fail("A grid layout supports between one and forty columns.");
  const hash = digest ?? (async text => Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text))))
    .map(byte => byte.toString(16).padStart(2, "0")).join(""));
  const byId = new Map<string, CatalogColumn>(), byKey = new Map<string, CatalogColumn>();
  for (const column of columns) {
    if (!/^[A-Za-z0-9_.-]{1,512}$/.test(column.colId) || byId.has(column.colId)) fail("Grid columns need unique stable semantic identities.");
    const key = `c-${(await hash(`berry-grid-column:v1\0${column.colId}`)).slice(0, 32)}`;
    if (!COLUMN_KEY.test(key) || byKey.has(key)) fail("Grid column identities could not be mapped safely. The saved layout was not changed.");
    const minWidth = Math.max(48, Math.ceil(column.minWidth ?? 48)), maxWidth = Math.min(1200, Math.floor(column.maxWidth ?? 1200));
    if (![minWidth, maxWidth, column.defaultWidth ?? 160].every(Number.isFinite) || minWidth > maxWidth) fail("The grid's column size limits are invalid.");
    if (column.defaultHidden !== undefined && typeof column.defaultHidden !== 'boolean') fail("The default column visibility is invalid.");
    if (column.restoreAfter !== undefined && typeof column.restoreAfter !== 'string') fail("The new column's default position is invalid.");
    const entry = { colId: column.colId, key, minWidth, maxWidth, defaultWidth: Math.min(maxWidth, Math.max(minWidth, Math.round(column.defaultWidth ?? 160))), lockedVisible: Boolean(column.lockedVisible),
      ...(column.defaultHidden ? { defaultHidden: true } : {}), ...(column.restoreAfter !== undefined ? { restoreAfter: column.restoreAfter } : {}) };
    byId.set(column.colId, entry); byKey.set(key, entry);
  }
  const entries = [...byId.values()];
  for (const [index, column] of entries.entries()) if (column.restoreAfter !== undefined) {
    const anchor = entries.findIndex(item => item.colId === column.restoreAfter);
    if (column.lockedVisible || anchor < 0 || anchor >= index) fail("A new column's default position needs an earlier available column.");
  }
  return { columns: entries, byId, byKey };
}
export function defaultGridLayout(catalog: ColumnCatalog): GridLayoutSnapshot {
  return { columns: catalog.columns.map(column => ({ colId: column.colId, width: column.defaultWidth, hide: !column.lockedVisible && Boolean(column.defaultHidden) })), sort: [], filterModel: {}, quickFilter: "" };
}
export function validateSheetLayout(value: unknown): SheetLayout {
  if (!object(value) || !Number.isSafeInteger(value.revision) || Number(value.revision) < 0) fail("The server returned an invalid layout revision.");
  const widths = value.widths, filters = value.filters;
  for (const key of keys(widths, 40)) if (!LEGAL_KEY.test(key) || !Number.isInteger((widths as Record<string, unknown>)[key])
    || Number((widths as Record<string, unknown>)[key]) < 48 || Number((widths as Record<string, unknown>)[key]) > 1200) fail("The saved column sizes are invalid.");
  for (const key of keys(filters, 25)) if (key.length > 40 || typeof (filters as Record<string, unknown>)[key] !== "string"
    || String((filters as Record<string, unknown>)[key]).length > 400) fail("The saved grid filters exceed their supported limits.");
  return { revision: Number(value.revision), widths: { ...(widths as Record<string, number>) }, order: [...list(value.order)], hidden: [...list(value.hidden)], filters: { ...(filters as Record<string, string>) } };
}
function cleanText(value: unknown, max = 200): string {
  return typeof value === "string" && value.length <= max && !/[\u0000-\u001f\u007f]/.test(value) ? value : fail("A grid filter contains unsupported text or exceeds its supported length.");
}
const OPERATIONS = new Set(["equals", "notEqual", "contains", "notContains", "startsWith", "endsWith", "lessThan", "lessThanOrEqual", "greaterThan", "greaterThanOrEqual", "inRange", "blank", "notBlank", "empty"]);
function filterValue(value: unknown, inheritedType?: string, nested = false): Record<string, unknown> {
  if (!object(value)) fail("The grid filter format is unsupported.");
  const type = value.filterType ?? inheritedType;
  if (!["text", "number", "date"].includes(String(type))) fail("Only Community text, number and date filters can be saved.");
  const result: Record<string, unknown> = { filterType: type };
  for (const key of Object.keys(value)) {
    if (key === "filterType") continue;
    if (key === "operator") {
      if (nested || !["AND", "OR"].includes(String(value[key]))) fail("The grid filter combination is unsupported.");
      result[key] = value[key];
    } else if (key === "conditions") {
      if (nested || !Array.isArray(value[key]) || value[key].length < 1 || value[key].length > 2) fail("At most two conditions can be saved for a column filter.");
      result[key] = value[key].map(condition => filterValue(condition, String(type), true));
    } else if (key === "type") {
      if (!OPERATIONS.has(String(value[key]))) fail("The grid filter operation is unsupported."); result[key] = value[key];
    } else if (["filter", "filterTo"].includes(key)) {
      const item = value[key];
      if (item === null) result[key] = null;
      else if (type === "number") {
        if (typeof item !== "number" || !Number.isFinite(item)) fail("The grid number filter is invalid."); result[key] = item;
      } else result[key] = cleanText(item);
    } else if (["dateFrom", "dateTo"].includes(key)) {
      const item = value[key];
      if (item !== null && (typeof item !== "string" || !/^\d{4}-\d{2}-\d{2}(?: \d{2}:\d{2}:\d{2})?$/.test(item))) fail("The grid date filter is invalid.");
      result[key] = item;
    } else fail("The grid filter contains unsupported fields.");
  }
  if (JSON.stringify(result).length > 400) fail("This column filter is too long to save. Shorten its conditions.");
  return result;
}
function storedSort(wire: SheetLayout): Array<[string, "asc" | "desc"]> {
  let value: unknown;
  try { value = JSON.parse(wire.filters.sort ?? "[]"); } catch { return fail("The saved grid sorting is invalid."); }
  if (!Array.isArray(value) || value.length > 5 || value.some(row => !Array.isArray(row) || row.length !== 2 || !COLUMN_KEY.test(row[0]) || !["asc", "desc"].includes(row[1]))
    || new Set(value.map(row => row[0])).size !== value.length) fail("The saved grid sorting exceeds its supported limits.");
  return value as Array<[string, "asc" | "desc"]>;
}
function assertSemanticWire(wire: SheetLayout): void {
  const refs = [...Object.keys(wire.widths), ...wire.order, ...wire.hidden, ...Object.keys(wire.filters).filter(key => !META.has(key))];
  if (refs.some(key => !COLUMN_KEY.test(key))) fail("The saved grid layout uses an unsupported column namespace.");
  for (const [key, value] of Object.entries(wire.filters)) if (!META.has(key)) {
    let parsed: unknown; try { parsed = JSON.parse(value); } catch { return fail("The saved column filter is invalid."); } filterValue(parsed);
  }
  cleanText(wire.filters.quick ?? ""); storedSort(wire);
  if (wire.filters.view !== undefined && !["grid", "cards"].includes(wire.filters.view)) fail("The saved display view is unsupported.");
}
/** Only genuinely new columns get a default position; every saved reference wins. */
function positionMissingColumns(order: string[], catalog: ColumnCatalog, savedReferences: ReadonlySet<string>): string[] {
  const result = [...order], tails = new Map<string, string>();
  for (const column of catalog.columns) {
    if (column.restoreAfter === undefined || savedReferences.has(column.key)) continue;
    const anchor = catalog.byId.get(column.restoreAfter)!.key;
    result.splice(result.indexOf(column.key), 1);
    const after = result.indexOf(tails.get(anchor) ?? anchor);
    result.splice(after + 1, 0, column.key);
    tails.set(anchor, column.key);
  }
  return result;
}
export function decodeGridLayout(value: unknown, catalog: ColumnCatalog): LoadedGridLayout {
  const wire = validateSheetLayout(value), snapshot = defaultGridLayout(catalog);
  const empty = wire.revision === 0 && !wire.order.length && !wire.hidden.length && !Object.keys(wire.widths).length && !Object.keys(wire.filters).length;
  if (empty) return { status: "default", revision: 0, snapshot, writable: true, retainedUnknownColumns: 0 };
  if (wire.filters.schema !== LAYOUT_SCHEMA) return { status: "legacy-unmapped", revision: wire.revision, snapshot, writable: false, retainedUnknownColumns: 0,
    notice: "The earlier layout cannot be matched safely to current columns. It remains saved; use a new layout namespace for these columns." };
  assertSemanticWire(wire);
  const refs = new Set([...wire.order, ...wire.hidden, ...Object.keys(wire.widths), ...storedSort(wire).map(([key]) => key), ...Object.keys(wire.filters).filter(key => !META.has(key))]);
  const pinned = catalog.columns.filter(column => column.lockedVisible).map(column => column.key);
  const ordered = positionMissingColumns([...new Set([...pinned, ...wire.order, ...catalog.columns.map(column => column.key)])], catalog, refs);
  snapshot.columns = ordered.flatMap(key => { const column = catalog.byKey.get(key); return column ? [{ colId: column.colId, width: width(wire.widths[key] ?? column.defaultWidth, column),
    hide: !column.lockedVisible && (wire.hidden.includes(key) || !wire.order.includes(key) && wire.widths[key] === undefined && Boolean(column.defaultHidden)) }] : []; });
  snapshot.sort = storedSort(wire).flatMap(([key, sort]) => { const column = catalog.byKey.get(key); return column ? [{ colId: column.colId, sort }] : []; });
  for (const [key, value] of Object.entries(wire.filters)) {
    const column = catalog.byKey.get(key); if (column) snapshot.filterModel[column.colId] = filterValue(JSON.parse(value));
  }
  snapshot.quickFilter = wire.filters.quick ?? "";
  if (wire.filters.view !== undefined) snapshot.view = wire.filters.view as "grid" | "cards";
  return { status: "restored", revision: wire.revision, snapshot, writable: true, retainedUnknownColumns: [...refs].filter(key => !catalog.byKey.has(key)).length };
}
export function encodeGridLayout(snapshot: GridLayoutSnapshot, catalog: ColumnCatalog, previous?: SheetLayout): SheetLayout {
  if (!Array.isArray(snapshot.columns) || snapshot.columns.length !== catalog.columns.length || new Set(snapshot.columns.map(column => column.colId)).size !== snapshot.columns.length) fail("Save the complete current column layout.");
  const base = previous ? validateSheetLayout(previous) : { revision: 0, widths: {}, order: [], hidden: [], filters: {} };
  if (previous && !decodeGridLayout(base, catalog).writable) throw new GridLayoutError("The earlier layout is preserved. Choose a new layout namespace before saving.", "migration");
  const widths = Object.fromEntries(Object.entries(base.widths).filter(([key]) => !catalog.byKey.has(key)));
  const hidden = base.hidden.filter(key => !catalog.byKey.has(key));
  const currentOrder: string[] = [];
  for (const state of snapshot.columns) {
    const column = catalog.byId.get(state.colId); if (!column || !Number.isFinite(state.width) || typeof state.hide !== "boolean") fail("The current grid column state is invalid.");
    widths[column.key] = width(state.width, column); currentOrder.push(column.key);
    if (state.hide && !column.lockedVisible) hidden.push(column.key);
  }
  const locked = catalog.columns.filter(column => column.lockedVisible).map(column => column.key);
  const order = [...new Set([...locked, ...currentOrder, ...base.order.filter(key => !catalog.byKey.has(key))])];
  const filters = Object.fromEntries(Object.entries(base.filters).filter(([key]) => !META.has(key) && !catalog.byKey.has(key)));
  filters.schema = LAYOUT_SCHEMA; filters.quick = cleanText(snapshot.quickFilter);
  const view = snapshot.view === undefined ? base.filters.view : snapshot.view;
  if (view !== undefined) {
    if (!["grid", "cards"].includes(view)) fail("The current display view is unsupported.");
    filters.view = view;
  }
  if (!Array.isArray(snapshot.sort) || snapshot.sort.length > 5 || new Set(snapshot.sort.map(item => item.colId)).size !== snapshot.sort.length) fail("At most five columns can be sorted in a saved grid layout.");
  const sort = snapshot.sort.map(item => {
    const column = catalog.byId.get(item.colId); if (!column || !["asc", "desc"].includes(item.sort)) fail("The current grid sorting is invalid.");
    return [column.key, item.sort];
  });
  const retainedSort = base.filters.schema === LAYOUT_SCHEMA ? storedSort(base).filter(([key]) => !catalog.byKey.has(key)) : [];
  if (sort.length + retainedSort.length > 5) fail("The retained and current grid sorting exceeds five columns. Earlier preferences have not been overwritten.");
  filters.sort = JSON.stringify([...sort, ...retainedSort]);
  for (const colId of keys(snapshot.filterModel, 22)) {
    const column = catalog.byId.get(colId); if (!column) fail("A grid filter refers to an unavailable column.");
    filters[column.key] = JSON.stringify(filterValue(snapshot.filterModel[colId]));
  }
  const wire = validateSheetLayout({ revision: base.revision, widths, order, hidden: [...new Set(hidden)], filters });
  if (new TextEncoder().encode(JSON.stringify(wire)).byteLength > 20_000) fail("The grid layout is too large to save. Earlier preferences have not been overwritten.");
  return wire;
}
export function validViewKey(value: string): boolean { return LEGAL_KEY.test(value); }
