<script setup>
/**
 * A paged, selectable table of one entity type.
 *
 * The 1Panel list treatment: a row is an abstract -- a handful of declared
 * summary columns -- and everything else about it is behind the row's own Edit
 * control rather than expanded inline. The previous Budget Manager rendered
 * every field of every record as stacked `<details>` paragraphs, which put
 * hundreds of lines of prose on one page and left no way to scan a column.
 *
 * What this component owns: paging, page size, selection, and the two row
 * controls. What it does not own: what a row *means*. Columns are declared by
 * the view, exactly as `DataTable`'s are, so a new field in the snapshot cannot
 * silently widen a table.
 *
 * Selection is keyed by a caller-supplied `rowKey`, not by page index, so a
 * selected row survives paging and a batch action cannot act on whatever
 * happens to sit at that index after the page turns.
 *
 * Data flow:
 *     a view's rows and column declarations -> here -> edit/delete events
 */
import { computed, ref, watch } from "vue";

import { NUMERIC_FORMATS, renderCell } from "../lib/common.js";

const props = defineProps({
  /** One entry per column: the same `{ key, label, format }` DataTable takes. */
  columns: { type: Array, required: true },
  rows: { type: Array, default: () => [] },
  /** Returns the stable identity of a row. Selection is keyed by this. */
  rowKey: { type: Function, required: true },
  /** Whether to draw the selection column and the two row controls. */
  selectable: { type: Boolean, default: false },
  editable: { type: Boolean, default: false },
  deletable: { type: Boolean, default: false },
  /** Rendered in place of the grid when there is nothing to show. */
  empty: { type: String, default: "No rows to show." },
  /** Shown beside the toolbar's count, naming what a row is. */
  noun: { type: String, default: "row" },
});

const emit = defineEmits(["edit", "delete", "delete-many"]);

const PAGE_SIZES = [10, 15, 30, 50, 100];

const pageSize = ref(PAGE_SIZES[0]);
const page = ref(1);
const search = ref("");
const selected = ref(new Set());

/**
 * Free-text filter across the declared columns only.
 *
 * Rendered text rather than raw fields, so what the reader searches is what
 * the reader sees: a row showing "Yes" for a boolean is found by "yes", and a
 * field that is in the record but in no column is not silently searchable.
 */
const filtered = computed(() => {
  const needle = search.value.trim().toLowerCase();
  if (!needle) return props.rows;
  return props.rows.filter((row) =>
    props.columns.some((column) =>
      String(renderCell(column, row)).toLowerCase().includes(needle),
    ),
  );
});

const pageCount = computed(() =>
  Math.max(1, Math.ceil(filtered.value.length / pageSize.value)),
);

/**
 * Clamped rather than reset, so narrowing the filter keeps the reader near
 * where they were instead of throwing them back to page one.
 */
watch([filtered, pageSize], () => {
  if (page.value > pageCount.value) page.value = pageCount.value;
});

const pageRows = computed(() => {
  const start = (page.value - 1) * pageSize.value;
  return filtered.value.slice(start, start + pageSize.value);
});

const firstShown = computed(() =>
  filtered.value.length === 0 ? 0 : (page.value - 1) * pageSize.value + 1,
);
const lastShown = computed(() =>
  Math.min(page.value * pageSize.value, filtered.value.length),
);

function isSelected(row) {
  return selected.value.has(props.rowKey(row));
}

function toggle(row) {
  // Reassigned rather than mutated: a Set mutated in place is the same object,
  // so Vue's reactivity would not see the change and no checkbox would repaint.
  const next = new Set(selected.value);
  const key = props.rowKey(row);
  if (next.has(key)) next.delete(key);
  else next.add(key);
  selected.value = next;
}

/** The header checkbox acts on the current page, which is what it can show. */
const pageAllSelected = computed(
  () => pageRows.value.length > 0 && pageRows.value.every(isSelected),
);

function togglePage() {
  const next = new Set(selected.value);
  if (pageAllSelected.value) {
    for (const row of pageRows.value) next.delete(props.rowKey(row));
  } else {
    for (const row of pageRows.value) next.add(props.rowKey(row));
  }
  selected.value = next;
}

function clearSelection() {
  selected.value = new Set();
}

/**
 * The selected rows, in the filtered order rather than selection order, so a
 * confirmation lists them as the table shows them.
 */
const selectedRows = computed(() =>
  filtered.value.filter((row) => selected.value.has(props.rowKey(row))),
);

function requestBatchDelete() {
  if (selectedRows.value.length === 0) return;
  emit("delete-many", selectedRows.value);
}

defineExpose({ clearSelection });
</script>

<template>
  <div class="entity-table">
    <div class="entity-toolbar">
      <slot name="toolbar-start" />

      <div class="field entity-search">
        <input v-model="search" type="search" :placeholder="`Search ${noun}s`" />
      </div>

      <span class="entity-count">
        {{ filtered.length.toLocaleString() }} {{ noun
        }}{{ filtered.length === 1 ? "" : "s" }}
        <template v-if="filtered.length !== rows.length">
          of {{ rows.length.toLocaleString() }}
        </template>
      </span>

      <div v-if="selectable && selectedRows.length" class="entity-batch">
        <span>{{ selectedRows.length.toLocaleString() }} selected</span>
        <button class="btn small" @click="clearSelection">Clear</button>
        <button
          v-if="deletable"
          class="btn small danger"
          @click="requestBatchDelete"
        >
          Delete selected
        </button>
      </div>

      <label class="entity-page-size">
        <span>Per page</span>
        <select v-model.number="pageSize">
          <option v-for="size in PAGE_SIZES" :key="size" :value="size">
            {{ size }}
          </option>
        </select>
      </label>
    </div>

    <div v-if="pageRows.length" class="table-wrap">
      <table>
        <thead>
          <tr>
            <th v-if="selectable" class="select-cell">
              <input
                type="checkbox"
                :checked="pageAllSelected"
                :aria-label="`Select every ${noun} on this page`"
                @change="togglePage"
              />
            </th>
            <th
              v-for="column in columns"
              :key="column.key"
              :class="{ num: NUMERIC_FORMATS.has(column.format) }"
              :style="column.width ? { width: column.width } : null"
            >
              {{ column.label }}
            </th>
            <th v-if="editable || deletable" class="row-actions-head">Actions</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="row in pageRows"
            :key="rowKey(row)"
            :class="{ selected: selectable && isSelected(row) }"
          >
            <td v-if="selectable" class="select-cell">
              <input
                type="checkbox"
                :checked="isSelected(row)"
                :aria-label="`Select ${rowKey(row)}`"
                @change="toggle(row)"
              />
            </td>
            <td
              v-for="column in columns"
              :key="column.key"
              :class="{ num: NUMERIC_FORMATS.has(column.format) }"
            >
              <span
                v-if="column.tone"
                class="tag"
                :class="column.tone(row[column.key], row)"
              >
                {{ renderCell(column, row) }}
              </span>
              <template v-else>{{ renderCell(column, row) }}</template>
            </td>
            <td v-if="editable || deletable" class="row-actions">
              <button
                v-if="editable"
                class="btn small"
                @click="emit('edit', row)"
              >
                Edit
              </button>
              <button
                v-if="deletable"
                class="btn small danger"
                @click="emit('delete', row)"
              >
                Delete
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <p v-else class="table-empty">
      {{ rows.length ? `No ${noun}s match this search.` : empty }}
    </p>

    <div v-if="filtered.length" class="entity-pager">
      <span class="entity-range">
        {{ firstShown.toLocaleString() }}–{{ lastShown.toLocaleString() }} of
        {{ filtered.length.toLocaleString() }}
      </span>
      <div class="entity-pager-controls">
        <button class="btn small" :disabled="page === 1" @click="page = 1">
          First
        </button>
        <button class="btn small" :disabled="page === 1" @click="page -= 1">
          Previous
        </button>
        <span class="entity-page-of">Page {{ page }} of {{ pageCount }}</span>
        <button
          class="btn small"
          :disabled="page === pageCount"
          @click="page += 1"
        >
          Next
        </button>
        <button
          class="btn small"
          :disabled="page === pageCount"
          @click="page = pageCount"
        >
          Last
        </button>
      </div>
    </div>
  </div>
</template>
