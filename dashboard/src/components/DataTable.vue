<script setup>
/**
 * A table of the values behind a chart.
 *
 * Every chart in the dashboard is paired with one of these, so no number is
 * reachable only by hovering. Columns are declared rather than inferred, so a
 * new field in the snapshot cannot silently widen a table.
 */
import { computed, ref } from "vue";

import {
  NUMERIC_FORMATS,
  nextTableSort,
  renderCell,
  sortTableRows,
} from "../lib/common.js";
import { termFor } from "../lib/terms.js";
import TermHelp from "./TermHelp.vue";

const props = defineProps({
  /**
   * One entry per column: `{ key, label, format, width }`. `format` is one of
   * `text`, `number`, `money`, `percent`, `ratio`, `share`, `flag`, or a
   * function taking the row's value.
   */
  columns: { type: Array, required: true },
  rows: { type: Array, default: () => [] },
  /** Rendered when there is nothing to show, instead of an empty grid. */
  empty: { type: String, default: "No rows to show." },
});

const numericFormats = NUMERIC_FORMATS;
const render = renderCell;

const hasRows = computed(() => props.rows.length > 0);
const sort = ref({ key: null, direction: null });
const sortedRows = computed(() => {
  const column = props.columns.find(({ key }) => key === sort.value.key);
  return sortTableRows(props.rows, column, sort.value.direction);
});

function changeSort(column) {
  sort.value = nextTableSort(sort.value, column.key);
}

function ariaSort(column) {
  if (sort.value.key !== column.key || !sort.value.direction) return "none";
  return sort.value.direction === "asc" ? "ascending" : "descending";
}
</script>

<template>
  <div class="table-wrap">
    <table v-if="hasRows">
      <thead>
        <tr>
          <th
            v-for="column in columns"
            :key="column.key"
            :class="{ num: numericFormats.has(column.format) }"
            :style="column.width ? { width: column.width } : null"
            :aria-sort="ariaSort(column)"
          >
            <button
              type="button"
              class="table-sort-button"
              :class="{ active: sort.key === column.key }"
              @click="changeSort(column)"
            >
              <span>{{ column.label }}</span>
              <span
                v-if="sort.key === column.key"
                class="table-sort-arrow"
                aria-hidden="true"
              >{{ sort.direction === "asc" ? "▲" : "▼" }}</span>
            </button>
            <TermHelp v-if="termFor(column.label)" :term="termFor(column.label)" />
          </th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="(row, index) in sortedRows" :key="row.id ?? index">
          <td
            v-for="column in columns"
            :key="column.key"
            :class="{ num: numericFormats.has(column.format) }"
          >
            <span
              v-if="column.format === 'flag'"
              class="tag"
              :class="row[column.key] ? 'green' : 'red'"
            >{{ row[column.key] ? "Pass" : "Fail" }}</span>
            <span v-else-if="column.tone" class="tag" :class="column.tone(row[column.key], row)">
              {{ render(column, row) }}
            </span>
            <template v-else>{{ render(column, row) }}</template>
          </td>
        </tr>
      </tbody>
    </table>
    <p v-else class="table-empty">{{ empty }}</p>
  </div>
</template>
