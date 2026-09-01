<script setup>
/**
 * One pipeline stage's controls, progress, and log.
 *
 * The web-panel treatment: a run control, a progress bar carrying the phase the
 * stage is actually in, and the command's own output streamed beneath it. The
 * command line is shown verbatim because the dashboard runs the same script the
 * documented terminal command does — a reader who wants to reproduce a run, or
 * to check what the dashboard actually did, can copy it.
 *
 * The progress bar reads phases matched from the script's own stdout rather
 * than a timer, so a slow fit shows as a slow phase instead of a bar that
 * reaches ninety percent and stops.
 *
 * Data flow:
 *     src/lib/useJobs.js -> here -> POST /api/jobs/:stage
 */
import { computed, ref, watch } from "vue";

const props = defineProps({
  /** The stage descriptor from `GET /api/jobs`. */
  stage: { type: Object, required: true },
  busy: { type: Boolean, default: false },
  /** Extra controls this stage offers, as `{ key, label, type, options }`. */
  controls: { type: Array, default: () => [] },
});

const emit = defineEmits(["start", "stop", "reload"]);

const options = ref({});
const logEnd = ref(null);

watch(
  () => [props.stage.key, props.stage.defaultDataset],
  () => {
    const ids = new Set((props.stage.datasets ?? []).map((item) => item.id));
    if (!ids.has(options.value.datasetId)) {
      options.value.datasetId = props.stage.defaultDataset ?? "";
    }
  },
  { immediate: true },
);

const job = computed(() => props.stage.current);
const running = computed(() => job.value?.state === "running");
const succeeded = computed(() => job.value?.state === "succeeded");
const failed = computed(() => job.value?.state === "failed");

/** Why the run control is disabled, or an empty string when it is not. */
const blocked = computed(() => {
  if (!props.stage.available) return props.stage.unavailableReason ?? "";
  if (!options.value.datasetId) return "Choose a compatible dataset before running.";
  return "";
});

const lines = computed(() => job.value?.lines ?? []);

/**
 * Follow the tail while a run is going.
 *
 * Only while running: scrolling a finished log to the bottom would fight a
 * reader who scrolled up to read why it failed.
 */
watch(
  () => lines.value.length,
  () => {
    if (!running.value) return;
    requestAnimationFrame(() => {
      logEnd.value?.scrollIntoView({ block: "end" });
    });
  },
);

function elapsed(record) {
  if (!record?.startedAt) return "";
  const end = record.finishedAt ? new Date(record.finishedAt) : new Date();
  const seconds = Math.max(0, Math.round((end - new Date(record.startedAt)) / 1000));
  if (seconds < 60) return `${seconds}s`;
  return `${Math.floor(seconds / 60)}m ${String(seconds % 60).padStart(2, "0")}s`;
}
</script>

<template>
  <div class="stage-runner">
    <div class="filter-row">
      <div class="field">
        <label :for="`stage-${stage.key}-dataset`">Data</label>
        <select
          :id="`stage-${stage.key}-dataset`"
          v-model="options.datasetId"
          :disabled="running || !(stage.datasets ?? []).length"
        >
          <option v-if="!(stage.datasets ?? []).length" value="">
            No compatible dataset
          </option>
          <option v-for="item in stage.datasets ?? []" :key="item.id" :value="item.id">
            {{ item.label }} · {{ item.description }}
          </option>
        </select>
      </div>
    </div>

    <div v-if="blocked" class="notice">{{ blocked }}</div>

    <template v-else>
      <div v-if="controls.length" class="filter-row">
        <div v-for="control in controls" :key="control.key" class="field">
          <label :for="`stage-${stage.key}-${control.key}`">{{ control.label }}</label>
          <select
            v-if="control.type === 'select'"
            :id="`stage-${stage.key}-${control.key}`"
            v-model="options[control.key]"
            :disabled="running"
          >
            <option v-for="item in control.options" :key="item.value" :value="item.value">
              {{ item.label }}
            </option>
          </select>
          <input
            v-else
            :id="`stage-${stage.key}-${control.key}`"
            v-model="options[control.key]"
            :type="control.type"
            :placeholder="control.placeholder"
            :disabled="running"
          />
        </div>
      </div>

      <div class="rec-actions">
        <button
          class="btn primary"
          :disabled="running || busy"
          @click="emit('start', options)"
        >
          {{ running ? "Running…" : `Run ${stage.label}` }}
        </button>
        <button v-if="running" class="btn" :disabled="busy" @click="emit('stop')">
          Stop
        </button>
        <button
          v-if="succeeded"
          class="btn"
          :disabled="busy"
          @click="emit('reload')"
        >
          Load the new results
        </button>
      </div>

      <template v-if="job">
        <!--
          `aria-valuenow` and the visible percentage read from one value, so a
          screen reader and the bar cannot report different progress.
        -->
        <div
          class="run-progress"
          role="progressbar"
          :aria-valuenow="job.percent"
          aria-valuemin="0"
          aria-valuemax="100"
          :aria-label="`${stage.label} progress`"
        >
          <div
            class="run-progress-fill"
            :class="{ failed, done: succeeded }"
            :style="{ width: `${job.percent}%` }"
          ></div>
        </div>

        <div class="run-status">
          <span class="run-phase">{{ job.phase }}</span>
          <span class="run-meta">
            {{ job.percent }}% · {{ elapsed(job) }}
            <template v-if="job.exitCode !== null"> · exit {{ job.exitCode }}</template>
          </span>
        </div>

        <div v-if="failed" class="notice bad">
          <b>The stage did not complete.</b>
          {{ job.error || "The command exited with a non-zero status. The output below says why." }}
        </div>
        <div v-else-if="succeeded" class="notice good">
          <b>Complete.</b> The new outputs are written. Choose
          <b>Load the new results</b> to read them into the dashboard.
        </div>

        <p v-if="job.droppedLines" class="caption">
          {{ job.droppedLines.toLocaleString() }} earlier line(s) dropped; this
          is the tail of the output.
        </p>

        <div class="log-stream run-log">
          <div
            v-for="(record, index) in lines"
            :key="index"
            class="log-row"
            :class="`log-${record.stream}`"
          >
            <span class="log-when">{{ record.at.slice(11, 19) }}</span>
            <span class="log-message">{{ record.text }}</span>
          </div>
          <div ref="logEnd"></div>
        </div>

        <p class="caption">
          The dashboard runs the project's own command, unchanged:
          <code>{{ job.command }}</code>
        </p>
      </template>

      <p v-else class="table-empty">
        This stage has not been run from the dashboard yet.
      </p>
    </template>
  </div>
</template>
