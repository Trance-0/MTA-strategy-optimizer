/**
 * Vite configuration for the dashboard client.
 *
 * Two build targets share one source tree:
 *
 *   vite build                  the local build, which fetches `/api/dashboard`
 *                               from the Express server beside it
 *   vite build --mode static    the published build, which fetches
 *                               `data/snapshot.json` written at build time
 *
 * `base` is relative in the static build because GitHub Pages serves a project
 * site from a subdirectory, and an absolute asset path would resolve against
 * the domain root instead.
 */

import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

export default defineConfig(({ mode }) => ({
  plugins: [vue()],
  base: mode === "static" ? "./" : "/",
  define: {
    "import.meta.env.VITE_STATIC_BUILD": JSON.stringify(String(mode === "static")),
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
