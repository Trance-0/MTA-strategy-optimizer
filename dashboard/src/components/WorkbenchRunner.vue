<script setup>
/** Operate one registered stage while preserving dataset and result identity. */
import { computed, onBeforeUnmount, ref, watch } from "vue";
import { useDashboard } from "../lib/useDashboard.js";
import { useWorkbench } from "../lib/useWorkbench.js";
import { IS_STATIC, startWorkbenchRun, fetchWorkbenchRun, stopWorkbenchRun } from "../api/client.js";
const props = defineProps({ stage: { type: String, required: true } });
const { selectedDatasetId, reload } = useDashboard();
const { selectedDataset, runs, refresh, runtime } = useWorkbench();
const record = ref(null);
const error = ref("");
const busy = ref(false);
const totalBudget = ref(1000);
const policy = ref("SPEND_UP_TO_BUDGET");
const target = ref("");
let generation = 0;
let timer;
const active = computed(() => ["queued", "running", "stopping"].includes(record.value?.state));
const capability = computed(() => selectedDataset.value?.capabilities?.[props.stage]);
const targets = computed(() => runs.value.filter(run => run.stage === "optimization" && run.state === "succeeded"));
const allowed = computed(() => !IS_STATIC && runtime.value.executionAvailable && Boolean(selectedDatasetId.value) &&
  (props.stage === "evaluation" ? targets.value.some(run => run.id === target.value) : capability.value?.available));
function schedule(token) {
  clearTimeout(timer);
  if (token === generation && active.value) timer = setTimeout(() => poll(token), 900);
}
async function poll(token) {
  try {
    const next = await fetchWorkbenchRun(record.value.id);
    if (token !== generation) return;
    record.value = next; error.value = "";
    if (!active.value) await refresh();
  } catch (cause) { if (token === generation) error.value = `Run status could not be read: ${cause.message}`; }
  finally { schedule(token); }
}
async function start() {
  const token = generation;
  busy.value = true; error.value = "";
  try {
    const next = await startWorkbenchRun({ datasetId: selectedDatasetId.value, stage: props.stage,
      ...(props.stage === "optimization" ? { totalBudget: totalBudget.value, budgetUsagePolicy: policy.value } : {}),
      ...(props.stage === "evaluation" ? { strategyRunId: target.value } : {}),
    });
    if (token !== generation) return;
    record.value = next; schedule(token);
  } catch (cause) { if (token === generation) error.value = cause.message; }
  finally { if (token === generation) busy.value = false; }
}
async function stop() {
  const token = generation;
  try { const next = await stopWorkbenchRun(record.value.id); if (token === generation) { record.value = next; schedule(token); } }
  catch (cause) { if (token === generation) error.value = cause.message; }
}
async function viewResults() {
  try { await reload(); } catch (cause) { error.value = cause.message; }
}
watch([selectedDatasetId, () => props.stage], () => {
  generation += 1; clearTimeout(timer); record.value = null; error.value = ""; busy.value = false; target.value = ""; refresh();
}, { immediate: true });
onBeforeUnmount(() => { generation += 1; clearTimeout(timer); });
</script>
<template>
  <article class="card">
    <div class="card-head"><h2>Run {{ stage }}</h2><span class="sub">{{ selectedDataset?.name }}</span></div>
    <div class="card-body">
      <p>Inputs are frozen from this dataset. Historical chart filters do not refit the model. <a href="#/budget/plans">Save a reusable budget plan</a></p>
      <div v-if="stage === 'optimization'" class="workbench-toolbar">
        <div class="field"><label for="run-total">Total budget · {{ selectedDataset?.scope?.currency }}</label><input id="run-total" v-model.number="totalBudget" type="number" min="0.01" step="0.01" :disabled="active || busy" /></div>
        <div class="field"><label for="run-policy">Budget policy</label><select id="run-policy" v-model="policy" :disabled="active || busy"><option value="SPEND_UP_TO_BUDGET">Spend up to budget</option><option value="SPEND_FULL_BUDGET">Spend full budget</option></select></div>
      </div>
      <div v-if="stage === 'evaluation'" class="field"><label for="evaluation-target">Completed optimization to evaluate</label><select id="evaluation-target" v-model="target" :disabled="active || busy"><option value="">Select a strategy run</option><option v-for="run in targets" :key="run.id" :value="run.id">{{ run.id }} · {{ run.createdAt }}</option></select></div>
      <p v-if="!allowed" class="notice">{{ !runtime.executionAvailable ? runtime.executionReason : stage === 'evaluation' ? 'Choose a completed optimization from this dataset. No default strategy is used.' : capability?.reason || 'This stage is unavailable for the selected data.' }}</p>
      <div class="rec-actions"><button class="btn primary" :disabled="!allowed || active || busy" @click="start">{{ record && !active ? 'Run again with new identity' : 'Start run' }}</button><button class="btn" :disabled="!active || record?.state === 'stopping'" @click="stop">Stop</button><button v-if="record?.state === 'succeeded'" class="btn" @click="viewResults">Refresh latest dataset results</button></div>
      <p v-if="error" role="alert">{{ error }}</p>
      <div v-if="record" role="status"><p>{{ record.id }} · {{ record.state }} · {{ record.phase }}</p><p v-if="record.state === 'succeeded'">Result saved under this run identity. Refresh loads the latest successful dataset results, which may belong to a newer run. Inspect this exact record and its artifacts in run history.</p><details><summary>Execution log and parameters</summary><pre class="workbench-json">{{ JSON.stringify(record, null, 2) }}</pre></details></div>
    </div>
  </article>
</template>
