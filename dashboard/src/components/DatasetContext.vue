<script setup>
/** Keep source selection reachable even when the selected page cannot load. */
import { onMounted, ref } from "vue";
import { useDashboard } from "../lib/useDashboard.js";
import { useWorkbench } from "../lib/useWorkbench.js";
const { selectedDatasetId, selectDataset, data } = useDashboard();
const { datasets, selectedDataset, catalogueError, reason, refreshDatasets } = useWorkbench();
const selectionError = ref("");
let selectionGeneration = 0;
onMounted(refreshDatasets);
async function choose(event) {
  const token = ++selectionGeneration;
  selectionError.value = "";
  try { await selectDataset(event.target.value); }
  catch (cause) { if (token === selectionGeneration) selectionError.value = cause.message; }
}
</script>
<template>
  <section class="card dataset-context" aria-label="Analysis dataset">
    <div class="card-body">
      <div class="workbench-toolbar">
        <div class="field">
          <label for="analysis-dataset">Analysis dataset</label>
          <select id="analysis-dataset" :value="selectedDatasetId" @change="choose">
            <option value="">Legacy source · configured database / sample files</option>
            <option v-if="selectedDatasetId && !selectedDataset" :value="selectedDatasetId">Unavailable dataset · {{ selectedDatasetId }}</option>
            <option v-for="item in datasets" :key="item.id" :value="item.id">{{ item.name }} · {{ item.source }}</option>
          </select>
        </div>
        <button class="btn small" @click="refreshDatasets">Refresh datasets</button>
        <a class="btn small" href="#/generator/import">Import data</a>
      </div>
      <p v-if="selectedDataset" class="caption">
        {{ selectedDataset.source }} · {{ selectedDataset.scope?.advertiserId }} · {{ selectedDataset.scope?.marketplace }} ·
        {{ selectedDataset.scope?.currency }} · {{ selectedDataset.scope?.start }} → {{ selectedDataset.scope?.end }} ·
        {{ selectedDataset.counts?.performance?.toLocaleString() ?? 0 }} performance rows
      </p>
      <p v-else-if="!selectedDatasetId" class="caption">{{ data.source || 'Configured legacy source' }}. Select a registered dataset to analyze generated or imported observations.</p>
      <details v-if="selectedDataset"><summary>Analysis capabilities and provenance</summary>
        <p v-for="(capability, key) in selectedDataset.capabilities" :key="key"><b>{{ key }}:</b> {{ capability.available ? 'Available' : 'Unavailable' }} · {{ capability.reason }}</p>
        <p class="caption">Dataset {{ selectedDataset.id }} · Created {{ selectedDataset.createdAt }} · Input fingerprint {{ selectedDataset.digest }}</p>
      </details>
      <p v-if="reason" class="caption">{{ reason }}</p>
      <p v-if="catalogueError || selectionError" role="alert">{{ catalogueError || selectionError }}</p>
    </div>
  </section>
</template>
