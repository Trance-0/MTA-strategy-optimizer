<script setup>
/**
 * Campaign Optimizer: what each model predicts, and what the shift implies.
 *
 * The two models disagree by construction -- Markov measures removal effect,
 * Shapley measures average marginal contribution -- so this view puts them side
 * by side per touchpoint and shows the governed recommendation between them.
 * The budget-shift panel then reads the recommendation forward: if spend
 * followed attributed credit rather than its current split, which touchpoints
 * would gain and which would give up budget.
 *
 * The shift is a restatement of the recommendation, not a new model. It never
 * overrides the pipeline's own allocation, and it is withheld outright when the
 * outcome's reliability verdict is UNRELIABLE.
 */
import { computed, ref } from "vue";

import DataTable from "../components/DataTable.vue";
import MetricRow from "../components/MetricRow.vue";
import PlotlyChart from "../components/PlotlyChart.vue";
import ReliabilityBanner from "../components/ReliabilityBanner.vue";
import TableView from "../components/TableView.vue";
import {
  OUTCOME_LABELS,
  groupSum,
  pretty,
  shortTouchpoint,
  sortBy,
  statusTone,
} from "../lib/common.js";
import { useDashboard } from "../lib/useDashboard.js";
import * as theme from "../theme.js";

const { data } = useDashboard();

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
</script>

<template>
  <section class="page-grid">
    <p class="caption">
      Model predictions per touchpoint, and the budget shift implied by moving
      spend toward attributed credit.
    </p>

    <template v-if="hasData">
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

    <article v-else class="card empty-card">
      <h2>No model comparison output</h2>
      <p>
        No model comparison output is available from the current data source. Run
        the pipeline, or switch <code>DATABASE</code> in <code>.env</code>.
      </p>
    </article>
  </section>
</template>
