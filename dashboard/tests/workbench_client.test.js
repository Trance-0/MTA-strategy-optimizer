/** Check real client transport identities and static refusal without a browser. */
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
async function client(isStatic) {
  const source = readFileSync(new URL("../src/api/client.js", import.meta.url), "utf8")
    .replace('import.meta.env.VITE_STATIC_BUILD === "true"', String(isStatic))
    .replace('"../pages.js"', JSON.stringify(new URL("../src/pages.js", import.meta.url).href));
  return import(`data:text/javascript;base64,${Buffer.from(source).toString("base64")}`);
}
test("resource request carries selected identity; errors retain bounded validation fields", async () => {
  const original = globalThis.fetch;
  const seen = [];
  globalThis.fetch = async (url, options) => {
    seen.push({ url, options });
    return new Response(JSON.stringify({ adsDaily: [{ cost: 5 }] }), { headers: { "Content-Type": "application/json" } });
  };
  try {
    const api = await client(false);
    const result = await api.fetchDashboardResource("performance", null, null, "ds_selected");
    assert.equal(new URL(seen[0].url, "http://local").searchParams.get("datasetId"), "ds_selected");
    assert.equal(result.adsDaily[0].cost, 5);
    await api.fetchBudgetPlans("");
    await api.fetchWorkbenchRuns();
    assert.equal(seen[1].url, "/api/workbench/plans");
    assert.equal(seen[2].url, "/api/workbench/runs");
    await api.fetchBudgetPlans("ds_selected");
    assert.equal(new URL(seen[3].url, "http://local").searchParams.get("datasetId"), "ds_selected");
    globalThis.fetch = async () => new Response(JSON.stringify({ error: "invalid_dataset", message: "Missing performance", issues: [{ path: "performance", message: "Required" }] }), { status: 400 });
    await assert.rejects(api.registerDataset({}), error => error.status === 400 && error.issues[0].path === "performance");
  } finally { globalThis.fetch = original; }
});
test("static dataset, plan and run operations cannot send network mutations", async () => {
  const original = globalThis.fetch;
  let calls = 0;
  globalThis.fetch = async () => { calls += 1; throw new Error("Unexpected request"); };
  try {
    const api = await client(true);
    assert.equal((await api.fetchDatasets()).available, false);
    for (const action of [() => api.registerDataset({}), () => api.validateDataset({}), () => api.saveBudgetPlan({}), () => api.startWorkbenchRun({}), () => api.stopWorkbenchRun("run_x")]) await assert.rejects(action(), /live backend/);
    assert.equal(calls, 0);
  } finally { globalThis.fetch = original; }
});
