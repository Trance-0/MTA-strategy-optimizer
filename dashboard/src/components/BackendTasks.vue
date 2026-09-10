<script setup>
/** Build-style inspector for queued and completed backend operator tasks. */
import { computed, onUnmounted, ref, watch } from "vue";

import LogViewer from "./LogViewer.vue";

import { fetchTasks, stopTask } from "../api/client.js";

const props = defineProps({
  active: { type: Boolean, default: false },
  focusTaskId: { type: String, default: "" },
});

const state = ref({ concurrency: 1, tasks: [] });
const selectedId = ref("");
const busy = ref(false);
const message = ref("");
let timer = null;

const selected = computed(() =>
  state.value.tasks.find((task) => task.id === selectedId.value) ?? null,
);
const running = computed(() =>
  state.value.tasks.some((task) => ["queued", "running", "stopping"].includes(task.state)),
);
const canStop = computed(() =>
  ["queued", "running"].includes(selected.value?.state),
);

function schedule() {
  if (timer !== null) window.clearTimeout(timer);
  timer = null;
  if (props.active && running.value) timer = window.setTimeout(refresh, 900);
}

async function refresh() {
  try {
    state.value = await fetchTasks();
    const preferred = props.focusTaskId || selectedId.value;
    selectedId.value = state.value.tasks.some((task) => task.id === preferred)
      ? preferred
      : state.value.tasks[0]?.id ?? "";
  } catch (error) {
    message.value = `${error.name}: ${error.message}`;
  } finally {
    schedule();
  }
}

watch(
  () => [props.active, props.focusTaskId],
  ([active]) => {
    if (active) refresh();
    else schedule();
  },
  { immediate: true },
);

onUnmounted(() => {
  if (timer !== null) window.clearTimeout(timer);
});

function timestamp(value) {
  if (!value) return "—";
  return new Date(value).toLocaleString();
}

function summary(task) {
  return Object.entries(task.summary ?? {})
    .filter(([, value]) => value !== null && value !== "")
    .map(([key, value]) => `${key}=${value}`)
    .join(" · ");
}

const logContext = computed(() => {
  const task = selected.value;
  if (!task) return [];
  return [
    `${task.label} — ${task.state}`, `Task ${task.id}`,
    `Created ${task.createdAt}`, `Started ${task.startedAt ?? "not started"}`,
    `Finished ${task.finishedAt ?? "not finished"}`, `Exit ${task.exitCode ?? "pending"}`,
    summary(task),
  ];
});

async function requestStop() {
  if (!selected.value) return;
  busy.value = true;
  message.value = "";
  try {
    await stopTask(selected.value.id);
    message.value = "Stop requested.";
    await refresh();
  } catch (error) {
    message.value = `${error.name}: ${error.message}`;
  } finally {
    busy.value = false;
  }
}
</script>

<template>
  <section class="tasks-panel" aria-label="Backend tasks">
    <div class="section-head">
      <div>
        <h3>Backend tasks</h3>
        <p class="caption">
          One worker processes database and model tasks in queue order.
        </p>
      </div>
      <button class="btn small" :disabled="busy" @click="refresh">Refresh</button>
    </div>

    <div v-if="message" class="notice">{{ message }}</div>
    <div v-if="!state.tasks.length" class="notice">
      No backend task has been recorded in this server process.
    </div>
    <div v-else class="task-layout">
      <div class="task-list" role="list" aria-label="Task history">
        <button
          v-for="task in state.tasks"
          :key="task.id"
          class="task-row"
          :class="{ active: task.id === selectedId }"
          role="listitem"
          @click="selectedId = task.id"
        >
          <span class="task-row-head">
            <b>{{ task.label }}</b>
            <span class="task-state" :class="task.state">{{ task.state }}</span>
          </span>
          <span>{{ summary(task) || task.action }}</span>
          <small>
            {{ timestamp(task.createdAt) }}
            <template v-if="task.queuePosition"> · queue {{ task.queuePosition }}</template>
          </small>
        </button>
      </div>

      <article v-if="selected" class="task-detail">
        <div class="section-head">
          <div>
            <h3>{{ selected.label }}</h3>
            <p class="caption">{{ selected.id }} · {{ selected.phase }}</p>
          </div>
          <div class="rec-actions">
            <button
              v-if="canStop"
              class="btn small danger"
              :disabled="busy"
              @click="requestStop"
            >
              Stop
            </button>
          </div>
        </div>

        <div class="task-timestamps">
          <span>Created <b>{{ timestamp(selected.createdAt) }}</b></span>
          <span>Started <b>{{ timestamp(selected.startedAt) }}</b></span>
          <span>Finished <b>{{ timestamp(selected.finishedAt) }}</b></span>
        </div>
        <p class="caption">{{ summary(selected) }}</p>
        <div class="load-progress-track" role="progressbar" :aria-valuenow="selected.percent" aria-valuemin="0" aria-valuemax="100">
          <div class="load-progress-fill" :style="{ width: `${selected.percent ?? 0}%` }"></div>
        </div>
        <p v-if="selected.error" class="notice bad">{{ selected.error }}</p>
        <LogViewer
          :key="selected.id"
          :records="selected.lines ?? []"
          :context="logContext"
          :command="selected.command ?? ''"
          :dropped-lines="selected.droppedLines ?? 0"
          :running="['queued', 'running', 'stopping'].includes(selected.state)"
        />
      </article>
    </div>
  </section>
</template>
