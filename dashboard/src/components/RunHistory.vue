<script setup>
/** Inspect retained records without changing the current result or dataset. */
import { computed, ref, watch } from "vue";
import { useDashboard } from "../lib/useDashboard.js";
import { useWorkbench } from "../lib/useWorkbench.js";
import { fetchWorkbenchRun, startWorkbenchRun, workbenchDownloadUrl } from "../api/client.js";
import EvaluationReport from "./EvaluationReport.vue";
const props = defineProps({ stage: { type: String, default: "" } });
const { selectedDatasetId } = useDashboard();
const { runs, refresh, error: loadError, runtime } = useWorkbench();
const selected = ref(null);
const state = ref("");
const from = ref("");
const to = ref("");
const error = ref("");
const busy = ref(false);
let generation = 0;
const page = ref(1);
const pageSize = 20;
const visible = computed(() => runs.value.filter(run => (!props.stage || run.stage === props.stage) && (!state.value || run.state === state.value) && (!from.value || run.createdAt.slice(0, 10) >= from.value) && (!to.value || run.createdAt.slice(0, 10) <= to.value)));
const pageCount = computed(() => Math.max(1, Math.ceil(visible.value.length / pageSize)));
const pageRows = computed(() => visible.value.slice((page.value - 1) * pageSize, page.value * pageSize));
const latestSuccess = computed(() => runs.value.find(run => run.stage === selected.value?.stage && run.state === "succeeded"));
const selectionLabel = computed(() => selected.value?.id === latestSuccess.value?.id ? "Latest successful result" : ["queued", "running", "stopping"].includes(selected.value?.state) ? "Active run record" : "Historical record");
watch([state, from, to, selectedDatasetId, () => props.stage], () => { page.value = 1; });
watch(pageCount, value => { page.value = Math.min(page.value, value); });
const filenames = computed(() => (selected.value?.artifacts ?? []).map(item => typeof item === "string" ? item : item.filename ?? item.name));
watch([selectedDatasetId, () => props.stage], () => { generation += 1; selected.value = null; error.value = ""; busy.value = false; refresh(); }, { immediate: true });
async function inspect(id) {
  if (busy.value) return;
  const token = ++generation;
  try { const result = await fetchWorkbenchRun(id); if (token === generation) selected.value = result; }
  catch (cause) { if (token === generation) error.value = cause.message; }
}
async function retry() {
  if (busy.value || !runtime.value.executionAvailable) return;
  busy.value = true; error.value = "";
  const old = selected.value;
  const token = ++generation;
  try {
    const result = await startWorkbenchRun({ datasetId: old.datasetId, stage: old.stage, options: old.options, planId: old.planId, revision: old.revision ?? old.planRevision, strategyRunId: old.strategyRunId });
    if (token !== generation) return;
    selected.value = result; await refresh();
  } catch (cause) { if (token === generation) error.value = cause.message; }
  finally { if (token === generation) busy.value = false; }
}
</script>
<template>
  <article class="card">
    <div class="card-head"><h2>Retained run history</h2><button class="btn small" @click="refresh">Refresh runs</button></div>
    <div class="card-body">
      <p>Inspecting an earlier record keeps your current dataset and displayed results unchanged.</p>
      <div class="workbench-toolbar">
        <div class="field"><label for="history-run-state">Run state</label><select id="history-run-state" v-model="state"><option value="">All states</option><option v-for="value in ['queued','running','stopping','succeeded','failed','stopped','interrupted']" :key="value">{{ value }}</option></select></div>
        <div class="field"><label for="run-history-from">Created from</label><input id="run-history-from" v-model="from" type="date" /></div>
        <div class="field"><label for="run-history-to">Created to</label><input id="run-history-to" v-model="to" type="date" /></div>
      </div>
      <p v-if="error || loadError" role="alert">{{ error || loadError }}</p>
      <p v-if="!visible.length" class="caption">No retained runs match this selection.</p>
      <div v-for="run in pageRows" :key="run.id" class="kv run-history-row"><span>{{ run.stage }} · {{ run.state }} · {{ run.createdAt }}</span><button class="btn link small" :disabled="busy" @click="inspect(run.id)">{{ run.id }}</button></div>
      <div v-if="visible.length" class="rec-actions"><button class="btn small" :disabled="page <= 1" @click="page -= 1">Previous runs</button><span>Page {{ page }} of {{ pageCount }} · {{ visible.length }} matching runs</span><button class="btn small" :disabled="page >= pageCount" @click="page += 1">Next runs</button></div>
      <section v-if="selected" class="panel">
        <p class="caption">{{ selectionLabel }}</p>
        <h3>{{ selected.id }} · {{ selected.state }}</h3>
        <p>Dataset {{ selected.datasetId }} · Input fingerprint {{ selected.digest ?? selected.datasetDigest }} · Plan revision {{ selected.revision ?? selected.planRevision ?? 'No saved plan' }}</p>
        <p v-if="selected.strategyRunId">Evaluates strategy run {{ selected.strategyRunId }}</p>
        <button v-if="['failed','stopped','interrupted'].includes(selected.state)" class="btn" :disabled="busy || !runtime.executionAvailable" @click="retry">Retry as a new run</button>
        <div v-if="selected.state === 'succeeded'" class="rec-actions"><a v-for="filename in filenames" :key="filename" class="btn small" :href="workbenchDownloadUrl(selected.id, filename)">Download {{ filename }}</a></div>
        <EvaluationReport v-if="selected.stage === 'evaluation' && selected.result" :report="selected.result.strategyEvaluation ?? selected.result" :run="selected" />
        <details><summary>Inputs, options, state and result</summary><pre class="workbench-json">{{ JSON.stringify(selected, null, 2) }}</pre></details>
      </section>
    </div>
  </article>
</template>
