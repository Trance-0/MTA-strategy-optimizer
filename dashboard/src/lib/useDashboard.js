/** Shared, route-aware dashboard resource store. */

import { computed, readonly, ref } from "vue";

import { fetchDashboardResource, reloadData } from "../api/client.js";

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

const snapshot = ref(freshSnapshot());
const completed = ref(new Set());
const failures = ref(new Map());
const activeRequests = ref(0);
const loadingProgress = ref({
  label: "Loading dashboard data", phase: "Starting request", visible: false,
  loaded: 0, total: null, percent: null, elapsedMs: 0,
});
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
  if (!values.length) return;
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

function loadResource(resource) {
  if (completed.value.has(resource)) return Promise.resolve(snapshot.value);
  if (inFlight.has(resource)) return inFlight.get(resource);
  activeRequests.value += 1;
  const request = withProgress(resource, (progress) =>
    fetchDashboardResource(resource, progress),
  )
    .then((payload) => {
      mergePayload(payload);
      completed.value = new Set([...completed.value, resource]);
      const nextFailures = new Map(failures.value);
      nextFailures.delete(resource);
      failures.value = nextFailures;
      return payload;
    })
    .catch((cause) => {
      failures.value = new Map(failures.value).set(resource, cause);
      throw cause;
    })
    .finally(() => {
      activeRequests.value -= 1;
      inFlight.delete(resource);
    });
  inFlight.set(resource, request);
  return request;
}

export function useDashboard() {
  return {
    data: computed(() => snapshot.value),
    loading: computed(() => activeRequests.value > 0),
    loaded: computed(() => completed.value.size > 0),
    loadingProgress: readonly(loadingProgress),
    isLoaded(resources) {
      return resources.every((resource) => completed.value.has(resource));
    },
    errorFor(resources) {
      for (const resource of resources) {
        const failure = failures.value.get(resource);
        if (failure) return failure;
      }
      return null;
    },
    ensureResources(resources) {
      currentResources = [...resources];
      return Promise.all(resources.map(loadResource));
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
