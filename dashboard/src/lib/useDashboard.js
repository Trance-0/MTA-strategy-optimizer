/** Shared, route-aware dashboard resource store. */

import { computed, readonly, ref } from "vue";

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

const snapshot = ref(freshSnapshot());
const completed = ref(new Set());
const failures = ref(new Map());
const activeRequests = ref(0);
const loadingProgress = ref({ ...IDLE_PROGRESS });
const inFlight = new Map();
const progressByResource = new Map();
let currentResources = [];

function mergePayload(payload) {
  snapshot.value = {
    ...snapshot.value,
    ...payload,
    simulationResearch: payload.simulationResearch
      ? { ...snapshot.value.simulationResearch, ...payload.simulationResearch }
      : snapshot.value.simulationResearch,
  };
}

function publishProgress() {
  const values = [...progressByResource.values()];
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

async function withProgress(resource, action) {
  const started = Date.now();
  progressByResource.set(resource, {
    resource,
    label: `Loading ${resource.replaceAll("-", " ")}`,
    phase: "Starting request", visible: true, loaded: 0, total: null,
    percent: 0, elapsedMs: 0,
  });
  publishProgress();
  const timer = setInterval(() => {
    progressByResource.set(resource, {
      ...progressByResource.get(resource),
      elapsedMs: Date.now() - started,
    });
    publishProgress();
  }, 250);
  try {
    return await action((value) => {
      const current = progressByResource.get(resource) ?? {};
      const nextPercent = Number.isFinite(value.percent)
        ? Math.max(current.percent ?? 0, value.percent)
        : current.percent;
      progressByResource.set(resource, {
        ...current,
        ...value,
        percent: nextPercent,
        elapsedMs: Date.now() - started,
      });
      publishProgress();
    });
  } finally {
    clearInterval(timer);
    progressByResource.delete(resource);
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

/**
 * A resource's cache identity.
 *
 * A windowed resource is keyed by its bounds as well as its name, so widening
 * the window is a different entry and refetches rather than returning the
 * narrower slice already loaded under the bare name.
 */
function cacheKey(resource) {
  if (!WINDOWED_RESOURCES.has(resource)) return resource;
  const { start, end } = historyWindow.value;
  return `${resource}:${start ?? ""}:${end ?? ""}`;
}

function loadResource(resource) {
  const key = cacheKey(resource);
  if (completed.value.has(key)) return Promise.resolve(snapshot.value);
  if (inFlight.has(key)) return inFlight.get(key);
  const window = WINDOWED_RESOURCES.has(resource) ? historyWindow.value : null;
  activeRequests.value += 1;
  const request = withProgress(resource, (progress) =>
    fetchDashboardResource(resource, progress, window),
  )
    .then((payload) => {
      mergePayload(payload);
      completed.value = new Set([...completed.value, key]);
      const nextFailures = new Map(failures.value);
      nextFailures.delete(key);
      failures.value = nextFailures;
      return payload;
    })
    .catch((cause) => {
      failures.value = new Map(failures.value).set(key, cause);
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
    loading: computed(() => activeRequests.value > 0),
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
      const affected = currentResources.filter((resource) =>
        WINDOWED_RESOURCES.has(resource),
      );
      if (!affected.length) return Promise.resolve(snapshot.value);
      return Promise.all(affected.map(loadResource));
    },
    async reload(resources = currentResources) {
      await Promise.allSettled([...inFlight.values()]);
      await reloadData();
      completed.value = new Set();
      failures.value = new Map();
      snapshot.value = freshSnapshot();
      return Promise.all(resources.map(loadResource));
    },
  };
}
