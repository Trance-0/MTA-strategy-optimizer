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
const NOISE_FIELDS = [
  ["conversion_probability_daily_noise_standard_deviation", "Conversion probability daily noise"],
  ["performance_volume_noise_standard_deviation", "Performance volume noise"],
  ["path_audience_noise_standard_deviation", "Path audience noise"],
  ["performance_revenue_noise_standard_deviation", "Performance revenue noise"],
  ["path_revenue_noise_standard_deviation", "Path revenue noise"],
];
const PROBABILITY_FIELDS = [
  ["additional_unit_probability", "Additional unit probability"],
  ["repeat_purchase_probability", "Repeat purchase probability"],
];

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
  <section :ref="(element) => setSectionDetails('configuration', element)" class="generator-config-editor" aria-label="Data Generator configuration editor" tabindex="-1">
    <div class="generator-config-editor__tabs" aria-label="Editor mode">
      <button
        class="generator-config-editor__tab"
        :class="{ 'is-active': editorMode === 'guided' }"
        :aria-pressed="editorMode === 'guided'"
        type="button"
        :disabled="disabled"
        @click="selectMode('guided')"
      >Guided editor</button>
      <button
        class="generator-config-editor__tab"
        :class="{ 'is-active': editorMode === 'json' }"
        :aria-pressed="editorMode === 'json'"
        type="button"
        :disabled="disabled"
        @click="selectMode('json')"
      >JSON configuration</button>
    </div>

    <div v-if="editorMode === 'json'" class="generator-config-editor__json">
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
      <div class="generator-config-editor__actions">
        <button type="button" :disabled="disabled" @click="formatJson">Format JSON</button>
      </div>
      <p v-if="jsonError" id="generator-configuration-json-error" class="generator-config-editor__error">{{ jsonError }}</p>
    </div>

    <div v-else class="generator-config-editor__guided">
      <ul v-if="sectionIssues('configuration').length" class="generator-config-editor__issues">
        <li v-for="item in sectionIssues('configuration')" :id="issueId(item)" :key="`${item.path}-${item.message}`"><button type="button" class="generator-config-editor__issue-link" @click="focusIssue(item)"><code>{{ item.path }}</code> {{ item.message }}</button></li>
      </ul>
      <details :ref="(element) => setSectionDetails('basics', element)" class="generator-config-editor__section" tabindex="-1" open>
        <summary>
          <span>Run basics</span><span class="generator-config-editor__status" :class="`is-${sectionState('basics')}`">{{ stateLabel('basics') }}</span>
        </summary>
        <div class="generator-config-editor__body">
          <div class="generator-config-editor__grid">
            <label>Random seed<input v-bind="fieldProps('/seed')" :value="modelValue.seed" type="number" step="1" :disabled="disabled" @input="updateNumber(['seed'], $event)"></label>
            <label>Advertiser identifier<input v-bind="fieldProps('/advertiser_id')" :value="modelValue.advertiser_id" type="text" :disabled="disabled" @input="updateText(['advertiser_id'], $event)"></label>
            <label>Report start date<input v-bind="fieldProps('/report_start_date')" :value="modelValue.report_start_date" type="date" :disabled="disabled" @input="updateText(['report_start_date'], $event)"></label>
            <label>Report end date<input v-bind="fieldProps('/report_end_date')" :value="modelValue.report_end_date" type="date" :disabled="disabled" @input="updateText(['report_end_date'], $event)"></label>
            <label>Base product price<input v-bind="fieldProps('/base_product_price')" :value="modelValue.base_product_price" type="number" min="0" step="0.01" :disabled="disabled" @input="updateNumber(['base_product_price'], $event)"></label>
            <label>Baseline conversion log odds<input v-bind="fieldProps('/baseline_conversion_log_odds')" :value="modelValue.baseline_conversion_log_odds" type="number" step="0.01" :disabled="disabled" @input="updateNumber(['baseline_conversion_log_odds'], $event)"></label>
            <label>Campaign replications<input v-bind="fieldProps('/campaign_replications')" :value="modelValue.campaign_replications ?? 1" type="number" min="1" max="50" step="1" :disabled="disabled" @input="updateNumber(['campaign_replications'], $event)"></label>
          </div>
          <ul v-if="sectionIssues('basics').length" class="generator-config-editor__issues"><li v-for="item in sectionIssues('basics')" :id="issueId(item)" :key="`${item.path}-${item.message}`"><button type="button" class="generator-config-editor__issue-link" @click="focusIssue(item)"><code>{{ item.path }}</code> {{ item.message }}</button></li></ul>
        </div>
      </details>

      <details :ref="(element) => setSectionDetails('global_behavior', element)" class="generator-config-editor__section" tabindex="-1">
        <summary>
          <span>Global behavior</span><span class="generator-config-editor__status" :class="`is-${sectionState('global_behavior')}`">{{ stateLabel('global_behavior') }}</span>
        </summary>
        <div class="generator-config-editor__body">
          <fieldset v-bind="fieldProps('/global_behavior/weekly_traffic_multipliers')" class="generator-config-editor__fieldset" tabindex="-1"><legend>Weekly traffic multipliers (Monday to Sunday)</legend>
            <div class="generator-config-editor__week">
              <label v-for="(day, index) in ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']" :key="day">{{ day }}<input v-bind="fieldProps(`/global_behavior/weekly_traffic_multipliers/${index}`)" :value="modelValue.global_behavior?.weekly_traffic_multipliers?.[index]" type="number" min="0" step="0.01" :disabled="disabled" @input="updateNumber(['global_behavior', 'weekly_traffic_multipliers', index], $event)"></label>
            </div>
          </fieldset>
          <div class="generator-config-editor__grid">
            <label>Daily traffic trend<input v-bind="fieldProps('/global_behavior/daily_traffic_trend')" :value="modelValue.global_behavior?.daily_traffic_trend" type="number" step="0.01" :disabled="disabled" @input="updateNumber(['global_behavior', 'daily_traffic_trend'], $event)"></label>
            <label v-for="field in NOISE_FIELDS" :key="field[0]">{{ field[1] }}<input v-bind="fieldProps(`/global_behavior/${field[0]}`)" :value="modelValue.global_behavior?.[field[0]]" type="number" min="0" step="0.01" :disabled="disabled" @input="updateNumber(['global_behavior', field[0]], $event)"></label>
            <label v-for="field in PROBABILITY_FIELDS" :key="field[0]">{{ field[1] }}<input v-bind="fieldProps(`/global_behavior/${field[0]}`)" :value="modelValue.global_behavior?.[field[0]]" type="number" min="0" max="1" step="0.01" :disabled="disabled" @input="updateNumber(['global_behavior', field[0]], $event)"></label>
          </div>
          <ul v-if="sectionIssues('global_behavior').length" class="generator-config-editor__issues"><li v-for="item in sectionIssues('global_behavior')" :id="issueId(item)" :key="`${item.path}-${item.message}`"><button type="button" class="generator-config-editor__issue-link" @click="focusIssue(item)"><code>{{ item.path }}</code> {{ item.message }}</button></li></ul>
        </div>
      </details>

      <details :ref="(element) => setSectionDetails('marketplace', element)" class="generator-config-editor__section" tabindex="-1">
        <summary>
          <span>Marketplace</span><span class="generator-config-editor__status" :class="`is-${sectionState('marketplace')}`">{{ stateLabel('marketplace') }}</span>
        </summary>
        <div class="generator-config-editor__body">
          <p class="generator-config-editor__hint">Exactly one marketplace is supported.</p>
          <div v-if="marketplace" v-bind="fieldProps('/marketplaces/0')" class="generator-config-editor__grid" tabindex="-1">
            <label>Marketplace code<input v-bind="fieldProps('/marketplaces/0/code')" :value="marketplace.code" type="text" :disabled="disabled" @input="updateText(['marketplaces', 0, 'code'], $event)"></label>
            <label>ISO currency code<input v-bind="fieldProps('/marketplaces/0/currency_code')" :value="marketplace.currency_code" type="text" maxlength="3" :disabled="disabled" @input="updateText(['marketplaces', 0, 'currency_code'], $event)"></label>
            <label>Traffic multiplier<input v-bind="fieldProps('/marketplaces/0/traffic_multiplier')" :value="marketplace.traffic_multiplier" type="number" min="0" step="0.01" :disabled="disabled" @input="updateNumber(['marketplaces', 0, 'traffic_multiplier'], $event)"></label>
            <label>Price multiplier<input v-bind="fieldProps('/marketplaces/0/price_multiplier')" :value="marketplace.price_multiplier" type="number" min="0" step="0.01" :disabled="disabled" @input="updateNumber(['marketplaces', 0, 'price_multiplier'], $event)"></label>
            <template v-if="regional">
              <label>Internet reach rate<input v-bind="fieldProps('/marketplaces/0/internet_reach_rate')" :value="marketplace.internet_reach_rate" type="number" min="0" max="1" step="0.01" :disabled="disabled" @input="updateNumber(['marketplaces', 0, 'internet_reach_rate'], $event)"></label>
              <label>Target audience density<input v-bind="fieldProps('/marketplaces/0/target_audience_density')" :value="marketplace.target_audience_density" type="number" min="0" max="1" step="0.01" :disabled="disabled" @input="updateNumber(['marketplaces', 0, 'target_audience_density'], $event)"></label>
              <label>Economic willingness multiplier<input v-bind="fieldProps('/marketplaces/0/economic_willingness_multiplier')" :value="marketplace.economic_willingness_multiplier" type="number" min="0" step="0.01" :disabled="disabled" @input="updateNumber(['marketplaces', 0, 'economic_willingness_multiplier'], $event)"></label>
              <label>Income inequality Gini<input v-bind="fieldProps('/marketplaces/0/income_inequality_gini')" :value="marketplace.income_inequality_gini" type="number" min="0" max="1" step="0.01" :disabled="disabled" @input="updateNumber(['marketplaces', 0, 'income_inequality_gini'], $event)"></label>
            </template>
          </div>
          <button v-else v-bind="fieldProps('/marketplaces')" type="button" :disabled="disabled" @click="ensureMarketplace">Add marketplace</button>
          <ul v-if="sectionIssues('marketplace').length" class="generator-config-editor__issues"><li v-for="item in sectionIssues('marketplace')" :id="issueId(item)" :key="`${item.path}-${item.message}`"><button type="button" class="generator-config-editor__issue-link" @click="focusIssue(item)"><code>{{ item.path }}</code> {{ item.message }}</button></li></ul>
        </div>
      </details>

      <details :ref="(element) => setSectionDetails('touchpoints', element)" class="generator-config-editor__section" tabindex="-1">
        <summary>
          <span>Touchpoints</span><span class="generator-config-editor__status" :class="`is-${sectionState('touchpoints')}`">{{ stateLabel('touchpoints') }}</span>
        </summary>
        <div class="generator-config-editor__body">
          <div class="generator-config-editor__actions"><button v-bind="fieldProps('/touchpoints')" type="button" :disabled="disabled" @click="useNext(addTouchpoint(modelValue))">Add touchpoint</button></div>
          <article v-for="(touchpoint, index) in touchpoints" v-bind="fieldProps(`/touchpoints/${index}`)" :key="index" class="generator-config-editor__card" tabindex="-1">
            <header><h4>Touchpoint {{ index + 1 }}</h4><div class="generator-config-editor__actions"><button type="button" :disabled="disabled || index === 0" @click="move(['touchpoints'], index, -1)">Move up</button><button type="button" :disabled="disabled || index === touchpoints.length - 1" @click="move(['touchpoints'], index, 1)">Move down</button><button type="button" :disabled="disabled" @click="useNext(duplicateTouchpoint(modelValue, index))">Duplicate</button><button type="button" :disabled="disabled" @click="deleteCard(index)">Delete</button></div></header>
            <div class="generator-config-editor__grid">
              <label>Identifier<input v-bind="fieldProps(`/touchpoints/${index}/identifier`)" :value="touchpoint.identifier" type="text" :disabled="disabled" @input="updateText(['touchpoints', index, 'identifier'], $event)"></label>
              <label>Ad product<input v-bind="fieldProps(`/touchpoints/${index}/ad_product`)" :value="touchpoint.ad_product" type="text" :disabled="disabled" @input="updateText(['touchpoints', index, 'ad_product'], $event)"></label>
              <label>Ad type<input v-bind="fieldProps(`/touchpoints/${index}/ad_type`)" :value="touchpoint.ad_type ?? ''" type="text" :disabled="disabled" @input="updateText(['touchpoints', index, 'ad_type'], $event)"></label>
              <label>Creative type<input v-bind="fieldProps(`/touchpoints/${index}/creative_type`)" :value="touchpoint.creative_type ?? ''" type="text" :disabled="disabled" @input="updateText(['touchpoints', index, 'creative_type'], $event)"></label>
              <label>Inventory type<input v-bind="fieldProps(`/touchpoints/${index}/inventory_type`)" :value="touchpoint.inventory_type ?? ''" type="text" :disabled="disabled" @input="updateText(['touchpoints', index, 'inventory_type'], $event)"></label>
              <label>Placement<input v-bind="fieldProps(`/touchpoints/${index}/placement`)" :value="touchpoint.placement ?? ''" type="text" :disabled="disabled" @input="updateText(['touchpoints', index, 'placement'], $event)"></label>
              <label>Base impressions<input v-bind="fieldProps(`/touchpoints/${index}/base_impressions`)" :value="touchpoint.base_impressions" type="number" min="0" step="1" :disabled="disabled" @input="updateNumber(['touchpoints', index, 'base_impressions'], $event)"></label>
              <label>Click-through rate<input v-bind="fieldProps(`/touchpoints/${index}/click_through_rate`)" :value="touchpoint.click_through_rate" type="number" min="0" max="1" step="0.01" :disabled="disabled" @input="updateNumber(['touchpoints', index, 'click_through_rate'], $event)"></label>
              <label>Platform conversion rate<input v-bind="fieldProps(`/touchpoints/${index}/platform_conversion_rate`)" :value="touchpoint.platform_conversion_rate" type="number" min="0" max="1" step="0.01" :disabled="disabled" @input="updateNumber(['touchpoints', index, 'platform_conversion_rate'], $event)"></label>
              <label>Cost per click<input v-bind="fieldProps(`/touchpoints/${index}/cost_per_click`)" :value="touchpoint.cost_per_click ?? ''" type="number" min="0" step="0.01" :disabled="disabled" @input="setBilling(index, 'cost_per_click', $event)"></label>
              <label>Cost per thousand impressions<input v-bind="fieldProps(`/touchpoints/${index}/cost_per_thousand_impressions`)" :value="touchpoint.cost_per_thousand_impressions ?? ''" type="number" min="0" step="0.01" :disabled="disabled" @input="setBilling(index, 'cost_per_thousand_impressions', $event)"></label>
              <label>Conversion log odds effect<input v-bind="fieldProps(`/touchpoints/${index}/conversion_log_odds_effect`)" :value="touchpoint.conversion_log_odds_effect" type="number" min="0" step="0.01" :disabled="disabled" @input="updateNumber(['touchpoints', index, 'conversion_log_odds_effect'], $event)"></label>
            </div>
          </article>
          <p v-if="blockedDeletion" class="generator-config-editor__error">Cannot delete this touchpoint: path scenario “{{ blockedDeletion.pathIdentifier }}” references it.</p>
          <ul v-if="sectionIssues('touchpoints').length" class="generator-config-editor__issues"><li v-for="item in sectionIssues('touchpoints')" :id="issueId(item)" :key="`${item.path}-${item.message}`"><button type="button" class="generator-config-editor__issue-link" @click="focusIssue(item)"><code>{{ item.path }}</code> {{ item.message }}</button></li></ul>
        </div>
      </details>

      <details :ref="setPathDetails" class="generator-config-editor__section" tabindex="-1">
        <summary>
          <span>Path scenarios</span><span class="generator-config-editor__status" :class="`is-${sectionState('path_scenarios')}`">{{ stateLabel('path_scenarios') }}</span>
        </summary>
        <div class="generator-config-editor__body">
          <div class="generator-config-editor__actions"><button v-bind="fieldProps('/path_scenarios')" type="button" :disabled="disabled" @click="useNext(addPathScenario(modelValue))">Add path scenario</button></div>
          <article v-for="(scenario, index) in pathScenarios" v-bind="fieldProps(`/path_scenarios/${index}`)" :key="index" class="generator-config-editor__card" tabindex="-1">
            <header><h4>Path scenario {{ index + 1 }}</h4><div class="generator-config-editor__actions"><button type="button" :disabled="disabled || index === 0" @click="move(['path_scenarios'], index, -1)">Move up</button><button type="button" :disabled="disabled || index === pathScenarios.length - 1" @click="move(['path_scenarios'], index, 1)">Move down</button><button type="button" :disabled="disabled" @click="useNext(duplicatePathScenario(modelValue, index))">Duplicate</button><button type="button" :disabled="disabled" @click="useNext(deletePathScenario(modelValue, index))">Delete</button></div></header>
            <div class="generator-config-editor__grid">
              <label>Identifier<input v-bind="fieldProps(`/path_scenarios/${index}/identifier`)" :value="scenario.identifier" type="text" :disabled="disabled" @input="updateText(['path_scenarios', index, 'identifier'], $event)"></label>
              <label>Base users<input v-bind="fieldProps(`/path_scenarios/${index}/base_users`)" :value="scenario.base_users" type="number" min="0" step="1" :disabled="disabled" @input="updateNumber(['path_scenarios', index, 'base_users'], $event)"></label>
              <label>Adjacent synergy log odds<input v-bind="fieldProps(`/path_scenarios/${index}/adjacent_synergy_log_odds`)" :value="scenario.adjacent_synergy_log_odds" type="number" min="0" step="0.01" :disabled="disabled" @input="updateNumber(['path_scenarios', index, 'adjacent_synergy_log_odds'], $event)"></label>
            </div>
            <fieldset class="generator-config-editor__fieldset"><legend>Ordered touchpoint references</legend>
              <div class="generator-config-editor__reference-add"><select v-model="referenceSelections[index]" :disabled="disabled"><option disabled value="">Choose an existing touchpoint</option><option v-for="identifier in availableTouchpointChoices(scenario)" :key="identifier" :value="identifier">{{ identifier }}</option></select><button type="button" :disabled="disabled || !referenceSelections[index]" @click="addReference(index)">Add reference</button></div>
              <ol v-bind="fieldProps(`/path_scenarios/${index}/touchpoint_identifiers`)" class="generator-config-editor__references" tabindex="-1"><li v-for="(identifier, referenceIndex) in pathReferences(scenario)" :key="`${identifier}-${referenceIndex}`"><code>{{ identifier }}</code><div class="generator-config-editor__actions"><button type="button" :disabled="disabled || referenceIndex === 0" @click="move(['path_scenarios', index, 'touchpoint_identifiers'], referenceIndex, -1)">Move up</button><button type="button" :disabled="disabled || referenceIndex === pathReferences(scenario).length - 1" @click="move(['path_scenarios', index, 'touchpoint_identifiers'], referenceIndex, 1)">Move down</button><button v-bind="fieldProps(`/path_scenarios/${index}/touchpoint_identifiers/${referenceIndex}`)" :ref="(element) => setReferenceButton(index, referenceIndex, element)" type="button" :disabled="disabled" @click="useNext(removePathReference(modelValue, index, referenceIndex))">Remove</button></div></li></ol>
            </fieldset>
          </article>
          <ul v-if="sectionIssues('path_scenarios').length" class="generator-config-editor__issues"><li v-for="item in sectionIssues('path_scenarios')" :id="issueId(item)" :key="`${item.path}-${item.message}`"><button type="button" class="generator-config-editor__issue-link" @click="focusIssue(item)"><code>{{ item.path }}</code> {{ item.message }}</button></li></ul>
        </div>
      </details>

      <details v-if="regional" :ref="(element) => setSectionDetails('regional_behavior', element)" class="generator-config-editor__section" tabindex="-1">
        <summary>
          <span>Regional behavior</span><span class="generator-config-editor__status" :class="`is-${sectionState('regional_behavior')}`">{{ stateLabel('regional_behavior') }}</span>
        </summary>
        <div class="generator-config-editor__body">
          <div class="generator-config-editor__grid">
            <label>Reference internet reach rate<input v-bind="fieldProps('/regional_behavior/reference_internet_reach_rate')" :value="modelValue.regional_behavior?.reference_internet_reach_rate" type="number" min="0" max="1" step="0.01" :disabled="disabled" @input="updateNumber(['regional_behavior', 'reference_internet_reach_rate'], $event)"></label>
            <label>Reference target audience density<input v-bind="fieldProps('/regional_behavior/reference_target_audience_density')" :value="modelValue.regional_behavior?.reference_target_audience_density" type="number" min="0" max="1" step="0.01" :disabled="disabled" @input="updateNumber(['regional_behavior', 'reference_target_audience_density'], $event)"></label>
            <label>Reference income inequality Gini<input v-bind="fieldProps('/regional_behavior/reference_income_inequality_gini')" :value="modelValue.regional_behavior?.reference_income_inequality_gini" type="number" min="0" max="1" step="0.01" :disabled="disabled" @input="updateNumber(['regional_behavior', 'reference_income_inequality_gini'], $event)"></label>
            <label>Economic willingness log odds weight<input v-bind="fieldProps('/regional_behavior/economic_willingness_log_odds_weight')" :value="modelValue.regional_behavior?.economic_willingness_log_odds_weight" type="number" min="0" step="0.01" :disabled="disabled" @input="updateNumber(['regional_behavior', 'economic_willingness_log_odds_weight'], $event)"></label>
            <label>Income inequality noise weight<input v-bind="fieldProps('/regional_behavior/income_inequality_noise_weight')" :value="modelValue.regional_behavior?.income_inequality_noise_weight" type="number" min="0" step="0.01" :disabled="disabled" @input="updateNumber(['regional_behavior', 'income_inequality_noise_weight'], $event)"></label>
          </div>
          <ul v-if="sectionIssues('regional_behavior').length" class="generator-config-editor__issues"><li v-for="item in sectionIssues('regional_behavior')" :id="issueId(item)" :key="`${item.path}-${item.message}`"><button type="button" class="generator-config-editor__issue-link" @click="focusIssue(item)"><code>{{ item.path }}</code> {{ item.message }}</button></li></ul>
        </div>
      </details>
    </div>
  </section>
</template>

<style scoped>
.generator-config-editor { display: grid; gap: 1rem; color: var(--ink, #1f2937); }
.generator-config-editor__tabs, .generator-config-editor__actions, .generator-config-editor__reference-add { display: flex; flex-wrap: wrap; gap: .5rem; align-items: center; }
.generator-config-editor__tab, .generator-config-editor button { border: 1px solid var(--line, #cbd5e1); border-radius: .35rem; background: var(--panel, #fff); color: inherit; cursor: pointer; padding: .45rem .7rem; }
.generator-config-editor__tab.is-active { border-color: var(--accent, #2456a6); box-shadow: inset 0 -2px var(--accent, #2456a6); font-weight: 700; }
.generator-config-editor:focus-visible, .generator-config-editor button:focus-visible, .generator-config-editor input:focus-visible, .generator-config-editor select:focus-visible, .generator-config-editor textarea:focus-visible, .generator-config-editor__section:focus-visible, .generator-config-editor__fieldset:focus-visible, .generator-config-editor__card:focus-visible { outline: 3px solid color-mix(in srgb, var(--accent, #2456a6) 45%, transparent); outline-offset: 2px; }
.generator-config-editor button:disabled, .generator-config-editor input:disabled, .generator-config-editor select:disabled, .generator-config-editor textarea:disabled { cursor: not-allowed; opacity: .6; }
.generator-config-editor__section { border: 1px solid var(--line, #cbd5e1); border-radius: .5rem; background: var(--panel, #fff); }
.generator-config-editor__section + .generator-config-editor__section { margin-top: .6rem; }
.generator-config-editor__section summary { align-items: center; cursor: pointer; display: flex; justify-content: space-between; gap: 1rem; padding: .8rem 1rem; font-weight: 700; }
.generator-config-editor__body { border-top: 1px solid var(--line, #cbd5e1); padding: 1rem; }
.generator-config-editor__grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: .75rem; }
.generator-config-editor label { display: grid; gap: .3rem; font-size: .9rem; font-weight: 600; }
.generator-config-editor input, .generator-config-editor select, .generator-config-editor textarea { box-sizing: border-box; border: 1px solid var(--line, #cbd5e1); border-radius: .3rem; background: var(--panel, #fff); color: inherit; font: inherit; min-width: 0; padding: .45rem; width: 100%; }
.generator-config-editor textarea { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; line-height: 1.45; resize: vertical; }
.generator-config-editor__status { border-radius: 99px; font-size: .75rem; font-weight: 700; padding: .2rem .5rem; }
.generator-config-editor__status.is-complete { background: #dcfce7; color: #166534; }
.generator-config-editor__status.is-incomplete { background: #fef3c7; color: #92400e; }
.generator-config-editor__status.is-error { background: #fee2e2; color: #991b1b; }
.generator-config-editor__card { border: 1px solid var(--line, #cbd5e1); border-radius: .4rem; margin-top: .75rem; padding: .8rem; }
.generator-config-editor__card header { align-items: center; display: flex; gap: .75rem; justify-content: space-between; margin-bottom: .75rem; }
.generator-config-editor__card h4 { margin: 0; }
.generator-config-editor__fieldset { border: 1px solid var(--line, #cbd5e1); border-radius: .35rem; margin: .8rem 0 0; padding: .8rem; }
.generator-config-editor__week { display: grid; grid-template-columns: repeat(7, minmax(0, 1fr)); gap: .4rem; }
.generator-config-editor__references { display: grid; gap: .5rem; margin: .75rem 0 0; padding-left: 1.5rem; }
.generator-config-editor__references li { align-items: center; display: flex; flex-wrap: wrap; gap: .6rem; justify-content: space-between; }
.generator-config-editor__issues, .generator-config-editor__error { color: #991b1b; margin: .8rem 0 0; }
.generator-config-editor__issue-link { border: 0 !important; color: inherit !important; padding: .15rem 0 !important; text-align: left; }
.generator-config-editor__issue-link code { margin-right: .35rem; }
.generator-config-editor__hint { color: var(--muted, #475569); margin-top: 0; }
@media (max-width: 720px) { .generator-config-editor__grid { grid-template-columns: 1fr; } .generator-config-editor__week { grid-template-columns: repeat(2, minmax(0, 1fr)); } .generator-config-editor__card header { align-items: flex-start; flex-direction: column; } }
</style>
