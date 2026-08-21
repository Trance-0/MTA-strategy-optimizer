/**
 * Whether the diagnostic views are shown.
 *
 * The dashboard's subject is an advertising account: Campaigns, budgets, and
 * what the attribution evidence says about them. A few surfaces describe the
 * pipeline that produced the data instead -- which run wrote it, under which
 * configuration and seed. Those answer an engineering question, not a
 * marketing one, and a reader planning budget should not have to walk past
 * them.
 *
 * They are therefore off by default and switched on in Settings, rather than
 * removed: the question they answer is real when a number looks wrong, and
 * deleting the surface would mean reaching for a database client instead.
 *
 * The preference is per-browser rather than server-side, because it is a
 * property of who is looking, not of the deployment: two people reading one
 * hosted dashboard can want different answers.
 *
 * Data flow:
 *     the settings dialog -> here (localStorage) -> the views that gate on it
 */

import { computed, ref } from "vue";

const STORAGE_KEY = "mta-dashboard.diagnostics";

/**
 * Read once at module load. `localStorage` is unavailable in the Node test
 * runner and in a privacy-restricted browser, so every access is guarded and
 * falls back to off rather than throwing on import.
 */
function readStored() {
  try {
    return globalThis.localStorage?.getItem(STORAGE_KEY) === "true";
  } catch {
    return false;
  }
}

const enabled = ref(readStored());

export function useDiagnostics() {
  return {
    /** True when diagnostic surfaces should be rendered. */
    diagnosticsOn: computed(() => enabled.value),

    setDiagnostics(on) {
      enabled.value = Boolean(on);
      try {
        globalThis.localStorage?.setItem(STORAGE_KEY, String(enabled.value));
      } catch {
        // A browser that refuses storage still honours the choice for this
        // session; only its persistence is lost.
      }
    },
  };
}
