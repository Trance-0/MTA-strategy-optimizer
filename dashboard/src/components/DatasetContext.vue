<script setup>
/**
 * The compact analysis-source selector that lives in the top bar.
 *
 * Source selection stays reachable even when the selected page cannot load,
 * which is why this renders in the header rather than inside a routed view.
 * The select is the control; scope, capabilities, and provenance of the
 * chosen dataset open from the adjacent details popover instead of occupying
 * a card above every page.
 */
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
  <div class="topbar-dataset" aria-label="Analysis dataset" data-tour="dataset-selector">
    <label class="sr-only" for="analysis-dataset">Analysis dataset</label>
    <select
      id="analysis-dataset"
      :value="selectedDatasetId"
      :title="selectedDataset
        ? `${selectedDataset.source} · ${selectedDataset.scope?.advertiserId} · ${selectedDataset.scope?.marketplace} · ${selectedDataset.scope?.currency} · ${selectedDataset.scope?.start} → ${selectedDataset.scope?.end}`
        : `${data.source || 'Configured legacy source'}. Select a registered dataset to analyze generated or imported observations.`"
      @change="choose"
    >
      <option value="">Legacy source · configured database / sample files</option>
      <option v-if="selectedDatasetId && !selectedDataset" :value="selectedDatasetId">Unavailable dataset · {{ selectedDatasetId }}</option>
      <option v-for="item in datasets" :key="item.id" :value="item.id">{{ item.name }} · {{ item.source }}</option>
    </select>
    <button class="btn small" title="Reload the registered dataset catalogue" @click="refreshDatasets">Refresh</button>
    <a class="btn small" href="#/generator/import" title="Import or generate a new dataset">Import</a>
    <details v-if="selectedDataset" class="topbar-dataset-details">
      <summary title="Analysis capabilities and provenance">Details</summary>
      <div class="topbar-dataset-popover">
        <p class="caption">
          {{ selectedDataset.source }} · {{ selectedDataset.scope?.advertiserId }} · {{ selectedDataset.scope?.marketplace }} ·
          {{ selectedDataset.scope?.currency }} · {{ selectedDataset.scope?.start }} → {{ selectedDataset.scope?.end }} ·
          {{ selectedDataset.counts?.performance?.toLocaleString() ?? 0 }} performance rows
        </p>
        <p v-for="(capability, key) in selectedDataset.capabilities" :key="key"><b>{{ key }}:</b> {{ capability.available ? 'Available' : 'Unavailable' }} · {{ capability.reason }}</p>
        <p class="caption">Dataset {{ selectedDataset.id }} · Created {{ selectedDataset.createdAt }} · Input fingerprint {{ selectedDataset.digest }}</p>
        <p v-if="reason" class="caption">{{ reason }}</p>
      </div>
    </details>
    <p v-if="catalogueError || selectionError" class="topbar-dataset-error" role="alert">{{ catalogueError || selectionError }}</p>
  </div>
</template>
