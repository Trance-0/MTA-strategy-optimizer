<script setup>
/**
 * Campaign Optimizer: the three models, each with its results and its runner.
 *
 * One tab per model in pipeline order -- attribution, then the strategy
 * optimization that consumes it, then the evaluation that scores the result.
 * Each tab shows that model's own output and, where a database is connected,
 * the controls to run its stage and watch it run. Results and the run that
 * produced them sit together rather than in separate places, because the
 * question "what does this say" and the question "is this current" are asked
 * at the same moment.
 *
 * Attribution: the two models disagree by construction -- Markov measures
 * removal effect, Shapley measures average marginal contribution -- so they are
 * shown side by side per touchpoint with the governed recommendation between
 * them. The budget-shift panel reads the recommendation forward: if spend
 * followed attributed credit rather than its current split, which touchpoints
 * would gain and which would give up budget. That shift is a restatement of the
 * recommendation, not a new model. It never overrides the pipeline's own
 * allocation, and it is withheld outright when the outcome's reliability
 * verdict is UNRELIABLE.
 *
 * Data flow:
 *     src/lib/useDashboard.js -> here (results)
 *     src/lib/useJobs.js      -> here (runs)
 */
import { computed, onMounted, ref } from "vue";

import DataTable from "../components/DataTable.vue";
import MetricRow from "../components/MetricRow.vue";
import PlotlyChart from "../components/PlotlyChart.vue";
import ReliabilityBanner from "../components/ReliabilityBanner.vue";
import StageRunner from "../components/StageRunner.vue";
import TableView from "../components/TableView.vue";
import {
  OUTCOME_LABELS,
  currencySymbol,
  groupSum,
  pretty,
  shortTouchpoint,
  sortBy,
  statusTone,
} from "../lib/common.js";
import { useDashboard } from "../lib/useDashboard.js";
import { useDeployment } from "../lib/deployment.js";
import { useJobs } from "../lib/useJobs.js";
import * as theme from "../theme.js";

const { data } = useDashboard();
const { writable } = useDeployment();
const {
  stages,
  busy: jobBusy,
  error: jobError,
  ensureLoaded: ensureJobsLoaded,
  start: startStage,
  stop: stopStage,
  reloadAfterRun,
} = useJobs();

onMounted(ensureJobsLoaded);

/** One tab per model, in the order the pipeline runs them. */
const MODEL_TABS = [
  { key: "attribution", label: "MTA attribution" },
  { key: "optimization", label: "MTA strategy optimization" },
  { key: "evaluation", label: "MTA strategy evaluation" },
];
const model = ref("attribution");

/**
 * The date range narrows which reporting days the attribution stage reads.
 *
 * Offered as free text rather than a picker over the loaded snapshot, because
 * the stage reads the source reports rather than the snapshot: a window the
 * snapshot cannot show may still be present in the files.
 */
const STAGE_CONTROLS = {
  attribution: [
    { key: "startDate", label: "From (YYYY-MM-DD)", type: "text", placeholder: "Earliest" },
    { key: "endDate", label: "To (YYYY-MM-DD)", type: "text", placeholder: "Latest" },
  ],
  optimization: [
    {
      key: "budgetUsagePolicy",
      label: "Budget usage",
      type: "select",
      options: [
        { value: "SPEND_FULL_BUDGET", label: "Spend the full budget" },
        { value: "SPEND_UP_TO_BUDGET", label: "Spend up to the budget" },
      ],
    },
    { key: "totalBudget", label: "Total daily budget", type: "text", placeholder: "Observed baseline" },
  ],
  evaluation: [],
};

const outcome = ref("converted_users");

const hasData = computed(
  () =>
    data.value.comparisonTouchpoints.length > 0 &&
    data.value.recommendedAttribution.length > 0,
);

const verdict = computed(
  () => data.value.comparisonSummary.find((row) => row.outcome === outcome.value) ?? {},
);

const status = computed(() => verdict.value.reliability_status ?? "UNKNOWN");

// ---------------------------------------------------------------------------
// Markov against Shapley
// ---------------------------------------------------------------------------

const comparison = computed(() =>
  sortBy(
    data.value.comparisonTouchpoints.filter((row) => row.outcome === outcome.value),
    "markov_share",
  ),
);

const comparisonTraces = computed(() => {
  const labels = comparison.value.map((row) => shortTouchpoint(row.touchpoint));
  return [
    ["markov_share", "markov"],
    ["shapley_share", "shapley"],
  ].map(([field, model]) => ({
    type: "bar",
    orientation: "h",
    name: pretty(model),
    y: labels,
    x: comparison.value.map((row) => row[field]),
    marker: {
      color: theme.MODEL_COLORS[model],
      line: { color: theme.SURFACE, width: 2 },
    },
    hovertemplate: `<b>${pretty(model)}</b><br>%{y}<br>Share %{x:.2%}<extra></extra>`,
  }));
});

const comparisonLayout = computed(() =>
  theme.layout({
    height: 460,
    barmode: "group",
    bargroupgap: 0.08,
    xaxis: { title: { text: "Attributed share" }, tickformat: ".0%" },
  }),
);

/** The touchpoint the two models disagree about most, named in the caption. */
const largestGap = computed(() => {
  const ordered = [...comparison.value].sort(
    (a, b) => Math.abs(b.gap_pp ?? 0) - Math.abs(a.gap_pp ?? 0),
  );
  return ordered[0] ?? null;
});

const comparisonColumns = [
  {
    key: "touchpoint",
    label: "Touchpoint",
    format: (value) => shortTouchpoint(value),
    width: "30%",
  },
  { key: "markov_share", label: "Markov", format: "share" },
  { key: "shapley_share", label: "Shapley", format: "share" },
  { key: "gap_pp", label: "Gap (pp)", format: "share", digits: 2 },
  { key: "relative_gap", label: "Relative gap", format: "share" },
  { key: "raw_converted_users", label: "Raw converted", format: "number" },
  { key: "reliability_status", label: "Reliability", tone: (value) => statusTone(value) },
];

const comparisonRows = computed(() =>
  [...comparison.value].sort(
    (a, b) => Math.abs(b.gap_pp ?? 0) - Math.abs(a.gap_pp ?? 0),
  ),
);

// ---------------------------------------------------------------------------
// Recommended attribution
// ---------------------------------------------------------------------------

const recommended = computed(() =>
  sortBy(
    data.value.recommendedAttribution.filter((row) => row.outcome === outcome.value),
    "official_share",
    "desc",
  ),
);

const recommendedColumns = [
  {
    key: "touchpoint",
    label: "Touchpoint",
    format: (value) => shortTouchpoint(value),
    width: "26%",
  },
  { key: "official_model", label: "Official" },
  { key: "official_share", label: "Official share", format: "share" },
  { key: "recommended_value", label: "Recommended" },
  { key: "benchmark_model", label: "Benchmark" },
  { key: "benchmark_share", label: "Benchmark share", format: "share" },
  { key: "gap_pp", label: "Gap (pp)", format: "share", digits: 2 },
  { key: "reliability_status", label: "Reliability", tone: (value) => statusTone(value) },
];

// ---------------------------------------------------------------------------
// Implied budget shift
// ---------------------------------------------------------------------------

const unreliable = computed(() => String(status.value).toUpperCase() === "UNRELIABLE");

/**
 * The current spend split against the split implied by attributed credit.
 *
 * Cost is taken from the Markov rows alone: both models report the same cost
 * per touchpoint, so summing across both would double every figure.
 */
const shift = computed(() => {
  if (unreliable.value) return [];

  const spend = new Map(
    groupSum(
      data.value.attributionResults.filter((row) => row.attribution_model === "markov"),
      "touchpoint",
      ["cost"],
    ).map((entry) => [entry.key, entry.cost]),
  );

  const merged = recommended.value
    .filter((row) => spend.has(row.touchpoint))
    .map((row) => ({
      touchpoint: row.touchpoint,
      official_share: row.official_share ?? 0,
      cost: spend.get(row.touchpoint) ?? 0,
    }));

  const totalSpend = merged.reduce((total, row) => total + row.cost, 0);
  const shareTotal = merged.reduce((total, row) => total + row.official_share, 0);
  if (!totalSpend || !shareTotal) return [];

  return merged.map((row) => {
    const currentShare = row.cost / totalSpend;
    const targetShare = row.official_share / shareTotal;
    const impliedBudget = targetShare * totalSpend;
    return {
      ...row,
      current_share: currentShare,
      target_share: targetShare,
      delta_pp: (targetShare - currentShare) * 100,
      implied_budget: impliedBudget,
      delta_budget: impliedBudget - row.cost,
    };
  });
});

const topN = ref(10);

const shiftTraces = computed(() => {
  const ordered = [...shift.value]
    .sort((a, b) => Math.abs(a.delta_pp) - Math.abs(b.delta_pp))
    .slice(-topN.value);
  return [
    {
      type: "bar",
      orientation: "h",
      y: ordered.map((row) => shortTouchpoint(row.touchpoint)),
      x: ordered.map((row) => row.delta_pp),
      marker: {
        color: ordered.map((row) =>
          row.delta_pp >= 0 ? theme.SERIES[2] : theme.SERIES[7],
        ),
        line: { color: theme.SURFACE, width: 2 },
      },
      customdata: ordered.map((row) => [row.cost, row.implied_budget, row.delta_budget]),
      hovertemplate:
        "<b>%{y}</b><br>Shift %{x:+.2f} pp<br>" +
        "Current spend %{customdata[0]:$,.2f}<br>" +
        "Implied spend %{customdata[1]:$,.2f}<br>" +
        "Change %{customdata[2]:+$,.2f}<extra></extra>",
    },
  ];
});

const shiftLayout = computed(() =>
  theme.layout({
    height: Math.max(320, 26 * topN.value + 90),
    legend: false,
    xaxis: { title: { text: "Change in spend share (percentage points)" }, zeroline: true },
    shapes: [
      {
        type: "line",
        yref: "paper",
        x0: 0,
        x1: 0,
        y0: 0,
        y1: 1,
        line: { color: theme.AXIS, width: 1 },
      },
    ],
  }),
);

const shiftTiles = computed(() => {
  const rows = shift.value;
  const gaining = rows.filter((row) => row.delta_pp > 0);
  const reallocated = rows
    .filter((row) => row.delta_budget > 0)
    .reduce((total, row) => total + row.delta_budget, 0);
  const largest = rows.reduce(
    (best, row) => Math.max(best, Math.abs(row.delta_pp)),
    0,
  );
  return [
    { label: "Spend re-allocated", value: theme.compactMoney(reallocated) },
    { label: "Touchpoints gaining", value: theme.count(gaining.length) },
    { label: "Touchpoints reduced", value: theme.count(rows.length - gaining.length) },
    { label: "Largest single shift", value: `${largest.toFixed(2)} pp` },
  ];
});

const shiftColumns = [
  {
    key: "touchpoint",
    label: "Touchpoint",
    format: (value) => shortTouchpoint(value),
    width: "28%",
  },
  { key: "cost", label: "Current spend", format: "money" },
  { key: "current_share", label: "Current share", format: "percent" },
  { key: "target_share", label: "Target share", format: "percent" },
  { key: "implied_budget", label: "Implied spend", format: "money" },
  { key: "delta_budget", label: "Change", format: "money" },
  { key: "delta_pp", label: "Shift (pp)", format: "share", digits: 2 },
];

const shiftRows = computed(() => sortBy(shift.value, "delta_pp", "desc"));

// ---------------------------------------------------------------------------
// Strategy optimization: the fitted response model's plan
// ---------------------------------------------------------------------------

const strategy = computed(() => data.value.campaignStrategy ?? {});
const plan = computed(() => strategy.value.optimized_strategy ?? {});
const hasPlan = computed(() => Boolean(plan.value.recommendation_type));
const isOptimized = computed(() => Boolean(plan.value.is_optimized));
const allocations = computed(() => plan.value.allocations ?? []);
const symbol = computed(() => currencySymbol(strategy.value.currency));

const planMetrics = computed(() => [
  {
    label: "Authorized",
    value: theme.money(plan.value.authorized_budget ?? 0, symbol.value),
    note: pretty(plan.value.budget_usage_policy),
  },
  {
    label: "Allocated",
    value: theme.money(plan.value.allocated_budget ?? 0, symbol.value),
    note: `${allocations.value.length} Campaigns`,
  },
  {
    label: "Expected revenue",
    value: theme.money(plan.value.expected_optimized_revenue ?? 0, symbol.value),
    note: `Initial ${theme.money(plan.value.expected_initial_revenue ?? 0, symbol.value)}`,
    help: "Estimated by the fitted response model, not a realized result.",
  },
  {
    label: "Expected change",
    value: theme.money(plan.value.expected_revenue_increase ?? 0, symbol.value),
    note: "Model estimate",
    help: "The difference between the two estimates above. It is not a guaranteed uplift.",
  },
]);

const allocationColumns = computed(() => [
  { key: "campaign_id", label: "Campaign", width: "20%" },
  { key: "initial_budget", label: "Initial", format: "money", currency: symbol.value },
  { key: "optimized_budget", label: "Optimized", format: "money", currency: symbol.value },
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
  { key: "marginal_expected_revenue", label: "Marginal return", format: "share", digits: 4 },
  {
    key: "response_support",
    label: "Evidence",
    format: (value) => pretty(value),
    tone: (value) => (value === "TARGET_HISTORY" ? "green" : "amber"),
  },
  { key: "is_extrapolated", label: "Extrapolated", format: "flag" },
]);

/** Allocations resting on the curve's shape beyond the evidence behind it. */
const extrapolated = computed(() =>
  allocations.value.filter((row) => row.is_extrapolated),
);

/** Campaigns whose curve was borrowed from comparable Campaigns. */
const pooled = computed(() =>
  allocations.value.filter((row) => row.response_support === "POOLED_TRANSFER"),
);

// ---------------------------------------------------------------------------
// Strategy evaluation
// ---------------------------------------------------------------------------

/**
 * The evaluation stage has no artifact to show.
 *
 * `modules/mta_strategy_evaluation/` is specified but unbuilt, so this tab
 * shows what the layer is for and what exists in its place, rather than an
 * empty table implying a run that failed. The stage's own runner states the
 * same thing from the server's side.
 */
const evaluationAvailable = computed(
  () => stages.value.evaluation?.available ?? false,
);
</script>

<template>
  <section class="page-grid">
    <p class="caption">
      The three models in pipeline order. Each tab carries that model's own
      results and, where a database is connected, the controls to run it.
    </p>

    <div class="tabs" role="tablist" aria-label="Models">
      <button
        v-for="entry in MODEL_TABS"
        :key="entry.key"
        class="tab"
        role="tab"
        :aria-selected="model === entry.key"
        :class="{ active: model === entry.key }"
        @click="model = entry.key"
      >
        {{ entry.label }}
      </button>
    </div>

    <article v-if="stages[model]" class="card">
      <div class="card-head">
        <h2>Run {{ stages[model].label }}</h2>
        <span class="sub">{{ stages[model].script || "No runnable script" }}</span>
      </div>
      <div class="card-body">
        <div v-if="jobError" class="notice bad">{{ jobError.message }}</div>
        <StageRunner
          :stage="stages[model]"
          :writable="writable"
          :busy="jobBusy"
          :controls="STAGE_CONTROLS[model] ?? []"
          @start="startStage(model, $event)"
          @stop="stopStage(model)"
          @reload="reloadAfterRun"
        />
      </div>
    </article>

    <!-- 1. MTA attribution -->
    <template v-if="model === 'attribution' && hasData">
      <div class="filter-row">
        <div class="field">
          <label for="optimizer-outcome">Outcome</label>
          <select id="optimizer-outcome" v-model="outcome">
            <option v-for="(label, key) in OUTCOME_LABELS" :key="key" :value="key">
              {{ label }}
            </option>
          </select>
        </div>
      </div>

      <ReliabilityBanner
        :status="status"
        :reason="verdict.reliability_reason || ''"
      />

      <article class="card">
        <div class="card-head">
          <h2>Markov against Shapley</h2>
          <span class="sub">{{ OUTCOME_LABELS[outcome] }}</span>
        </div>
        <div class="card-body">
          <PlotlyChart
            v-if="comparison.length"
            :traces="comparisonTraces"
            :layout="comparisonLayout"
            label="Markov and Shapley attributed share for every touchpoint"
          />
          <p v-else class="table-empty">
            No comparison rows for {{ OUTCOME_LABELS[outcome] }}.
          </p>
          <p v-if="largestGap" class="caption">
            Where the two bars differ, the models disagree about how much credit a
            touchpoint deserves. Largest gap:
            <b>{{ shortTouchpoint(largestGap.touchpoint) }}</b> at
            {{ Number(largestGap.gap_pp).toFixed(2) }} percentage points.
          </p>
          <TableView
            label="View comparison as a table"
            :columns="comparisonColumns"
            :rows="comparisonRows"
          />
        </div>
      </article>

      <article class="card">
        <div class="card-head">
          <h2>Recommended attribution</h2>
          <span class="sub">The governed value</span>
        </div>
        <div class="card-body">
          <DataTable
            :columns="recommendedColumns"
            :rows="recommended"
            :empty="`No recommended rows for ${OUTCOME_LABELS[outcome]}.`"
          />
          <p class="caption">
            A RELIABLE row carries the official model's point value. An
            UNRELIABLE row carries the closed interval between the two models
            instead, and grants no budgeting authority.
          </p>
        </div>
      </article>

      <article class="card">
        <div class="card-head">
          <h2>Implied budget shift</h2>
          <span class="sub">A restatement, not a prediction</span>
        </div>
        <div class="card-body">
          <div v-if="unreliable" class="notice warn">
            This outcome is <b>UNRELIABLE</b>, so no budget shift is shown. The
            recommended value is an interval, and an interval cannot carry a
            spend split.
          </div>
          <p v-else-if="shift.length === 0" class="table-empty">
            No spend to compare the recommendation against.
          </p>
          <template v-else>
            <div class="filter-row">
              <div class="field">
                <label for="optimizer-top">Touchpoints shown: {{ topN }}</label>
                <input
                  id="optimizer-top"
                  v-model.number="topN"
                  type="range"
                  min="5"
                  :max="shift.length"
                />
              </div>
            </div>

            <PlotlyChart
              :traces="shiftTraces"
              :layout="shiftLayout"
              label="Change in spend share per touchpoint, in percentage points"
            />

            <MetricRow :items="shiftTiles" />

            <p class="caption">
              Green gains share, red gives it up. This restates the recommended
              attribution as a spend split at constant total budget; it does not
              predict the outcome of making the change, and it does not replace
              the allocation in the Budget Manager view.
            </p>
            <TableView
              label="View the implied shift as a table"
              :columns="shiftColumns"
              :rows="shiftRows"
            />
          </template>
        </div>
      </article>
    </template>

    <article v-else-if="model === 'attribution'" class="card empty-card">
      <h2>No attribution output</h2>
      <p>
        No attribution output is available from the current data source. Run the
        stage above, or switch <code>DATABASE</code> in <code>.env</code>.
      </p>
    </article>

    <!-- 2. MTA strategy optimization -->
    <template v-if="model === 'optimization'">
      <template v-if="hasPlan && isOptimized">
        <MetricRow :items="planMetrics" />

        <article class="card">
          <div class="card-head">
            <h2>Optimized Campaign budget</h2>
            <span class="sub">{{ allocations.length }} Campaigns</span>
          </div>
          <div class="card-body">
            <DataTable
              :columns="allocationColumns"
              :rows="allocations"
              empty="No Campaign received an optimized budget."
            />
            <p class="caption">
              Each Campaign's budget comes from its own fitted budget-to-spend
              and spend-to-revenue response, allocated so the marginal return of
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
                  {{ theme.money(row.optimized_budget, symbol) }}, outside the
                  {{ theme.money(row.observed_budget_range[0], symbol) }} to
                  {{ theme.money(row.observed_budget_range[1], symbol) }} range
                  its fit observed.
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

            <div v-if="(plan.excluded_campaign_ids ?? []).length" class="notice">
              Excluded from optimization:
              {{ (plan.excluded_campaign_ids ?? []).join(", ") }}
            </div>
          </div>
        </article>
      </template>

      <article v-else-if="hasPlan" class="card">
        <div class="card-head">
          <h2>No allocation was produced</h2>
        </div>
        <div class="card-body">
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
            The Budget Manager's seed remains the current recommendation.
          </p>
        </div>
      </article>

      <article v-else class="card empty-card">
        <h2>No optimized strategy</h2>
        <p>
          The budget response models have not been fitted against the current
          data. Run the stage above to fit them and optimize.
        </p>
      </article>
    </template>

    <!-- 3. MTA strategy evaluation -->
    <template v-if="model === 'evaluation'">
      <article class="card">
        <div class="card-head">
          <h2>Strategy evaluation</h2>
          <span class="sub">Specified, not yet built</span>
        </div>
        <div class="card-body">
          <p>
            This layer scores a strategy the way
            <code>modules/mta_standard</code> scores an attribution model:
            load a strategy through a validated contract, run it, and compare
            its output against a baseline and, where one exists, ground truth.
            It is specified but not implemented — neither
            <code>modules/mta_strategy_evaluation/</code> nor
            <code>script/evaluate_strategies.py</code> exists yet.
          </p>
          <p class="caption">
            The tab is shown rather than hidden because the gap is real and
            worth seeing: the optimization tab above reports an expected
            revenue that nothing currently scores against a realized outcome.
            Attribution model evaluation against simulator ground truth does
            exist, in <code>modules/mta_standard/src/evaluation.py</code>.
          </p>
          <div v-if="!evaluationAvailable" class="notice">
            Until the layer is built, an optimized plan's quality can be judged
            only by the evidence labels on each allocation — whether its curve
            came from that Campaign's own history, and whether its budget sits
            inside the range the fit observed.
          </div>
        </div>
      </article>
    </template>
  </section>
</template>
