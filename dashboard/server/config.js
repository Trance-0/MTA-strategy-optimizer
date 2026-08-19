/**
 * Environment configuration and repository paths for the dashboard.
 *
 * Reads `.env` at the repository root. The single switch that matters is
 * `DATABASE`: when false the dashboard reads the committed CSV and JSON files
 * directly, and when true it reads the PostgreSQL database described by the
 * `PG_*` variables.
 *
 * `.env` is git-ignored. `sample.env` is the tracked template; copy it and fill
 * in real values. Never put real credentials in a tracked file.
 *
 * Data flow:
 *     .env -> here -> server/data_source.js -> the API -> the Vue views
 */

import { existsSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import dotenv from "dotenv";

const here = dirname(fileURLToPath(import.meta.url));

/** Repository root, two levels above this file. */
export const REPO_ROOT = resolve(here, "..", "..");

export const DASHBOARD_ROOT = resolve(here, "..");

const ATTRIBUTION_MODULE = resolve(REPO_ROOT, "modules", "mta_attribution");
const STRATEGY_MODULE = resolve(
  REPO_ROOT,
  "modules",
  "mta_strategy_recommendation",
);

export const SIMULATED_DIR = resolve(ATTRIBUTION_MODULE, "data", "simulated");
export const ATTRIBUTION_OUTPUT_DIR = resolve(
  ATTRIBUTION_MODULE,
  "outputs",
  "attribution",
);
export const STRATEGY_INPUT_DIR = resolve(STRATEGY_MODULE, "data", "simulated");
export const STRATEGY_OUTPUT_DIR = resolve(STRATEGY_MODULE, "outputs");

/**
 * Return the optional MTA-SIM CSV run used by file-mode research views.
 *
 * When unset, the dashboard keeps using its committed module fixtures. The
 * path is deliberately configuration rather than a cross-repository import:
 * MTA-SIM and this project remain independently runnable.
 */
export function simulatorDataDirectory() {
  loadEnv();
  const configured = String(process.env.MTA_SIM_DATA_DIR ?? "").trim();
  return configured ? resolve(configured) : null;
}

/**
 * Amazon Ads and path-report samples carry a Chinese field-description row
 * directly under the header. It is documentation, not data, and every reader
 * must drop it before parsing numbers.
 */
export const DESCRIPTION_ROW_MARKERS = ["报告日期", "报告开始日期"];

const TRUE_VALUES = new Set(["1", "true", "yes", "on"]);

let loaded = false;

/** Load `.env` from the repository root, without overriding real env vars. */
function loadEnv() {
  if (loaded) return;
  const path = resolve(REPO_ROOT, ".env");
  if (existsSync(path)) {
    dotenv.config({ path, override: false, quiet: true });
  }
  loaded = true;
}

function flag(name) {
  loadEnv();
  return TRUE_VALUES.has(String(process.env[name] ?? "").trim().toLowerCase());
}

/**
 * Return true when running as the published static build.
 *
 * The static build has no Node process behind it: `scripts/export_static_data.mjs`
 * writes the snapshot to a JSON file at build time and the browser fetches that
 * file directly. There is no socket to reach PostgreSQL with and no writable
 * `.env`, so the flag lets the settings dialog say so plainly instead of
 * offering controls that could never take effect.
 */
export function isHosted() {
  return flag("DASHBOARD_HOSTED");
}

/** Return true when the dashboard should read from PostgreSQL. */
export function useDatabase() {
  if (isHosted()) return false;
  return flag("DATABASE");
}

/**
 * Return the configured PostgreSQL settings.
 *
 * Throws naming every missing variable and pointing at `sample.env`, rather
 * than failing later at connection time with a misleading network error.
 */
export function databaseSettings() {
  loadEnv();
  const missing = ["PG_HOST", "PG_DATABASE", "PG_USER", "PG_PASSWORD"].filter(
    (name) => !process.env[name],
  );
  if (missing.length > 0) {
    throw new Error(
      `Missing required environment variable(s): ${missing.join(", ")}. ` +
        "Copy sample.env to .env and fill in the connection details, " +
        "or set DATABASE=false to read the local CSV files instead.",
    );
  }
  return {
    host: process.env.PG_HOST,
    port: Number.parseInt(process.env.PG_PORT || "5432", 10),
    database: process.env.PG_DATABASE,
    user: process.env.PG_USER,
    password: process.env.PG_PASSWORD,
    sslmode: process.env.PG_SSLMODE || "prefer",
  };
}

/**
 * Return a display string that never contains the password.
 *
 * This is the only rendering of a connection the dashboard performs. The
 * password is omitted by construction rather than masked, so no future edit
 * can accidentally widen it.
 */
export function safeSummary(settings = databaseSettings()) {
  return `${settings.user}@${settings.host}:${settings.port}/${settings.database}`;
}

/** The port the API and the built client are served on. */
export function serverPort() {
  loadEnv();
  return Number.parseInt(process.env.DASHBOARD_PORT || "8501", 10);
}
