/**
 * Guard Data Generator preflight and polling responses against stale browser state.
 *
 * Data flow: DataGenerator.vue -> lifecycle identity/token checks -> current UI state.
 */

/** Create the state guards shared by configuration preflight and run polling. */
export function createGeneratorLifecycle() {
  let revision = 0;
  let currentIdentity = null;
  let acceptedIdentity = null;
  let preflightSequence = 0;
  let activeRun = null;
  let runSequence = 0;

  function configurationChanged(variant, configuration) {
    revision += 1;
    currentIdentity = configurationIdentity(variant, configuration, revision);
    acceptedIdentity = null;
    return currentIdentity;
  }

  function beginPreflight(variant, configuration) {
    const identity = configurationIdentity(variant, configuration, revision);
    return { identity, sequence: ++preflightSequence };
  }

  function acceptPreflight(request) {
    if (!isCurrentPreflight(request)) return false;
    acceptedIdentity = request.identity;
    return true;
  }

  function isCurrentPreflight(request) {
    return request.sequence === preflightSequence && request.identity === currentIdentity;
  }

  function canGenerate(variant, configuration) {
    return acceptedIdentity === configurationIdentity(variant, configuration, revision);
  }

  function beginRun(runId) {
    activeRun = { runId, sequence: ++runSequence };
    return activeRun;
  }

  function clearRun() {
    activeRun = null;
    runSequence += 1;
  }

  function isCurrentRun(token, runId) {
    return activeRun?.sequence === token.sequence && activeRun.runId === runId;
  }

  return {
    configurationChanged,
    beginPreflight,
    acceptPreflight,
    isCurrentPreflight,
    canGenerate,
    beginRun,
    clearRun,
    isCurrentRun,
  };
}

/** Replace a dirty preset only after its caller confirms the destructive action. */
export async function replacePresetIfConfirmed({ dirty, confirm, loadPreset, variant, preset }) {
  if (dirty && !confirm()) return false;
  return Boolean(await loadPreset(variant, preset));
}

function configurationIdentity(variant, configuration, revision) {
  return `${revision}:${variant}:${stableStringify(configuration)}`;
}

function stableStringify(value, depth = 0) {
  if (depth > 64) return '"[depth-limit]"';
  if (Array.isArray(value)) return `[${value.map((item) => stableStringify(item, depth + 1)).join(",")}]`;
  if (value !== null && typeof value === "object") {
    return `{${Object.keys(value).sort().map((key) => `${JSON.stringify(key)}:${stableStringify(value[key], depth + 1)}`).join(",")}}`;
  }
  return JSON.stringify(value);
}
