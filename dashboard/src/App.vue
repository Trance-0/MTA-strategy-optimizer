<script setup>
/**
 * The application shell: the rail, the header, and the selected view.
 *
 * The layout is the reference prototype's App.vue
 * (`external/UI_design/brandlens-vue`, by Rouxin Jin) -- an `.app-shell` grid
 * of the navigation rail beside a main column, hash routing, and a toast for
 * transient confirmations. The seven views behind it are this project's own.
 *
 * Data flow:
 *     src/lib/useDashboard.js -> here -> the selected view
 */
import { computed, onMounted, onUnmounted, ref } from "vue";

import SettingsDialog from "./components/SettingsDialog.vue";
import LoadingProgress from "./components/LoadingProgress.vue";
import SidebarNav from "./components/SidebarNav.vue";
import TopBar from "./components/TopBar.vue";
import BudgetManager from "./views/BudgetManager.vue";
import CampaignOptimizer from "./views/CampaignOptimizer.vue";
import Campaigns from "./views/Campaigns.vue";
import CommandCenter from "./views/CommandCenter.vue";
import DataGenerator from "./views/DataGenerator.vue";
import KnowledgeBase from "./views/KnowledgeBase.vue";
import OptimizationLog from "./views/OptimizationLog.vue";
import SchemaRecovery from "./components/SchemaRecovery.vue";
import { IS_STATIC, fetchSettings } from "./api/client.js";
import { useDashboard } from "./lib/useDashboard.js";
import { useDeployment } from "./lib/deployment.js";
import { useDiagnostics } from "./lib/diagnostics.js";
import {
  DEFAULT_PAGE,
  DOCS_URL,
  PAGES,
  PAGE_KEYS,
  REPO_URL,
  parseRoute,
  routeHash,
  routeResources,
} from "./pages.js";

const VIEWS = {
  overview: CommandCenter,
  generator: DataGenerator,
  budget: BudgetManager,
  campaigns: Campaigns,
  optimizer: CampaignOptimizer,
  log: OptimizationLog,
  knowledge: KnowledgeBase,
};

const { data, loadingProgress, ensureResources, errorFor, isLoaded, reload } = useDashboard();
const {
  writable,
  theme: deploymentTheme,
  label: deploymentLabel,
  readOnlyReason,
} = useDeployment();
const { diagnosticsOn } = useDiagnostics();

const page = ref(DEFAULT_PAGE);
const section = ref(PAGES[DEFAULT_PAGE].defaultSection);
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

const requiredResources = computed(() => routeResources(page.value, section.value));
const routeLoaded = computed(() => isLoaded(requiredResources.value));
const routeError = computed(() => errorFor(requiredResources.value));

function guardRoute(route) {
  if (
    route.page === "budget" &&
    route.section === "generation-configs" &&
    !diagnosticsOn.value
  ) {
    return { page: "budget", section: "overview" };
  }
  return route;
}

function writeRoute(nextPage, nextSection, replace = false) {
  const parsed = guardRoute(parseRoute(routeHash(nextPage, nextSection)));
  page.value = parsed.page;
  section.value = parsed.section;
  const canonicalHash = routeHash(parsed.page, parsed.section);
  if (!replace && window.location.hash === canonicalHash) {
    ensureResources(routeResources(parsed.page, parsed.section)).catch(() => null);
    return;
  }
  const url = `${window.location.pathname}${window.location.search}${canonicalHash}`;
  window.history[replace ? "replaceState" : "pushState"](null, "", url);
  ensureResources(routeResources(parsed.page, parsed.section)).catch(() => null);
}

function go(key) {
  if (!PAGE_KEYS.includes(key)) return;
  writeRoute(key, PAGES[key].defaultSection);
}

function goSection(key) {
  writeRoute(page.value, key);
}

function readLocation() {
  const parsed = guardRoute(parseRoute(window.location.hash));
  page.value = parsed.page;
  section.value = parsed.section;
  if (window.location.hash !== routeHash(parsed.page, parsed.section)) {
    writeRoute(parsed.page, parsed.section, true);
    return;
  }
  ensureResources(routeResources(parsed.page, parsed.section)).catch(() => null);
}

async function refreshStatus() {
  const settings = await fetchSettings().catch(() => null);
  if (!settings) return;
  status.value = settings.status ?? {};
  loggingOn.value = settings.logging?.enabled ?? false;
}

onMounted(() => {
  readLocation();
  window.addEventListener("hashchange", readLocation);
  window.addEventListener("popstate", readLocation);
  refreshStatus();
});

onUnmounted(() => {
  window.removeEventListener("hashchange", readLocation);
  window.removeEventListener("popstate", readLocation);
  clearTimeout(toastTimer);
});

async function onReload() {
  await reload(requiredResources.value);
  await refreshStatus();
  showToast("Data reloaded from the source.");
}

async function onSettingsChanged() {
  await reload(requiredResources.value);
  await refreshStatus();
  showToast("Settings saved. Data reloaded.");
}

const meta = computed(() => PAGES[page.value]);

/**
 * The deployment's accent, applied as the custom properties `style.css`
 * already reads.
 *
 * Overriding the tokens rather than adding a second set of rules is what keeps
 * one stylesheet: every `var(--blue)` in the sheet follows the deployment, and
 * no component needs a variant class. The chart series palette is deliberately
 * not included — a series colour follows its entity, so the same Campaign must
 * not change colour between the two sites.
 */
const themeStyle = computed(() => ({
  "--blue": deploymentTheme.value.accent,
  "--blue2": deploymentTheme.value.accentSoft,
  "--blue-strong": deploymentTheme.value.accentStrong,
  "--navy": deploymentTheme.value.rail,
  "--rail-active": deploymentTheme.value.railActive,
}));

/** The report window, read from the data rather than fixed in the header. */
const reportWindow = computed(() => {
  const context = data.value.dashboardContext ?? {};
  if (!context.reportStartDate) return "";
  return `${context.reportStartDate} → ${context.reportEndDate}`;
});

const marketplace = computed(() => {
  const context = data.value.dashboardContext ?? {};
  if (!context.platform && !context.marketplace) return "";
  return [context.platform, context.marketplace].filter(Boolean).join(" · ");
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
  <div
    class="app-shell"
    :class="`deployment-${deploymentTheme.key}`"
    :style="themeStyle"
  >
    <SidebarNav
      :current="page"
      :status="status"
      :logging-on="loggingOn"
      :docs-href="docsHref"
      :repo-href="REPO_URL"
      @go="go"
      @settings="settingsOpen = true"
    />

    <main class="main">
      <TopBar
        :title="meta.title"
        :crumb="meta.crumb"
        :window="reportWindow"
        :marketplace="marketplace"
        :deployment-label="deploymentLabel"
        :writable="writable"
      />

      <div class="content">
        <!--
          Stated once, at the top of every view, rather than at each control it
          governs. A reader who cannot edit should learn that from the page,
          not by hunting for a button that is not there.
        -->
        <div v-if="routeLoaded && !writable" class="notice deployment-notice">
          <b>Read-only deployment.</b> {{ readOnlyReason }}
        </div>
        <div v-if="!routeLoaded && !routeError" class="card empty-card">
          <h2>Loading the pipeline's artifacts…</h2>
          <p>Reading the attribution outputs, the budget seed, and the history.</p>
          <LoadingProgress :progress="loadingProgress" />
        </div>

        <div v-else-if="routeError" class="card empty-card error-card">
          <h2>The dashboard data could not be loaded</h2>
          <p class="error-detail">{{ routeError.message }}</p>
          <!--
            The remedies are rendered as controls rather than as a command to
            paste into a terminal. A reader reaching this page has a browser
            and, on a deployed instance, nothing else; naming a shell command
            here would describe a fix they cannot carry out.
          -->
          <SchemaRecovery
            v-if="routeError.code === 'database_unavailable'"
            @recovered="onReload"
            @settings="settingsOpen = true"
          />
          <div class="rec-actions">
            <button class="btn" @click="onReload">Try again</button>
            <button class="btn primary" @click="settingsOpen = true">Settings</button>
          </div>
        </div>

        <component
          :is="VIEWS[page]"
          v-else
          :section="section"
          @navigate="goSection"
        />
      </div>
    </main>

    <SettingsDialog
      :open="settingsOpen"
      @close="settingsOpen = false"
      @changed="onSettingsChanged"
      @reload="onReload"
    />

    <div class="toast" :class="{ show: toast }">{{ toast }}</div>
  </div>
</template>
