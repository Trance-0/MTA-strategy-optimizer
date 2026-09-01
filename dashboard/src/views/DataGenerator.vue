<script setup>
/** Configure, run, preview, and export the pinned MTA-SIM generator. */
import { computed, onMounted, onUnmounted, ref } from "vue";

import DataTable from "../components/DataTable.vue";
import {
  exportGeneratorRun,
  fetchGeneratorOverview,
  fetchGeneratorPreset,
  fetchGeneratorRun,
  generatorDownloadUrl,
  startGeneratorRun,
} from "../api/client.js";

const overview = ref(null);
const variant = ref("baseline");
const preset = ref("toy");
const editorMode = ref("guided");
const configuration = ref({});
const editorText = ref("{}");
const editorError = ref("");
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

const marketplace = computed(() => configuration.value.marketplaces?.[0] ?? {});
const availablePresets = computed(
  () => overview.value?.variants?.find((item) => item.key === variant.value)?.presets ?? [],
);
const running = computed(() => ["queued", "running"].includes(run.value?.status));
const completed = computed(() => run.value?.status === "completed");
const secureExport = computed(() =>
  window.location.protocol === "https:" ||
  ["localhost", "127.0.0.1", "::1"].includes(window.location.hostname),
);

function setConfiguration(value) {
  configuration.value = JSON.parse(JSON.stringify(value ?? {}));
  editorText.value = JSON.stringify(configuration.value, null, 2);
  editorError.value = "";
}

function parseEditor() {
  try {
    const value = JSON.parse(editorText.value);
    if (!value || Array.isArray(value) || typeof value !== "object") {
      throw new Error("The configuration must be a JSON object.");
    }
    configuration.value = value;
    editorError.value = "";
    return true;
  } catch (cause) {
    editorError.value = cause.message;
    return false;
  }
}

function formatEditor() {
  if (!parseEditor()) return;
  editorText.value = JSON.stringify(configuration.value, null, 2);
}

function chooseMode(mode) {
  if (mode === "guided" && !parseEditor()) return;
  if (mode === "json") editorText.value = JSON.stringify(configuration.value, null, 2);
  editorMode.value = mode;
}

async function loadPreset() {
  busy.value = true;
  error.value = "";
  try {
    const result = await fetchGeneratorPreset(variant.value, preset.value);
    setConfiguration(result.configuration);
    run.value = null;
  } catch (cause) {
    error.value = cause.message;
  } finally {
    busy.value = false;
  }
}

function schedulePoll() {
  if (pollTimer !== null) window.clearTimeout(pollTimer);
  pollTimer = null;
  if (running.value || run.value?.export?.status === "running") {
    pollTimer = window.setTimeout(pollRun, 600);
  }
}

async function pollRun() {
  try {
    run.value = await fetchGeneratorRun(run.value.runId);
  } catch (cause) {
    error.value = cause.message;
  } finally {
    schedulePoll();
  }
}

async function generate() {
  if (editorMode.value === "json" && !parseEditor()) return;
  busy.value = true;
  error.value = "";
  try {
    run.value = await startGeneratorRun(variant.value, configuration.value);
    schedulePoll();
  } catch (cause) {
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
              <select id="generator-variant" v-model="variant" @change="loadPreset">
                <option v-for="item in overview.variants" :key="item.key" :value="item.key">
                  {{ item.key }}
                </option>
              </select>
            </div>
            <div class="field">
              <label for="generator-preset">Reviewed preset</label>
              <select id="generator-preset" v-model="preset" @change="loadPreset">
                <option v-for="item in availablePresets" :key="item.key" :value="item.key">
                  {{ item.label }}
                </option>
              </select>
            </div>
          </div>

          <div class="tabs editor-mode-tabs" role="tablist">
            <button class="tab" :class="{ active: editorMode === 'guided' }" @click="chooseMode('guided')">
              Guided editor
            </button>
            <button class="tab" :class="{ active: editorMode === 'json' }" @click="chooseMode('json')">
              JSON configuration
            </button>
          </div>

          <div v-if="editorMode === 'guided'" class="form-grid generator-guided">
            <div class="field">
              <label for="generator-seed">Random seed</label>
              <input id="generator-seed" v-model.number="configuration.seed" type="number" step="1" />
            </div>
            <div class="field span-2">
              <label for="generator-advertiser">Synthetic advertiser identifier</label>
              <input id="generator-advertiser" v-model="configuration.advertiser_id" type="text" />
            </div>
            <div class="field">
              <label for="generator-start">Report start</label>
              <input id="generator-start" v-model="configuration.report_start_date" type="date" />
            </div>
            <div class="field">
              <label for="generator-end">Report end</label>
              <input id="generator-end" v-model="configuration.report_end_date" type="date" />
            </div>
            <div class="field">
              <label for="generator-market">Marketplace</label>
              <input id="generator-market" v-model="marketplace.code" type="text" />
            </div>
            <div class="field">
              <label for="generator-currency">ISO currency</label>
              <input id="generator-currency" v-model="marketplace.currency_code" type="text" />
            </div>
            <div class="field">
              <label for="generator-price">Base product price</label>
              <input id="generator-price" v-model.number="configuration.base_product_price" type="number" min="0" step="0.01" />
            </div>
            <div class="field">
              <label for="generator-replications">Campaign replications</label>
              <input id="generator-replications" v-model.number="configuration.campaign_replications" type="number" min="1" :max="overview.limits?.campaignReplications" step="1" />
            </div>
          </div>

          <div v-else class="generator-json-editor">
            <textarea
              v-model="editorText"
              aria-label="MTA-SIM JSON configuration"
              spellcheck="false"
              rows="24"
            ></textarea>
            <div class="rec-actions">
              <button class="btn" @click="formatEditor">Validate and format JSON</button>
            </div>
            <p v-if="editorError" class="notice bad">{{ editorError }}</p>
          </div>

          <div class="rec-actions">
            <button class="btn primary" :disabled="busy || running" @click="generate">
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
