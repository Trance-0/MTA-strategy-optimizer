/**
 * The client's single route to the data.
 *
 * Two deployments share one contract. A local run fetches `/api/dashboard`
 * from the Flask backend beside it; the published static build has no server,
 * so `script/export_dashboard_snapshot.py` writes the same payload to
 * `data/snapshot.json` at build time and this module fetches that instead.
 * A view sees no difference, which is the browser-side counterpart of the
 * `DATABASE=true/false` contract the loaders keep.
 *
 * Data flow:
 *     server/data_source.js (or data/snapshot.json) -> here -> useDashboard()
 */

/**
 * True when the app was built for a static host.
 *
 * `import.meta.env.VITE_STATIC_BUILD` is baked in at build time by
 * `vite build --mode static`; a normal build leaves it undefined and the API
 * is used.
 */
export const IS_STATIC = import.meta.env.VITE_STATIC_BUILD === "true";

/**
 * Where the snapshot comes from.
 *
 * The static path is relative, not absolute, because GitHub Pages serves a
 * project site from a subdirectory and an absolute path would resolve to the
 * domain root.
 */
const SNAPSHOT_URL = IS_STATIC ? "data/snapshot.json" : "/api/dashboard";
const RESEARCH_HISTORY_URL = IS_STATIC
  ? "data/research-history.json"
  : "/api/dashboard/research-history";

async function readJson(response, onProgress = null) {
  let text;
  if (onProgress && response.body?.getReader) {
    const totalHeader = Number(response.headers.get("Content-Length"));
    const total = Number.isFinite(totalHeader) && totalHeader > 0 ? totalHeader : null;
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    const parts = [];
    let loaded = 0;
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      loaded += value.byteLength;
      parts.push(decoder.decode(value, { stream: true }));
      onProgress({ loaded, total, percent: total ? Math.min(100, loaded / total * 100) : null });
    }
    parts.push(decoder.decode());
    text = parts.join("");
  } else {
    text = await response.text();
  }
  try {
    return JSON.parse(text);
  } catch {
    // A proxy or a 404 page returns HTML; reporting the status is more use
    // than a parse error naming character 0.
    throw new Error(
      `Expected JSON from ${response.url} but received ${response.status} ` +
        `${response.statusText}.`,
    );
  }
}

/** Fetch the whole dashboard snapshot. */
export async function fetchDashboard(onProgress = null) {
  const response = await fetch(SNAPSHOT_URL, { headers: { Accept: "application/json" } });
  const payload = await readJson(response, onProgress);
  if (!response.ok) {
    const error = new Error(payload.message || "Failed to load the dashboard data.");
    error.code = payload.error;
    error.source = payload.source;
    throw error;
  }
  return payload;
}

/** Fetch the observation-heavy research arrays only when a view needs them. */
export async function fetchResearchHistory(onProgress = null) {
  const response = await fetch(RESEARCH_HISTORY_URL, {
    headers: { Accept: "application/json" },
  });
  const payload = await readJson(response, onProgress);
  if (!response.ok) throw new Error(payload.message || "Failed to load research history.");
  return payload;
}

/** Drop the server's cached reads. A static build has no cache to drop. */
export async function reloadData() {
  if (IS_STATIC) return { ok: true };
  const response = await fetch("/api/reload", { method: "POST" });
  return readJson(response);
}

/** Save one future-run master/configuration object in database mode. */
export async function saveMasterObject(entityType, entityId, payload) {
  if (IS_STATIC) throw new Error("Master editing is unavailable in the static build.");
  const response = await fetch(
    `/api/master/${encodeURIComponent(entityType)}/${encodeURIComponent(entityId)}`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ payload }),
    },
  );
  const result = await readJson(response);
  if (!response.ok) throw new Error(result.message ?? "Master object was not saved.");
  return result;
}

/** Archive one future-run object; generated history has no deletion endpoint. */
export async function archiveMasterObject(entityType, entityId) {
  if (IS_STATIC) throw new Error("Master editing is unavailable in the static build.");
  const response = await fetch(
    `/api/master/${encodeURIComponent(entityType)}/${encodeURIComponent(entityId)}`,
    { method: "DELETE" },
  );
  const result = await readJson(response);
  if (!response.ok) throw new Error(result.message ?? "Master object was not archived.");
  return result;
}

/**
 * The three pipeline stages, their current run, and their logs.
 *
 * The static build has no server to run anything, so it answers with three
 * stages that are all unavailable rather than issuing a request that would
 * 404. The view then renders its three tabs from one shape in both
 * deployments, and the reason a stage cannot run is the deployment's own.
 */
export async function fetchJobs() {
  if (IS_STATIC) {
    const unavailable =
      "The published build runs as static assets with no server behind it, " +
      "so it cannot run a pipeline stage. Run the dashboard locally against " +
      "a PostgreSQL mirror to run them.";
    const stages = {};
    for (const [key, label] of [
      ["attribution", "MTA attribution"],
      ["optimization", "MTA strategy optimization"],
      ["evaluation", "MTA strategy evaluation"],
    ]) {
      stages[key] = {
        key,
        label,
        script: null,
        available: false,
        unavailableReason: unavailable,
        datasets: [],
        defaultDataset: null,
        current: null,
      };
    }
    return { stages, history: [] };
  }
  const response = await fetch("/api/jobs");
  return readJson(response);
}

/** Start one pipeline stage. Throws with the server's reason when refused. */
export async function startJob(stage, options = {}) {
  if (IS_STATIC) {
    throw new Error(
      "The published build cannot run a pipeline stage. Run the dashboard " +
        "locally against a PostgreSQL mirror.",
    );
  }
  const response = await fetch(`/api/jobs/${encodeURIComponent(stage)}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(options),
  });
  const result = await readJson(response);
  if (!response.ok) throw new Error(result.message ?? "The stage was not started.");
  return result;
}

/** Stop a running stage. */
export async function stopJob(stage) {
  if (IS_STATIC) return null;
  const response = await fetch(`/api/jobs/${encodeURIComponent(stage)}`, {
    method: "DELETE",
  });
  return readJson(response);
}

/**
 * The settings state.
 *
 * The static build has no server to ask, so it returns the hosted state
 * directly rather than issuing a request that would 404.
 */
export async function fetchSettings() {
  if (IS_STATIC) {
    return {
      hosted: true,
      useDatabase: false,
      backendIdentity: null,
      connection: null,
      status: {
        // The rail dot matches the read-only deployment accent in
        // `src/lib/deployment.js`, so the rail and the theme cannot disagree
        // about which deployment this is.
        label: "Sample data",
        colour: "#7ed6a4",
        detail: "Published build, reading the repository's committed samples.",
      },
      logging: { enabled: false, level: "INFO", capacity: 0, records: [] },
    };
  }
  const response = await fetch("/api/settings");
  return readJson(response);
}

/** Send a settings action: `test`, `save`, `logging`, or `clearLog`. */
export async function postSettings(payload) {
  if (IS_STATIC) {
    return {
      ok: false,
      message:
        "The published build reads the repository's committed sample files " +
        "and cannot open a database connection.",
    };
  }
  const response = await fetch("/api/settings", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return readJson(response);
}

/** Confirm a server-side runtime schema selection. */
export async function selectRuntimeSchema(schema) {
  if (IS_STATIC) throw new Error("Schema selection requires a live backend.");
  const response = await fetch("/api/settings/schema-selection", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ schema }),
  });
  const result = await readJson(response);
  if (!response.ok) throw new Error(result.message ?? "The schema was not selected.");
  return result;
}

/** Return generator capability and the default self-contained configuration. */
export async function fetchGeneratorOverview() {
  if (IS_STATIC) {
    return {
      available: false,
      reason: "The static build has no backend to run MTA-SIM.",
      variants: [],
      configuration: {},
    };
  }
  const response = await fetch("/api/data-generator");
  return readJson(response);
}

/** Load one reviewed generator preset. */
export async function fetchGeneratorPreset(variant, preset) {
  const response = await fetch(
    `/api/data-generator/presets/${encodeURIComponent(variant)}/${encodeURIComponent(preset)}`,
  );
  const result = await readJson(response);
  if (!response.ok) throw new Error(result.message ?? "The preset was not loaded.");
  return result;
}

/** Start a configured generator run. */
export async function startGeneratorRun(variant, configuration) {
  const response = await fetch("/api/data-generator/runs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ variant, configuration }),
  });
  const result = await readJson(response);
  if (!response.ok) throw new Error(result.message ?? "Generation was not started.");
  return result;
}

/** Poll one configured generator run. */
export async function fetchGeneratorRun(runId) {
  const response = await fetch(`/api/data-generator/runs/${encodeURIComponent(runId)}`);
  const result = await readJson(response);
  if (!response.ok) throw new Error(result.message ?? "The generator run was not found.");
  return result;
}

/** Start backend-only PostgreSQL export for a completed run. */
export async function exportGeneratorRun(runId, connection, replace = false) {
  const response = await fetch(
    `/api/data-generator/runs/${encodeURIComponent(runId)}/postgresql`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ connection, replace }),
    },
  );
  const result = await readJson(response);
  if (!response.ok) throw new Error(result.message ?? "PostgreSQL export was not started.");
  return result;
}

/** URL for one declared generated table download. */
export function generatorDownloadUrl(runId, table) {
  return `/api/data-generator/runs/${encodeURIComponent(runId)}/files/${encodeURIComponent(table)}`;
}

/**
 * Poll the active or most recent database-schema setup operation.
 *
 * Carries `available` and `reason` beside the record, so the dialog enables
 * its buttons from what the server would actually accept rather than from a
 * rule it reconstructs from the deployment flags.
 */
export async function fetchSchemaOperation() {
  if (IS_STATIC) {
    return {
      current: null,
      available: false,
      reason:
        "The published build reads the repository's committed sample files " +
        "and has no database to set up.",
    };
  }
  const response = await fetch("/api/schema-operations");
  return readJson(response);
}

/**
 * What can be clicked when the loaded schema cannot serve the dashboard.
 *
 * Returns a state rather than throwing: this is fetched precisely when
 * something is already wrong, and a failed recovery fetch would leave the
 * error card with nothing under it.
 */
export async function fetchSchemaRecovery() {
  if (IS_STATIC) {
    return {
      available: false,
      reason:
        "The published build reads the repository's committed sample files " +
        "and has no database to repair.",
      active: null,
      setupEnabled: false,
      options: [],
    };
  }
  try {
    const response = await fetch("/api/schema-recovery");
    return await readJson(response);
  } catch (cause) {
    return {
      available: false,
      reason: `The schema options could not be listed — ${cause.message}`,
      active: null,
      setupEnabled: false,
      options: [],
    };
  }
}

/** Start initialization or simulator parsing for one validated schema name. */
export async function startSchemaOperation(action, schema, replace = false) {
  if (IS_STATIC) throw new Error("Schema setup is unavailable in the static build.");
  const response = await fetch("/api/schema-operations", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action, schema, replace }),
  });
  const result = await readJson(response);
  if (!response.ok) {
    const error = new Error(result.message ?? "The schema operation was not started.");
    error.code = result.error;
    throw error;
  }
  return result;
}

/** Request termination of the active schema setup operation. */
export async function stopSchemaOperation() {
  if (IS_STATIC) return { current: null };
  const response = await fetch("/api/schema-operations", { method: "DELETE" });
  const result = await readJson(response);
  if (!response.ok) throw new Error(result.message ?? "No schema operation is running.");
  return result;
}
