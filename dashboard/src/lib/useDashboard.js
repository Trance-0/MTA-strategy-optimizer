/**
 * The single shared load of the dashboard snapshot.
 *
 * Every view reads from this one store rather than fetching for itself, which
 * is what makes switching views instant and guarantees that two views on the
 * same screen can never show two different reads of the same source. It is the
 * browser-side counterpart of the loader cache the Python dashboard held.
 *
 * Data flow:
 *     src/api/client.js -> here -> the six views
 */

import { computed, readonly, ref } from "vue";

import { fetchDashboard, reloadData } from "../api/client.js";

const snapshot = ref(null);
const loading = ref(false);
const error = ref(null);

let inFlight = null;

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
  strategyRequest: {},
  candidatePool: {},
};

async function load() {
  // Concurrent callers share one request: the six views mount together on the
  // first paint and would otherwise each issue their own.
  if (inFlight) return inFlight;
  loading.value = true;
  error.value = null;
  inFlight = fetchDashboard()
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

export function useDashboard() {
  const data = computed(() => snapshot.value ?? EMPTY);

  return {
    data,
    loading: readonly(loading),
    error: readonly(error),
    loaded: computed(() => snapshot.value !== null),
    ensureLoaded() {
      if (snapshot.value === null && !inFlight) return load();
      return inFlight ?? Promise.resolve(snapshot.value);
    },
    async reload() {
      await reloadData();
      snapshot.value = null;
      return load();
    },
  };
}
