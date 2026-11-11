import assert from "node:assert/strict";
import test from "node:test";
import { SurfaceMemory } from "../src/app/surface-memory.ts";
import { EMPTY_CONTEXT, investigationHref, isNativeSurfacePath, parseInvestigation } from "../src/contracts/investigation.ts";

const landscape = key => ({ path: "/app/landscape", key });
const briefing = key => ({ path: "/app/briefing", key });

test("loading-height clamps never overwrite a pending destination's saved position", () => {
  const memory = new SurfaceMemory();
  memory.begin(landscape("a"), "POP"); memory.finish({ x: 0, y: 1000 });
  memory.begin(briefing("b"), "PUSH");
  memory.observe({ x: 0, y: 0 });
  memory.finish({ x: 0, y: 50 });
  memory.begin(landscape("c"), "PUSH");
  for (let n = 0; n < 4; n++) memory.observe({ x: 0, y: 0 });
  assert.deepEqual(memory.pending(landscape("c")), { x: 0, y: 1000 });
  memory.finish({ x: 0, y: 1000 });
  memory.begin(briefing("d"), "PUSH");
  assert.deepEqual(memory.pending(briefing("d")), { x: 0, y: 50 });
});

test("same-surface direct actions retain viewport while Back/Forward restore exact entries", () => {
  const memory = new SurfaceMemory();
  memory.begin(landscape("sourceParent"), "POP"); memory.finish({ x: 0, y: 700 });
  memory.begin(landscape("sourceDetail"), "PUSH");
  assert.equal(memory.pending(landscape("sourceDetail")), null);
  memory.observe({ x: 0, y: 950 });
  memory.begin(landscape("sourceParent"), "POP");
  assert.deepEqual(memory.pending(landscape("sourceParent")), { x: 0, y: 700 });
  memory.finish({ x: 0, y: 700 });
  memory.begin(landscape("sourceDetail"), "POP");
  assert.deepEqual(memory.pending(landscape("sourceDetail")), { x: 0, y: 950 });
});

test("same-surface loading can defer its viewport without recording a DOM clamp", () => {
  const memory = new SurfaceMemory();
  memory.begin(landscape("initial"), "POP"); memory.finish({ x: 0, y: 800 });
  memory.begin(landscape("changedScope"), "PUSH");
  memory.defer(landscape("changedScope"));
  memory.observe({ x: 0, y: 0 });
  assert.deepEqual(memory.pending(landscape("changedScope")), { x: 0, y: 800 });
  memory.finish({ x: 0, y: 800 });
});

test("reload retains bounded coordinate memory without source, context or learning identifiers", () => {
  const memory = new SurfaceMemory();
  const learning = { path: "/app/learn/concept/concept-private-example", key: "learning" };
  memory.begin(learning, "PUSH"); memory.finish({ x: 12, y: 510 });
  const serialized = memory.serialize();
  assert.doesNotMatch(serialized, /concept-private-example|detail_path|countries/);
  const reload = new SurfaceMemory(serialized);
  reload.begin(learning, "POP");
  assert.deepEqual(reload.pending(learning), { x: 12, y: 510 });
  for (let n = 0; n < 100; n++) {
    reload.begin(landscape(`entry${n}`), "PUSH"); reload.finish({ x: 0, y: n });
  }
  assert.equal(JSON.parse(reload.serialize()).entries.length, 64);
});

test("session clearing prevents pending or delayed scroll events from repopulating memory", () => {
  const memory = new SurfaceMemory();
  memory.begin(landscape("a"), "POP"); memory.finish({ x: 0, y: 123 });
  memory.clear();
  memory.observe({ x: 0, y: 456 }); memory.finish({ x: 0, y: 789 });
  memory.begin(briefing("b"), "PUSH");
  assert.deepEqual(JSON.parse(memory.serialize()), { v: 1, surfaces: [], entries: [] });
  assert.equal(memory.pending(landscape("a")), null);
});

test("untrusted storage cannot add unsupported routes or nonfinite positions", () => {
  const memory = new SurfaceMemory(JSON.stringify({ v: 1, surfaces: [{ path: "/secret", x: 0, y: 100 }, { path: "/app/learn", x: -1, y: 20 }],
    entries: [{ path: "/app/landscape", key: "private?query", x: 0, y: 5 }, { path: "/app/briefing", key: "safe", x: 0, y: "100" }] }));
  assert.deepEqual(JSON.parse(memory.serialize()), { v: 1, surfaces: [], entries: [] });
});

test("native learning destinations preserve global scope and reject malformed route identifiers", () => {
  for (const kind of ["concept", "lesson"]) {
    const path = `/app/learn/${kind}/learning-example.v1`;
    assert.equal(isNativeSurfacePath(path), true);
    const href = investigationHref(path, { ...EMPTY_CONTEXT, berry: "berry-blueberry", countries: "geography-china" });
    assert.equal(new URL(href, "https://test.invalid").pathname, path);
    assert.equal(parseInvestigation(new URL(href, "https://test.invalid").search).context.countries, "geography-china");
  }
  for (const path of ["/app/learn/concept/.", "/app/learn/lesson/..", "/app/learn/concept/%2e%2e", "/app/learn/concept/a/b", `/app/learn/concept/${"a".repeat(181)}`, "/app/learn/unknown/id", "//external.test/app/learn"]) {
    assert.equal(isNativeSurfacePath(path), false);
    assert.throws(() => investigationHref(path, EMPTY_CONTEXT));
  }
});
