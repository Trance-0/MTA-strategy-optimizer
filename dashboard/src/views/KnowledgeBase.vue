<script setup>
/**
 * Knowledge Base: the vocabulary and rules the numbers obey.
 *
 * The reference prototype's Knowledge Base holds an ontology. This project has
 * a real one -- the five-segment touchpoint key, the three outcomes, the
 * capacity rules, and the reliability contract -- so the view is populated from
 * the data and configuration actually in use rather than from prose. Every
 * entry here is read from the current source, so it cannot drift from what the
 * charts show.
 */
import { computed, ref } from "vue";

import DataTable from "../components/DataTable.vue";
import KeyValuePanel from "../components/KeyValuePanel.vue";
import {
  OUTCOME_LABELS,
  OUTCOME_SHARE_COLUMNS,
  OUTCOME_VALUE_COLUMNS,
  currencySymbol,
  distinct,
  pretty,
  shortTouchpoint,
} from "../lib/common.js";
import { useDashboard } from "../lib/useDashboard.js";
import { money } from "../theme.js";

const { data } = useDashboard();

const tab = ref("vocabulary");
const TABS = [
  { key: "vocabulary", label: "Touchpoint vocabulary" },
  { key: "rules", label: "Rules" },
  { key: "entities", label: "Entities" },
  { key: "sources", label: "Data sources" },
];

/**
 * What each segment of the touchpoint key means. The values are read from the
 * data; these are the definitions that give them meaning.
 */
const SEGMENT_NOTES = {
  ad_product: "Which Amazon ad product served the impression or click.",
  format: "The ad or inventory type. UNSPECIFIED when the product has none.",
  placement: "Where it appeared. UNSPECIFIED for products without placement.",
  creative: "The creative type. UNSPECIFIED when not reported.",
  interaction_type: "IMPRESSION or CLICK. Decides which cost type applies.",
};

const attribution = computed(() => data.value.attributionResults);

const segments = computed(() =>
  Object.entries(SEGMENT_NOTES).map(([segment, meaning]) => {
    const values = distinct(attribution.value, segment);
    return {
      segment: pretty(segment),
      meaning,
      distinct: values.length,
      values: values.join(", "),
    };
  }),
);

const segmentColumns = [
  { key: "segment", label: "Segment" },
  { key: "meaning", label: "Meaning", width: "34%" },
  { key: "distinct", label: "Values", format: "number" },
  { key: "values", label: "Observed", width: "34%" },
];

const touchpoints = computed(() =>
  distinct(attribution.value, "touchpoint").map((key) => ({
    touchpoint: key,
    reads_as: shortTouchpoint(key),
  })),
);

const touchpointColumns = [
  { key: "touchpoint", label: "Key", width: "56%" },
  { key: "reads_as", label: "Reads as" },
];

const outcomeRows = computed(() =>
  Object.entries(OUTCOME_LABELS).map(([key, label]) => ({
    outcome: label,
    key,
    share_column: OUTCOME_SHARE_COLUMNS[key],
    attributed_column: OUTCOME_VALUE_COLUMNS[key],
  })),
);

const outcomeColumns = [
  { key: "outcome", label: "Outcome" },
  { key: "key", label: "Key" },
  { key: "share_column", label: "Share column" },
  { key: "attributed_column", label: "Attributed column" },
];

const request = computed(() => data.value.strategyRequest ?? {});
const group = computed(() => request.value.campaign_group ?? {});
const pool = computed(() => data.value.candidatePool ?? {});

const capacityRules = computed(() => {
  const rules = request.value.capacity_rules ?? {};
  return Object.entries(rules).map(([adProduct, values]) => ({
    ad_product: adProduct,
    ...values,
  }));
});

const capacityColumns = computed(() => {
  const first = capacityRules.value[0];
  if (!first) return [];
  return Object.keys(first).map((key) => ({
    key,
    label: pretty(key),
    format: key === "ad_product" ? undefined : "number",
  }));
});

const groupRows = computed(() => [
  { label: "Identifier", value: group.value.campaign_group_id || "--" },
  { label: "Name", value: group.value.group_name || "--" },
  { label: "Platform", value: group.value.platform || "--" },
  { label: "Marketplace", value: group.value.marketplace || "--" },
  { label: "Advertiser", value: group.value.advertiser_id || "--" },
  {
    label: "Total daily budget",
    value: money(
      group.value.total_daily_budget ?? 0,
      currencySymbol(group.value.currency ?? "USD"),
    ),
  },
]);

const campaignColumns = [
  { key: "campaign_id", label: "Campaign" },
  { key: "campaign_name", label: "Name", width: "30%" },
  { key: "ad_product", label: "Ad product" },
  { key: "status", label: "Status" },
];

const candidateCounts = computed(() => pool.value.campaign_candidate_counts ?? []);

const candidateColumns = computed(() => {
  const first = candidateCounts.value[0];
  if (!first) return [];
  return Object.keys(first).map((key) => ({
    key,
    label: pretty(key),
    format: key === "campaign_id" ? undefined : "number",
  }));
});

const sourceRows = computed(() => [
  { label: "DATABASE", value: data.value.mode === "database" ? "true" : "false" },
  { label: "Reading from", value: data.value.source || "--" },
]);

const ARTIFACTS = [
  {
    artifact: "amazon_ads_report_sample.csv",
    layer: "History",
    provides: "Daily spend, impressions, clicks, and reported sales",
  },
  {
    artifact: "amc_mta_path_report_raw_sample.csv",
    layer: "History",
    provides: "Aggregated conversion paths",
  },
  {
    artifact: "amc_touchpoint_entity_aggregate_sample.csv",
    layer: "History",
    provides: "Touchpoint to Campaign and Ad Group bridge",
  },
  {
    artifact: "amc_markov_attribution_results.csv",
    layer: "Model output",
    provides: "Markov shares, attributed totals, efficiency",
  },
  {
    artifact: "amc_shapley_attribution_results.csv",
    layer: "Model output",
    provides: "Shapley shares, attributed totals, efficiency",
  },
  {
    artifact: "amc_mta_model_comparison_touchpoints.csv",
    layer: "Model output",
    provides: "Per-touchpoint gaps and reliability flags",
  },
  {
    artifact: "amc_mta_model_comparison_summary.csv",
    layer: "Model output",
    provides: "Per-outcome diagnostics and verdict",
  },
  {
    artifact: "amc_mta_recommended_attribution.csv",
    layer: "Model output",
    provides: "The governed value per touchpoint",
  },
  {
    artifact: "strategy_request.json",
    layer: "Entity",
    provides: "Campaign Group, Campaigns, weights, capacity rules",
  },
  {
    artifact: "candidate_pool.json",
    layer: "Entity",
    provides: "Eligible targeting object counts",
  },
  {
    artifact: "initial_budget_recommendation.json",
    layer: "Strategy",
    provides: "Campaign budgets and Ad Group slots",
  },
];

const artifactColumns = [
  { key: "artifact", label: "Artifact", width: "30%" },
  { key: "layer", label: "Layer" },
  { key: "provides", label: "Provides", width: "44%" },
];
</script>

<template>
  <section class="page-grid">
    <p class="caption">
      The vocabulary and rules behind every number in this dashboard, read from
      the data in use.
    </p>

    <div class="tabs" role="tablist">
      <button
        v-for="entry in TABS"
        :key="entry.key"
        class="tab"
        role="tab"
        :aria-selected="tab === entry.key"
        :class="{ active: tab === entry.key }"
        @click="tab = entry.key"
      >
        {{ entry.label }}
      </button>
    </div>

    <!-- Touchpoint vocabulary -->
    <template v-if="tab === 'vocabulary'">
      <article class="card">
        <div class="card-head"><h2>The five-segment touchpoint key</h2></div>
        <div class="card-body">
          <div class="panel">
            <code class="key-formula">
              AD_PRODUCT : FORMAT : PLACEMENT : CREATIVE : INTERACTION_TYPE
            </code>
            <p class="caption">
              One key identifies one kind of interaction. Every attributed value,
              every spend row, and every path step is expressed in these keys, so
              attribution and spend can be compared without a join key of their
              own.
            </p>
          </div>
          <DataTable :columns="segmentColumns" :rows="segments" />
        </div>
      </article>

      <article class="card">
        <div class="card-head">
          <h2>Touchpoints in the current window</h2>
          <span class="sub">{{ touchpoints.length }} distinct keys</span>
        </div>
        <div class="card-body">
          <DataTable :columns="touchpointColumns" :rows="touchpoints" />
        </div>
      </article>
    </template>

    <!-- Rules -->
    <template v-else-if="tab === 'rules'">
      <article class="card">
        <div class="card-head"><h2>Reliability contract</h2></div>
        <div class="card-body">
          <div class="panel">
            <div class="kv">
              <span>calculation_valid</span>
              <span>The arithmetic held: shares are finite and sum to one.</span>
            </div>
            <div class="kv">
              <span>data_support_sufficient</span>
              <span>Enough observed journeys to support the estimate.</span>
            </div>
            <div class="kv">
              <span>models_consistent</span>
              <span>Markov and Shapley agree within tolerance.</span>
            </div>
            <div class="kv">
              <span>Verdict</span>
              <span><b>AND of all three.</b> One false flag means UNRELIABLE.</span>
            </div>
          </div>
          <p class="caption">
            Diagnostics — total variation distance, Spearman correlation, Top-K
            overlap — inform the reader but never change the verdict. An
            UNRELIABLE row carries an interval instead of a point value and
            grants no budgeting authority.
          </p>
        </div>
      </article>

      <article class="card">
        <div class="card-head"><h2>Outcomes</h2></div>
        <div class="card-body">
          <DataTable :columns="outcomeColumns" :rows="outcomeRows" />
          <p class="caption">
            Every outcome is attributed independently. A touchpoint can lead on
            revenue and trail on converted users; neither is derived from the
            other.
          </p>
        </div>
      </article>

      <article class="card">
        <div class="card-head"><h2>Capacity rules</h2></div>
        <div class="card-body">
          <DataTable
            v-if="capacityRules.length"
            :columns="capacityColumns"
            :rows="capacityRules"
          />
          <div v-else class="notice">
            Capacity rules are pipeline configuration rather than observed data,
            so they are not stored in the database. Switch <code>DATABASE</code>
            to <code>false</code> in <code>.env</code> to read them from
            <code>strategy_request.json</code>.
          </div>
          <p v-if="capacityRules.length" class="caption">
            These caps decide how many Ad Groups a Campaign can support, which in
            turn sets its minimum required daily budget.
          </p>
        </div>
      </article>
    </template>

    <!-- Entities -->
    <template v-else-if="tab === 'entities'">
      <article class="card">
        <div class="card-head"><h2>Advertising hierarchy</h2></div>
        <div class="card-body">
          <KeyValuePanel title="Campaign Group" :rows="groupRows" />
          <DataTable
            :columns="campaignColumns"
            :rows="request.campaigns ?? []"
            empty="No Campaigns in the strategy request."
          />
          <p class="caption">
            A Campaign carries exactly one ad product, which is why the ad
            product is the level at which attribution evidence is bridged into
            budget shares.
          </p>
        </div>
      </article>

      <article class="card">
        <div class="card-head"><h2>Eligible targeting candidates</h2></div>
        <div class="card-body">
          <DataTable
            :columns="candidateColumns"
            :rows="candidateCounts"
            empty="No candidate counts available."
          />
          <p v-if="candidateCounts.length" class="caption">
            Usage policy: <b>{{ pool.candidate_usage_policy || "--" }}</b>. These
            counts drive the capacity calculation that decides how many new Ad
            Groups each Campaign can support.
          </p>
        </div>
      </article>
    </template>

    <!-- Data sources -->
    <template v-else>
      <article class="card">
        <div class="card-head"><h2>Active source</h2></div>
        <div class="card-body">
          <KeyValuePanel title="Mode" :rows="sourceRows" />
        </div>
      </article>

      <article class="card">
        <div class="card-head"><h2>Artifacts</h2></div>
        <div class="card-body">
          <DataTable :columns="artifactColumns" :rows="ARTIFACTS" />
          <p class="caption">
            The dashboard reads these artifacts and never recomputes their
            values, so it cannot become a second, divergent implementation of the
            pipeline.
          </p>
        </div>
      </article>
    </template>
  </section>
</template>
