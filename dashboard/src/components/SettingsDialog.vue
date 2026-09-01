<script setup>
/**
 * The settings modal behind the rail's gear button.
 *
 * Two tabs: the data source this dashboard connects with, and the streaming
 * data log. The published build renders neither form -- it has no writable
 * `.env` and no socket, so offering a credential field there would invite a
 * real password into a page that could never use it -- and states the local-run
 * instructions instead.
 *
 * The password field is write-only. The server never sends a stored password
 * back, and leaving the field blank keeps the stored one rather than clearing
 * it, so the value is never rendered into the page.
 */
import { computed, onUnmounted, ref, watch } from "vue";

import {
  fetchSchemaOperation,
  fetchSettings,
  postSettings,
  startSchemaOperation,
  stopSchemaOperation,
} from "../api/client.js";
import { useDiagnostics } from "../lib/diagnostics.js";
import { DOCS_URL, REPO_URL } from "../pages.js";

const { diagnosticsOn, setDiagnostics } = useDiagnostics();

const props = defineProps({
  open: { type: Boolean, default: false },
});

const emit = defineEmits(["close", "changed"]);

const tab = ref("source");
const state = ref(null);
const busy = ref(false);
const message = ref(null);

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
let operationTimer = null;

const setupOption = computed(() =>
  (schemas.value.schemas ?? []).find((item) => item.name === setupSchema.value),
);
const inspectedOption = computed(() =>
  schemaOptions.value.find((item) => item.name === inspectedSchema.value),
);
const operation = computed(() => schemaOperation.value.current);
const operationRunning = computed(() =>
  ["running", "stopping"].includes(operation.value?.state),
);
const connectionSaved = computed(() => {
  if (!state.value?.useDatabase || form.value.PG_PASSWORD) return false;
  const saved = state.value.connection ?? {};
  return ["PG_HOST", "PG_PORT", "PG_DATABASE", "PG_USER", "PG_SSLMODE", "PG_SCHEMA"].every(
    (key) => String(form.value[key] ?? "") === String(saved[key] ?? ""),
  );
});

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

function scheduleOperationPoll() {
  if (operationTimer !== null) window.clearTimeout(operationTimer);
  operationTimer = null;
  if (props.open && operationRunning.value) {
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

async function refreshSchemaCensus() {
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

watch(
  () => props.open,
  (isOpen) => {
    if (isOpen) {
      message.value = null;
      refresh();
    }
  },
  { immediate: true },
);

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
          "Saved to .env and caches cleared. Close this dialog to reload.",
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
    message.value = {
      ok: true,
      text: `${action === "derive" ? "Parsing" : "Initialization"} started.`,
    };
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
  <div v-if="open" class="modal-backdrop" @click.self="emit('close')">
    <div class="modal" role="dialog" aria-modal="true" aria-label="Settings">
      <div class="modal-head">
        <h2>Settings</h2>
        <button class="btn small" @click="emit('close')">Close</button>
      </div>

      <div class="tabs" role="tablist">
        <button
          class="tab"
          role="tab"
          :aria-selected="tab === 'source'"
          :class="{ active: tab === 'source' }"
          @click="tab = 'source'"
        >
          Data source
        </button>
        <button
          class="tab"
          role="tab"
          :aria-selected="tab === 'logging'"
          :class="{ active: tab === 'logging' }"
          @click="tab = 'logging'"
        >
          Logging
        </button>
      </div>

      <div class="modal-body">
        <section class="deployment-identity" aria-label="Deployment identity">
          <div class="identity-head">
            <div>
              <h3>Deployment identity</h3>
              <p class="caption">Compare independently built frontend and backend artifacts.</p>
            </div>
            <span class="identity-status" :class="identityStatus.tone">
              {{ identityStatus.label }}
            </span>
          </div>
          <div class="identity-grid">
            <div>
              <span>Dashboard version</span>
              <code>{{ frontendIdentity.version }}</code>
            </div>
            <div>
              <span>Dashboard commit SHA</span>
              <code>{{ frontendIdentity.commit }}</code>
            </div>
            <div>
              <span>Backend version</span>
              <code>{{ backendIdentity?.version ?? "not connected" }}</code>
            </div>
            <div>
              <span>Backend commit SHA</span>
              <code>{{ backendIdentity?.commit ?? "not connected" }}</code>
            </div>
            <div>
              <span>Backend Python</span>
              <code>{{ backendIdentity?.runtime?.python ?? "not connected" }}</code>
            </div>
            <div>
              <span>Backend Flask</span>
              <code>{{ backendIdentity?.runtime?.flask ?? "not connected" }}</code>
            </div>
          </div>
          <p class="caption">{{ identityStatus.detail }}</p>
        </section>

        <template v-if="tab === 'source'">
          <div v-if="state" class="source-banner">
            <b>{{ state.status.label }}</b>
            <span>{{ state.status.detail }}</span>
          </div>

          <!--
            A view preference rather than a deployment setting, so it is
            offered in every deployment including the published build, where
            nothing else on this tab can be changed.
          -->
          <label class="toggle">
            <input
              type="checkbox"
              :checked="diagnosticsOn"
              @change="setDiagnostics($event.target.checked)"
            />
            <span>
              Show data run diagnostics
              <small>
                Adds a Budget Manager section describing how the current data
                run was produced — its run identifier, seed, and configuration
                checksum. Off by default: it answers an engineering question
                about the pipeline, not a question about the advertising
                account.
              </small>
            </span>
          </label>

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
              <code>uv run --extra dashboard python script/import_to_database.py</code>.
              The specification is at <a :href="DOCS_URL" target="_blank" rel="noopener">the
              documentation site</a>.
            </p>
          </template>

          <template v-else-if="state?.readOnly">
            <div class="notice">
              <b>This server reads protected deployment configuration.</b>
              Change the data-source values in the server's deployment
              environment and restart the dashboard service. Credentials cannot
              be tested or rewritten from this page.
            </div>
            <h3>Database schemas</h3>
            <p class="caption">
              Inspect the active and readable schemas. This selector changes
              only the description below; it cannot change the server's
              configured <code>PG_SCHEMA</code>.
            </p>
            <div class="field">
              <label for="protected-schema">Schema inventory</label>
              <select id="protected-schema" v-model="inspectedSchema">
                <option
                  v-for="option in schemaOptions"
                  :key="option.name"
                  :value="option.name"
                >
                  {{ option.name }}{{ option.selected ? " — active" : "" }}
                  — database {{ option.databaseRevision ?? "not tracked" }}
                </option>
              </select>
            </div>
            <p v-if="inspectedOption" class="caption schema-help">
              <b>{{ inspectedOption.name }}</b> — {{ schemaKind(inspectedOption) }};
              database structure <b>{{ inspectedOption.databaseRevision ?? "not tracked" }}</b>.
              {{ inspectedOption.detail }}
            </p>
            <p v-else class="caption schema-help">
              <template v-if="schemas.error">
                The schema list is unavailable — {{ schemas.error }}
              </template>
              <template v-else>No readable schemas were returned.</template>
            </p>
          </template>

          <template v-else-if="state">
            <label class="toggle">
              <input v-model="form.useDatabase" type="checkbox" />
              <span>
                Read from the database
                <small>
                  Off reads the committed CSV and JSON artifacts, which needs no
                  database at all. On reads the imported PostgreSQL mirror.
                </small>
              </span>
            </label>

            <h3>PostgreSQL connection</h3>
            <div class="form-grid">
              <div class="field span-2">
                <label for="pg-host">Host</label>
                <input id="pg-host" v-model="form.PG_HOST" type="text" />
              </div>
              <div class="field">
                <label for="pg-port">Port</label>
                <input id="pg-port" v-model="form.PG_PORT" type="text" />
              </div>
              <div class="field">
                <label for="pg-database">Database</label>
                <input id="pg-database" v-model="form.PG_DATABASE" type="text" />
              </div>
              <div class="field">
                <label for="pg-user">User</label>
                <input id="pg-user" v-model="form.PG_USER" type="text" />
              </div>
              <div class="field span-2">
                <label for="pg-password">Password</label>
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
              </div>
              <div class="field">
                <label for="pg-sslmode">SSL mode</label>
                <select id="pg-sslmode" v-model="form.PG_SSLMODE">
                  <option v-for="mode in SSL_MODES" :key="mode" :value="mode">
                    {{ mode }}
                  </option>
                </select>
              </div>
              <div class="field span-2">
                <label for="pg-schema">Dashboard schema</label>
                <!--
                  A schema that cannot serve the dashboard is listed and
                  disabled rather than omitted. Omitting it would leave a reader
                  who knows the schema exists with no account of its absence;
                  disabling it puts the reason where they would have chosen it.

                  The option tooltip is the browser's own and some do not show
                  it over an open dropdown, so the caption below carries the
                  same explanation unconditionally rather than depending on a
                  hover that may never arrive.
                -->
                <select
                  id="pg-schema"
                  v-model="form.PG_SCHEMA"
                  aria-describedby="pg-schema-help"
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
              </div>
            </div>

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

            <template v-if="form.useDatabase">
              <h3>Schema setup</h3>
              <p class="caption">
                Manage every readable schema on the saved connection. Parse-ready
                sources stay read-only and produce one dashboard schema per
                scenario; empty or new schemas can receive the committed sample.
              </p>
              <p v-if="!connectionSaved" class="notice">
                Save the database connection and active schema before running
                setup. Operations always use the saved connection.
              </p>
              <div class="form-grid">
                <div class="field span-2">
                  <label for="setup-schema">Existing schema</label>
                  <select id="setup-schema" v-model="setupSchema">
                    <option
                      v-for="option in schemas.schemas"
                      :key="option.name"
                      :value="option.name"
                    >
                      {{ option.name }} — {{ schemaKind(option) }}
                    </option>
                  </select>
                </div>
                <div class="field span-2">
                  <label for="new-schema">New schema name</label>
                  <input
                    id="new-schema"
                    v-model="newSchema"
                    type="text"
                    placeholder="Optional target for sample initialization"
                  />
                </div>
              </div>

              <p v-if="setupOption" class="caption schema-help">
                <b>{{ setupOption.name }}</b> — {{ setupOption.detail }}
              </p>

              <label class="toggle">
                <input v-model="replaceSchemas" type="checkbox" />
                <span>
                  Replace existing target tables
                  <small>
                    Off is safe for first runs. On requires confirmation and is
                    needed only to rebuild an existing dashboard target.
                  </small>
                </span>
              </label>

              <div class="rec-actions">
                <button
                  class="btn"
                  :disabled="busy || operationRunning || !connectionSaved || (!newSchema.trim() && !setupOption?.canInitialize)"
                  @click="runSchemaOperation('initialize')"
                >
                  Initialize sample model
                </button>
                <button
                  class="btn primary"
                  :disabled="busy || operationRunning || !connectionSaved || !setupOption?.canDerive"
                  @click="runSchemaOperation('derive')"
                >
                  Parse all scenarios
                </button>
              </div>

              <section v-if="operation" class="schema-operation" aria-live="polite">
                <div class="section-head">
                  <div>
                    <h4>
                      {{ operation.action }} {{ operation.schema }} —
                      {{ operation.state }}
                    </h4>
                    <p class="caption">
                      Started {{ operation.startedAt }}
                      <template v-if="operation.finishedAt">
                        · finished {{ operation.finishedAt }}
                      </template>
                      <template v-if="operation.exitCode !== null">
                        · exit {{ operation.exitCode }}
                      </template>
                    </p>
                  </div>
                  <button
                    v-if="operationRunning"
                    class="btn small"
                    :disabled="busy"
                    @click="stopSchemaSetup"
                  >
                    Stop
                  </button>
                </div>
                <p v-if="operation.error" class="notice bad">{{ operation.error }}</p>
                <p v-if="operation.droppedLines" class="caption">
                  {{ operation.droppedLines }} earlier log line(s) dropped.
                </p>
                <pre class="schema-command"><code>{{ operation.command }}</code></pre>
                <div class="log-stream schema-log">
                  <div
                    v-for="(line, index) in operation.lines"
                    :key="`${line.at}-${index}`"
                    class="log-row"
                  >
                    <span class="log-when">{{ line.at }}</span>
                    <span class="log-source">{{ line.stream }}</span>
                    <span class="log-message">{{ line.text }}</span>
                  </div>
                </div>
              </section>
            </template>

            <div class="rec-actions">
              <button class="btn" :disabled="busy" @click="send('test')">
                Test connection
              </button>
              <button class="btn primary" :disabled="busy" @click="send('save')">
                Save to .env
              </button>
            </div>

            <div v-if="message" class="notice" :class="message.ok ? 'good' : 'bad'">
              {{ message.text }}
            </div>

            <p class="caption">
              Credentials are written to <code>.env</code> at the repository
              root, which is git-ignored. <code>sample.env</code> is the tracked
              template and must never hold a real credential. The password is
              never rendered back to this page.
            </p>
          </template>
        </template>

        <template v-else>
          <p>
            Records what the dashboard reads while it reads it: the queries
            issued to PostgreSQL, the source each snapshot came from, and how
            long it took. Off by default, because logging every read costs time.
          </p>

          <template v-if="state">
            <div class="filter-row">
              <label class="toggle">
                <input
                  type="checkbox"
                  :checked="state.logging.enabled"
                  :disabled="readOnly"
                  @change="toggleLogging($event.target.checked)"
                />
                <span>Enable logging</span>
              </label>
              <div class="field">
                <label for="log-level">Level</label>
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
              </div>
              <button class="btn small" :disabled="readOnly" @click="send('clearLog')">
                Clear captured records
              </button>
            </div>

            <p v-if="state.logging.records.length === 0" class="notice">
              No records captured yet. Enable logging, then switch views or press
              Reload to generate activity.
            </p>
            <template v-else>
              <p class="caption">
                {{ state.logging.records.length }} record(s), newest last.
                Capacity {{ state.logging.capacity }}.
              </p>
              <div class="log-stream">
                <div
                  v-for="(record, index) in state.logging.records"
                  :key="index"
                  class="log-row"
                >
                  <span class="log-when">{{ record.when }}</span>
                  <span class="log-level" :class="record.level.toLowerCase()">
                    {{ record.level }}
                  </span>
                  <span class="log-source">{{ record.source }}</span>
                  <span class="log-message">{{ record.message }}</span>
                </div>
              </div>
            </template>
          </template>
        </template>
      </div>
    </div>
  </div>
</template>
