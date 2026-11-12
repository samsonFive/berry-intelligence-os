import { test } from "node:test";
import assert from "node:assert/strict";
import { EMPTY_CONTEXT } from "../../contracts/investigation.ts";
import { compareCommand } from "./command-actions.ts";

function harness() {
  let revision = 7;
  const actions = [];
  return {
    actions, setRevision: value => { revision = value; },
    host: { context: { ...EMPTY_CONTEXT, focus: "variety-kept", cohort_varieties: "variety-kept" },
      getRevision: () => revision, dispatch: action => { actions.push(action); revision += 1; return true; },
      read: async () => ({ data: { invalid_ids: [], overflow_ids: [] } }),
    },
  };
}
test("comparison dispatch uses the same selector state and preserves independent focus/cohort", async () => {
  const { host, actions } = harness();
  const result = await compareCommand(host, { revision: 7, kind: "company", ids: ["company-fall-creek-farm-and-nursery", "company-costa-group-holdings"], countries: ["geography-china"] });
  assert.equal(result.ok, true);
  assert.equal(actions.length, 1);
  assert.equal(actions[0].type, "replaceContext");
  assert.equal(actions[0].context.lens, "comparison");
  assert.equal(actions[0].context.countries, "geography-china");
  assert.equal(actions[0].context.focus, "variety-kept");
  assert.equal(actions[0].context.cohort_varieties, "variety-kept");
  assert.equal(actions[0].expectedRevision, 7);
});
test("late backend/model result cannot replace a newer direct selection", async () => {
  const { host, actions, setRevision } = harness();
  host.read = async () => { setRevision(8); return { data: { invalid_ids: [], overflow_ids: [] } }; };
  const result = await compareCommand(host, { revision: 7, kind: "company", ids: ["company-a"] });
  assert.equal(result.code, "stale_command"); assert.equal(actions.length, 0);
});
test("unresolved identities and unsupported cohort sizes never dispatch", async () => {
  const { host, actions } = harness();
  host.read = async () => ({ data: { invalid_ids: ["company-missing"], overflow_ids: [] } });
  assert.equal((await compareCommand(host, { revision: 7, kind: "company", ids: ["company-missing"] })).ok, false);
  assert.equal((await compareCommand(host, { revision: 7, kind: "variety", ids: ["v-a", "v-b", "v-c", "v-d", "v-e"] })).code, "invalid_selection");
  assert.equal(actions.length, 0);
});
