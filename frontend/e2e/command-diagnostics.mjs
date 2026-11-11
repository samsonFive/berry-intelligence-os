/** Receipt metadata only. Never return source bodies, tool arguments or model text. */
const tools = new Set(['search_catalog', 'show_portfolio_comparison', 'show_company_summary', 'show_evidence_detail', 'show_related_developments', 'show_geography_connections', 'show_sensory_demo']);
const queries = new Set(['fall creek', 'costa', 'china']);
const codes = new Set(['applied', 'stale_command', 'unavailable', 'invalid_selection', 'invalid_context', 'unavailable_identity', 'invalid_id', 'cancelled', 'no_action']);
const argumentKeys = new Set(['revision', 'kind', 'query', 'ids', 'countries', 'id', 'type']);
const object = value => typeof value === 'string' ? (() => { try { return JSON.parse(value); } catch { return {}; } })() : value ?? {};

export function toolMetadata(name, raw) {
  if (!tools.has(name)) return { tool_name: 'unrecognized' };
  const args = object(raw);
  const result = { tool_name: name, argument_keys: Object.keys(args).filter(key => argumentKeys.has(key)).sort() };
  if (Number.isSafeInteger(args.revision) && args.revision >= 0) result.revision = args.revision;
  if (['company', 'variety', 'geography'].includes(args.kind)) result.kind = args.kind;
  if (typeof args.query === 'string') {
    const query = args.query.trim().toLowerCase();
    if (queries.has(query)) result.query = query;
    else result.query = '[outside approved selector labels]';
  }
  return result;
}

export function sanitizeRunEnvelope(envelope) {
  if (envelope?.method !== 'agent/run') return null;
  const body = object(envelope.body);
  const messages = Array.isArray(body.messages) ? body.messages : [];
  const calls = new Map();
  for (const message of messages) for (const call of message.toolCalls ?? []) {
    const name = call.function?.name ?? call.name;
    if (tools.has(name)) calls.set(call.id, name);
  }
  return {
    registered_tools: (body.tools ?? []).filter(tool => tools.has(tool.name)).map(tool => tool.name),
    unknown_tool_count: (body.tools ?? []).filter(tool => !tools.has(tool.name)).length,
    message_role_counts: Object.fromEntries(['user', 'assistant', 'tool', 'system'].map(role => [role, messages.filter(message => message.role === role).length])),
    tool_calls: messages.flatMap(message => (message.toolCalls ?? []).map(call => toolMetadata(call.function?.name ?? call.name, call.function?.arguments ?? call.arguments))),
    tool_results: messages.filter(message => message.role === 'tool').map(message => {
      const value = object(message.content);
      return { tool_name: calls.get(message.toolCallId ?? message.tool_call_id) ?? 'unrecognized',
        ...(typeof value.ok === 'boolean' ? { ok: value.ok } : {}),
        ...(codes.has(value.code) ? { code: value.code } : {}),
        ...(Array.isArray(value.results) ? { result_count: value.results.length } : {}) };
    }),
  };
}

/** Serialized into Chromium. The response clone leaves the SDK stream intact. */
export function installCommandDiagnostics() {
  const names = new Set(['search_catalog', 'show_portfolio_comparison', 'show_company_summary', 'show_evidence_detail', 'show_related_developments', 'show_geography_connections', 'show_sensory_demo']);
  const labels = new Set(['fall creek', 'costa', 'china']);
  const keys = new Set(['revision', 'kind', 'query', 'ids', 'countries', 'id', 'type']);
  const originalFetch = window.fetch;
  window.__berryCommandWire = { event_counts: {}, tool_calls: [], lookups: [], terminals: [], read_errors: 0 };
  window.fetch = async function (...args) {
    const response = await originalFetch.apply(this, args);
    const address = typeof args[0] === 'string' ? args[0] : args[0]?.url;
    if (!address) return response;
    const url = new URL(address, location.href);
    if (url.origin !== location.origin) return response;
    if (url.pathname === '/api/investigations/v1/options' && labels.has((url.searchParams.get('q') ?? '').trim().toLowerCase())) {
      void response.clone().json().then(body => {
        const data = body.data ?? {};
        window.__berryCommandWire.lookups.push({ query: url.searchParams.get('q').trim().toLowerCase(), status: response.status,
          counts: Object.fromEntries(['companies', 'varieties', 'countries'].map(key => [key, Array.isArray(data[key]) ? data[key].length : 0])) });
      }).catch(() => { window.__berryCommandWire.read_errors++; });
    }
    if (!url.pathname.startsWith('/api/investigations/v1/copilot') || !(response.headers.get('content-type') ?? '').includes('text/event-stream')) return response;
    void (async () => {
      const reader = response.clone().body?.getReader(); if (!reader) return;
      const decoder = new TextDecoder(); let remainder = ''; const calls = new Map();
      for (;;) {
        const { done, value } = await reader.read(); if (done) break;
        const lines = (remainder + decoder.decode(value, { stream: true })).split(/\r?\n/); remainder = lines.pop() ?? '';
        for (const line of lines) {
          if (!line.startsWith('data:')) continue;
          try {
            const event = JSON.parse(line.slice(5).trim());
            if (!/^[A-Z_]{1,60}$/.test(event.type ?? '')) continue;
            const receipt = window.__berryCommandWire;
            receipt.event_counts[event.type] = (receipt.event_counts[event.type] ?? 0) + 1;
            if (event.type === 'TOOL_CALL_START') calls.set(event.toolCallId, { name: names.has(event.toolCallName) ? event.toolCallName : 'unrecognized', raw: '' });
            if (event.type === 'TOOL_CALL_ARGS' && calls.has(event.toolCallId)) {
              const call = calls.get(event.toolCallId); if (call.raw.length < 16000 && typeof event.delta === 'string') call.raw += event.delta;
            }
            if (event.type === 'TOOL_CALL_END' && calls.has(event.toolCallId)) {
              const call = calls.get(event.toolCallId); calls.delete(event.toolCallId);
              const row = { tool_name: call.name };
              try {
                const values = JSON.parse(call.raw);
                row.argument_keys = Object.keys(values).filter(key => keys.has(key)).sort();
                if (Number.isSafeInteger(values.revision) && values.revision >= 0) row.revision = values.revision;
                if (['company', 'variety', 'geography'].includes(values.kind)) row.kind = values.kind;
                if (typeof values.query === 'string') row.query = labels.has(values.query.trim().toLowerCase()) ? values.query.trim().toLowerCase() : '[outside approved selector labels]';
              } catch { row.arguments_parseable = false; }
              receipt.tool_calls.push(row);
            }
            if (!['RUN_ERROR', 'RUN_FINISHED'].includes(event.type)) continue;
            const entries = event.usage ?? event.result?.usage ?? event.data?.usage;
            const usage = Array.isArray(entries) ? entries.slice(0, 20).map(row => {
              const record = {};
              for (const key of ['provider', 'model']) if (typeof row?.[key] === 'string' && /^[A-Za-z0-9/_.:-]{1,120}$/.test(row[key])) record[key] = row[key];
              for (const key of ['inputTokens', 'outputTokens', 'totalTokens', 'reasoningTokens', 'cachedInputTokens', 'cacheReadInputTokens', 'cacheWriteInputTokens']) if (Number.isSafeInteger(row?.[key]) && row[key] >= 0) record[key] = row[key];
              return record;
            }) : [];
            receipt.terminals.push({ type: event.type, usage, ...(event.type === 'RUN_ERROR' ? { message_present: typeof event.message === 'string' } : {}) });
          } catch { /* Event bodies and unrecognized payloads never become diagnostics. */ }
        }
      }
    })().catch(() => { window.__berryCommandWire.read_errors++; });
    return response;
  };
}
