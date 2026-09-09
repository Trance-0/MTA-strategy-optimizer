/** Exercise workbench context races and independent read/write capability failures. */
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { computed, ref, shallowRef } from "vue";

function deferred() {
  let resolve, reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}

function store(overrides = {}) {
  const selectedDatasetId = ref("ds_a");
  const env = { computed, ref, shallowRef,
    useDashboard: () => ({ selectedDatasetId }),
    fetchDatasets: async () => ({ datasets: [], available: true }),
    fetchBudgetPlans: async () => ({ plans: [] }),
    fetchWorkbenchRuns: async () => ({ runs: [] }), ...overrides };
  // Fresh module state per fixture prevents unrelated tests sharing a catalogue.
  const source = readFileSync(new URL("../src/lib/useWorkbench.js", import.meta.url), "utf8")
    .replace(/import[\s\S]*?from\s+["'][^"']+["'];/g, "")
    .replace("export function useWorkbench", "function useWorkbench");
  const state = new Function(...Object.keys(env), `${source}\nreturn useWorkbench();`)(...Object.values(env));
  return { ...state, selectedDatasetId };
}

const ready = { storageAvailable: true, executionAvailable: true };

test("cold direct route exposes first refresh after guarded lists were read empty", async () => {
  const plans = deferred(), runs = deferred();
  const state = store({ fetchBudgetPlans: () => plans.promise, fetchWorkbenchRuns: () => runs.promise });
  // A route renders before its mounted refresh while the persisted id is set.
  assert.deepEqual(state.plans.value, []);
  assert.deepEqual(state.runs.value, []);
  assert.equal(state.error.value, "");
  const refresh = state.refresh();
  plans.resolve({ plans: [{ id: "plan_retained" }] });
  runs.resolve({ runs: [{ id: "run_retained" }], ...ready });
  await refresh;
  assert.deepEqual(state.plans.value, [{ id: "plan_retained" }]);
  assert.deepEqual(state.runs.value, [{ id: "run_retained" }]);
  assert.equal(state.selectedDatasetId.value, "ds_a");
});

test("cold direct route exposes a first-refresh error and then explicit recovery", async () => {
  let offline = true;
  const state = store({ fetchBudgetPlans: async () => {
    if (offline) throw new Error("Saved plans unavailable");
    return { plans: [{ id: "plan_recovered" }] };
  }, fetchWorkbenchRuns: async () => ({ runs: [{ id: "run_recovered" }], ...ready }) });
  assert.equal(state.error.value, "");
  assert.deepEqual(state.plans.value, []);
  assert.deepEqual(state.runs.value, []);
  await state.refresh();
  assert.equal(state.error.value, "Saved plans unavailable");
  offline = false;
  await state.refresh();
  assert.equal(state.error.value, "");
  assert.deepEqual(state.plans.value, [{ id: "plan_recovered" }]);
  assert.deepEqual(state.runs.value, [{ id: "run_recovered" }]);
});

test("late dataset lists and errors cannot replace a newer catalogue", async () => {
  const requests = [];
  const state = store({ fetchDatasets: () => { const request = deferred(); requests.push(request); return request.promise; } });
  const first = state.refreshDatasets();
  const second = state.refreshDatasets();
  requests[1].resolve({ datasets: [{ id: "ds_b" }], available: true });
  await second;
  requests[0].reject(new Error("Old connection failed"));
  await first;
  assert.deepEqual(state.datasets.value, [{ id: "ds_b" }]);
  assert.equal(state.catalogueError.value, "");
  assert.equal(state.available.value, true);
});

test("old plan/run success cannot merge across an A → B → A selection", async () => {
  const planRequests = [], runRequests = [];
  const request = list => id => { const pending = deferred(); list.push({ id, ...pending }); return pending.promise; };
  const state = store({ fetchBudgetPlans: request(planRequests), fetchWorkbenchRuns: request(runRequests) });
  const first = state.refresh();
  state.selectedDatasetId.value = "ds_b";
  assert.deepEqual(state.plans.value, []);
  const second = state.refresh();
  state.selectedDatasetId.value = "ds_a";
  const third = state.refresh();
  planRequests[2].resolve({ plans: [{ id: "plan_new" }] });
  runRequests[2].resolve({ runs: [{ id: "run_new" }], ...ready });
  await third;
  planRequests[0].resolve({ plans: [{ id: "plan_old" }] });
  runRequests[0].resolve({ runs: [{ id: "run_old" }], storageAvailable: false });
  planRequests[1].reject(new Error("Old B request failed"));
  runRequests[1].resolve({ runs: [] });
  await Promise.all([first, second]);
  assert.deepEqual(state.plans.value, [{ id: "plan_new" }]);
  assert.deepEqual(state.runs.value, [{ id: "run_new" }]);
  assert.equal(state.error.value, "");
  assert.equal(state.loading.value, false);
  assert.equal(state.runtime.value.executionAvailable, true);
});

test("catalogue readability is independent of runtime write and execution access", async () => {
  const state = store({ fetchBudgetPlans: async () => ({ plans: [], storageAvailable: false,
    storageReason: "Runtime is read-only", executionAvailable: false, executionReason: "Execution disabled" }) });
  await Promise.all([state.refreshDatasets(), state.refreshCapabilities()]);
  assert.equal(state.available.value, true);
  assert.equal(state.runtime.value.storageAvailable, false);
  assert.equal(state.runtime.value.storageReason, "Runtime is read-only");
  assert.equal(state.runtime.value.executionAvailable, false);
  assert.equal(state.runtime.value.executionReason, "Execution disabled");
});

test("failed refresh disables dependent writes until successful explicit recovery", async () => {
  let offline = false;
  const state = store({
    fetchBudgetPlans: async () => { if (offline) throw new Error("Connection unavailable"); return { plans: [], ...ready }; },
    fetchWorkbenchRuns: async () => ({ runs: [], ...ready }),
  });
  await state.refresh();
  assert.equal(state.runtime.value.executionAvailable, true);
  offline = true;
  await state.refresh();
  assert.equal(state.error.value, "Connection unavailable");
  assert.equal(state.runtime.value.executionAvailable, false);
  assert.equal(state.runtime.value.storageAvailable, false);
  offline = false;
  await state.refresh();
  assert.equal(state.error.value, "");
  assert.equal(state.runtime.value.executionAvailable, true);
});
