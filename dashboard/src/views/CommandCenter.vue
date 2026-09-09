<script setup>
/**
 * Command Center: the headline state of the account.
 *
 * Answers three questions in order -- what was spent and returned, which
 * touchpoints the models credit, and whether that credit is trustworthy. The
 * reliability verdict sits beside the attribution figures rather than in a
 * footnote, because an unreliable share must not be read as a fact.
 */
import { computed, ref } from "vue";

import MetricRow from "../components/MetricRow.vue";
import PlotlyChart from "../components/PlotlyChart.vue";
import DataTable from "../components/DataTable.vue";
import TableView from "../components/TableView.vue";
import {
  OUTCOME_LABELS,
  currencySymbol,
  distinct,
  groupSum,
  pretty,
  shortDate,
  statusTone,
  sum,
} from "../lib/common.js";
import { useDashboard } from "../lib/useDashboard.js";
import { aggregatePerformance, safeRatio } from "../lib/chartData.js";
import * as theme from "../theme.js";

const { data } = useDashboard();

const currency = computed(() =>
  currencySymbol(data.value.dataset?.scope?.currency ?? data.value.dashboardContext?.currency ?? data.value.strategyRequest?.campaign_group?.currency ?? "USD"),
);

const totals = computed(() => {
  const ads = data.value.adsDaily;
  const spend = sum(ads, "cost");
  const sales = sum(ads, "sales");
  return {
    spend: ads.length ? spend : null,
    sales: ads.length ? sales : null,
    roas: ads.length ? safeRatio(sales, spend) : null,
    days: distinct(ads, "report_date").length,
    touchpoints: distinct(ads, "touchpoint").length,
  };
});

const tiles = computed(() => {
  const budget = data.value.budgetRecommendation ?? {};
  return [
    { label: "Total spend", value: theme.compactMoney(totals.value.spend, currency.value) },
    { label: "Reported sales", value: theme.compactMoney(totals.value.sales, currency.value) },
    { label: "Blended ROAS", value: theme.ratio(totals.value.roas) },
    ...["purchases", "impressions", "clicks"].map(key => ({ label: pretty(key), value: data.value.adsDaily.length ? theme.count(sum(data.value.adsDaily, key)) : "--" })),
    {
      label: "Touchpoints",
      value: theme.count(totals.value.touchpoints),
      help: "Distinct interaction keys observed in this dataset.",
    },
    {
      label: "Recommended budget",
      value: theme.compactMoney(budget.budget_seed_total, currency.value),
      note: budget.budget_seed_total == null ? "Not run for this dataset" : `Daily total across ${(budget.campaigns ?? []).length} Campaigns`,
    },
  ];
});

const grain = ref("day");
const daily = computed(() => aggregatePerformance(data.value.adsDaily, grain.value));
const spendTraces = computed(() => daily.value.length ? [{
  type: "scatter", mode: "lines+markers", name: "Return on ad spend",
  x: daily.value.map(row => row.key), y: daily.value.map(row => row.roas),
  connectgaps: false, line: { color: theme.SERIES[1], width: 2.5 },
  hovertemplate: "%{x}<br>ROAS %{y:.2f}x<extra></extra>",
}] : []);
const amountTraces = computed(() => daily.value.length ? ["cost", "sales"].map((field, index) => ({
  type: "scatter", mode: "lines+markers", name: field === "cost" ? "Spend" : "Reported sales",
  x: daily.value.map(row => row.key), y: daily.value.map(row => row[field]),
  connectgaps: false, line: { color: theme.SERIES[index], width: 2 },
  hovertemplate: "%{x}<br>%{y:,.2f}<extra>%{fullData.name}</extra>",
})) : []);
const spendLayout = computed(() => theme.layout({ height: 300,
  yaxis: { title: { text: "Return on ad spend" }, ticksuffix: "x" },
}));
const amountLayout = computed(() => theme.layout({ height: 300,
  yaxis: { title: { text: `Amount (${data.value.dataset?.scope?.currency ?? data.value.dashboardContext?.currency ?? currency.value})` } },
}));

const dailyColumns = [
  { key: "key", label: "Period starting" },
  { key: "cost", label: "Spend", format: value => theme.money(value, currency.value) },
  { key: "sales", label: "Reported sales", format: value => theme.money(value, currency.value) },
  { key: "roas", label: "ROAS", format: (value) => theme.ratio(value) },
];

/** Per-outcome verdict on whether the two models agree. */
const summaryRows = computed(() =>
  data.value.comparisonSummary.map((row) => ({
    ...row,
    outcome_label: OUTCOME_LABELS[row.outcome] ?? row.outcome,
  })),
);

const summaryColumns = [
  { key: "outcome_label", label: "Outcome" },
  { key: "tvd", label: "TVD", format: "share" },
  { key: "spearman_rho", label: "Spearman", format: "share", digits: 3 },
  { key: "top_k_overlap_rate", label: "Top-K overlap", format: "share", digits: 2 },
  { key: "touchpoint_count", label: "Touchpoints", format: "number" },
];

/** Where the credit lands, by ad product, for each model. */
const byProduct = computed(() => {
  const rows = data.value.attributionResults;
  const models = [...new Set(rows.map((row) => row.attribution_model))].sort();
  const order = groupSum(rows, "ad_product", ["attributed_revenue"])
    .sort((a, b) => a.attributed_revenue - b.attributed_revenue)
    .map((entry) => entry.key);

  return models.map((model) => {
    const scoped = groupSum(
      rows.filter((row) => row.attribution_model === model),
      "ad_product",
      ["attributed_revenue"],
    );
    const lookup = new Map(scoped.map((entry) => [entry.key, entry.attributed_revenue]));
    return {
      type: "bar",
      orientation: "h",
      name: pretty(model),
      y: order.map(pretty),
      x: order.map((key) => lookup.get(key) ?? 0),
      marker: {
        color: theme.MODEL_COLORS[model] ?? theme.SERIES[0],
        line: { color: theme.SURFACE, width: 2 },
      },
      hovertemplate:
        `<b>${pretty(model)}</b><br>%{y}<br>` +
        `Attributed revenue (${data.value.dataset?.scope?.currency ?? data.value.dashboardContext?.currency ?? "USD"}) %{x:,.2f}<extra></extra>`,
    };
  });
});

const productLayout = computed(() =>
  theme.layout({
    height: 300,
    barmode: "group",
    bargroupgap: 0.08,
    xaxis: { title: { text: "Attributed revenue" } },
  }),
);

const productRows = computed(() =>
  groupSum(data.value.attributionResults, (row) => `${row.ad_product}|${row.attribution_model}`, [
    "attributed_revenue",
    "cost",
  ]).map((entry) => {
    const [product, model] = entry.key.split("|");
    return {
      product: pretty(product),
      model: pretty(model),
      attributed_revenue: entry.attributed_revenue,
      cost: entry.cost,
    };
  }),
);

const productColumns = [
  { key: "product", label: "Ad product" },
  { key: "model", label: "Model" },
  { key: "attributed_revenue", label: "Attributed revenue", format: value => theme.money(value, currency.value) },
  { key: "cost", label: "Cost", format: value => theme.money(value, currency.value) },
];
</script>

<template>
  <section class="page-grid">
    <p class="caption">
      Attribution evidence and budget readiness for the current report window.
    </p>

    <div class="field">
      <label for="overview-group">Group observations</label>
      <select id="overview-group" v-model="grain"><option value="day">Daily</option><option value="week">Weekly (Monday)</option><option value="month">Monthly</option></select>
    </div>
    <MetricRow :items="tiles" />
    <p v-if="data.runProvenance?.attribution" class="caption">Attribution result {{ data.runProvenance.attribution.id }} · Completed {{ data.runProvenance.attribution.finishedAt }} · Dataset {{ data.runProvenance.attribution.datasetId }}. <a href="#/optimizer/attribution">Inspect attribution evidence</a></p>
    <div v-if="data.dataset" class="rec-actions">
      <a v-if="data.dataset.capabilities?.attribution?.available" class="btn" href="#/optimizer/attribution">Run attribution</a>
      <a v-if="data.dataset.capabilities?.history?.available" class="btn" href="#/campaigns/history">Explore Campaign history</a>
      <a v-if="data.dataset.capabilities?.optimization?.available" class="btn primary" href="#/budget/plans">Create a budget plan</a>
      <a class="btn" href="#/campaigns/performance">Explore performance</a>
    </div>
    <p class="caption">
      {{ data.adsDaily.length.toLocaleString() }} source rows · {{ data.source }}. Window covers {{ totals.days }} days of platform-reported performance. Spend
      and sales are what the platform reported; attributed values below are what
      the models assigned.
    </p>

    <article class="card">
      <div class="card-head"><h2>Spend and reported sales</h2><span class="sub">Observed amounts · {{ currency }}</span></div>
      <div class="card-body">
        <PlotlyChart v-if="amountTraces.length" :traces="amountTraces" :layout="amountLayout" label="Observed spend and sales by selected calendar period" />
        <p v-else class="table-empty">No performance observations. Generate or import a dataset to begin.</p>
        <TableView :columns="dailyColumns" :rows="daily" label="View grouped performance values" />
      </div>
    </article>
    <div class="page-grid two-up">
      <article class="card">
        <div class="card-head">
          <h2>Return on ad spend</h2>
          <span class="sub">Sales ÷ spend in each period</span>
        </div>
        <div class="card-body">
          <PlotlyChart
            v-if="spendTraces.length"
            :traces="spendTraces"
            :layout="spendLayout"
            label="Return on ad spend by selected calendar period"
          />
          <p v-else class="table-empty">No daily performance rows in this window.</p>
          <p class="caption">
            Ratios are recomputed from period totals. A period with no spend is
            unavailable, not a zero return. Amounts appear in the separate chart.
          </p>
          <TableView
            label="View daily values as a table"
            :columns="dailyColumns"
            :rows="daily"
          />
        </div>
      </article>

      <article class="card">
        <div class="card-head">
          <h2>Model agreement</h2>
        </div>
        <div class="card-body">
          <div class="panel">
            <div class="panel-title">Reliability by outcome</div>
            <div v-for="row in summaryRows" :key="row.outcome" class="kv">
              <span>{{ row.outcome_label }}</span>
              <span class="tag" :class="statusTone(row.reliability_status)">
                {{ row.reliability_status }}
              </span>
            </div>
          </div>
          <DataTable
            :columns="summaryColumns"
            :rows="summaryRows"
            empty="No comparison summary available."
          />
          <p class="caption">
            Diagnostics inform the reader. They never change the verdict, which
            AND-aggregates the per-touchpoint reliability flags. TVD is total
            variation distance; lower is closer.
          </p>
        </div>
      </article>
    </div>

    <article class="card">
      <div class="card-head">
        <h2>Attributed revenue by ad product</h2>
        <span class="sub">Both models, grouped</span>
      </div>
      <div class="card-body">
        <PlotlyChart
          v-if="byProduct.length"
          :traces="byProduct"
          :layout="productLayout"
          label="Attributed revenue by ad product, for each attribution model"
        />
        <p v-else class="table-empty">No attribution results available.</p>
        <p class="caption">
          Both models are shown because neither is authoritative on its own. The
          governed recommendation is in the Budget Manager view.
        </p>
        <TableView
          label="View attributed revenue as a table"
          :columns="productColumns"
          :rows="productRows"
        />
      </div>
    </article>
  </section>
</template>
