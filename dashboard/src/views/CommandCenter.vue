<script setup>
/**
 * Command Center: the headline state of the account.
 *
 * Answers three questions in order -- what was spent and returned, which
 * touchpoints the models credit, and whether that credit is trustworthy. The
 * reliability verdict sits beside the attribution figures rather than in a
 * footnote, because an unreliable share must not be read as a fact.
 */
import { computed } from "vue";

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
import * as theme from "../theme.js";

const { data } = useDashboard();

const currency = computed(() =>
  currencySymbol(data.value.strategyRequest?.campaign_group?.currency ?? "USD"),
);

const totals = computed(() => {
  const ads = data.value.adsDaily;
  const spend = sum(ads, "cost");
  const sales = sum(ads, "sales");
  return {
    spend,
    sales,
    roas: spend ? sales / spend : 0,
    days: distinct(ads, "report_date").length,
    touchpoints: distinct(data.value.attributionResults, "touchpoint").length,
  };
});

const tiles = computed(() => {
  const budget = data.value.budgetRecommendation ?? {};
  return [
    { label: "Total spend", value: theme.compactMoney(totals.value.spend, currency.value) },
    { label: "Reported sales", value: theme.compactMoney(totals.value.sales, currency.value) },
    { label: "Blended ROAS", value: theme.ratio(totals.value.roas) },
    {
      label: "Touchpoints",
      value: theme.count(totals.value.touchpoints),
      help: "Distinct five-segment interaction keys the models scored.",
    },
    {
      label: "Recommended budget",
      value: theme.compactMoney(budget.budget_seed_total ?? 0, currency.value),
      note: `Daily total across ${(budget.campaigns ?? []).length} Campaigns`,
    },
  ];
});

/** Daily return on ad spend, with spend retained as low-contrast context. */
const daily = computed(() =>
  groupSum(data.value.adsDaily, "report_date", ["cost", "sales"])
    .map((row) => ({ ...row, roas: row.cost ? row.sales / row.cost : 0 }))
    .sort((a, b) => a.key < b.key ? -1 : 1),
);

const spendTraces = computed(() => {
  const rows = daily.value;
  if (rows.length === 0) return [];
  const meanSpend = rows.reduce((total, row) => total + row.cost, 0) / rows.length;
  return [
    {
      type: "scatter", mode: "lines", name: "Spend context",
      x: rows.map((row) => row.key),
      y: rows.map((row) => meanSpend ? row.cost / meanSpend * totals.value.roas : 0),
      fill: "tozeroy", fillcolor: "rgba(42,120,214,0.10)",
      line: { color: "rgba(42,120,214,0.20)", width: 1 },
      customdata: rows.map((row) => row.cost),
      hovertemplate: "%{x}<br>Spend %{customdata:$,.2f}<extra></extra>",
    },
    {
      type: "scatter", mode: "lines+markers", name: "Daily ROAS",
      x: rows.map((row) => row.key), y: rows.map((row) => row.roas),
      line: { color: theme.SERIES[1], width: 2.5 }, marker: { size: 5 },
      customdata: rows.map((row) => [row.cost, row.sales]),
      hovertemplate: "<b>%{x}</b><br>ROAS %{y:.2f}x<br>Spend %{customdata[0]:$,.2f}<br>Sales %{customdata[1]:$,.2f}<extra></extra>",
    },
  ];
});

const spendLayout = computed(() =>
  theme.layout({
    height: 300,
    yaxis: { title: { text: "Return on ad spend" }, ticksuffix: "x" },
    shapes: [
      {
        type: "line",
        xref: "paper",
        x0: 0,
        x1: 1,
        y0: totals.value.roas,
        y1: totals.value.roas,
        line: { color: theme.AXIS, width: 1 },
      },
    ],
    annotations: [
      {
        xref: "paper",
        x: 1,
        y: totals.value.roas,
        yanchor: "bottom",
        xanchor: "right",
        text: `window average ${totals.value.roas.toFixed(2)}x`,
        showarrow: false,
        font: { size: 10, color: theme.MUTED },
      },
    ],
  }),
);

const dailyColumns = [
  { key: "key", label: "Date", format: (value) => shortDate(value) },
  { key: "cost", label: "Spend", format: "money" },
  { key: "sales", label: "Reported sales", format: "money" },
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
        "Attributed revenue %{x:$,.2f}<extra></extra>",
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
  { key: "attributed_revenue", label: "Attributed revenue", format: "money" },
  { key: "cost", label: "Cost", format: "money" },
];
</script>

<template>
  <section class="page-grid">
    <p class="caption">
      Attribution evidence and budget readiness for the current report window.
    </p>

    <MetricRow :items="tiles" />
    <p class="caption">
      Window covers {{ totals.days }} days of platform-reported performance. Spend
      and sales are what the platform reported; attributed values below are what
      the models assigned.
    </p>

    <div class="page-grid two-up">
      <article class="card">
        <div class="card-head">
          <h2>Daily return on ad spend</h2>
          <span class="sub">Spend remains as a light context band</span>
        </div>
        <div class="card-body">
          <PlotlyChart
            v-if="spendTraces.length"
            :traces="spendTraces"
            :layout="spendLayout"
            label="Daily return on ad spend against its window average with spend context"
          />
          <p v-else class="table-empty">No daily performance rows in this window.</p>
          <p class="caption">
            The line answers whether spend earned its return. The shaded band
            shows relative spend pressure without adding a second axis.
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
