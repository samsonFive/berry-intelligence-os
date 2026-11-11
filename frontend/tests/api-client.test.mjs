import assert from "node:assert/strict";
import test from "node:test";
import { EMPTY_CONTEXT } from "../src/contracts/investigation.ts";
import { getInvestigation, InvestigationApiError, investigationQueryKey } from "../src/api/client.ts";

const envelope = revision => ({ api_v: 1, request_id: "request-1", revision, scope_key: "scope-1", applied_scope: {}, issues: [], data: { title: "Source-backed result" } });
test("the API sends only selectors to the fixed same-origin endpoint with an abort signal", async () => {
  const original = globalThis.fetch;
  const controller = new AbortController();
  let request;
  globalThis.fetch = async (url, options) => {
    request = { url, options };
    return new Response(JSON.stringify(envelope(7)), { headers: { "content-type": "application/json" } });
  };
  try {
    const result = await getInvestigation("/detail?type=source&id=ev-a", EMPTY_CONTEXT, 7, controller.signal);
    assert.equal(result.revision, 7);
    assert.match(request.url, /^\/api\/investigations\/v1\/detail\?/);
    const params = new URL(request.url, "https://test.invalid").searchParams;
    assert.equal(params.get("revision"), "7"); assert.equal(params.get("type"), "source");
    assert.equal(params.get("berry"), "all"); assert.equal(params.get("countries"), "");
    assert.equal(request.options.signal, controller.signal);
    assert.equal(request.options.credentials, "same-origin");
    assert.equal(request.options.cache, "no-store");
  } finally { globalThis.fetch = original; }
});
test("stale response envelopes and login redirects cannot masquerade as current data", async () => {
  const original = globalThis.fetch;
  try {
    globalThis.fetch = async () => new Response(JSON.stringify(envelope(2)), { headers: { "content-type": "application/json" } });
    await assert.rejects(getInvestigation("/landscape", EMPTY_CONTEXT, 3), error => error instanceof InvestigationApiError && error.status === 502);
    globalThis.fetch = async () => ({ redirected: true, status: 200 });
    await assert.rejects(getInvestigation("/landscape", EMPTY_CONTEXT, 3), error => error instanceof InvestigationApiError && error.requiresSession);
  } finally { globalThis.fetch = original; }
});
test("external endpoints and query parameter injection are rejected before fetch", async () => {
  await assert.rejects(getInvestigation("https://external.invalid", EMPTY_CONTEXT, 0));
  await assert.rejects(getInvestigation("//external.invalid", EMPTY_CONTEXT, 0));
  await assert.rejects(getInvestigation("/detail?berry=blueberry", EMPTY_CONTEXT, 0));
});
test("bounded FastAPI string validation detail is preserved for the caller", async () => {
  const original = globalThis.fetch;
  globalThis.fetch = async () => new Response(JSON.stringify({ detail: "Choose a supported geographic basis." }), { status: 400, headers: { "content-type": "application/json" } });
  try {
    await assert.rejects(getInvestigation("/landscape", EMPTY_CONTEXT, 0), error => error instanceof InvestigationApiError && error.message === "Choose a supported geographic basis.");
  } finally { globalThis.fetch = original; }
});
test("query keys isolate focus, both cohorts, source detail and action revision", () => {
  const base = investigationQueryKey("/landscape", EMPTY_CONTEXT, 0);
  assert.notDeepEqual(base, investigationQueryKey("/landscape", { ...EMPTY_CONTEXT, focus: "company-a" }, 0));
  assert.notDeepEqual(base, investigationQueryKey("/landscape", { ...EMPTY_CONTEXT, cohort_companies: "company-a" }, 0));
  assert.notDeepEqual(base, investigationQueryKey("/landscape", { ...EMPTY_CONTEXT, detail_path: "source:ev-a" }, 0));
  assert.notDeepEqual(base, investigationQueryKey("/landscape", EMPTY_CONTEXT, 1));
});
