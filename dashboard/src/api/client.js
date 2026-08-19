/**
 * The client's single route to the data.
 *
 * Two deployments share one contract. A local run fetches `/api/dashboard`
 * from the Express server beside it; the published static build has no server,
 * so `scripts/export_static_data.mjs` writes the same payload to
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

async function readJson(response) {
  const text = await response.text();
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
export async function fetchDashboard() {
  const response = await fetch(SNAPSHOT_URL, { headers: { Accept: "application/json" } });
  const payload = await readJson(response);
  if (!response.ok) {
    const error = new Error(payload.message || "Failed to load the dashboard data.");
    error.code = payload.error;
    error.source = payload.source;
    throw error;
  }
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
      connection: null,
      status: {
        label: "Sample data",
        colour: "#9db7e8",
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
