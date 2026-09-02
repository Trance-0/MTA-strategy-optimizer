/**
 * The pipeline stages' run state, polled while anything is running.
 *
 * One shared store rather than a fetch per tab: the Campaign Optimizer shows
 * three stages at once, and three components each polling for themselves would
 * be three times the requests to paint one screen, with three answers free to
 * disagree about which stage is running.
 *
 * Polling stops when nothing is running. A dashboard left open on an idle
 * pipeline should not issue a request every second forever, and a stage that
 * starts from this browser restarts the poll itself.
 *
 * Data flow:
 *     server/jobs.js -> src/api/client.js -> here -> the optimizer's tabs
 */

import { computed, readonly, ref } from "vue";

import {
  fetchJobs,
  importJobArtifacts,
  startJob,
  stopJob,
  uploadJobArtifacts,
} from "../api/client.js";
import { useDashboard } from "./useDashboard.js";

/** How often a running stage is polled. */
const POLL_MS = 1500;

const state = ref(null);
const busy = ref(false);
const error = ref(null);

let timer = null;
let loaded = false;

function anyRunning(value) {
  return Object.values(value?.stages ?? {}).some(
    (stage) => stage.current?.state === "running",
  );
}

async function refresh() {
  try {
    state.value = await fetchJobs();
    error.value = null;
  } catch (cause) {
    error.value = cause;
  }
  schedule();
}

/**
 * Poll again only while something is running.
 *
 * The timer is cleared first every time, so a manual refresh landing beside a
 * scheduled one cannot leave two timers polling in parallel — which would
 * double the request rate for every such overlap.
 */
function schedule() {
  clearTimeout(timer);
  timer = null;
  if (anyRunning(state.value)) {
    timer = setTimeout(refresh, POLL_MS);
  }
}

export function useJobs() {
  const { reload } = useDashboard();

  const stages = computed(() => state.value?.stages ?? {});

  return {
    stages,
    busy: readonly(busy),
    error: readonly(error),
    running: computed(() => anyRunning(state.value)),

    /** Fetch once on mount; the poll takes over only if something is running. */
    ensureLoaded() {
      if (loaded) return;
      loaded = true;
      return refresh();
    },

    refresh,

    /**
     * Start a stage, then poll it.
     *
     * The refusal reason from the server is surfaced rather than swallowed: a
     * stage that will not start because no research snapshot is configured is
     * a different problem from one that will not start because the deployment
     * is read-only, and only the message distinguishes them.
     */
    async start(stage, options) {
      busy.value = true;
      error.value = null;
      try {
        state.value = await startJob(stage, options);
        schedule();
        return true;
      } catch (cause) {
        error.value = cause;
        return false;
      } finally {
        busy.value = false;
      }
    },

    async stop(stage) {
      busy.value = true;
      try {
        const result = await stopJob(stage);
        if (result) state.value = result;
        schedule();
      } finally {
        busy.value = false;
      }
    },

    async uploadOutputs(stage, files) {
      busy.value = true;
      error.value = null;
      try {
        await uploadJobArtifacts(stage, files);
        await refresh();
        await reload();
        return true;
      } catch (cause) {
        error.value = cause;
        return false;
      } finally {
        busy.value = false;
      }
    },

    async importOutputs(stage) {
      busy.value = true;
      error.value = null;
      try {
        await importJobArtifacts(stage);
        await refresh();
        return true;
      } catch (cause) {
        error.value = cause;
        return false;
      } finally {
        busy.value = false;
      }
    },

    /**
     * Pull the new outputs into the dashboard.
     *
     * Separate from the run itself, and manual: a stage rewrites what every
     * view reads, and swapping the numbers under a reader mid-read would be a
     * worse surprise than a button that says the data is ready.
     */
    async reloadAfterRun() {
      await reload();
      await refresh();
    },
  };
}
