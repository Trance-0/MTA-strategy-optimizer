/** Shared, route-aware dashboard resource store. */

import { computed, readonly, ref, shallowRef } from "vue";

import { fetchDashboardResource, reloadData } from "../api/client.js";
import { WINDOWED_RESOURCES } from "../pages.js";

const EMPTY = {
  mode: "", source: "", dashboardContext: {}, adsDaily: [],
  attributionResults: [], comparisonTouchpoints: [], comparisonSummary: [],
  recommendedAttribution: [], entityBridge: [], pathReport: [],
  budgetRecommendation: {}, campaignStrategy: {}, strategyEvaluation: {},
  strategyRequest: {}, candidatePool: {},
  simulationResearch: {
    runs: [], providers: [], products: [], campaigns: [], adGroups: [],
    touchpoints: [], productEconomics: [], campaignProductLinks: [], history: [],
    delivery: [], generationConfigs: [], touchpointObservations: [], masterObjects: [],
  },
};

const freshSnapshot = () => ({
  ...EMPTY,
  dashboardContext: {},
  simulationResearch: { ...EMPTY.simulationResearch },
});

/** What the progress report reads while nothing is in flight. */
const IDLE_PROGRESS = {
  label: "Loading dashboard data", phase: "Starting request", visible: false,
  loaded: 0, total: null, percent: null, elapsedMs: 0,
};

// Resource merges replace the root; immutable observation rows need no proxies.
const snapshot = shallowRef(freshSnapshot());
const completed = ref(new Set());
const failures = ref(new Map());
const activeRequests = ref(0);
const loadingProgress = ref({ ...IDLE_PROGRESS });
const inFlight = new Map();
const progressByResource = new Map();
let currentResources = [];
let contextGeneration = 0;
function readSelection() {
  try { return globalThis.localStorage?.getItem("mta.selectedDatasetId") || ""; } catch { return ""; }
}
const selectedDatasetId = ref(readSelection());
function invalidateContext() {
  contextGeneration += 1;
  completed.value = new Set();
  failures.value = new Map();
  snapshot.value = freshSnapshot();
  progressByResource.clear();
  publishProgress();
}

function mergePayload(payload) {
  snapshot.value = {
    ...snapshot.value,
    ...payload,
    runProvenance: { ...snapshot.value.runProvenance, ...payload.runProvenance },
    simulationResearch: payload.simulationResearch
      ? { ...snapshot.value.simulationResearch, ...payload.simulationResearch }
      : snapshot.value.simulationResearch,
  };
}

function publishProgress() {
  const values = [...progressByResource.entries()]
    .filter(([key, item]) => key === cacheKey(item.resource))
    .map(([, item]) => item);
  // Cleared rather than left standing: the last resource to finish removes its
  // entry, and returning early here would leave the previous report visible
  // with its final percentage. The next route that reuses a cached resource
  // starts no request of its own, so nothing would ever overwrite it and its
  // transition card would show a stale bar from an unrelated load.
  if (!values.length) {
    loadingProgress.value = { ...IDLE_PROGRESS };
    return;
  }
  const visible = values.filter((item) => item.resource !== "shell");
  const candidates = visible.length ? visible : values;
  const current = candidates.reduce((slowest, item) =>
    (item.percent ?? 0) < (slowest.percent ?? 0) ? item : slowest,
  );
  loadingProgress.value = { ...current };
}

async function withProgress(resource, action, key = resource) {
  const started = Date.now();
  progressByResource.set(key, {
    resource,
    label: `Loading ${resource.replaceAll("-", " ")}`,
    phase: "Starting request", visible: true, loaded: 0, total: null,
    percent: 0, elapsedMs: 0,
  });
  publishProgress();
  const timer = setInterval(() => {
    if (key !== cacheKey(resource)) return;
    progressByResource.set(key, {
      ...progressByResource.get(key),
      elapsedMs: Date.now() - started,
    });
    publishProgress();
  }, 250);
  try {
    return await action((value) => {
      if (key !== cacheKey(resource)) return;
      const current = progressByResource.get(key) ?? {};
      const nextPercent = Number.isFinite(value.percent)
        ? Math.max(current.percent ?? 0, value.percent)
        : current.percent;
      progressByResource.set(key, {
        ...current,
        ...value,
        percent: nextPercent,
        elapsedMs: Date.now() - started,
      });
      publishProgress();
    });
  } finally {
    clearInterval(timer);
    progressByResource.delete(key);
    publishProgress();
  }
}

/**
 * The history window every windowed resource is currently requested with.
 *
 * Held here rather than in the view because it selects what is fetched, and a
 * view that owned it could not tell whether the rows already in the snapshot
 * were read under the same bounds.
 */
const historyWindow = ref({ start: null, end: null });
let historyGeneration = 0;

/**
 * A resource's cache identity.
 *
 * A windowed resource is keyed by its bounds as well as its name, so widening
 * the window is a different entry and refetches rather than returning the
 * narrower slice already loaded under the bare name.
 */
function cacheKey(resource) {
  const prefix = `${resource}:${selectedDatasetId.value}:${contextGeneration}`;
  if (!WINDOWED_RESOURCES.has(resource)) return prefix;
  const { start, end } = historyWindow.value;
  return `${prefix}:${start ?? ""}:${end ?? ""}:${historyGeneration}`;
}

function loadResource(resource) {
  const key = cacheKey(resource);
  if (completed.value.has(key)) return Promise.resolve(snapshot.value);
  if (inFlight.has(key)) return inFlight.get(key);
  const window = WINDOWED_RESOURCES.has(resource) ? historyWindow.value : null;
  activeRequests.value += 1;
  const request = withProgress(resource, (progress) =>
    fetchDashboardResource(resource, progress, window, selectedDatasetId.value),
    key,
  )
    .then((payload) => {
      if (key !== cacheKey(resource)) return payload;
      mergePayload(payload);
      completed.value = new Set([...completed.value, key]);
      const nextFailures = new Map(failures.value);
      nextFailures.delete(key);
      failures.value = nextFailures;
      return payload;
    })
    .catch((cause) => {
      if (key === cacheKey(resource)) failures.value = new Map(failures.value).set(key, cause);
      throw cause;
    })
    .finally(() => {
      activeRequests.value -= 1;
      inFlight.delete(key);
    });
  inFlight.set(key, request);
  return request;
}

export function useDashboard() {
  return {
    data: computed(() => snapshot.value),
    selectedDatasetId: readonly(selectedDatasetId),
    selectDataset(id) {
      if (id === selectedDatasetId.value) return Promise.resolve(snapshot.value);
      selectedDatasetId.value = id || "";
      try { globalThis.localStorage?.setItem("mta.selectedDatasetId", selectedDatasetId.value); } catch { /* Storage may be blocked; in-memory selection still works. */ }
      historyWindow.value = { start: null, end: null };
      invalidateContext();
      return Promise.all(currentResources.map(loadResource));
    },
    loading: computed(() => loadingProgress.value.visible),
    loaded: computed(() => completed.value.size > 0),
    loadingProgress: readonly(loadingProgress),
    historyWindow: readonly(historyWindow),
    isLoaded(resources) {
      return resources.every((resource) => completed.value.has(cacheKey(resource)));
    },
    errorFor(resources) {
      for (const resource of resources) {
        const failure = failures.value.get(cacheKey(resource));
        if (failure) return failure;
      }
      return null;
    },
    ensureResources(resources) {
      currentResources = [...resources];
      return Promise.all(resources.map(loadResource));
    },
    /**
     * Request a different history window and reload what depends on it.
     *
     * Only the windowed resources are dropped from the completed set: the
     * entity catalogues loaded beside them do not vary with the window, and
     * refetching them would make changing a date re-transfer everything.
     */
    setHistoryWindow(window) {
      const next = { start: window?.start || null, end: window?.end || null };
      const current = historyWindow.value;
      if (next.start === current.start && next.end === current.end) {
        return Promise.resolve(snapshot.value);
      }
      historyWindow.value = next;
      historyGeneration += 1;
      const isWindowedKey = (key) => WINDOWED_RESOURCES.has(key.split(":")[0]);
      completed.value = new Set([...completed.value].filter((key) => !isWindowedKey(key)));
      failures.value = new Map([...failures.value].filter(([key]) => !isWindowedKey(key)));
      publishProgress();
      const affected = currentResources.filter((resource) =>
        WINDOWED_RESOURCES.has(resource),
      );
      if (!affected.length) return Promise.resolve(snapshot.value);
      return Promise.all(affected.map(loadResource));
    },
    async reload(resources = currentResources) {
      invalidateContext();
      const generation = contextGeneration;
      await reloadData();
      if (generation !== contextGeneration) return snapshot.value;
      return Promise.all(resources.map(loadResource));
    },
  };
}
