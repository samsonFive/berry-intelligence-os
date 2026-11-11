import assert from "node:assert/strict";
import test from "node:test";
import { createHash } from "node:crypto";
import { AccountGridLayouts } from "../src/features/grids/account-layout.ts";
import { createColumnCatalog, decodeGridLayout, defaultGridLayout, encodeGridLayout, GridLayoutError, LAYOUT_SCHEMA } from "../src/features/grids/layout-codec.ts";

const specs = [
  { colId: "cultivar.identity", defaultWidth: 220, minWidth: 150, lockedVisible: true },
  { colId: "cultivar.comparison-pin", defaultWidth: 75, minWidth: 65, maxWidth: 90, lockedVisible: true },
  { colId: "company.company-one.recorded-role", defaultWidth: 260 },
  { colId: "company.company-two.recorded-role", defaultWidth: 260 },
];
const empty = () => ({ revision: 0, widths: {}, order: [], hidden: [], filters: {} });
const json = (body, status = 200) => new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });

test("semantic IDs map to stable legal storage keys, title/order independent, with collision guards", async () => {
  const a = await createColumnCatalog(specs), b = await createColumnCatalog([...specs].reverse());
  for (const column of a.columns) {
    assert.match(column.key, /^c-[a-f0-9]{32}$/); assert.equal(b.byId.get(column.colId).key, column.key);
    assert.equal(column.key, `c-${createHash("sha256").update(`berry-grid-column:v1\0${column.colId}`).digest("hex").slice(0, 32)}`);
  }
  await assert.rejects(createColumnCatalog(specs, async () => "0".repeat(64)), /mapped safely/);
  await assert.rejects(createColumnCatalog([specs[0], specs[0]]), /unique stable/);
});

test("only display state round trips; locked identity columns stay visible and legal sizes clamp", async () => {
  const catalog = await createColumnCatalog(specs), snapshot = defaultGridLayout(catalog);
  snapshot.columns.reverse(); snapshot.columns.find(column => column.colId === specs[0].colId).hide = true;
  snapshot.columns.find(column => column.colId === specs[1].colId).width = 2000;
  snapshot.columns.find(column => column.colId === specs[2].colId).hide = true;
  snapshot.sort = [{ colId: specs[2].colId, sort: "desc" }];
  snapshot.quickFilter = "cultivar or role";
  snapshot.filterModel[specs[3].colId] = { filterType: "text", type: "contains", filter: "license" };
  const wire = encodeGridLayout(snapshot, catalog);
  assert.deepEqual(Object.keys(wire).sort(), ["filters", "hidden", "order", "revision", "widths"]);
  assert.doesNotMatch(JSON.stringify(wire), /cultivar\.identity|company\.company|cohort|detail_path/);
  assert.equal(wire.filters.schema, LAYOUT_SCHEMA);
  const restored = decodeGridLayout({ ...wire, revision: 1 }, catalog);
  assert.equal(restored.status, "restored"); assert.equal(restored.writable, true);
  assert.deepEqual(restored.snapshot.columns.slice(0, 2).map(column => column.colId), specs.slice(0, 2).map(column => column.colId));
  assert.equal(restored.snapshot.columns[0].hide, false); assert.equal(restored.snapshot.columns[1].width, 90);
  assert.equal(restored.snapshot.columns.find(column => column.colId === specs[2].colId).hide, true);
  assert.deepEqual(restored.snapshot.filterModel, snapshot.filterModel); assert.deepEqual(restored.snapshot.sort, snapshot.sort);
  assert.equal(restored.snapshot.quickFilter, snapshot.quickFilter);
});

test("temporarily absent dynamic columns retain preferences and rejoin through current semantic lookup", async () => {
  const all = await createColumnCatalog(specs), subset = await createColumnCatalog(specs.slice(0, 3));
  const original = defaultGridLayout(all); original.columns[3].width = 415; original.columns[3].hide = true;
  original.sort = [{ colId: specs[3].colId, sort: "asc" }]; original.filterModel[specs[3].colId] = { filterType: "number", type: "greaterThan", filter: 3 };
  const saved = { ...encodeGridLayout(original, all), revision: 2 };
  const partial = decodeGridLayout(saved, subset); assert.equal(partial.retainedUnknownColumns, 1);
  partial.snapshot.columns[2].width = 310;
  const updated = { ...encodeGridLayout(partial.snapshot, subset, saved), revision: 3 };
  const returned = decodeGridLayout(updated, all);
  assert.equal(returned.snapshot.columns.find(column => column.colId === specs[3].colId).width, 415);
  assert.equal(returned.snapshot.columns.find(column => column.colId === specs[3].colId).hide, true);
  assert.deepEqual(returned.snapshot.sort, original.sort); assert.deepEqual(returned.snapshot.filterModel, original.filterModel);
});

test("hash-only legacy layouts remain untouched without provable semantic correspondence", async () => {
  const catalog = await createColumnCatalog(specs);
  const legacy = { revision: 5, widths: { "c0-a23": 300 }, order: ["c0-a23"], hidden: [], filters: {} };
  const before = JSON.stringify(legacy), loaded = decodeGridLayout(legacy, catalog);
  assert.equal(loaded.status, "legacy-unmapped"); assert.equal(loaded.writable, false);
  assert.throws(() => encodeGridLayout(loaded.snapshot, catalog, legacy), error => error.kind === "migration");
  assert.equal(JSON.stringify(legacy), before);
});

test("limits reject oversized, unknown or non-Community filters before any write", async () => {
  const catalog = await createColumnCatalog(specs), snapshot = defaultGridLayout(catalog);
  snapshot.filterModel[specs[2].colId] = { filterType: "set", values: ["private"] };
  assert.throws(() => encodeGridLayout(snapshot, catalog), /Community/);
  snapshot.filterModel[specs[2].colId] = { filterType: "text", type: "contains", filter: "x".repeat(201) };
  assert.throws(() => encodeGridLayout(snapshot, catalog), /supported length/);
  snapshot.filterModel[specs[2].colId] = { filterType: "text", type: "contains", filter: "okay", rows: [{ evidence: "not layout" }] };
  assert.throws(() => encodeGridLayout(snapshot, catalog), /unsupported fields/);
  await assert.rejects(createColumnCatalog(Array.from({ length: 41 }, (_, i) => ({ colId: `column.${i}` }))), /forty/);
});

test("accumulated dynamic columns and UTF-8 payload limits fail without dropping older preferences", async () => {
  const columns = Array.from({ length: 41 }, (_, i) => ({ colId: `column.${i}` }));
  const oldCatalog = await createColumnCatalog(columns.slice(0, 40)), nextCatalog = await createColumnCatalog(columns.slice(1));
  const saved = { ...encodeGridLayout(defaultGridLayout(oldCatalog), oldCatalog), revision: 2 }, before = JSON.stringify(saved);
  assert.throws(() => encodeGridLayout(defaultGridLayout(nextCatalog), nextCatalog, saved), /dimensions/);
  assert.equal(JSON.stringify(saved), before);
  const snapshot = defaultGridLayout(oldCatalog);
  snapshot.columns.forEach(column => { column.hide = true; column.width = 1200; });
  snapshot.sort = columns.slice(0, 5).map(column => ({ colId: column.colId, sort: "asc" }));
  for (const column of columns.slice(0, 22)) snapshot.filterModel[column.colId] = { filterType: "text", type: "contains", filter: "界".repeat(200) };
  assert.throws(() => encodeGridLayout(snapshot, oldCatalog), /too large/);
});

test("account endpoint uses credentials, optimistic revisions and serial writes without selector state", async () => {
  const catalog = await createColumnCatalog(specs), calls = []; let wire = empty();
  const controller = new AccountGridLayouts({ viewKey: "berry-portfolio-v1", catalog, fetch: async (url, options) => {
    calls.push({ url, options });
    if (options.method === "POST") { const payload = JSON.parse(options.body); assert.equal(payload.revision, wire.revision); wire = { ...payload, revision: wire.revision + 1 }; }
    return json(wire);
  } });
  await assert.rejects(controller.save(defaultGridLayout(catalog)), error => error.kind === "unloaded");
  assert.equal((await controller.load()).status, "default");
  const snapshot = defaultGridLayout(catalog);
  const first = controller.save(snapshot); snapshot.columns[2].width = 395; const second = controller.save(snapshot);
  await Promise.all([first, second]);
  assert.deepEqual(calls.map(call => call.options.method), ["GET", "POST", "POST"]);
  assert.equal(JSON.parse(calls[1].options.body).widths[catalog.byId.get(specs[2].colId).key], 260);
  assert.equal(JSON.parse(calls[2].options.body).widths[catalog.byId.get(specs[2].colId).key], 395);
  for (const call of calls) { assert.equal(call.url, "/api/ui/sheets/berry-portfolio-v1"); assert.equal(call.options.credentials, "same-origin"); assert.equal(call.options.cache, "no-store"); }
  assert.equal(controller.getState().revision, 2); controller.dispose();
});

test("a 409 freezes queued saves until explicit reload and never overwrites another tab", async () => {
  const catalog = await createColumnCatalog(specs); let reads = 0, posts = 0;
  const controller = new AccountGridLayouts({ viewKey: "berry-portfolio-v1", catalog, fetch: async (_, options) => {
    if (options.method === "GET") return json(reads++ ? { ...encodeGridLayout(defaultGridLayout(catalog), catalog), revision: 7 } : empty());
    posts++; return posts === 1 ? json({ detail: "This layout changed in another tab. Reload before saving more changes." }, 409) : json({ ...JSON.parse(options.body), revision: 8 });
  } });
  await controller.load();
  const results = await Promise.allSettled([controller.save(defaultGridLayout(catalog)), controller.save(defaultGridLayout(catalog))]);
  assert.ok(results.every(result => result.status === "rejected" && result.reason.kind === "conflict"));
  assert.equal(posts, 1); assert.equal(controller.getState().conflict, true);
  assert.equal((await controller.load()).revision, 7); assert.equal(controller.getState().conflict, false);
  assert.equal((await controller.save(defaultGridLayout(catalog))).revision, 8); controller.dispose();
});

test("login redirects and session transition clear private cached layouts and block delayed writes", async () => {
  const catalog = await createColumnCatalog(specs), events = new EventTarget(); let posts = 0;
  const controller = new AccountGridLayouts({ viewKey: "berry-portfolio-v1", catalog, sessionEvents: events, fetch: async (_, options) => { if (options.method === "POST") posts++; return json(empty()); } });
  await controller.load(); events.dispatchEvent(new Event("berry:session-transition"));
  assert.deepEqual(controller.getState(), { status: "disposed", revision: null, conflict: false });
  await assert.rejects(controller.save(defaultGridLayout(catalog)), error => error.kind === "disposed"); assert.equal(posts, 0);
  let required = 0;
  const expired = new AccountGridLayouts({ viewKey: "berry-portfolio-v1", catalog, onSessionRequired: () => required++, fetch: async () => ({ redirected: true, status: 200 }) });
  await assert.rejects(expired.load(), error => error instanceof GridLayoutError && error.kind === "session");
  assert.equal(required, 1); assert.equal(expired.getState().status, "disposed");
  assert.throws(() => new AccountGridLayouts({ viewKey: "../other-account", catalog }), /Unsupported/);
});

test("a delayed response cannot repopulate an account layout after logout", async () => {
  const catalog = await createColumnCatalog(specs), events = new EventTarget(); let release, started;
  const began = new Promise(resolve => { started = resolve; });
  const controller = new AccountGridLayouts({ viewKey: "berry-portfolio-v1", catalog, sessionEvents: events, fetch: async () => {
    started(); return await new Promise(resolve => { release = () => resolve(json(empty())); });
  } });
  const loading = controller.load(); await began;
  events.dispatchEvent(new Event("berry:session-transition")); release();
  await assert.rejects(loading, error => error.kind === "disposed");
  assert.deepEqual(controller.getState(), { status: "disposed", revision: null, conflict: false });
});
