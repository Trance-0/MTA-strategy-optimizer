/**
 * Vite configuration for the dashboard client.
 *
 * Two build targets share one source tree:
 *
 *   vite build                  the local build, which fetches dashboard
 *                               resources from the Flask backend beside it
 *   vite build --mode static    the published build, which fetches
 *                               `data/resources/*.json` written at build time
 *
 * `base` is relative in the static build because GitHub Pages serves a project
 * site from a subdirectory, and an absolute asset path would resolve against
 * the domain root instead.
 */

import vue from "@vitejs/plugin-vue";
import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig } from "vite";

const DASHBOARD_DIR = dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = resolve(DASHBOARD_DIR, "..");
const COMMIT = /^(?:[0-9a-f]{40}|[0-9a-f]{64})$/i;

function buildVersion() {
  try {
    const value = readFileSync(resolve(REPO_ROOT, "VERSION"), "utf8").trim();
    return /^\d+\.\d+\.\d+$/.test(value) ? value : "unknown";
  } catch {
    return "unknown";
  }
}

function buildCommit() {
  for (const value of [process.env.BUILD_COMMIT, process.env.GITHUB_SHA]) {
    if (COMMIT.test(value ?? "")) return value.toLowerCase();
  }
  try {
    const value = execFileSync("git", ["-C", REPO_ROOT, "rev-parse", "HEAD"], {
      encoding: "utf8",
      timeout: 2000,
      stdio: ["ignore", "pipe", "ignore"],
    }).trim();
    return COMMIT.test(value) ? value.toLowerCase() : "unknown";
  } catch {
    return "unknown";
  }
}

export default defineConfig(({ mode }) => ({
  plugins: [vue()],
  base: mode === "static" ? "./" : "/",
  define: {
    "import.meta.env.VITE_STATIC_BUILD": JSON.stringify(String(mode === "static")),
    __DASHBOARD_VERSION__: JSON.stringify(buildVersion()),
    __DASHBOARD_COMMIT__: JSON.stringify(buildCommit()),
  },
  build: {
    outDir: mode === "static" ? "dist-static" : "dist",
    emptyOutDir: true,
    // Plotly is large and versioned independently of the app code, so it is
    // split out: a change to a view leaves the visitor's cached copy intact.
    // Vite 8 bundles with Rolldown, which takes only the function form of
    // `manualChunks`; the object form fails the build rather than being
    // normalised, so the mapping is written as a lookup over the module id.
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes("plotly.js-dist-min")) return "plotly";
          if (/node_modules[\\/]@?vue/.test(id)) return "vue";
          return null;
        },
      },
    },
  },
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8501",
        changeOrigin: true,
      },
    },
  },
}));
