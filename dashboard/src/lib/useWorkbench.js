/** Shared catalogue and context-scoped lists for immutable workbench records. */
import { computed, ref, shallowRef } from "vue";
import { fetchDatasets, fetchBudgetPlans, fetchWorkbenchRuns } from "../api/client.js";
import { useDashboard } from "./useDashboard.js";

const datasets = shallowRef([]);
const plans = shallowRef([]);
const runs = shallowRef([]);
const error = ref("");
const catalogueError = ref("");
const available = ref(false);
const reason = ref("");
const loading = ref(false);
const runtime = ref({ storageAvailable: false, executionAvailable: false, executionReason: "Checking model execution availability." });
let catalogueGeneration = 0;
let generation = 0;
// Scope itself must invalidate guarded computed values after a cold route read.
const scope = ref("");

async function refreshDatasets() {
  const token = ++catalogueGeneration;
  try {
    const result = await fetchDatasets();
    if (token !== catalogueGeneration) return;
    datasets.value = result.datasets ?? [];
    available.value = result.available !== false;
    reason.value = result.reason ?? "";
    catalogueError.value = "";
  } catch (cause) {
    if (token !== catalogueGeneration) return;
    catalogueError.value = cause.message;
    available.value = false;
  }
}

async function refreshCapabilities() {
  try { const result = await fetchBudgetPlans(""); runtime.value = {
    storageAvailable: result.storageAvailable === true, storageReason: result.storageReason ?? "", executionAvailable: result.executionAvailable === true,
    executionReason: result.executionReason ?? "Model execution is unavailable in this deployment.",
  }; } catch (cause) { runtime.value = { storageAvailable: false, executionAvailable: false, executionReason: cause.message }; }
}

async function refresh() {
  const id = useDashboard().selectedDatasetId.value;
  const token = ++generation;
  scope.value = id;
  plans.value = [];
  runs.value = [];
  error.value = "";
  if (!id) { loading.value = false; return; }
  loading.value = true;
  try {
    const [planResult, runResult] = await Promise.all([fetchBudgetPlans(id), fetchWorkbenchRuns(id)]);
    if (token !== generation || id !== useDashboard().selectedDatasetId.value) return;
    plans.value = planResult.plans ?? [];
    runs.value = runResult.runs ?? [];
    runtime.value = { storageAvailable: runResult.storageAvailable === true, storageReason: runResult.storageReason ?? "", executionAvailable: runResult.executionAvailable === true, executionReason: runResult.executionReason ?? "" };
  } catch (cause) {
    if (token === generation && id === useDashboard().selectedDatasetId.value) {
      error.value = cause.message;
      // Revoke stale write capability after a current read fails; an older
      // context's failure must not disable a newly selected dataset.
      runtime.value = { storageAvailable: false, storageReason: cause.message,
        executionAvailable: false, executionReason: cause.message };
    }
  } finally {
    if (token === generation) loading.value = false;
  }
}

export function useWorkbench() {
  const { selectedDatasetId } = useDashboard();
  return {
    datasets: computed(() => datasets.value),
    selectedDataset: computed(() => datasets.value.find(item => item.id === selectedDatasetId.value) ?? null),
    plans: computed(() => scope.value === selectedDatasetId.value ? plans.value : []),
    runs: computed(() => scope.value === selectedDatasetId.value ? runs.value : []),
    error: computed(() => scope.value === selectedDatasetId.value ? error.value : ""),
    catalogueError, available, reason, loading, runtime, refresh, refreshDatasets, refreshCapabilities,
  };
}
