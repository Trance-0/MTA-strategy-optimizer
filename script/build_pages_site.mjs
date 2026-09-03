/**
 * Assemble the GitHub Pages site: the dashboard at the root, the documentation
 * under `/docs/`.
 *
 * Pages serves static files only, so the published dashboard is the Vue client
 * built in static mode: it fetches files below `data/resources/`, exported
 * from committed artifacts at build time, instead of the Flask API. The client
 * source is the same one the local run serves — the published build is a
 * different data path, never a different codebase.
 *
 * Run it after both builds:
 *
 *   uv run --extra backend python -m script.export_dashboard_snapshot
 *   cd dashboard && npm run build:static && cd ..
 *   cd docs && DOCS_BASE_PATH=/<repo>/docs/ npm run build && cd ..
 *   node script/build_pages_site.mjs
 *
 * The documentation must be built with `DOCS_BASE_PATH` ending in `/docs/`,
 * because Pages performs no rewrites and every internal link is resolved at
 * build time.
 *
 * Output goes to `site/`, which is what the Pages workflow uploads.
 *
 * Data flow:
 *     dashboard/dist-static + docs/.vitepress/dist -> here -> site/
 */

import { cp, mkdir, readdir, rm, stat, writeFile } from "node:fs/promises";
import { existsSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { verifyPublishedOntologyReviewBundle } from "./import_ontology_review_fixtures.mjs";

const scriptDirectory = dirname(fileURLToPath(import.meta.url));
const repositoryRoot = resolve(scriptDirectory, "..");
const outputRoot = resolve(repositoryRoot, "site");

const dashboardBuild = resolve(repositoryRoot, "dashboard", "dist-static");
const documentationBuild = resolve(repositoryRoot, "docs", ".vitepress", "dist");

/** Total bytes and file count under a directory. */
async function measure(directory) {
  let bytes = 0;
  let files = 0;
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    const path = join(directory, entry.name);
    if (entry.isDirectory()) {
      const nested = await measure(path);
      bytes += nested.bytes;
      files += nested.files;
    } else {
      bytes += (await stat(path)).size;
      files += 1;
    }
  }
  return { bytes, files };
}

function fail(message) {
  console.error(`build_pages_site: ${message}`);
  process.exit(1);
}

if (!existsSync(dashboardBuild)) {
  fail(
    "The dashboard has not been built for a static host. Run " +
      "`npm run build:static` in dashboard/ first.",
  );
}

// The shell resource is required by every route. Without it every
// view renders its error card, which would reach a visitor as a broken page
// rather than as a failed build.
const shellResource = resolve(dashboardBuild, "data", "resources", "shell.json");
if (!existsSync(shellResource)) {
  fail(
    "The static build carries no data/resources/shell.json. Run " +
      "`uv run --extra backend python -m script.export_dashboard_snapshot` " +
      "before building the client.",
  );
}

if (!existsSync(documentationBuild)) {
  fail(
    "The documentation has not been built. Run `npm run build` in docs/ with " +
      "DOCS_BASE_PATH set to the Pages base path plus `docs/`.",
  );
}

await rm(outputRoot, { recursive: true, force: true });
await mkdir(outputRoot, { recursive: true });

await cp(dashboardBuild, outputRoot, { recursive: true });
await cp(documentationBuild, join(outputRoot, "docs"), { recursive: true });
await verifyPublishedOntologyReviewBundle(join(outputRoot, "data", "ontology-review"));

// Without this marker Pages runs Jekyll, which drops the underscore-prefixed
// files inside the built assets.
await writeFile(join(outputRoot, ".nojekyll"), "", "utf8");

const { bytes, files } = await measure(outputRoot);
console.log(
  `Assembled site/ — ${files} files, ${(bytes / 1024 / 1024).toFixed(1)} MB. ` +
    "Dashboard at the root, documentation under /docs/.",
);
