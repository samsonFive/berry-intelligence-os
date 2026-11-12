import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { APPROVED_COMPARISON_COMMAND, createGuardedHandler, readConfig, restrictCommandModel, safeFailureDiagnostic } from "../server.mjs";

const fixtureEnvironment = () => ({ BIOS_COPILOT_MODEL: "perplexity:openai/gpt-5.6-sol", PERPLEXITY_API_KEY: "synthetic-fixture-key",
  BIOS_COPILOT_RUNTIME_TOKEN: "synthetic-token-with-at-least-thirty-two-characters", BIOS_RESEARCH_CREDIT_FREE_ONLY: "1", BIOS_COPILOT_ALLOW_PAID_COMPARISON: "1" });
// Captured from the real mounted SDK's outgoing tool registrations; no messages, context or results.
const registeredTools = JSON.parse(readFileSync(new URL("./fixtures/registered-frontend-tools.json", import.meta.url), "utf8"));
const fixtureArguments = { revision: 0, kind: "company", query: "Fixture" };

function providerStream(final = false) {
  const argumentsText = JSON.stringify(fixtureArguments);
  const call = { type: "function_call", id: "fc-fixture", call_id: "call-fixture", name: "search_catalog", arguments: argumentsText, status: "completed" };
  const events = [
    { type: "response.created", response: { id: "resp-fixture", created_at: 0, model: "openai/gpt-5.6-sol", status: "in_progress" } },
    { type: "response.output_item.added", output_index: 0, item: { ...call, arguments: "", status: "in_progress" } },
    { type: "response.function_call_arguments.delta", item_id: call.id, output_index: 0, delta: argumentsText },
    { type: "response.function_call_arguments.done", item_id: call.id, output_index: 0, arguments: argumentsText },
    { type: "response.output_item.done", output_index: 0, item: call },
    { type: "response.completed", response: { id: "resp-fixture", model: "openai/gpt-5.6-sol", created_at: 0, status: "completed", output: [call],
      usage: { input_tokens: 100, output_tokens: 30, total_tokens: 130, input_tokens_details: { cached_tokens: 0 }, output_tokens_details: { reasoning_tokens: 0 } } } },
  ];
  const message = { type: "message", id: "msg-fixture", role: "assistant", status: "completed", content: [{ type: "output_text", text: "Fixture completed.", annotations: [] }] };
  const finalEvents = [events[0], { type: "response.output_item.added", output_index: 0, item: { ...message, content: [], status: "in_progress" } },
    { type: "response.output_text.delta", item_id: message.id, output_index: 0, content_index: 0, delta: "Fixture completed." },
    { type: "response.output_item.done", output_index: 0, item: message },
    { ...events.at(-1), response: { ...events.at(-1).response, output: [message] } }];
  return new Response((final ? finalEvents : events).map(event => `event: ${event.type}\ndata: ${JSON.stringify(event)}\n\n`).join(""), { headers: { "content-type": "text/event-stream" } });
}

test("the actual guarded BuiltInAgent streams only approved functions over the fixed Perplexity Responses transport", { timeout: 60_000 }, async () => {
  const fetch = globalThis.fetch;
  const captures = [];
  globalThis.fetch = async (url, init = {}) => {
    assert.equal(typeof url === "string" ? url : url.url, "https://api.perplexity.ai/v1/responses");
    captures.push(JSON.parse(init.body));
    return providerStream(captures.length > 1);
  };
  try {
    const diagnostics = [];
    const config = { ...readConfig(fixtureEnvironment()), reportDiagnostic: event => diagnostics.push(event) };
    const handler = createGuardedHandler(config);
    const input = {
        threadId: "synthetic-thread", runId: "synthetic-run", state: {}, context: [{ description: "Current investigation revision", value: "0" }], forwardedProps: {},
        messages: [{ id: "synthetic-message", role: "user", content: APPROVED_COMPARISON_COMMAND }], tools: registeredTools,
      };
    const request = body => new Request("http://127.0.0.1:8200/copilot", { method: "POST", headers: { "X-Berry-Runtime-Token": config.token,
      "Content-Type": "application/json", Accept: "text/event-stream" }, body: JSON.stringify({ method: "agent/run", params: { agentId: "default" }, body }) });
    const response = await handler(request(input));
    assert.equal(response.status, 200);
    const text = await response.text();
    assert.doesNotMatch(text, /RUN_ERROR/);
    assert.match(text, /TOOL_CALL_START/);
    assert.match(text, /search_catalog/);
    assert.match(text, /RUN_FINISHED/);
    assert.equal(captures.length, 1);
    const body = captures[0];
    assert.equal(body.model, "openai/gpt-5.6-sol");
    assert.equal(body.stream, true);
    assert.equal(body.store, false);
    assert.equal(body.max_output_tokens, 450);
    assert.equal(body.tools.length, 7);
    assert.ok(body.tools.every(tool => tool.type === "function"));
    assert.deepEqual(body.tools.map(tool => tool.name), registeredTools.map(tool => tool.name));
    assert.deepEqual(diagnostics.find(event => event.type === "command_model_request"), { type: "command_model_request", tool_count: 7, excluded_tool_count: 2 });
    assert.equal(diagnostics.find(event => event.type === "command_provider_finish").input_tokens, 100);
    assert.equal("effort" in body, false); assert.equal("preset" in body, false); assert.equal("models" in body, false);
    const followup = await handler(request({ ...input, runId: "synthetic-followup", messages: [...input.messages,
      { id: "synthetic-assistant", role: "assistant", toolCalls: [{ id: "call-fixture", type: "function", function: { name: "search_catalog", arguments: JSON.stringify(fixtureArguments) } }] },
      { id: "synthetic-result", role: "tool", toolCallId: "call-fixture", content: '{"ok":true,"results":[]}' },
    ] }));
    const final = await followup.text();
    assert.doesNotMatch(final, /RUN_ERROR/); assert.match(final, /RUN_FINISHED/); assert.match(final, /Fixture completed/);
    assert.equal(captures.length, 2);
    const result = captures[1].input.find(item => item.type === "function_call_output");
    assert.equal(result.call_id, "call-fixture"); assert.equal(result.output, '{"ok":true,"results":[]}');
  } finally { globalThis.fetch = fetch; }
});

test("provider diagnostics retain only allowlisted category/status/code and numeric usage", async () => {
  const secretText = "PRIVATE_FIXTURE_PAYLOAD_AND_KEY";
  const error = Object.assign(new Error(secretText), { name: "AI_APICallError", statusCode: 400,
    data: { error: { code: "invalid_json_schema", param: "tools", message: secretText } }, responseBody: secretText,
    responseHeaders: { "x-request-id": "req_synthetic123456", authorization: secretText } });
  assert.deepEqual(safeFailureDiagnostic(error), { type: "command_provider_error", terminal_event: "RUN_ERROR", category: "provider_http", name: "AI_APICallError", http_status: 400, provider_code: "invalid_json_schema", param: "tools", request_id: "req_synthetic123456" });
  assert.doesNotMatch(JSON.stringify(safeFailureDiagnostic({ name: secretText, code: secretText })), /PRIVATE/);
  const diagnostics = [];
  const model = restrictCommandModel({ provider: "synthetic", modelId: "fixture", specificationVersion: "v3", supportedUrls: {},
    async doGenerate() { throw error; } }, value => diagnostics.push(value));
  await assert.rejects(model.doGenerate({ tools: [{ type: "function", name: "AGUISendStateSnapshot" }, { type: "provider", name: "web_search" }] }), { name: "AI_APICallError" });
  assert.equal(diagnostics[0].tool_count, 0);
  assert.equal(diagnostics[0].excluded_tool_count, 2);
  assert.doesNotMatch(JSON.stringify(diagnostics), /PRIVATE/);
});

test("undeclared SDK state tools are rejected before returning a tool call to the agent", async () => {
  const diagnostics = [];
  class Model {
    #provider = "synthetic-provider";
    get provider() { return this.#provider; }
    get modelId() { return "synthetic-model"; }
    get specificationVersion() { return "v3"; }
    get supportedUrls() { return {}; }
    async doGenerate() { assert.equal(this.#provider, "synthetic-provider"); return { content: [{ type: "tool-call", toolName: "AGUISendStateSnapshot", input: "PRIVATE_FIXTURE_STATE" }] }; }
    async doStream() { assert.equal(this.#provider, "synthetic-provider"); return { stream: new ReadableStream({ start(controller) {
      controller.enqueue({ type: "tool-input-start", id: "synthetic-call", toolName: "AGUISendStateDelta" }); controller.close();
    } }) }; }
  }
  const model = restrictCommandModel(new Model(), event => diagnostics.push(event));
  assert.equal(model.provider, "synthetic-provider"); assert.equal(model.modelId, "synthetic-model"); assert.equal(model.specificationVersion, "v3");
  await assert.rejects(model.doGenerate({ tools: [] }), { name: "CommandToolBoundaryError" });
  const { stream } = await model.doStream({ tools: [] });
  await assert.rejects(stream.getReader().read(), { name: "CommandToolBoundaryError" });
  assert.equal(diagnostics.filter(event => event.provider_code === "unsupported_tool").length, 2);
  assert.doesNotMatch(JSON.stringify(diagnostics), /PRIVATE/);
});
