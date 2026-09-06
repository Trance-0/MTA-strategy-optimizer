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

import { PLOT_CONFIG } from "../theme.js";

const props = defineProps({
  traces: { type: Array, required: true },
  layout: { type: Object, default: () => ({}) },
  /** Accessible description of what the chart shows. */
  label: { type: String, default: "Chart" },
});

const host = ref(null);
const error = ref("");
let plotly;
let frame;
let disposed = false;
let drawing = false;
let revision = 0;

async function draw() {
  frame = null;
  if (disposed || !host.value || drawing) return;
  drawing = true;
  const current = revision;
  const element = host.value;
  try {
    plotly ??= (await import("plotly.js-dist-min")).default;
    if (disposed) return;
    await plotly.react(element, props.traces, props.layout, PLOT_CONFIG);
    error.value = "";
  } catch {
    if (!disposed) error.value = "The chart could not load. The values remain available in the table.";
  } finally {
    drawing = false;
    if (disposed) plotly?.purge(element);
    else if (current !== revision) schedule();
  }
}

function schedule() {
  revision += 1;
  if (!disposed && frame == null && !drawing) frame = requestAnimationFrame(draw);
}

onMounted(schedule);
watch(() => [props.traces, props.layout], schedule);

onBeforeUnmount(() => {
  disposed = true;
  if (frame != null) cancelAnimationFrame(frame);
  if (host.value && !drawing) plotly?.purge(host.value);
});
</script>

<template>
  <div ref="host" class="plot" role="img" :aria-label="label"></div>
  <p v-if="error" role="alert">{{ error }}</p>
</template>
