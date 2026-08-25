/**
 * Preserve the former Node settings module as a parity fixture.
 *
 * Runtime requests use `backend/services/settings.py`. The JavaScript
 * regression suite retains this implementation to compare environment-file,
 * credential-redaction, and bounded-log behavior during migration.
 *
 * Credentials are written to `.env` at the repository root, which is
 * git-ignored. Nothing here writes a credential to a tracked file, to the API
 * response, or to the log: `config.safeSummary()` is the only rendering of a
 * connection, and it omits the password by construction.
 *
 * Parity-test flow:
 *     dashboard/tests -> server/index.js -> here -> temporary .env
 */

import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";

import {
  REPO_ROOT,
  configReadOnly,
  databaseSettings,
  isHosted,
  safeSummary,
  useDatabase,
} from "./config.js";
import { clearCaches, databaseAvailable, disposePool } from "./data_source.js";

/**
 * Written to `.env`. Order is preserved when the file is rewritten, so a
 * hand-edited file keeps its shape.
 */
export const ENV_KEYS = [
  "DATABASE",
  "PG_HOST",
  "PG_PORT",
  "PG_DATABASE",
  "PG_USER",
  "PG_PASSWORD",
  "PG_SSLMODE",
];

export const ENV_PATH = resolve(REPO_ROOT, ".env");

/**
 * How many log records the in-memory stream keeps. Bounded so a long session
 * cannot grow without limit.
 */
export const LOG_CAPACITY = 400;

/**
 * A bounded ring buffer of recent records.
 *
 * A file would be the wrong choice here: the reader wants to watch what the
 * dashboard is doing right now, and a capped buffer cannot fill a disk on a
 * demonstration machine.
 */
export class RingBuffer {
  constructor(capacity = LOG_CAPACITY) {
    this.capacity = capacity;
    this.records = [];
  }

  push(record) {
    this.records.push(record);
    if (this.records.length > this.capacity) {
      this.records.splice(0, this.records.length - this.capacity);
    }
  }

  clear() {
    this.records = [];
  }
}

const buffer = new RingBuffer();

let loggingOn = false;
let loggingLevel = "INFO";

const LEVEL_ORDER = { DEBUG: 10, INFO: 20, WARNING: 30, ERROR: 40 };

/** Record one line of dashboard activity, if logging is on. */
export function log(level, source, message) {
  if (!loggingOn) return;
  if ((LEVEL_ORDER[level] ?? 20) < (LEVEL_ORDER[loggingLevel] ?? 20)) return;
  buffer.push({
    when: new Date().toISOString().slice(11, 19),
    level,
    source,
    // A long SQL statement or a long error is truncated rather than stored
    // whole, so one record cannot dominate the buffer.
    message: String(message).slice(0, 400),
  });
}

export function loggingEnabled() {
  return loggingOn;
}

export function applyLogging(enabled, level = "INFO") {
  loggingOn = Boolean(enabled);
  loggingLevel = LEVEL_ORDER[level] ? level : "INFO";
}

export function logState() {
  return {
    enabled: loggingOn,
    level: loggingLevel,
    capacity: LOG_CAPACITY,
    records: buffer.records.slice(-120),
  };
}

export function clearLog() {
  buffer.clear();
}

/** Read the current `.env` values, falling back to the live environment. */
export function readEnv() {
  const values = {};
  if (existsSync(ENV_PATH)) {
    for (const raw of readFileSync(ENV_PATH, "utf8").split(/\r?\n/)) {
      const line = raw.trim();
      if (!line || line.startsWith("#") || !line.includes("=")) continue;
      const index = line.indexOf("=");
      values[line.slice(0, index).trim()] = line.slice(index + 1).trim();
    }
  }
  for (const key of ENV_KEYS) {
    if (values[key] === undefined) values[key] = process.env[key] ?? "";
  }
  return values;
}

/**
 * Merge `updates` into `.env`, preserving comments and unrelated keys.
 *
 * The file is rewritten rather than appended to, so a key set twice cannot end
 * up with the stale value winning depending on read order.
 */
export function writeEnv(updates, path = ENV_PATH) {
  const lines = [];
  const seen = new Set();

  if (existsSync(path)) {
    for (const raw of readFileSync(path, "utf8").split(/\r?\n/)) {
      const line = raw.trim();
      if (!line || line.startsWith("#") || !line.includes("=")) {
        lines.push(raw);
        continue;
      }
      const key = line.slice(0, line.indexOf("=")).trim();
      if (key in updates) {
        lines.push(`${key}=${updates[key]}`);
        seen.add(key);
      } else {
        lines.push(raw);
      }
    }
  }

  // A file ending in a newline splits to a trailing empty string; dropping it
  // stops the file growing a blank line on every save.
  while (lines.length > 0 && lines[lines.length - 1].trim() === "") lines.pop();

  const missing = ENV_KEYS.filter((key) => key in updates && !seen.has(key));
  if (missing.length > 0) {
    if (lines.length > 0) lines.push("");
    lines.push("# Written by the dashboard settings module.");
    for (const key of missing) lines.push(`${key}=${updates[key]}`);
  }

  writeFileSync(path, `${lines.join("\n")}\n`, "utf8");

  // The values are exported into this process too, so the change takes effect
  // without a restart, and every cached read is dropped because it may have
  // come from the other source.
  for (const [key, value] of Object.entries(updates)) process.env[key] = value;
  clearCaches();
  return disposePool();
}

/** Return the `{ label, colour, detail }` triple the rail displays. */
export async function status() {
  // The dot colours match the deployment accents in `src/lib/deployment.js`:
  // green wherever the dashboard is reading committed files and cannot write,
  // and the brand tint only where a database is actually connected. The rail
  // and the theme therefore cannot disagree about which deployment this is.
  if (isHosted()) {
    return {
      label: "Sample data",
      colour: "#7ed6a4",
      detail: "Published build, reading the repository's committed samples.",
    };
  }
  if (useDatabase()) {
    const { usable, message } = await databaseAvailable();
    return {
      label: "Database",
      colour: usable ? "#7ee0b0" : "#ffb4ad",
      detail: usable ? message : `Unavailable — ${message}`,
    };
  }
  return {
    label: "Local files",
    colour: "#7ed6a4",
    detail: "Reading committed CSV and JSON artifacts. Read-only.",
  };
}

/**
 * Open a throwaway connection with the entered values.
 *
 * Tests what was typed rather than what is saved, so a reader can validate a
 * correction before committing it to `.env`.
 */
export async function testConnection(updates) {
  const missing = ["PG_HOST", "PG_DATABASE", "PG_USER", "PG_PASSWORD"].filter(
    (key) => !updates[key],
  );
  if (missing.length > 0) {
    return { ok: false, message: `Missing ${missing.join(", ")}.` };
  }

  const settings = {
    host: updates.PG_HOST,
    port: Number.parseInt(updates.PG_PORT || "5432", 10),
    database: updates.PG_DATABASE,
    user: updates.PG_USER,
    password: updates.PG_PASSWORD,
    sslmode: updates.PG_SSLMODE || "prefer",
  };

  let client;
  try {
    const { default: pg } = await import("pg");
    client = new pg.Client({
      ...settings,
      ssl: ["require", "verify-ca", "verify-full"].includes(settings.sslmode)
        ? { rejectUnauthorized: settings.sslmode !== "require" }
        : false,
      connectionTimeoutMillis: 10_000,
    });
    await client.connect();
    const version = await client.query("select version()");
    const tables = await client.query(
      "select count(*)::int as count from information_schema.tables " +
        "where table_schema = 'public'",
    );
    return {
      ok: true,
      message:
        `Connected to ${safeSummary(settings)} — ` +
        `${tables.rows[0].count} table(s). ` +
        `${String(version.rows[0].version).split(",")[0]}`,
    };
  } catch (error) {
    return { ok: false, message: `${error.name}: ${String(error.message).slice(0, 300)}` };
  } finally {
    // The client is closed whether or not the probe succeeded, so a failed
    // test cannot leave a socket open on the shared instance.
    await client?.end().catch(() => {});
  }
}

/**
 * The state the settings dialog renders, with no credential in it beyond the
 * host, port, database, and user the reader typed themselves.
 */
export async function settingsState() {
  const values = readEnv();
  const state = {
    hosted: isHosted(),
    readOnly: configReadOnly(),
    useDatabase: useDatabase(),
    connection: {
      PG_HOST: values.PG_HOST ?? "",
      PG_PORT: values.PG_PORT || "5432",
      PG_DATABASE: values.PG_DATABASE ?? "",
      PG_USER: values.PG_USER ?? "",
      PG_SSLMODE: values.PG_SSLMODE || "prefer",
      // The password is never sent back to the page. The flag says whether one
      // is stored, which is all the dialog needs to explain a blank field.
      passwordStored: Boolean(values.PG_PASSWORD),
    },
    status: await status(),
    logging: logState(),
  };
  return state;
}
