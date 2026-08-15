/**
 * Write the dashboard snapshot to a JSON file for the published static build.
 *
 * GitHub Pages serves static files and cannot run the Express API, so the
 * published client fetches `data/snapshot.json` instead of `/api/dashboard`.
 * This command produces that file from the same loaders the API calls, which
 * is what keeps the two deployments one codebase rather than two: a view
 * cannot tell which it is reading, exactly as it cannot tell files from the
 * database.
 *
 * The export is forced to file mode. The published site is a static host with
 * no socket to reach PostgreSQL, and a snapshot exported from a database would
 * bake one deployment's private data into a public artifact.
 *
 *   node script/export_dashboard_snapshot.mjs [outputPath]
 *
 * Defaults to `dashboard/public/data/snapshot.json`, which Vite copies into
 * the build output verbatim.
 *
 * Data flow:
 *     dashboard/server/data_source.js -> here -> data/snapshot.json
 *         -> dashboard/src/api/client.js -> the six views
 */

import { mkdir, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = resolve(HERE, "..");

// Pinned before `data_source.js` is imported: `config.js` caches the mode on
// first read, so setting it afterwards would have no effect.
process.env.DATABASE = "false";
process.env.DASHBOARD_HOSTED = "true";

const { loadSnapshot } = await import(
  new URL("../dashboard/server/data_source.js", import.meta.url)
);

const outputPath = resolve(
  REPO_ROOT,
  process.argv[2] ?? "dashboard/public/data/snapshot.json",
);

const snapshot = await loadSnapshot();

if (snapshot.mode !== "local files") {
  console.error(
    `Refusing to export: the snapshot reports mode "${snapshot.mode}" rather ` +
      "than the committed files. A published snapshot must never carry data " +
      "read from a private database.",
  );
  process.exit(1);
}

await mkdir(dirname(outputPath), { recursive: true });
// No pretty-printing: the payload is machine-read, and indentation adds
// roughly a third to a file every visitor downloads.
const json = JSON.stringify(snapshot);
await writeFile(outputPath, json, "utf8");

const rows = Object.entries(snapshot)
  .filter(([, value]) => Array.isArray(value))
  .reduce((total, [, value]) => total + value.length, 0);

console.log(
  `Wrote ${outputPath.replace(REPO_ROOT + "\\", "").replace(REPO_ROOT + "/", "")} ` +
    `— ${rows} rows, ${(json.length / 1024).toFixed(0)} KB, read from ${snapshot.source}.`,
);
