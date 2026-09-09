<script setup>
/**
 * Edit one complete MTA-SIM configuration in guided or JSON form.
 *
 * Public interface: v-model receives the complete object; `variant`,
 * `backendIssues`, and `disabled` control rendering. The component emits
 * `local-issues-change` and `dirty-change` for the parent preflight workflow.
 */
import { computed, nextTick, ref, watch } from "vue";

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
  serializeConfiguration,
  shouldShowRegionalBehavior,
  validateLocalConfiguration,
} from "../generator/configuration.js";

const props = defineProps({
  /** The complete, self-contained JSON configuration object. */
  modelValue: { type: Object, required: true },
  /** The selected generator variant: baseline or regional. */
  variant: { type: String, required: true },
  /** Structured preflight issues returned by the backend. */
  backendIssues: { type: Array, default: () => [] },
  /** Prevent configuration edits while a parent operation is running. */
  disabled: { type: Boolean, default: false },
});

const emit = defineEmits(["update:modelValue", "local-issues-change", "dirty-change"]);
const editorMode = ref("guided");
const jsonText = ref(serializeConfiguration(props.modelValue));
const jsonError = ref("");
const baseline = ref(cloneConfiguration(props.modelValue));
const lastEmitted = ref("");
const blockedDeletion = ref(null);
const referenceSelections = ref({});
const pathDetails = ref(null);
const referenceButtons = {};
const sectionDetails = {};
// Each entry is [key, label, helper sentence]. The helper says what the number
// changes in the generated data, because the field name alone names a symbol.
const NOISE_FIELDS = [
  ["conversion_probability_daily_noise_standard_deviation", "Conversion probability daily noise", "Day-to-day random variation in how likely a conversion is."],
  ["performance_volume_noise_standard_deviation", "Performance volume noise", "Random variation in the impressions and clicks reported each day."],
  ["path_audience_noise_standard_deviation", "Path audience noise", "Random variation in how many users enter each path."],
  ["performance_revenue_noise_standard_deviation", "Performance revenue noise", "Random variation in the revenue on performance rows."],
  ["path_revenue_noise_standard_deviation", "Path revenue noise", "Random variation in the revenue on path rows."],
];
const PROBABILITY_FIELDS = [
  ["additional_unit_probability", "Additional unit probability", "Chance a converting order carries more than one unit."],
  ["repeat_purchase_probability", "Repeat purchase probability", "Chance a converted user buys again inside the window."],
];
/** Section state as a tone the rest of the dashboard already uses for status. */
const STATE_TONES = { complete: "green", incomplete: "amber", error: "red" };

const localIssues = computed(() => {
  const issues = validateLocalConfiguration(props.modelValue, props.variant);
  if (editorMode.value === "json" && jsonError.value) {
    issues.push({ path: "/", section: "configuration", message: jsonError.value });
  }
  return issues;
});
const allIssues = computed(() => {
  const unique = new Map();
  for (const item of [...localIssues.value, ...(props.backendIssues ?? [])]) {
    unique.set(`${item.path}\n${item.section}\n${item.message}`, item);
  }
  return [...unique.values()];
});
const statuses = computed(() => getSectionStatuses(
  props.modelValue,
  props.variant,
  localIssues.value,
  props.backendIssues ?? [],
));
const touchpoints = computed(() => (Array.isArray(props.modelValue.touchpoints) ? props.modelValue.touchpoints : [])
  .map((item) => item && typeof item === "object" && !Array.isArray(item) ? item : {}));
const pathScenarios = computed(() => (Array.isArray(props.modelValue.path_scenarios) ? props.modelValue.path_scenarios : [])
  .map((item) => item && typeof item === "object" && !Array.isArray(item) ? item : {}));
const marketplace = computed(() => Array.isArray(props.modelValue.marketplaces) && props.modelValue.marketplaces[0]
  && typeof props.modelValue.marketplaces[0] === "object" && !Array.isArray(props.modelValue.marketplaces[0])
  ? props.modelValue.marketplaces[0] : null);
const touchpointChoices = computed(() => touchpoints.value
  .map((item) => item?.identifier)
  .filter((identifier) => typeof identifier === "string" && identifier));
const regional = computed(() => shouldShowRegionalBehavior(props.variant));
const isDirty = computed(() => {
  if (editorMode.value === "json" && jsonError.value) return true;
  return isDirtyConfiguration(baseline.value, props.modelValue);
});

watch(localIssues, (issues) => emit("local-issues-change", issues), { immediate: true });
watch(isDirty, (value) => emit("dirty-change", value), { immediate: true });
watch(() => props.modelValue, (value) => {
  const serialized = serializeConfiguration(value);
  if (serialized !== lastEmitted.value) {
    baseline.value = cloneConfiguration(value);
    if (editorMode.value === "guided") jsonText.value = serialized;
  }
}, { deep: true });

function publish(next) {
  lastEmitted.value = serializeConfiguration(next);
  emit("update:modelValue", next);
}

function setValue(path, value) {
  const next = cloneConfiguration(props.modelValue);
  let target = next;
  for (const [index, key] of path.slice(0, -1).entries()) {
    const nextKey = path[index + 1];
    if (typeof nextKey === "number") {
      if (!Array.isArray(target[key])) target[key] = [];
    } else if (!target[key] || typeof target[key] !== "object" || Array.isArray(target[key])) {
      target[key] = {};
    }
    target = target[key];
  }
  target[path.at(-1)] = value;
  publish(next);
}

function numberValue(event) {
  const value = event.target.value;
  return value === "" ? "" : Number(value);
}

function updateNumber(path, event) { setValue(path, numberValue(event)); }
function updateText(path, event) { setValue(path, event.target.value); }

function selectMode(mode) {
  if (mode === editorMode.value) return;
  if (mode === "json") {
    jsonText.value = serializeConfiguration(props.modelValue);
    jsonError.value = "";
    editorMode.value = "json";
    return;
  }
  const parsed = parseConfigurationText(jsonText.value);
  if (!parsed.ok) {
    jsonError.value = parsed.error;
    return;
  }
  jsonError.value = "";
  editorMode.value = "guided";
  publish(parsed.configuration);
}

function onJsonInput(event) {
  jsonText.value = event.target.value;
  const parsed = parseConfigurationText(jsonText.value);
  if (!parsed.ok) {
    jsonError.value = parsed.error;
    return;
  }
  jsonError.value = "";
  publish(parsed.configuration);
}

function formatJson() {
  const formatted = formatConfigurationText(jsonText.value);
  if (!formatted.ok) {
    jsonError.value = formatted.error;
    return;
  }
  jsonError.value = "";
  jsonText.value = formatted.text;
  publish(formatted.configuration);
}

function useNext(next) { blockedDeletion.value = null; referenceSelections.value = {}; publish(next); }
function move(path, index, direction) { useNext(moveListItem(props.modelValue, path, index, index + direction)); }
function addReference(index) {
  const identifier = referenceSelections.value[index];
  if (identifier) useNext(addPathReference(props.modelValue, index, identifier));
}
async function deleteCard(index) {
  const result = deleteTouchpoint(props.modelValue, index);
  if (result.deleted) { useNext(result.configuration); return; }
  if (!result.reference) return;
  blockedDeletion.value = result.reference;
  pathDetails.value.open = true;
  await nextTick();
  referenceButtons[`${result.reference.pathIndex}-${result.reference.referenceIndex}`]?.focus();
}
function setReferenceButton(pathIndex, referenceIndex, element) {
  const key = `${pathIndex}-${referenceIndex}`;
  if (element) referenceButtons[key] = element;
  else delete referenceButtons[key];
}
function availableTouchpointChoices(scenario) {
  const selected = new Set(Array.isArray(scenario?.touchpoint_identifiers) ? scenario.touchpoint_identifiers : []);
  return touchpointChoices.value.filter((identifier) => !selected.has(identifier));
}
function pathReferences(scenario) {
  return Array.isArray(scenario?.touchpoint_identifiers) ? scenario.touchpoint_identifiers : [];
}
function ensureMarketplace() {
  const next = cloneConfiguration(props.modelValue);
  const entry = {
    code: "MARKET",
    currency_code: "USD",
    traffic_multiplier: 1,
    price_multiplier: 1,
  };
  if (regional.value) Object.assign(entry, {
    internet_reach_rate: 1,
    target_audience_density: 1,
    economic_willingness_multiplier: 1,
    income_inequality_gini: 0,
  });
  next.marketplaces = [entry];
  useNext(next);
}
function setBilling(index, basis, event) {
  const next = cloneConfiguration(props.modelValue);
  if (!Array.isArray(next.touchpoints) || index < 0 || index >= next.touchpoints.length) return;
  if (!next.touchpoints[index] || typeof next.touchpoints[index] !== "object" || Array.isArray(next.touchpoints[index])) {
    next.touchpoints[index] = {};
  }
  const touchpoint = next.touchpoints[index];
  touchpoint[basis] = numberValue(event);
  touchpoint[basis === "cost_per_click" ? "cost_per_thousand_impressions" : "cost_per_click"] = null;
  publish(next);
}
function sectionIssues(section) { return allIssues.value.filter((item) => item.section === section); }
function sectionState(section) { return statuses.value[section] ?? "complete"; }
function stateLabel(section) { return sectionState(section).replace(/^./, (letter) => letter.toUpperCase()); }
function stateTone(section) { return STATE_TONES[sectionState(section)] ?? "gray"; }
function hashText(text) {
  let hash = 2166136261;
  for (const character of text) {
    hash ^= character.codePointAt(0);
    hash = Math.imul(hash, 16777619);
  }
  return (hash >>> 0).toString(36);
}
function fieldId(path) { return `generator-field-${hashText(path)}`; }
function issueId(item) { return `generator-issue-${hashText(`${item.path}\n${item.message}`)}`; }
function issuesAtPath(path) { return allIssues.value.filter((item) => item.path === path); }
function fieldProps(path) {
  const matching = issuesAtPath(path);
  return {
    id: fieldId(path),
    "data-config-path": path,
    "aria-invalid": matching.length ? "true" : undefined,
    "aria-describedby": matching.length ? matching.map(issueId).join(" ") : undefined,
  };
}
function setSectionDetails(section, element) {
  if (element) sectionDetails[section] = element;
  else delete sectionDetails[section];
}
function setPathDetails(element) {
  pathDetails.value = element;
  setSectionDetails("path_scenarios", element);
}
async function focusIssue(item) {
  const details = sectionDetails[item.section];
  if (details) details.open = true;
  await nextTick();
  const field = document.getElementById(fieldId(item.path));
  if (field) field.focus();
  else if (details) details.focus();
}
</script>

<template>
  <section :ref="(element) => setSectionDetails('configuration', element)" class="generator-editor" aria-label="Data Generator configuration editor" tabindex="-1">
    <div class="tabs" aria-label="Editor mode">
      <button
        class="tab"
        :class="{ active: editorMode === 'guided' }"
        :aria-pressed="editorMode === 'guided'"
        type="button"
        :disabled="disabled"
        @click="selectMode('guided')"
      >Guided editor</button>
      <button
        class="tab"
        :class="{ active: editorMode === 'json' }"
        :aria-pressed="editorMode === 'json'"
        type="button"
        :disabled="disabled"
        @click="selectMode('json')"
      >JSON configuration</button>
    </div>

    <div v-if="editorMode === 'json'" class="generator-json-editor">
      <label for="generator-configuration-json">Complete JSON configuration</label>
      <textarea
        id="generator-configuration-json"
        :value="jsonText"
        :disabled="disabled"
        aria-describedby="generator-configuration-json-error"
        spellcheck="false"
        rows="24"
        @input="onJsonInput"
      ></textarea>
      <div class="rec-actions">
        <button class="btn" type="button" :disabled="disabled" @click="formatJson">Format JSON</button>
      </div>
      <p v-if="jsonError" id="generator-configuration-json-error" class="notice bad">{{ jsonError }}</p>
    </div>

    <!--
      Each section is an option group: the field named on the left with the
      sentence that says what it changes in the generated data, and the control
      on the right. The `<label>` wraps its own control so clicking the name
      focuses the field, which is also how the section rows stay one element.
    -->
    <div v-else class="generator-guided">
      <ul v-if="sectionIssues('configuration').length" class="generator-issues">
        <li v-for="item in sectionIssues('configuration')" :id="issueId(item)" :key="`${item.path}-${item.message}`"><button type="button" class="btn link generator-issue-link" @click="focusIssue(item)"><code>{{ item.path }}</code> {{ item.message }}</button></li>
      </ul>
      <details :ref="(element) => setSectionDetails('basics', element)" class="setting-group generator-section" tabindex="-1" open>
        <summary>
          <span>Run basics</span><span class="tag" :class="stateTone('basics')">{{ stateLabel('basics') }}</span>
        </summary>
        <div class="generator-section-body">
          <label class="setting-row">
            <span class="setting-label">Random seed<small>The same seed with the same configuration reproduces the same dataset.</small></span>
            <span class="setting-control"><input v-bind="fieldProps('/seed')" :value="modelValue.seed" type="number" step="1" :disabled="disabled" @input="updateNumber(['seed'], $event)"></span>
          </label>
          <label class="setting-row">
            <span class="setting-label">Advertiser identifier<small>Names the advertiser every generated row belongs to.</small></span>
            <span class="setting-control"><input v-bind="fieldProps('/advertiser_id')" :value="modelValue.advertiser_id" type="text" :disabled="disabled" @input="updateText(['advertiser_id'], $event)"></span>
          </label>
          <label class="setting-row">
            <span class="setting-label">Report start date<small>First day of the reporting window, included.</small></span>
            <span class="setting-control"><input v-bind="fieldProps('/report_start_date')" :value="modelValue.report_start_date" type="date" :disabled="disabled" @input="updateText(['report_start_date'], $event)"></span>
          </label>
          <label class="setting-row">
            <span class="setting-label">Report end date<small>Last day of the reporting window, included.</small></span>
            <span class="setting-control"><input v-bind="fieldProps('/report_end_date')" :value="modelValue.report_end_date" type="date" :disabled="disabled" @input="updateText(['report_end_date'], $event)"></span>
          </label>
          <label class="setting-row">
            <span class="setting-label">Base product price<small>Price a single unit sells for before marketplace multipliers.</small></span>
            <span class="setting-control"><input v-bind="fieldProps('/base_product_price')" :value="modelValue.base_product_price" type="number" min="0" step="0.01" :disabled="disabled" @input="updateNumber(['base_product_price'], $event)"></span>
          </label>
          <label class="setting-row">
            <span class="setting-label">Baseline conversion log odds<small>How likely a user converts with no advertising. Negative values are rarer.</small></span>
            <span class="setting-control"><input v-bind="fieldProps('/baseline_conversion_log_odds')" :value="modelValue.baseline_conversion_log_odds" type="number" step="0.01" :disabled="disabled" @input="updateNumber(['baseline_conversion_log_odds'], $event)"></span>
          </label>
          <label class="setting-row">
            <span class="setting-label">Campaign replications<small>How many campaigns each touchpoint produces, from 1 to 50.</small></span>
            <span class="setting-control"><input v-bind="fieldProps('/campaign_replications')" :value="modelValue.campaign_replications ?? 1" type="number" min="1" max="50" step="1" :disabled="disabled" @input="updateNumber(['campaign_replications'], $event)"></span>
          </label>
          <ul v-if="sectionIssues('basics').length" class="generator-issues"><li v-for="item in sectionIssues('basics')" :id="issueId(item)" :key="`${item.path}-${item.message}`"><button type="button" class="btn link generator-issue-link" @click="focusIssue(item)"><code>{{ item.path }}</code> {{ item.message }}</button></li></ul>
        </div>
      </details>

      <details :ref="(element) => setSectionDetails('global_behavior', element)" class="setting-group generator-section" tabindex="-1">
        <summary>
          <span>Global behavior</span><span class="tag" :class="stateTone('global_behavior')">{{ stateLabel('global_behavior') }}</span>
        </summary>
        <div class="generator-section-body">
          <!--
            The seven days are one setting, not seven: they are read across as a
            week-shaped curve, so they keep a compact row of their own rather
            than becoming seven option rows that hide the shape.
          -->
          <fieldset v-bind="fieldProps('/global_behavior/weekly_traffic_multipliers')" class="setting-block generator-fieldset" tabindex="-1">
            <legend>Weekly traffic multipliers</legend>
            <p class="caption">Relative traffic on each weekday, Monday to Sunday. 1 is an average day.</p>
            <div class="generator-week">
              <label v-for="(day, index) in ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']" :key="day">{{ day }}<input v-bind="fieldProps(`/global_behavior/weekly_traffic_multipliers/${index}`)" :value="modelValue.global_behavior?.weekly_traffic_multipliers?.[index]" type="number" min="0" step="0.01" :disabled="disabled" @input="updateNumber(['global_behavior', 'weekly_traffic_multipliers', index], $event)"></label>
            </div>
          </fieldset>
          <label class="setting-row">
            <span class="setting-label">Daily traffic trend<small>Steady growth or decline across the window. 0 holds traffic flat.</small></span>
            <span class="setting-control"><input v-bind="fieldProps('/global_behavior/daily_traffic_trend')" :value="modelValue.global_behavior?.daily_traffic_trend" type="number" step="0.01" :disabled="disabled" @input="updateNumber(['global_behavior', 'daily_traffic_trend'], $event)"></span>
          </label>
          <label v-for="field in NOISE_FIELDS" :key="field[0]" class="setting-row">
            <span class="setting-label">{{ field[1] }}<small>{{ field[2] }}</small></span>
            <span class="setting-control"><input v-bind="fieldProps(`/global_behavior/${field[0]}`)" :value="modelValue.global_behavior?.[field[0]]" type="number" min="0" step="0.01" :disabled="disabled" @input="updateNumber(['global_behavior', field[0]], $event)"></span>
          </label>
          <label v-for="field in PROBABILITY_FIELDS" :key="field[0]" class="setting-row">
            <span class="setting-label">{{ field[1] }}<small>{{ field[2] }}</small></span>
            <span class="setting-control"><input v-bind="fieldProps(`/global_behavior/${field[0]}`)" :value="modelValue.global_behavior?.[field[0]]" type="number" min="0" max="1" step="0.01" :disabled="disabled" @input="updateNumber(['global_behavior', field[0]], $event)"></span>
          </label>
          <ul v-if="sectionIssues('global_behavior').length" class="generator-issues"><li v-for="item in sectionIssues('global_behavior')" :id="issueId(item)" :key="`${item.path}-${item.message}`"><button type="button" class="btn link generator-issue-link" @click="focusIssue(item)"><code>{{ item.path }}</code> {{ item.message }}</button></li></ul>
        </div>
      </details>

      <details :ref="(element) => setSectionDetails('marketplace', element)" class="setting-group generator-section" tabindex="-1">
        <summary>
          <span>Marketplace</span><span class="tag" :class="stateTone('marketplace')">{{ stateLabel('marketplace') }}</span>
        </summary>
        <div class="generator-section-body">
          <div class="setting-block"><p class="caption">Exactly one marketplace is supported.</p></div>
          <template v-if="marketplace">
            <label class="setting-row" v-bind="fieldProps('/marketplaces/0')" tabindex="-1">
              <span class="setting-label">Marketplace code<small>Short code the marketplace is reported under.</small></span>
              <span class="setting-control"><input v-bind="fieldProps('/marketplaces/0/code')" :value="marketplace.code" type="text" :disabled="disabled" @input="updateText(['marketplaces', 0, 'code'], $event)"></span>
            </label>
            <label class="setting-row">
              <span class="setting-label">ISO currency code<small>Three letters, such as USD. Every amount is reported in it.</small></span>
              <span class="setting-control"><input v-bind="fieldProps('/marketplaces/0/currency_code')" :value="marketplace.currency_code" type="text" maxlength="3" :disabled="disabled" @input="updateText(['marketplaces', 0, 'currency_code'], $event)"></span>
            </label>
            <label class="setting-row">
              <span class="setting-label">Traffic multiplier<small>Scales all impressions in this marketplace. 1 leaves them as configured.</small></span>
              <span class="setting-control"><input v-bind="fieldProps('/marketplaces/0/traffic_multiplier')" :value="marketplace.traffic_multiplier" type="number" min="0" step="0.01" :disabled="disabled" @input="updateNumber(['marketplaces', 0, 'traffic_multiplier'], $event)"></span>
            </label>
            <label class="setting-row">
              <span class="setting-label">Price multiplier<small>Scales the base product price in this marketplace.</small></span>
              <span class="setting-control"><input v-bind="fieldProps('/marketplaces/0/price_multiplier')" :value="marketplace.price_multiplier" type="number" min="0" step="0.01" :disabled="disabled" @input="updateNumber(['marketplaces', 0, 'price_multiplier'], $event)"></span>
            </label>
            <template v-if="regional">
              <label class="setting-row">
                <span class="setting-label">Internet reach rate<small>Share of the population that can be reached online, from 0 to 1.</small></span>
                <span class="setting-control"><input v-bind="fieldProps('/marketplaces/0/internet_reach_rate')" :value="marketplace.internet_reach_rate" type="number" min="0" max="1" step="0.01" :disabled="disabled" @input="updateNumber(['marketplaces', 0, 'internet_reach_rate'], $event)"></span>
              </label>
              <label class="setting-row">
                <span class="setting-label">Target audience density<small>Share of reachable people who are in the target audience.</small></span>
                <span class="setting-control"><input v-bind="fieldProps('/marketplaces/0/target_audience_density')" :value="marketplace.target_audience_density" type="number" min="0" max="1" step="0.01" :disabled="disabled" @input="updateNumber(['marketplaces', 0, 'target_audience_density'], $event)"></span>
              </label>
              <label class="setting-row">
                <span class="setting-label">Economic willingness multiplier<small>How much local purchasing power raises or lowers conversion.</small></span>
                <span class="setting-control"><input v-bind="fieldProps('/marketplaces/0/economic_willingness_multiplier')" :value="marketplace.economic_willingness_multiplier" type="number" min="0" step="0.01" :disabled="disabled" @input="updateNumber(['marketplaces', 0, 'economic_willingness_multiplier'], $event)"></span>
              </label>
              <label class="setting-row">
                <span class="setting-label">Income inequality Gini<small>0 is an even income spread, 1 is the most uneven.</small></span>
                <span class="setting-control"><input v-bind="fieldProps('/marketplaces/0/income_inequality_gini')" :value="marketplace.income_inequality_gini" type="number" min="0" max="1" step="0.01" :disabled="disabled" @input="updateNumber(['marketplaces', 0, 'income_inequality_gini'], $event)"></span>
              </label>
            </template>
          </template>
          <div v-else class="setting-block rec-actions">
            <button v-bind="fieldProps('/marketplaces')" class="btn" type="button" :disabled="disabled" @click="ensureMarketplace">Add marketplace</button>
          </div>
          <ul v-if="sectionIssues('marketplace').length" class="generator-issues"><li v-for="item in sectionIssues('marketplace')" :id="issueId(item)" :key="`${item.path}-${item.message}`"><button type="button" class="btn link generator-issue-link" @click="focusIssue(item)"><code>{{ item.path }}</code> {{ item.message }}</button></li></ul>
        </div>
      </details>

      <details :ref="(element) => setSectionDetails('touchpoints', element)" class="setting-group generator-section" tabindex="-1">
        <summary>
          <span>Touchpoints</span><span class="tag" :class="stateTone('touchpoints')">{{ stateLabel('touchpoints') }}</span>
        </summary>
        <div class="generator-section-body">
          <div class="setting-block rec-actions"><button v-bind="fieldProps('/touchpoints')" class="btn" type="button" :disabled="disabled" @click="useNext(addTouchpoint(modelValue))">Add touchpoint</button></div>
          <!--
            A card's actions sit in their own left-aligned bar under the title
            rather than opposite it, so the buttons of every card start on the
            same edge no matter how long the title beside them is.
          -->
          <article v-for="(touchpoint, index) in touchpoints" v-bind="fieldProps(`/touchpoints/${index}`)" :key="index" class="setting-group generator-card" tabindex="-1">
            <header><h4>Touchpoint {{ index + 1 }}</h4></header>
            <div class="setting-block rec-actions"><button class="btn small" type="button" :disabled="disabled || index === 0" @click="move(['touchpoints'], index, -1)">Move up</button><button class="btn small" type="button" :disabled="disabled || index === touchpoints.length - 1" @click="move(['touchpoints'], index, 1)">Move down</button><button class="btn small" type="button" :disabled="disabled" @click="useNext(duplicateTouchpoint(modelValue, index))">Duplicate</button><button class="btn small danger" type="button" :disabled="disabled" @click="deleteCard(index)">Delete</button></div>
            <label class="setting-row">
              <span class="setting-label">Identifier<small>Unique name path scenarios use to reference this touchpoint.</small></span>
              <span class="setting-control"><input v-bind="fieldProps(`/touchpoints/${index}/identifier`)" :value="touchpoint.identifier" type="text" :disabled="disabled" @input="updateText(['touchpoints', index, 'identifier'], $event)"></span>
            </label>
            <label class="setting-row">
              <span class="setting-label">Ad product<small>The advertising product this touchpoint is bought as.</small></span>
              <span class="setting-control"><input v-bind="fieldProps(`/touchpoints/${index}/ad_product`)" :value="touchpoint.ad_product" type="text" :disabled="disabled" @input="updateText(['touchpoints', index, 'ad_product'], $event)"></span>
            </label>
            <label class="setting-row">
              <span class="setting-label">Ad type</span>
              <span class="setting-control"><input v-bind="fieldProps(`/touchpoints/${index}/ad_type`)" :value="touchpoint.ad_type ?? ''" type="text" :disabled="disabled" @input="updateText(['touchpoints', index, 'ad_type'], $event)"></span>
            </label>
            <label class="setting-row">
              <span class="setting-label">Creative type</span>
              <span class="setting-control"><input v-bind="fieldProps(`/touchpoints/${index}/creative_type`)" :value="touchpoint.creative_type ?? ''" type="text" :disabled="disabled" @input="updateText(['touchpoints', index, 'creative_type'], $event)"></span>
            </label>
            <label class="setting-row">
              <span class="setting-label">Inventory type</span>
              <span class="setting-control"><input v-bind="fieldProps(`/touchpoints/${index}/inventory_type`)" :value="touchpoint.inventory_type ?? ''" type="text" :disabled="disabled" @input="updateText(['touchpoints', index, 'inventory_type'], $event)"></span>
            </label>
            <label class="setting-row">
              <span class="setting-label">Placement</span>
              <span class="setting-control"><input v-bind="fieldProps(`/touchpoints/${index}/placement`)" :value="touchpoint.placement ?? ''" type="text" :disabled="disabled" @input="updateText(['touchpoints', index, 'placement'], $event)"></span>
            </label>
            <label class="setting-row">
              <span class="setting-label">Base impressions<small>Impressions this touchpoint serves on an average day.</small></span>
              <span class="setting-control"><input v-bind="fieldProps(`/touchpoints/${index}/base_impressions`)" :value="touchpoint.base_impressions" type="number" min="0" step="1" :disabled="disabled" @input="updateNumber(['touchpoints', index, 'base_impressions'], $event)"></span>
            </label>
            <label class="setting-row">
              <span class="setting-label">Click-through rate<small>Share of impressions that become clicks, from 0 to 1.</small></span>
              <span class="setting-control"><input v-bind="fieldProps(`/touchpoints/${index}/click_through_rate`)" :value="touchpoint.click_through_rate" type="number" min="0" max="1" step="0.01" :disabled="disabled" @input="updateNumber(['touchpoints', index, 'click_through_rate'], $event)"></span>
            </label>
            <label class="setting-row">
              <span class="setting-label">Platform conversion rate<small>Conversion rate the ad platform reports for this touchpoint.</small></span>
              <span class="setting-control"><input v-bind="fieldProps(`/touchpoints/${index}/platform_conversion_rate`)" :value="touchpoint.platform_conversion_rate" type="number" min="0" max="1" step="0.01" :disabled="disabled" @input="updateNumber(['touchpoints', index, 'platform_conversion_rate'], $event)"></span>
            </label>
            <label class="setting-row">
              <span class="setting-label">Cost per click<small>Billing basis. Setting this clears cost per thousand impressions.</small></span>
              <span class="setting-control"><input v-bind="fieldProps(`/touchpoints/${index}/cost_per_click`)" :value="touchpoint.cost_per_click ?? ''" type="number" min="0" step="0.01" :disabled="disabled" @input="setBilling(index, 'cost_per_click', $event)"></span>
            </label>
            <label class="setting-row">
              <span class="setting-label">Cost per thousand impressions<small>The other billing basis. Setting this clears cost per click.</small></span>
              <span class="setting-control"><input v-bind="fieldProps(`/touchpoints/${index}/cost_per_thousand_impressions`)" :value="touchpoint.cost_per_thousand_impressions ?? ''" type="number" min="0" step="0.01" :disabled="disabled" @input="setBilling(index, 'cost_per_thousand_impressions', $event)"></span>
            </label>
            <label class="setting-row">
              <span class="setting-label">Conversion log odds effect<small>How much exposure to this touchpoint raises the chance of converting.</small></span>
              <span class="setting-control"><input v-bind="fieldProps(`/touchpoints/${index}/conversion_log_odds_effect`)" :value="touchpoint.conversion_log_odds_effect" type="number" min="0" step="0.01" :disabled="disabled" @input="updateNumber(['touchpoints', index, 'conversion_log_odds_effect'], $event)"></span>
            </label>
          </article>
          <p v-if="blockedDeletion" class="notice bad setting-block">Cannot delete this touchpoint: path scenario “{{ blockedDeletion.pathIdentifier }}” references it.</p>
          <ul v-if="sectionIssues('touchpoints').length" class="generator-issues"><li v-for="item in sectionIssues('touchpoints')" :id="issueId(item)" :key="`${item.path}-${item.message}`"><button type="button" class="btn link generator-issue-link" @click="focusIssue(item)"><code>{{ item.path }}</code> {{ item.message }}</button></li></ul>
        </div>
      </details>

      <details :ref="setPathDetails" class="setting-group generator-section" tabindex="-1">
        <summary>
          <span>Path scenarios</span><span class="tag" :class="stateTone('path_scenarios')">{{ stateLabel('path_scenarios') }}</span>
        </summary>
        <div class="generator-section-body">
          <div class="setting-block rec-actions"><button v-bind="fieldProps('/path_scenarios')" class="btn" type="button" :disabled="disabled" @click="useNext(addPathScenario(modelValue))">Add path scenario</button></div>
          <article v-for="(scenario, index) in pathScenarios" v-bind="fieldProps(`/path_scenarios/${index}`)" :key="index" class="setting-group generator-card" tabindex="-1">
            <header><h4>Path scenario {{ index + 1 }}</h4></header>
            <div class="setting-block rec-actions"><button class="btn small" type="button" :disabled="disabled || index === 0" @click="move(['path_scenarios'], index, -1)">Move up</button><button class="btn small" type="button" :disabled="disabled || index === pathScenarios.length - 1" @click="move(['path_scenarios'], index, 1)">Move down</button><button class="btn small" type="button" :disabled="disabled" @click="useNext(duplicatePathScenario(modelValue, index))">Duplicate</button><button class="btn small danger" type="button" :disabled="disabled" @click="useNext(deletePathScenario(modelValue, index))">Delete</button></div>
            <label class="setting-row">
              <span class="setting-label">Identifier<small>Names this path in the generated data.</small></span>
              <span class="setting-control"><input v-bind="fieldProps(`/path_scenarios/${index}/identifier`)" :value="scenario.identifier" type="text" :disabled="disabled" @input="updateText(['path_scenarios', index, 'identifier'], $event)"></span>
            </label>
            <label class="setting-row">
              <span class="setting-label">Base users<small>How many users travel this path on an average day.</small></span>
              <span class="setting-control"><input v-bind="fieldProps(`/path_scenarios/${index}/base_users`)" :value="scenario.base_users" type="number" min="0" step="1" :disabled="disabled" @input="updateNumber(['path_scenarios', index, 'base_users'], $event)"></span>
            </label>
            <label class="setting-row">
              <span class="setting-label">Adjacent synergy log odds<small>Extra conversion lift when two referenced touchpoints are seen in sequence.</small></span>
              <span class="setting-control"><input v-bind="fieldProps(`/path_scenarios/${index}/adjacent_synergy_log_odds`)" :value="scenario.adjacent_synergy_log_odds" type="number" min="0" step="0.01" :disabled="disabled" @input="updateNumber(['path_scenarios', index, 'adjacent_synergy_log_odds'], $event)"></span>
            </label>
            <!--
              The reference list is ordered, so it is a list and not a row: the
              order the touchpoints are listed in is the order users see them.
            -->
            <fieldset class="setting-block generator-fieldset">
              <legend>Ordered touchpoint references</legend>
              <div class="rec-actions generator-reference-add"><select v-model="referenceSelections[index]" :disabled="disabled"><option disabled value="">Choose an existing touchpoint</option><option v-for="identifier in availableTouchpointChoices(scenario)" :key="identifier" :value="identifier">{{ identifier }}</option></select><button class="btn" type="button" :disabled="disabled || !referenceSelections[index]" @click="addReference(index)">Add reference</button></div>
              <ol v-bind="fieldProps(`/path_scenarios/${index}/touchpoint_identifiers`)" class="generator-references" tabindex="-1"><li v-for="(identifier, referenceIndex) in pathReferences(scenario)" :key="`${identifier}-${referenceIndex}`"><code>{{ identifier }}</code><div class="rec-actions"><button class="btn small" type="button" :disabled="disabled || referenceIndex === 0" @click="move(['path_scenarios', index, 'touchpoint_identifiers'], referenceIndex, -1)">Move up</button><button class="btn small" type="button" :disabled="disabled || referenceIndex === pathReferences(scenario).length - 1" @click="move(['path_scenarios', index, 'touchpoint_identifiers'], referenceIndex, 1)">Move down</button><button v-bind="fieldProps(`/path_scenarios/${index}/touchpoint_identifiers/${referenceIndex}`)" :ref="(element) => setReferenceButton(index, referenceIndex, element)" class="btn small danger" type="button" :disabled="disabled" @click="useNext(removePathReference(modelValue, index, referenceIndex))">Remove</button></div></li></ol>
            </fieldset>
          </article>
          <ul v-if="sectionIssues('path_scenarios').length" class="generator-issues"><li v-for="item in sectionIssues('path_scenarios')" :id="issueId(item)" :key="`${item.path}-${item.message}`"><button type="button" class="btn link generator-issue-link" @click="focusIssue(item)"><code>{{ item.path }}</code> {{ item.message }}</button></li></ul>
        </div>
      </details>

      <details v-if="regional" :ref="(element) => setSectionDetails('regional_behavior', element)" class="setting-group generator-section" tabindex="-1">
        <summary>
          <span>Regional behavior</span><span class="tag" :class="stateTone('regional_behavior')">{{ stateLabel('regional_behavior') }}</span>
        </summary>
        <div class="generator-section-body">
          <label class="setting-row">
            <span class="setting-label">Reference internet reach rate<small>The reach rate a marketplace is compared against, from 0 to 1.</small></span>
            <span class="setting-control"><input v-bind="fieldProps('/regional_behavior/reference_internet_reach_rate')" :value="modelValue.regional_behavior?.reference_internet_reach_rate" type="number" min="0" max="1" step="0.01" :disabled="disabled" @input="updateNumber(['regional_behavior', 'reference_internet_reach_rate'], $event)"></span>
          </label>
          <label class="setting-row">
            <span class="setting-label">Reference target audience density<small>The audience density a marketplace is compared against.</small></span>
            <span class="setting-control"><input v-bind="fieldProps('/regional_behavior/reference_target_audience_density')" :value="modelValue.regional_behavior?.reference_target_audience_density" type="number" min="0" max="1" step="0.01" :disabled="disabled" @input="updateNumber(['regional_behavior', 'reference_target_audience_density'], $event)"></span>
          </label>
          <label class="setting-row">
            <span class="setting-label">Reference income inequality Gini<small>The Gini value a marketplace is compared against.</small></span>
            <span class="setting-control"><input v-bind="fieldProps('/regional_behavior/reference_income_inequality_gini')" :value="modelValue.regional_behavior?.reference_income_inequality_gini" type="number" min="0" max="1" step="0.01" :disabled="disabled" @input="updateNumber(['regional_behavior', 'reference_income_inequality_gini'], $event)"></span>
          </label>
          <label class="setting-row">
            <span class="setting-label">Economic willingness log odds weight<small>How strongly purchasing power moves the chance of converting.</small></span>
            <span class="setting-control"><input v-bind="fieldProps('/regional_behavior/economic_willingness_log_odds_weight')" :value="modelValue.regional_behavior?.economic_willingness_log_odds_weight" type="number" min="0" step="0.01" :disabled="disabled" @input="updateNumber(['regional_behavior', 'economic_willingness_log_odds_weight'], $event)"></span>
          </label>
          <label class="setting-row">
            <span class="setting-label">Income inequality noise weight<small>How strongly unequal income widens the random spread of results.</small></span>
            <span class="setting-control"><input v-bind="fieldProps('/regional_behavior/income_inequality_noise_weight')" :value="modelValue.regional_behavior?.income_inequality_noise_weight" type="number" min="0" step="0.01" :disabled="disabled" @input="updateNumber(['regional_behavior', 'income_inequality_noise_weight'], $event)"></span>
          </label>
          <ul v-if="sectionIssues('regional_behavior').length" class="generator-issues"><li v-for="item in sectionIssues('regional_behavior')" :id="issueId(item)" :key="`${item.path}-${item.message}`"><button type="button" class="btn link generator-issue-link" @click="focusIssue(item)"><code>{{ item.path }}</code> {{ item.message }}</button></li></ul>
        </div>
      </details>
    </div>
  </section>
</template>
