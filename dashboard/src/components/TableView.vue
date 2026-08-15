<script setup>
/**
 * A collapsed table beneath a chart.
 *
 * Every chart ships one, so a tooltip stays an enhancement rather than the
 * only way to read a value. It is closed by default because the chart is the
 * answer and the table is the evidence.
 */
import { ref } from "vue";

import DataTable from "./DataTable.vue";

defineProps({
  label: { type: String, default: "View as table" },
  columns: { type: Array, required: true },
  rows: { type: Array, default: () => [] },
});

const open = ref(false);
</script>

<template>
  <div class="table-view">
    <button class="btn link small" :aria-expanded="open" @click="open = !open">
      {{ open ? "Hide" : label }}
      <span class="chevron" :class="{ open }" aria-hidden="true">›</span>
    </button>
    <DataTable v-if="open" :columns="columns" :rows="rows" />
  </div>
</template>
