import assert from "node:assert/strict";
import test from "node:test";
import { EMPTY_CONTEXT, PRESENTATION_CONTEXT, currentDetail, hasBlockingIssues, investigationHref, normalizeContext, parseInvestigation, serializeInvestigation } from "../src/contracts/investigation.ts";
import { initialInvestigation, reduceInvestigation, revisionMatches } from "../src/state/reducer.ts";

const initial = (context = PRESENTATION_CONTEXT) => initialInvestigation(normalizeContext(context));
const step = (state, action) => reduceInvestigation(state, action).state;
test("a URL round trip retains explicit All, both cohorts, detail ancestors and publication dates", () => {
  const context = normalizeContext({ ...EMPTY_CONTEXT, cohort_companies: "company-b,company-a", cohort_varieties: "variety-one", detail_path: "company:company-b~relationship:rel-a~source:ev-source", news_from: "2026-01-01", news_to: "2026-11-11", q: "Fall Creek & Costa" }).context;
  const encoded = serializeInvestigation(context);
  assert.match(encoded, /berry=all/); assert.match(encoded, /countries=/);
  assert.deepEqual(parseInvestigation(encoded).context, context);
  assert.deepEqual(parseInvestigation("").context, EMPTY_CONTEXT);
});
test("focus, comparison membership and source inspection are separate actions", () => {
  let state = initial();
  state = step(state, { type: "togglePin", entity: { type: "company", id: "company-costa" } });
  assert.equal(state.context.focus, ""); assert.equal(state.context.detail_path, "");
  state = step(state, { type: "focusEntity", entity: { type: "company", id: "company-fall-creek" } });
  const focused = state.context.focus;
  state = step(state, { type: "openDetail", detail: { type: "source", id: "ev-source" } });
  assert.equal(state.context.focus, focused);
  assert.equal(state.context.cohort_companies, "company-costa");
  assert.equal(state.context.countries, PRESENTATION_CONTEXT.countries);
  state = step(state, { type: "closeDetail" });
  assert.deepEqual(currentDetail(state.context), { type: "company", id: "company-fall-creek" });
});
test("changing scope retains pinned outside-scope IDs and both typed cohorts", () => {
  let state = initial();
  state = step(state, { type: "setCohort", kind: "company", ids: ["company-a", "company-b"] });
  state = step(state, { type: "setCohort", kind: "variety", ids: ["variety-a"] });
  state = step(state, { type: "applyScope", scope: { berry: "berry-strawberry", countries: "", focus: "company-unexpected" } });
  assert.equal(state.context.cohort_companies, "company-a,company-b");
  assert.equal(state.context.cohort_varieties, "variety-a");
  assert.equal(state.context.focus, "");
});
test("stale model actions cannot replace newer direct actions", () => {
  const old = initial();
  const changed = step(old, { type: "setLens", lens: "geography" });
  const stale = reduceInvestigation(changed, { type: "setLens", lens: "comparison", expectedRevision: old.revision, origin: "copilot" });
  assert.equal(stale.accepted, false); assert.equal(stale.state, changed);
  assert.equal(revisionMatches(changed.revision, old.revision), false);
});
test("cohort order is stable, duplicate IDs deduplicate and overflow is explicit", () => {
  const result = normalizeContext({ cohort_companies: "c-b,c-a,c-b,c-c,c-d,c-e,c-f", cohort_varieties: "v-a,v-b,v-c,v-d,v-e" });
  assert.equal(result.context.cohort_companies, "c-b,c-a,c-c,c-d,c-e,c-f");
  assert.deepEqual(result.issues.find(issue => issue.field === "cohort_companies").values, ["c-f"]);
  assert.deepEqual(result.issues.find(issue => issue.field === "cohort_varieties").values, ["v-e"]);
});
test("invalid dates, versions, identifiers and duplicate URL fields produce issues", () => {
  const result = parseInvestigation("ctx_v=9&berry=blueberry&berry=all&countries=geography-chile,%3Cscript%3E&news_from=2026-02-30&detail_path=source:../secret");
  assert.equal(result.context.countries, "geography-chile,<script>");
  assert.equal(result.context.news_from, "2026-02-30");
  assert.ok(result.issues.some(issue => issue.code === "unsupported_version"));
  assert.ok(result.issues.some(issue => issue.code === "duplicate_parameter"));
  assert.ok(result.issues.some(issue => issue.code === "invalid_date"));
  assert.ok(result.issues.some(issue => issue.code === "invalid_reference"));
  assert.equal(hasBlockingIssues(result.issues), true);
  assert.equal(normalizeContext({ news_from: "2026-99-99" }).issues[0].code, "invalid_date");
  assert.equal(normalizeContext({ berry: "blueberry" }).context.berry, "berry-blueberry");
});
test("unsupported scope remains visible through unrelated actions instead of becoming All", () => {
  const bad = initialInvestigation(parseInvestigation("berry=unknown&countries=invalid%20country"));
  const changed = step(bad, { type: "setLens", lens: "portfolio" });
  assert.equal(changed.context.berry, "unknown");
  assert.equal(changed.context.countries, "invalid country");
  assert.equal(hasBlockingIssues(changed.issues), true);
  assert.equal(hasBlockingIssues(normalizeContext({ cohort_companies: "a,b,c,d,e,f" }).issues), false);
});
test("legacy focus aliases normalize to a canonical identifier and zero saved revision is valid", () => {
  const result = normalizeContext({ focus: "company:company-fall-creek", saved_revision: "0" });
  assert.equal(result.context.focus, "company-fall-creek");
  assert.equal(result.context.saved_revision, "0");
  assert.deepEqual(result.issues, []);
});
test("search replaces URL state while applied scope and detail deliberately push", () => {
  const state = initial();
  assert.equal(reduceInvestigation(state, { type: "setSearch", q: "Costa" }).history, "replace");
  assert.equal(reduceInvestigation(state, { type: "applyScope", scope: { countries: "" } }).history, "push");
  assert.equal(reduceInvestigation(state, { type: "openDetail", detail: { type: "company", id: "company-a" } }).history, "push");
});
test("detail history is bounded and returning to an ancestor trims descendants", () => {
  let state = initial();
  for (let index = 0; index < 10; index++) state = step(state, { type: "openDetail", detail: { type: "source", id: `ev-${index}` } });
  assert.equal(state.context.detail_path.split("~").length, 8);
  state = step(state, { type: "openDetail", detail: { type: "source", id: "ev-4" } });
  assert.equal(state.context.detail_path, "source:ev-2~source:ev-3~source:ev-4");
});
test("application hrefs cannot direct saved selectors to another origin", () => {
  assert.match(investigationHref("/app/landscape", PRESENTATION_CONTEXT), /^\/app\/landscape\?ctx_v=1/);
  assert.throws(() => investigationHref("https://example.com", PRESENTATION_CONTEXT));
});
