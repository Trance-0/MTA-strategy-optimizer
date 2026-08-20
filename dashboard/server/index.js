/**
 * The dashboard's HTTP server: the JSON API, and the built client beside it.
 *
 * One process serves both, so a local run is one command and one port. The API
 * is the only place that reads a file or opens a database connection; the Vue
 * client is static assets that fetch from it.
 *
 * Run it from the repository root:
 *
 *     ./dashboard/run.sh          # dashboard\run.bat on Windows
 *
 * Data flow:
 *     server/data_source.js -> here -> src/api/client.js -> the six views
 */

import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import express from "express";

import {
  DASHBOARD_ROOT,
  configReadOnly,
  isHosted,
  serverHost,
  serverPort,
  useDatabase,
} from "./config.js";
import {
  clearCaches,
  databaseAvailable,
  loadSnapshot,
  archiveMasterObject,
  saveMasterObject,
  sourceLabel,
} from "./data_source.js";
import {
  applyLogging,
  clearLog,
  log,
  settingsState,
  testConnection,
  writeEnv,
} from "./settings.js";

const here = dirname(fileURLToPath(import.meta.url));
const clientDist = resolve(DASHBOARD_ROOT, "dist");

export function createApp() {
  const app = express();
  app.use(express.json({ limit: "256kb" }));

  /**
   * Liveness only: the Node process is up and Express is routing requests.
   *
   * Deliberately independent of `DATABASE`/`PG_*` and of `attribution_result`
   * having rows, unlike `/api/dashboard`. A release with no data loaded yet is
   * still a successfully deployed release; conflating the two meant a deploy
   * could never go healthy until the database was seeded, and a rollback to a
   * perfectly good prior release would fail the exact same way.
   */
  app.get("/api/health", (request, response) => {
    response.json({ ok: true });
  });

  /**
   * The whole snapshot in one response.
   *
   * A database that is configured but unreachable is reported as a page-level
   * state rather than as a failed fetch inside whichever chart read it first,
   * which is what lets the client name both remedies.
   */
  app.get("/api/dashboard", async (request, response) => {
    const started = Date.now();
    try {
      if (useDatabase()) {
        const { usable, message } = await databaseAvailable();
        if (!usable) {
          log("ERROR", "data_source", `database unusable: ${message}`);
          response.status(503).json({
            error: "database_unavailable",
            message,
            source: sourceLabel(),
          });
          return;
        }
      }
      const snapshot = await loadSnapshot();
      log(
        "INFO",
        "data_source",
        `snapshot from ${snapshot.mode} in ${Date.now() - started} ms`,
      );
      response.json(snapshot);
    } catch (error) {
      log("ERROR", "data_source", `${error.name}: ${error.message}`);
      response.status(500).json({
        error: "load_failed",
        message: `${error.name}: ${String(error.message).slice(0, 400)}`,
      });
    }
  });

  /** Drop the cached reads so the next request hits the source again. */
  app.post("/api/reload", (request, response) => {
    clearCaches();
    log("INFO", "data_source", "caches cleared by the reload control");
    response.json({ ok: true });
  });

  /**
   * Save an editable master/configuration draft for a future simulator run.
   * Generated delivery, budget, outcome, and path tables have no mutation
   * route, which keeps historical experiments reproducible.
   */
  app.put("/api/master/:entityType/:entityId", async (request, response) => {
    try {
      const saved = await saveMasterObject(
        request.params.entityType,
        request.params.entityId,
        request.body?.payload,
      );
      response.json({ ok: true, object: saved });
    } catch (error) {
      response.status(useDatabase() ? 400 : 403).json({
        error: "master_write_rejected",
        message: error.message,
      });
    }
  });

  /** Archive a future-run draft; this never deletes generated history. */
  app.delete("/api/master/:entityType/:entityId", async (request, response) => {
    try {
      const archived = await archiveMasterObject(
        request.params.entityType,
        request.params.entityId,
      );
      response.json({ ok: true, object: archived });
    } catch (error) {
      response.status(useDatabase() ? 400 : 403).json({
        error: "master_archive_rejected",
        message: error.message,
      });
    }
  });

  app.get("/api/settings", async (request, response) => {
    response.json(await settingsState());
  });

  /**
   * Apply a settings change.
   *
   * `test` probes the entered values without saving them. `save` rewrites
   * `.env`. `logging` toggles the capture. The published build accepts none of
   * them: it has no writable `.env` and no socket, so a change could not take
   * effect and pretending otherwise would invite a real password into a page
   * that cannot use it.
   */
  app.post("/api/settings", async (request, response) => {
    if (isHosted()) {
      response.status(403).json({
        error: "hosted",
        message:
          "The published build reads the repository's committed sample files " +
          "and cannot open a database connection.",
      });
      return;
    }

    if (configReadOnly()) {
      response.status(403).json({
        error: "read_only_configuration",
        message:
          "This server reads protected deployment configuration. Change it " +
          "through the server deployment environment, then restart the service.",
      });
      return;
    }

    const { action, connection, logging } = request.body ?? {};

    if (action === "logging") {
      applyLogging(Boolean(logging?.enabled), logging?.level ?? "INFO");
      response.json(await settingsState());
      return;
    }

    if (action === "clearLog") {
      clearLog();
      response.json(await settingsState());
      return;
    }

    const updates = {
      DATABASE: request.body?.useDatabase ? "true" : "false",
      PG_HOST: String(connection?.PG_HOST ?? "").trim(),
      PG_PORT: String(connection?.PG_PORT ?? "").trim() || "5432",
      PG_DATABASE: String(connection?.PG_DATABASE ?? "").trim(),
      PG_USER: String(connection?.PG_USER ?? "").trim(),
      PG_PASSWORD: String(connection?.PG_PASSWORD ?? ""),
      PG_SSLMODE: String(connection?.PG_SSLMODE ?? "prefer"),
    };

    // An empty password field means "keep the stored one" rather than "clear
    // it", because the dialog never receives the stored value to echo back.
    if (updates.PG_PASSWORD === "") {
      const { readEnv } = await import("./settings.js");
      updates.PG_PASSWORD = readEnv().PG_PASSWORD ?? "";
    }

    if (action === "test") {
      const result = await testConnection(updates);
      log("INFO", "settings", `connection test: ${result.ok ? "ok" : "failed"}`);
      response.json(result);
      return;
    }

    if (action === "save") {
      await writeEnv(updates);
      log("INFO", "settings", "credentials written to .env, caches cleared");
      response.json({ ok: true, ...(await settingsState()) });
      return;
    }

    response.status(400).json({ error: "unknown_action" });
  });

  // The built client, when there is one. `vite build` writes it to
  // `dashboard/dist`; `npm run dev` serves the sources from Vite instead and
  // proxies `/api` here, so this branch is simply absent during development.
  if (existsSync(clientDist)) {
    app.use(express.static(clientDist));
    // The client routes on the hash, so every path resolves to one document.
    app.get(/^\/(?!api\/).*/, (request, response) => {
      response.sendFile(resolve(clientDist, "index.html"));
    });
  }

  return app;
}

/**
 * Open the dashboard in the reader's default browser.
 *
 * Only when the launcher asks for it, so a server started by hand or by a test
 * never steals focus. Failure is silent by design: a machine with no browser,
 * or a headless session, is not a reason to fail a server that started.
 */
function openBrowser(url) {
  const command =
    process.platform === "win32"
      ? ["cmd", ["/c", "start", "", url]]
      : process.platform === "darwin"
        ? ["open", [url]]
        : ["xdg-open", [url]];
  try {
    spawn(command[0], command[1], { stdio: "ignore", detached: true }).unref();
  } catch {
    // No browser to open. The URL is printed either way.
  }
}

// Started directly rather than imported by a test.
if (process.argv[1] && resolve(process.argv[1]) === resolve(here, "index.js")) {
  const port = Number.parseInt(process.argv[2] ?? "", 10) || serverPort();
  const host = serverHost();
  const displayHost = host.includes(":") ? `[${host}]` : host;
  const url = `http://${displayHost}:${port}`;

  /**
   * `listen()` is called with no callback and the two outcomes are handled as
   * events, because Express aliases the two: `app.listen(port, done)` runs
   *
   *     server.once("error", done)
   *
   * as well as passing `done` to `server.listen`, so a callback written for a
   * successful bind also runs on failure — with the error as a first argument
   * an arrow function taking none silently drops. On an occupied port that
   * prints "Listening on …" and then the EADDRINUSE report below it.
   */
  const server = createApp().listen(port, host);

  server.on("listening", () => {
    if (!existsSync(clientDist)) {
      console.log(
        "[dashboard] No built client in dashboard/dist. " +
          "Run `npm run build` in dashboard/ to create one.",
      );
    }
    console.log(`[dashboard] Reading from ${sourceLabel()}`);
    console.log(`[dashboard] Listening on ${url}`);
    console.log("[dashboard] Press Ctrl+C to stop.");
    if (process.env.DASHBOARD_OPEN === "1") openBrowser(url);
  });

  /**
   * A port already in use is the most common local failure, and Node's default
   * report for it is an unhandled `EADDRINUSE` stack trace naming neither the
   * port nor the remedy. Naming both here means the launchers do not each need
   * their own port probe.
   *
   * The handler goes on the `Server` that `listen()` returns, not on the
   * Express app: the app is an EventEmitter too, so `app.on("error", …)`
   * registers happily and is simply never called, and the failure escapes as
   * the raw stack trace this exists to replace.
   */
  server.on("error", (error) => {
    if (error.code === "EADDRINUSE") {
      console.error(
        `\n[dashboard] Port ${port} is already in use.\n\n` +
          "  Another program holds it — often a dashboard left running by an\n" +
          "  earlier session. Either stop that one, or start this on a free\n" +
          `  port:\n\n` +
          `      ./dashboard/run.sh ${port + 1}      # dashboard\\run.bat ${port + 1} on Windows\n`,
      );
    } else if (error.code === "EACCES") {
      console.error(
        `\n[dashboard] Not permitted to listen on port ${port}.\n\n` +
          "  Ports below 1024 are reserved on most systems. Choose a higher\n" +
          "  one, for example 8501.\n",
      );
    } else {
      console.error(`\n[dashboard] Could not start the server: ${error.message}\n`);
    }
    process.exit(1);
  });
}
