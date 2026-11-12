/** Controlled CopilotKit v2 runtime. No provider call occurs on import/startup. */
import { createServer } from "node:http";
import { timingSafeEqual } from "node:crypto";
import { pathToFileURL } from "node:url";

// This dedicated runtime sends only explicitly submitted model commands.
process.env.COPILOTKIT_TELEMETRY_DISABLED = "true";

const PROVIDER_KEYS = { openai: "OPENAI_API_KEY", anthropic: "ANTHROPIC_API_KEY", google: "GOOGLE_API_KEY", minimax: "MINIMAX_API_KEY", perplexity: "PERPLEXITY_API_KEY" };
export const PERPLEXITY_AGENT_BASE_URL = "https://api.perplexity.ai/v1";
// This bounded profile uses the model in Perplexity's documented custom-function loop.
// Model choices and transport changes require explicit configuration; no fallback exists.
const PERPLEXITY_COMMAND_MODELS = new Set(["openai/gpt-5.6-sol"]);
export const APPROVED_COMPARISON_COMMAND = "Compare Fall Creek and Costa in China";
const APPROVED_TOOL_NAMES = new Set(["search_catalog", "show_portfolio_comparison", "show_company_summary", "show_evidence_detail", "show_related_developments", "show_geography_connections", "show_sensory_demo"]);
const ALLOWED_METHODS = new Set(["info", "agent/run", "agent/connect", "agent/stop"]);
export function readConfig(env = process.env) {
  const model = String(env.BIOS_COPILOT_MODEL || "").trim();
  const separator = model.search(/[:/]/);
  const provider = model.slice(0, separator).toLowerCase();
  const modelId = separator < 0 ? "" : model.slice(separator + 1);
  if (!modelId || !PROVIDER_KEYS[provider]) throw new Error("Configure BIOS_COPILOT_MODEL with an explicit supported provider:model.");
  if (provider === "perplexity" && !PERPLEXITY_COMMAND_MODELS.has(modelId))
    throw new Error("Choose the explicitly supported Perplexity command model openai/gpt-5.6-sol.");
  const credentialName = PROVIDER_KEYS[provider];
  if (!env[credentialName]) throw new Error(`Configure the selected provider's ${credentialName} on the runtime server.`);
  const token = String(env.BIOS_COPILOT_RUNTIME_TOKEN || "");
  if (token.length < 32) throw new Error("BIOS_COPILOT_RUNTIME_TOKEN must contain at least 32 characters.");
  const port = Number(env.BIOS_COPILOT_PORT || 8200);
  if (!Number.isInteger(port) || port < 1024 || port > 65535) throw new Error("Choose a valid BIOS_COPILOT_PORT.");
  return {
    model, provider, sdkModel: provider === "perplexity" ? `openai:${modelId}` : model,
    token, port,
    // Resolve only this profile's existing key at invocation time. Never copy
    // PERPLEXITY_API_KEY into OPENAI_API_KEY or persist it in another record.
    readCredential: () => env[credentialName],
    creditFreeOnly: () => ["1", "true", "yes"].includes(String(env.BIOS_RESEARCH_CREDIT_FREE_ONLY || "").trim().toLowerCase()),
    allowApprovedComparison: () => env.BIOS_COPILOT_ALLOW_PAID_COMPARISON === "1",
  };
}
export function createCommandPermission(config) {
  let approvedMessageId = null;
  let approvedThreadId = null;
  let requests = 0;
  return envelope => {
    if (envelope.method !== "agent/run") return { allowed: true };
    const comparisonPermit = config.provider === "perplexity" && config.allowApprovedComparison?.();
    if (!comparisonPermit) return config.creditFreeOnly?.()
      ? { allowed: false, error: "Paid commands are paused by the credit-free setting. The investigation controls remain available." }
      : { allowed: true };
    let body = envelope.body;
    if (typeof body === "string") { try { body = JSON.parse(body); } catch { body = null; } }
    const users = Array.isArray(body?.messages) ? body.messages.filter(message => message?.role === "user") : [];
    const user = users[0];
    const text = typeof user?.content === "string" ? user.content : Array.isArray(user?.content)
      && user.content.every(part => part?.type === "text" && typeof part.text === "string") ? user.content.map(part => part.text).join("") : "";
    const normalized = text.trim().replace(/\s+/g, " ").toLowerCase();
    const validId = value => typeof value === "string" && value.length > 0 && value.length <= 180;
    const tools = Array.isArray(body?.tools) ? body.tools : [];
    if (users.length !== 1 || normalized !== APPROVED_COMPARISON_COMMAND.toLowerCase()
      || !validId(user?.id) || !validId(body?.threadId)
      || tools.some(tool => !APPROVED_TOOL_NAMES.has(tool?.name) || tool.type && tool.type !== "function"))
      return { allowed: false, error: "This runtime is limited to the one approved comparison and its investigation tools." };
    if (approvedMessageId !== null && (approvedMessageId !== user.id || approvedThreadId !== body.threadId))
      return { allowed: false, error: "The approved comparison has already been used in this runtime." };
    if (requests >= 8) return { allowed: false, error: "The approved comparison request limit has been reached." };
    approvedMessageId = user.id;
    approvedThreadId = body.threadId;
    requests += 1;
    return { allowed: true };
  };
}
export function sdkAgentSettings(config) {
  const apiKey = typeof config.readCredential === "function" ? config.readCredential() : config.apiKey;
  if (!apiKey) throw new Error("The selected provider credential is unavailable.");
  if (config.provider === "perplexity") {
    // Dedicated runtime process: fixed Perplexity destination, Responses wire
    // protocol, and no OpenAI-account key. A custom host otherwise defaults to
    // Chat Completions in the installed SDK, so the API override is required.
    process.env.OPENAI_BASE_URL = PERPLEXITY_AGENT_BASE_URL;
    process.env.COPILOTKIT_OPENAI_API = "responses";
  }
  return {
    model: config.sdkModel || config.model, apiKey,
    ...(config.provider === "perplexity" ? { providerOptions: { openai: { store: false } } } : {}),
  };
}
const SAFE_ERROR_NAMES = new Set(["AI_APICallError", "AI_TypeValidationError", "AI_InvalidResponseDataError", "AI_NoOutputGeneratedError", "AI_LoadAPIKeyError", "AI_RetryError", "TypeError", "AbortError", "CommandToolBoundaryError"]);
const SAFE_PROVIDER_CODES = new Set(["insufficient_quota", "invalid_api_key", "rate_limit_exceeded", "invalid_request_error", "invalid_model", "model_not_found", "authentication_error", "permission_denied", "context_length_exceeded", "invalid_json_schema", "server_error", "unsupported_tool"]);
const SAFE_ERROR_PARAMS = new Set(["model", "input", "instructions", "max_output_tokens", "stream", "tools", "store", "previous_response_id", "tool_choice"]);
const safeRequestId = headers => {
  const value = headers?.["x-request-id"] ?? headers?.["request-id"];
  return typeof value === "string" && (/^req_[A-Za-z0-9_-]{8,100}$/.test(value) || /^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/i.test(value)) ? value : undefined;
};
export function safeFailureDiagnostic(error) {
  const name = SAFE_ERROR_NAMES.has(error?.name) ? error.name : "RuntimeError";
  const status = error?.statusCode ?? error?.status;
  const httpStatus = Number.isInteger(status) && status >= 100 && status <= 599 ? status : undefined;
  const code = error?.data?.error?.code ?? error?.code;
  const param = error?.data?.error?.param;
  const requestId = safeRequestId(error?.responseHeaders);
  return { type: "command_provider_error", terminal_event: "RUN_ERROR", category: httpStatus ? "provider_http" : name.includes("Validation") || name.includes("ResponseData") ? "provider_stream_validation"
    : name === "AbortError" ? "cancelled" : name === "TypeError" ? "provider_network_or_type" : "provider_or_sdk", name,
    ...(httpStatus ? { http_status: httpStatus } : {}), provider_code: SAFE_PROVIDER_CODES.has(code) ? code : "unclassified",
    ...(SAFE_ERROR_PARAMS.has(param) ? { param } : {}), ...(requestId ? { request_id: requestId } : {}) };
}
const safeUsage = usage => {
  const values = { input_tokens: usage?.inputTokens?.total ?? usage?.inputTokens, output_tokens: usage?.outputTokens?.total ?? usage?.outputTokens,
    cached_input_tokens: usage?.inputTokens?.cacheRead ?? usage?.cachedInputTokens, reasoning_tokens: usage?.outputTokens?.reasoning ?? usage?.reasoningTokens };
  return Object.fromEntries(Object.entries(values).filter(([, value]) => Number.isSafeInteger(value) && value >= 0));
};
/** The supported custom LanguageModel seam keeps SDK-injected state tools away from the provider. */
export function restrictCommandModel(model, reportDiagnostic = () => {}) {
  const report = value => { try { reportDiagnostic(value); } catch { /* Diagnostics cannot alter command behavior. */ } };
  const assertTool = part => {
    if (["tool-call", "tool-input-start"].includes(part?.type) && !APPROVED_TOOL_NAMES.has(part.toolName))
      throw Object.assign(new Error("The command provider returned an unsupported tool."), { name: "CommandToolBoundaryError", code: "unsupported_tool" });
  };
  const invoke = async (method, options) => {
    const tools = options.tools?.filter(tool => tool.type === "function" && APPROVED_TOOL_NAMES.has(tool.name));
    report({ type: "command_model_request", tool_count: tools?.length ?? 0, excluded_tool_count: (options.tools?.length ?? 0) - (tools?.length ?? 0) });
    try {
      const result = await model[method]({ ...options, tools });
      if (!result.stream) { for (const part of result.content ?? []) assertTool(part); return result; }
      const requestId = safeRequestId(result.response?.headers);
      report({ type: "command_provider_response", ...(requestId ? { request_id: requestId } : {}) });
      const reader = result.stream.getReader();
      return { ...result, stream: new ReadableStream({
        async pull(controller) {
          try {
            const { done, value } = await reader.read();
            if (done) { controller.close(); return; }
            assertTool(value);
            if (value.type === "error") report(safeFailureDiagnostic(value.error));
            if (value.type === "finish") report({ type: "command_provider_finish", terminal_event: "PROVIDER_FINISH", ...safeUsage(value.usage) });
            controller.enqueue(value);
          } catch (error) { report(safeFailureDiagnostic(error)); controller.error(error); }
        },
        cancel(reason) { return reader.cancel(reason); },
      }) };
    } catch (error) { report(safeFailureDiagnostic(error)); throw error; }
  };
  return new Proxy(model, { get(target, property) {
    if (property === "doStream" || property === "doGenerate") return options => invoke(property, options);
    const value = Reflect.get(target, property, target);
    return typeof value === "function" ? value.bind(target) : value;
  } });
}
function tokenMatches(expected, received) {
  const left = Buffer.from(expected), right = Buffer.from(received || "");
  return left.length === right.length && timingSafeEqual(left, right);
}
const PROMPT = `You operate Berry OS's existing investigation using its registered frontend tools.
Use search_catalog to resolve names to canonical IDs. Never invent IDs, facts, scores, roles, geography, sources or tool arguments containing factual payloads.
Look up one company or country name per search. A unique exact_name or exact_alias result identifies an authored catalog name match, not evidence approval. Prefer that unique exact match over substring results. If several exact matches remain, ask for clarification rather than guessing. Search results alone do not apply a view change.
For "Compare Fall Creek and Costa in China", find the canonical company IDs and China geography ID, then call show_portfolio_comparison with those company IDs and that explicitly requested country. Preserve berry and other state.
Use the exact read-only investigation revision for every tool. If stale or unavailable, ask the user to resubmit; never increment a revision yourself. Apply one composite view change per user command.
The controlled components are CompanySummary, PortfolioComparison, GeographyConnections, RelatedDevelopments, EvidenceDetail, and SensoryDemo. They update the shared analytical field or coordinated detail area. Do not create a duplicate comparison or analytical report in chat.
No research, acquisition, saving, canonical edits, publication approval, claim approval or ranking tools are available. Unsupported requests must be declined clearly. Publication review does not approve claims, and company presence does not imply variety growing. Synthetic demo specimens are never measured commercial cultivar performance.
Only acknowledge the performed action briefly. Do not produce uncited factual or strategic synthesis.`;

export function createGuardedHandler(config) {
  const commandPermission = createCommandPermission(config);
  return async request => {
    const headers = { "Cache-Control": "private, no-store", "Content-Type": "application/json" };
    if (!tokenMatches(config.token, request.headers.get("X-Berry-Runtime-Token")))
      return new Response(JSON.stringify({ error: "Unauthorized" }), { status: 401, headers });
    if (request.method !== "POST" || new URL(request.url).pathname !== "/copilot")
      return new Response(JSON.stringify({ error: "Unsupported runtime route" }), { status: 404, headers });
    if (Number(request.headers.get("content-length") || 0) > 512_000)
      return new Response(JSON.stringify({ error: "Command context exceeds the supported size" }), { status: 413, headers });
    let envelope;
    try { envelope = await request.clone().json(); }
    catch { return new Response(JSON.stringify({ error: "Expected a runtime JSON envelope" }), { status: 400, headers }); }
    if (!ALLOWED_METHODS.has(envelope?.method))
      return new Response(JSON.stringify({ error: "This runtime supports explicit investigation commands only" }), { status: 403, headers });
    const permission = commandPermission(envelope);
    if (!permission.allowed) return new Response(JSON.stringify({ error: permission.error }), { status: 403, headers });
    let agentSettings;
    try { agentSettings = sdkAgentSettings(config); }
    catch { return new Response(JSON.stringify({ error: "The selected command provider is unavailable." }), { status: 503, headers }); }
    const { BuiltInAgent, CopilotRuntime, createCopilotRuntimeHandler, resolveModel } = await import("@copilotkit/runtime/v2");
    // A new runner for each request retains no cross-account server history.
    // The browser supplies its bounded page-session conversation on each run.
    const runtime = new CopilotRuntime({ agents: { default: new BuiltInAgent({
      ...agentSettings, model: restrictCommandModel(resolveModel(agentSettings.model, agentSettings.apiKey), config.reportDiagnostic), prompt: PROMPT, maxSteps: 4,
      maxOutputTokens: 450, maxRetries: 0, urlDownload: "disabled", overridableProperties: [],
    }) } });
    const handler = createCopilotRuntimeHandler({ runtime, basePath: "/copilot", mode: "single-route", cors: false });
    return handler(request);
  };
}

export async function startServer(env = process.env) {
  const config = readConfig(env);
  // SDK transport errors can include request bodies. This dedicated process
  // reports a bounded failure marker; prompts, tool payloads and keys stay out
  // of operator logs. Structured token usage remains in RUN_FINISHED events.
  const originalConsoleError = console.error;
  config.reportDiagnostic = event => originalConsoleError.call(console, `Berry command diagnostic: ${JSON.stringify(event)}`);
  const safeConsoleError = () => originalConsoleError.call(console, "Berry command runtime could not complete a request.");
  console.error = safeConsoleError;
  const { createCopilotNodeHandler } = await import("@copilotkit/runtime/v2/node");
  const listener = createCopilotNodeHandler(createGuardedHandler(config));
  const server = createServer((request, response) => {
    Promise.resolve(listener(request, response)).catch(() => {
      if (!response.headersSent) response.writeHead(502, { "Content-Type": "application/json" });
      response.end(JSON.stringify({ error: "The configured runtime could not complete this request" }));
    });
  });
  server.once("close", () => { if (console.error === safeConsoleError) console.error = originalConsoleError; });
  server.listen(config.port, "127.0.0.1");
  return server;
}
if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  startServer().then(() => console.log("Berry command runtime listening on loopback.")).catch(error => {
    console.error(error.message); process.exitCode = 1;
  });
}
