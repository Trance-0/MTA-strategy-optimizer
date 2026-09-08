/** Verify draft preservation, error focus and retained-history interactions. */
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { computed, effectScope, nextTick, ref, watch } from "vue";

function deferred() {
  let resolve, reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}

function control(t, name, exposed, overrides = {}) {
  const selectedDatasetId = ref("ds_a");
  const plans = ref([]), runs = ref([]);
  const environment = { computed, nextTick, ref, watch,
    defineProps: () => ({ stage: "" }), IS_STATIC: false,
    useDashboard: () => ({ selectedDatasetId, selectDataset: async id => { selectedDatasetId.value = id; } }),
    useWorkbench: () => ({ plans, runs, selectedDataset: ref({ scope: { currency: "USD" } }),
      error: ref(""), runtime: ref({ storageAvailable: true, executionAvailable: true }),
      refresh: async () => {}, refreshDatasets: async () => {} }),
    saveBudgetPlan: async body => ({ ...body, id: "plan_a", revision: 1 }),
    startWorkbenchRun: async () => ({ id: "run_new" }),
    fetchWorkbenchRun: async id => runs.value.find(run => run.id === id),
    validateDataset: async () => ({}), registerDataset: async () => ({ id: "ds_new" }),
    ...overrides,
  };
  // Execute the production handlers with Vue refs/watchers, not copied logic.
  const source = readFileSync(new URL(`../src/components/${name}.vue`, import.meta.url), "utf8")
    .split("<script setup>")[1].split("</script>")[0]
    .replace(/import[\s\S]*?from\s+["'][^"']+["'];/g, "");
  const scope = effectScope();
  t.after(() => scope.stop());
  const api = scope.run(() => new Function(...Object.keys(environment), `${source}\nreturn { ${exposed} };`)(...Object.values(environment)));
  return { ...api, selectedDatasetId, plans, runs };
}

test("unsaved plan remains bound to its original dataset until explicit discard", async t => {
  const calls = [];
  const v = control(t, "BudgetPlans", "form, formDataset, mismatch, editing, save, reset", {
    saveBudgetPlan: async body => { calls.push(body); return { ...body, id: "plan_a", revision: 1 }; },
  });
  v.form.value.name = "Keep my draft";
  v.form.value.totalBudget = 42;
  v.selectedDatasetId.value = "ds_b";
  await nextTick();
  assert.equal(v.formDataset.value, "ds_a");
  assert.equal(v.mismatch.value, true);
  await v.save();
  assert.equal(calls.length, 0);
  assert.equal(v.form.value.name, "Keep my draft");
  v.selectedDatasetId.value = "ds_a";
  await nextTick();
  assert.equal(v.mismatch.value, false);
  assert.equal(v.form.value.totalBudget, 42);
  v.selectedDatasetId.value = "ds_b";
  await nextTick();
  v.reset();
  assert.equal(v.formDataset.value, "ds_b");
  assert.equal(v.form.value.name, "");
});

test("late save after A → B → A cannot replace a newer draft or clear its busy state", async t => {
  const requests = [];
  const v = control(t, "BudgetPlans", "form, editing, busy, message, save", {
    saveBudgetPlan: body => { const request = deferred(); requests.push({ ...request, body }); return request.promise; },
  });
  v.form.value.name = "Original";
  const first = v.save();
  v.selectedDatasetId.value = "ds_b";
  await nextTick();
  v.selectedDatasetId.value = "ds_a";
  await nextTick();
  v.form.value.name = "Current draft";
  const second = v.save();
  requests[0].resolve({ ...requests[0].body, id: "plan_old", revision: 1 });
  await first;
  assert.equal(v.form.value.name, "Current draft");
  assert.equal(v.busy.value, true);
  assert.equal(v.editing.value, null);
  requests[1].resolve({ ...requests[1].body, id: "plan_new", revision: 1 });
  await second;
  assert.equal(v.editing.value.id, "plan_new");
  assert.equal(v.busy.value, false);
});

test("conflict retains local fields and focuses error; latest replaces only on request", async t => {
  const v = control(t, "BudgetPlans", "form, editing, edit, conflict, errorSummary, save, reloadRevision", {
    saveBudgetPlan: async () => { throw Object.assign(new Error("Plan changed"), { status: 409 }); },
  });
  const original = { id: "plan_a", datasetId: "ds_a", revision: 1, name: "Saved", totalBudget: 100, budgetUsagePolicy: "SPEND_UP_TO_BUDGET" };
  v.edit(original);
  v.form.value.name = "My unsaved changes";
  let focuses = 0;
  v.errorSummary.value = { focus: () => { focuses += 1; } };
  await v.save();
  assert.equal(v.conflict.value, true);
  assert.equal(v.form.value.name, "My unsaved changes");
  assert.equal(v.editing.value.revision, 1);
  assert.equal(focuses, 1);
  v.plans.value = [{ ...original, revision: 2, name: "Other editor's revision" }];
  assert.equal(v.form.value.name, "My unsaved changes");
  await v.reloadRevision();
  assert.equal(v.form.value.name, "Other editor's revision");
  assert.equal(v.editing.value.revision, 2);
  assert.equal(v.conflict.value, false);
});

test("run uses saved plan revision instead of unsaved budget fields", async t => {
  const calls = [];
  const v = control(t, "BudgetPlans", "form, run", { startWorkbenchRun: async body => { calls.push(body); return { id: "run_new" }; } });
  v.form.value.totalBudget = 9999;
  await v.run({ id: "plan_a", revision: 2, totalBudget: 50 });
  assert.deepEqual(calls, [{ datasetId: "ds_a", stage: "optimization", planId: "plan_a", revision: 2 }]);
});

test("invalid import retains file/name, focuses row issues and publishes nothing", async t => {
  let published = 0, focused = 0;
  const v = control(t, "DatasetImport", "name, files, error, issues, errorSummary, preview, submit", {
    validateDataset: async () => { throw Object.assign(new Error("Invalid counts"), { issues: [{ field: "clicks", row: 1, message: "Must be nonnegative" }] }); },
    registerDataset: async () => { published += 1; },
  });
  v.name.value = "External input";
  const file = new Blob(["[]"], { type: "application/json" });
  v.files.value = { performance: file };
  v.errorSummary.value = { focus: () => { focused += 1; } };
  await v.submit();
  assert.equal(v.name.value, "External input");
  assert.equal(v.files.value.performance, file);
  assert.equal(v.issues.value[0].field, "clicks");
  assert.equal(v.preview.value, null);
  assert.equal(v.selectedDatasetId.value, "ds_a");
  assert.equal(published, 0);
  assert.equal(focused, 1);
});

test("history pages records and labels older selection without changing dataset", async t => {
  const v = control(t, "RunHistory", "page, pageRows, pageCount, selected, selectionLabel, state, inspect");
  v.runs.value = Array.from({ length: 45 }, (_, i) => ({ id: `run_${i}`, stage: "optimization", state: i === 44 ? "interrupted" : "succeeded", createdAt: "2026-09-08T01:00:00Z" }));
  assert.equal(v.pageCount.value, 3);
  assert.equal(v.pageRows.value.length, 20);
  v.page.value = 3;
  assert.equal(v.pageRows.value.length, 5);
  await v.inspect("run_21");
  assert.equal(v.selectionLabel.value, "Historical record");
  assert.equal(v.selectedDatasetId.value, "ds_a");
  await v.inspect("run_0");
  assert.equal(v.selectionLabel.value, "Latest successful result");
  v.state.value = "interrupted";
  await nextTick();
  assert.equal(v.page.value, 1);
  assert.equal(v.pageRows.value[0].id, "run_44");
});
