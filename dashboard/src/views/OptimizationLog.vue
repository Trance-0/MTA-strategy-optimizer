<script setup>
/**
 * Optimization Log: the run record and its provenance.
 *
 * Two kinds of record, kept apart. The provenance tab answers what produced
 * the numbers currently loaded -- which window, which inputs, which hashes --
 * and is derived from the artifacts themselves, so it is answerable in every
 * deployment. The three model tabs answer what happened the last time each
 * stage was run from this dashboard, which only a server that ran one can say.
 *
 * The reference prototype shows an audit trail of optimisation actions. No
 * module writes such a trail, so rather than invent placeholder entries this
 * view shows the real records that do exist.
 *
 * Data flow:
 *     src/lib/useDashboard.js -> here (provenance)
 *     src/lib/useJobs.js      -> here (per-model run logs)
 */
import { computed, onMounted, ref } from "vue";

import DataTable from "../components/DataTable.vue";
import KeyValuePanel from "../components/KeyValuePanel.vue";
import MetricRow from "../components/MetricRow.vue";
import PlotlyChart from "../components/PlotlyChart.vue";
import {
  OUTCOME_LABELS,
  currencySymbol,
  distinct,
  pretty,
  statusTone,
} from "../lib/common.js";
import { useDashboard } from "../lib/useDashboard.js";
import { useJobs } from "../lib/useJobs.js";
import { money } from "../theme.js";
import * as theme from "../theme.js";

const { data } = useDashboard();
// Renamed on import: `stages` below is the pipeline's five artifact-producing
// stages, which is a different list from the three runnable models.
const { stages: modelStages, ensureLoaded: ensureJobsLoaded } = useJobs();

onMounted(ensureJobsLoaded);

/** Provenance first, then one log tab per model in pipeline order. */
const LOG_TABS = [
  { key: "provenance", label: "Provenance" },
  { key: "attribution", label: "Attribution log" },
  { key: "optimization", label: "Optimization log" },
  { key: "evaluation", label: "Evaluation log" },
];
const tab = ref("provenance");

/** The stage descriptor behind a model tab, or null on the provenance tab. */
const activeStage = computed(() => modelStages.value[tab.value] ?? null);

const activeRun = computed(() => activeStage.value?.current ?? null);

function elapsed(record) {
  if (!record?.startedAt) return "--";
  const end = record.finishedAt ? new Date(record.finishedAt) : new Date();
  const seconds = Math.max(0, Math.round((end - new Date(record.startedAt)) / 1000));
  if (seconds < 60) return `${seconds}s`;
  return `${Math.floor(seconds / 60)}m ${String(seconds % 60).padStart(2, "0")}s`;
}

const budget = computed(() => data.value.budgetRecommendation ?? {});
const request = computed(() => data.value.strategyRequest ?? {});
const summary = computed(() => data.value.comparisonSummary);
const comparison = computed(() => data.value.comparisonTouchpoints);

// ---------------------------------------------------------------------------
// Stage 5: the optimized Campaign budget plan
// ---------------------------------------------------------------------------

const strategy = computed(() => data.value.campaignStrategy ?? {});

/** The optimizer's plan, present only once the research command has run. */
const plan = computed(() => strategy.value.optimized_strategy ?? {});

const hasPlan = computed(() => Boolean(plan.value.recommendation_type));

const isOptimized = computed(() => Boolean(plan.value.is_optimized));

const allocations = computed(() => plan.value.allocations ?? []);

const symbol = computed(() => currencySymbol(strategy.value.currency));

/**
 * Whether any allocation sits outside the budget range its fit observed.
 *
 * An extrapolated budget is still the solver's answer, but it rests on the
 * curve's shape beyond the evidence, so the view says so rather than letting
 * the number stand unqualified.
 */
const extrapolated = computed(() =>
  allocations.value.filter((row) => row.is_extrapolated),
);

/** Campaigns whose curve was borrowed from comparable Campaigns, not their own. */
const pooled = computed(() =>
  allocations.value.filter((row) => row.response_support === "POOLED_TRANSFER"),
);

const planMetrics = computed(() => [
  {
    label: "Authorized",
    value: money(plan.value.authorized_budget ?? 0, symbol.value),
    note: pretty(plan.value.budget_usage_policy),
  },
  {
    label: "Allocated",
    value: money(plan.value.allocated_budget ?? 0, symbol.value),
    note: `${allocations.value.length} Campaigns`,
  },
  {
    label: "Expected revenue",
    value: money(plan.value.expected_optimized_revenue ?? 0, symbol.value),
    note: `Initial ${money(plan.value.expected_initial_revenue ?? 0, symbol.value)}`,
    help: "Estimated by the fitted response model, not a realized result.",
  },
  {
    label: "Expected change",
    value: money(plan.value.expected_revenue_increase ?? 0, symbol.value),
    note: "Model estimate",
    help: "The difference between the two estimates above. It is not a guaranteed uplift.",
  },
]);

const allocationColumns = computed(() => [
  { key: "campaign_id", label: "Campaign", width: "22%" },
  { key: "initial_budget", label: "Initial", format: "money", currency: symbol.value },
  {
    key: "optimized_budget",
    label: "Optimized",
    format: "money",
    currency: symbol.value,
  },
  {
    key: "expected_revenue_at_optimized",
    label: "Expected revenue",
    format: "money",
    currency: symbol.value,
  },
  {
    key: "expected_revenue_delta",
    label: "Change",
    format: "money",
    currency: symbol.value,
  },
  {
    key: "marginal_expected_revenue",
    label: "Marginal return",
    format: "share",
    digits: 4,
  },
  {
    key: "response_support",
    label: "Evidence",
    format: (value) => pretty(value),
    tone: (value) => (value === "TARGET_HISTORY" ? "green" : "amber"),
  },
  { key: "is_extrapolated", label: "Extrapolated", format: "flag" },
]);

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
      produced: "Campaign budgets from fitted response curves",
      count: allocations.value.length,
      status: hasPlan.value
        ? isOptimized.value
          ? "COMPLETE"
          : plan.value.recommendation_type
        : "NOT RUN",
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

/** The governed AND verdict for every outcome/touchpoint pair at once. */
const reliabilityMatrixTraces = computed(() => {
  const outcomes = Object.keys(OUTCOME_LABELS);
  const touchpoints = distinct(comparison.value, "touchpoint");
  const lookup = new Map(comparison.value.map((row) => [
    `${row.outcome}\u0000${row.touchpoint}`, row.reliability_status,
  ]));
  const score = { UNRELIABLE: 0, PARTIAL: 0.5, RELIABLE: 1 };
  return touchpoints.length ? [{
    type: "heatmap",
    x: touchpoints.map((value) => value.split(":").filter((part) => part !== "UNSPECIFIED").join(" / ")),
    y: outcomes.map((value) => OUTCOME_LABELS[value]),
    z: outcomes.map((outcomeKey) => touchpoints.map((touchpoint) =>
      score[lookup.get(`${outcomeKey}\u0000${touchpoint}`)] ?? 0.5)),
    customdata: outcomes.map((outcomeKey) => touchpoints.map((touchpoint) =>
      lookup.get(`${outcomeKey}\u0000${touchpoint}`) ?? "NO RESULT")),
    colorscale: [
      [0, theme.STATUS_COLORS.UNRELIABLE], [0.49, theme.STATUS_COLORS.UNRELIABLE],
      [0.5, theme.STATUS_COLORS.PARTIAL], [0.51, theme.STATUS_COLORS.PARTIAL],
      [0.52, theme.STATUS_COLORS.RELIABLE], [1, theme.STATUS_COLORS.RELIABLE],
    ],
    zmin: 0, zmax: 1, showscale: false,
    xgap: 2, ygap: 2,
    hovertemplate: "%{y}<br>%{x}<br><b>%{customdata}</b><extra></extra>",
  }] : [];
});
const reliabilityMatrixLayout = computed(() => theme.layout({
  height: 430, legend: false, margin: { l: 105, r: 8, t: 8, b: 185 },
  xaxis: { tickangle: -45, title: { text: "Touchpoint" } },
  yaxis: { title: { text: "Outcome" }, autorange: "reversed" },
}));
</script>

<template>
  <section class="page-grid">
    <p class="caption">
      Where the current numbers came from, and what happened the last time each
      model was run from this dashboard.
    </p>

    <div class="tabs" role="tablist" aria-label="Log sections">
      <button
        v-for="entry in LOG_TABS"
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

    <!-- One model's run record -->
    <template v-if="activeStage">
      <article class="card">
        <div class="card-head">
          <h2>{{ activeStage.label }}</h2>
          <span class="sub">{{ activeStage.script || "No runnable script" }}</span>
        </div>
        <div class="card-body">
          <div v-if="!activeStage.available" class="notice">
            {{ activeStage.unavailableReason }}
          </div>

          <template v-if="activeRun">
            <KeyValuePanel
              title="Last run"
              :rows="[
                { label: 'State', value: activeRun.state },
                { label: 'Started', value: activeRun.startedAt.replace('T', ' ').slice(0, 19) },
                { label: 'Duration', value: elapsed(activeRun) },
                {
                  label: 'Exit code',
                  value: activeRun.exitCode === null ? '--' : String(activeRun.exitCode),
                },
                { label: 'Command', value: activeRun.command, code: true },
              ]"
            />

            <div v-if="activeRun.error" class="notice bad">{{ activeRun.error }}</div>

            <p v-if="activeRun.droppedLines" class="caption">
              {{ activeRun.droppedLines.toLocaleString() }} earlier line(s)
              dropped; this is the tail of the output.
            </p>

            <div class="log-stream run-log">
              <div
                v-for="(record, index) in activeRun.lines"
                :key="index"
                class="log-row"
                :class="`log-${record.stream}`"
              >
                <span class="log-when">{{ record.at.slice(11, 19) }}</span>
                <span class="log-message">{{ record.text }}</span>
              </div>
            </div>
            <p class="caption">
              The dashboard runs the project's own command unchanged, so this is
              the same output the documented terminal command prints.
            </p>
          </template>

          <p v-else-if="activeStage.available" class="table-empty">
            This model has not been run from the dashboard yet. Run it from the
            Campaign Optimizer's matching tab.
          </p>
        </div>
      </article>
    </template>

    <!-- Provenance of whatever is currently loaded -->
    <template v-else>
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
          Stage 4 produced the seed: an allocation across
          {{ (budget.campaigns ?? []).length }} Campaigns and
          {{ slotCount }} Ad Group slots derived from historical attribution,
          with <code>is_optimized</code> =
          <b>{{ String(budget.is_optimized ?? false) }}</b>.
          <template v-if="hasPlan">
            Stage 5 then reallocated at the Campaign level from fitted budget
            response, which does not read attribution at all.
          </template>
          <template v-else>
            Stage 5 has not run. Run
            <code>script/generate_campaign_strategy.py</code> to fit the
            response models and optimize.
          </template>
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

    <article v-if="hasPlan" class="card">
      <div class="card-head">
        <h2>Optimized Campaign budget</h2>
      </div>
      <div class="card-body">
        <template v-if="isOptimized">
          <MetricRow :items="planMetrics" />

          <DataTable
            :columns="allocationColumns"
            :rows="allocations"
            empty="No Campaign received an optimized budget."
          />
          <p class="caption">
            Each Campaign's budget comes from its own fitted budget-to-spend and
            spend-to-revenue response, allocated so that the marginal return of
            the last unit of budget is equal across every unconstrained
            Campaign. Attribution is not an input here: it divides credit for
            what already happened, which is a different question from how
            revenue responds when a budget changes.
          </p>

          <div v-if="extrapolated.length" class="notice warn">
            <b>Outside observed range</b>
            <ul>
              <li v-for="row in extrapolated" :key="row.campaign_id">
                {{ row.campaign_id }} is optimized to
                {{ money(row.optimized_budget, symbol) }}, outside the
                {{ money(row.observed_budget_range[0], symbol) }} to
                {{ money(row.observed_budget_range[1], symbol) }} range its fit
                observed.
              </li>
            </ul>
          </div>

          <div v-if="pooled.length" class="notice warn">
            <b>Borrowed response</b>
            <ul>
              <li v-for="row in pooled" :key="row.campaign_id">
                {{ row.campaign_id }} has too little budget variation of its
                own, so its curve was pooled from comparable Campaigns. The
                estimate is legitimate but is not this Campaign's observed
                behavior.
              </li>
            </ul>
          </div>

          <p class="caption">
            Budgets are optimized at the Campaign level only
            (<code>{{ plan.ad_group_optimization_claim }}</code>). Any split
            below a Campaign is
            <code>{{ plan.ad_group_projection_basis }}</code>, a projection
            rather than an optimization, because the candidate pool carries
            counts rather than features that would distinguish one new Ad Group
            from another.
          </p>
        </template>

        <template v-else>
          <div class="notice warn">
            <b>{{ pretty(plan.recommendation_type) }}</b>
            <ul>
              <li v-for="reason in plan.infeasibility_reasons ?? []" :key="reason">
                {{ reason }}
              </li>
            </ul>
          </div>
          <p class="caption">
            The optimizer returned no allocation rather than a fabricated one.
            The seed above remains the current recommendation.
          </p>
        </template>

        <div v-if="(plan.excluded_campaign_ids ?? []).length" class="notice">
          Excluded from optimization:
          {{ (plan.excluded_campaign_ids ?? []).join(", ") }}
        </div>
      </div>
    </article>

    <article class="card">
      <div class="card-head">
        <h2>Reliability flags by touchpoint</h2>
      </div>
      <div class="card-body">
        <PlotlyChart
          v-if="reliabilityMatrixTraces.length"
          :traces="reliabilityMatrixTraces"
          :layout="reliabilityMatrixLayout"
          label="Reliability verdict matrix by outcome and touchpoint"
        />
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
    </template>
  </section>
</template>
