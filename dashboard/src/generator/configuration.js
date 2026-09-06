/**
 * Lossless client-side configuration operations for the Data Generator editor.
 *
 * This module sits between the full JSON configuration value and the Vue
 * editor. It mirrors only immediate, visible validation; backend preflight is
 * authoritative for simulation semantics.
 */

export const SECTION_NAMES = Object.freeze([
  "basics",
  "global_behavior",
  "marketplace",
  "touchpoints",
  "path_scenarios",
  "regional_behavior",
  "configuration",
]);

const NOISE_FIELDS = [
  "conversion_probability_daily_noise_standard_deviation",
  "performance_volume_noise_standard_deviation",
  "path_audience_noise_standard_deviation",
  "performance_revenue_noise_standard_deviation",
  "path_revenue_noise_standard_deviation",
];

const MAX_CONFIGURATION_DEPTH = 64;
const MAX_CONFIGURATION_ISSUES = 128;
const MAX_PATH_REFERENCES = 64;

const TOUCHPOINT_TEMPLATE = {
  identifier: "touchpoint",
  ad_product: "",
  ad_type: null,
  creative_type: null,
  inventory_type: null,
  placement: null,
  base_impressions: 0,
  click_through_rate: 0,
  platform_conversion_rate: 0,
  cost_per_click: 0,
  cost_per_thousand_impressions: null,
  conversion_log_odds_effect: 0,
};

const PATH_TEMPLATE = {
  identifier: "path_scenario",
  touchpoint_identifiers: [],
  base_users: 1,
  adjacent_synergy_log_odds: 0,
};

/** Return a detached clone without dropping arbitrary JSON-compatible keys. */
export function cloneConfiguration(configuration) {
  if (typeof structuredClone === "function") {
    try {
      return structuredClone(configuration);
    } catch {
      // Vue passes reactive proxies to the component. Configurations are JSON
      // values, so JSON cloning is the safe detached fallback for that input.
    }
  }
  return JSON.parse(JSON.stringify(configuration));
}

/** Serialize an entire configuration for the JSON editor. */
export function serializeConfiguration(configuration) {
  return JSON.stringify(configuration, null, 2);
}

/** Parse JSON text without overwriting the last valid guided configuration. */
export function parseConfigurationText(text) {
  try {
    const configuration = JSON.parse(text);
    if (!isPlainObject(configuration)) {
      throw new Error("The configuration must be a JSON object.");
    }
    if (!isStrictJsonValue(configuration)) {
      throw new Error("The configuration must contain only finite JSON values and may be at most 64 levels deep.");
    }
    return { ok: true, configuration: cloneConfiguration(configuration) };
  } catch (error) {
    return { ok: false, text, error: error.message };
  }
}

/** Validate and consistently indent JSON editor text. */
export function formatConfigurationText(text) {
  const parsed = parseConfigurationText(text);
  if (!parsed.ok) return parsed;
  return { ok: true, configuration: parsed.configuration, text: serializeConfiguration(parsed.configuration) };
}

/** Compare values independent of object-key insertion order. */
export function isDirtyConfiguration(before, after) {
  return stableStringify(before) !== stableStringify(after);
}

/** Whether the selected variant exposes regional configuration controls. */
export function shouldShowRegionalBehavior(variant) {
  return variant === "regional";
}

/** Return lightweight client issues in the backend's { path, section, message } shape. */
export function validateLocalConfiguration(configuration, variant) {
  if (!isPlainObject(configuration)) {
    return [issue("/configuration", "configuration", "Configuration must be a JSON object.")];
  }
  const issues = [];
  validateBasics(configuration, issues);
  validateGlobalBehavior(configuration, issues);
  validateMarketplace(configuration, variant, issues);
  const touchpointIdentifiers = validateTouchpoints(configuration, issues);
  validatePathScenarios(configuration, touchpointIdentifiers, issues);
  if (shouldShowRegionalBehavior(variant)) validateRegionalBehavior(configuration, issues);
  if (issues.length <= MAX_CONFIGURATION_ISSUES) return issues;
  return issues.slice(0, MAX_CONFIGURATION_ISSUES - 1).concat(
    issue("/", "configuration", "Additional local configuration issues were omitted."),
  );
}

/** Derive accordion status; backend responses take precedence over local checks. */
export function getSectionStatuses(configuration, variant, localIssues = [], backendIssues = []) {
  const statuses = Object.fromEntries(SECTION_NAMES.map((name) => [name, "complete"]));
  statuses.regional_behavior = shouldShowRegionalBehavior(variant) ? "complete" : "hidden";
  for (const item of localIssues) {
    if (statuses[item.section] !== undefined && statuses[item.section] !== "hidden") {
      statuses[item.section] = "incomplete";
    }
  }
  for (const item of backendIssues) {
    if (statuses[item.section] !== undefined && statuses[item.section] !== "hidden") {
      statuses[item.section] = "error";
    }
  }
  return statuses;
}

/** Append a detached default touchpoint with an identifier unique to the list. */
export function addTouchpoint(configuration) {
  const next = cloneConfiguration(configuration);
  next.touchpoints = Array.isArray(next.touchpoints) ? next.touchpoints : [];
  const identifiers = new Set(next.touchpoints.map((item) => item?.identifier));
  next.touchpoints.push({ ...cloneConfiguration(TOUCHPOINT_TEMPLATE), identifier: uniqueIdentifier("touchpoint", identifiers) });
  return next;
}

/** Duplicate a touchpoint without sharing objects or arrays and allocate a unique identifier. */
export function duplicateTouchpoint(configuration, index) {
  const next = cloneConfiguration(configuration);
  if (!Array.isArray(next.touchpoints) || !isPlainObject(next.touchpoints[index])) return next;
  const duplicate = cloneConfiguration(next.touchpoints[index]);
  const identifiers = new Set(next.touchpoints.map((item) => item?.identifier));
  duplicate.identifier = uniqueIdentifier(`${String(duplicate.identifier || "touchpoint")}_copy`, identifiers);
  next.touchpoints.splice(index + 1, 0, duplicate);
  return next;
}

/** Delete an unreferenced touchpoint or return the first path that protects it. */
export function deleteTouchpoint(configuration, index) {
  const next = cloneConfiguration(configuration);
  const touchpoint = next.touchpoints?.[index];
  if (!isPlainObject(touchpoint)) {
    if (Array.isArray(next.touchpoints) && index >= 0 && index < next.touchpoints.length) {
      next.touchpoints.splice(index, 1);
      return { configuration: next, deleted: true, reference: null };
    }
    return { configuration: next, deleted: false, reference: null };
  }
  const reference = findTouchpointReference(next, touchpoint.identifier);
  if (reference) return { configuration: next, deleted: false, reference };
  next.touchpoints.splice(index, 1);
  return { configuration: next, deleted: true, reference: null };
}

/** Append a detached path scenario. */
export function addPathScenario(configuration) {
  const next = cloneConfiguration(configuration);
  next.path_scenarios = Array.isArray(next.path_scenarios) ? next.path_scenarios : [];
  const identifiers = new Set(next.path_scenarios.map((item) => item?.identifier));
  next.path_scenarios.push({ ...cloneConfiguration(PATH_TEMPLATE), identifier: uniqueIdentifier("path_scenario", identifiers) });
  return next;
}

/** Duplicate a path card and assign an independent identifier. */
export function duplicatePathScenario(configuration, index) {
  const next = cloneConfiguration(configuration);
  if (!Array.isArray(next.path_scenarios) || !isPlainObject(next.path_scenarios[index])) return next;
  const duplicate = cloneConfiguration(next.path_scenarios[index]);
  const identifiers = new Set(next.path_scenarios.map((item) => item?.identifier));
  duplicate.identifier = uniqueIdentifier(`${String(duplicate.identifier || "path_scenario")}_copy`, identifiers);
  next.path_scenarios.splice(index + 1, 0, duplicate);
  return next;
}

/** Remove a path scenario by its displayed index. */
export function deletePathScenario(configuration, index) {
  const next = cloneConfiguration(configuration);
  if (Array.isArray(next.path_scenarios) && index >= 0 && index < next.path_scenarios.length) {
    next.path_scenarios.splice(index, 1);
  }
  return next;
}

/** Add an existing touchpoint identifier to a path if it is not already present. */
export function addPathReference(configuration, pathIndex, identifier) {
  const next = cloneConfiguration(configuration);
  const scenario = next.path_scenarios?.[pathIndex];
  const touchpoints = Array.isArray(next.touchpoints) ? next.touchpoints : [];
  const known = new Set(touchpoints.map((item) => item?.identifier));
  if (!isPlainObject(scenario) || !known.has(identifier)) return next;
  scenario.touchpoint_identifiers = Array.isArray(scenario.touchpoint_identifiers)
    ? scenario.touchpoint_identifiers : [];
  if (!scenario.touchpoint_identifiers.includes(identifier)) scenario.touchpoint_identifiers.push(identifier);
  return next;
}

/** Remove one ordered path reference. */
export function removePathReference(configuration, pathIndex, referenceIndex) {
  const next = cloneConfiguration(configuration);
  const references = next.path_scenarios?.[pathIndex]?.touchpoint_identifiers;
  if (Array.isArray(references) && referenceIndex >= 0 && referenceIndex < references.length) {
    references.splice(referenceIndex, 1);
  }
  return next;
}

/** Move an item within a nested list, returning an untouched clone for invalid moves. */
export function moveListItem(configuration, listPath, fromIndex, toIndex) {
  const next = cloneConfiguration(configuration);
  const list = listPath.reduce((value, key) => value?.[key], next);
  if (!Array.isArray(list) || fromIndex < 0 || toIndex < 0 || fromIndex >= list.length || toIndex >= list.length) return next;
  const [item] = list.splice(fromIndex, 1);
  list.splice(toIndex, 0, item);
  return next;
}

function validateBasics(configuration, issues) {
  if (!Number.isInteger(configuration.seed)) issues.push(issue("/seed", "basics", "Seed must be an integer."));
  if (
    typeof configuration.advertiser_id !== "string"
    || !configuration.advertiser_id.trim()
    || configuration.advertiser_id.length > 128
  ) {
    issues.push(issue("/advertiser_id", "basics", "Advertiser ID is required and must contain at most 128 characters."));
  }
  const start = validDate(configuration.report_start_date);
  const end = validDate(configuration.report_end_date);
  if (!start) issues.push(issue("/report_start_date", "basics", "Report start date must be an ISO date."));
  if (!end) issues.push(issue("/report_end_date", "basics", "Report end date must be an ISO date."));
  if (start && end && (end < start || (end - start) / 86400000 + 1 > 366)) {
    issues.push(issue("/report_end_date", "basics", "Report window must contain 1 to 366 days."));
  }
  numberIssue(configuration.base_product_price, "/base_product_price", "basics", "Base product price must be positive and finite.", issues, (value) => value > 0);
  numberIssue(configuration.baseline_conversion_log_odds, "/baseline_conversion_log_odds", "basics", "Baseline conversion log odds must be finite.", issues);
  const replications = configuration.campaign_replications ?? 1;
  if (!Number.isInteger(replications)) issues.push(issue("/campaign_replications", "basics", "Campaign replications must be an integer."));
  else if (replications < 1 || replications > 50) issues.push(issue("/campaign_replications", "basics", "Campaign replications must be between 1 and 50."));
}

function validateGlobalBehavior(configuration, issues) {
  const behavior = configuration.global_behavior;
  if (!isPlainObject(behavior)) {
    issues.push(issue("/global_behavior", "global_behavior", "Global behavior must be an object."));
    return;
  }
  if (!Array.isArray(behavior.weekly_traffic_multipliers) || behavior.weekly_traffic_multipliers.length !== 7) {
    issues.push(issue("/global_behavior/weekly_traffic_multipliers", "global_behavior", "Weekly traffic multipliers must contain seven values."));
  } else behavior.weekly_traffic_multipliers.forEach((value, index) => numberIssue(value, `/global_behavior/weekly_traffic_multipliers/${index}`, "global_behavior", "Traffic multiplier must be positive and finite.", issues, (item) => item > 0));
  numberIssue(behavior.daily_traffic_trend, "/global_behavior/daily_traffic_trend", "global_behavior", "Daily traffic trend must be finite.", issues);
  NOISE_FIELDS.forEach((field) => numberIssue(behavior[field], `/global_behavior/${field}`, "global_behavior", "Noise standard deviation must be non-negative and finite.", issues, (value) => value >= 0));
  ["additional_unit_probability", "repeat_purchase_probability"].forEach((field) => numberIssue(behavior[field], `/global_behavior/${field}`, "global_behavior", "Probability must be between 0 and 1.", issues, (value) => value >= 0 && value <= 1));
}

function validateMarketplace(configuration, variant, issues) {
  if (!Array.isArray(configuration.marketplaces) || configuration.marketplaces.length !== 1) {
    issues.push(issue("/marketplaces", "marketplace", "Exactly one marketplace is required."));
    return;
  }
  const marketplace = configuration.marketplaces[0];
  if (!isPlainObject(marketplace)) {
    issues.push(issue("/marketplaces/0", "marketplace", "Marketplace must be an object."));
    return;
  }
  if (typeof marketplace.code !== "string" || !marketplace.code.trim()) issues.push(issue("/marketplaces/0/code", "marketplace", "Marketplace code is required."));
  if (typeof marketplace.currency_code !== "string" || !/^[A-Z]{3}$/.test(marketplace.currency_code)) issues.push(issue("/marketplaces/0/currency_code", "marketplace", "Currency code must be a three-letter uppercase ISO code."));
  ["traffic_multiplier", "price_multiplier"].forEach((field) => numberIssue(marketplace[field], `/marketplaces/0/${field}`, "marketplace", `${field === "traffic_multiplier" ? "Traffic" : "Price"} multiplier must be positive and finite.`, issues, (value) => value > 0));
  if (shouldShowRegionalBehavior(variant)) {
    ["internet_reach_rate", "target_audience_density"].forEach((field) => numberIssue(marketplace[field], `/marketplaces/0/${field}`, "marketplace", "Value must be greater than 0 and at most 1.", issues, (value) => value > 0 && value <= 1));
    numberIssue(marketplace.economic_willingness_multiplier, "/marketplaces/0/economic_willingness_multiplier", "marketplace", "Economic willingness multiplier must be positive and finite.", issues, (value) => value > 0);
    numberIssue(marketplace.income_inequality_gini, "/marketplaces/0/income_inequality_gini", "marketplace", "Income inequality Gini must be between 0 and 1.", issues, (value) => value >= 0 && value <= 1);
  }
}

function validateTouchpoints(configuration, issues) {
  if (!Array.isArray(configuration.touchpoints) || configuration.touchpoints.length < 1 || configuration.touchpoints.length > 64) {
    issues.push(issue("/touchpoints", "touchpoints", "Touchpoints must contain 1 to 64 items."));
    return new Set();
  }
  const identifiers = new Set();
  configuration.touchpoints.forEach((touchpoint, index) => {
    const prefix = `/touchpoints/${index}`;
    if (!isPlainObject(touchpoint)) { issues.push(issue(prefix, "touchpoints", "Touchpoint must be an object.")); return; }
    if (typeof touchpoint.identifier !== "string" || !touchpoint.identifier.trim()) issues.push(issue(`${prefix}/identifier`, "touchpoints", "Touchpoint identifier is required."));
    else if (identifiers.has(touchpoint.identifier)) issues.push(issue(`${prefix}/identifier`, "touchpoints", "Touchpoint identifier must be unique."));
    else identifiers.add(touchpoint.identifier);
    numberIssue(touchpoint.base_impressions, `${prefix}/base_impressions`, "touchpoints", "Base impressions must be non-negative and finite.", issues, (value) => value >= 0);
    ["click_through_rate", "platform_conversion_rate"].forEach((field) => numberIssue(touchpoint[field], `${prefix}/${field}`, "touchpoints", "Rate must be between 0 and 1.", issues, (value) => value >= 0 && value <= 1));
    numberIssue(touchpoint.conversion_log_odds_effect, `${prefix}/conversion_log_odds_effect`, "touchpoints", "Conversion log odds effect must be non-negative and finite.", issues, (value) => value >= 0);
    const cpc = validNumber(touchpoint.cost_per_click) && touchpoint.cost_per_click >= 0;
    const cpm = validNumber(touchpoint.cost_per_thousand_impressions) && touchpoint.cost_per_thousand_impressions >= 0;
    if (touchpoint.cost_per_click !== null && !cpc) issues.push(issue(`${prefix}/cost_per_click`, "touchpoints", "CPC must be a non-negative number or null."));
    else if (touchpoint.cost_per_thousand_impressions !== null && !cpm) issues.push(issue(`${prefix}/cost_per_thousand_impressions`, "touchpoints", "CPM must be a non-negative number or null."));
    else if (cpc === cpm) issues.push(issue(`${prefix}/cost_per_click`, "touchpoints", "Exactly one of CPC or CPM must be a non-negative number."));
  });
  return identifiers;
}

function validatePathScenarios(configuration, touchpointIdentifiers, issues) {
  if (!Array.isArray(configuration.path_scenarios) || configuration.path_scenarios.length < 1 || configuration.path_scenarios.length > 256) {
    issues.push(issue("/path_scenarios", "path_scenarios", "Path scenarios must contain 1 to 256 items."));
    return;
  }
  const identifiers = new Set();
  configuration.path_scenarios.forEach((scenario, index) => {
    const prefix = `/path_scenarios/${index}`;
    if (!isPlainObject(scenario)) { issues.push(issue(prefix, "path_scenarios", "Path scenario must be an object.")); return; }
    if (typeof scenario.identifier !== "string" || !scenario.identifier.trim()) issues.push(issue(`${prefix}/identifier`, "path_scenarios", "Path scenario identifier is required."));
    else if (identifiers.has(scenario.identifier)) issues.push(issue(`${prefix}/identifier`, "path_scenarios", "Path scenario identifier must be unique."));
    else identifiers.add(scenario.identifier);
    if (!Array.isArray(scenario.touchpoint_identifiers) || !scenario.touchpoint_identifiers.length) issues.push(issue(`${prefix}/touchpoint_identifiers`, "path_scenarios", "Path scenario requires one or more touchpoint identifiers."));
    else if (scenario.touchpoint_identifiers.length > MAX_PATH_REFERENCES) issues.push(issue(`${prefix}/touchpoint_identifiers`, "path_scenarios", `Path scenario may contain at most ${MAX_PATH_REFERENCES} touchpoint references.`));
    else {
      const references = new Set();
      scenario.touchpoint_identifiers.forEach((identifier, referenceIndex) => {
        const path = `${prefix}/touchpoint_identifiers/${referenceIndex}`;
        if (typeof identifier !== "string" || !touchpointIdentifiers.has(identifier)) issues.push(issue(path, "path_scenarios", "Path scenario references an unknown touchpoint."));
        else if (references.has(identifier)) issues.push(issue(path, "path_scenarios", "Path scenario cannot repeat a touchpoint identifier."));
        references.add(identifier);
      });
    }
    numberIssue(scenario.base_users, `${prefix}/base_users`, "path_scenarios", "Base users must be positive and finite.", issues, (value) => value > 0);
    numberIssue(scenario.adjacent_synergy_log_odds, `${prefix}/adjacent_synergy_log_odds`, "path_scenarios", "Adjacent synergy log odds must be non-negative and finite.", issues, (value) => value >= 0);
  });
}

function validateRegionalBehavior(configuration, issues) {
  const behavior = configuration.regional_behavior;
  if (!isPlainObject(behavior)) { issues.push(issue("/regional_behavior", "regional_behavior", "Regional behavior must be an object.")); return; }
  ["reference_internet_reach_rate", "reference_target_audience_density"].forEach((field) => numberIssue(behavior[field], `/regional_behavior/${field}`, "regional_behavior", "Value must be greater than 0 and at most 1.", issues, (value) => value > 0 && value <= 1));
  numberIssue(behavior.reference_income_inequality_gini, "/regional_behavior/reference_income_inequality_gini", "regional_behavior", "Reference income inequality Gini must be between 0 and 1.", issues, (value) => value >= 0 && value <= 1);
  ["economic_willingness_log_odds_weight", "income_inequality_noise_weight"].forEach((field) => numberIssue(behavior[field], `/regional_behavior/${field}`, "regional_behavior", "Weight must be non-negative and finite.", issues, (value) => value >= 0));
}

function issue(path, section, message) { return { path, section, message }; }
function validNumber(value) { return typeof value === "number" && Number.isFinite(value); }
function numberIssue(value, path, section, message, issues, predicate = () => true) { if (!validNumber(value) || !predicate(value)) issues.push(issue(path, section, message)); }
function isPlainObject(value) { return value !== null && typeof value === "object" && !Array.isArray(value); }
function validDate(value) { if (typeof value !== "string" || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return null; const date = new Date(`${value}T00:00:00Z`); return Number.isNaN(date.valueOf()) || date.toISOString().slice(0, 10) !== value ? null : date; }
function uniqueIdentifier(base, identifiers) { let candidate = base; let suffix = 2; while (identifiers.has(candidate)) { candidate = `${base}_${suffix}`; suffix += 1; } return candidate; }
function findTouchpointReference(configuration, identifier) { const scenarios = Array.isArray(configuration.path_scenarios) ? configuration.path_scenarios : []; for (const [pathIndex, scenario] of scenarios.entries()) { const references = Array.isArray(scenario?.touchpoint_identifiers) ? scenario.touchpoint_identifiers : []; const referenceIndex = references.indexOf(identifier); if (referenceIndex >= 0) return { pathIndex, referenceIndex, pathIdentifier: scenario.identifier, path: `/path_scenarios/${pathIndex}/touchpoint_identifiers/${referenceIndex}` }; } return null; }
function isStrictJsonValue(value) {
  const pending = [{ value, depth: 0 }];
  while (pending.length) {
    const current = pending.pop();
    if (current.depth > MAX_CONFIGURATION_DEPTH) return false;
    if (typeof current.value === "number" && !Number.isFinite(current.value)) return false;
    if (current.value === null || ["string", "boolean", "number"].includes(typeof current.value)) continue;
    if (Array.isArray(current.value)) {
      current.value.forEach((item) => pending.push({ value: item, depth: current.depth + 1 }));
      continue;
    }
    if (isPlainObject(current.value)) {
      Object.values(current.value).forEach((item) => pending.push({ value: item, depth: current.depth + 1 }));
      continue;
    }
    return false;
  }
  return true;
}
function stableStringify(value, depth = 0) { if (depth > MAX_CONFIGURATION_DEPTH) return '"[depth-limit]"'; if (Array.isArray(value)) return `[${value.map((item) => stableStringify(item, depth + 1)).join(",")}]`; if (isPlainObject(value)) return `{${Object.keys(value).sort().map((key) => `${JSON.stringify(key)}:${stableStringify(value[key], depth + 1)}`).join(",")}}`; return JSON.stringify(value); }
