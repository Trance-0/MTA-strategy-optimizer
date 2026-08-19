/**
 * Export every co-located English documentation Draw.io source to explicit
 * light- and dark-theme SVG files consumed by the VitePress diagram component.
 *
 * A `-human` suffix marks a hand-authored counterpart of a diagram that also
 * has an agent-authored version. Both sources are tracked, because the pair is
 * worth keeping side by side, but only the unsuffixed source is rendered: two
 * renders of one diagram would give a page two published pictures of the same
 * subject with nothing to say which is authoritative. `DrawioDiagram` embeds a
 * basename, so the unsuffixed source is the one a page resolves to, and the
 * `-human` file is opened from the repository rather than from the site.
 */

import { access, readdir } from "node:fs/promises";
import { constants } from "node:fs";
import { dirname, resolve } from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const scriptDirectory = dirname(fileURLToPath(import.meta.url));
const repositoryRoot = resolve(scriptDirectory, "..");
const englishDocumentationRoot = resolve(repositoryRoot, "docs", "en");

/** Sources kept for reference but never rendered to a published SVG. */
const UNRENDERED_SUFFIX = "-human.drawio";

async function findDrawioSources(directory) {
  const sources = [];
  const skipped = [];
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    const entryPath = resolve(directory, entry.name);
    if (entry.isDirectory()) {
      const nested = await findDrawioSources(entryPath);
      sources.push(...nested.sources);
      skipped.push(...nested.skipped);
    } else if (entry.isFile() && entry.name.endsWith(UNRENDERED_SUFFIX)) {
      skipped.push(entryPath);
    } else if (entry.isFile() && entry.name.endsWith(".drawio")) {
      sources.push(entryPath);
    }
  }
  return { sources, skipped };
}

function drawioExecutable() {
  if (process.env.DRAWIO_EXECUTABLE) {
    return process.env.DRAWIO_EXECUTABLE;
  }
  if (process.platform === "win32") {
    return "C:\\Program Files\\draw.io\\draw.io.exe";
  }
  if (process.platform === "darwin") {
    return "/Applications/draw.io.app/Contents/MacOS/draw.io";
  }
  return "drawio";
}

async function assertFile(path) {
  await access(path, constants.R_OK);
}

const executable = drawioExecutable();
const { sources, skipped } = await findDrawioSources(englishDocumentationRoot);

for (const source of sources.sort()) {
  for (const theme of ["light", "dark"]) {
    const output = source.replace(/\.drawio$/i, `.${theme}.drawio.svg`);
    const result = spawnSync(
      executable,
      [
        "--export",
        "--disable-update",
        "--format",
        "svg",
        "--embed-diagram",
        "--transparent",
        "--crop",
        "--theme",
        theme,
        "--output",
        output,
        source,
      ],
      // Electron may leave a helper process holding inherited output handles on
      // Windows. Ignoring stdio lets the CLI process terminate deterministically.
      { stdio: "ignore" },
    );
    if (result.status !== 0) {
      throw new Error(
        `Draw.io export failed for ${source} (${theme}) with status ${result.status}.`,
      );
    }
    await assertFile(output);
  }
}

// The skipped count is reported rather than left silent: a source that is
// tracked but produces no render should be a visible decision, not something a
// reader discovers by finding a diagram missing from the site.
const skippedNote = skipped.length
  ? ` Skipped ${skipped.length} reference-only ${UNRENDERED_SUFFIX} source${
      skipped.length === 1 ? "" : "s"
    }.`
  : "";

console.log(
  `[docs] Exported ${sources.length} Draw.io sources in light and dark themes.${skippedNote}`,
);
