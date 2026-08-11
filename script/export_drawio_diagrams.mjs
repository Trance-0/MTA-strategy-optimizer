/**
 * Export every co-located English documentation Draw.io source to explicit
 * light- and dark-theme SVG files consumed by the VitePress diagram component.
 */

import { access, readdir } from "node:fs/promises";
import { constants } from "node:fs";
import { dirname, resolve } from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const scriptDirectory = dirname(fileURLToPath(import.meta.url));
const repositoryRoot = resolve(scriptDirectory, "..");
const englishDocumentationRoot = resolve(repositoryRoot, "docs", "en");

async function findDrawioSources(directory) {
  const sources = [];
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    const entryPath = resolve(directory, entry.name);
    if (entry.isDirectory()) {
      sources.push(...(await findDrawioSources(entryPath)));
    } else if (entry.isFile() && entry.name.endsWith(".drawio")) {
      sources.push(entryPath);
    }
  }
  return sources;
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
const sources = await findDrawioSources(englishDocumentationRoot);

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

console.log(`[docs] Exported ${sources.length} Draw.io sources in light and dark themes.`);
