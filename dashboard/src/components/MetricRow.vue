<script setup>
/**
 * A row of headline tiles.
 *
 * Each tile is one number with its label, in a card rather than bare on the
 * plane. A single value has no shape to plot, so it is a tile, not a chart.
 */
defineProps({
  /** `{ label, value, note, help }` per tile. */
  items: { type: Array, required: true },
});
</script>

<template>
  <div class="metrics">
    <div v-for="item in items" :key="item.label" class="metric">
      <label :title="item.help">{{ item.label }}</label>
      <b>{{ item.value }}</b>
      <span v-if="item.note">{{ item.note }}</span>
    </div>
  </div>
</template>
