<script setup>
/** Preview and publish canonical reports without implicit dataset selection. */
import { nextTick, ref } from "vue";
import DataTable from "./DataTable.vue";
import { IS_STATIC, fetchDatasetTemplates, validateDataset, registerDataset } from "../api/client.js";
import { downloadCsv } from "../lib/chartData.js";
import { useDashboard } from "../lib/useDashboard.js";
import { useWorkbench } from "../lib/useWorkbench.js";
const { selectDataset } = useDashboard();
const { refreshDatasets } = useWorkbench();
const name = ref("");
const files = ref({});
const preview = ref(null);
const published = ref(null);
const busy = ref(false);
const error = ref("");
const issues = ref([]);
const errorSummary = ref(null);
let generation = 0;
function invalidate() { generation += 1; preview.value = null; published.value = null; issues.value = []; error.value = ""; }
function choose(role, event) { files.value = { ...files.value, [role]: event.target.files[0] }; invalidate(); }
function body() {
  const form = new FormData();
  form.append("name", name.value);
  for (const [role, file] of Object.entries(files.value)) if (file) form.append(role, file);
  return form;
}
async function submit(publish = false) {
  const token = generation;
  busy.value = true; error.value = ""; issues.value = [];
  try {
    const result = await (publish ? registerDataset : validateDataset)(body());
    if (token !== generation) return;
    if (publish) { published.value = result; await refreshDatasets(); }
    else preview.value = result;
  } catch (cause) {
    if (token === generation) { error.value = cause.message; issues.value = cause.issues ?? []; await nextTick(); errorSummary.value?.focus(); }
  } finally { busy.value = false; }
}
async function template(role) {
  try {
    const result = await fetchDatasetTemplates();
    const entry = result[role];
    downloadCsv(entry.fields.map(key => ({ key })), entry.rows, `${role}-template.csv`);
  } catch (cause) { error.value = cause.message; }
}
async function usePublished() {
  try { await selectDataset(published.value.id); window.location.hash = "#/overview/summary"; }
  catch (cause) { error.value = cause.message; }
}
</script>
<template>
  <article class="card">
    <div class="card-head"><h2>Import an analysis dataset</h2></div>
    <div class="card-body">
      <p>Use the standard performance report and optional paths or research context. One account, marketplace and currency per dataset. Maximum upload: 26 MiB.</p>
      <p v-if="IS_STATIC" class="notice">Import requires a live backend. This published site is a read-only demonstration.</p>
      <fieldset :disabled="IS_STATIC || busy || Boolean(published)">
        <div class="field"><label for="dataset-name">Dataset name</label><input id="dataset-name" :aria-describedby="error ? 'import-errors' : undefined" v-model="name" maxlength="120" @input="invalidate" /></div>
        <div v-for="role in ['performance', 'paths', 'research']" :key="role" class="field">
          <label :for="`import-${role}`">{{ role }} {{ role === 'performance' ? '(required)' : '(optional)' }}</label>
          <input :id="`import-${role}`" :aria-describedby="error ? 'import-errors' : undefined" type="file" :accept="role === 'research' ? '.json' : '.csv,.json'" @change="choose(role, $event)" />
          <button v-if="role !== 'research'" class="btn link small" @click="template(role)">Download {{ role }} template</button>
        </div>
        <div class="rec-actions">
          <button class="btn" :disabled="!name.trim() || !files.performance" @click="submit(false)">Validate and preview</button>
          <button class="btn primary" :disabled="!preview" @click="submit(true)">Import validated dataset</button>
        </div>
      </fieldset>
      <p v-if="busy" role="status">Validating and reading the selected reports…</p>
      <div v-if="error" id="import-errors" ref="errorSummary" tabindex="-1" role="alert"><p>{{ error }}</p><ul><li v-for="(issue, index) in issues" :key="index">{{ typeof issue === 'string' ? issue : `${issue.field ?? issue.path ?? ''} ${issue.row ?? ''}: ${issue.message ?? JSON.stringify(issue)}` }}</li></ul></div>
      <section v-if="preview">
        <h3>Validated preview</h3><p>{{ preview.scope?.marketplace }} · {{ preview.scope?.currency }} · {{ preview.scope?.start }} → {{ preview.scope?.end }}</p>
        <p v-for="(capability, stage) in preview.capabilities" :key="stage"><b>{{ stage }}:</b> {{ capability.available ? 'Available' : 'Unavailable' }} · {{ capability.reason }}</p>
        <details v-for="(rows, role) in preview.preview" :key="role"><summary>{{ role }} · {{ preview.counts?.[role] ?? rows.length }} rows · preview limited to 20</summary>
          <DataTable :columns="Object.keys(rows[0] ?? {}).map(key => ({key, label:key}))" :rows="rows" />
        </details>
      </section>
      <div v-if="published" class="notice" role="status"><p>Saved {{ published.name }}. Your current analysis selection has not changed.</p>
        <button class="btn primary" @click="usePublished">Use for analysis</button>
        <button class="btn" @click="invalidate">Import another dataset</button>
      </div>
    </div>
  </article>
</template>
