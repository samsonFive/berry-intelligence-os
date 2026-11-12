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

test("news and monitoring pagination retain the company universe and independent comparison selectors", async () => {
  const original = globalThis.fetch; const requests = [];
  globalThis.fetch = async (url, options) => { requests.push({ url, options }); return new Response(JSON.stringify(envelope(9)), { headers: { "content-type": "application/json" } }); };
  const selected = { ...EMPTY_CONTEXT, company_set: "watched", countries: "geography-china", cohort_companies: "company-a,company-b" };
  try {
    for (const endpoint of ["/monitoring?offset=10&limit=10", "/news?offset=20&limit=20"]) await getInvestigation(endpoint, selected, 9);
    for (const request of requests) {
      const params = new URL(request.url, "https://test.invalid").searchParams;
      assert.equal(params.get("company_set"), "watched"); assert.equal(params.get("countries"), "geography-china");
      assert.equal(params.get("cohort_companies"), "company-a,company-b"); assert.equal(params.get("revision"), "9");
      assert.equal(request.options.credentials, "same-origin"); assert.equal(request.options.cache, "no-store");
    }
    assert.equal(selected.company_set, "watched");
  } finally { globalThis.fetch = original; }
});

test("invalid pages, duplicate parameters and selector/revision overrides fail before any request", async () => {
  const original = globalThis.fetch; let requests = 0;
  globalThis.fetch = async () => { requests++; throw new Error("Must not fetch invalid pagination"); };
  try {
    for (const endpoint of ["/landscape?offset=0", "/comparison?limit=10", "/news?offset=-1", "/news?offset=1.5", "/news?offset=1e2",
      "/news?offset=9007199254740992", "/monitoring?limit=0", "/monitoring?limit=101", "/news?offset=0&offset=10",
      "/news?limit=10&limit=20", "/news?revision=1", "/monitoring?company_set=all", "/news?countries="])
      await assert.rejects(getInvestigation(endpoint, EMPTY_CONTEXT, 0), error => error instanceof InvestigationApiError && error.status === 400);
    assert.equal(requests, 0);
  } finally { globalThis.fetch = original; }
});

test("a safe-integer offset has no artificial company-count cap", async () => {
  const original = globalThis.fetch; let captured;
  globalThis.fetch = async url => { captured = url; return new Response(JSON.stringify(envelope(0)), { headers: { "content-type": "application/json" } }); };
  try {
    await getInvestigation("/monitoring?offset=9007199254740991&limit=100", EMPTY_CONTEXT, 0);
    const params = new URL(captured, "https://test.invalid").searchParams;
    assert.equal(params.get("offset"), "9007199254740991"); assert.equal(params.get("limit"), "100");
  } finally { globalThis.fetch = original; }
});
