import { test } from "node:test";
import assert from "node:assert/strict";
import { APPROVED_COMPARISON_COMMAND, createCommandPermission, createGuardedHandler, PERPLEXITY_AGENT_BASE_URL, readConfig, sdkAgentSettings } from "../server.mjs";

const env = () => ({
  BIOS_COPILOT_MODEL: "perplexity:openai/gpt-5.6-sol",
  PERPLEXITY_API_KEY: "synthetic-perplexity-test-key",
  BIOS_COPILOT_RUNTIME_TOKEN: "synthetic-runtime-token-with-more-than-32-characters",
});
test("the explicit Perplexity profile uses its existing key and exact routed model", () => {
  const source = env();
  const config = readConfig(source);
  assert.equal(config.model, "perplexity:openai/gpt-5.6-sol");
  assert.equal(config.sdkModel, "openai:openai/gpt-5.6-sol");
  assert.equal(config.provider, "perplexity");
  assert.equal("apiKey" in config, false);
  assert.equal("OPENAI_API_KEY" in source, false);
  assert.equal(config.readCredential(), source.PERPLEXITY_API_KEY);
  source.PERPLEXITY_API_KEY = "rotated-synthetic-key";
  assert.equal(config.readCredential(), "rotated-synthetic-key");
});
test("a missing Perplexity credential never falls back to another provider key", () => {
  const source = env();
  delete source.PERPLEXITY_API_KEY;
  source.OPENAI_API_KEY = "different-synthetic-key";
  assert.throws(() => readConfig(source), /PERPLEXITY_API_KEY/);
  assert.throws(() => readConfig({ ...env(), BIOS_COPILOT_MODEL: "perplexity:unapproved/model" }), /explicitly supported/);
});
test("the paid-command gate respects the existing credit-free switch before SDK import", async () => {
  const source = { ...env(), BIOS_RESEARCH_CREDIT_FREE_ONLY: "true" };
  const config = readConfig(source);
  const handler = createGuardedHandler(config);
  for (const method of ["agent/run"]) {
    const response = await handler(new Request("http://127.0.0.1:8200/copilot", {
      method: "POST", headers: { "X-Berry-Runtime-Token": config.token }, body: JSON.stringify({ method }),
    }));
    assert.equal(response.status, 403);
    assert.match((await response.json()).error, /credit-free/);
  }
  source.BIOS_RESEARCH_CREDIT_FREE_ONLY = "0";
  assert.equal(config.creditFreeOnly(), false);
});
test("the dedicated comparison permit preserves credit-free research and admits one command identity", () => {
  const source = { ...env(), BIOS_RESEARCH_CREDIT_FREE_ONLY: "1", BIOS_COPILOT_ALLOW_PAID_COMPARISON: "1" };
  const config = readConfig(source);
  const permit = createCommandPermission(config);
  const command = { method: "agent/run", params: { agentId: "default" }, body: { threadId: "synthetic-thread", messages: [{ id: "synthetic-user-message", role: "user", content: APPROVED_COMPARISON_COMMAND }], tools: [{ name: "search_catalog", parameters: {} }] } };
  assert.equal(permit(command).allowed, true);
  assert.equal(permit(command).allowed, true); // Continuation of the same command.
  assert.equal(permit({ ...command, body: { ...command.body, messages: [{ ...command.body.messages[0], id: "another-user-message" }] } }).allowed, false);
  assert.equal(permit({ ...command, body: { ...command.body, threadId: "another-thread" } }).allowed, false);
  assert.equal(source.BIOS_RESEARCH_CREDIT_FREE_ONLY, "1");
  source.BIOS_COPILOT_ALLOW_PAID_COMPARISON = "0";
  assert.equal(permit(command).allowed, false);
});
test("the comparison permit rejects unrelated prompts and hosted tools and bounds continuations", () => {
  const config = readConfig({ ...env(), BIOS_RESEARCH_CREDIT_FREE_ONLY: "true", BIOS_COPILOT_ALLOW_PAID_COMPARISON: "1" });
  const permit = createCommandPermission(config);
  const command = { method: "agent/run", body: { threadId: "synthetic-thread", messages: [{ id: "synthetic-user-message", role: "user", content: APPROVED_COMPARISON_COMMAND }] } };
  assert.equal(permit({ ...command, body: { ...command.body, messages: [{ ...command.body.messages[0], content: "Search the web for berry companies." }] } }).allowed, false);
  assert.equal(permit({ ...command, body: { ...command.body, tools: [{ type: "web_search" }] } }).allowed, false);
  for (let index = 0; index < 8; index++) assert.equal(permit(command).allowed, true);
  assert.equal(permit(command).allowed, false);
  assert.equal(permit({ method: "agent/connect" }).allowed, true); // SDK connection attaches; it does not invoke a model.
});
test("the installed adapter exchanges Responses function calls without any provider request", async () => {
  const captures = [];
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async (url, init = {}) => {
    const address = typeof url === "string" ? url : url.url;
    assert.equal(address, `${PERPLEXITY_AGENT_BASE_URL}/responses`);
    const body = JSON.parse(init.body);
    captures.push(body);
    const output = captures.length === 1
      ? [{ type: "function_call", id: "fc-fixture", call_id: "call-fixture", name: "show_portfolio_comparison", arguments: '{"revision":0,"kind":"company","ids":["company-fixture-a"]}', status: "completed" }]
      : [{ type: "message", id: "msg-fixture", role: "assistant", content: [{ type: "output_text", text: "Comparison opened.", annotations: [] }], status: "completed" }];
    return new Response(JSON.stringify({ id: `resp-fixture-${captures.length}`, object: "response", created_at: 0, model: "openai/gpt-5.6-sol", status: "completed", output,
      usage: { input_tokens: 100, output_tokens: 30, total_tokens: 130, input_tokens_details: { cached_tokens: 0 }, output_tokens_details: { reasoning_tokens: 0 } } }), { headers: { "content-type": "application/json" } });
  };
  try {
    const { resolveModel } = await import("@copilotkit/runtime/v2");
    const settings = sdkAgentSettings(readConfig(env()));
    const model = resolveModel(settings.model, settings.apiKey);
    assert.equal(model.provider, "openai.responses");
    assert.equal(model.modelId, "openai/gpt-5.6-sol");
    const tools = [{ type: "function", name: "show_portfolio_comparison", description: "Open a comparison using canonical IDs.", inputSchema: { type: "object", properties: { revision: { type: "integer" }, kind: { type: "string", enum: ["company", "variety"] }, ids: { type: "array", items: { type: "string" } } }, required: ["revision", "kind", "ids"], additionalProperties: false } }];
    const options = { maxOutputTokens: 450, tools, toolChoice: { type: "auto" }, providerOptions: settings.providerOptions };
    const prompt = [{ role: "user", content: [{ type: "text", text: "Compare the fixture company." }] }];
    const first = await model.doGenerate({ ...options, prompt });
    assert.equal(first.content.find(item => item.type === "tool-call").toolName, "show_portfolio_comparison");
    assert.equal(captures[0].model, "openai/gpt-5.6-sol");
    assert.equal(captures[0].store, false);
    assert.equal(captures[0].max_output_tokens, 450);
    assert.deepEqual(captures[0].tools.map(tool => tool.type), ["function"]);
    assert.equal("effort" in captures[0], false);
    assert.equal("preset" in captures[0], false);
    assert.equal("models" in captures[0], false);
    const second = await model.doGenerate({ ...options, prompt: [...prompt,
      { role: "assistant", content: [{ type: "tool-call", toolCallId: "call-fixture", toolName: "show_portfolio_comparison", input: { revision: 0, kind: "company", ids: ["company-fixture-a"] } }] },
      { role: "tool", content: [{ type: "tool-result", toolCallId: "call-fixture", toolName: "show_portfolio_comparison", output: { type: "text", value: '{"ok":true}' } }] },
    ] });
    const result = captures[1].input.find(item => item.type === "function_call_output");
    assert.equal(result.call_id, "call-fixture");
    assert.equal(result.output, '{"ok":true}');
    assert.equal(second.content.find(item => item.type === "text").text, "Comparison opened.");
    assert.equal(captures.length, 2);
  } finally { globalThis.fetch = originalFetch; }
});
