/**
 * Which deployment this is, and therefore what it is allowed to do.
 *
 * The dashboard ships in two deployments from one source tree, and until now
 * each view worked that out for itself: `data.mode === "database"` in one
 * place, `IS_STATIC` in another. The two are not the same question, and asking
 * either one alone is what let the published build render an editing control
 * it could never honour.
 *
 * The two questions are separated here:
 *
 *     writable   may this deployment change data?
 *     capability which theme, which label, which explanation?
 *
 * `writable` is derived from the snapshot's own `mode`, not from the build
 * flag, because it is the server that decides: a local run against the
 * committed files is read-only for exactly the same reason the published build
 * is -- there is no database behind it to write to. A view therefore asks
 * `writable` and never branches on the build.
 *
 * Data flow:
 *     snapshot mode -> editing permission
 *     snapshot mode or shell Settings response -> deployment identity/theme
 */

import { computed } from "vue";

import { DEPLOYMENT_THEMES } from "../theme.js";
import { useDashboard } from "./useDashboard.js";

/**
 * The two accent sets, re-exported from `theme.js` where every colour lives.
 *
 * They are not declared here, because a colour declared in two places is free
 * to disagree with itself.
 */
export const THEMES = DEPLOYMENT_THEMES;

/**
 * Whether this bundle was built for a static host.
 *
 * Read through a function rather than imported from `src/api/client.js`,
 * because `import.meta.env` exists only under Vite: importing the client
 * module makes this file unloadable in the Node test runner, which is where
 * the deployment contract is asserted. The flag identifies a static file
 * deployment before data arrives and selects its label and remedy, never whether it may
 * write, which the snapshot's own mode decides.
 */
function isStaticBuild() {
  return import.meta.env?.VITE_STATIC_BUILD === "true";
}

/**
 * Describe the active deployment.
 *
 * Returns computed refs rather than plain values, because the mode is not known
 * until Settings or the first snapshot resolves: a component that read a plain boolean at
 * setup time would fix itself to the pre-load default and never correct.
 */
export function useDeployment(settings = null) {
  const { data } = useDashboard();

  /** True once the server has reported a database it can actually write to. */
  const writable = computed(() => data.value.mode === "database");

  // Settings has no data resources. Use its confirmed configuration for display
  // while data is absent, including after reload clears the shared snapshot.
  // This fallback must never grant the write capability above.
  const mode = computed(() => {
    if (data.value.mode) return data.value.mode;
    if (settings?.value?.useDatabase === true) return "database";
    if (settings?.value?.useDatabase === false || isStaticBuild()) return "local files";
    return "";
  });
  const theme = computed(() =>
    mode.value === "local files" ? THEMES.read_only : THEMES.writable,
  );

  /**
   * What to call this deployment in the interface.
   *
   * The published build and a local file-mode run are both read-only, but they
   * are read-only for different reasons and a reader can act on only one of
   * them, so they are named apart rather than collapsed into one label.
   */
  const label = computed(() => {
    if (writable.value) return "Database connected";
    if (mode.value === "database") return "Database configured";
    if (!mode.value) return "Checking data source";
    return isStaticBuild() ? "Published build" : "Local files";
  });

  /** Why data operations are unavailable, phrased as the remedy. */
  const readOnlyReason = computed(() => {
    if (writable.value) return "";
    if (!mode.value) return "The data source has not been confirmed. Open Settings to check the connection or reload before editing.";
    if (mode.value === "database") return "Database data has not loaded. Open Settings to check the connection or reload before editing.";
    return isStaticBuild()
      ? "The published build reads a snapshot exported from the repository's " +
          "committed files. It has no server behind it, so adding, editing, and " +
          "removing data are unavailable here. Run the dashboard locally against " +
          "a PostgreSQL mirror to make these changes."
      : "This run reads the committed CSV and JSON artifacts. Set " +
          "DATABASE=true in .env, or use Settings in the rail, to connect a " +
          "PostgreSQL mirror and enable adding, editing, and removing data.";
  });

  return { mode, writable, theme, label, readOnlyReason, isStatic: isStaticBuild() };
}
