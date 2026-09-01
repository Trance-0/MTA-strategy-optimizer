/**
 * The single shared load of the dashboard snapshot.
 *
 * Every view reads from this one store rather than fetching for itself, which
 * is what makes switching views instant and guarantees that two views on the
 * same screen can never show two different reads of the same source. It is the
 * browser-side counterpart of the loader cache the Python dashboard held.
 *
 * Data flow:
 *     src/api/client.js -> here -> the seven views
 */

import { computed, readonly, ref } from "vue";

import { fetchDashboard, fetchResearchHistory, reloadData } from "../api/client.js";

const snapshot = ref(null);
const loading = ref(false);
const error = ref(null);

let inFlight = null;
let researchInFlight = null;

const researchLoading = ref(false);
const researchLoaded = ref(false);
const researchError = ref(null);
const loadingProgress = ref({
  label: "Loading dashboard data", visible: false, loaded: 0, total: null, percent: null,
});
const researchProgress = ref({
  label: "Loading research observations", visible: false, loaded: 0, total: null, percent: null,
});

async function withProgress(state, action) {
  state.value = { ...state.value, visible: false, loaded: 0, total: null, percent: null };
  const timer = setTimeout(() => {
    state.value = { ...state.value, visible: true };
  }, 3000);
  try {
    return await action((value) => {
      state.value = { ...state.value, ...value };
    });
  } finally {
    clearTimeout(timer);
  }
}

/** An empty snapshot, so a view can render its own empty state rather than crash. */
const EMPTY = {
  mode: "",
  source: "",
  adsDaily: [],
  attributionResults: [],
  comparisonTouchpoints: [],
  comparisonSummary: [],
  recommendedAttribution: [],
  entityBridge: [],
  pathReport: [],
  budgetRecommendation: {},
  campaignStrategy: {},
  strategyEvaluation: {},
  strategyRequest: {},
  candidatePool: {},
  simulationResearch: {
    runs: [],
    providers: [],
    products: [],
    campaigns: [],
    adGroups: [],
    touchpoints: [],
    productEconomics: [],
    campaignProductLinks: [],
    history: [],
    delivery: [],
    generationConfigs: [],
    touchpointObservations: [],
    masterObjects: [],
  },
};

async function load() {
  // Concurrent callers share one request: the seven views mount together on the
  // first paint and would otherwise each issue their own.
  if (inFlight) return inFlight;
  loading.value = true;
  error.value = null;
  inFlight = withProgress(loadingProgress, fetchDashboard)
    .then((payload) => {
      snapshot.value = payload;
      return payload;
    })
    .catch((cause) => {
      error.value = cause;
      throw cause;
    })
    .finally(() => {
      loading.value = false;
      inFlight = null;
    });
  return inFlight.catch(() => null);
}

async function loadResearchHistory() {
  if (researchInFlight) return researchInFlight;
  researchLoading.value = true;
  researchError.value = null;
  researchInFlight = withProgress(researchProgress, fetchResearchHistory)
    .then((payload) => {
      const current = snapshot.value?.simulationResearch ?? {};
      snapshot.value = {
        ...snapshot.value,
        simulationResearch: { ...current, ...payload },
      };
      researchLoaded.value = true;
      return payload;
    })
    .catch((cause) => {
      researchError.value = cause;
      throw cause;
    })
    .finally(() => {
      researchLoading.value = false;
      researchInFlight = null;
    });
  return researchInFlight.catch(() => null);
}

export function useDashboard() {
  const data = computed(() => snapshot.value ?? EMPTY);

  return {
    data,
    loading: readonly(loading),
    error: readonly(error),
    loaded: computed(() => snapshot.value !== null),
    loadingProgress: readonly(loadingProgress),
    researchLoading: readonly(researchLoading),
    researchLoaded: readonly(researchLoaded),
    researchError: readonly(researchError),
    researchProgress: readonly(researchProgress),
    ensureLoaded() {
      if (snapshot.value === null && !inFlight) return load();
      return inFlight ?? Promise.resolve(snapshot.value);
    },
    ensureResearchHistory() {
      if (researchLoaded.value) return Promise.resolve(data.value.simulationResearch);
      return loadResearchHistory();
    },
    async reload() {
      await reloadData();
      snapshot.value = null;
      researchLoaded.value = false;
      researchError.value = null;
      return load();
    },
  };
}
