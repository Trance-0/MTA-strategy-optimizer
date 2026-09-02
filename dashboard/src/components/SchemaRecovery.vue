<script setup>
/**
 * The remedies offered under the error card when a schema cannot be read.
 *
 * The server's own 503 names the problem; this names what to do about it, as
 * buttons. Every option is one the backend has already classified as safe for
 * the schema it names -- load a ready one, build dashboard schemas from a
 * source, or write the sample into an empty one -- and each is revalidated by
 * the route that carries it out, so nothing here grants a capability.
 *
 * Nothing offered here overwrites anything. Replacing an existing schema is a
 * deliberate act with a checkbox that states what it destroys, and that lives
 * in Settings where a reader arrives on purpose rather than after a failure.
 *
 * Data flow:
 *     GET /api/schema-recovery -> here -> schema-selection or schema-operations
 */
import { computed, onMounted, onUnmounted, ref } from "vue";

import {
  fetchSchemaOperation,
  fetchSchemaRecovery,
  selectRuntimeSchema,
  startSchemaOperation,
} from "../api/client.js";

const emit = defineEmits(["recovered", "settings"]);

const state = ref(null);
const busy = ref(false);
const failure = ref("");
const operation = ref(null);
let timer = null;

const options = computed(() => state.value?.options ?? []);
const running = computed(() =>
  ["queued", "running", "stopping"].includes(operation.value?.state),
);

/** The three actions read as instructions, not as the API's verbs. */
const HEADINGS = {
  select: "Load a schema that is ready",
  derive: "Build dashboard schemas from a source",
  initialize: "Start from the sample account",
};

const grouped = computed(() =>
  ["select", "derive", "initialize"]
    .map((action) => ({
      action,
      heading: HEADINGS[action],
      items: options.value.filter((item) => item.action === action),
    }))
    .filter((group) => group.items.length),
);

async function refresh() {
  state.value = await fetchSchemaRecovery();
}

onMounted(refresh);
onUnmounted(() => {
  if (timer !== null) window.clearTimeout(timer);
});

async function pollOperation() {
  if (timer !== null) window.clearTimeout(timer);
  timer = null;
  const result = await fetchSchemaOperation().catch(() => null);
  if (result) operation.value = result.current;
  if (running.value) {
    timer = window.setTimeout(pollOperation, 1200);
    return;
  }
  // A finished build has changed what the server holds, so the offer list is
  // re-read rather than left describing the database as it was before.
  await refresh();
  if (operation.value?.state === "succeeded") emit("recovered");
}

async function choose(option) {
  busy.value = true;
  failure.value = "";
  try {
    if (option.action === "select") {
      await selectRuntimeSchema(option.schema);
      emit("recovered");
    } else {
      operation.value = (
        await startSchemaOperation(option.action, option.schema, option.replace)
      ).current;
      pollOperation();
    }
  } catch (cause) {
    failure.value = cause.message;
  } finally {
    busy.value = false;
  }
}
</script>

<template>
  <section class="schema-recovery" aria-label="Schema remedies">
    <template v-if="state === null">
      <p class="caption">Checking what this database offers…</p>
    </template>

    <template v-else-if="!state.available">
      <p class="caption">{{ state.reason }}</p>
    </template>

    <template v-else>
      <p v-if="state.active" class="caption">
        Schema <code>{{ state.active }}</code> is loaded and cannot serve the
        views. Choose what to do with the database this server is connected to.
      </p>

      <p v-if="!options.length" class="caption">
        No other schema on this server can be loaded, built, or populated.
        <template v-if="!state.setupEnabled">
          This server was deployed without schema setup, so a schema must be
          prepared outside the dashboard.
        </template>
        <template v-else>
          Open <b>Settings</b> to point the dashboard at a different database.
        </template>
      </p>

      <div v-for="group in grouped" :key="group.action" class="recovery-group">
        <h3>{{ group.heading }}</h3>
        <div
          v-for="item in group.items"
          :key="`${item.action}-${item.schema}`"
          class="recovery-option"
        >
          <div class="recovery-text">
            <b>{{ item.schema }}</b>
            <span class="caption">{{ item.summary }}</span>
          </div>
          <button
            class="btn"
            :class="{ primary: group.action === 'select' }"
            :disabled="busy || running"
            @click="choose(item)"
          >
            {{ item.label }}
          </button>
        </div>
      </div>

      <p v-if="failure" class="notice bad">{{ failure }}</p>

      <!--
        The log is shown while a build runs rather than a spinner: these
        commands take minutes, and a reader watching one needs to see it is
        still doing something.
      -->
      <section v-if="operation" class="schema-operation" aria-live="polite">
        <p class="caption">
          {{ operation.action }} {{ operation.schema }} — {{ operation.state }}
          <template v-if="operation.exitCode !== null">
            · exit {{ operation.exitCode }}
          </template>
        </p>
        <p v-if="operation.error" class="notice bad">{{ operation.error }}</p>
        <div class="log-stream schema-log">
          <div
            v-for="(line, index) in operation.lines"
            :key="`${line.at}-${index}`"
            class="log-row"
          >
            <span class="log-when">{{ line.at }}</span>
            <span class="log-message">{{ line.text }}</span>
          </div>
        </div>
      </section>
    </template>
  </section>
</template>
