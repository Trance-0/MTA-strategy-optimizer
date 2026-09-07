<script setup>
/** Configure, run, preview, and export the pinned MTA-SIM generator. */
import { computed, onMounted, onUnmounted, ref } from "vue";

import DataTable from "../components/DataTable.vue";
import GeneratorConfigEditor from "../components/GeneratorConfigEditor.vue";
import { createGeneratorLifecycle, replacePresetIfConfirmed } from "../generator/lifecycle.js";
import {
  exportGeneratorRun,
  fetchGeneratorOverview,
  fetchGeneratorPreset,
  fetchGeneratorRun,
  generatorDownloadUrl,
  startGeneratorRun,
  validateGeneratorConfiguration,
} from "../api/client.js";

const overview = ref(null);
const variant = ref("baseline");
const preset = ref("toy");
const configuration = ref({});
const editorKey = ref(0);
const backendIssues = ref([]);
const localIssues = ref([]);
const configurationDirty = ref(false);
const preflight = ref({ status: "not_run", message: "Run preflight before generation." });
const busy = ref(false);
const error = ref("");
const run = ref(null);
const exportOpen = ref(false);
const exportForm = ref({
  host: "",
  port: "5432",
  database: "",
  user: "",
  password: "",
  sslmode: "require",
  schema: "",
  replace: false,
});
let pollTimer = null;
let presetSequence = 0;
const lifecycle = createGeneratorLifecycle();

const availablePresets = computed(
  () => overview.value?.variants?.find((item) => item.key === variant.value)?.presets ?? [],
);
const running = computed(() => ["queued", "running"].includes(run.value?.status));
const completed = computed(() => run.value?.status === "completed");
const operationActive = computed(() =>
  running.value || run.value?.export?.status === "running",
);
const canRunPreflight = computed(() =>
  overview.value?.available && !busy.value && !operationActive.value && !localIssues.value.length,
);
const canGenerate = computed(() =>
  canRunPreflight.value
    && preflight.value.status === "valid"
    && lifecycle.canGenerate(variant.value, configuration.value),
);
const secureExport = computed(() =>
  window.location.protocol === "https:" ||
  ["localhost", "127.0.0.1", "::1"].includes(window.location.hostname),
);

function setConfiguration(value) {
  if (pollTimer !== null) window.clearTimeout(pollTimer);
  pollTimer = null;
  lifecycle.clearRun();
  configuration.value = JSON.parse(JSON.stringify(value ?? {}));
  backendIssues.value = [];
  localIssues.value = [];
  configurationDirty.value = false;
  preflight.value = { status: "not_run", message: "Run preflight before generation." };
  lifecycle.configurationChanged(variant.value, configuration.value);
  editorKey.value += 1;
}

function updateConfiguration(value) {
  configuration.value = JSON.parse(JSON.stringify(value ?? {}));
  backendIssues.value = [];
  preflight.value = { status: "not_run", message: "Configuration changed; run preflight again." };
  lifecycle.configurationChanged(variant.value, configuration.value);
}

function updateLocalIssues(issues) {
  localIssues.value = issues;
  if (preflight.value.status === "valid" || issues.length) {
    preflight.value = { status: "not_run", message: "Configuration changed; run preflight again." };
  }
}

async function loadPreset(nextVariant, nextPreset) {
  const sequence = ++presetSequence;
  busy.value = true;
  error.value = "";
  try {
    const result = await fetchGeneratorPreset(nextVariant, nextPreset);
    if (sequence !== presetSequence) return false;
    variant.value = nextVariant;
    preset.value = nextPreset;
    setConfiguration(result.configuration);
    run.value = null;
    return true;
  } catch (cause) {
    if (sequence !== presetSequence) return false;
    error.value = cause.message;
    return false;
  } finally {
    if (sequence === presetSequence) busy.value = false;
  }
}

function resetSelect(event, value) {
  event.target.value = value;
}

async function requestPresetChange(nextVariant, nextPreset, event) {
  if (nextVariant === variant.value && nextPreset === preset.value) return;
  const changed = await replacePresetIfConfirmed({
    dirty: configurationDirty.value,
    confirm: () => window.confirm("Changing the preset or variant discards the current configuration edit. Continue?"),
    loadPreset,
    variant: nextVariant,
    preset: nextPreset,
  });
  if (!changed) {
    resetSelect(event, nextVariant === variant.value ? preset.value : variant.value);
  }
}

function chooseVariant(event) {
  const nextVariant = event.target.value;
  const nextPreset = overview.value?.variants
    ?.find((item) => item.key === nextVariant)?.presets?.[0]?.key;
  if (!nextPreset) {
    resetSelect(event, variant.value);
    return;
  }
  requestPresetChange(nextVariant, nextPreset, event);
}

function choosePreset(event) {
  requestPresetChange(variant.value, event.target.value, event);
}

async function runPreflight() {
  if (!canRunPreflight.value) return;
  busy.value = true;
  error.value = "";
  backendIssues.value = [];
  const request = lifecycle.beginPreflight(variant.value, configuration.value);
  try {
    const signal = typeof AbortSignal !== "undefined" && typeof AbortSignal.timeout === "function"
      ? AbortSignal.timeout(15000)
      : undefined;
    const result = await validateGeneratorConfiguration(variant.value, configuration.value, { signal });
    if (!lifecycle.isCurrentPreflight(request)) return;
    preflight.value = result.valid === false
      ? { status: "invalid", message: "The configuration did not pass preflight." }
      : { status: "valid", message: "Preflight passed. Generation is enabled." };
    backendIssues.value = result.issues ?? [];
    if (result.valid !== false) lifecycle.acceptPreflight(request);
  } catch (cause) {
    if (!lifecycle.isCurrentPreflight(request)) return;
    backendIssues.value = cause.issues ?? [];
    const message = cause.name === "TimeoutError" || cause.name === "AbortError"
      ? "Preflight timed out after 15 seconds. Check the backend and try again."
      : cause.message;
    preflight.value = { status: "invalid", message };
    error.value = message;
  } finally {
    busy.value = false;
  }
}

function schedulePoll() {
  if (pollTimer !== null) window.clearTimeout(pollTimer);
  pollTimer = null;
  const runId = run.value?.runId;
  const token = runId ? lifecycle.beginRun(runId) : null;
  if (runId && operationActive.value) {
    pollTimer = window.setTimeout(() => pollRun(runId, token), 600);
  }
}

async function pollRun(runId, token) {
  if (!runId || !token || !lifecycle.isCurrentRun(token, runId) || run.value?.runId !== runId) return;
  try {
    const result = await fetchGeneratorRun(runId);
    if (!lifecycle.isCurrentRun(token, runId) || run.value?.runId !== runId) return;
    run.value = result;
  } catch (cause) {
    if (!lifecycle.isCurrentRun(token, runId) || run.value?.runId !== runId) return;
    error.value = cause.message;
  } finally {
    if (lifecycle.isCurrentRun(token, runId)) schedulePoll();
  }
}

async function generate() {
  if (!canGenerate.value) return;
  busy.value = true;
  error.value = "";
  try {
    run.value = await startGeneratorRun(variant.value, configuration.value);
    lifecycle.beginRun(run.value.runId);
    schedulePoll();
  } catch (cause) {
    if (cause.issues?.length) {
      backendIssues.value = cause.issues;
      preflight.value = { status: "invalid", message: cause.message };
    }
    error.value = cause.message;
  } finally {
    busy.value = false;
  }
}

function previewColumns(preview) {
  return preview.columns.map((key) => ({ key, label: key }));
}

async function exportPostgresql() {
  if (!secureExport.value) return;
  if (
    exportForm.value.replace &&
    !window.confirm(
      `Replace existing MTA-SIM tables in schema ${exportForm.value.schema}? ` +
        "This database operation cannot be undone from the dashboard.",
    )
  ) return;
  busy.value = true;
  error.value = "";
  try {
    const connection = {
      host: exportForm.value.host,
      port: exportForm.value.port,
      database: exportForm.value.database,
      user: exportForm.value.user,
      password: exportForm.value.password,
      sslmode: exportForm.value.sslmode,
      schema: exportForm.value.schema,
    };
    run.value = await exportGeneratorRun(
      run.value.runId,
      connection,
      exportForm.value.replace,
    );
    exportForm.value.password = "";
    schedulePoll();
  } catch (cause) {
    exportForm.value.password = "";
    error.value = cause.message;
  } finally {
    busy.value = false;
  }
}

onMounted(async () => {
  try {
    overview.value = await fetchGeneratorOverview();
    variant.value = overview.value.defaultVariant ?? "baseline";
    preset.value = overview.value.defaultPreset ?? "toy";
    setConfiguration(overview.value.configuration);
  } catch (cause) {
    error.value = cause.message;
  }
});

onUnmounted(() => {
  if (pollTimer !== null) window.clearTimeout(pollTimer);
  lifecycle.clearRun();
});
</script>

<template>
  <section class="page-grid generator-page">
    <p class="caption">
      Generate a validated synthetic dataset with the pinned MTA-SIM package.
      The browser edits configuration; only the backend runs simulation or storage.
    </p>

    <article v-if="overview && !overview.available" class="card empty-card">
      <h2>Data Generator is unavailable</h2>
      <p>{{ overview.reason }}</p>
    </article>

    <template v-else-if="overview">
      <article class="card">
        <div class="card-head">
          <h2>1. Configure generation</h2>
          <span class="sub">Self-contained JSON only</span>
        </div>
        <div class="card-body">
          <div class="form-grid">
            <div class="field">
              <label for="generator-variant">Generator variant</label>
              <select id="generator-variant" :value="variant" :disabled="busy || operationActive" @change="chooseVariant">
                <option v-for="item in overview.variants" :key="item.key" :value="item.key">
                  {{ item.key }}
                </option>
              </select>
            </div>
            <div class="field">
              <label for="generator-preset">Reviewed preset</label>
              <select id="generator-preset" :value="preset" :disabled="busy || operationActive" @change="choosePreset">
                <option v-for="item in availablePresets" :key="item.key" :value="item.key">
                  {{ item.label }}
                </option>
              </select>
            </div>
          </div>

          <GeneratorConfigEditor
            :key="editorKey"
            :model-value="configuration"
            :variant="variant"
            :backend-issues="backendIssues"
            :disabled="busy || operationActive"
            @update:model-value="updateConfiguration"
            @local-issues-change="updateLocalIssues"
            @dirty-change="configurationDirty = $event"
          />

          <p
            class="notice"
            :class="preflight.status === 'valid' ? 'good' : preflight.status === 'invalid' ? 'bad' : 'warn'"
          >{{ preflight.message }}</p>

          <div class="rec-actions">
            <button class="btn" :disabled="!canRunPreflight" @click="runPreflight">
              Run preflight
            </button>
            <button class="btn primary" :disabled="!canGenerate" @click="generate">
              Generate dataset
            </button>
          </div>
        </div>
      </article>

      <article v-if="run" class="card" aria-live="polite">
        <div class="card-head">
          <h2>2. Generation result</h2>
          <span class="tag" :class="run.status === 'completed' ? 'green' : run.status === 'failed' ? 'red' : 'amber'">
            {{ run.status }}
          </span>
        </div>
        <div class="card-body">
          <p><b>{{ run.phase }}</b></p>
          <p v-if="run.message" class="notice bad">{{ run.message }}</p>
          <div v-if="completed" class="metrics compact-metrics">
            <div class="metric"><label>Path rows</label><b>{{ run.summary.pathRows }}</b></div>
            <div class="metric"><label>Performance rows</label><b>{{ run.summary.performanceRows }}</b></div>
            <div class="metric"><label>Touchpoints</label><b>{{ run.summary.touchpoints }}</b></div>
            <div class="metric"><label>Marketplace</label><b>{{ run.summary.marketplace }}</b></div>
          </div>
        </div>
      </article>

      <article v-for="preview in run?.previews ?? []" :key="preview.key" class="card">
        <div class="card-head">
          <h2>{{ preview.label }}</h2>
          <span class="sub">First {{ preview.rows.length }} rows · maximum 20</span>
        </div>
        <div class="card-body">
          <DataTable :columns="previewColumns(preview)" :rows="preview.rows" />
        </div>
      </article>

      <article v-if="completed" class="card">
        <div class="card-head"><h2>3. Export generated data</h2></div>
        <div class="card-body">
          <h3>Download CSV</h3>
          <div class="rec-actions">
            <a
              v-for="file in run.downloads"
              :key="file.key"
              class="btn"
              :href="generatorDownloadUrl(run.runId, file.key)"
            >Download {{ file.name }}</a>
          </div>

          <h3>Export to PostgreSQL</h3>
          <div v-if="!secureExport" class="notice warn">
            PostgreSQL credentials are accepted only over HTTPS or localhost.
            This page is using insecure remote HTTP, so the credential form is not rendered.
          </div>
          <template v-else>
            <button class="btn" @click="exportOpen = !exportOpen">
              {{ exportOpen ? "Hide PostgreSQL form" : "Enter PostgreSQL credentials" }}
            </button>
            <div v-if="exportOpen" class="form-grid generator-export-form">
              <div class="field span-2"><label for="export-host">Host</label><input id="export-host" v-model="exportForm.host" type="text" /></div>
              <div class="field"><label for="export-port">Port</label><input id="export-port" v-model="exportForm.port" type="text" /></div>
              <div class="field"><label for="export-database">Database</label><input id="export-database" v-model="exportForm.database" type="text" /></div>
              <div class="field"><label for="export-user">User</label><input id="export-user" v-model="exportForm.user" type="text" /></div>
              <div class="field span-2"><label for="export-password">Password</label><input id="export-password" v-model="exportForm.password" type="password" autocomplete="new-password" /></div>
              <div class="field"><label for="export-ssl">SSL mode</label><select id="export-ssl" v-model="exportForm.sslmode"><option>require</option><option>verify-ca</option><option>verify-full</option></select></div>
              <div class="field"><label for="export-schema">Existing schema</label><input id="export-schema" v-model="exportForm.schema" type="text" /></div>
              <label class="toggle span-2"><input v-model="exportForm.replace" type="checkbox" /><span>Replace existing simulator tables<small>Requires a separate confirmation.</small></span></label>
              <div class="rec-actions span-2"><button class="btn primary" :disabled="busy || run.export.status === 'running'" @click="exportPostgresql">Export from backend</button></div>
            </div>
          </template>
          <p v-if="run.export.status !== 'idle'" class="notice" :class="run.export.status === 'failed' ? 'bad' : run.export.status === 'completed' ? 'good' : ''">
            {{ run.export.status }} — {{ run.export.message }}
          </p>
        </div>
      </article>
    </template>

    <p v-if="error" class="notice bad">{{ error }}</p>
  </section>
</template>
