/** Exercise the actual resource store under delayed, reordered window responses. */
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { isProxy } from "vue";

const moduleUrl = (source) => `data:text/javascript;base64,${Buffer.from(source).toString("base64")}`;

test("window changes discard stale responses and revisit fetches the correct rows", async () => {
  const clientUrl = moduleUrl(`export const pending = [];
    export function fetchDashboardResource(resource, progress, window) {
      return new Promise((resolve, reject) => pending.push({resource, window, resolve, reject}));
    }
    export async function reloadData() {}`);
  const client = await import(clientUrl);
  const source = readFileSync(new URL("../src/lib/useDashboard.js", import.meta.url), "utf8")
    .replace('"vue"', JSON.stringify(import.meta.resolve("vue")))
    .replace('"../api/client.js"', JSON.stringify(clientUrl))
    .replace('"../pages.js"', JSON.stringify(new URL("../src/pages.js", import.meta.url).href));
  const { useDashboard } = await import(moduleUrl(source));
  const store = useDashboard();
  const resource = "research-campaign-history";
  const rows = (tag) => ({ simulationResearch: { history: [{ tag }] } });
  const initial = store.ensureResources([resource]);
  client.pending[0].resolve(rows("default"));
  await initial;
  assert.equal(isProxy(store.data.value.simulationResearch.history[0]), false);
  const older = store.setHistoryWindow({ start: "2026-01-01", end: "2026-01-31" });
  const newer = store.setHistoryWindow({ start: "2026-02-01", end: "2026-02-28" });
  client.pending[2].resolve(rows("February"));
  await newer;
  client.pending[1].resolve(rows("January"));
  await older;
  assert.equal(store.data.value.simulationResearch.history[0].tag, "February");
  assert.equal(store.isLoaded([resource]), true);
  assert.equal(store.loadingProgress.value.visible, false);
  const revisit = store.setHistoryWindow({ start: "2026-01-01", end: "2026-01-31" });
  assert.equal(client.pending.length, 4);
  assert.equal(store.isLoaded([resource]), false);
  client.pending[3].resolve(rows("January refreshed"));
  await revisit;
  assert.equal(store.data.value.simulationResearch.history[0].tag, "January refreshed");
});

test("dataset changes discard late non-windowed results, errors and reloads", async () => {
  const clientUrl = moduleUrl(`export const pending = [];
    export function fetchDashboardResource(resource, progress, window, datasetId) {
      return new Promise((resolve, reject) => pending.push({resource, datasetId, progress, resolve, reject}));
    }
    export async function reloadData() {}`);
  const client = await import(clientUrl);
  const source = readFileSync(new URL("../src/lib/useDashboard.js", import.meta.url), "utf8")
    .replace('"vue"', JSON.stringify(import.meta.resolve("vue")))
    .replace('"../api/client.js"', JSON.stringify(clientUrl))
    .replace('"../pages.js"', JSON.stringify(new URL("../src/pages.js", import.meta.url).href));
  const store = (await import(moduleUrl(source))).useDashboard();
  const initial = store.ensureResources(["performance"]).catch(() => null);
  const first = store.selectDataset("ds_a");
  const second = store.selectDataset("ds_b");
  assert.equal(store.data.value.adsDaily.length, 0);
  client.pending[2].resolve({ adsDaily: [{ cost: 27 }] });
  await second;
  client.pending[1].resolve({ adsDaily: [{ cost: 999 }] });
  client.pending[0].reject(new Error("old database failed"));
  await Promise.all([first, initial]);
  assert.equal(store.data.value.adsDaily[0].cost, 27);
  assert.equal(store.errorFor(["performance"]), null);
  assert.equal(store.loadingProgress.value.visible, false);
  assert.equal(client.pending[2].datasetId, "ds_b");
});
