<script setup>
/**
 * The routed Settings page behind the rail's final destination.
 *
 * Four tabs: basic deployment identity, a database doctor, the request log,
 * and queued backend tasks. The published build renders
 * neither mutable form -- it has no writable
 * `.env` and no socket, so offering a credential field there would invite a
 * real password into a page that could never use it -- and states the local-run
 * instructions instead.
 *
 * The password field is write-only. The server never sends a stored password
 * back, and leaving the field blank keeps the stored one rather than clearing
 * it, so the value is never rendered into the page.
 */
import { computed, onMounted, onUnmounted, ref } from "vue";
import { useWorkbench } from "../lib/useWorkbench.js";
const { available: storageAvailable, catalogueError: storageError, reason: storageReason, refreshDatasets, refreshCapabilities, runtime } = useWorkbench();

import LogViewer from "../components/LogViewer.vue";
import BackendTasks from "../components/BackendTasks.vue";
import {
  fetchSchemaOperation,
  fetchSettings,
  postSettings,
  selectRuntimeSchema,
  startSchemaOperation,
  stopSchemaOperation,
} from "../api/client.js";
import { useDiagnostics } from "../lib/diagnostics.js";
import { DOCS_URL, REPO_URL } from "../pages.js";

const { diagnosticsOn, setDiagnostics } = useDiagnostics();

const props = defineProps({
  section: { type: String, default: "general" },
});

const emit = defineEmits(["changed", "reload", "navigate"]);

const tab = computed(() => props.section);
const state = ref(null);
const busy = ref(false);
const message = ref(null);
const focusedTaskId = ref("");

const form = ref({
  useDatabase: false,
  PG_HOST: "",
  PG_PORT: "5432",
  PG_DATABASE: "",
  PG_USER: "",
  PG_PASSWORD: "",
  PG_SSLMODE: "prefer",
  PG_SCHEMA: "public",
});

const SSL_MODES = ["disable", "allow", "prefer", "require", "verify-ca", "verify-full"];
const LOG_LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR"];
const displayLevel = ref("DEBUG");
const displaySource = ref("all");

const logSources = computed(() => [
  "all",
  ...new Set((state.value?.logging?.records ?? []).map((record) => record.source)),
]);
const visibleRecords = computed(() =>
  (state.value?.logging?.records ?? []).filter(
    (record) =>
      LOG_LEVELS.indexOf(record.level) >= LOG_LEVELS.indexOf(displayLevel.value) &&
      (displaySource.value === "all" || record.source === displaySource.value),
  ),
);

const hosted = computed(() => state.value?.hosted ?? false);
const readOnly = computed(() => hosted.value || (state.value?.readOnly ?? false));
const frontendIdentity = Object.freeze({
  version: __DASHBOARD_VERSION__,
  commit: __DASHBOARD_COMMIT__,
});
const backendIdentity = computed(() => state.value?.backendIdentity ?? null);

function knownIdentity(value) {
  return Boolean(value && value !== "unknown");
}

const identityStatus = computed(() => {
  const backend = backendIdentity.value;
  if (!backend) {
    return {
      tone: "neutral",
      label: "Backend not connected",
      detail: "This dashboard build has no live backend identity to compare.",
    };
  }
  const values = [
    frontendIdentity.version,
    frontendIdentity.commit,
    backend.version,
    backend.commit,
  ];
  if (!values.every(knownIdentity)) {
    return {
      tone: "warning",
      label: "Identity incomplete",
      detail: "At least one build did not receive complete version or commit metadata.",
    };
  }
  if (
    frontendIdentity.version !== backend.version ||
    frontendIdentity.commit !== backend.commit
  ) {
    return {
      tone: "bad",
      label: "Build mismatch",
      detail: "The dashboard and backend came from different project builds.",
    };
  }
  return {
    tone: "good",
    label: "Builds match",
    detail: "The dashboard and backend report the same version and commit.",
  };
});

/**
 * The schemas the connected server offers.
 *
 * Held apart from `state` because a connection test refreshes it without
 * refreshing anything else: the reader edits the host, tests, and the list
 * becomes that server's rather than the saved one's.
 */
const schemas = ref({ schemas: [], selected: "public", error: null });
const inspectedSchema = ref("");
const setupSchema = ref("");
const newSchema = ref("");
const replaceSchemas = ref(false);
const schemaOperation = ref({ current: null });
const pendingSchema = ref(null);
let operationTimer = null;

const setupOption = computed(() =>
  (schemas.value.schemas ?? []).find((item) => item.name === setupSchema.value),
);
const inspectedOption = computed(() =>
  schemaOptions.value.find((item) => item.name === inspectedSchema.value),
);
const operation = computed(() => schemaOperation.value.current);
const operationRunning = computed(() =>
  ["queued", "running", "stopping"].includes(operation.value?.state),
);

/**
 * Whether setup is offered at all, as the server reports it.
 *
 * Read from the poll rather than reconstructed from `hosted` and `readOnly`.
 * Protected configuration governs credentials, not the data in the database
 * the platform already pointed this service at, so a dialog that inferred the
 * rule from `readOnly` would hide the only remedy a reader with no shell has
 * on exactly the deployment where they have no shell.
 */
const setupAvailable = computed(() => schemaOperation.value.available === true);
const setupReason = computed(() => schemaOperation.value.reason ?? "");
const doctorSteps = computed(() => {
  const census = schemas.value ?? {};
  const active = (census.schemas ?? []).find((item) => item.name === census.selected);
  const connected = state.value?.useDatabase && !String(state.value?.status?.detail ?? "").includes("Unavailable");
  const inspected = connected && !census.error && (census.schemas ?? []).length > 0;
  const importing = ["queued", "running", "stopping"].includes(operation.value?.state);
  return [
    { number: 1, label: "Connect", state: connected ? "complete" : "current" },
    { number: 2, label: "Inspect", state: inspected ? "complete" : connected ? "current" : "blocked" },
    { number: 3, label: "Import", state: importing ? "current" : active?.selectable ? "optional" : inspected ? "current" : "blocked" },
    { number: 4, label: "Verify", state: active?.selectable && !importing ? "complete" : importing ? "blocked" : "current" },
  ];
});

/**
 * Whether the entered connection is the saved one.
 *
 * Setup always runs against what is in `.env`, so unsaved edits would target a
 * different server than the fields on screen describe. On a protected
 * deployment nothing here can be edited in the first place, so there is
 * nothing to be out of step with and the check does not apply.
 */
const connectionSaved = computed(() => {
  if (!state.value?.useDatabase) return false;
  if (readOnly.value) return true;
  if (form.value.PG_PASSWORD) return false;
  const saved = state.value.connection ?? {};
  return ["PG_HOST", "PG_PORT", "PG_DATABASE", "PG_USER", "PG_SSLMODE", "PG_SCHEMA"].every(
    (key) => String(form.value[key] ?? "") === String(saved[key] ?? ""),
  );
});

/** Setup is reachable whenever the server would accept it and a target is known. */
const setupReady = computed(() => setupAvailable.value && connectionSaved.value);

/**
 * The stored schema, kept as an option even when the list does not contain it.
 *
 * A database that is unreachable enumerates nothing, and a dropdown that
 * silently dropped the saved value would show the reader a selection they
 * never made and save it on the next write.
 */
const schemaOptions = computed(() => {
  const listed = schemas.value.schemas ?? [];
  const current = form.value.PG_SCHEMA;
  if (!current || listed.some((item) => item.name === current)) return listed;
  return [
    {
      name: current,
      databaseRevision: "not tracked",
      selectable: true,
      tableCount: null,
      missingTables: [],
      missingCount: 0,
      detail: schemas.value.error
        ? `Saved selection. The schema list is unavailable — ${schemas.value.error}`
        : "Saved selection. Test the connection to list the schemas this server offers.",
    },
    ...listed,
  ];
});

/** The help text under the dropdown: whichever schema the pointer is over. */
const hoveredSchema = ref(null);
const describedSchema = computed(() => {
  const name = hoveredSchema.value ?? form.value.PG_SCHEMA;
  return schemaOptions.value.find((item) => item.name === name) ?? null;
});

function schemaTitle(option) {
  if (option.selectable) return option.detail;
  const missing = option.missingTables.length
    ? ` Missing: ${option.missingTables.join(", ")}${
        option.missingCount > option.missingTables.length
          ? ` and ${option.missingCount - option.missingTables.length} more`
          : ""
      }.`
    : "";
  return `Unavailable. ${option.detail}${missing}`;
}

function schemaKind(option) {
  return {
    dashboard: "dashboard-ready",
    source: "parse-ready source",
    partial_source: "partial source",
    empty: "empty",
    other: "other application",
  }[option.kind] ?? "unclassified";
}

function chooseSetupDefault() {
  const listed = schemas.value.schemas ?? [];
  const inspectable = schemaOptions.value;
  if (!inspectable.some((item) => item.name === inspectedSchema.value)) {
    inspectedSchema.value =
      inspectable.find((item) => item.selected)?.name ??
      form.value.PG_SCHEMA ??
      inspectable[0]?.name ??
      "";
  }
  if (!listed.some((item) => item.name === setupSchema.value)) {
    setupSchema.value =
      listed.find((item) => item.canDerive)?.name ??
      listed.find((item) => item.canInitialize)?.name ??
      listed[0]?.name ??
      "";
  }
}

function inspectSchema() {
  proposeSchemaSelection(inspectedSchema.value);
}

function chooseDashboardSchema() {
  proposeSchemaSelection(form.value.PG_SCHEMA);
}

function proposeSchemaSelection(name) {
  const option = schemaOptions.value.find((item) => item.name === name);
  if (option?.selectable && option.name !== schemas.value.selected) {
    pendingSchema.value = option;
  }
}

function cancelSchemaSelection() {
  inspectedSchema.value = schemas.value.selected ?? form.value.PG_SCHEMA;
  form.value.PG_SCHEMA = schemas.value.selected ?? form.value.PG_SCHEMA;
  pendingSchema.value = null;
}

async function confirmSchemaSelection() {
  const target = pendingSchema.value;
  if (!target) return;
  busy.value = true;
  message.value = null;
  try {
    state.value = await selectRuntimeSchema(target.name);
    schemas.value = state.value.schemas;
    form.value.PG_SCHEMA = state.value.connection?.PG_SCHEMA ?? target.name;
    inspectedSchema.value = target.name;
    pendingSchema.value = null;
    message.value = {
      ok: true,
      text: `Schema ${target.name} is active. Reloading every dashboard view.`,
    };
    emit("changed");
  } catch (cause) {
    message.value = { ok: false, text: `${cause.name}: ${cause.message}` };
    cancelSchemaSelection();
  } finally {
    busy.value = false;
  }
}

function requestReload() {
  emit("reload");
  message.value = { ok: true, text: "Reloading data from the active source." };
}

function navigate(nextTab) {
  emit("navigate", nextTab);
}

function scheduleOperationPoll() {
  if (operationTimer !== null) window.clearTimeout(operationTimer);
  operationTimer = null;
  if (operationRunning.value) {
    operationTimer = window.setTimeout(refreshOperation, 900);
  }
}

async function refreshOperation() {
  const previous = operation.value;
  try {
    schemaOperation.value = await fetchSchemaOperation();
    const current = operation.value;
    if (previous?.state === "running" && current?.state === "succeeded") {
      await refreshSchemaCensus();
    }
  } catch (error) {
    message.value = { ok: false, text: `${error.name}: ${error.message}` };
  } finally {
    scheduleOperationPoll();
  }
}

/**
 * Re-enumerate the schemas after setup has changed what the server holds.
 *
 * A connection test is how the census is refreshed while credentials are being
 * edited, because it asks the server the reader just typed. A protected
 * deployment refuses that route and has nothing unsaved to ask about, so its
 * census is re-read from the settings state instead.
 */
async function refreshSchemaCensus() {
  if (readOnly.value) {
    state.value = await fetchSettings();
    if (state.value.schemas) schemas.value = state.value.schemas;
    chooseSetupDefault();
    return;
  }
  const result = await postSettings({
    action: "test",
    useDatabase: form.value.useDatabase,
    connection: connectionPayload(),
  });
  if (result.schemas) {
    schemas.value = result.schemas;
    chooseSetupDefault();
  }
}

async function refresh() {
  state.value = await fetchSettings();
  if (state.value.connection) {
    form.value = {
      useDatabase: state.value.useDatabase,
      ...state.value.connection,
      PG_PASSWORD: "",
    };
  }
  if (state.value.schemas) schemas.value = state.value.schemas;
  chooseSetupDefault();
  await refreshOperation();
}

onMounted(() => {
  message.value = null;
  refresh();
  refreshDatasets();
  refreshCapabilities();
});

onUnmounted(() => {
  if (operationTimer !== null) window.clearTimeout(operationTimer);
});

function connectionPayload() {
  return {
    PG_HOST: form.value.PG_HOST,
    PG_PORT: form.value.PG_PORT,
    PG_DATABASE: form.value.PG_DATABASE,
    PG_USER: form.value.PG_USER,
    PG_PASSWORD: form.value.PG_PASSWORD,
    PG_SSLMODE: form.value.PG_SSLMODE,
    PG_SCHEMA: form.value.PG_SCHEMA,
  };
}

async function send(action, extra = {}) {
  busy.value = true;
  message.value = null;
  try {
    const result = await postSettings({
      action,
      useDatabase: form.value.useDatabase,
      connection: connectionPayload(),
      ...extra,
    });
    if (action === "test") {
      message.value = { ok: result.ok, text: result.message };
      // A successful test is the only moment the schema list is knowable, so
      // it fills the dropdown from the server the reader just reached rather
      // than from the one that happens to be saved.
      if (result.schemas) schemas.value = result.schemas;
      chooseSetupDefault();
    } else if (action === "save") {
      message.value = {
        ok: result.ok !== false,
        text:
          result.message ??
          "Saved to .env and caches cleared. Dashboard data is reloading.",
      };
      await refresh();
      emit("changed");
    } else {
      state.value = result;
    }
  } catch (error) {
    message.value = { ok: false, text: `${error.name}: ${error.message}` };
  } finally {
    busy.value = false;
  }
}

async function runSchemaOperation(action) {
  const schema =
    action === "initialize" && newSchema.value.trim()
      ? newSchema.value.trim()
      : setupSchema.value;
  if (!schema) {
    message.value = { ok: false, text: "Choose or enter a schema first." };
    return;
  }
  if (
    replaceSchemas.value &&
    !window.confirm(
      action === "derive"
        ? `Replace any existing derived target schemas while parsing ${schema}? ` +
            "The source stays read-only, but target replacement cannot be undone " +
            "from the dashboard."
        : `Rebuild dashboard schema ${schema}? Existing target tables will be ` +
            "replaced and cannot be restored from the dashboard.",
    )
  ) {
    return;
  }
  busy.value = true;
  message.value = null;
  try {
    schemaOperation.value = await startSchemaOperation(
      action,
      schema,
      replaceSchemas.value,
    );
    focusedTaskId.value = String(schemaOperation.value.current?.id ?? "");
    navigate("tasks");
    scheduleOperationPoll();
  } catch (error) {
    message.value = { ok: false, text: `${error.name}: ${error.message}` };
  } finally {
    busy.value = false;
  }
}

async function stopSchemaSetup() {
  busy.value = true;
  try {
    schemaOperation.value = await stopSchemaOperation();
  } catch (error) {
    message.value = { ok: false, text: `${error.name}: ${error.message}` };
  } finally {
    busy.value = false;
    scheduleOperationPoll();
  }
}

function toggleLogging(enabled) {
  send("logging", { logging: { enabled, level: state.value?.logging?.level ?? "INFO" } });
}

function setLevel(level) {
  send("logging", {
    logging: { enabled: state.value?.logging?.enabled ?? false, level },
  });
}

</script>

<template>
  <section class="settings-page card" aria-label="Settings">
      <div class="tabs settings-tabs" role="tablist" aria-label="Settings sections">
        <button
          class="tab"
          role="tab"
          :aria-selected="tab === 'general'"
          :class="{ active: tab === 'general' }"
          @click="navigate('general')"
        >
          General
        </button>
        <button
          class="tab"
          role="tab"
          :aria-selected="tab === 'source'"
          :class="{ active: tab === 'source' }"
          @click="navigate('source')"
        >
          Data source
        </button>
        <button
          class="tab"
          role="tab"
          :aria-selected="tab === 'logging'"
          :class="{ active: tab === 'logging' }"
          @click="navigate('logging')"
        >
          Logging
        </button>
        <button
          class="tab"
          role="tab"
          :aria-selected="tab === 'tasks'"
          :class="{ active: tab === 'tasks' }"
          @click="navigate('tasks')"
        >
          Tasks
        </button>
      </div>

      <div class="settings-body modal-body">
        <!--
          Six read-only values rather than six options, but the same row: the
          name on the left, the value on the right. A reader who has learned
          where to look on the tabs that do offer controls finds the same
          arrangement here, and the group header carries the one sentence that
          explains all six, so no individual row needs helper text of its own.
        -->
        <section
          v-if="tab === 'general'"
          class="setting-group"
          aria-label="Deployment identity"
        >
          <header>
            <div>
              <h3>Deployment identity</h3>
              <p class="caption">Compare independently built frontend and backend artifacts.</p>
            </div>
            <span class="identity-status" :class="identityStatus.tone">
              {{ identityStatus.label }}
            </span>
          </header>
          <div class="setting-row">
            <span class="setting-label">Dashboard version</span>
            <span class="setting-control"><code>{{ frontendIdentity.version }}</code></span>
          </div>
          <div class="setting-row">
            <span class="setting-label">Dashboard commit SHA</span>
            <span class="setting-control"><code>{{ frontendIdentity.commit }}</code></span>
          </div>
          <div class="setting-row">
            <span class="setting-label">Backend version</span>
            <span class="setting-control">
              <code>{{ backendIdentity?.version ?? "not connected" }}</code>
            </span>
          </div>
          <div class="setting-row">
            <span class="setting-label">Backend commit SHA</span>
            <span class="setting-control">
              <code>{{ backendIdentity?.commit ?? "not connected" }}</code>
            </span>
          </div>
          <div class="setting-row">
            <span class="setting-label">Backend Python</span>
            <span class="setting-control">
              <code>{{ backendIdentity?.runtime?.python ?? "not connected" }}</code>
            </span>
          </div>
          <div class="setting-row">
            <span class="setting-label">Backend Flask</span>
            <span class="setting-control">
              <code>{{ backendIdentity?.runtime?.flask ?? "not connected" }}</code>
            </span>
          </div>
          <p class="setting-block caption">{{ identityStatus.detail }}</p>
        </section>

        <template v-else-if="tab === 'source'">
          <section class="panel"><h3>Analysis storage and model readiness</h3>
            <p>{{ storageAvailable ? 'Dataset catalogue is readable.' : 'Dataset catalogue is unavailable.' }} {{ storageReason || storageError }}</p>
            <p>{{ runtime.storageAvailable ? 'Runtime storage is writable.' : 'Runtime storage is not writable.' }} {{ runtime.storageReason }}</p>
            <p>Model availability depends on the selected dataset and server execution settings. Missing research or paths disables only the affected analysis.</p>
            <p>{{ runtime.executionAvailable ? 'Server model execution is enabled.' : runtime.executionReason }}</p>
            <div class="rec-actions"><button class="btn" @click="Promise.all([refreshDatasets(), refreshCapabilities()])">Check analysis storage</button><a class="btn" href="#/generator/import">Import data</a><a class="btn" href="#/optimizer/optimization">Model controls</a></div>
          </section>
          <div class="doctor-steps" aria-label="Database setup steps">
            <span v-for="step in doctorSteps" :key="step.number" :class="step.state">
              <b>{{ step.number }}</b>
              <span>{{ step.label }}<small>{{ step.state }}</small></span>
            </span>
          </div>
          <!--
            The active source and the two options that apply to every
            deployment, including the published build where nothing else on
            this tab can be changed. Diagnostics is a view preference rather
            than a deployment setting, which is why it is offered here and not
            beside the connection fields.
          -->
          <section class="setting-group" aria-label="Active source">
            <header v-if="state">
              <div>
                <h3>{{ state.status.label }}</h3>
                <p class="caption">{{ state.status.detail }}</p>
              </div>
            </header>
            <div v-if="!hosted" class="setting-row">
              <span class="setting-label">
                Reload data
                <small>
                  Clears the backend and browser caches and reads the selected
                  schema again. Use it after an import, or when a view is
                  showing data older than the source.
                </small>
              </span>
              <span class="setting-control">
                <button class="btn" :disabled="busy" @click="requestReload">Reload data</button>
              </span>
            </div>
            <label class="setting-row toggle">
              <span class="setting-label">
                Show data run diagnostics
                <small>
                  Adds a Budget Manager section describing how the current data
                  run was produced — its run identifier, seed, and configuration
                  checksum. Off by default: it answers an engineering question
                  about the pipeline, not a question about the advertising
                  account.
                </small>
              </span>
              <span class="setting-control">
                <input
                  class="switch"
                  type="checkbox"
                  :checked="diagnosticsOn"
                  @change="setDiagnostics($event.target.checked)"
                />
              </span>
            </label>
          </section>

          <template v-if="hosted">
            <div class="notice">
              <b>This published build reads the repository's committed sample
              files.</b>
              It runs as static assets with no server behind it, so it cannot
              open a database connection and the connection settings are
              available only in a local run.
            </div>
            <p>Run it locally against your own PostgreSQL mirror:</p>
            <pre><code>git clone {{ REPO_URL }}.git
cd MTA-strategy-optimizer
cp sample.env .env      # set DATABASE=true and the PG_* values
./dashboard/run.sh      # dashboard\run.bat on Windows</code></pre>
            <p class="caption">
              The import command that populates the mirror is
              <code>uv run --extra dashboard python -m backend.import_to_database</code>.
              The specification is at <a :href="DOCS_URL" target="_blank" rel="noopener">the
              documentation site</a>.
            </p>
          </template>

          <template v-else-if="state?.readOnly">
            <div class="notice">
              <b>This server reads protected deployment configuration.</b>
              This page cannot change the server's credentials — change those in
              the deployment environment and restart the service. Which schema is
              loaded, and setting one up, remain available below: neither
              rewrites a credential.
            </div>

            <section class="setting-group" aria-label="Step 2 — Inspect database schemas">
              <header>
                <div>
                  <h3>Step 2 — Inspect database schemas</h3>
                  <p class="caption">
                    Source and incomplete schemas stay inspectable but cannot be
                    activated.
                  </p>
                </div>
              </header>
              <div class="setting-row">
                <label class="setting-label" for="protected-schema">
                  Schema inventory
                  <small>
                    Selecting a dashboard-ready schema opens a confirmation
                    window and loads its actual data.
                  </small>
                </label>
                <span class="setting-control">
                  <select id="protected-schema" v-model="inspectedSchema" @change="inspectSchema">
                    <option
                      v-for="option in schemaOptions"
                      :key="option.name"
                      :value="option.name"
                    >
                      {{ option.name }}{{ option.selected ? " — active" : "" }}
                      — database {{ option.databaseRevision ?? "not tracked" }}
                    </option>
                  </select>
                </span>
              </div>
              <div class="setting-block">
                <p v-if="inspectedOption" class="caption schema-help">
                  <b>{{ inspectedOption.name }}</b> — {{ schemaKind(inspectedOption) }};
                  database structure <b>{{ inspectedOption.databaseRevision ?? "not tracked" }}</b>.
                  {{ inspectedOption.detail }}
                </p>
                <p v-if="state.configuredSchema !== schemas.selected" class="caption">
                  Runtime selection only. A server restart returns to configured
                  schema <code>{{ state.configuredSchema }}</code>.
                </p>
                <div v-if="message" class="notice" :class="message.ok ? 'good' : 'bad'">
                  {{ message.text }}
                </div>
                <p v-else class="caption schema-help">
                  <template v-if="schemas.error">
                    The schema list is unavailable — {{ schemas.error }}
                  </template>
                  <template v-else>No readable schemas were returned.</template>
                </p>
              </div>
            </section>
          </template>

          <template v-else-if="state">
            <section class="setting-group" aria-label="Step 1 — Connect PostgreSQL">
              <header>
                <div>
                  <h3>Step 1 — Connect PostgreSQL</h3>
                  <p class="caption">
                    Where this server reads the advertising account from.
                  </p>
                </div>
              </header>

              <label class="setting-row toggle">
                <span class="setting-label">
                  Read from the database
                  <small>
                    Off reads the committed CSV and JSON artifacts, which needs
                    no database at all. On reads the imported PostgreSQL mirror.
                  </small>
                </span>
                <span class="setting-control">
                  <input v-model="form.useDatabase" class="switch" type="checkbox" />
                </span>
              </label>

              <!--
                Host through SSL mode carry no helper text. Each names a
                standard PostgreSQL connection parameter whose meaning the
                field label already gives in full, and a sentence under every
                one of them would bury the two rows that do say something a
                reader cannot infer -- the write-only password and the schema
                selection.
              -->
              <div class="setting-row">
                <label class="setting-label" for="pg-host">Host</label>
                <span class="setting-control">
                  <input id="pg-host" v-model="form.PG_HOST" type="text" />
                </span>
              </div>
              <div class="setting-row">
                <label class="setting-label" for="pg-port">Port</label>
                <span class="setting-control">
                  <input id="pg-port" v-model="form.PG_PORT" type="text" />
                </span>
              </div>
              <div class="setting-row">
                <label class="setting-label" for="pg-database">Database</label>
                <span class="setting-control">
                  <input id="pg-database" v-model="form.PG_DATABASE" type="text" />
                </span>
              </div>
              <div class="setting-row">
                <label class="setting-label" for="pg-user">User</label>
                <span class="setting-control">
                  <input id="pg-user" v-model="form.PG_USER" type="text" />
                </span>
              </div>
              <div class="setting-row">
                <label class="setting-label" for="pg-password">
                  Password
                  <small>
                    Write-only. The stored password is never sent back to this
                    page, so leaving the field blank keeps it rather than
                    clearing it.
                  </small>
                </label>
                <span class="setting-control">
                  <input
                    id="pg-password"
                    v-model="form.PG_PASSWORD"
                    type="password"
                    autocomplete="new-password"
                    :placeholder="
                      state.connection?.passwordStored
                        ? 'Stored — leave blank to keep it'
                        : 'Not set'
                    "
                  />
                </span>
              </div>
              <div class="setting-row">
                <label class="setting-label" for="pg-sslmode">SSL mode</label>
                <span class="setting-control">
                  <select id="pg-sslmode" v-model="form.PG_SSLMODE">
                    <option v-for="mode in SSL_MODES" :key="mode" :value="mode">
                      {{ mode }}
                    </option>
                  </select>
                </span>
              </div>

              <div class="setting-block rec-actions">
                <button class="btn" :disabled="busy" @click="send('test')">
                  Test connection
                </button>
                <button class="btn primary" :disabled="busy" @click="send('save')">
                  Save to .env
                </button>
              </div>

              <div class="setting-block">
                <div v-if="message" class="notice" :class="message.ok ? 'good' : 'bad'">
                  {{ message.text }}
                </div>
                <p class="caption">
                  Credentials are written to <code>.env</code> at the repository
                  root, which is git-ignored. <code>sample.env</code> is the
                  tracked template and must never hold a real credential.
                </p>
              </div>
            </section>

            <section class="setting-group" aria-label="Step 2 — Inspect and select schema">
              <header>
                <div>
                  <h3>Step 2 — Inspect and select schema</h3>
                  <p class="caption">
                    Which schema on the connected database every view reads.
                  </p>
                </div>
              </header>
              <div class="setting-row">
                <label class="setting-label" for="pg-schema">
                  Dashboard schema
                  <small>
                    A schema that cannot serve the dashboard is listed and
                    disabled rather than omitted, so its absence is accounted
                    for where it would have been chosen.
                  </small>
                </label>
                <!--
                  The option tooltip is the browser's own and some do not show
                  it over an open dropdown, so the caption below carries the
                  same explanation unconditionally rather than depending on a
                  hover that may never arrive.
                -->
                <span class="setting-control">
                  <select
                    id="pg-schema"
                    v-model="form.PG_SCHEMA"
                    aria-describedby="pg-schema-help"
                    @change="chooseDashboardSchema"
                    @mouseleave="hoveredSchema = null"
                  >
                    <option
                      v-for="option in schemaOptions"
                      :key="option.name"
                      :value="option.name"
                      :disabled="!option.selectable"
                      :title="schemaTitle(option)"
                      @mouseenter="hoveredSchema = option.name"
                    >
                      {{ option.name }} — database
                      {{ option.databaseRevision ?? "not tracked" }}{{
                        option.selectable ? "" : " — unavailable"
                      }}
                    </option>
                  </select>
                </span>
              </div>
              <div class="setting-block">
                <p v-if="describedSchema" id="pg-schema-help" class="caption schema-help">
                  <b>{{ describedSchema.name }}</b> — {{ describedSchema.detail }}
                  <template v-if="describedSchema.missingTables.length">
                    <br />
                    Missing:
                    <code>{{ describedSchema.missingTables.join(", ") }}</code
                    ><template
                      v-if="describedSchema.missingCount > describedSchema.missingTables.length"
                    >
                      and
                      {{ describedSchema.missingCount - describedSchema.missingTables.length }}
                      more</template
                    >.
                  </template>
                </p>
                <p v-else id="pg-schema-help" class="caption schema-help">
                  <template v-if="schemas.error">
                    The schema list is unavailable — {{ schemas.error }}
                  </template>
                  <template v-else>
                    Test the connection to list the schemas this server offers.
                  </template>
                </p>
              </div>
            </section>
          </template>

          <!--
            Outside the three branches above rather than inside the writable
            one, which is where it used to be and where a protected deployment
            never reached it. Setup writes tables into the database this
            service was already pointed at; it rewrites no credential, so it is
            not what `readOnly` governs, and hiding it there left the readers
            with no shell -- the deployed ones -- with no way to populate a
            schema at all. `setupAvailable` comes from the server, so the
            buttons and the route cannot disagree.
          -->
          <template v-if="!hosted && state">
            <section class="setting-group" aria-label="Schema setup">
              <header>
                <div>
                  <h3>Schema setup</h3>
                  <p class="caption">
                    <b>Step 3 — Import data.</b> Build or populate a schema on
                    the connected database. A source schema stays unchanged and
                    produces one dashboard schema per scenario; an empty schema
                    can receive the committed sample account.
                  </p>
                </div>
              </header>

              <div
                v-if="!state.useDatabase || !setupAvailable || !connectionSaved"
                class="setting-block"
              >
                <p v-if="!state.useDatabase" class="notice">
                  Setup needs database mode. Turn on <b>Read from the database</b>
                  above, save the connection, then return here.
                </p>
                <p v-else-if="!setupAvailable" class="notice">
                  {{ setupReason || "This server does not offer schema setup." }}
                </p>
                <p v-else class="notice">
                  Save the database connection and active schema before running
                  setup. Operations always use the saved connection.
                </p>
              </div>

              <template v-if="state.useDatabase">
                <div class="setting-row">
                  <label class="setting-label" for="setup-schema">
                    Existing schema
                    <small>The schema the operation reads or writes.</small>
                  </label>
                  <span class="setting-control">
                    <select id="setup-schema" v-model="setupSchema">
                      <option
                        v-for="option in schemas.schemas"
                        :key="option.name"
                        :value="option.name"
                      >
                        {{ option.name }} — {{ schemaKind(option) }}
                      </option>
                    </select>
                  </span>
                </div>
                <div class="setting-row">
                  <label class="setting-label" for="new-schema">
                    New schema name
                    <small>
                      Optional. Set it to initialize the committed sample
                      account into a schema that does not exist yet.
                    </small>
                  </label>
                  <span class="setting-control">
                    <input
                      id="new-schema"
                      v-model="newSchema"
                      type="text"
                      placeholder="Optional target"
                    />
                  </span>
                </div>

                <label class="setting-row toggle">
                  <span class="setting-label">
                    Replace existing target tables
                    <small>
                      Off is safe for first runs. On requires confirmation and
                      is needed only to rebuild an existing dashboard target.
                    </small>
                  </span>
                  <span class="setting-control">
                    <input v-model="replaceSchemas" class="switch" type="checkbox" />
                  </span>
                </label>

                <p v-if="setupOption" class="setting-block caption schema-help">
                  <b>{{ setupOption.name }}</b> — {{ setupOption.remedy?.summary }}
                </p>

                <div class="setting-block rec-actions">
                  <button
                    class="btn"
                    :disabled="busy || operationRunning || !setupReady || (!newSchema.trim() && !setupOption?.canInitialize)"
                    @click="runSchemaOperation('initialize')"
                  >
                    Initialize sample model
                  </button>
                  <button
                    class="btn primary"
                    :disabled="busy || operationRunning || !setupReady || !setupOption?.canDerive"
                    @click="runSchemaOperation('derive')"
                  >
                    Parse all scenarios
                  </button>
                </div>
              </template>
            </section>

            <section
              v-if="state.useDatabase"
              class="setting-group"
              aria-label="Step 4 — Verify the imported schema"
            >
              <header>
                <div>
                  <h3>Step 4 — Verify the imported schema</h3>
                  <p class="caption">
                    Start an import to open its complete build log in Tasks.
                    When it succeeds, return here, select the new
                    dashboard-ready schema, and reload the actual data.
                  </p>
                </div>
              </header>
              <div v-if="operation" class="setting-row">
                <span class="setting-label">
                  Import task
                  <small>The most recent operation this server started.</small>
                </span>
                <span class="setting-control">
                  <button class="btn small" @click="navigate('tasks')">
                    View {{ operation.state }} task
                  </button>
                </span>
              </div>
            </section>
          </template>
        </template>

        <template v-else-if="tab === 'logging'">
          <p>
            Records what the dashboard reads while it reads it: the queries
            issued to PostgreSQL, the source each snapshot came from, and how
            long it took. Capture starts enabled at INFO level.
          </p>

          <template v-if="state">
            <!--
              What the server captures is separated from what this page shows,
              because the two are not the same decision: capture is a server
              setting that a protected deployment refuses, and the filters
              below only narrow records this browser already holds.
            -->
            <section class="setting-group" aria-label="Capture">
              <header>
                <div>
                  <h3>Capture</h3>
                  <p class="caption">What the server records, for every reader.</p>
                </div>
              </header>
              <label class="setting-row toggle">
                <span class="setting-label">
                  Enable logging
                  <small>
                    Off stops recording entirely; the records already captured
                    stay readable below.
                  </small>
                </span>
                <span class="setting-control">
                  <input
                    class="switch"
                    type="checkbox"
                    :checked="state.logging.enabled"
                    :disabled="readOnly"
                    @change="toggleLogging($event.target.checked)"
                  />
                </span>
              </label>
              <div class="setting-row">
                <label class="setting-label" for="log-level">
                  Capture level
                  <small>
                    The lowest severity worth recording. Anything below it is
                    never captured and cannot be shown later.
                  </small>
                </label>
                <span class="setting-control">
                  <select
                    id="log-level"
                    :value="state.logging.level"
                    :disabled="readOnly"
                    @change="setLevel($event.target.value)"
                  >
                    <option v-for="level in LOG_LEVELS" :key="level" :value="level">
                      {{ level }}
                    </option>
                  </select>
                </span>
              </div>
              <div class="setting-row">
                <span class="setting-label">
                  Clear captured records
                  <small>Discards the server's buffer. Capture continues.</small>
                </span>
                <span class="setting-control">
                  <button class="btn" :disabled="readOnly" @click="send('clearLog')">
                    Clear captured records
                  </button>
                </span>
              </div>
            </section>

            <section class="setting-group" aria-label="Captured records">
              <header>
                <div>
                  <h3>Captured records</h3>
                  <p class="caption">
                    <template v-if="state.logging.records.length">
                      {{ visibleRecords.length }} of {{ state.logging.records.length }}
                      record(s), newest last. Capacity {{ state.logging.capacity }}.
                    </template>
                    <template v-else>Nothing captured yet.</template>
                  </p>
                </div>
              </header>
              <div class="setting-row">
                <label class="setting-label" for="log-display-level">Show severity</label>
                <span class="setting-control">
                  <select id="log-display-level" v-model="displayLevel">
                    <option v-for="level in LOG_LEVELS" :key="level" :value="level">
                      {{ level }}+
                    </option>
                  </select>
                </span>
              </div>
              <div class="setting-row">
                <label class="setting-label" for="log-source">Source</label>
                <span class="setting-control">
                  <select id="log-source" v-model="displaySource">
                    <option v-for="source in logSources" :key="source" :value="source">
                      {{ source === "all" ? "All sources" : source }}
                    </option>
                  </select>
                </span>
              </div>
              <div class="setting-block">
                <LogViewer
                  :records="visibleRecords"
                  copy-label="Copy visible logs"
                  empty-text="No records match these filters. Enable logging or adjust the filters to see activity."
                />
              </div>
            </section>
          </template>
        </template>

        <BackendTasks
          v-else-if="tab === 'tasks'"
          :active="tab === 'tasks'"
          :focus-task-id="focusedTaskId"
        />
      </div>
  </section>

  <div v-if="pendingSchema" class="modal-backdrop schema-select-backdrop">
      <div class="modal confirm-modal" role="dialog" aria-modal="true" aria-label="Select database schema">
        <div class="modal-head">
          <h2>Load another database schema?</h2>
        </div>
        <div class="modal-body">
          <p>
            Change every dashboard view from <b>{{ schemas.selected }}</b> to
            <b>{{ pendingSchema.name }}</b> and reload its actual data.
          </p>
          <p class="caption">
            {{ pendingSchema.detail }} Database structure
            {{ pendingSchema.databaseRevision ?? "not tracked" }}. The selection
            lasts until this backend process restarts.
          </p>
          <div class="rec-actions">
            <button class="btn" :disabled="busy" @click="cancelSchemaSelection">Cancel</button>
            <button class="btn primary" :disabled="busy" @click="confirmSchemaSelection">
              Select and reload
            </button>
          </div>
        </div>
      </div>
  </div>
</template>
