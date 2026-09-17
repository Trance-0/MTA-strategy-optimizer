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
import { computed, onMounted, onBeforeUnmount, ref, watch } from "vue";

import TermHelp from "../components/TermHelp.vue";
import { optimizeCampaign, IS_STATIC } from "../api/client.js";
import EntityTable from "../components/EntityTable.vue";
import MetricRow from "../components/MetricRow.vue";
import PlotlyChart from "../components/PlotlyChart.vue";
import ReliabilityBanner from "../components/ReliabilityBanner.vue";
import WorkbenchRunner from "../components/WorkbenchRunner.vue";
import EvaluationReport from "../components/EvaluationReport.vue";
import StageRunner from "../components/StageRunner.vue";
import TableView from "../components/TableView.vue";
import WillowGmvForecast from "../components/WillowGmvForecast.vue";
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
import { useJobs } from "../lib/useJobs.js";
import * as theme from "../theme.js";

const { data, selectedDatasetId } = useDashboard();
const props = defineProps({ section: { type: String, default: "attribution" } });
const emit = defineEmits(["navigate"]);
const {
  stages,
  busy: jobBusy,
  error: jobError,
  ensureLoaded: ensureJobsLoaded,
  start: startStage,
  stop: stopStage,
  uploadOutputs,
  importOutputs,
  reloadAfterRun,
} = useJobs();

onMounted(() => { if (!selectedDatasetId.value) ensureJobsLoaded(); });

/** One tab per model, in the order the pipeline runs them. */
const MODEL_TABS = [
  { key: "attribution", label: "MTA attribution" },
  { key: "optimization", label: "MTA strategy optimization" },
  { key: "evaluation", label: "MTA strategy evaluation" },
];
const model = computed(() => props.section);

const STAGE_CONTROLS = {
  attribution: [],
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
  data.value.comparisonTouchpoints
    .filter((row) => row.outcome === outcome.value)
    .slice()
    .sort((a, b) => Math.abs(a.gap_pp ?? 0) - Math.abs(b.gap_pp ?? 0)),
);

const comparisonTraces = computed(() => {
  const labels = comparison.value.map((row) => shortTouchpoint(row.touchpoint));
  return [
    {
      type: "scatter", mode: "lines", name: "Gap",
      x: comparison.value.flatMap((row) => [row.markov_share, row.shapley_share, null]),
      y: labels.flatMap((label) => [label, label, null]),
      line: { color: theme.AXIS, width: 3 }, hoverinfo: "skip", showlegend: false,
    },
    ...[["markov_share", "markov"], ["shapley_share", "shapley"]].map(([field, name]) => ({
      type: "scatter", mode: "markers", name: pretty(name),
      x: comparison.value.map((row) => row[field]), y: labels,
      customdata: comparison.value.map((row) => row.gap_pp),
      marker: { color: theme.MODEL_COLORS[name], size: 10,
        line: { color: theme.SURFACE, width: 1 } },
      hovertemplate: `<b>${pretty(name)}</b><br>%{y}<br>Share %{x:.2%}<br>Gap %{customdata:.2f} pp<extra></extra>`,
    })),
  ];
});

const comparisonLayout = computed(() =>
  theme.layout({
    height: 460,
    xaxis: { title: { text: "Attributed share" }, tickformat: ".0%" },
  }),
);

/** The touchpoint the two models disagree about most, named in the caption. */
const largestGap = computed(() => {
  const ordered = comparison.value.filter(row => Number.isFinite(row.gap_pp)).sort(
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
  { key: "markov_share", label: "Markov", format: "percent" },
  { key: "shapley_share", label: "Shapley", format: "percent" },
  { key: "gap_pp", label: "Gap (pp)", format: "number", digits: 2 },
  { key: "relative_gap", label: "Relative gap", format: "percent" },
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
  { key: "official_share", label: "Official share", format: "percent" },
  { key: "recommended_value", label: "Recommended" },
  { key: "benchmark_model", label: "Benchmark" },
  { key: "benchmark_share", label: "Benchmark share", format: "percent" },
  { key: "gap_pp", label: "Gap (pp)", format: "number", digits: 2 },
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
      official_share: row.official_share,
      cost: spend.get(row.touchpoint),
    }));

  if (merged.some(row => !Number.isFinite(row.official_share) || !Number.isFinite(row.cost))) return [];

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
          row.delta_pp >= 0 ? theme.DIVERGING[1] : theme.DIVERGING[3],
        ),
        line: { color: theme.SURFACE, width: 2 },
      },
      customdata: ordered.map((row) => [row.cost, row.implied_budget, row.delta_budget]),
      hovertemplate:
        "<b>%{y}</b><br>Shift %{x:+.2f} pp<br>" +
        "Current spend %{customdata[0]:,.2f}<br>" +
        "Implied spend %{customdata[1]:,.2f}<br>" +
        "Change %{customdata[2]:+,.2f}<extra></extra>",
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
    { label: "Spend re-allocated", value: theme.compactMoney(reallocated, symbol.value) },
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
  { key: "delta_pp", label: "Shift (pp)", format: "number", digits: 2 },
];

const shiftRows = computed(() => sortBy(shift.value, "delta_pp", "desc"));

// ---------------------------------------------------------------------------
// Strategy optimization: the fitted response model's plan
// ---------------------------------------------------------------------------

const campaignQuery = new URLSearchParams(window.location.search);
const selectedCampaign = ref(campaignQuery.get("campaignId") || "");
const selectedMarketplace = ref(campaignQuery.get("marketplace") || data.value.dataset?.scope?.marketplace || data.value.dashboardContext?.marketplace || "");
const campaignSource = ref(campaignQuery.get("campaignSource") || selectedDatasetId.value || "legacy");
const scopedPreview = computed(() => Boolean(selectedCampaign.value) && model.value === "optimization");
const campaignSearch = ref("");
const campaignOptions = computed(() => {
  const unique = new Map();
  for (const row of data.value.simulationResearch?.campaigns ?? []) {
    if (row.campaign_id) unique.set(row.campaign_id, row);
  }
  return [...unique.values()].sort((a, b) => a.campaign_id.localeCompare(b.campaign_id));
});
const matchingCampaigns = computed(() => {
  const query = campaignSearch.value.trim().toLowerCase();
  return campaignOptions.value.filter(row => [row.campaign_id, row.campaign_name, row.provider, row.ad_product]
    .some(value => String(value ?? "").toLowerCase().includes(query)));
});
function chooseCampaign() {
  campaignSource.value = selectedDatasetId.value || "legacy";
  initialBudget.value = "";
}
const historyMode = ref("full");
const initialBudget = ref("");
const similarityThreshold = ref(0);
const inputError = computed(() => {
  if (initialBudget.value !== "" && (typeof initialBudget.value !== "number" || !Number.isFinite(initialBudget.value) || initialBudget.value <= 0)) return "Enter an initial budget greater than zero, or leave it blank for the historical default.";
  if (historyMode.value === "full" && (typeof similarityThreshold.value !== "number" || !Number.isFinite(similarityThreshold.value) || similarityThreshold.value < 0 || similarityThreshold.value > 1)) return "Enter a similarity threshold between 0 and 1.";
  return "";
});
const similarityHelp = {
  definition: "References must match account, marketplace, currency, provider and ad product. Budget similarity is 1 minus the absolute budget difference divided by the larger budget (at least 1). Zero includes all compatible budgets; one requires an exact budget match. Your initial budget is the reference when entered; otherwise the Campaign baseline is used. Own history is retained.",
  href: "/en/introduction/backend/recommendation",
};
const preview = ref(null);
const previewBusy = ref(false);
const previewError = ref("");
let previewGeneration = 0;
const optimizerHelp = {
  definition: "Fits two saturating curves from ordinary historical observations: budget to spend, then spend to revenue. The constrained solver maximizes predicted revenue within the budget limit. Full dataset searches compatible history across all dates in the same account, marketplace, currency, provider and ad product. With sufficient variation it fits a transferred response; otherwise it returns an observed historical baseline without claiming an optimum.",
  href: "/en/strategy-recommendation/campaign-budget-optimizer/",
};
async function computeCampaign() {
  const token = ++previewGeneration;
  preview.value = null; previewError.value = ""; previewBusy.value = false;
  if (!scopedPreview.value || !selectedMarketplace.value.trim()) return;
  if (inputError.value) return;
  if ((selectedDatasetId.value || "legacy") !== campaignSource.value) {
    previewError.value = "The selected source changed. Open Optimize from the Campaign in the current source.";
    return;
  }
  previewBusy.value = true;
  try {
    const result = await optimizeCampaign({ campaignId: selectedCampaign.value, marketplace: selectedMarketplace.value.trim(), historyMode: historyMode.value,
      similarityThreshold: historyMode.value === "full" ? similarityThreshold.value : 0,
      ...(initialBudget.value === "" ? {} : { initialBudget: initialBudget.value }),
      ...(selectedDatasetId.value ? { datasetId: selectedDatasetId.value } : {}) });
    if (token === previewGeneration) preview.value = result;
  } catch (error) { if (token === previewGeneration) previewError.value = error.message; }
  finally { if (token === previewGeneration) previewBusy.value = false; }
}
// Numeric edits invalidate old results immediately; submit only on Recompute.
watch([initialBudget, similarityThreshold], () => {
  previewGeneration += 1; preview.value = null; previewBusy.value = false;
  previewError.value = "";
}, { flush: "sync" });
watch(selectedDatasetId, () => {
  selectedCampaign.value = ""; campaignSearch.value = "";
  campaignSource.value = selectedDatasetId.value || "legacy";
  initialBudget.value = "";
  selectedMarketplace.value = data.value.dataset?.scope?.marketplace || data.value.dashboardContext?.marketplace || "";
}, { flush: "sync" });
watch([scopedPreview, selectedCampaign, selectedMarketplace, selectedDatasetId, historyMode], computeCampaign, { immediate: true });
onBeforeUnmount(() => { previewGeneration += 1; });
const strategy = computed(() => scopedPreview.value ? preview.value ?? {} : data.value.campaignStrategy ?? {});
const plan = computed(() => strategy.value.optimized_strategy ?? {});
const hasPlan = computed(() => Boolean(plan.value.recommendation_type));
const isOptimized = computed(() => Boolean(plan.value.is_optimized));
const allocations = computed(() => plan.value.allocations ?? []);
const symbol = computed(() => currencySymbol(strategy.value.currency ?? data.value.dataset?.scope?.currency ?? data.value.dashboardContext?.currency ?? data.value.strategyRequest?.campaign_group?.currency));
const evidenceColumns = columns => columns.map(column => column.format === "money"
  ? { ...column, currency: symbol.value } : column);
/** Read only dates carried by the displayed result, never the historical filter. */
const evidenceWindow = computed(() => {
  const rows = model.value === "optimization" ? strategy.value.response_observations ?? [] : data.value.attributionResults;
  let start = null, end = null;
  for (const row of rows) {
    const first = row.report_start_date ?? row.report_date;
    const last = row.report_end_date ?? row.report_date;
    if (first && (!start || first < start)) start = first;
    if (last && (!end || last > end)) end = last;
  }
  return start && end ? `${start} to ${end}` : "Reporting window unavailable in this result";
});

const planMetrics = computed(() => [
  {
    label: "Authorized",
    value: theme.money(plan.value.authorized_budget, symbol.value),
    note: pretty(plan.value.budget_usage_policy),
  },
  {
    label: "Allocated",
    value: theme.money(plan.value.allocated_budget, symbol.value),
    note: `${allocations.value.length} Campaigns`,
  },
  {
    label: "Expected revenue",
    value: theme.money(plan.value.expected_optimized_revenue, symbol.value),
    note: `Initial ${theme.money(plan.value.expected_initial_revenue, symbol.value)}`,
    help: "Estimated by the fitted response model, not a realized result.",
  },
  {
    label: "Expected change",
    value: theme.money(plan.value.expected_revenue_increase, symbol.value),
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
    label: "Expected optimized revenue",
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
    key: "response_support",
    label: "Evidence",
    format: (value) => pretty(value),
    tone: (value) => (value === "TARGET_HISTORY" ? "green" : "amber"),
  },
  { key: "expected_revenue_at_initial", label: "Expected initial revenue", format: "money", currency: symbol.value },
  { key: "observed_budget_range", label: "Observed budget range" },
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

const responseCampaign = ref("");
const responseModels = computed(() => strategy.value.response_models?.campaign_models ?? {});
const responseCampaigns = computed(() => [...new Set([...Object.keys(responseModels.value), ...allocations.value.map(row => row.campaign_id)])].sort());
const activeResponseCampaign = computed(() =>
  responseCampaign.value && responseCampaigns.value.includes(responseCampaign.value)
    ? responseCampaign.value : responseCampaigns.value[0] ?? "",
);
const activeResponseModel = computed(() => responseModels.value[activeResponseCampaign.value] ?? {});
const activeAllocation = computed(() =>
  allocations.value.find((row) => row.campaign_id === activeResponseCampaign.value) ?? {},
);
const responseObservations = computed(() =>
  (strategy.value.response_observations ?? []).filter(
    (row) => row.campaign_id === activeResponseCampaign.value ||
      (activeResponseModel.value.diagnostics?.support === "POOLED_TRANSFER" &&
       (activeResponseModel.value.diagnostics?.pooled_campaign_ids ?? []).includes(row.campaign_id)),
  ),
);

/** Project the serialized fitted model only when every required parameter exists. */
function expectedRevenue(model, budget) {
  const spendModel = model.spend_response ?? {};
  const revenueModel = model.revenue_response ?? {};
  const params = [budget, spendModel.capacity, spendModel.scale, revenueModel.baseline, revenueModel.alpha, revenueModel.kappa];
  if (!params.every(value => typeof value === "number" && Number.isFinite(value)) ||
      spendModel.scale <= 0 || revenueModel.kappa <= 0) return null;
  const spend = spendModel.capacity * (1 - Math.exp(-Math.max(0, budget) / spendModel.scale));
  return revenueModel.baseline + revenueModel.alpha * (1 - Math.exp(-spend / revenueModel.kappa));
}
// Sampling changes plotted density only; the complete observation table stays available.
const responsePlotObservations = computed(() => {
  const rows = responseObservations.value.filter(row => Number.isFinite(row.configured_budget) && Number.isFinite(row.total_revenue));
  if (rows.length <= 500) return rows;
  return Array.from({ length: 500 }, (_, index) => rows[Math.floor(index * (rows.length - 1) / 499)]);
});
const responseMaximum = computed(() => {
  const range = activeResponseModel.value.diagnostics?.observed_budget_range;
  return Math.max(Number.isFinite(range?.[1]) ? range[1] : 0,
    Number.isFinite(activeAllocation.value.optimized_budget) ? activeAllocation.value.optimized_budget : 0, 1) * 1.25;
});
const responseCurveValues = computed(() => {
  const model = activeResponseModel.value;
  if (expectedRevenue(model, 0) == null) return [];
  return Array.from({ length: 81 }, (_, index) => {
    const budget = responseMaximum.value * index / 80;
    return { budget, expected_revenue: expectedRevenue(model, budget) };
  });
});
const responseValueColumns = computed(() => [
  { key: "budget", label: "Budget", format: "money", currency: symbol.value },
  { key: "expected_revenue", label: "Expected revenue", format: "money", currency: symbol.value },
]);
const responseObservationColumns = computed(() => [
  { key: "campaign_id", label: "Observed Campaign" },
  { key: "report_date", label: "Date" }, { key: "intervention_id", label: "Intervention" },
  { key: "configured_budget", label: "Budget", format: "money", currency: symbol.value },
  { key: "actual_spend", label: "Spend", format: "money", currency: symbol.value },
  { key: "total_revenue", label: "Revenue", format: "money", currency: symbol.value },
]);
const responseRowKey = row => JSON.stringify([row.campaign_id, row.report_date, row.intervention_id, row.configured_budget, row.marketplace]);

const responseCurveTraces = computed(() => {
  const allocation = activeAllocation.value;
  const traces = [];
  if (responseCurveValues.value.length) traces.push({
    type: "scatter", mode: "lines", name: "Fitted response",
    x: responseCurveValues.value.map(row => row.budget),
    y: responseCurveValues.value.map(row => row.expected_revenue),
    line: { color: theme.SERIES[0], width: 3 },
    hovertemplate: `Budget ${symbol.value}%{x:,.2f}<br>Expected revenue ${symbol.value}%{y:,.2f}<extra></extra>`,
  });
  if (responsePlotObservations.value.length) traces.push({
    type: "scatter", mode: "markers", name: "Observed",
    x: responsePlotObservations.value.map(row => row.configured_budget),
    y: responsePlotObservations.value.map(row => row.total_revenue),
    customdata: responsePlotObservations.value.map(row => row.report_date),
    marker: { color: theme.SERIES[2], size: 7, opacity: 0.72 },
    hovertemplate: `%{customdata}<br>Budget ${symbol.value}%{x:,.2f}<br>Observed revenue ${symbol.value}%{y:,.2f}<extra></extra>`,
  });
  const decisions = [
    { label: "Initial", budget: allocation.initial_budget, revenue: allocation.expected_revenue_at_initial },
    { label: "Optimized", budget: allocation.optimized_budget, revenue: allocation.expected_revenue_at_optimized },
  ].filter(row => Number.isFinite(row.budget) && Number.isFinite(row.revenue));
  if (decisions.length) traces.push({
    type: "scatter", mode: "markers+text", name: "Decision",
    x: decisions.map(row => row.budget), y: decisions.map(row => row.revenue),
    text: decisions.map(row => row.label), textposition: "top center",
    marker: { color: decisions.map(row => row.label === "Initial" ? theme.MUTED : theme.MODEL_COLORS.recommended), size: 12 },
    hovertemplate: `%{text}<br>Budget ${symbol.value}%{x:,.2f}<br>Expected revenue ${symbol.value}%{y:,.2f}<extra></extra>`,
  });
  return traces;
});
const responseCurveLayout = computed(() => {
  const observed = activeResponseModel.value.diagnostics?.observed_budget_range;
  const validRange = Array.isArray(observed) && observed.length === 2 && observed.every(Number.isFinite);
  return theme.layout({
    height: 430,
    xaxis: { title: { text: `Configured budget (${symbol.value.trim()})` }, range: [0, responseMaximum.value] },
    yaxis: { title: { text: `Revenue (${symbol.value.trim()})` } },
    shapes: validRange ? [
      { type: "rect", x0: 0, x1: observed[0], y0: 0, y1: 1, yref: "paper",
        fillcolor: "rgba(148,98,0,0.08)", line: { width: 0 }, layer: "below" },
      { type: "rect", x0: observed[1], x1: responseMaximum.value, y0: 0, y1: 1, yref: "paper",
        fillcolor: "rgba(148,98,0,0.08)", line: { width: 0 }, layer: "below" },
    ] : [],
  });
});

const allocationWaterfall = computed(() => {
  if (!allocations.value.length || allocations.value.some(row => !Number.isFinite(row.initial_budget) || !Number.isFinite(row.optimized_budget))) return [];
  const initial = allocations.value.reduce((total, row) => total + Number(row.initial_budget ?? 0), 0);
  return [{
    type: "waterfall", orientation: "v",
    measure: ["absolute", ...allocations.value.map(() => "relative"), "total"],
    x: ["Initial total", ...allocations.value.map((row) => row.campaign_id), "Optimized total"],
    y: [initial, ...allocations.value.map((row) => Number(row.optimized_budget) - Number(row.initial_budget)), 0],
    text: [theme.money(initial, symbol.value), ...allocations.value.map((row) =>
      theme.money(Number(row.optimized_budget) - Number(row.initial_budget), symbol.value)),
      theme.money(plan.value.allocated_budget, symbol.value)],
    textposition: "outside",
    increasing: { marker: { color: theme.DIVERGING[1] } },
    decreasing: { marker: { color: theme.DIVERGING[3] } },
    totals: { marker: { color: theme.MODEL_COLORS.recommended } },
    connector: { line: { color: theme.AXIS } },
    hovertemplate: "%{x}<br>%{text}<extra></extra>",
  }];
});
const allocationWaterfallLayout = computed(() => theme.layout({
  height: 360, legend: false, yaxis: { title: { text: "Budget" } },
}));

// ---------------------------------------------------------------------------
// Strategy evaluation
// ---------------------------------------------------------------------------

/**
 * The evaluation stage publishes an API artifact that this view does not yet
 * render. Its tab explains the implemented layers and exposes the same runner
 * as the other stages, while avoiding a partial visualization of the report.
 *
 * `evaluationAvailable` is the deployment's ability to start the stage, not
 * whether an evaluation artifact has already been produced.
 */
const evaluationAvailable = computed(
  () => stages.value.evaluation?.available ?? false,
);

</script>

<template>
  <section class="page-grid">
    <p class="caption">
      Each stage uses the selected dataset and its available evidence. A live
      backend with writable runtime storage provides execution controls.
    </p>

    <div class="tabs" role="tablist" aria-label="Models">
      <button
        v-for="entry in MODEL_TABS"
        :key="entry.key"
        class="tab"
        role="tab"
        :aria-selected="model === entry.key"
        :class="{ active: model === entry.key }"
        @click="emit('navigate', entry.key)"
      >
        {{ entry.label }}
      </button>
    </div>

    <article v-if="model === 'optimization'" class="card">
      <div class="card-head"><h2>Select Campaign to optimize</h2></div>
      <div class="card-body setting-group">
        <div class="setting-row"><div class="setting-label"><label for="optimizer-campaign-search">Find Campaign</label><small>Type a name, identifier, provider or ad product to narrow the choices.</small></div><div class="setting-control"><input id="optimizer-campaign-search" v-model="campaignSearch" type="search" placeholder="Type to match Campaigns" /></div></div>
        <div class="setting-row"><div class="setting-label"><label for="optimizer-campaign">Campaign</label><small>Select the Campaign that will receive the strategy recommendation.</small></div><div class="setting-control"><select id="optimizer-campaign" v-model="selectedCampaign" @change="chooseCampaign"><option value="">Select a Campaign</option><option v-if="selectedCampaign && !matchingCampaigns.some(row => row.campaign_id === selectedCampaign)" :value="selectedCampaign">{{ selectedCampaign }} · current selection</option><option v-for="row in matchingCampaigns" :key="row.campaign_id" :value="row.campaign_id">{{ row.campaign_name || row.campaign_id }} · {{ row.campaign_id }}</option></select></div></div>
        <p v-if="!matchingCampaigns.length" role="status">No Campaigns match this search.</p>
        <div class="setting-row"><div class="setting-label"><label for="optimizer-marketplace">Marketplace</label><small>Use the recorded marketplace code, such as US or CA.</small></div><div class="setting-control"><input id="optimizer-marketplace" v-model.lazy="selectedMarketplace" type="text" /></div></div>
      </div>
    </article>
    <article v-if="scopedPreview" class="card">
      <div class="card-head"><h2>Optimize {{ selectedCampaign }}</h2><TermHelp :term="optimizerHelp" /></div>
      <div class="card-body"><p>{{ selectedMarketplace }} · {{ campaignSource === 'legacy' ? 'Configured source' : campaignSource }} · Historical Campaign strategy</p>
        <p>Use valid historical records to recommend a daily budget. Full dataset includes compatible Campaigns across the complete recorded period.</p>
        <div class="setting-group"><div class="setting-row"><div class="setting-label"><label for="optimizer-history-mode">History source</label><small>Full dataset uses compatible Campaign records when this Campaign has insufficient history.</small></div><div class="setting-control"><select id="optimizer-history-mode" v-model="historyMode"><option value="full">Full dataset · similar history</option><option value="campaign">This Campaign only</option></select></div></div></div>
        <div class="setting-group">
          <div class="setting-row"><div class="setting-label"><label for="optimizer-initial-budget">Initial daily budget</label><small>Comparison baseline in the selected currency; leave blank to use history. This does not change the authorized budget cap.</small></div><div class="setting-control"><input id="optimizer-initial-budget" v-model.number="initialBudget" type="number" min="0.01" step="0.01" placeholder="Historical default" :aria-invalid="initialBudget !== '' && Boolean(inputError)" /></div></div>
          <div class="setting-row"><div class="setting-label"><label for="optimizer-similarity-threshold">Similarity threshold</label><TermHelp :term="similarityHelp" /><small>0 includes all compatible budgets; 1 requires an exact budget match. Applies to Full dataset references.</small></div><div class="setting-control"><input id="optimizer-similarity-threshold" v-model.number="similarityThreshold" type="number" min="0" max="1" step="0.05" :disabled="historyMode !== 'full'" :aria-invalid="historyMode === 'full' && Boolean(inputError)" /></div></div>
        </div>
        <p v-if="inputError" role="alert">{{ inputError }}</p>
        <p v-else-if="!preview && !previewBusy && !previewError" role="status">Select Recompute strategy to apply these settings.</p>
        <p v-if="preview">Initial daily budget used: {{ theme.money(preview.initial_strategy?.allocations?.[0]?.initial_budget, symbol) }}.</p>
        <p v-if="preview?.history_selection">{{ preview.history_selection.target_observation_count }} own observations · {{ preview.history_selection.reference_observation_count }} comparable observations. Reference Campaigns: {{ preview.history_selection.reference_campaign_ids.join(', ') || 'None' }}.</p>
        <p v-if="previewBusy" role="status">Fitting historical response and computing the strategy…</p>
        <p v-if="previewError" role="alert">{{ previewError }}</p>
        <p v-if="preview">{{ preview.observation_count }} valid observations · {{ evidenceWindow }}. {{ preview.history_selection?.excluded_observation_count ?? 0 }} unmatched or invalid observations excluded.</p>
        <section v-if="preview?.historical_recommendation" aria-label="Historical baseline recommendation">
          <h3>Historical baseline recommendation</h3>
          <p>{{ preview.historical_recommendation.reason }}</p>
          <div class="setting-row"><div class="setting-label">Recommended daily budget</div><div class="setting-control">{{ theme.money(preview.historical_recommendation.recommended_budget, symbol) }}</div></div>
          <p>Reference averages at this budget: spend {{ theme.money(preview.historical_recommendation.mean_observed_spend, symbol) }}, revenue {{ theme.money(preview.historical_recommendation.mean_observed_revenue, symbol) }} across {{ preview.historical_recommendation.observation_count }} observations.</p>
        </section>
        <div class="rec-actions"><button :disabled="previewBusy || IS_STATIC || Boolean(inputError) || !selectedMarketplace.trim()" @click="computeCampaign">Recompute strategy</button></div>
      </div>
    </article>
    <WorkbenchRunner v-else-if="selectedDatasetId" :key="`${selectedDatasetId}:${model}`" :stage="model" />
    <article v-else-if="stages[model]" class="card">
      <div class="card-head">
        <h2>Run {{ stages[model].label }} <TermHelp v-if="model === 'optimization'" :term="optimizerHelp" /></h2>
        <span class="sub">{{ stages[model].script || "No runnable script" }}</span>
      </div>
      <div class="card-body">
        <div v-if="jobError" class="notice bad">{{ jobError.message }}</div>
        <StageRunner
          :stage="stages[model]"
          :busy="jobBusy"
          :controls="STAGE_CONTROLS[model] ?? []"
          @start="startStage(model, $event)"
          @stop="stopStage(model)"
          @upload="uploadOutputs(model, $event)"
          @import="importOutputs(model)"
          @reload="reloadAfterRun"
        />
      </div>
    </article>

    <section v-if="selectedDatasetId && !scopedPreview" class="panel" aria-label="Displayed result provenance">
      <template v-if="data.runProvenance?.[model]">
        <h2>Displayed {{ model }} result</h2>
        <p>Run {{ data.runProvenance[model].id }} · Completed {{ data.runProvenance[model].finishedAt }} · Plan revision {{ data.runProvenance[model].revision ?? 'No saved plan' }}</p>
        <p class="caption">Dataset {{ data.runProvenance[model].datasetId }} · Input fingerprint {{ data.runProvenance[model].datasetDigest }}</p>
        <a href="#/log/provenance">Inspect retained run records and artifacts</a>
      </template>
      <p v-else>Not run for this dataset. No stored {{ model }} result is displayed.</p>
    </section>
    <p v-if="model !== 'evaluation' && !scopedPreview" class="caption">
      Stored result evidence · {{ evidenceWindow }} · {{ symbol.trim() }}.
      Historical date filters do not refit these models or change their stored predictions.
    </p>

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
          <h2>Markov–Shapley disagreement</h2>
          <span class="sub">{{ OUTCOME_LABELS[outcome] }} · longest connector is the largest gap</span>
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
            Connector length is model disagreement. Largest gap:
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
          <EntityTable
            :row-key="row => `${row.outcome}:${row.touchpoint}`"
            noun="attribution recommendation"
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
              :columns="evidenceColumns(shiftColumns)"
              :rows="shiftRows"
            />
          </template>
        </div>
      </article>
    </template>

    <article v-else-if="model === 'attribution'" class="card empty-card">
      <h2>No attribution output</h2>
      <p>
        Not run. No attribution output is selected for this source. Use the available stage controls above to run or open a matching result.
      </p>
    </article>

    <!-- 2. MTA strategy optimization -->
    <template v-if="model === 'optimization'">
      <template v-if="hasPlan && isOptimized">
        <MetricRow :items="planMetrics" />

        <article class="card">
          <div class="card-head">
            <h2>Campaign response curve</h2>
            <span class="sub">Observed points, fitted response, and decision</span>
          </div>
          <div class="card-body">
            <div class="filter-row">
              <div class="field">
                <label for="response-campaign">Campaign</label>
                <select
                  id="response-campaign"
                  :value="activeResponseCampaign"
                  @change="responseCampaign = $event.target.value"
                >
                  <option v-for="campaign in responseCampaigns" :key="campaign" :value="campaign">
                    {{ campaign }}
                  </option>
                </select>
              </div>
            </div>
            <PlotlyChart
              v-if="responseCurveTraces.length"
              :traces="responseCurveTraces"
              :layout="responseCurveLayout"
              label="Fitted campaign budget response with observations and initial and optimized budgets"
            />
            <p v-else class="table-empty">No fitted response model is available.</p>
            <p v-if="!responseCurveValues.length" class="notice">Insufficient evidence: complete fitted response parameters are unavailable. No response prediction is drawn.</p>
            <p class="caption">
              {{ responseObservations.length.toLocaleString() }} stored observations;
              {{ responsePlotObservations.length.toLocaleString() }} plotted{{ responseObservations.length > 500 ? ' (deterministic sample)' : '' }}.
              Support: {{ pretty(activeResponseModel.diagnostics?.support ?? activeAllocation.response_support ?? 'UNAVAILABLE') }}.
              Fit observations: {{ activeResponseModel.diagnostics?.observation_count ?? 'Unavailable' }}.
              Observed budget range: {{ theme.money(activeResponseModel.diagnostics?.observed_budget_range?.[0], symbol) }} to {{ theme.money(activeResponseModel.diagnostics?.observed_budget_range?.[1], symbol) }}.
            </p>
            <TableView label="View fitted response values" :columns="responseValueColumns" :rows="responseCurveValues" />
            <EntityTable :columns="responseObservationColumns" :rows="responseObservations" :row-key="responseRowKey" noun="response observation" />
            <p class="caption">
              Amber shading is outside the observed budget range. A decision in
              that area is extrapolated visibly rather than reduced to a flag.
            </p>
          </div>
        </article>

        <article class="card">
          <div class="card-head">
            <h2>Allocation waterfall</h2>
            <span class="sub">Initial total → Campaign shifts → optimized total</span>
          </div>
          <div class="card-body">
            <PlotlyChart
              :traces="allocationWaterfall"
              :layout="allocationWaterfallLayout"
              label="Budget allocation waterfall from initial to optimized total"
            />
          </div>
        </article>

        <article class="card">
          <div class="card-head">
            <h2>Optimized Campaign budget</h2>
            <span class="sub">{{ allocations.length }} Campaigns</span>
          </div>
          <div class="card-body">
            <EntityTable
              :row-key="row => row.campaign_id"
              noun="Campaign allocation"
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
                  {{ theme.money(row.observed_budget_range?.[0], symbol) }} to
                  {{ theme.money(row.observed_budget_range?.[1], symbol) }} range
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

      <article v-else-if="hasPlan && !strategy.historical_recommendation" class="card">
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

      <article v-else-if="!scopedPreview" class="card empty-card">
        <h2>No optimized strategy</h2>
        <p>
          Not run. The budget response models have not been fitted against the current
          data. Run the stage above to fit them and optimize.
        </p>
      </article>
    </template>

    <!-- 3. MTA strategy evaluation -->
    <template v-if="model === 'evaluation'">
      <article class="card">
        <div class="card-head">
          <h2>Strategy evaluation</h2>
          <span class="sub">Runnable assurance stage</span>
        </div>
        <div class="card-body">
          <p>
            This layer scores a strategy the way
            <code>modules/mta_standard</code> scores an attribution model:
            project both strategy artifacts into one validated contract, check
            conservation, and compare an allocation with observed baselines
            when every allocated Campaign has observations. Ground-truth
            scoring remains explicitly not run because the simulator does not
            publish a true optimal strategy allocation.
          </p>
          <p class="caption">
            Run the stage above to publish
            <code>strategy_evaluation.json</code>. Willow Sakura’s contributed
            interactive neural-network forecast is rendered below as native
            dashboard widgets, separate from production recommendations.
          </p>
          <div v-if="!selectedDatasetId && !evaluationAvailable" class="notice">
            This deployment cannot start the evaluation command. Run the
            dashboard in a writable deployment, or execute
            <code>uv run --extra strategy-evaluation python -m modules.mta_strategy_evaluation.src.evaluate_strategies</code> from a terminal.
          </div>
        </div>
      </article>

      <EvaluationReport :report="data.strategyEvaluation" :run="data.runProvenance?.evaluation ?? {}" />
      <p class="notice">Demonstration · Willow forecast is independent from the selected dataset and production evaluation.</p>
      <WillowGmvForecast />
    </template>
  </section>
</template>
