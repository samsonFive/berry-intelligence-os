import { test } from "node:test";
import assert from "node:assert/strict";
import { createGuardedHandler, readConfig } from "../server.mjs";

const config = { model: "openai:test-only-model", apiKey: "test-only", token: "test-only-runtime-token-with-32-characters", port: 8200 };
test("configuration requires an explicit provider/model and key, with no fallback", () => {
  assert.throws(() => readConfig({}), /BIOS_COPILOT_MODEL/);
  assert.throws(() => readConfig({ BIOS_COPILOT_MODEL: "unknown:model" }), /explicit supported/);
  assert.throws(() => readConfig({ BIOS_COPILOT_MODEL: "openai:chosen-model" }), /OPENAI_API_KEY/);
  assert.equal(readConfig({ BIOS_COPILOT_MODEL: config.model, OPENAI_API_KEY: config.apiKey, BIOS_COPILOT_RUNTIME_TOKEN: config.token }).model, config.model);
});
test("runtime rejects missing/wrong token before importing SDK or invoking a provider", async () => {
  const handler = createGuardedHandler(config);
  assert.equal((await handler(new Request("http://127.0.0.1:8200/copilot", { method: "POST", body: '{}' }))).status, 401);
});
test("thread/resource/acquisition methods are unavailable", async () => {
  const handler = createGuardedHandler(config);
  for (const method of ["resource/request", "threads/list", "threads/clear", "transcribe"]) {
    const response = await handler(new Request("http://127.0.0.1:8200/copilot", {
      method: "POST", headers: { "X-Berry-Runtime-Token": config.token }, body: JSON.stringify({ method }),
    }));
    assert.equal(response.status, 403);
  }
});
