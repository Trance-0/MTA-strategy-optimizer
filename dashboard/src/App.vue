<script setup>
/**
 * The application shell: the rail, the header, and the selected view.
 *
 * The layout is the reference prototype's App.vue
 * (`external/UI_design/brandlens-vue`, by Rouxin Jin) -- an `.app-shell` grid
 * of the navigation rail beside a main column, hash routing, and a toast for
 * transient confirmations. The six views behind it are this project's own.
 *
 * Data flow:
 *     src/lib/useDashboard.js -> here -> the selected view
 */
import { computed, onMounted, onUnmounted, ref } from "vue";

import SettingsDialog from "./components/SettingsDialog.vue";
import SidebarNav from "./components/SidebarNav.vue";
import TopBar from "./components/TopBar.vue";
import BudgetManager from "./views/BudgetManager.vue";
import CampaignOptimizer from "./views/CampaignOptimizer.vue";
import Campaigns from "./views/Campaigns.vue";
import CommandCenter from "./views/CommandCenter.vue";
import KnowledgeBase from "./views/KnowledgeBase.vue";
import OptimizationLog from "./views/OptimizationLog.vue";
import { IS_STATIC, fetchSettings } from "./api/client.js";
import { useDashboard } from "./lib/useDashboard.js";
import { DEFAULT_PAGE, DOCS_URL, PAGES, PAGE_KEYS, REPO_URL } from "./pages.js";

const VIEWS = {
  overview: CommandCenter,
  budget: BudgetManager,
  campaigns: Campaigns,
  optimizer: CampaignOptimizer,
  log: OptimizationLog,
  knowledge: KnowledgeBase,
};

const { data, loading, error, loaded, ensureLoaded, reload } = useDashboard();

const page = ref(DEFAULT_PAGE);
const settingsOpen = ref(false);
const toast = ref("");
const status = ref({});
const loggingOn = ref(false);

let toastTimer = null;

function showToast(text) {
  toast.value = text;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    toast.value = "";
  }, 2400);
}

// The rail writes the page into the hash so a view is linkable and survives a
// refresh. `replaceState` rather than assignment, so switching views does not
// fill the browser's back stack with intermediate pages.
function syncHash(key) {
  const url = `${window.location.pathname}${window.location.search}#${key}`;
  window.history.replaceState(null, "", url);
}

function go(key) {
  if (!PAGE_KEYS.includes(key)) return;
  page.value = key;
  syncHash(key);
}

function readHash() {
  const key = window.location.hash.replace(/^#/, "");
  if (PAGE_KEYS.includes(key)) page.value = key;
}

async function refreshStatus() {
  const settings = await fetchSettings().catch(() => null);
  if (!settings) return;
  status.value = settings.status ?? {};
  loggingOn.value = settings.logging?.enabled ?? false;
}

onMounted(() => {
  readHash();
  syncHash(page.value);
  window.addEventListener("hashchange", readHash);
  ensureLoaded();
  refreshStatus();
});

onUnmounted(() => {
  window.removeEventListener("hashchange", readHash);
  clearTimeout(toastTimer);
});

async function onReload() {
  await reload();
  await refreshStatus();
  showToast("Data reloaded from the source.");
}

async function onSettingsChanged() {
  await reload();
  await refreshStatus();
  showToast("Settings saved. Data reloaded.");
}

const meta = computed(() => PAGES[page.value]);

/** The report window, read from the data rather than fixed in the header. */
const reportWindow = computed(() => {
  const summary = data.value.comparisonSummary?.[0];
  if (!summary?.report_start_date) return "";
  return `${summary.report_start_date} → ${summary.report_end_date}`;
});

const marketplace = computed(() => {
  const group = data.value.strategyRequest?.campaign_group ?? {};
  if (!group.platform && !group.marketplace) return "";
  return [group.platform, group.marketplace].filter(Boolean).join(" · ");
});

/**
 * The documentation link is relative in the published build, where the site
 * serves the dashboard at its root and the documentation one level down at
 * `/docs/`; a local run has no such sibling and so points at the published
 * site.
 */
const docsHref = computed(() => (IS_STATIC ? "./docs/" : `${DOCS_URL}/`));
</script>

<template>
  <div class="app-shell">
    <SidebarNav
      :current="page"
      :status="status"
      :logging-on="loggingOn"
      :docs-href="docsHref"
      :repo-href="REPO_URL"
      @go="go"
      @reload="onReload"
      @settings="settingsOpen = true"
    />

    <main class="main">
      <TopBar
        :title="meta.title"
        :crumb="meta.crumb"
        :window="reportWindow"
        :marketplace="marketplace"
      />

      <div class="content">
        <div v-if="loading && !loaded" class="card empty-card">
          <h2>Loading the pipeline's artifacts…</h2>
          <p>Reading the attribution outputs, the budget seed, and the history.</p>
        </div>

        <div v-else-if="error" class="card empty-card error-card">
          <h2>The dashboard data could not be loaded</h2>
          <p class="error-detail">{{ error.message }}</p>
          <p v-if="error.code === 'database_unavailable'">
            <code>DATABASE=true</code>, but the database cannot be used. Open
            <b>Settings</b> in the rail to correct the credentials or switch back
            to the committed files, or run
            <code>uv run --extra dashboard python script/import_to_database.py</code>
            to populate the database.
          </p>
          <div class="rec-actions">
            <button class="btn" @click="onReload">Try again</button>
            <button class="btn primary" @click="settingsOpen = true">Settings</button>
          </div>
        </div>

        <component :is="VIEWS[page]" v-else />
      </div>
    </main>

    <SettingsDialog
      :open="settingsOpen"
      @close="settingsOpen = false"
      @changed="onSettingsChanged"
    />

    <div class="toast" :class="{ show: toast }">{{ toast }}</div>
  </div>
</template>
