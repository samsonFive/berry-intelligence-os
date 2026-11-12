import assert from "node:assert/strict";
import test from "node:test";
import { EMPTY_CONTEXT, currentDetail, normalizeContext, parseInvestigation, parseRef, refString, sameDetailIdentity, serializeInvestigation } from "../src/contracts/investigation.ts";
import { initialInvestigation, reduceInvestigation } from "../src/state/reducer.ts";

const initial = context => initialInvestigation(normalizeContext(context));
const step = (state, action) => reduceInvestigation(state, action).state;

test("source section round trips canonically while historical bare refs stay unchanged", () => {
  assert.equal(refString(parseRef("source:ev-first@article")), "source:ev-first");
  assert.deepEqual(parseRef("source:ev-first"), { type: "source", id: "ev-first" });
  assert.equal(sameDetailIdentity(parseRef("source:ev-first@brief"), parseRef("source:ev-first")), true);
  const context = normalizeContext({ detail_path: "company:company-one~source:ev-first@article~source:ev-second@brief" }).context;
  assert.equal(context.detail_path, "company:company-one~source:ev-first~source:ev-second@brief");
  assert.deepEqual(currentDetail(parseInvestigation(serializeInvestigation(context)).context), { type: "source", id: "ev-second", section: "brief" });
  for (const ref of ["source:ev-first@summary", "company:company-one@brief", "source:ev:first", "source:ev-first@brief@article"]) assert.equal(parseRef(ref), null);
});

test("nested source return restores ancestor section and changing section uses a pushed revision", () => {
  let state = initial({ detail_path: "company:company-one~source:ev-parent", focus: "company-one" });
  const changed = reduceInvestigation(state, { type: "setDetailSection", section: "brief" });
  assert.equal(changed.history, "push"); assert.equal(changed.state.revision, state.revision + 1);
  state = step(changed.state, { type: "openDetail", detail: { type: "source", id: "ev-child" } });
  assert.equal(state.context.detail_path, "company:company-one~source:ev-parent@brief~source:ev-child");
  state = step(state, { type: "closeDetail" });
  assert.deepEqual(currentDetail(state.context), { type: "source", id: "ev-parent", section: "brief" });
  state = step(state, { type: "setDetailSection", section: "article" });
  assert.equal(state.context.detail_path, "company:company-one~source:ev-parent");
  assert.equal(state.context.focus, "company-one");
});

test("source identity ignores section when reopening an ancestor and stale section changes reject", () => {
  let state = initial({ detail_path: "source:ev-parent@brief~source:ev-child" });
  state = step(state, { type: "openDetail", detail: { type: "source", id: "ev-parent" } });
  assert.equal(state.context.detail_path, "source:ev-parent");
  const stale = reduceInvestigation(state, { type: "setDetailSection", section: "brief", expectedRevision: 0 });
  assert.equal(stale.accepted, false); assert.equal(stale.state, state);
  const entity = initial({ detail_path: "company:company-one" });
  assert.equal(reduceInvestigation(entity, { type: "setDetailSection", section: "brief" }).changed, false);
});

test("dismissDetails closes the entire stack while Back pops one and investigation selectors survive", () => {
  const state = initial({ berry: 'berry-blueberry', countries: 'geography-china', actor_roles: 'breeder',
    cohort_companies: 'company-one,company-two', cohort_varieties: 'variety-one', focus: 'company-one',
    company_set: 'watched', q: 'flavor', news_from: '2026-11-01',
    detail_path: 'company:company-one~relationship:rel-one~source:ev-parent@brief' });
  assert.equal(step(state, { type: 'closeDetail' }).context.detail_path, 'company:company-one~relationship:rel-one');
  const result = reduceInvestigation(state, { type: 'dismissDetails' });
  assert.deepEqual(result.state.context, { ...state.context, detail_path: '' });
  assert.equal(result.history, 'push');
  assert.equal(result.state.revision, state.revision + 1);
  assert.equal(reduceInvestigation(result.state, { type: 'dismissDetails' }).changed, false);
  assert.equal(reduceInvestigation(state, { type: 'dismissDetails', expectedRevision: state.revision + 1 }).accepted, false);
});

test("synthetic cohort is URL state independent of real cohorts and scope", () => {
  let state = initial({ ...EMPTY_CONTEXT, cohort_companies: "company-one", cohort_varieties: "variety-one", countries: "geography-china", focus: "company-one" });
  state = step(state, { type: "setDemoCohort", ids: ["demo-specimen-fern", "demo-specimen-amber", "demo-specimen-fern"] });
  assert.equal(state.context.demo_specimens, "demo-specimen-fern,demo-specimen-amber");
  assert.equal(state.context.cohort_companies, "company-one"); assert.equal(state.context.cohort_varieties, "variety-one");
  assert.equal(state.context.countries, "geography-china"); assert.equal(state.context.focus, "company-one");
  assert.deepEqual(parseInvestigation(serializeInvestigation(state.context)).context, state.context);
  assert.equal(step(state, { type: "setDemoCohort", ids: [] }).context.demo_specimens, ""); // Empty means all fixture specimens.
});

test("unknown synthetic IDs remain visible to fixture validation and malformed selections stay diagnosed", () => {
  const unknown = normalizeContext({ demo_specimens: "demo-specimen-future,demo-specimen-amber" });
  assert.equal(unknown.context.demo_specimens, "demo-specimen-future,demo-specimen-amber");
  const invalid = normalizeContext({ demo_specimens: "company-one,demo-specimen-" });
  assert.equal(invalid.context.demo_specimens, "company-one,demo-specimen-");
  assert.equal(invalid.issues[0].field, "demo_specimens");
  assert.equal(normalizeContext({ demo_specimens: Array.from({ length: 41 }, (_, i) => `demo-specimen-${i}`).join(",") }).issues[0].code, "excessive_selection");
});
