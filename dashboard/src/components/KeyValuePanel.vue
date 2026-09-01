<script setup>
/**
 * A titled card of label/value pairs.
 *
 * Used where the content is a handful of facts rather than a series: a run
 * record, a derivation, a set of weights.
 */
import { termFor } from "../lib/terms.js";
import TermHelp from "./TermHelp.vue";

defineProps({
  title: { type: String, required: true },
  /** `{ label, value, code }` per row. `code` renders the value monospaced. */
  rows: { type: Array, default: () => [] },
});
</script>

<template>
  <div class="panel">
    <div class="panel-title">{{ title }}</div>
    <div v-for="row in rows" :key="row.label" class="kv">
      <span>
        {{ row.label }}
        <TermHelp v-if="termFor(row.label)" :term="termFor(row.label)" />
      </span>
      <span v-if="row.code" class="kv-code">{{ row.value }}</span>
      <span v-else>{{ row.value }}</span>
    </div>
    <p v-if="rows.length === 0" class="caption">Not recorded.</p>
  </div>
</template>
