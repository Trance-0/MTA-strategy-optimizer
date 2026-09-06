/**
 * Regression tests for the lossless Data Generator configuration editor.
 *
 * Data flow:
 *   generator/configuration.js -> GeneratorConfigEditor.vue -> DataGenerator.vue
 */

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { pathToFileURL } from "node:url";
import test from "node:test";
import { compileScript, parse } from "@vue/compiler-sfc";
import { createRenderer, h, nextTick, ref } from "vue";

import {
  SECTION_NAMES,
  addPathReference,
  addPathScenario,
  addTouchpoint,
  cloneConfiguration,
  deletePathScenario,
  deleteTouchpoint,
  duplicatePathScenario,
  duplicateTouchpoint,
  formatConfigurationText,
  getSectionStatuses,
  isDirtyConfiguration,
  moveListItem,
  parseConfigurationText,
  removePathReference,
  shouldShowRegionalBehavior,
  validateLocalConfiguration,
} from "../src/generator/configuration.js";
import { createGeneratorLifecycle, replacePresetIfConfirmed } from "../src/generator/lifecycle.js";

const EDITOR_COMPONENT = resolve(import.meta.dirname, "..", "src", "components", "GeneratorConfigEditor.vue");
const VUE_MODULE = pathToFileURL(resolve(import.meta.dirname, "..", "node_modules", "vue", "index.mjs")).href;
const CONFIGURATION_MODULE = pathToFileURL(resolve(import.meta.dirname, "..", "src", "generator", "configuration.js")).href;
const CLIENT_MODULE = resolve(import.meta.dirname, "..", "src", "api", "client.js");
const GENERATOR_VIEW = resolve(import.meta.dirname, "..", "src", "views", "DataGenerator.vue");
const APP_VIEW = resolve(import.meta.dirname, "..", "src", "App.vue");
const DATA_GENERATOR_VIEW = resolve(import.meta.dirname, "..", "src", "views", "DataGenerator.vue");

function baselineConfiguration() {
  return {
    seed: 1729,
    report_start_date: "2025-01-01",
    report_end_date: "2025-01-03",
    advertiser_id: "toy_advertiser",
    base_product_price: 20,
    baseline_conversion_log_odds: -3.5,
    campaign_replications: 1,
    global_behavior: {
      weekly_traffic_multipliers: [1, 1, 1, 1, 1, 1, 1],
      daily_traffic_trend: 0,
      conversion_probability_daily_noise_standard_deviation: 0.05,
      performance_volume_noise_standard_deviation: 0.05,
      path_audience_noise_standard_deviation: 0.05,
      performance_revenue_noise_standard_deviation: 0.02,
      path_revenue_noise_standard_deviation: 0.02,
      additional_unit_probability: 0.1,
      repeat_purchase_probability: 0.05,
    },
    marketplaces: [{
      code: "TOY",
      currency_code: "USD",
      traffic_multiplier: 1,
      price_multiplier: 1,
    }],
    touchpoints: [{
      identifier: "display_ad",
      ad_product: "AMAZON_DSP",
      ad_type: null,
      creative_type: "IMAGE",
      inventory_type: "DISPLAY",
      placement: null,
      base_impressions: 1000,
      click_through_rate: 0.6,
      platform_conversion_rate: 0.02,
      cost_per_click: null,
      cost_per_thousand_impressions: 10,
      conversion_log_odds_effect: 0.3,
      extension: { enabled: false },
    }],
    path_scenarios: [{
      identifier: "display_only",
      touchpoint_identifiers: ["display_ad"],
      base_users: 100,
      adjacent_synergy_log_odds: 0,
    }],
    provenance: { source: "fixture", intentional_null: null },
    unknown_extension: { retained: true, count: 0 },
  };
}

test("guided and JSON helpers retain unknown fields, null, zero, and false", () => {
  const original = baselineConfiguration();
  const detached = cloneConfiguration(original);
  detached.global_behavior.daily_traffic_trend = 0;

  const parsed = parseConfigurationText(JSON.stringify(detached));
  assert.equal(parsed.ok, true);
  assert.deepEqual(parsed.configuration, original);
  assert.equal(parsed.configuration.provenance.intentional_null, null);
  assert.equal(parsed.configuration.unknown_extension.count, 0);
  assert.equal(parsed.configuration.touchpoints[0].extension.enabled, false);
  assert.equal(isDirtyConfiguration(original, parsed.configuration), false);
});

test("invalid JSON remains text-only and format returns a parse error", () => {
  const invalid = '{\n  "seed": 1729,\n';
  const parsed = parseConfigurationText(invalid);
  const formatted = formatConfigurationText(invalid);

  assert.equal(parsed.ok, false);
  assert.equal(parsed.text, invalid);
  assert.ok(parsed.error.length > 0);
  assert.equal(formatted.ok, false);
  assert.equal(formatted.text, invalid);
});

test("JSON parsing rejects non-finite numbers and over-deep unknown values", () => {
  assert.equal(parseConfigurationText('{"seed":1e400}').ok, false);
  const nested = `${'{"nested":'.repeat(70)}null${"}".repeat(70)}`;
  assert.equal(parseConfigurationText(nested).ok, false);
});

test("regional controls are visible only for the regional variant", () => {
  assert.equal(shouldShowRegionalBehavior("baseline"), false);
  assert.equal(shouldShowRegionalBehavior("regional"), true);
});

test("duplicate touchpoints receive a unique identifier and independent nested data", () => {
  const original = baselineConfiguration();
  const duplicated = duplicateTouchpoint(original, 0);

  assert.equal(duplicated.touchpoints.length, 2);
  assert.equal(duplicated.touchpoints[1].identifier, "display_ad_copy");
  duplicated.touchpoints[1].extension.enabled = true;
  assert.equal(duplicated.touchpoints[0].extension.enabled, false);
  assert.equal(original.touchpoints.length, 1);
});

test("card and reference operations preserve order without reconstructing unknown fields", () => {
  let configuration = baselineConfiguration();
  configuration = addTouchpoint(configuration);
  configuration = addPathScenario(configuration);
  configuration = addPathReference(configuration, 1, configuration.touchpoints[1].identifier);
  configuration = moveListItem(configuration, ["touchpoints"], 1, 0);

  assert.equal(configuration.touchpoints[0].identifier, "touchpoint");
  assert.deepEqual(configuration.path_scenarios[1].touchpoint_identifiers, ["touchpoint"]);
  assert.deepEqual(configuration.unknown_extension, { retained: true, count: 0 });
});

test("referenced touchpoints cannot be deleted and identify the first path reference", () => {
  const result = deleteTouchpoint(baselineConfiguration(), 0);

  assert.equal(result.deleted, false);
  assert.equal(result.reference.pathIndex, 0);
  assert.equal(result.reference.pathIdentifier, "display_only");
  assert.equal(result.configuration.touchpoints.length, 1);
});

test("local validation uses backend-compatible paths and approved sections", () => {
  const invalid = baselineConfiguration();
  invalid.marketplaces = [];
  invalid.touchpoints.push({ ...invalid.touchpoints[0], identifier: "display_ad" });
  invalid.touchpoints[0].cost_per_click = 1;
  invalid.path_scenarios[0].touchpoint_identifiers = ["missing", "missing"];
  invalid.global_behavior.additional_unit_probability = 2;

  const issues = validateLocalConfiguration(invalid, "baseline");
  assert.deepEqual(SECTION_NAMES, [
    "basics", "global_behavior", "marketplace", "touchpoints",
    "path_scenarios", "regional_behavior", "configuration",
  ]);
  assert.ok(issues.some((issue) => issue.path === "/marketplaces" && issue.section === "marketplace"));
  assert.ok(issues.some((issue) => issue.path === "/touchpoints/1/identifier" && issue.section === "touchpoints"));
  assert.ok(issues.some((issue) => issue.path === "/touchpoints/0/cost_per_click" && issue.section === "touchpoints"));
  assert.ok(issues.some((issue) => issue.path === "/path_scenarios/0/touchpoint_identifiers/0" && issue.section === "path_scenarios"));
  assert.ok(issues.every((issue) => SECTION_NAMES.includes(issue.section)));
});

test("local billing validation points malformed CPM at the CPM control", () => {
  const invalid = baselineConfiguration();
  invalid.touchpoints[0].cost_per_click = null;
  invalid.touchpoints[0].cost_per_thousand_impressions = "invalid";
  const issues = validateLocalConfiguration(invalid, "baseline");
  assert.ok(issues.some((item) => item.path === "/touchpoints/0/cost_per_thousand_impressions"));
  assert.ok(!issues.some((item) => item.path === "/touchpoints/0/cost_per_click"));
});

test("backend issues take error precedence over incomplete local section status", () => {
  const statuses = getSectionStatuses(
    baselineConfiguration(),
    "baseline",
    [{ path: "/seed", section: "basics", message: "Seed must be an integer." }],
    [{ path: "/seed", section: "basics", message: "Backend rejected seed." }],
  );

  assert.equal(statuses.basics, "error");
  assert.equal(statuses.regional_behavior, "hidden");
  assert.equal(statuses.marketplace, "complete");
});

test("regional marketplace validation remains owned by the marketplace section", () => {
  const configuration = baselineConfiguration();
  Object.assign(configuration.marketplaces[0], {
    internet_reach_rate: 0,
    target_audience_density: 2,
    economic_willingness_multiplier: 0,
    income_inequality_gini: 2,
  });
  configuration.regional_behavior = {
    reference_internet_reach_rate: 0.8,
    reference_target_audience_density: 0.1,
    reference_income_inequality_gini: 0.35,
    economic_willingness_log_odds_weight: 1,
    income_inequality_noise_weight: 1,
  };

  const issues = validateLocalConfiguration(configuration, "regional")
    .filter((item) => item.path.startsWith("/marketplaces/0/"));
  assert.equal(issues.length, 4);
  assert.ok(issues.every((item) => item.section === "marketplace"));
});

test("editor component exposes the full-object binding and validation change interface", () => {
  const source = readFileSync(EDITOR_COMPONENT, "utf8");

  for (const prop of ["modelValue", "variant", "backendIssues", "disabled"]) {
    assert.match(source, new RegExp(`\\b${prop}\\b`));
  }
  for (const event of ["update:modelValue", "local-issues-change", "dirty-change"]) {
    assert.match(source, new RegExp(event));
  }
  assert.match(source, /Format JSON/);
  assert.match(source, /<details/);
});

test("path and reference operations duplicate, delete, remove, and reorder detached values", () => {
  let configuration = baselineConfiguration();
  configuration = addTouchpoint(configuration);
  configuration = addPathReference(configuration, 0, "touchpoint");
  configuration = duplicatePathScenario(configuration, 0);
  configuration = moveListItem(configuration, ["path_scenarios"], 1, 0);
  configuration = moveListItem(configuration, ["path_scenarios", 0, "touchpoint_identifiers"], 1, 0);
  configuration = removePathReference(configuration, 0, 1);

  assert.equal(configuration.path_scenarios[0].identifier, "display_only_copy");
  assert.deepEqual(configuration.path_scenarios[0].touchpoint_identifiers, ["touchpoint"]);
  assert.deepEqual(configuration.path_scenarios[1].touchpoint_identifiers, ["display_ad", "touchpoint"]);
  const deleted = deleteTouchpoint(configuration, 1);
  assert.equal(deleted.deleted, false, "the remaining copied path protects touchpoint");
  const withoutPaths = deletePathScenario(deletePathScenario(configuration, 1), 0);
  assert.equal(deleteTouchpoint(withoutPaths, 1).deleted, true);
});

test("local advertiser validation accepts 128 characters and rejects 129", () => {
  const atLimit = baselineConfiguration();
  atLimit.advertiser_id = "a".repeat(128);
  const tooLong = cloneConfiguration(atLimit);
  tooLong.advertiser_id += "a";

  assert.ok(!validateLocalConfiguration(atLimit, "baseline").some((item) => item.path === "/advertiser_id"));
  assert.ok(validateLocalConfiguration(tooLong, "baseline").some((item) => item.path === "/advertiser_id" && item.section === "basics"));
});

test("mounted editor immediately publishes valid JSON, retains the last valid object on parse failure, and reports dirty state", async () => {
  const original = baselineConfiguration();
  const mounted = await mountEditor(original);
  click(findByText(mounted.root, "JSON configuration"));
  await nextTick();
  const textarea = findNode(mounted.root, (node) => node.type === "textarea");
  const valid = cloneConfiguration(original);
  valid.seed = 99;
  textarea.props.onInput({ target: { value: JSON.stringify(valid) } });
  await nextTick();

  assert.equal(mounted.value.value.seed, 99);
  assert.notStrictEqual(mounted.value.value, original);
  assert.equal(original.seed, 1729);
  assert.ok(mounted.dirty.includes(true));
  textarea.props.onInput({ target: { value: '{"seed":' } });
  await nextTick();

  assert.equal(mounted.value.value.seed, 99);
  assert.ok(mounted.issues.at(-1).some((item) => item.section === "configuration"));
  click(findByText(mounted.root, "Guided editor"));
  await nextTick();
  assert.ok(findNode(mounted.root, (node) => node.type === "textarea"), "invalid JSON blocks Guided mode");
});

test("reselecting the active editor mode is a no-op", async () => {
  const mounted = await mountEditor(baselineConfiguration());
  const seed = findInputByLabel(mounted.root, "Random seed");
  seed.props.onInput({ target: { value: "88" } });
  await nextTick();
  click(findByText(mounted.root, "Guided editor"));
  await nextTick();
  assert.equal(mounted.value.value.seed, 88, "active Guided tab must not publish stale JSON");

  click(findByText(mounted.root, "JSON configuration"));
  await nextTick();
  const textarea = findNode(mounted.root, (node) => node.type === "textarea");
  textarea.props.onInput({ target: { value: '{"seed":' } });
  await nextTick();
  click(findByText(mounted.root, "JSON configuration"));
  await nextTick();
  assert.equal(findNode(mounted.root, (node) => node.type === "textarea").value, '{"seed":');
  assert.ok(mounted.issues.at(-1).some((item) => item.section === "configuration"));
});

test("mounted editor repairs malformed collection fields without crashing", async () => {
  const configuration = baselineConfiguration();
  configuration.marketplaces = {};
  configuration.touchpoints = {};
  configuration.path_scenarios = {};
  configuration.global_behavior.weekly_traffic_multipliers = {};
  const mounted = await mountEditor(configuration);

  assert.ok(findByText(mounted.root, "Add marketplace"));
  assert.ok(findByText(mounted.root, "Add touchpoint"));
  assert.ok(findByText(mounted.root, "Add path scenario"));
  const monday = findInputByLabel(mounted.root, "Mon");
  monday.props.onInput({ target: { value: "1.2" } });
  await nextTick();
  assert.ok(Array.isArray(mounted.value.value.global_behavior.weekly_traffic_multipliers));
  assert.equal(mounted.value.value.global_behavior.weekly_traffic_multipliers[0], 1.2);
  mounted.restore();
});

test("mounted editor can repair or delete malformed collection members", async () => {
  const configuration = baselineConfiguration();
  configuration.touchpoints = [null];
  configuration.path_scenarios = [null];
  const mounted = await mountEditor(configuration);
  const identifier = findInputByLabel(mounted.root, "Identifier");
  identifier.props.onInput({ target: { value: "repaired_touchpoint" } });
  await nextTick();
  assert.equal(mounted.value.value.touchpoints[0].identifier, "repaired_touchpoint");
  click(findAllByText(mounted.root, "Delete")[0]);
  await nextTick();
  assert.equal(mounted.value.value.touchpoints.length, 0);
  mounted.restore();
});

test("backend issue links mark and focus their exact repeated field", async () => {
  const issue = {
    path: "/touchpoints/0/identifier",
    section: "touchpoints",
    message: "Backend rejected the identifier.",
  };
  const mounted = await mountEditor(baselineConfiguration(), "baseline", [issue]);
  const input = findNode(mounted.root, (node) => node.props?.["data-config-path"] === issue.path);
  assert.ok(input);
  assert.equal(input.props["aria-invalid"], "true");
  const details = findDetails(mounted.root, "Touchpoints");
  await findNode(mounted.root, (node) => node.type === "button" && textOf(node).includes(issue.message))
    .props.onClick({ preventDefault() {} });
  assert.equal(details.open, true);
  assert.equal(mounted.document.activeElement === input, true);
  mounted.restore();
});

test("mounted editor retains focused identifier inputs across immutable parent updates", async () => {
  const mounted = await mountEditor(baselineConfiguration());
  const touchpoint = findNode(mounted.root, (node) => node.type === "input" && node.value === "display_ad");
  touchpoint.focus();
  touchpoint.props.onInput({ target: { value: "display_ad_edited" } });
  await nextTick();
  assert.strictEqual(findNode(mounted.root, (node) => node.type === "input" && node.value === "display_ad_edited"), touchpoint);
  assert.strictEqual(mounted.document.activeElement, touchpoint);

  const path = findNode(mounted.root, (node) => node.type === "input" && node.value === "display_only");
  path.focus();
  path.props.onInput({ target: { value: "display_only_edited" } });
  await nextTick();
  assert.strictEqual(findNode(mounted.root, (node) => node.type === "input" && node.value === "display_only_edited"), path);
  assert.strictEqual(mounted.document.activeElement, path);
});

test("protected delete opens path scenarios and focuses the first referenced control", async () => {
  const mounted = await mountEditor(baselineConfiguration());
  const pathDetails = findDetails(mounted.root, "Path scenarios");
  assert.equal(pathDetails.open, undefined);
  click(findAllByText(mounted.root, "Delete")[0]);
  await nextTick();
  await nextTick();

  assert.equal(pathDetails.open, true);
  assert.equal(mounted.document.activeElement.type, "button");
  assert.equal(textOf(mounted.document.activeElement), "Remove");
});

test("mounted editor applies regional visibility and distinct numeric constraint ranges", async () => {
  const baseline = await mountEditor(baselineConfiguration());
  assert.equal(findNode(baseline.root, (node) => textOf(node).includes("Regional behavior")), null);
  const regionalConfiguration = baselineConfiguration();
  regionalConfiguration.regional_behavior = {
    reference_internet_reach_rate: 0.8,
    reference_target_audience_density: 0.1,
    reference_income_inequality_gini: 0.35,
    economic_willingness_log_odds_weight: 1,
    income_inequality_noise_weight: 1,
  };
  Object.assign(regionalConfiguration.marketplaces[0], {
    internet_reach_rate: 0.8,
    target_audience_density: 0.1,
    economic_willingness_multiplier: 1,
    income_inequality_gini: 0.35,
  });
  const regional = await mountEditor(regionalConfiguration, "regional");
  assert.ok(findNode(regional.root, (node) => textOf(node).includes("Regional behavior")));
  const trend = findInputByLabel(regional.root, "Daily traffic trend");
  const noise = findInputByLabel(regional.root, "Conversion probability daily noise");
  const probability = findInputByLabel(regional.root, "Additional unit probability");
  assert.equal(trend.props.min, undefined);
  assert.equal(noise.props.min, "0");
  assert.equal(noise.props.max, undefined);
  assert.equal(probability.props.min, "0");
  assert.equal(probability.props.max, "1");
});

test("generator validation preserves backend 400 issues for the editor", async () => {
  const client = await loadClient(false);
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async (url, options) => new Response(JSON.stringify({
    error: "invalid_configuration",
    valid: false,
    issues: [{ path: "/seed", section: "basics", message: "Seed must be an integer." }],
  }), { status: 400, headers: { "Content-Type": "application/json" } });
  try {
    await assert.rejects(
      client.validateGeneratorConfiguration("baseline", baselineConfiguration()),
      (error) => error.code === "invalid_configuration"
        && error.issues?.[0]?.path === "/seed"
        && error.issues?.[0]?.section === "basics",
    );
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("generator preflight forwards the caller's timeout signal", async () => {
  const client = await loadClient(false);
  const originalFetch = globalThis.fetch;
  const signal = {};
  globalThis.fetch = async (_url, options) => {
    assert.strictEqual(options.signal, signal);
    return new Response(JSON.stringify({ valid: true, issues: [] }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  };
  try {
    assert.equal((await client.validateGeneratorConfiguration("baseline", baselineConfiguration(), { signal })).valid, true);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("static generator operations refuse without requesting an API", async () => {
  const client = await loadClient(true);
  const originalFetch = globalThis.fetch;
  let requested = false;
  globalThis.fetch = async () => { requested = true; throw new Error("static must not fetch"); };
  try {
    await assert.rejects(client.fetchGeneratorPreset("baseline", "toy"), /static build/i);
    await assert.rejects(client.validateGeneratorConfiguration("baseline", {}), /static build/i);
    await assert.rejects(client.startGeneratorRun("baseline", {}), /static build/i);
    await assert.rejects(client.fetchGeneratorRun("run-1"), /static build/i);
    await assert.rejects(client.exportGeneratorRun("run-1", {}), /static build/i);
    assert.equal(requested, false);
    assert.match((await client.fetchGeneratorOverview()).reason, /local or container full-stack deployment/i);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("generator page delegates editing to the complete editor and gates runs on preflight", () => {
  const source = readFileSync(GENERATOR_VIEW, "utf8");

  assert.match(source, /import GeneratorConfigEditor from "\.\.\/components\/GeneratorConfigEditor\.vue"/);
  assert.match(source, /validateGeneratorConfiguration/);
  assert.match(source, /function runPreflight\(\)/);
  assert.match(source, /@local-issues-change/);
  assert.match(source, /@dirty-change/);
  assert.match(source, /:backend-issues="backendIssues"/);
  assert.match(source, /:disabled="busy \|\| operationActive"/);
  assert.match(source, /Run preflight/);
  assert.match(source, /preflight.*valid/s);
  assert.match(source, /window\.confirm/);
  assert.doesNotMatch(source, /generator-guided/);
});

test("application shell leaves Data Generator capability messaging to its own page", () => {
  const source = readFileSync(APP_VIEW, "utf8");

  assert.match(source, /routeLoaded && !writable && page !== 'generator'/);
});

test("a deferred preflight cannot authorize a newer configuration", () => {
  const lifecycle = createGeneratorLifecycle();
  const original = baselineConfiguration();
  const request = lifecycle.beginPreflight("baseline", original);
  const changed = cloneConfiguration(original);
  changed.seed = 99;
  lifecycle.configurationChanged("baseline", changed);

  assert.equal(lifecycle.acceptPreflight(request), false);
  assert.equal(lifecycle.canGenerate("baseline", changed), false);
});

test("a deferred preflight error is ignored after the configuration changes", () => {
  const lifecycle = createGeneratorLifecycle();
  const original = baselineConfiguration();
  lifecycle.configurationChanged("baseline", original);
  const request = lifecycle.beginPreflight("baseline", original);
  const changed = cloneConfiguration(original);
  changed.seed = 100;
  lifecycle.configurationChanged("baseline", changed);

  assert.equal(lifecycle.isCurrentPreflight(request), false);
});

test("run tokens reject a late poll after the active run has been cleared", () => {
  const lifecycle = createGeneratorLifecycle();
  const poll = lifecycle.beginRun("run-1");
  lifecycle.clearRun();

  assert.equal(lifecycle.isCurrentRun(poll, "run-1"), false);
});

test("dirty preset cancellation keeps the mounted editor state and confirmation replaces it", async () => {
  const calls = [];
  const cancelled = await replacePresetIfConfirmed({
    dirty: true,
    confirm: () => false,
    loadPreset: async (...args) => calls.push(args),
    variant: "regional",
    preset: "toy",
  });
  assert.equal(cancelled, false);
  assert.deepEqual(calls, []);

  const confirmed = await replacePresetIfConfirmed({
    dirty: true,
    confirm: () => true,
    loadPreset: async (...args) => calls.push(args),
    variant: "regional",
    preset: "toy",
  });
  assert.equal(confirmed, true);
  assert.deepEqual(calls, [["regional", "toy"]]);

  const failed = await replacePresetIfConfirmed({
    dirty: true,
    confirm: () => true,
    loadPreset: async () => false,
    variant: "regional",
    preset: "standard",
  });
  assert.equal(failed, false);
});

test("mounted generator page renders static unavailability without mounting an editor or calling a preset API", async () => {
  const calls = [];
  const mounted = await mountGeneratorPage({
    fetchGeneratorOverview: async () => ({ available: false, reason: "Full-stack deployment required.", variants: [], configuration: {} }),
    fetchGeneratorPreset: async () => calls.push("preset"),
  });

  assert.ok(findNode(mounted.root, (node) => textOf(node) === "Data Generator is unavailable"));
  assert.equal(findNode(mounted.root, (node) => node.props?.id === "generator-editor-test"), null);
  assert.deepEqual(calls, []);
  mounted.restore();
});

test("a late preset response cannot overwrite the newest requested selection", async () => {
  const resolvers = {};
  const mounted = await mountGeneratorPage({
    fetchGeneratorOverview: async () => generatorOverview(),
    fetchGeneratorPreset: async (_variant, preset) => new Promise((resolve) => { resolvers[preset] = resolve; }),
  });
  const select = findNode(mounted.root, (node) => node.props?.id === "generator-preset");
  select.props.onChange({ target: { value: "standard" } });
  select.props.onChange({ target: { value: "extended" } });
  await nextTick();

  const newest = baselineConfiguration();
  newest.seed = 300;
  resolvers.extended({ configuration: newest });
  await Promise.resolve();
  await nextTick();
  const older = baselineConfiguration();
  older.seed = 200;
  resolvers.standard({ configuration: older });
  await Promise.resolve();
  await nextTick();
  await nextTick();

  assert.equal(findNode(mounted.root, (node) => node.props?.id === "generator-editor-test").props["data-seed"], 300);
  assert.equal(findNode(mounted.root, (node) => node.props?.id === "generator-preset").value, "extended");
  mounted.restore();
});

test("mounted generator page forwards preflight and final-run issues, while a stale preflight is ignored", async () => {
  let resolvePreflight;
  const deferred = new Promise((resolve) => { resolvePreflight = resolve; });
  const mounted = await mountGeneratorPage({
    fetchGeneratorOverview: async () => generatorOverview(),
    validateGeneratorConfiguration: async () => deferred,
    startGeneratorRun: async () => {
      const error = new Error("Final validation rejected configuration.");
      error.issues = [{ path: "/seed", section: "basics", message: "Final seed issue." }];
      throw error;
    },
  });
  const preflightButton = findNode(mounted.root, (node) => textOf(node).trim() === "Run preflight" && node.props?.onClick);
  assert.ok(preflightButton, textOf(mounted.root));
  click(preflightButton);
  await nextTick();
  click(findByText(mounted.root, "Change config"));
  await nextTick();
  resolvePreflight({ valid: true, issues: [] });
  await nextTick();
  await nextTick();
  assert.ok(findNode(mounted.root, (node) => textOf(node).trim() === "Configuration changed; run preflight again."));

  mounted.client.validateGeneratorConfiguration = async () => ({ valid: true, issues: [] });
  click(findNode(mounted.root, (node) => textOf(node).trim() === "Run preflight" && node.props?.onClick));
  await nextTick();
  await nextTick();
  click(findNode(mounted.root, (node) => textOf(node).trim() === "Generate dataset" && node.props?.onClick));
  await nextTick();
  await nextTick();
  assert.ok(findNode(mounted.root, (node) => textOf(node).trim() === "Final seed issue."));
  mounted.restore();
});

test("mounted generator page disables preset and variant selectors for an active run", async () => {
  const mounted = await mountGeneratorPage({ fetchGeneratorOverview: async () => generatorOverview() });
  click(findNode(mounted.root, (node) => textOf(node).trim() === "Run preflight" && node.props?.onClick));
  await nextTick();
  await nextTick();
  click(findNode(mounted.root, (node) => textOf(node).trim() === "Generate dataset" && node.props?.onClick));
  await nextTick();
  await nextTick();
  assert.equal(findNode(mounted.root, (node) => node.props?.id === "generator-variant").props.disabled, true);
  assert.equal(findNode(mounted.root, (node) => node.props?.id === "generator-preset").props.disabled, true);
  assert.equal(findNode(mounted.root, (node) => node.props?.id === "generator-editor-test").props["data-disabled"], true);
  mounted.restore();
});

async function loadEditor() {
  const source = readFileSync(EDITOR_COMPONENT, "utf8");
  const descriptor = parse(source, { filename: EDITOR_COMPONENT }).descriptor;
  const compiled = compileScript(descriptor, { id: "generator-config-editor-test", inlineTemplate: true });
  const code = compiled.content
    .replaceAll('from "vue"', `from ${JSON.stringify(VUE_MODULE)}`)
    .replaceAll('from "../generator/configuration.js"', `from ${JSON.stringify(CONFIGURATION_MODULE)}`);
  return import(`data:text/javascript,${encodeURIComponent(code)}`);
}

function generatorOverview() {
  return {
    available: true,
    defaultVariant: "baseline",
    defaultPreset: "toy",
    configuration: baselineConfiguration(),
    variants: [{
      key: "baseline",
      presets: [
        { key: "toy", label: "Toy" },
        { key: "standard", label: "Standard" },
        { key: "extended", label: "Extended" },
      ],
    }],
  };
}

async function mountGeneratorPage(clientOverrides) {
  const client = {
    exportGeneratorRun: async () => ({}),
    fetchGeneratorOverview: async () => generatorOverview(),
    fetchGeneratorPreset: async () => ({ configuration: baselineConfiguration() }),
    fetchGeneratorRun: async () => ({}),
    generatorDownloadUrl: () => "#download",
    startGeneratorRun: async () => ({ runId: "run-1", status: "queued" }),
    validateGeneratorConfiguration: async () => ({ valid: true, issues: [] }),
    ...clientOverrides,
  };
  globalThis.__generatorPageClient = client;
  const component = await loadGeneratorPage();
  const root = createNode("root");
  const document = { activeElement: null, getElementById: (id) => findNode(root, (node) => node.props?.id === id) };
  const previousDocument = globalThis.document;
  const previousWindow = globalThis.window;
  globalThis.document = document;
  globalThis.window = {
    location: { protocol: "https:", hostname: "localhost" },
    confirm: () => true,
    setTimeout: () => 1,
    clearTimeout() {},
  };
  createRenderer(rendererOptions(document)).createApp(component).mount(root);
  await nextTick();
  await Promise.resolve();
  await new Promise((resolve) => setTimeout(resolve, 0));
  await nextTick();
  return {
    root,
    client,
    restore() { globalThis.document = previousDocument; globalThis.window = previousWindow; delete globalThis.__generatorPageClient; },
  };
}

async function loadGeneratorPage() {
  const vueUrl = JSON.stringify(VUE_MODULE);
  const tableUrl = `data:text/javascript,${encodeURIComponent("export default { render: () => null };")}`;
  const editorSource = `import { h } from ${vueUrl}; export default { props: ["modelValue", "backendIssues", "disabled"], emits: ["update:modelValue", "dirty-change"], setup(props, { emit }) { return () => h("div", { id: "generator-editor-test", "data-disabled": props.disabled, "data-seed": props.modelValue.seed }, [h("button", { onClick: () => emit("dirty-change", true) }, "Dirty editor"), h("button", { onClick: () => emit("update:modelValue", { ...props.modelValue, seed: 99 }) }, "Change config"), ...props.backendIssues.map((item) => h("span", item.message))]); } };`;
  const editorUrl = `data:text/javascript,${encodeURIComponent(editorSource)}`;
  const apiSource = `const c = () => globalThis.__generatorPageClient; export const exportGeneratorRun = (...a) => c().exportGeneratorRun(...a); export const fetchGeneratorOverview = (...a) => c().fetchGeneratorOverview(...a); export const fetchGeneratorPreset = (...a) => c().fetchGeneratorPreset(...a); export const fetchGeneratorRun = (...a) => c().fetchGeneratorRun(...a); export const generatorDownloadUrl = (...a) => c().generatorDownloadUrl(...a); export const startGeneratorRun = (...a) => c().startGeneratorRun(...a); export const validateGeneratorConfiguration = (...a) => c().validateGeneratorConfiguration(...a);`;
  const apiUrl = `data:text/javascript,${encodeURIComponent(apiSource)}`;
  const source = readFileSync(DATA_GENERATOR_VIEW, "utf8");
  const descriptor = parse(source, { filename: DATA_GENERATOR_VIEW }).descriptor;
  const compiled = compileScript(descriptor, { id: "data-generator-page-test", inlineTemplate: true });
  const code = compiled.content
    .replaceAll('from "vue"', `from ${vueUrl}`)
    .replace('from "../components/DataTable.vue"', `from ${JSON.stringify(tableUrl)}`)
    .replace('from "../components/GeneratorConfigEditor.vue"', `from ${JSON.stringify(editorUrl)}`)
    .replace('from "../generator/lifecycle.js"', `from ${JSON.stringify(pathToFileURL(resolve(import.meta.dirname, "..", "src", "generator", "lifecycle.js")).href)}`)
    .replace('from "../api/client.js"', `from ${JSON.stringify(apiUrl)}`);
  return (await import(`data:text/javascript,${encodeURIComponent(code)}`)).default;
}

async function loadClient(staticBuild) {
  const source = readFileSync(CLIENT_MODULE, "utf8")
    .replace('import { DASHBOARD_RESOURCES } from "../pages.js";', "const DASHBOARD_RESOURCES = [];")
    .replace(
      'export const IS_STATIC = import.meta.env.VITE_STATIC_BUILD === "true";',
      `export const IS_STATIC = ${staticBuild};`,
    );
  return import(`data:text/javascript,${encodeURIComponent(source)}`);
}

async function mountEditor(configuration, variant = "baseline", backendIssues = []) {
  const component = (await loadEditor()).default;
  const root = createNode("root");
  const document = { activeElement: null, getElementById: (id) => findNode(root, (node) => node.props?.id === id) };
  const previousDocument = globalThis.document;
  globalThis.document = document;
  const value = ref(cloneConfiguration(configuration));
  const dirty = [];
  const issues = [];
  const renderer = createRenderer(rendererOptions(document));
  renderer.createApp({
    setup() {
      return () => h(component, {
        modelValue: value.value,
        variant,
        backendIssues,
        disabled: false,
        "onUpdate:modelValue": (next) => { value.value = next; },
        "onDirty-change": (next) => dirty.push(next),
        "onLocal-issues-change": (next) => issues.push(next),
      });
    },
  }).mount(root);
  await nextTick();
  return { root, value, dirty, issues, document, restore: () => { globalThis.document = previousDocument; } };
}

function rendererOptions(document) {
  return {
    createElement: (type) => createNode(type, document),
    createElementNS: (_namespace, type) => createNode(type, document),
    createText: (text) => ({ type: "#text", text, parent: null }),
    createComment: (text) => ({ type: "#comment", text, parent: null }),
    setText: (node, text) => { node.text = text; },
    setElementText: (node, text) => { node.children = [{ type: "#text", text, parent: node }]; },
    parentNode: (node) => node.parent,
    nextSibling: (node) => node.parent?.children[node.parent.children.indexOf(node) + 1] ?? null,
    insert: (child, parent, anchor = null) => {
      child.parent = parent;
      const position = anchor ? parent.children.indexOf(anchor) : -1;
      if (position === -1) parent.children.push(child);
      else parent.children.splice(position, 0, child);
      if (parent.type === "select") parent.options = parent.children.filter((item) => item.type === "option");
    },
    remove: (child) => { if (child.parent) child.parent.children.splice(child.parent.children.indexOf(child), 1); },
    patchProp: (node, key, _previous, value) => {
      node.props[key] = value;
      if (key === "value" || key === "checked" || key === "open" || key === "selected") node[key] = value;
    },
  };
}

function createNode(type, document = null) {
  return {
    type, props: {}, children: [], parent: null, text: "", options: [],
    addEventListener() {}, removeEventListener() {},
    focus() { if (document) document.activeElement = this; },
  };
}

function findNode(node, predicate) {
  if (predicate(node)) return node;
  for (const child of node.children ?? []) { const found = findNode(child, predicate); if (found) return found; }
  return null;
}
function findAll(node, predicate, found = []) { if (predicate(node)) found.push(node); for (const child of node.children ?? []) findAll(child, predicate, found); return found; }
function textOf(node) { return node?.text + (node?.children ?? []).map(textOf).join(""); }
function findByText(root, text) { const node = findNode(root, (item) => item.type === "button" && textOf(item) === text); assert.ok(node, `button ${text} exists`); return node; }
function findAllByText(root, text) { return findAll(root, (item) => item.type === "button" && textOf(item) === text); }
function click(node) { node.props.onClick({ preventDefault() {} }); }
function findDetails(root, label) { const node = findNode(root, (item) => item.type === "details" && textOf(item.children[0]).includes(label)); assert.ok(node, `${label} details exists`); return node; }
function findInputByLabel(root, label) { const labelNode = findNode(root, (item) => item.type === "label" && textOf(item).includes(label)); return findNode(labelNode, (item) => item.type === "input"); }
