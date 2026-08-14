/**
 * Assemble the GitHub Pages site: the dashboard at the root, the documentation
 * under `/docs/`.
 *
 * Pages serves static files only, so the dashboard runs in the browser through
 * stlite rather than on a Streamlit server. This script copies the same
 * `dashboard/` sources the local `streamlit run` uses -- the web build is a
 * different runtime, never a different codebase -- along with the committed
 * sample artifacts the file-mode loaders read, and the stlite runtime from
 * `node_modules`.
 *
 * Run it after the VitePress build, which must have been built with
 * `DOCS_BASE_PATH` ending in `/docs/`:
 *
 *   node script/build_pages_site.mjs
 *
 * Output goes to `site/`, which is what the Pages workflow uploads.
 */

import { cp, mkdir, rm, readdir, stat, writeFile } from "node:fs/promises";
import { existsSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const scriptDirectory = dirname(fileURLToPath(import.meta.url));
const repositoryRoot = resolve(scriptDirectory, "..");
const outputRoot = resolve(repositoryRoot, "site");

/** The stlite runtime, installed as a dev dependency of the docs package. */
const stliteBuild = resolve(
  repositoryRoot,
  "docs",
  "node_modules",
  "@stlite",
  "browser",
  "build",
);

/**
 * Python files the app imports in file mode.
 *
 * `dashboard/models.py` is excluded deliberately: it declares the PostgreSQL
 * schema, which a browser cannot reach, and nothing imports it when reading
 * files. `dashboard/tests/` is excluded because the published app does not run
 * them. Both exclusions are asserted against `web/index.html` below, so the
 * two lists cannot drift apart silently.
 */
const pythonFiles = [
  "dashboard/__init__.py",
  "dashboard/app.py",
  "dashboard/config.py",
  "dashboard/data_source.py",
  "dashboard/settings.py",
  "dashboard/theme.py",
  "dashboard/views/__init__.py",
  "dashboard/views/budget_manager.py",
  "dashboard/views/campaign_optimizer.py",
  "dashboard/views/campaigns.py",
  "dashboard/views/command_center.py",
  "dashboard/views/common.py",
  "dashboard/views/knowledge_base.py",
  "dashboard/views/optimization_log.py",
];

/**
 * The committed artifacts the file-mode loaders open, at the same
 * repository-relative paths `dashboard/config.py` resolves.
 *
 * `synthetic_user_events_sample.csv` is not here: at 2.8 MB it is by far the
 * largest artifact and no view reads it, so publishing it would cost every
 * visitor a download for nothing.
 */
const dataFiles = [
  "modules/mta_attribution/data/simulated/amazon_ads_report_sample.csv",
  "modules/mta_attribution/data/simulated/amc_mta_path_report_raw_sample.csv",
  "modules/mta_attribution/data/simulated/amc_touchpoint_entity_aggregate_sample.csv",
  "modules/mta_attribution/outputs/attribution/amc_markov_attribution_results.csv",
  "modules/mta_attribution/outputs/attribution/amc_shapley_attribution_results.csv",
  "modules/mta_attribution/outputs/attribution/amc_mta_model_comparison_touchpoints.csv",
  "modules/mta_attribution/outputs/attribution/amc_mta_model_comparison_summary.csv",
  "modules/mta_attribution/outputs/attribution/amc_mta_recommended_attribution.csv",
  "modules/mta_strategy_recommendation/data/simulated/strategy_request.json",
  "modules/mta_strategy_recommendation/data/simulated/candidate_pool.json",
  "modules/mta_strategy_recommendation/outputs/initial_budget_recommendation.json",
];

async function copyInto(relativePath) {
  const source = resolve(repositoryRoot, relativePath);
  if (!existsSync(source)) {
    throw new Error(`Missing file required by the Pages build: ${relativePath}`);
  }
  const destination = resolve(outputRoot, relativePath);
  await mkdir(dirname(destination), { recursive: true });
  await cp(source, destination);
}

async function directorySize(directory) {
  let total = 0;
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    const entryPath = join(directory, entry.name);
    total += entry.isDirectory()
      ? await directorySize(entryPath)
      : (await stat(entryPath)).size;
  }
  return total;
}

/**
 * Fail the build when `web/index.html` and this script disagree about which
 * files the app needs. The loader lists them for the browser and this script
 * copies them; a file added to one and not the other would surface as a
 * missing-module error in a visitor's console rather than here.
 */
async function assertLoaderAgrees() {
  const loader = await import("node:fs/promises").then((fs) =>
    fs.readFile(resolve(repositoryRoot, "web", "index.html"), "utf8"),
  );
  const missing = [...pythonFiles, ...dataFiles].filter(
    (path) => !loader.includes(`"${path}"`),
  );
  if (missing.length > 0) {
    throw new Error(
      "web/index.html does not list these files that the build copies:\n  " +
        missing.join("\n  "),
    );
  }
}

async function main() {
  await assertLoaderAgrees();

  const documentationDist = resolve(repositoryRoot, "docs", ".vitepress", "dist");
  if (!existsSync(documentationDist)) {
    throw new Error(
      "docs/.vitepress/dist is missing. Build the documentation first:\n" +
        "  cd docs && DOCS_BASE_PATH=/<repo>/docs/ npm run build",
    );
  }
  if (!existsSync(stliteBuild)) {
    throw new Error(
      "The stlite runtime is missing. Install the docs dependencies first:\n" +
        "  cd docs && npm ci",
    );
  }

  await rm(outputRoot, { recursive: true, force: true });
  await mkdir(outputRoot, { recursive: true });

  // The dashboard shell and the runtime that executes it.
  await copyInto("web/index.html");
  await cp(resolve(outputRoot, "web", "index.html"), resolve(outputRoot, "index.html"));
  await rm(resolve(outputRoot, "web"), { recursive: true, force: true });

  // The runtime ships source maps that no visitor fetches; at roughly 58 MB
  // they are two thirds of the published site on their own.
  await cp(stliteBuild, resolve(outputRoot, "stlite"), {
    recursive: true,
    filter: (source) => !source.endsWith(".map"),
  });

  for (const path of [...pythonFiles, ...dataFiles]) {
    await copyInto(path);
  }

  // The documentation, one level down. Pages has no server-side rewrite, so the
  // VitePress build must already carry `/docs/` as its base.
  await cp(documentationDist, resolve(outputRoot, "docs"), { recursive: true });

  // Jekyll would otherwise drop the `_`-prefixed files inside the built assets.
  await writeFile(resolve(outputRoot, ".nojekyll"), "");

  const megabytes = ((await directorySize(outputRoot)) / 1024 / 1024).toFixed(1);
  console.log(
    `[pages] Assembled site/ with the dashboard at the root and the ` +
      `documentation under /docs/: ${pythonFiles.length} Python files, ` +
      `${dataFiles.length} sample artifacts, ${megabytes} MB total.`,
  );
}

await main();
