/** Test-only Responses transport. Every outbound fetch is intercepted locally.
 * Refuses to load with a real key, or without the explicit offline fixture flag.
 */
import assert from 'node:assert/strict';
assert.equal(process.env.BERRY_FULLSTACK_OFFLINE, '1', 'This preload is only for the offline full-stack fixture');
assert.equal(process.env.PERPLEXITY_API_KEY, 'synthetic-fullstack-offline-key', 'Never run this fixture with a real provider credential');
assert.equal(process.env.BIOS_COPILOT_MODEL, 'perplexity:openai/gpt-5.6-sol');
for (const name of ['OPENAI_API_KEY', 'ANTHROPIC_API_KEY', 'GOOGLE_API_KEY', 'MINIMAX_API_KEY']) assert.equal(process.env[name], undefined);
const endpoint = 'https://api.perplexity.ai/v1/responses';
const approved = new Set(['search_catalog','show_portfolio_comparison','show_company_summary','show_evidence_detail','show_related_developments','show_geography_connections','show_sensory_demo']);
const expectedIds = ['company-fall-creek-farm-and-nursery', 'company-costa-group-holdings'];
let requests = 0;
const receipt = value => console.log(`Berry offline provider fixture: ${JSON.stringify(value)}`);

function providerEvents(stage) {
  const responseId = `resp-offline-${stage}`;
  const base = { id: responseId, created_at: 0, model: 'openai/gpt-5.6-sol' };
  const rows = [{ type: 'response.created', response: { ...base, status: 'in_progress' } }];
  const selected = stage === 1 ? [
    ['offline-search-fall', 'search_catalog', { revision: 0, kind: 'company', query: 'Fall Creek' }],
    ['offline-search-costa', 'search_catalog', { revision: 0, kind: 'company', query: 'Costa' }],
    ['offline-search-china', 'search_catalog', { revision: 0, kind: 'geography', query: 'China' }],
  ] : stage === 2 ? [['offline-compare', 'show_portfolio_comparison', { revision: 0, kind: 'company', ids: expectedIds, countries: ['geography-china'] }]] : [];
  const calls = selected.map(([callId, name, args], outputIndex) => ({ outputIndex,
    item: { type: 'function_call', id: `fc-${callId}`, call_id: callId, name, arguments: JSON.stringify(args), status: 'completed' } }));
  for (const { item, outputIndex } of calls) rows.push({ type: 'response.output_item.added', output_index: outputIndex, item: { ...item, arguments: '', status: 'in_progress' } });
  for (const half of [0, 1]) for (const { item, outputIndex } of calls) {
    const middle = Math.floor(item.arguments.length / 2);
    rows.push({ type: 'response.function_call_arguments.delta', item_id: item.id, output_index: outputIndex,
      delta: half === 0 ? item.arguments.slice(0, middle) : item.arguments.slice(middle) });
  }
  for (const { item, outputIndex } of calls) rows.push(
    { type: 'response.function_call_arguments.done', item_id: item.id, output_index: outputIndex, arguments: item.arguments },
    { type: 'response.output_item.done', output_index: outputIndex, item });
  const message = { type: 'message', id: 'msg-offline-ack', role: 'assistant', status: 'completed', content: [{ type: 'output_text', text: 'Comparison opened.', annotations: [] }] };
  if (stage === 3) rows.push({ type: 'response.output_item.added', output_index: 0, item: { ...message, content: [], status: 'in_progress' } },
    { type: 'response.output_text.delta', item_id: message.id, output_index: 0, content_index: 0, delta: 'Comparison opened.' },
    { type: 'response.output_item.done', output_index: 0, item: message });
  rows.push({ type: 'response.completed', response: { ...base, status: 'completed', output: stage === 3 ? [message] : calls.map(row => row.item),
    usage: { input_tokens: 100, output_tokens: 30, total_tokens: 130, input_tokens_details: { cached_tokens: 0 }, output_tokens_details: { reasoning_tokens: 0 } } } });
  return rows;
}

globalThis.fetch = async (input, init = {}) => {
  const address = typeof input === 'string' ? input : input.url;
  if (address !== endpoint) {
    receipt({ type: 'blocked_outbound_fetch' });
    throw new Error('The offline fixture rejects every unexpected outbound fetch');
  }
  assert.equal(new Headers(init.headers ?? (input instanceof Request ? input.headers : {})).get('authorization'), 'Bearer synthetic-fullstack-offline-key');
  const body = JSON.parse(init.body);
  assert.equal(body.model, 'openai/gpt-5.6-sol'); assert.equal(body.stream, true); assert.equal(body.store, false);
  assert.equal(body.tools.length, 7);
  assert.ok(body.tools.every(tool => tool.type === 'function' && approved.has(tool.name)));
  const outputs = (body.input ?? []).filter(row => row.type === 'function_call_output');
  const comparison = outputs.find(row => row.call_id === 'offline-compare');
  const stage = comparison ? 3 : outputs.length ? 2 : 1;
  requests++;
  assert.equal(requests, stage, 'The real runtime must resume each frontend tool batch exactly once');
  if (stage === 2) {
    assert.equal(outputs.length, 3);
    const results = outputs.map(row => JSON.parse(row.output));
    assert.ok(results.every(row => row.results?.length > 0));
    assert.ok(results.some(row => row.results.some(item => item.id === expectedIds[0])));
    assert.ok(results.some(row => row.results.some(item => item.id === expectedIds[1])));
    assert.ok(results.some(row => row.results.some(item => item.id === 'geography-china')));
    const byCall = new Map(outputs.map(row => [row.call_id, JSON.parse(row.output)]));
    for (const [call, id, label, basis] of [
      ['offline-search-fall', expectedIds[0], 'Fall Creek', 'exact_alias'],
      ['offline-search-costa', expectedIds[1], 'Costa', 'exact_alias'],
      ['offline-search-china', 'geography-china', 'China', 'exact_name'],
    ]) {
      const result = byCall.get(call);
      assert.equal(result.exact_match_count, 1, 'The emitted client must disclose a unique authored exact match');
      assert.equal(result.results[0].id, id);
      assert.equal(result.results[0].match_basis, basis);
      assert.equal(result.results[0].matched_label.toLowerCase(), label.toLowerCase());
      assert.equal(result.returned_count, result.results.length);
      assert.equal(typeof result.results_limited, 'boolean');
    }
  }
  if (stage === 3) assert.equal(JSON.parse(comparison.output).code, 'applied');
  receipt({ type: 'mock_responses_request', stage, tool_count: body.tools.length, function_output_count: outputs.length,
    ...(stage === 2 ? { lookup_exact_match_counts: [1,1,1], lookup_match_basis: ['exact_alias','exact_alias','exact_name'] } : {}),
    ...(stage === 3 ? { comparison_result: 'applied' } : {}), real_provider_requests: 0 });
  const encoder = new TextEncoder();
  const events = providerEvents(stage);
  return new Response(new ReadableStream({ async start(controller) {
    for (const event of events) {
      controller.enqueue(encoder.encode(`event: ${event.type}\ndata: ${JSON.stringify(event)}\n\n`));
      await new Promise(resolve => setTimeout(resolve, 2));
    }
    controller.close();
  } }), { headers: { 'content-type': 'text/event-stream', 'x-request-id': `req_offlinefixture000${stage}` } });
};
receipt({ type: 'offline_fetch_guard_installed', real_provider_requests: 0 });
