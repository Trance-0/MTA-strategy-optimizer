/**
 * Assert that the dashboard's loaders return the same snapshot whether
 * `DATABASE` is true or false.
 *
 * This is the Node counterpart of `script/verify_source_parity.py`, and it
 * enforces the contract `dashboard/server/data_source.js` documents: a view
 * must never be able to tell which source it is reading, so every loader must
 * return the same fields, types, values, AND row order in both modes.
 *
 * Row order is part of the contract, not an accident of it. The views render
 * tables in the order the loader returns them, so two modes that agree on
 * contents but disagree on order put the same four Campaigns on screen in two
 * different sequences.
 *
 * The two modes run in separate child processes, because `config.js` caches
 * the mode after the first read and one process therefore cannot hold both.
 *
 *   node script/verify_dashboard_parity.mjs
 *
 * Exits non-zero naming every field that differs. Requires a populated
 * PostgreSQL instance configured in `.env`; it is a command rather than a unit
 * test for that reason.
 *
 * Data flow:
 *     dashboard/server/data_source.js -> here -> a pass/fail report
 */

import { spawnSync } from "node:child_process";
import { dirname, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = resolve(HERE, "..");
const DASHBOARD = resolve(REPO_ROOT, "dashboard");

/**
 * Load one snapshot in a child process with `DATABASE` forced to `mode`.
 *
 * The child prints the snapshot as JSON on stdout and nothing else, so a log
 * line from a loader cannot corrupt the payload.
 */
function snapshotFor(useDatabase) {
  // Imported as a `file://` URL: a Windows absolute path begins with a drive
  // letter, which the ESM loader reads as an unsupported URL scheme.
  const source = `
    import { loadSnapshot } from ${JSON.stringify(
      pathToFileURL(resolve(DASHBOARD, "server", "data_source.js")).href,
    )};
    const snapshot = await loadSnapshot();
    process.stdout.write(JSON.stringify(snapshot));
    process.exit(0);
  `;
  const result = spawnSync(
    process.execPath,
    ["--input-type=module", "--eval", source],
    {
      cwd: DASHBOARD,
      env: { ...process.env, DATABASE: useDatabase ? "true" : "false", DASHBOARD_HOSTED: "" },
      encoding: "utf8",
      maxBuffer: 256 * 1024 * 1024,
    },
  );
  if (result.status !== 0) {
    throw new Error(
      `Loading the ${useDatabase ? "database" : "file"} snapshot failed:\n${
        result.stderr || result.stdout
      }`,
    );
  }
  return JSON.parse(result.stdout);
}

/**
 * Collect every difference between two values, depth-first.
 *
 * Reports the full path to each difference rather than the first one, because
 * a single normalisation bug usually shows up in many fields at once and the
 * pattern across them is what identifies the cause.
 */
function diff(a, b, path, out) {
  if (out.length >= 200) return;
  const typeOf = (v) =>
    v === null ? "null" : Array.isArray(v) ? "array" : typeof v;
  if (typeOf(a) !== typeOf(b)) {
    out.push(`${path}: type ${typeOf(a)} (database) vs ${typeOf(b)} (files)`);
    return;
  }
  if (Array.isArray(a)) {
    if (a.length !== b.length) {
      out.push(`${path}: ${a.length} rows (database) vs ${b.length} rows (files)`);
      return;
    }
    for (let i = 0; i < a.length; i += 1) diff(a[i], b[i], `${path}[${i}]`, out);
    return;
  }
  if (a !== null && typeof a === "object") {
    for (const key of [...new Set([...Object.keys(a), ...Object.keys(b)])].sort()) {
      if (!(key in a)) {
        out.push(`${path}.${key}: absent in database mode`);
      } else if (!(key in b)) {
        out.push(`${path}.${key}: absent in file mode`);
      } else {
        diff(a[key], b[key], `${path}.${key}`, out);
      }
    }
    return;
  }
  if (a !== b) {
    out.push(
      `${path}: ${JSON.stringify(a)} (database) vs ${JSON.stringify(b)} (files)`,
    );
  }
}

/**
 * Fields that are legitimately absent in database mode.
 *
 * The strategy JSON artifacts carry pipeline configuration and derivation
 * detail the relational schema does not model: capacity rules are inputs to
 * the pipeline rather than observations, and the per-campaign derivation
 * breakdown is intermediate arithmetic. No view reads them, and adding tables
 * for them would mean the database stored figures the dashboard is forbidden
 * to recompute. They are listed here so the exemption is explicit and a new
 * absence is still a failure.
 */
const ALLOWED_DB_ABSENCES = [
  /^strategyRequest\.capacity_rules\./,
  /^strategyRequest\.mta_source\.(attribution_file|entity_file|available_touchpoint_count|entity_row_count)$/,
  /^budgetRecommendation\.budget_derivation\.(?!formula_version$|normalization_universe$|outcome_weights)/,
  /^budgetRecommendation\.campaigns\[\d+\]\.(count_rationale|bridge_summary)\./,
];

function main() {
  console.log("Loading the database snapshot...");
  const database = snapshotFor(true);
  console.log("Loading the file snapshot...");
  const files = snapshotFor(false);

  if (database.mode !== "database") {
    console.error(
      `Expected the first snapshot to read the database but it read ` +
        `"${database.mode}". Set DATABASE=true and the PG_* values in .env.`,
    );
    process.exit(2);
  }

  const loaders = Object.keys(database).filter(
    (key) => key !== "mode" && key !== "source",
  );

  let failed = 0;
  for (const loader of loaders) {
    const found = [];
    diff(database[loader], files[loader], loader, found);
    const real = found.filter(
      (line) =>
        !(
          line.endsWith("absent in database mode") &&
          ALLOWED_DB_ABSENCES.some((pattern) => pattern.test(line.split(":")[0]))
        ),
    );
    const exempt = found.length - real.length;
    const count = Array.isArray(database[loader])
      ? `${database[loader].length} rows`
      : `${Object.keys(database[loader]).length} keys`;

    if (real.length === 0) {
      console.log(
        `  ok    ${loader.padEnd(24)} ${count}` +
          (exempt > 0 ? `  (${exempt} documented absences)` : ""),
      );
      continue;
    }
    failed += 1;
    console.log(`  FAIL  ${loader.padEnd(24)} ${real.length} difference(s)`);
    for (const line of real.slice(0, 10)) console.log(`          ${line}`);
    if (real.length > 10) console.log(`          ... and ${real.length - 10} more`);
  }

  console.log("");
  if (failed > 0) {
    console.error(
      `${failed} of ${loaders.length} loaders differ between the two sources.`,
    );
    process.exit(1);
  }
  console.log(
    `All ${loaders.length} loaders return identical fields, values, and row ` +
      `order in both modes.`,
  );
}

main();
