<script setup>
/**
 * A table of the values behind a chart.
 *
 * Every chart in the dashboard is paired with one of these, so no number is
 * reachable only by hovering. Columns are declared rather than inferred, so a
 * new field in the snapshot cannot silently widen a table.
 */
import { computed } from "vue";

import { count, money, percent, ratio } from "../theme.js";

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

const numericFormats = new Set(["number", "money", "percent", "ratio", "share"]);

function render(column, row) {
  const value = row[column.key];
  if (typeof column.format === "function") return column.format(value, row);
  if (value === null || value === undefined || value === "") return "--";
  switch (column.format) {
    case "number":
      return count(value, column.digits ?? 0);
    case "money":
      return money(value, column.currency ?? "$");
    case "percent":
      return percent(value, column.digits ?? 2);
    case "share":
      return Number(value).toFixed(column.digits ?? 4);
    case "ratio":
      return ratio(value, column.digits ?? 2);
    case "flag":
      return value ? "Yes" : "No";
    default:
      return String(value);
  }
}

const hasRows = computed(() => props.rows.length > 0);
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
          >
            {{ column.label }}
          </th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="(row, index) in rows" :key="row.id ?? index">
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
