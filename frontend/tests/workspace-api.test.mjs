import assert from 'node:assert/strict';
import test from 'node:test';
import { EMPTY_CONTEXT } from '../src/contracts/investigation.ts';
import { listSaved, saveInvestigation, downloadOutput, WorkspaceRequestError } from '../src/features/workspaces/api.ts';

test('a save conflict remains explicit and cannot be treated as a successful revision', async () => {
  const original = globalThis.fetch;
  globalThis.fetch = async () => new Response(JSON.stringify({ detail: 'This saved view changed in another window.' }), {
    status: 409, headers: { 'content-type': 'application/json' },
  });
  try {
    await assert.rejects(saveInvestigation({ name: 'China', context: EMPTY_CONTEXT, id: 'lview-existing', revision: 1, save_as_new: false }),
      error => error instanceof WorkspaceRequestError && error.status === 409 && /another window/.test(error.message));
  } finally { globalThis.fetch = original; }
});

test('a saved row cannot redirect the private client to an external destination', async () => {
  const original = globalThis.fetch;
  globalThis.fetch = async () => new Response(JSON.stringify({ api_v: 1, data: [{ id: 'view-a', name: 'A', revision: 1,
    is_investigation: true, href: '//external.invalid/app/landscape', filters: {} }] }), { headers: { 'content-type': 'application/json' } });
  try { await assert.rejects(listSaved(), error => error instanceof WorkspaceRequestError && error.status === 502); }
  finally { globalThis.fetch = original; }
});

test('only a real PDF bound to the reviewed content hash becomes a download', async () => {
  const original = globalThis.fetch;
  const hash = 'a'.repeat(64), selection = { context: EMPTY_CONTEXT, section_ids: ['readout'], include_demo: false };
  let payload;
  try {
    globalThis.fetch = async (url, options) => {
      payload = JSON.parse(options.body);
      return new Response('%PDF-1.7\nreviewed output', { headers: { 'content-type': 'application/pdf', 'x-investigation-content-hash': 'b'.repeat(64) } });
    };
    await assert.rejects(downloadOutput(selection, hash), error => error.status === 502);
    assert.equal(payload.expected_content_hash, hash);
    assert.equal(payload.include_demo, false);
    globalThis.fetch = async () => new Response('<html>Sign in</html>', { headers: { 'content-type': 'application/pdf', 'x-investigation-content-hash': hash } });
    await assert.rejects(downloadOutput(selection, hash), error => error.status === 502);
    globalThis.fetch = async () => new Response('%PDF-1.7\nreviewed output', { headers: { 'content-type': 'application/pdf', 'x-investigation-content-hash': hash } });
    assert.equal((await downloadOutput(selection, hash)).type, 'application/pdf');
  } finally { globalThis.fetch = original; }
});
