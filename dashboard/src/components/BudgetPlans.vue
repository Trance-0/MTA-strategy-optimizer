<script setup>
/** Persist budget revisions and run exactly the selected saved options. */
import { computed, nextTick, ref, watch } from "vue";
import { useDashboard } from "../lib/useDashboard.js";
import { useWorkbench } from "../lib/useWorkbench.js";
import { IS_STATIC, saveBudgetPlan, startWorkbenchRun } from "../api/client.js";
const { selectedDatasetId, selectDataset } = useDashboard();
const { plans, selectedDataset, error: loadError, refresh, runtime } = useWorkbench();
const form = ref({ name: "", totalBudget: 1000, budgetUsagePolicy: "SPEND_UP_TO_BUDGET" });
const editing = ref(null);
const busy = ref(false);
const error = ref("");
const message = ref("");
const formDataset = ref(selectedDatasetId.value);
const conflict = ref(false);
const errorSummary = ref(null);
const mismatch = computed(() => formDataset.value !== selectedDatasetId.value);
let generation = 0;
function reset() { formDataset.value = selectedDatasetId.value; conflict.value = false; editing.value = null; form.value = { name: "", totalBudget: 1000, budgetUsagePolicy: "SPEND_UP_TO_BUDGET" }; error.value = ""; }
function edit(plan) { formDataset.value = plan.datasetId; conflict.value = false; editing.value = plan; form.value = { name: plan.name, totalBudget: plan.totalBudget, budgetUsagePolicy: plan.budgetUsagePolicy }; error.value = ""; }
watch(selectedDatasetId, () => { generation += 1; busy.value = false; message.value = ""; refresh(); }, { immediate: true });
async function reloadRevision() {
  const token = generation;
  await refresh();
  if (token !== generation) return;
  const latest = plans.value.find(plan => plan.id === editing.value?.id);
  if (latest) edit(latest);
}
async function save() {
  if (mismatch.value || busy.value) return;
  const token = generation;
  const id = selectedDatasetId.value;
  busy.value = true; error.value = ""; message.value = "";
  try {
    const saved = await saveBudgetPlan({ ...form.value, datasetId: id, ...(editing.value ? { revision: editing.value.revision } : {}) }, editing.value?.id);
    if (token !== generation) return;
    edit(saved); message.value = `Saved revision ${saved.revision}.`; await refresh();
  } catch (cause) { if (token === generation) { error.value = cause.message; conflict.value = cause.status === 409; await nextTick(); errorSummary.value?.focus(); } }
  finally { if (token === generation) busy.value = false; }
}
async function run(plan) {
  if (busy.value) return;
  const token = generation;
  const id = selectedDatasetId.value;
  busy.value = true; error.value = "";
  try {
    const result = await startWorkbenchRun({ datasetId: id, stage: "optimization", planId: plan.id, revision: plan.revision });
    if (token !== generation) return;
    message.value = `Run ${result.id} queued using saved revision ${plan.revision}.`; await refresh();
  } catch (cause) { if (token === generation) { error.value = cause.message; conflict.value = cause.status === 409; await nextTick(); errorSummary.value?.focus(); } }
  finally { if (token === generation) busy.value = false; }
}
</script>
<template>
  <section class="card">
    <div class="card-head"><h2>Budget plans</h2><button class="btn small" @click="refresh">Refresh saved plans</button></div>
    <div class="card-body">
      <p>Save a budget for this dataset, then run its saved revision. Entity drafts are not connected to these model runs.</p>
      <p v-if="!selectedDatasetId || IS_STATIC" class="notice">Select a registered dataset on a live backend to save plans.</p>
      <p v-if="mismatch" class="notice">This draft remains bound to {{ formDataset || 'the previous legacy context' }}. Return to its dataset to save, or choose New plan to discard it and start for this dataset. <button class="btn small" @click="selectDataset(formDataset)">Return to draft dataset</button></p>
      <form @submit.prevent="save">
        <fieldset :disabled="!selectedDatasetId || IS_STATIC || busy || !runtime.storageAvailable">
          <div class="workbench-toolbar">
            <div class="field"><label for="plan-name">Plan name</label><input id="plan-name" :aria-describedby="error ? 'plan-errors' : undefined" v-model="form.name" required maxlength="120" /></div>
            <div class="field"><label for="plan-budget">Total budget · {{ mismatch ? 'Original dataset currency' : selectedDataset?.scope?.currency }}</label><input id="plan-budget" :aria-describedby="error ? 'plan-errors' : undefined" v-model.number="form.totalBudget" type="number" min="0.01" step="0.01" required /></div>
            <div class="field"><label for="plan-policy">Budget policy</label><select id="plan-policy" :aria-describedby="error ? 'plan-errors' : undefined" v-model="form.budgetUsagePolicy"><option value="SPEND_UP_TO_BUDGET">Spend up to budget</option><option value="SPEND_FULL_BUDGET">Spend full budget</option></select></div>
          </div>
          <p v-if="editing">Editing {{ editing.name }} · expected revision {{ editing.revision }}</p>
          <button class="btn primary" type="submit" :disabled="mismatch">{{ editing ? 'Save new revision' : 'Create plan' }}</button>
          <button class="btn" type="button" @click="reset">New plan</button>
        </fieldset>
      </form>
      <p v-if="error || loadError" id="plan-errors" ref="errorSummary" tabindex="-1" role="alert">{{ error || loadError }} Your draft has been retained.</p>
      <button v-if="conflict && !mismatch" class="btn" :disabled="busy" @click="reloadRevision">Load latest revision (replace draft)</button>
      <p v-if="message" role="status">{{ message }} <a href="#/log/provenance">View run history</a></p>
      <p v-if="!plans.length" class="caption">No saved plans for this dataset.</p>
      <article v-for="plan in plans" :key="plan.id" class="panel">
        <h3>{{ plan.name }} · Revision {{ plan.revision }}</h3>
        <p>{{ plan.totalBudget }} {{ selectedDataset?.scope?.currency }} · {{ plan.budgetUsagePolicy }}</p>
        <button class="btn small" :disabled="busy" @click="edit(plan)">Edit revision</button>
        <button class="btn primary small" :disabled="busy || !runtime.executionAvailable || !selectedDataset?.capabilities?.optimization?.available" @click="run(plan)">Run saved revision {{ plan.revision }}</button>
      </article>
      <p v-if="selectedDataset && !selectedDataset.capabilities?.optimization?.available" class="notice">{{ selectedDataset.capabilities?.optimization?.reason }}</p>
      <p v-if="!runtime.executionAvailable" class="caption">{{ runtime.executionReason }}</p>
    </div>
  </section>
</template>
