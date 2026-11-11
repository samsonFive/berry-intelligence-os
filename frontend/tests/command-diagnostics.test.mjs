import { strict as assert } from 'node:assert';
import { test } from 'node:test';
import { toolMetadata, sanitizeRunEnvelope } from '../e2e/command-diagnostics.mjs';

test('only approved selector labels and argument shape survive', () => {
  const value = toolMetadata('search_catalog', { revision: 0, kind: 'company', query: 'Fall Creek', secret: 'never-retain-me', ids: ['private-value'] });
  assert.deepEqual(value, { tool_name: 'search_catalog', argument_keys: ['ids', 'kind', 'query', 'revision'], revision: 0, kind: 'company', query: 'fall creek' });
  assert.ok(!JSON.stringify(value).includes('never-retain-me'));
  assert.ok(!JSON.stringify(value).includes('private-value'));
  assert.equal(toolMetadata('search_catalog', { query: 'private prose' }).query, '[outside approved selector labels]');
  assert.deepEqual(toolMetadata('arbitrary_tool', { query: 'private prose' }), { tool_name: 'unrecognized' });
});

test('continuations retain tool result counts and fixed codes without content', () => {
  const value = sanitizeRunEnvelope({ method: 'agent/run', body: { tools: [{ name: 'search_catalog' }, { name: 'private-tool-name' }], messages: [
    { role: 'user', content: 'discard user prose' },
    { role: 'assistant', content: 'discard model prose', toolCalls: [{ id: 'opaque', function: { name: 'search_catalog', arguments: JSON.stringify({ revision: 2, kind: 'company', query: 'Costa' }) } }] },
    { role: 'tool', toolCallId: 'opaque', content: JSON.stringify({ results: [{ id: 'private-id', label: 'private label' }], internal: 'private metadata' }) },
    { role: 'tool', content: JSON.stringify({ ok: false, code: 'stale_command', message: 'private error prose' }) },
  ] } });
  assert.deepEqual(value.tool_results, [{ tool_name: 'search_catalog', result_count: 1 }, { tool_name: 'unrecognized', ok: false, code: 'stale_command' }]);
  assert.deepEqual(value.registered_tools, ['search_catalog']);
  assert.equal(value.unknown_tool_count, 1);
  assert.ok(!JSON.stringify(value).includes('private'));
  assert.ok(!JSON.stringify(value).includes('discard'));
  assert.equal(sanitizeRunEnvelope({ method: 'info' }), null);
});
