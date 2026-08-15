<script setup>
/**
 * Optimization Log: the run record and its provenance.
 *
 * The reference prototype shows an audit trail of optimisation actions. No
 * module in this project writes such a trail, so rather than invent
 * placeholder entries this view shows the real record that does exist: which
 * attribution run produced the evidence, which files it hashed, and which
 * budget run consumed it. That is the same question -- what happened, and can
 * it be reproduced -- answered from data instead of from a mock.
 */
import { computed, ref } from "vue";

import DataTable from "../components/DataTable.vue";
import KeyValuePanel from "../components/KeyValuePanel.vue";
import { OUTCOME_LABELS, distinct, statusTone } from "../lib/common.js";
import { useDashboard } from "../lib/useDashboard.js";

const { data } = useDashboard();

const budget = computed(() => data.value.budgetRecommendation ?? {});
const request = computed(() => data.value.strategyRequest ?? {});
const summary = computed(() => data.value.comparisonSummary);
const comparison = computed(() => data.value.comparisonTouchpoints);

const snapshot = computed(
  () => budget.value.mta_source_snapshot ?? request.value.mta_source ?? {},
);

const reportWindow = computed(() => {
  const first = summary.value[0];
  if (first?.report_start_date) {
    return { start: first.report_start_date, end: first.report_end_date };
  }
  return {
    start: snapshot.value.report_start_date ?? "--",
    end: snapshot.value.report_end_date ?? "--",
  };
});

const attributionRows = computed(() => [
  { label: "Batch", value: budget.value.mta_batch_id || "--" },
  { label: "Window", value: `${reportWindow.value.start} to ${reportWindow.value.end}` },
  { label: "Marketplace", value: snapshot.value.marketplace || "--" },
  { label: "Advertiser", value: snapshot.value.advertiser_id || "--" },
  {
    label: "Touchpoint gap",
    value:
      summary.value[0]?.max_touchpoint_gap_days != null
        ? `${summary.value[0].max_touchpoint_gap_days} days`
        : "--",
  },
]);

const budgetRows = computed(() => [
  { label: "Schema", value: budget.value.schema_version || "--" },
  { label: "Campaign Group", value: budget.value.campaign_group_id || "--" },
  { label: "Candidate pool", value: budget.value.candidate_pool_id || "--" },
  { label: "Type", value: budget.value.recommendation_type || "--" },
  { label: "Handoff", value: budget.value.handoff_status || "--" },
]);

const digestRows = computed(() =>
  [
    { label: "Attribution input", value: snapshot.value.attribution_sha256, code: true },
    { label: "Entity input", value: snapshot.value.entity_sha256, code: true },
  ].filter((row) => row.value),
);

/** The pipeline stages that ran, in order, with what each produced. */
const stages = computed(() => {
  const campaignEntries = budget.value.campaigns ?? [];
  const reliable = summary.value.filter(
    (row) => row.reliability_status === "RELIABLE",
  ).length;
  return [
    {
      stage: "1. Standardisation",
      produced: "Five-segment touchpoint keys",
      count: distinct(comparison.value, "touchpoint").length,
      status: "COMPLETE",
    },
    {
      stage: "2. Attribution",
      produced: "Markov and Shapley shares per touchpoint",
      count: comparison.value.length,
      status: "COMPLETE",
    },
    {
      stage: "3. Comparison",
      produced: "Reliability verdict per outcome",
      count: summary.value.length,
      status: summary.value.length
        ? `${reliable}/${summary.value.length} RELIABLE`
        : "--",
    },
    {
      stage: "4. Budget seed",
      produced: "Campaign budgets and Ad Group slots",
      count: campaignEntries.length,
      status: budget.value.handoff_status ?? "--",
    },
    {
      stage: "5. Optimisation",
      produced: "Optimised allocation",
      count: 0,
      status: "NOT RUN",
    },
  ];
});

const stageColumns = [
  { key: "stage", label: "Stage", width: "22%" },
  { key: "produced", label: "Produced", width: "38%" },
  { key: "count", label: "Rows", format: "number" },
  { key: "status", label: "Status" },
];

const slotCount = computed(() =>
  (budget.value.campaigns ?? []).reduce(
    (total, entry) => total + (entry.recommended_ad_groups ?? []).length,
    0,
  ),
);

const warnings = computed(() => budget.value.warnings ?? []);

/** Which reliability flags each touchpoint passed. */
const outcome = ref("converted_users");

const flagRows = computed(() =>
  comparison.value
    .filter((row) => row.outcome === outcome.value)
    .slice()
    .sort((a, b) =>
      String(a.reliability_status).localeCompare(String(b.reliability_status)),
    ),
);

const flagColumns = [
  {
    key: "touchpoint",
    label: "Touchpoint",
    format: (value) => value.split(":").filter((part) => part !== "UNSPECIFIED").join(" / "),
    width: "26%",
  },
  { key: "calculation_valid", label: "Calculation", format: "flag" },
  { key: "data_support_sufficient", label: "Data support", format: "flag" },
  { key: "models_consistent", label: "Consistent", format: "flag" },
  { key: "reliability_status", label: "Verdict", tone: (value) => statusTone(value) },
  { key: "reliability_reason", label: "Reason", width: "24%" },
];
</script>

<template>
  <section class="page-grid">
    <p class="caption">
      Provenance of the current numbers: which run produced them, over which
      window, from which inputs.
    </p>

    <div class="page-grid two-up">
      <KeyValuePanel title="Attribution run" :rows="attributionRows" />
      <KeyValuePanel title="Budget run" :rows="budgetRows" />
    </div>

    <article class="card">
      <div class="card-head">
        <h2>Input digests</h2>
      </div>
      <div class="card-body">
        <KeyValuePanel title="SHA-256" :rows="digestRows" />
        <p class="caption">
          The digests identify the exact input files. A recommendation can be
          traced back to the attribution output that justified it.
        </p>
      </div>
    </article>

    <article class="card">
      <div class="card-head">
        <h2>Pipeline stages</h2>
      </div>
      <div class="card-body">
        <DataTable :columns="stageColumns" :rows="stages" />
        <p class="caption">
          Stage 5 has not run: <code>is_optimized</code> is
          <b>{{ String(budget.is_optimized ?? false) }}</b>. The current
          allocation across {{ (budget.campaigns ?? []).length }} Campaigns and
          {{ slotCount }} Ad Group slots is a deterministic seed derived from
          historical attribution.
        </p>

        <div v-if="warnings.length" class="notice warn">
          <b>Warnings raised</b>
          <ul>
            <li v-for="warning in warnings" :key="warning">{{ warning }}</li>
          </ul>
        </div>
        <div v-else class="notice good">
          The budget run completed with no warnings.
        </div>
      </div>
    </article>

    <article class="card">
      <div class="card-head">
        <h2>Reliability flags by touchpoint</h2>
      </div>
      <div class="card-body">
        <div class="filter-row">
          <div class="field">
            <label for="log-outcome">Outcome</label>
            <select id="log-outcome" v-model="outcome">
              <option v-for="(label, key) in OUTCOME_LABELS" :key="key" :value="key">
                {{ label }}
              </option>
            </select>
          </div>
        </div>

        <DataTable
          :columns="flagColumns"
          :rows="flagRows"
          empty="No comparison rows available."
        />
        <p class="caption">
          The verdict is the AND of the three flags. One false flag makes the row
          UNRELIABLE regardless of how close the two models happen to be.
        </p>
      </div>
    </article>
  </section>
</template>
