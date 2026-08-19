/**
 * Unit tests for the dashboard server and client contracts.
 *
 * These are the checks a clean checkout can run: they read the committed
 * artifacts and never open a database connection, so a contributor with no
 * PostgreSQL instance still gets a meaningful verification. The dual-source
 * parity contract needs a populated database and is therefore a command,
 * `script/verify_dashboard_parity.mjs`, rather than a test here.
 *
 *   cd dashboard && npm test
 *
 * Data flow:
 *     server/csv.js, server/settings.js, server/data_source.js, src/pages.js
 *         -> here
 */

import assert from "node:assert/strict";
import { mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import test from "node:test";

// Pinned before anything imports `config.js`, which caches the mode on its
// first read. A test run must never touch the operator's real database.
process.env.DATABASE = "false";
process.env.DASHBOARD_HOSTED = "";

const { parseCsv, readCsv } = await import("../server/csv.js");
const { ENV_KEYS, RingBuffer, writeEnv, applyLogging, log, logState, clearLog } =
  await import("../server/settings.js");
const {
  clearCaches,
  formatDate,
  loadSimulationResearch,
  loadSnapshot,
  TOUCHPOINT_SEGMENTS,
} = await import(
  "../server/data_source.js"
);
const { createApp } = await import("../server/index.js");
const { PAGES, PAGE_GROUPS, PAGE_KEYS, DEFAULT_PAGE } = await import("../src/pages.js");

const HERE = resolve(import.meta.dirname);
const APP_VUE = readFileSync(resolve(HERE, "..", "src", "App.vue"), "utf8");
const BUDGET_MANAGER = readFileSync(
  resolve(HERE, "..", "src", "views", "BudgetManager.vue"),
  "utf8",
);
const CAMPAIGNS = readFileSync(
  resolve(HERE, "..", "src", "views", "Campaigns.vue"),
  "utf8",
);
const OPTIMIZATION_LOG = readFileSync(
  resolve(HERE, "..", "src", "views", "OptimizationLog.vue"),
  "utf8",
);

// ---------------------------------------------------------------------------
// CSV
// ---------------------------------------------------------------------------

test("parseCsv keeps commas and newlines inside quoted fields", () => {
  const rows = parseCsv('a,b\n"x,1","line\nbreak"\n');
  assert.deepEqual(rows, [
    ["a", "b"],
    ["x,1", "line\nbreak"],
  ]);
});

test("parseCsv reads a doubled quote as one literal quote", () => {
  assert.deepEqual(parseCsv('a\n"say ""hi"""\n'), [["a"], ['say "hi"']]);
});

test("parseCsv treats CRLF as one row terminator", () => {
  assert.deepEqual(parseCsv("a,b\r\n1,2\r\n"), [
    ["a", "b"],
    ["1", "2"],
  ]);
});

test("parseCsv strips a UTF-8 byte-order mark from the first header", () => {
  // Without this, every lookup of the first column misses: the header is named
  // "﻿date" rather than "date".
  assert.deepEqual(parseCsv("﻿date,cost\n2026-01-01,5\n")[0], ["date", "cost"]);
});

test("readCsv drops the Chinese description row but keeps real rows", () => {
  const directory = mkdtempSync(join(tmpdir(), "csv-"));

  const withMarker = join(directory, "with.csv");
  writeFileSync(withMarker, "报告日期,cost\n报告日期,花费\n2026-01-01,5\n", "utf8");
  const marked = readCsv(withMarker);
  assert.equal(marked.length, 1);
  assert.equal(marked[0]["报告日期"], "2026-01-01");

  // The marker is matched exactly rather than guessed. An earlier heuristic
  // that dropped any first row without digits also discarded a real data row
  // from the files that carry no description row.
  const without = join(directory, "without.csv");
  writeFileSync(without, "touchpoint,cost\nSPONSORED_PRODUCTS:X,5\n", "utf8");
  assert.equal(readCsv(without).length, 1);
});

test("readCsv ignores the empty row a trailing newline produces", () => {
  const file = join(mkdtempSync(join(tmpdir(), "csv-")), "trail.csv");
  writeFileSync(file, "a,b\n1,2\n\n", "utf8");
  assert.equal(readCsv(file).length, 1);
});

// ---------------------------------------------------------------------------
// Settings
// ---------------------------------------------------------------------------

test("writeEnv replaces a key in place and preserves comments", () => {
  const file = join(mkdtempSync(join(tmpdir(), "env-")), ".env");
  writeFileSync(file, "# a comment\nDATABASE=false\nUNRELATED=keep\n", "utf8");

  writeEnv({ DATABASE: "true" }, file);

  const text = readFileSync(file, "utf8");
  assert.match(text, /^# a comment$/m);
  assert.match(text, /^UNRELATED=keep$/m);
  assert.match(text, /^DATABASE=true$/m);
  // Replaced, not appended: two values for one key would leave the winner
  // decided by read order.
  assert.equal(text.match(/^DATABASE=/gm).length, 1);
});

test("writeEnv appends a missing key exactly once", () => {
  const file = join(mkdtempSync(join(tmpdir(), "env-")), ".env");
  writeFileSync(file, "DATABASE=false\n", "utf8");

  writeEnv({ PG_HOST: "db.example.com" }, file);
  writeEnv({ PG_HOST: "db2.example.com" }, file);

  const text = readFileSync(file, "utf8");
  assert.equal(text.match(/^PG_HOST=/gm).length, 1);
  assert.match(text, /^PG_HOST=db2\.example\.com$/m);
});

test("writeEnv does not grow a blank line on every save", () => {
  const file = join(mkdtempSync(join(tmpdir(), "env-")), ".env");
  writeFileSync(file, "DATABASE=false\n", "utf8");
  for (let i = 0; i < 5; i += 1) writeEnv({ DATABASE: "false" }, file);
  assert.equal(readFileSync(file, "utf8"), "DATABASE=false\n");
});

test("writeEnv writes every key the settings dialog sends", () => {
  const file = join(mkdtempSync(join(tmpdir(), "env-")), ".env");
  writeFileSync(file, "", "utf8");
  const updates = Object.fromEntries(ENV_KEYS.map((key) => [key, "v"]));
  writeEnv(updates, file);
  const text = readFileSync(file, "utf8");
  for (const key of ENV_KEYS) assert.match(text, new RegExp(`^${key}=v$`, "m"));
});

test("the log buffer stays bounded", () => {
  const buffer = new RingBuffer(3);
  for (let i = 0; i < 10; i += 1) buffer.push(i);
  assert.equal(buffer.records.length, 3);
  assert.deepEqual(buffer.records, [7, 8, 9]);
});

test("logging is off by default and records nothing until enabled", () => {
  clearLog();
  log("INFO", "test", "before");
  assert.equal(logState().records.length, 0);

  applyLogging(true, "INFO");
  log("INFO", "test", "after");
  assert.equal(logState().records.length, 1);

  // A record below the active level is dropped rather than stored and filtered
  // on display, so raising the level actually reduces the work done.
  applyLogging(true, "ERROR");
  log("INFO", "test", "too quiet");
  assert.equal(logState().records.length, 1);

  applyLogging(false);
  clearLog();
});

test("a log message is truncated so one record cannot dominate the buffer", () => {
  applyLogging(true, "INFO");
  log("INFO", "test", "x".repeat(5000));
  assert.equal(logState().records.at(-1).message.length, 400);
  applyLogging(false);
  clearLog();
});

// ---------------------------------------------------------------------------
// Navigation
// ---------------------------------------------------------------------------

test("every navigable page has an icon, a title, and a component", () => {
  for (const key of PAGE_KEYS) {
    assert.ok(PAGES[key], `${key} is grouped but absent from PAGES`);
    assert.ok(PAGES[key].title, `${key} has no title`);
    assert.ok(PAGES[key].icon, `${key} has no icon`);
    // The rail cannot offer a destination the shell cannot render.
    assert.match(
      APP_VUE,
      new RegExp(`\\b${key}:\\s*\\w+`),
      `${key} is in the rail but not in App.vue's component map`,
    );
  }
});

test("the two foot controls are drawn but are not navigable pages", () => {
  for (const key of ["reload", "settings"]) {
    assert.ok(PAGES[key], `${key} has no icon entry`);
    assert.ok(!PAGE_KEYS.includes(key), `${key} must not be a navigable page`);
  }
});

test("page keys are unique and the default is one of them", () => {
  assert.equal(new Set(PAGE_KEYS).size, PAGE_KEYS.length);
  assert.ok(PAGE_KEYS.includes(DEFAULT_PAGE));
  assert.equal(PAGE_GROUPS.flatMap((group) => group.pages).length, PAGE_KEYS.length);
});

// ---------------------------------------------------------------------------
// The snapshot, in file mode
// ---------------------------------------------------------------------------

test("the file-mode snapshot carries every loader", async () => {
  const snapshot = await loadSnapshot();
  assert.equal(snapshot.mode, "local files");
  for (const key of [
    "adsDaily",
    "attributionResults",
    "comparisonTouchpoints",
    "comparisonSummary",
    "recommendedAttribution",
    "entityBridge",
    "pathReport",
  ]) {
    assert.ok(Array.isArray(snapshot[key]), `${key} is not an array`);
    assert.ok(snapshot[key].length > 0, `${key} is empty`);
  }
  for (const key of ["budgetRecommendation", "strategyRequest", "candidatePool"]) {
    assert.ok(Object.keys(snapshot[key]).length > 0, `${key} is empty`);
  }
  // The optimizer's artifact is produced by a research command rather than by
  // the import pipeline, so a checkout that has not run it must still load.
  assert.ok("campaignStrategy" in snapshot, "campaignStrategy is absent");
  assert.equal(typeof snapshot.campaignStrategy, "object");
});

test("an unrun optimizer yields an empty plan rather than a failure", async () => {
  const { campaignStrategy } = await loadSnapshot();
  // `readJson` returns `{}` for a missing file, so the key is always an object
  // and the view's `hasPlan` guard is what decides whether stage 5 ran.
  assert.notEqual(campaignStrategy, null);
  if (Object.keys(campaignStrategy).length === 0) return;

  const plan = campaignStrategy.optimized_strategy;
  assert.ok(plan, "an artifact exists but carries no optimized_strategy");
  assert.equal(typeof plan.is_optimized, "boolean");
  assert.ok(plan.recommendation_type, "the plan states no recommendation type");
  // A plan that claims optimization must never be labelled with the
  // initializer's own type: the two are different recommendations.
  if (plan.is_optimized) {
    assert.equal(plan.recommendation_type, "OPTIMIZED_CAMPAIGN_BUDGET");
    assert.notEqual(plan.recommendation_type, "INITIAL_SEED");
  }
});

test("the Optimization Log reports stage 5 from the plan, not a constant", () => {
  // The view previously hard-coded "NOT RUN", which would keep reading NOT RUN
  // after the optimizer had in fact produced a plan.
  assert.doesNotMatch(OPTIMIZATION_LOG, /count: 0,\s*status: "NOT RUN"/);
  assert.match(OPTIMIZATION_LOG, /data\.value\.campaignStrategy/);
  assert.match(OPTIMIZATION_LOG, /strategy\.value\.optimized_strategy/);

  // Every claim the plan must disclose rather than let a number stand alone.
  for (const field of ["is_extrapolated", "response_support",
    "ad_group_optimization_claim", "ad_group_projection_basis",
    "infeasibility_reasons", "excluded_campaign_ids"]) {
    assert.match(OPTIMIZATION_LOG, new RegExp(field));
  }
  assert.match(OPTIMIZATION_LOG, /Attribution is not an input here/);
  assert.match(OPTIMIZATION_LOG, /POOLED_TRANSFER/);
});

test("reliability flags are real booleans, not the string 'false'", async () => {
  const { comparisonTouchpoints } = await loadSnapshot();
  const flags = ["calculation_valid", "data_support_sufficient", "models_consistent"];
  for (const row of comparisonTouchpoints) {
    for (const flag of flags) {
      // Every non-empty string is truthy in JavaScript, so the string "false"
      // read from a CSV would keep unreliable rows a view meant to drop.
      assert.equal(typeof row[flag], "boolean", `${flag} is ${typeof row[flag]}`);
    }
  }
});

test("formatDate pins a Date object to YYYY-MM-DD", () => {
  // This is the database's shape. `String(date).slice(0, 10)` yields
  // "Tue Mar 31" -- a weekday and a month name -- which is why every date goes
  // through this function rather than being sliced at the call site. File mode
  // alone cannot catch the regression, because a CSV never produces a Date.
  assert.equal(formatDate(new Date(2026, 2, 31)), "2026-03-31");
  assert.equal(formatDate(new Date(2026, 0, 1)), "2026-01-01");
});

test("formatDate reads a local date rather than converting to UTC", () => {
  // `toISOString()` converts to UTC first and so reports the previous day for
  // any host east of Greenwich; midnight local is the case that exposes it.
  assert.equal(formatDate(new Date(2026, 0, 1, 0, 0, 0)), "2026-01-01");
});

test("formatDate returns null for a value carrying no date", () => {
  for (const empty of [null, undefined, ""]) assert.equal(formatDate(empty), null);
});

test("formatDate passes an already-formatted string through", () => {
  assert.equal(formatDate("2026-03-31"), "2026-03-31");
  assert.equal(formatDate("2026-03-31T00:00:00Z"), "2026-03-31");
});

test("dates are pinned to YYYY-MM-DD, never a Date's own string form", async () => {
  const snapshot = await loadSnapshot();
  for (const row of snapshot.comparisonSummary) {
    for (const field of ["report_start_date", "report_end_date"]) {
      assert.match(
        row[field],
        /^\d{4}-\d{2}-\d{2}$/,
        `${field} is "${row[field]}"`,
      );
    }
  }
  // The same rule applies to the dates rebuilt from the strategy documents,
  // which are formatted separately.
  assert.match(
    snapshot.budgetRecommendation.mta_source_snapshot.report_start_date,
    /^\d{4}-\d{2}-\d{2}$/,
  );
});

test("an absent text value is null in file mode, never an empty string", async () => {
  const { entityBridge } = await loadSnapshot();
  for (const row of entityBridge) {
    for (const [field, value] of Object.entries(row)) {
      assert.notEqual(value, "", `${field} is an empty string rather than null`);
    }
  }
});

test("numeric columns are numbers or null, never strings", async () => {
  const { adsDaily } = await loadSnapshot();
  for (const row of adsDaily.slice(0, 50)) {
    for (const field of ["cost", "impressions", "clicks"]) {
      if (row[field] === null) continue;
      assert.equal(typeof row[field], "number", `${field} is ${typeof row[field]}`);
      // NaN is not representable in JSON and would reach the browser as null,
      // so the two modes would disagree before serialisation and agree after.
      assert.ok(Number.isFinite(row[field]), `${field} is not finite`);
    }
  }
});

test("every touchpoint row carries the five key segments", async () => {
  const { attributionResults } = await loadSnapshot();
  for (const row of attributionResults) {
    assert.equal(String(row.touchpoint).split(":").length, TOUCHPOINT_SEGMENTS.length);
    for (const segment of TOUCHPOINT_SEGMENTS) {
      assert.ok(row[segment], `${segment} is missing from a touchpoint row`);
    }
  }
});

test("the snapshot survives JSON serialisation unchanged", async () => {
  // The API sends it as JSON, so anything that does not round-trip -- a Date,
  // a NaN, an undefined -- is a difference between what the loader returned
  // and what a view receives.
  const snapshot = await loadSnapshot();
  assert.deepEqual(JSON.parse(JSON.stringify(snapshot)), snapshot);
});

test("a simulator sidecar becomes canonical file-mode research data", async () => {
  const directory = mkdtempSync(join(tmpdir(), "mta-sim-dashboard-"));
  writeFileSync(
    join(directory, "effective_configuration.json"),
    JSON.stringify({
      seed: 7,
      touchpoints: [{
        identifier: "search",
        ad_product: "SPONSORED_PRODUCTS",
        ad_type: "PRODUCT_AD",
        creative_type: null,
        placement: "TOP_OF_SEARCH",
        cost_per_click: 1.2,
        cost_per_thousand_impressions: null,
        base_impressions: 100,
        click_through_rate: 0.1,
        platform_conversion_rate: 0.2,
        conversion_log_odds_effect: 0.4,
      }],
    }),
  );
  const scope = {
    marketplace: "US",
    advertiser_id: "adv",
    currency: "USD",
    report_start_date: "2026-01-01",
    report_end_date: "2026-01-01",
  };
  writeFileSync(
    join(directory, "simulation_research.json"),
    JSON.stringify({
      simulation_runs: [{
        run_id: "sim-test",
        seed: 7,
        configuration_sha256: "a".repeat(64),
        providers: [{ provider: "AMAZON_ADS", supported_ad_products: ["SPONSORED_PRODUCTS"] }],
        products: [{ product_id: "p1" }],
        campaigns: [{ campaign_id: "c1", provider: "AMAZON_ADS", ad_product: "SPONSORED_PRODUCTS" }],
        ad_groups: [{ ad_group_id: "g1", campaign_id: "c1" }],
        campaign_product_links: [{ campaign_id: "c1", product_id: "p1" }],
        product_economics: [{ product_id: "p1", currency: "USD", unit_cogs: null }],
        effective_configuration: { seed: 7 },
      }],
      budget_observations: [{ campaign_id: "c1", reporting_scope: scope,
        configured_budget: 100, actual_spend: 80, budget_level: 1 }],
      evaluation_outcome_observations: [{ campaign_id: "c1", product_id: "p1",
        reporting_scope: scope, total_units: 4, total_revenue: 40,
        contribution_profit: null, budget_level: 1 }],
      delivery_observations: [],
      touchpoint_observations: [],
    }),
  );
  process.env.MTA_SIM_DATA_DIR = directory;
  clearCaches();
  const research = await loadSimulationResearch();
  assert.equal(research.history.length, 1);
  assert.equal(research.history[0].actual_spend, 80);
  assert.equal(research.history[0].total_revenue, 40);
  assert.equal(research.touchpoints[0].compatibility_keys.length, 2);
  assert.equal(research.productEconomics[0].unit_cogs, null);
  delete process.env.MTA_SIM_DATA_DIR;
  clearCaches();
});

test("the dashboard server starts and protects generated observations", async () => {
  const server = createApp().listen(0);
  await new Promise((resolvePromise) => server.once("listening", resolvePromise));
  const { port } = server.address();
  try {
    const dashboard = await fetch(`http://127.0.0.1:${port}/api/dashboard`);
    assert.equal(dashboard.status, 200);
    const master = await fetch(
      `http://127.0.0.1:${port}/api/master/product/p1`,
      { method: "PUT", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ payload: { product_id: "p1" } }) },
    );
    assert.equal(master.status, 403);
    const historyMutation = await fetch(
      `http://127.0.0.1:${port}/api/history/delivery/1`,
      { method: "DELETE" },
    );
    assert.equal(historyMutation.status, 404);
  } finally {
    await new Promise((resolvePromise) => server.close(resolvePromise));
  }
});

test("Budget Manager exposes progressive canonical entity sections", () => {
  for (const label of ["Overview", "Ad Providers", "Products", "Campaigns",
    "Ad Groups", "Touchpoints", "Product Economics", "Generation Configs"]) {
    assert.match(BUDGET_MANAGER, new RegExp(label));
  }
  for (const field of ["placement_availability", "creative_availability",
    "interaction_type_availability", "billing_type", "click_through_rate"]) {
    assert.match(BUDGET_MANAGER, new RegExp(field));
  }
  for (const field of ["sku_id", "variable_fulfillment_cost_per_unit",
    "variable_platform_fee_per_unit", "other_variable_cost_per_unit"]) {
    assert.match(BUDGET_MANAGER, new RegExp(field));
  }
  for (const behavior of ["Upload and validate JSON", "Download snapshot",
    "Edit as future-run draft", "Archive draft", "Validate and save"]) {
    assert.match(BUDGET_MANAGER, new RegExp(behavior));
  }
  assert.match(BUDGET_MANAGER, /missing COGS is not treated as zero/);
  assert.match(BUDGET_MANAGER, /Generated observations are read-only/);
});

test("Campaigns exposes generated filters and presentation-only similarity", () => {
  for (const label of ["Provider", "Product", "Campaign", "Ad product",
    "Marketplace", "Simulation run", "Configured budget vs actual spend",
    "Interaction-aware delivery"]) {
    assert.match(CAMPAIGNS, new RegExp(label, "i"));
  }
  assert.match(
    CAMPAIGNS,
    /Historical reference only\. Not used by attribution or strategy optimization\./,
  );
  for (const field of ["subject_type", "subject_id", "comparable_id",
    "similarity_score", "rationale", "generated_by"]) {
    assert.match(CAMPAIGNS, new RegExp(field));
  }
  assert.match(CAMPAIGNS, /row\.similarity_score >= similarityThreshold\.value/);
  assert.match(CAMPAIGNS, /type="range" min="0" max="1" step="0\.05"/);
  assert.match(CAMPAIGNS, /row\.subject_id !== row\.comparable_id/);
  assert.match(CAMPAIGNS, /Attribution not available\./);
});
