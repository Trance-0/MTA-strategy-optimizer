<script setup>
/**
 * Accessible progress for a user-visible dataset request lasting over three seconds.
 *
 * Timing and byte counting live in `useDashboard`; this component only renders
 * shared state so two views observing one request cannot disagree.
 */
import { computed } from "vue";

const props = defineProps({ progress: { type: Object, required: true } });
const determinate = computed(() => Number.isFinite(props.progress.percent));
const percent = computed(() => determinate.value ? Math.round(props.progress.percent) : null);

function bytes(value) {
  if (!Number.isFinite(value)) return "";
  return `${(value / 1024 / 1024).toFixed(value >= 10 * 1024 * 1024 ? 1 : 2)} MB`;
}

const elapsed = computed(() => `${(Number(props.progress.elapsedMs ?? 0) / 1000).toFixed(1)}s`);
</script>

<template>
  <div v-if="progress.visible" class="load-progress">
    <div
      class="load-progress-track"
      role="progressbar"
      :aria-label="progress.label"
      :aria-valuenow="percent"
      aria-valuemin="0"
      aria-valuemax="100"
    >
      <div
        class="load-progress-fill"
        :class="{ indeterminate: !determinate }"
        :style="determinate ? { width: `${percent}%` } : null"
      ></div>
    </div>
    <div class="run-status">
      <span class="run-phase">{{ progress.phase || progress.label }}</span>
      <span class="run-meta">
        <template v-if="determinate">{{ percent }}% · {{ elapsed }}<template v-if="progress.total"> · {{ bytes(progress.loaded) }} of {{ bytes(progress.total) }}</template></template>
        <template v-else>{{ elapsed }} · {{ bytes(progress.loaded) || "Waiting for data" }}</template>
      </span>
    </div>
  </div>
</template>
