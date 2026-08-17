<script setup>
/**
 * One Plotly figure, sized to its card and redrawn when its data changes.
 *
 * Plotly draws into a real element rather than through a virtual DOM, so the
 * figure is created on mount and updated with `react`, which diffs against the
 * existing plot instead of tearing it down. Tearing down would lose the
 * reader's hover state on every reactive change.
 */
import { onBeforeUnmount, onMounted, ref, watch } from "vue";

import Plotly from "plotly.js-dist-min";

import { PLOT_CONFIG } from "../theme.js";

const props = defineProps({
  traces: { type: Array, required: true },
  layout: { type: Object, default: () => ({}) },
  /** Accessible description of what the chart shows. */
  label: { type: String, default: "Chart" },
});

const host = ref(null);

function draw() {
  if (!host.value) return;
  Plotly.react(host.value, props.traces, props.layout, PLOT_CONFIG);
}

onMounted(draw);
watch(() => [props.traces, props.layout], draw, { deep: true });

onBeforeUnmount(() => {
  // Plotly attaches window resize listeners per plot; purging releases them.
  if (host.value) Plotly.purge(host.value);
});
</script>

<template>
  <div ref="host" class="plot" role="img" :aria-label="label"></div>
</template>
