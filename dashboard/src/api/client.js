/**
 * The client's single route to the data.
 *
 * Two deployments share one contract. A local run fetches allow-listed
 * resources from Flask; the static build fetches equivalent generated files.
 * A view sees no difference, which is the browser-side counterpart of the
 * `DATABASE=true/false` contract the loaders keep.
 *
 * Data flow:
 *     Flask resources (or data/resources/*.json) -> here -> useDashboard()
 */

/**
 * True when the app was built for a static host.
 *
 * `import.meta.env.VITE_STATIC_BUILD` is baked in at build time by
 * `vite build --mode static`; a normal build leaves it undefined and the API
 * is used.
 */
import { DASHBOARD_RESOURCES } from "../pages.js";

export const IS_STATIC = import.meta.env.VITE_STATIC_BUILD === "true";

/**
 * How static resource paths resolve.
 *
 * The static path is relative, not absolute, because GitHub Pages serves a
 * project site from a subdirectory and an absolute path would resolve to the
 * domain root.
 */
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

/**
 * How much must transfer before the byte counter is republished.
 *
 * A reader cannot perceive a counter moving every 16 KiB, but every republish
 * is a reactive write that repaints the progress bar. A 48 MB Campaign history
 * arrives in roughly three thousand chunks, so reporting each one spends more
 * time repainting the report than the transfer it describes.
 */
const PROGRESS_BYTE_STEP = 512 * 1024;

/** Read newline-delimited backend milestones followed by one result frame. */
async function readResourceStream(response, onProgress) {
  if (!response.body?.getReader) return readJson(response, onProgress);
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  /**
   * The undelimited pieces of the line still being read, joined only once its
   * newline arrives.
   *
   * Held as pieces rather than as one growing string because the result frame
   * is the whole resource on a single line -- tens of megabytes for a full
   * Campaign history. Appending to one string and splitting it per chunk
   * rescans every byte already received, so the scan is quadratic in the frame
   * size: on a 48 MB history that is tens of seconds of blocked main thread,
   * during which the progress report this function feeds cannot repaint.
   * Scanning only the newly decoded chunk keeps the cost linear.
   */
  let parts = [];
  let transferred = 0;
  let announced = 0;
  let result = null;

  const consume = (line) => {
    if (!line.trim()) return;
    const frame = JSON.parse(line);
    if (frame.type === "progress") {
      onProgress?.({
        phase: frame.phase,
        percent: frame.percent,
        loaded: transferred,
        total: null,
      });
    } else if (frame.type === "error") {
      const payload = frame.payload ?? {};
      const error = new Error(payload.message ?? "Dashboard resource load failed.");
      error.code = payload.error;
      error.source = payload.source;
      throw error;
    } else if (frame.type === "result") {
      result = frame.payload;
    }
  };

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    transferred += value.byteLength;
    let piece = decoder.decode(value, { stream: true });
    let index;
    while ((index = piece.indexOf("\n")) !== -1) {
      parts.push(piece.slice(0, index));
      const line = parts.join("");
      parts = [];
      piece = piece.slice(index + 1);
      consume(line);
    }
    if (piece) parts.push(piece);
    if (result === null && transferred - announced >= PROGRESS_BYTE_STEP) {
      announced = transferred;
      onProgress?.({ loaded: transferred, total: null });
    }
  }
  parts.push(decoder.decode());
  consume(parts.join(""));
  if (result === null) throw new Error("The backend resource stream ended without data.");
  onProgress?.({ phase: "Dashboard data ready", percent: 100, loaded: transferred });
  return result;
}

/**
 * Apply a history window to a resource a static host served whole.
 *
 * A static file is written at build time and cannot be re-queried, so the
 * bounds are applied here instead of in SQL. The payload is rewritten to report
 * the window that was applied, exactly as the backend does, so a view reads one
 * contract and never asks which deployment it is running in. `earliest` and
 * `latest` are left as the file wrote them: they describe the whole recorded
 * range, which is what tells the reader what a narrowed window excluded.
 */
function windowStaticPayload(payload, window) {
  const research = payload?.simulationResearch;
  if (!research?.historyWindow) return payload;
  const start = window?.start ?? null;
  const end = window?.end ?? null;
  const within = (rows) =>
    (rows ?? []).filter((row) => {
      const date = row.report_date;
      if (!date) return false;
      return !(start && date < start) && !(end && date > end);
    });
  return {
    ...payload,
    simulationResearch: {
      ...research,
      history: start || end ? within(research.history) : research.history ?? [],
      delivery: start || end ? within(research.delivery) : research.delivery ?? [],
      historyWindow: { ...research.historyWindow, start, end },
    },
  };
}

/**
 * Fetch one declared dashboard resource.
 *
 * `window` optionally bounds the observation history by `report_date` as
 * `{start, end}`. A live backend pushes the bounds into its queries so a
 * narrower window transfers less; a static host has only whole files, so the
 * same bounds are applied to the payload after it arrives. Either way the
 * result states the window it was read under.
 */
export async function fetchDashboardResource(
  resource,
  onProgress = null,
  window = null,
) {
  if (!DASHBOARD_RESOURCES.includes(resource)) {
    throw new Error(`Unknown dashboard resource: ${resource}`);
  }
  const query = new URLSearchParams({ stream: "1" });
  if (window?.start) query.set("start", window.start);
  if (window?.end) query.set("end", window.end);
  const url = IS_STATIC
    ? `data/resources/${resource}.json`
    : `/api/dashboard/resources/${encodeURIComponent(resource)}?${query}`;
  const response = await fetch(url, { headers: { Accept: "application/json" } });
  if (!response.ok) {
    const payload = await readJson(response);
    const error = new Error(payload.message || `Failed to load dashboard resource ${resource}.`);
    error.code = payload.error;
    error.source = payload.source;
    throw error;
  }
  if (
    !IS_STATIC &&
    response.headers.get("Content-Type")?.includes("application/x-ndjson")
  ) {
    return readResourceStream(response, onProgress);
  }
  const payload = await readJson(response, onProgress);
  if (!response.ok) {
    const error = new Error(payload.message || `Failed to load dashboard resource ${resource}.`);
    error.code = payload.error;
    error.source = payload.source;
    throw error;
  }
  return IS_STATIC ? windowStaticPayload(payload, window) : payload;
}

/** List every queued, active, and retained backend operator task. */
export async function fetchTasks() {
  if (IS_STATIC) return { concurrency: 0, tasks: [] };
  const response = await fetch("/api/tasks");
  return readJson(response);
}

/** Cancel one queued task or request termination of its running child. */
export async function stopTask(taskId) {
  if (IS_STATIC) throw new Error("Backend tasks are unavailable in the static build.");
  const response = await fetch(`/api/tasks/${encodeURIComponent(taskId)}`, {
    method: "DELETE",
  });
  const payload = await readJson(response);
  if (!response.ok) throw new Error(payload.message ?? "The task could not be stopped.");
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
        artifacts: {
          files: [],
          complete: false,
          canUpload: false,
          canImport: false,
        },
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

/** Upload one complete allow-listed model-output set for backend parsing. */
export async function uploadJobArtifacts(stage, files) {
  if (IS_STATIC) throw new Error("Model output upload requires a live backend.");
  const body = new FormData();
  for (const file of files) body.append("files", file, file.name);
  const response = await fetch(`/api/jobs/${encodeURIComponent(stage)}/artifacts`, {
    method: "POST",
    body,
  });
  const result = await readJson(response);
  if (!response.ok) throw new Error(result.message ?? "Model outputs were not uploaded.");
  return result;
}

/** Ask the backend to import the validated runtime set into PostgreSQL. */
export async function importJobArtifacts(stage) {
  if (IS_STATIC) throw new Error("Model output import requires a live backend.");
  const response = await fetch(
    `/api/jobs/${encodeURIComponent(stage)}/artifacts/import`,
    { method: "POST" },
  );
  const result = await readJson(response);
  if (!response.ok) throw new Error(result.message ?? "Model outputs were not imported.");
  return result;
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
