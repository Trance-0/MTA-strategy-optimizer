/**
 * Dual-mode data access for the dashboard.
 *
 * Every view reads the snapshot these loaders produce and never touches a file
 * path or a SQL statement itself. Each loader returns the same fields, types,
 * and values in both modes, so a view cannot tell whether `DATABASE` was true
 * or false. Four differences make that non-trivial, and each is normalised
 * here rather than in a view:
 *
 * * PostgreSQL folds unquoted identifiers to lowercase, so the platform's
 *   camelCase field names survive only in file mode. Both modes are renamed to
 *   snake_case.
 * * The pipeline writes reliability flags as the strings `true` and `false`,
 *   and every non-empty string is truthy in JavaScript. They are parsed to real
 *   booleans.
 * * A date read from a file is a string and from the database a `Date`. Both
 *   are pinned to a `YYYY-MM-DD` string, which is also what survives the JSON
 *   the browser receives.
 * * Every numeric column arrives as text from a CSV and as a number from the
 *   database; `pg` additionally returns `numeric` as a string to protect
 *   precision. All of them are coerced to numbers.
 *
 * `scripts/verify_source_parity.mjs` asserts these invariants against a live
 * database.
 *
 * Data flow:
 *     DATABASE=false -> modules/&#42;/data/simulated/&#42;.csv, modules/&#42;/outputs/&#42;&#42;
 *     DATABASE=true  -> the PostgreSQL tables script/import_to_database.py writes
 *
 * Results are cached in memory, so switching views does not re-read the source.
 * Use the Reload button in the rail to clear it.
 */

import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";

import {
  ATTRIBUTION_OUTPUT_DIR,
  SIMULATED_DIR,
  STRATEGY_INPUT_DIR,
  STRATEGY_OUTPUT_DIR,
  databaseSettings,
  safeSummary,
  simulatorDataDirectory,
  useDatabase,
} from "./config.js";
import { readCsv } from "./csv.js";

const CACHE_TTL_MS = 600_000;

const cache = new Map();

/** Run `producer` at most once per TTL, keyed by loader name. */
async function cached(key, producer) {
  const hit = cache.get(key);
  if (hit && Date.now() - hit.at < CACHE_TTL_MS) return hit.value;
  const value = await producer();
  cache.set(key, { at: Date.now(), value });
  return value;
}

/** Drop every cached result so the next read hits the source again. */
export function clearCaches() {
  cache.clear();
}

// ---------------------------------------------------------------------------
// Coercion helpers
// ---------------------------------------------------------------------------

/**
 * Coerce the named fields to numbers, leaving blanks as null.
 *
 * Null rather than NaN: NaN is not representable in JSON and would reach the
 * browser as `null` anyway, so producing it here would mean the two modes
 * disagreed before serialisation and agreed after.
 */
function toNumeric(rows, columns) {
  for (const row of rows) {
    for (const column of columns) {
      if (!(column in row)) continue;
      const raw = row[column];
      if (raw === null || raw === undefined || String(raw).trim() === "") {
        row[column] = null;
        continue;
      }
      const value = Number(raw);
      row[column] = Number.isFinite(value) ? value : null;
    }
  }
  return rows;
}

/** Reliability flags, written by the pipeline as the strings `true`/`false`. */
const BOOLEAN_COLUMNS = [
  "calculation_valid",
  "data_support_sufficient",
  "models_consistent",
];

/**
 * Coerce the reliability flag columns to real booleans.
 *
 * A CSV read yields the strings `true` and `false`, and every non-empty string
 * is truthy in JavaScript. Without this, a view filtering on the flag would
 * keep unreliable rows in file mode and drop them in database mode.
 */
function toBoolean(rows) {
  for (const row of rows) {
    for (const column of BOOLEAN_COLUMNS) {
      if (!(column in row)) continue;
      const raw = row[column];
      row[column] =
        typeof raw === "boolean"
          ? raw
          : String(raw).trim().toLowerCase() === "true";
    }
  }
  return rows;
}

/**
 * Date columns that appear across several artifacts. A CSV read yields strings
 * and the database yields `Date` objects, so both are pinned to `YYYY-MM-DD`
 * here and a view can always compare or format them the same way.
 */
const DATE_COLUMNS = ["report_start_date", "report_end_date"];

/**
 * Pin one date value to `YYYY-MM-DD`, or null when it carries no date.
 *
 * A `Date` is formatted from its local components rather than through
 * `toISOString()`, which converts to UTC first and so reports the previous day
 * for any host east of Greenwich. Slicing `String(date)` is not an alternative:
 * a `Date` stringifies to `Tue Mar 31 2026 ...`, so the first ten characters
 * are a weekday and a month name rather than the date. Every date the API
 * returns goes through this one function for that reason.
 */
export function formatDate(raw) {
  if (raw === null || raw === undefined || raw === "") return null;
  if (raw instanceof Date) {
    const month = String(raw.getMonth() + 1).padStart(2, "0");
    const day = String(raw.getDate()).padStart(2, "0");
    return `${raw.getFullYear()}-${month}-${day}`;
  }
  return String(raw).slice(0, 10);
}

/** Pin the named date fields of every row to `YYYY-MM-DD`. */
function toDateString(rows, columns = DATE_COLUMNS) {
  for (const row of rows) {
    for (const column of columns) {
      if (!(column in row)) continue;
      row[column] = formatDate(row[column]);
    }
  }
  return rows;
}

/**
 * The five segments of a touchpoint key, in order. These names are the
 * canonical vocabulary: the database stores them as columns on `touchpoint`,
 * and file mode derives them by splitting the key, so both modes agree.
 */
export const TOUCHPOINT_SEGMENTS = [
  "ad_product",
  "format",
  "placement",
  "creative",
  "interaction_type",
];

/**
 * Add the five key segments as their own fields.
 *
 * The fifth segment is the interaction type. Files that already carry an
 * `interaction_type` field agree with it, so overwriting is harmless and keeps
 * the field present for the files that omit it.
 */
function splitTouchpoint(rows) {
  for (const row of rows) {
    if (!("touchpoint" in row)) continue;
    const segments = String(row.touchpoint).split(":");
    TOUCHPOINT_SEGMENTS.forEach((name, index) => {
      if (index < segments.length) row[name] = segments[index];
    });
  }
  return rows;
}

/**
 * Keep only the named fields, in the order given, so both modes agree.
 *
 * An absent text value is pinned to null in both modes. A CSV represents it as
 * an empty string and PostgreSQL as NULL, and the two are not interchangeable
 * to a view: `row.keyword_id ?? "none"` yields `"none"` in one mode and `""`
 * in the other, and `JSON.stringify` preserves the difference, so a parity
 * check comparing serialised rows fails on fields no view even reads.
 * Numeric fields are already pinned to null by `toNumeric`.
 */
function project(rows, fields) {
  return rows.map((row) => {
    const record = {};
    for (const field of fields) {
      const value = row[field];
      record[field] =
        value === undefined || value === null || value === "" ? null : value;
    }
    return record;
  });
}

function readJson(path) {
  if (!existsSync(path)) return {};
  return JSON.parse(readFileSync(path, "utf8"));
}

// ---------------------------------------------------------------------------
// Database access
// ---------------------------------------------------------------------------

let pool = null;

/**
 * Return the shared connection pool, created on first use.
 *
 * `pg` is imported lazily so a file-mode run never loads the driver, which is
 * what keeps `DATABASE=false` working in a checkout that installed nothing
 * beyond the client dependencies.
 */
async function getPool() {
  if (pool) return pool;
  const settings = databaseSettings();
  const { default: pg } = await import("pg");
  pool = new pg.Pool({
    host: settings.host,
    port: settings.port,
    database: settings.database,
    user: settings.user,
    password: settings.password,
    // `sslmode` is libpq's spelling; `pg` takes a boolean or a TLS options
    // object. Anything at or above `require` needs TLS, and the managed
    // instances this connects to present a certificate chain the client does
    // not carry, so verification is left to the stricter modes.
    ssl: ["require", "verify-ca", "verify-full"].includes(settings.sslmode)
      ? { rejectUnauthorized: settings.sslmode !== "require" }
      : false,
    connectionTimeoutMillis: 20_000,
    max: 4,
  });
  return pool;
}

/** Run a read-only query and return its rows. */
async function query(sql, values = []) {
  const client = await getPool();
  const result = await client.query(sql, values);
  return result.rows;
}

/** Close the pool, so a settings change can rebuild it with new credentials. */
export async function disposePool() {
  if (!pool) return;
  const closing = pool;
  pool = null;
  await closing.end().catch(() => {});
}

// ---------------------------------------------------------------------------
// Mode reporting
// ---------------------------------------------------------------------------

/** Return `database` or `local files`, for display in the rail. */
export function activeMode() {
  return useDatabase() ? "database" : "local files";
}

/** Return a human-readable description of where data is being read from. */
export function sourceLabel() {
  if (!useDatabase()) {
    const simulatorDirectory = simulatorDataDirectory();
    return simulatorDirectory ?? "modules/*/data and outputs";
  }
  try {
    return safeSummary();
  } catch (error) {
    return `Not configured — ${error.message}`;
  }
}

/**
 * Check that the configured database is reachable and populated.
 *
 * Returns `{ usable, message }` rather than throwing, so the shell can report
 * a connection failure as a page rather than as a stack trace inside whichever
 * chart read it first.
 */
export async function databaseAvailable() {
  if (!useDatabase()) return { usable: false, message: "DATABASE=false" };
  try {
    const rows = await query("select count(*)::int as count from attribution_result");
    const count = rows[0]?.count ?? 0;
    if (!count) {
      return { usable: false, message: "Connected, but attribution_result is empty." };
    }
    return { usable: true, message: `Connected to ${safeSummary()}` };
  } catch (error) {
    return {
      usable: false,
      message: `${error.name}: ${String(error.message).slice(0, 180)}`,
    };
  }
}

// ---------------------------------------------------------------------------
// Model output
// ---------------------------------------------------------------------------

const ATTRIBUTION_FIELDS = [
  "attribution_model",
  "touchpoint",
  "ad_product",
  "format",
  "placement",
  "creative",
  "interaction_type",
  "converted_user_share",
  "purchase_count_share",
  "revenue_share",
  "attributed_converted_users",
  "attributed_purchase_count",
  "attributed_revenue",
  "impressions",
  "clicks",
  "cost",
  "reported_purchases",
  "reported_sales",
  "roas",
  "roi",
  "cpa",
  "cost_per_converted_user",
];

const ATTRIBUTION_NUMERIC = ATTRIBUTION_FIELDS.slice(7);

/**
 * Per-model attributed outcomes, cost, and efficiency for each touchpoint.
 */
export function loadAttributionResults() {
  return cached("attribution_results", async () => {
    let rows;
    if (useDatabase()) {
      rows = await query(`
        select r.attribution_model, t.touchpoint_key as touchpoint,
               t.interaction_type, t.ad_product, t.format, t.placement,
               t.creative,
               r.converted_user_share, r.purchase_count_share,
               r.revenue_share, r.attributed_converted_users,
               r.attributed_purchase_count, r.attributed_revenue,
               r.impressions, r.clicks, r.cost, r.reported_purchases,
               r.reported_sales, r.roas, r.roi, r.cpa,
               r.cost_per_converted_user
        from attribution_result r
        join touchpoint t on t.id = r.touchpoint_pk
        order by r.attribution_model, t.touchpoint_key
      `);
    } else {
      rows = [];
      for (const model of ["markov", "shapley"]) {
        rows.push(
          ...readCsv(
            resolve(ATTRIBUTION_OUTPUT_DIR, `amc_${model}_attribution_results.csv`),
          ),
        );
      }
      splitTouchpoint(rows);
    }
    return project(toNumeric(rows, ATTRIBUTION_NUMERIC), ATTRIBUTION_FIELDS);
  });
}

const COMPARISON_FIELDS = [
  "touchpoint",
  "outcome",
  "ad_product",
  "format",
  "placement",
  "creative",
  "interaction_type",
  "markov_share",
  "shapley_share",
  "gap_pp",
  "relative_gap",
  "raw_unique_paths",
  "raw_converted_users",
  "raw_purchase_count",
  "calculation_valid",
  "data_support_sufficient",
  "models_consistent",
  "reliability_status",
  "reliability_reason",
];

/** Markov against Shapley per touchpoint and outcome, with reliability. */
export function loadComparisonTouchpoints() {
  return cached("comparison_touchpoints", async () => {
    let rows;
    if (useDatabase()) {
      rows = await query(`
        select t.touchpoint_key as touchpoint, c.outcome, c.markov_share,
               c.shapley_share, c.gap_pp, c.relative_gap,
               c.raw_unique_paths, c.raw_converted_users,
               c.raw_purchase_count, c.calculation_valid,
               c.data_support_sufficient, c.models_consistent,
               c.reliability_status, c.reliability_reason,
               t.ad_product, t.format, t.placement, t.creative,
               t.interaction_type
        from model_comparison_touchpoint c
        join touchpoint t on t.id = c.touchpoint_pk
        order by c.outcome, t.touchpoint_key
      `);
    } else {
      rows = readCsv(
        resolve(ATTRIBUTION_OUTPUT_DIR, "amc_mta_model_comparison_touchpoints.csv"),
      );
      splitTouchpoint(rows);
    }
    toNumeric(rows, [
      "markov_share",
      "shapley_share",
      "gap_pp",
      "relative_gap",
      "raw_unique_paths",
      "raw_converted_users",
      "raw_purchase_count",
    ]);
    return project(toBoolean(rows), COMPARISON_FIELDS);
  });
}

const SUMMARY_FIELDS = [
  "outcome",
  "report_start_date",
  "report_end_date",
  "max_touchpoint_gap_days",
  "touchpoint_count",
  "tvd",
  "spearman_rho",
  "top_k_overlap_rate",
  "calculation_valid",
  "data_support_sufficient",
  "models_consistent",
  "reliability_status",
  "reliability_reason",
];

/** One diagnostic row per outcome: TVD, Spearman, and Top-K overlap. */
export function loadComparisonSummary() {
  return cached("comparison_summary", async () => {
    let rows;
    if (useDatabase()) {
      rows = await query(`
        select s.outcome, r.report_start_date, r.report_end_date,
               r.max_touchpoint_gap_days, s.touchpoint_count, s.tvd,
               s.spearman_rho, s.top_k_overlap_rate, s.calculation_valid,
               s.data_support_sufficient, s.models_consistent,
               s.reliability_status, s.reliability_reason
        from model_comparison_summary s
        join attribution_run r on r.id = s.run_pk
        order by s.outcome
      `);
    } else {
      rows = readCsv(
        resolve(ATTRIBUTION_OUTPUT_DIR, "amc_mta_model_comparison_summary.csv"),
      );
    }
    toNumeric(rows, [
      "touchpoint_count",
      "tvd",
      "spearman_rho",
      "top_k_overlap_rate",
      "max_touchpoint_gap_days",
    ]);
    return project(toBoolean(toDateString(rows)), SUMMARY_FIELDS);
  });
}

const RECOMMENDED_FIELDS = [
  "touchpoint",
  "outcome",
  "ad_product",
  "format",
  "placement",
  "creative",
  "interaction_type",
  "official_model",
  "official_share",
  "recommended_value",
  "benchmark_model",
  "benchmark_share",
  "gap_pp",
  "relative_gap",
  "calculation_valid",
  "data_support_sufficient",
  "models_consistent",
  "reliability_status",
  "reliability_reason",
];

/** The governed view: official share, benchmark, and recommended value. */
export function loadRecommendedAttribution() {
  return cached("recommended_attribution", async () => {
    let rows;
    if (useDatabase()) {
      rows = await query(`
        select t.touchpoint_key as touchpoint, r.outcome, t.interaction_type,
               r.official_model, r.official_share, r.recommended_value,
               r.benchmark_model, r.benchmark_share, r.gap_pp,
               r.relative_gap, r.calculation_valid,
               r.data_support_sufficient, r.models_consistent,
               r.reliability_status, r.reliability_reason,
               t.ad_product, t.format, t.placement, t.creative
        from recommended_attribution r
        join touchpoint t on t.id = r.touchpoint_pk
        order by r.outcome, t.touchpoint_key
      `);
    } else {
      rows = readCsv(
        resolve(ATTRIBUTION_OUTPUT_DIR, "amc_mta_recommended_attribution.csv"),
      );
      splitTouchpoint(rows);
    }
    toNumeric(rows, ["official_share", "benchmark_share", "gap_pp", "relative_gap"]);
    return project(toBoolean(rows), RECOMMENDED_FIELDS);
  });
}

// ---------------------------------------------------------------------------
// History
// ---------------------------------------------------------------------------

/**
 * The Amazon Ads sample uses the platform's camelCase field names. The
 * dashboard speaks snake_case everywhere, and PostgreSQL folds unquoted
 * identifiers to lowercase anyway, so file mode is renamed to match rather
 * than the database being forced to quote every alias.
 */
const ADS_COLUMN_RENAMES = {
  reportDate: "report_date",
  accountId: "account_id",
  adProduct: "ad_product",
  adType: "ad_type",
  creativeType: "creative_type",
  inventoryType: "inventory_type",
  currencyCode: "currency",
  normalizedTouchpoint: "touchpoint",
};

const ADS_FIELDS = [
  "report_date",
  "marketplace",
  "account_id",
  "touchpoint",
  "ad_product",
  "format",
  "placement",
  "creative",
  "interaction_type",
  "cost_type",
  "currency",
  "impressions",
  "clicks",
  "cost",
  "purchases",
  "sales",
];

/**
 * Daily platform performance per touchpoint, with a pinned report_date.
 *
 * The `format` and `creative` fields are the touchpoint key's second and
 * fourth segments. In the source file those arrive split across
 * `adType`/`inventoryType` and `creativeType`; the segments carry the same
 * values, so both modes expose the segment names.
 */
export function loadAdsDaily() {
  return cached("ads_daily", async () => {
    let rows;
    if (useDatabase()) {
      rows = await query(`
        select a.report_date, a.marketplace, a.account_id,
               t.touchpoint_key as touchpoint, t.ad_product,
               t.format, t.placement, t.creative, t.interaction_type,
               t.cost_type, a.currency, a.impressions,
               a.clicks, a.cost, a.purchases, a.sales
        from ads_daily_performance a
        join touchpoint t on t.id = a.touchpoint_pk
        order by a.report_date
      `);
    } else {
      const simulatorDirectory = simulatorDataDirectory();
      const sourcePath = simulatorDirectory
        ? resolve(
            simulatorDirectory,
            "amazon_ads_daily_touchpoint_performance.csv",
          )
        : resolve(SIMULATED_DIR, "amazon_ads_report_sample.csv");
      rows = readCsv(sourcePath).map(
        (row) => {
          const record = {};
          for (const [key, value] of Object.entries(row)) {
            record[ADS_COLUMN_RENAMES[key] ?? key] = value;
          }
          return record;
        },
      );
      splitTouchpoint(rows);
    }
    toNumeric(rows, ["impressions", "clicks", "cost", "purchases", "sales"]);
    toDateString(rows, ["report_date"]);
    return project(
      rows.filter((row) => row.report_date),
      ADS_FIELDS,
    );
  });
}

const PATH_FIELDS = [
  "report_start_date",
  "report_end_date",
  "marketplace",
  "advertiser_id",
  "path",
  "path_length",
  "users",
  "converted_users",
  "purchase_count",
  "revenue",
];

/** Anonymous aggregated conversion paths with their outcome totals. */
export function loadPathReport() {
  return cached("path_report", async () => {
    let rows;
    if (useDatabase()) {
      rows = await query(`
        select report_start_date, report_end_date, marketplace,
               advertiser_id, path, path_length, users, converted_users,
               purchase_count, revenue
        from path_report
        order by id
      `);
    } else {
      const simulatorDirectory = simulatorDataDirectory();
      rows = readCsv(
        simulatorDirectory
          ? resolve(simulatorDirectory, "amc_path_report.csv")
          : resolve(SIMULATED_DIR, "amc_mta_path_report_raw_sample.csv"),
      );
      for (const row of rows) {
        row.path_length = String(row.path).split(">").length;
      }
    }
    toNumeric(rows, [
      "users",
      "converted_users",
      "purchase_count",
      "revenue",
      "path_length",
    ]);
    return project(toDateString(rows), PATH_FIELDS);
  });
}

const BRIDGE_FIELDS = [
  "report_start_date",
  "report_end_date",
  "marketplace",
  "advertiser_id",
  "touchpoint",
  "campaign_group_id",
  "campaign_id",
  "ad_group_id",
  "keyword_id",
  "keyword_text",
  "match_type",
  "target_id",
  "audience_id",
  "advertised_asin",
  "sku_id",
  "unique_users",
  "journey_count",
  "impressions",
  "clicks",
  "cost",
  "assisted_converted_users",
  "assisted_purchase_count",
  "assisted_revenue",
  "reported_purchases",
  "reported_sales",
];

/** Touchpoint-to-Campaign/Ad Group links and their assisted outcomes. */
export function loadEntityBridge() {
  return cached("entity_bridge", async () => {
    let rows;
    if (useDatabase()) {
      rows = await query(`
        select b.report_start_date, b.report_end_date, b.marketplace,
               b.advertiser_id, t.touchpoint_key as touchpoint,
               b.campaign_group_id, b.campaign_id, b.ad_group_id,
               b.keyword_id, b.keyword_text, b.match_type, b.target_id,
               b.audience_id, b.advertised_asin, b.sku_id, b.unique_users,
               b.journey_count, b.impressions, b.clicks, b.cost,
               b.assisted_converted_users, b.assisted_purchase_count,
               b.assisted_revenue, b.reported_purchases, b.reported_sales
        from touchpoint_entity_bridge b
        join touchpoint t on t.id = b.touchpoint_pk
        order by b.id
      `);
    } else {
      rows = readCsv(
        resolve(SIMULATED_DIR, "amc_touchpoint_entity_aggregate_sample.csv"),
      );
    }
    toNumeric(rows, [
      "unique_users",
      "journey_count",
      "impressions",
      "clicks",
      "cost",
      "assisted_converted_users",
      "assisted_purchase_count",
      "assisted_revenue",
      "reported_purchases",
      "reported_sales",
    ]);
    return project(toDateString(rows), BRIDGE_FIELDS);
  });
}

// ---------------------------------------------------------------------------
// Strategy
// ---------------------------------------------------------------------------

/**
 * The canonical initial-budget recommendation, as a nested object.
 *
 * Returned in the JSON artifact's own shape in both modes, so views can read
 * `campaigns[i].recommended_ad_groups` without branching.
 */
export function loadBudgetRecommendation() {
  return cached("budget_recommendation", async () => {
    if (!useDatabase()) {
      return readJson(resolve(STRATEGY_OUTPUT_DIR, "initial_budget_recommendation.json"));
    }

    const runs = await query(
      "select * from budget_recommendation_run order by id desc limit 1",
    );
    if (runs.length === 0) return {};
    const run = runs[0];
    // Ordered by the surrogate key, not by `campaign_id`. The importer inserts
    // campaigns in the artifact's own order, so `id` reproduces it; sorting by
    // the business key would sort alphabetically and put the four Campaigns in
    // a different order than file mode returns them in.
    const campaigns = await query(`
      select * from campaign_budget_recommendation
      where run_pk = ${Number(run.id)} order by id
    `);
    const slots = await query(`
      select s.*, c.campaign_id
      from ad_group_budget_slot s
      join campaign_budget_recommendation c
        on c.id = s.campaign_recommendation_pk
      order by s.id
    `);
    return rebuildBudgetDocument(run, campaigns, slots);
  });
}

/** Reassemble the JSON artifact shape from three relational tables. */
function rebuildBudgetDocument(run, campaigns, slots) {
  const campaignRecords = campaigns.map((row) => ({
    campaign_id: row.campaign_id,
    recommended_ad_group_count: Number(row.recommended_ad_group_count),
    count_rationale: {
      count_formula_version: row.count_formula_version,
      capacity_required_count: Number(row.capacity_required_count),
      final_recommended_count: Number(row.recommended_ad_group_count),
    },
    outcome_contributions: {
      converted_users: Number(row.score_converted_users),
      purchase_count: Number(row.score_purchase_count),
      revenue: Number(row.score_revenue),
    },
    campaign_mta_score: Number(row.campaign_mta_score),
    bridge_summary: {
      historical_ad_group_count: Number(row.bridge_historical_ad_group_count),
      touchpoint_count: Number(row.bridge_touchpoint_count),
      fallback_used: Boolean(row.bridge_fallback_used),
    },
    budget_seed_share: Number(row.budget_seed_share),
    minimum_required_daily_budget: Number(row.minimum_required_daily_budget),
    campaign_budget_seed: Number(row.campaign_budget_seed),
    execution_status: row.execution_status,
    recommended_ad_groups: slots
      .filter((slot) => slot.campaign_id === row.campaign_id)
      .map((slot) => ({
        ad_group_slot_id: slot.ad_group_slot_id,
        allocation_basis: slot.allocation_basis,
        budget_seed_share: Number(slot.budget_seed_share),
        initial_daily_budget: Number(slot.initial_daily_budget),
      })),
  }));

  return {
    schema_version: run.schema_version,
    campaign_group_id: run.campaign_group_id,
    candidate_pool_id: run.candidate_pool_id,
    mta_batch_id: run.mta_batch_id,
    mta_source_snapshot: {
      report_start_date: formatDate(run.source_report_start_date),
      report_end_date: formatDate(run.source_report_end_date),
      marketplace: run.source_marketplace,
      advertiser_id: run.source_advertiser_id,
      attribution_sha256: run.source_attribution_sha256,
      entity_sha256: run.source_entity_sha256,
    },
    recommendation_type: run.recommendation_type,
    handoff_status: run.handoff_status,
    is_optimized: Boolean(run.is_optimized),
    budget_derivation: {
      formula_version: run.formula_version,
      normalization_universe: run.normalization_universe,
      outcome_weights: {
        converted_users: Number(run.weight_converted_users),
        purchase_count: Number(run.weight_purchase_count),
        revenue: Number(run.weight_revenue),
      },
    },
    campaigns: campaignRecords,
    budget_seed_total: Number(run.budget_seed_total),
    warnings: [],
  };
}

/**
 * The Campaign Group, its Campaigns, weights, and capacity rules.
 *
 * Capacity rules are pipeline configuration rather than observed data, so no
 * table holds them; in database mode the key is present but empty. Views must
 * treat it as optional. The outcome weights are recoverable, because the
 * budget run records the weights it was executed with.
 */
export function loadStrategyRequest() {
  return cached("strategy_request", async () => {
    if (!useDatabase()) {
      return readJson(resolve(STRATEGY_INPUT_DIR, "strategy_request.json"));
    }

    const groups = await query(`
      select g.campaign_group_id, g.group_name, g.platform, g.currency,
             g.total_daily_budget, g.sample_version, g.candidate_pool_id,
             g.mta_batch_id, a.marketplace, a.advertiser_id
      from campaign_group g
      join advertiser a on a.id = g.advertiser_pk
      limit 1
    `);
    if (groups.length === 0) return {};

    // See `loadBudgetRecommendation`: `id` is the artifact's insertion order,
    // `campaign_id` is alphabetical and would disagree with file mode.
    const campaigns = await query(`
      select campaign_id, campaign_name, ad_product, status
      from campaign order by id
    `);
    const runs = await query(`
      select weight_converted_users, weight_purchase_count,
             weight_revenue, source_report_start_date,
             source_report_end_date, source_marketplace,
             source_advertiser_id, source_attribution_sha256,
             source_entity_sha256
      from budget_recommendation_run order by id desc limit 1
    `);

    let weights = {};
    let source = {};
    if (runs.length > 0) {
      const run = runs[0];
      weights = {
        converted_users: Number(run.weight_converted_users),
        purchase_count: Number(run.weight_purchase_count),
        revenue: Number(run.weight_revenue),
      };
      source = {
        report_start_date: formatDate(run.source_report_start_date),
        report_end_date: formatDate(run.source_report_end_date),
        marketplace: run.source_marketplace,
        advertiser_id: run.source_advertiser_id,
        attribution_sha256: run.source_attribution_sha256,
        entity_sha256: run.source_entity_sha256,
      };
    }

    const group = groups[0];
    return {
      sample_version: group.sample_version || "",
      candidate_pool_id: group.candidate_pool_id || "",
      mta_batch_id: group.mta_batch_id || "",
      mta_source: source,
      campaign_group: {
        campaign_group_id: group.campaign_group_id,
        group_name: group.group_name,
        platform: group.platform,
        marketplace: group.marketplace,
        advertiser_id: group.advertiser_id,
        currency: group.currency,
        total_daily_budget: Number(group.total_daily_budget),
      },
      campaigns,
      outcome_weights: weights,
      capacity_rules: {},
    };
  });
}

/** Eligible keyword, SKU, target, and audience counts per Campaign. */
export function loadCandidatePool() {
  return cached("candidate_pool", async () => {
    if (!useDatabase()) {
      return readJson(resolve(STRATEGY_INPUT_DIR, "candidate_pool.json"));
    }

    const rows = await query(`
      select c.campaign_id, tc.candidate_kind, tc.eligible_count,
             tc.candidate_pool_id, tc.candidate_usage_policy,
             tc.sample_version
      from targeting_candidate tc
      join campaign c on c.id = tc.campaign_pk
      order by c.id, tc.id
    `);

    const counts = new Map();
    let poolId = "";
    let policy = "";
    let version = "";
    for (const row of rows) {
      poolId ||= row.candidate_pool_id;
      policy ||= row.candidate_usage_policy || "";
      version ||= row.sample_version || "";
      if (!counts.has(row.campaign_id)) {
        counts.set(row.campaign_id, { campaign_id: row.campaign_id });
      }
      counts.get(row.campaign_id)[row.candidate_kind] = Number(row.eligible_count);
    }

    const group = await query("select campaign_group_id from campaign_group limit 1");
    return {
      sample_version: version,
      candidate_pool_id: poolId,
      campaign_group_id: group[0]?.campaign_group_id ?? "",
      candidate_usage_policy: policy,
      campaign_candidate_counts: [...counts.values()],
    };
  });
}

// ---------------------------------------------------------------------------
// MTA-SIM canonical research data
// ---------------------------------------------------------------------------

function availabilityFor(value, explicit) {
  return explicit ?? (value === null || value === undefined ? "NOT_PROVIDED" : "AVAILABLE");
}

function localTouchpointConfigurations(configuration) {
  return (configuration.touchpoints ?? []).map((item) => {
    const format =
      item.format ??
      (item.ad_product === "AMAZON_DSP" ? item.inventory_type : item.ad_type);
    const creative = item.creative ?? item.creative_type ?? null;
    const availability = item.field_availability ?? {};
    const interactions = [
      ...(item.impression_enabled === false ? [] : ["IMPRESSION"]),
      ...(item.click_enabled === false ? [] : ["CLICK"]),
    ];
    const base = [
      item.ad_product,
      format,
      item.placement ?? "UNSPECIFIED",
      creative ?? "UNSPECIFIED",
    ].join(":");
    return {
      identifier: item.identifier,
      provider: item.provider ?? "AMAZON_ADS",
      ad_product: item.ad_product,
      format,
      placement: item.placement ?? null,
      placement_availability: availabilityFor(
        item.placement,
        availability.placement,
      ),
      creative,
      creative_availability: availabilityFor(
        creative,
        availability.creative,
      ),
      interaction_type_availability:
        availability.interaction_type ?? "AVAILABLE",
      supported_interactions: interactions,
      impression_enabled: interactions.includes("IMPRESSION"),
      click_enabled: interactions.includes("CLICK"),
      billing_type:
        item.billing_type ?? item.cost_type ??
        (item.cost_per_click !== null && item.cost_per_click !== undefined
          ? "CPC"
          : "CPM"),
      cost_per_click: item.cost_per_click ?? null,
      cost_per_thousand_impressions:
        item.cost_per_thousand_impressions ?? null,
      base_impressions: item.base_impressions ?? null,
      click_through_rate: item.click_through_rate ?? null,
      platform_conversion_rate: item.platform_conversion_rate ?? null,
      conversion_log_odds_effect: item.conversion_log_odds_effect ?? null,
      compatibility_keys: interactions.map((interaction) => `${base}:${interaction}`),
      active: true,
    };
  });
}

function flattenObservation(item) {
  const scope = item.reporting_scope ?? {};
  const touchpoint = item.touchpoint ?? {};
  return {
    ...item,
    ...scope,
    provider: touchpoint.provider ?? item.provider ?? null,
    touchpoint: touchpoint.ad_product
      ? [
          touchpoint.ad_product,
          touchpoint.format,
          touchpoint.placement ?? "UNSPECIFIED",
          touchpoint.creative ?? "UNSPECIFIED",
          touchpoint.interaction_type,
        ].join(":")
      : item.touchpoint_key ?? null,
    interaction_type: touchpoint.interaction_type ?? null,
    placement_availability:
      touchpoint.field_availability?.placement ?? item.placement_availability ?? null,
    creative_availability:
      touchpoint.field_availability?.creative ?? item.creative_availability ?? null,
    interaction_type_availability:
      touchpoint.field_availability?.interaction_type ??
      item.interaction_type_availability ?? null,
    report_date: scope.report_start_date ?? item.report_date ?? null,
  };
}

function localSimulationResearch() {
  const directory = simulatorDataDirectory();
  if (!directory) return {
    runs: [], providers: [], products: [], campaigns: [], adGroups: [],
    touchpoints: [], productEconomics: [], campaignProductLinks: [],
    history: [], delivery: [], generationConfigs: [], touchpointObservations: [],
    masterObjects: [],
  };
  const research = readJson(resolve(directory, "simulation_research.json"));
  const configuration = readJson(resolve(directory, "effective_configuration.json"));
  const runs = research.simulation_runs ?? [];
  const run = runs[0] ?? {};
  const budget = research.budget_observations ?? [];
  const evaluations = research.evaluation_outcome_observations ?? [];
  const outcomes = new Map(
    evaluations.map((item) => {
      const scope = item.reporting_scope ?? {};
      return [
        [item.campaign_id, scope.marketplace, scope.report_start_date, item.budget_level].join("|"),
        flattenObservation(item),
      ];
    }),
  );
  const history = budget.map((item) => {
    const row = flattenObservation(item);
    const outcome = outcomes.get(
      [item.campaign_id, row.marketplace, row.report_date, item.budget_level].join("|"),
    ) ?? {};
    return { ...row, ...outcome, configured_budget: item.configured_budget,
      actual_spend: item.actual_spend, budget_level: item.budget_level };
  });
  return {
    runs,
    providers: (run.providers ?? []).map((item) => ({ ...item, active: true })),
    products: run.products ?? [],
    campaigns: run.campaigns ?? [],
    adGroups: run.ad_groups ?? [],
    touchpoints: localTouchpointConfigurations(configuration),
    productEconomics: run.product_economics ?? [],
    campaignProductLinks: run.campaign_product_links ?? [],
    history,
    delivery: (research.delivery_observations ?? []).map(flattenObservation),
    generationConfigs: runs.map((item) => ({
      run_id: item.run_id,
      seed: item.seed,
      configuration_sha256: item.configuration_sha256,
      effective_configuration: item.effective_configuration,
    })),
    touchpointObservations: research.touchpoint_observations ?? [],
    masterObjects: [],
  };
}

async function simulationTablesAvailable() {
  const rows = await query(
    "select to_regclass('public.mta_simulation_run')::text as table_name",
  );
  return Boolean(rows[0]?.table_name);
}

async function databaseSimulationResearch() {
  if (!(await simulationTablesAvailable())) return localSimulationResearch();
  const [runs, providers, products, campaigns, adGroups, touchpoints,
    productEconomics, campaignProductLinks, history, delivery] = await Promise.all([
    query("select run_id, seed, configuration_sha256, effective_configuration from mta_simulation_run order by run_id"),
    query("select *, true as active from mta_sim_provider order by run_id, provider"),
    query("select * from mta_sim_product order by run_id, product_id"),
    query("select * from mta_sim_campaign order by run_id, campaign_id"),
    query("select * from mta_sim_ad_group order by run_id, campaign_id, ad_group_id"),
    query(`select *, array_remove(array[
      case when impression_enabled then concat(ad_product, ':', format, ':', coalesce(placement, 'UNSPECIFIED'), ':', coalesce(creative, 'UNSPECIFIED'), ':IMPRESSION') end,
      case when click_enabled then concat(ad_product, ':', format, ':', coalesce(placement, 'UNSPECIFIED'), ':', coalesce(creative, 'UNSPECIFIED'), ':CLICK') end
    ], null) as compatibility_keys from mta_sim_touchpoint order by run_id, identifier`),
    query("select * from mta_sim_product_economics order by run_id, product_id, currency"),
    query("select * from mta_sim_campaign_product_link order by run_id, campaign_id, product_id"),
    query(`select b.run_id, b.campaign_id, b.marketplace, b.advertiser_id,
      b.currency, b.report_date, b.budget_level, b.configured_budget,
      b.actual_spend, o.product_id, o.total_units, o.total_revenue,
      o.expected_organic_units, o.expected_organic_revenue,
      o.incremental_units, o.incremental_revenue, o.contribution_profit
      from mta_sim_budget_observation b
      left join mta_sim_outcome_observation o
        on o.run_id = b.run_id and o.campaign_id = b.campaign_id
       and o.marketplace = b.marketplace and o.report_date = b.report_date
       and o.budget_level = b.budget_level and o.evaluation_only = true
      order by b.run_id, b.report_date, b.campaign_id, b.budget_level`),
    query("select * from mta_sim_delivery_observation order by run_id, report_date, campaign_id, id"),
  ]);
  toDateString(history, ["report_date"]);
  toDateString(delivery, ["report_date"]);
  for (const row of delivery) row.touchpoint = row.touchpoint_key;
  splitTouchpoint(delivery);
  toNumeric(history, ["budget_level", "configured_budget", "actual_spend",
    "total_units", "total_revenue", "expected_organic_units",
    "expected_organic_revenue", "incremental_units", "incremental_revenue",
    "contribution_profit"]);
  toNumeric(delivery, ["impressions", "clicks", "cost", "reported_purchases", "reported_sales"]);
  const masterTable = await query(
    "select to_regclass('public.dashboard_master_object')::text as table_name",
  );
  const masterObjects = masterTable[0]?.table_name
    ? await query("select * from dashboard_master_object order by entity_type, entity_id")
    : [];
  return {
    runs, providers, products, campaigns, adGroups, touchpoints,
    productEconomics, campaignProductLinks, history, delivery,
    generationConfigs: runs,
    touchpointObservations: [],
    masterObjects,
  };
}

const MASTER_ENTITY_TYPES = new Set([
  "provider", "product", "campaign", "ad_group", "touchpoint",
  "product_economics", "generation_config",
]);

async function ensureMasterObjectTable() {
  await query(`create table if not exists dashboard_master_object (
    entity_type text not null,
    entity_id text not null,
    payload jsonb not null,
    active boolean not null default true,
    updated_at timestamptz not null default now(),
    primary key (entity_type, entity_id),
    check (entity_type in ('provider', 'product', 'campaign', 'ad_group',
      'touchpoint', 'product_economics', 'generation_config'))
  )`);
}

function validateMasterObject(entityType, entityId, payload) {
  if (!MASTER_ENTITY_TYPES.has(entityType)) {
    throw new Error(`unsupported master entity type: ${entityType}`);
  }
  if (!String(entityId ?? "").trim()) throw new Error("entity_id is required");
  if (!payload || Array.isArray(payload) || typeof payload !== "object") {
    throw new Error("payload must be a JSON object");
  }
}

/** Save an editable future-run master object without mutating generated history. */
export async function saveMasterObject(entityType, entityId, payload) {
  if (!useDatabase()) throw new Error("Master editing requires DATABASE=true");
  validateMasterObject(entityType, entityId, payload);
  await ensureMasterObjectTable();
  const rows = await query(
    `insert into dashboard_master_object
       (entity_type, entity_id, payload, active, updated_at)
     values ($1, $2, $3::jsonb, true, now())
     on conflict (entity_type, entity_id) do update
       set payload = excluded.payload, active = true, updated_at = now()
     returning *`,
    [entityType, entityId, JSON.stringify(payload)],
  );
  clearCaches();
  return rows[0];
}

/** Archive a future-run master object; generated observations remain immutable. */
export async function archiveMasterObject(entityType, entityId) {
  if (!useDatabase()) throw new Error("Master editing requires DATABASE=true");
  validateMasterObject(entityType, entityId, {});
  await ensureMasterObjectTable();
  const rows = await query(
    `update dashboard_master_object set active = false, updated_at = now()
      where entity_type = $1 and entity_id = $2 returning *`,
    [entityType, entityId],
  );
  clearCaches();
  return rows[0] ?? null;
}

/** Load immutable MTA-SIM history and editable master/configuration entities. */
export function loadSimulationResearch() {
  return cached("simulation_research", async () =>
    useDatabase() ? databaseSimulationResearch() : localSimulationResearch(),
  );
}

/**
 * Every loader's result in one object: the payload `GET /api/dashboard`
 * returns and the static build writes to a file.
 *
 * The whole snapshot is roughly 400 KB of JSON, which is smaller than the
 * artifacts it was read from and small enough to send once rather than
 * paginate. Sending it whole is also what lets the six views share one source
 * of truth, exactly as the Python views shared one cache.
 */
export async function loadSnapshot() {
  const [
    adsDaily,
    attributionResults,
    comparisonTouchpoints,
    comparisonSummary,
    recommendedAttribution,
    entityBridge,
    pathReport,
    budgetRecommendation,
    strategyRequest,
    candidatePool,
    simulationResearch,
  ] = await Promise.all([
    loadAdsDaily(),
    loadAttributionResults(),
    loadComparisonTouchpoints(),
    loadComparisonSummary(),
    loadRecommendedAttribution(),
    loadEntityBridge(),
    loadPathReport(),
    loadBudgetRecommendation(),
    loadStrategyRequest(),
    loadCandidatePool(),
    loadSimulationResearch(),
  ]);

  return {
    mode: activeMode(),
    source: sourceLabel(),
    adsDaily,
    attributionResults,
    comparisonTouchpoints,
    comparisonSummary,
    recommendedAttribution,
    entityBridge,
    pathReport,
    budgetRecommendation,
    strategyRequest,
    candidatePool,
    simulationResearch,
  };
}
