<script setup>
/**
 * Campaigns: historical performance, filterable and queryable.
 *
 * The one place a reader can interrogate the raw record -- daily platform
 * performance, the Campaign and Ad Group bridge, and the conversion paths. All
 * filters sit in a single row above the charts, so every panel on the page
 * shows the same slice.
 */
import { computed, ref } from "vue";

import DataTable from "../components/DataTable.vue";
import EntityTable from "../components/EntityTable.vue";
import MetricRow from "../components/MetricRow.vue";
import PlotlyChart from "../components/PlotlyChart.vue";
import {
  distinct,
  groupSum,
  pretty,
  shortDate,
  shortTouchpoint,
  sortBy,
  sum,
} from "../lib/common.js";
import { useDashboard } from "../lib/useDashboard.js";
import { useDiagnostics } from "../lib/diagnostics.js";
import * as theme from "../theme.js";

const { data } = useDashboard();
const { diagnosticsOn } = useDiagnostics();

const tab = ref("history");
const TABS = [
  { key: "history", label: "Budget history" },
  { key: "performance", label: "Daily performance" },
  { key: "bridge", label: "Campaign bridge" },
  { key: "paths", label: "Conversion paths" },
];

// ---------------------------------------------------------------------------
// Campaign budget and spend history
// ---------------------------------------------------------------------------

const research = computed(() => data.value.simulationResearch ?? {});
const historyProvider = ref("");
const historyProduct = ref("");
const historyCampaign = ref("");
const historyAdProduct = ref("");
const historyMarketplace = ref("");
const historyRun = ref("");
const historyFrom = ref("");
const historyTo = ref("");
const similarityOpen = ref(false);
const similarityCampaign = ref("");
const similarityProduct = ref("");
const similarityProvider = ref("");
const similarityAdProduct = ref("");
const similarityBudget = ref("");
const similarityThreshold = ref(0.6);

const campaignById = computed(() => new Map(
  (research.value.campaigns ?? []).map((item) => [item.campaign_id, item]),
));

const budgetHistory = computed(() =>
  (research.value.history ?? []).map((row) => {
    const campaign = campaignById.value.get(row.campaign_id) ?? {};
    return {
      ...row,
      provider: row.provider ?? campaign.provider ?? null,
      ad_product: row.ad_product ?? campaign.ad_product ?? null,
      campaign_name: campaign.campaign_name ?? row.campaign_id,
    };
  }),
);

const historyDates = computed(() => distinct(budgetHistory.value, "report_date"));
const historyProviders = computed(() => distinct(budgetHistory.value, "provider"));
const historyProducts = computed(() => distinct(budgetHistory.value, "product_id"));
const historyCampaigns = computed(() => distinct(budgetHistory.value, "campaign_id"));
const historyAdProducts = computed(() => distinct(budgetHistory.value, "ad_product"));
const historyMarketplaces = computed(() => distinct(budgetHistory.value, "marketplace"));
const historyRuns = computed(() => distinct(budgetHistory.value, "run_id"));

const scopedHistory = computed(() => budgetHistory.value.filter((row) => {
  if (historyProvider.value && row.provider !== historyProvider.value) return false;
  if (historyProduct.value && row.product_id !== historyProduct.value) return false;
  if (historyCampaign.value && row.campaign_id !== historyCampaign.value) return false;
  if (historyAdProduct.value && row.ad_product !== historyAdProduct.value) return false;
  if (historyMarketplace.value && row.marketplace !== historyMarketplace.value) return false;
  if (historyRun.value && row.run_id !== historyRun.value) return false;
  if (historyFrom.value && row.report_date < historyFrom.value) return false;
  if (historyTo.value && row.report_date > historyTo.value) return false;
  return true;
}));

const productsByCampaign = computed(() => {
  const values = new Map();
  for (const link of research.value.campaignProductLinks ?? []) {
    if (!values.has(link.campaign_id)) values.set(link.campaign_id, new Set());
    values.get(link.campaign_id).add(link.product_id);
  }
  return values;
});

const scopedDelivery = computed(() => (research.value.delivery ?? []).filter((row) => {
  const campaign = campaignById.value.get(row.campaign_id) ?? {};
  if (historyProvider.value && row.provider !== historyProvider.value) return false;
  if (historyProduct.value && !productsByCampaign.value.get(row.campaign_id)?.has(historyProduct.value)) return false;
  if (historyCampaign.value && row.campaign_id !== historyCampaign.value) return false;
  if (historyAdProduct.value && campaign.ad_product !== historyAdProduct.value) return false;
  if (historyMarketplace.value && row.marketplace !== historyMarketplace.value) return false;
  if (historyRun.value && row.run_id !== historyRun.value) return false;
  if (historyFrom.value && row.report_date < historyFrom.value) return false;
  if (historyTo.value && row.report_date > historyTo.value) return false;
  return true;
}));

const historyTiles = computed(() => {
  const spend = sum(scopedHistory.value, "actual_spend");
  const impressions = sum(scopedDelivery.value, "impressions");
  const clicks = sum(scopedDelivery.value, "clicks");
  const deliveryCost = sum(scopedDelivery.value, "cost");
  const economicsComplete = scopedHistory.value.length > 0 && scopedHistory.value.every(
    (row) => row.contribution_profit !== null && row.contribution_profit !== undefined,
  );
  return [
    { label: "Configured budget", value: theme.compactMoney(sum(scopedHistory.value, "configured_budget")) },
    { label: "Actual spend", value: theme.compactMoney(spend) },
    { label: "Impressions", value: theme.count(impressions) },
    { label: "Clicks", value: theme.count(clicks) },
    { label: "CTR", value: theme.percent(impressions ? clicks / impressions : 0) },
    { label: "CPC", value: theme.money(clicks ? deliveryCost / clicks : 0) },
    { label: "CPM", value: theme.money(impressions ? deliveryCost * 1000 / impressions : 0) },
    { label: "Purchases", value: theme.count(sum(scopedDelivery.value, "reported_purchases")) },
    { label: "Units", value: theme.count(sum(scopedHistory.value, "total_units")) },
    { label: "Revenue", value: theme.compactMoney(sum(scopedHistory.value, "total_revenue")) },
    { label: "Contribution profit", value: economicsComplete
      ? theme.compactMoney(sum(scopedHistory.value, "contribution_profit"))
      : "Unavailable" },
  ];
});

const interactionHistoryTraces = computed(() => {
  const rows = groupSum(scopedDelivery.value, "interaction_type", [
    "impressions", "clicks", "cost", "reported_purchases", "reported_sales",
  ]);
  return [{
    type: "bar",
    x: rows.map((row) => row.key || "Unavailable"),
    y: rows.map((row) => row.cost),
    text: rows.map((row) => `${theme.count(row.impressions)} imp · ${theme.count(row.clicks)} clicks`),
    textposition: "outside",
    marker: { color: theme.SERIES[2] },
    hovertemplate: "%{x}<br>Spend %{y:$,.2f}<br>%{text}<extra></extra>",
  }];
});
const interactionHistoryLayout = computed(() => theme.layout({
  height: 300, legend: false, yaxis: { title: { text: "Spend" } },
}));

const budgetHistoryTraces = computed(() => {
  const campaigns = distinct(scopedHistory.value, "campaign_id");
  const colors = theme.seriesColors(campaigns);
  return campaigns.map((campaign) => {
    const rows = scopedHistory.value.filter((row) => row.campaign_id === campaign);
    return {
      type: "scatter",
      mode: "markers",
      name: campaign,
      x: rows.map((row) => row.configured_budget),
      y: rows.map((row) => row.actual_spend),
      customdata: rows.map((row) => [row.report_date, row.budget_level]),
      marker: { color: colors[campaign], size: 8, opacity: 0.68 },
      hovertemplate:
        `<b>${campaign}</b><br>%{customdata[0]} · %{customdata[1]}×<br>` +
        "Budget %{x:$,.2f}<br>Spend %{y:$,.2f}<extra></extra>",
    };
  });
});
const budgetHistoryLayout = computed(() => {
  const highest = Math.max(
    1,
    ...scopedHistory.value.flatMap((row) => [row.configured_budget, row.actual_spend].map(Number)),
  );
  return theme.layout({
    height: 360,
    xaxis: { title: { text: "Configured budget" }, range: [0, highest * 1.04] },
    yaxis: { title: { text: "Actual spend" }, range: [0, highest * 1.04] },
    shapes: [{
      type: "line", x0: 0, y0: 0, x1: highest, y1: highest,
      line: { color: theme.AXIS, width: 1.5, dash: "dash" },
    }],
  });
});

const historicalColumns = [
  { key: "report_date", label: "Date" },
  { key: "run_id", label: "Run" },
  { key: "provider", label: "Provider" },
  { key: "product_id", label: "Product" },
  { key: "campaign_id", label: "Campaign" },
  { key: "ad_product", label: "Ad product" },
  { key: "marketplace", label: "Marketplace" },
  { key: "budget_level", label: "Level", format: "number" },
  { key: "configured_budget", label: "Budget", format: "money" },
  { key: "actual_spend", label: "Spend", format: "money" },
  { key: "total_units", label: "Units", format: "number" },
  { key: "total_revenue", label: "Revenue", format: "money" },
  { key: "contribution_profit", label: "Contribution profit", format: "money" },
];

const similarityMatches = computed(() => {
  const selectedCampaign = campaignById.value.get(similarityCampaign.value) ?? {};
  const profile = {
    provider: similarityProvider.value || selectedCampaign.provider || null,
    product_id: similarityProduct.value || null,
    ad_product: similarityAdProduct.value || selectedCampaign.ad_product || null,
    budget: Number(similarityBudget.value) || null,
  };
  const candidates = new Map();
  for (const row of budgetHistory.value) {
    const key = [row.run_id, row.campaign_id, row.product_id, row.report_date].join("|");
    if (!candidates.has(key)) candidates.set(key, []);
    candidates.get(key).push(row);
  }
  return [...candidates.values()].map((rows) => {
    const first = rows[0];
    const components = [];
    if (profile.provider) components.push(first.provider === profile.provider ? 1 : 0);
    if (profile.product_id) components.push(first.product_id === profile.product_id ? 1 : 0);
    if (profile.ad_product) components.push(first.ad_product === profile.ad_product ? 1 : 0);
    if (profile.budget) {
      const distance = Math.abs(Number(first.configured_budget ?? 0) - profile.budget);
      components.push(Math.max(0, 1 - distance / Math.max(profile.budget, 1)));
    }
    const score = components.length
      ? components.reduce((total, value) => total + value, 0) / components.length
      : 0;
    const subjectId = similarityCampaign.value || similarityProduct.value || "temporary-profile";
    const comparableId = similarityCampaign.value
      ? first.campaign_id
      : (first.product_id || first.campaign_id);
    return {
      subject_type: similarityCampaign.value ? "CAMPAIGN" : "PRODUCT",
      subject_id: subjectId,
      comparable_id: comparableId,
      similarity_score: score,
      rationale: `Equal-weight match across ${components.length} selected profile component(s).`,
      generated_by: "dashboard-selector-profile-v1",
      run_id: first.run_id,
      provider: first.provider,
      product_id: first.product_id,
      campaign_id: first.campaign_id,
      historical_period: first.report_date,
      budget: sum(rows, "configured_budget"),
      spend: sum(rows, "actual_spend"),
      revenue: sum(rows, "total_revenue"),
      contribution_profit: rows.every((row) => row.contribution_profit != null)
        ? sum(rows, "contribution_profit") : null,
      touchpoint_summary: `${first.ad_product ?? 'Unknown'} · ${rows.length} budget level(s)`,
    };
  }).filter((row) => row.subject_id !== row.comparable_id)
    .filter((row) => row.similarity_score >= similarityThreshold.value)
    .sort((left, right) => right.similarity_score - left.similarity_score);
});

const similarityColumns = [
  { key: "similarity_score", label: "Similarity", format: "percent" },
  { key: "provider", label: "Provider" },
  { key: "product_id", label: "Product" },
  { key: "campaign_id", label: "Campaign" },
  { key: "historical_period", label: "Period" },
  { key: "budget", label: "Budget", format: "money" },
  { key: "spend", label: "Spend", format: "money" },
  { key: "revenue", label: "Revenue", format: "money" },
  { key: "contribution_profit", label: "Contribution profit", format: "money" },
  { key: "touchpoint_summary", label: "Performance summary" },
];

// ---------------------------------------------------------------------------
// Daily performance
// ---------------------------------------------------------------------------

const ads = computed(() => data.value.adsDaily);

const dates = computed(() => distinct(ads.value, "report_date"));
const from = ref("");
const to = ref("");
const product = ref("");
const placement = ref("");
const interaction = ref("");

const windowStart = computed(() => from.value || dates.value[0] || "");
const windowEnd = computed(() => to.value || dates.value[dates.value.length - 1] || "");

/** Every filter narrows the same frame, so all panels below show one slice. */
const scoped = computed(() =>
  ads.value.filter((row) => {
    if (windowStart.value && row.report_date < windowStart.value) return false;
    if (windowEnd.value && row.report_date > windowEnd.value) return false;
    if (product.value && row.ad_product !== product.value) return false;
    if (placement.value && row.placement !== placement.value) return false;
    if (interaction.value && row.interaction_type !== interaction.value) return false;
    return true;
  }),
);

const products = computed(() => distinct(ads.value, "ad_product"));
const placements = computed(() => distinct(ads.value, "placement"));
const interactions = computed(() => distinct(ads.value, "interaction_type"));

const performanceTiles = computed(() => {
  const spend = sum(scoped.value, "cost");
  const sales = sum(scoped.value, "sales");
  return [
    { label: "Spend", value: theme.compactMoney(spend) },
    { label: "Sales", value: theme.compactMoney(sales) },
    { label: "Impressions", value: theme.count(sum(scoped.value, "impressions")) },
    { label: "Clicks", value: theme.count(sum(scoped.value, "clicks")) },
    { label: "ROAS", value: theme.ratio(spend ? sales / spend : 0) },
  ];
});

/** Daily spend split by ad product. */
const spendByProduct = computed(() => {
  const names = distinct(scoped.value, "ad_product");
  const colors = theme.seriesColors(names);
  return names.map((name) => {
    const rows = groupSum(
      scoped.value.filter((row) => row.ad_product === name),
      "report_date",
      ["cost"],
    ).sort((a, b) => (a.key < b.key ? -1 : 1));
    return {
      type: "scatter",
      mode: "lines",
      name: pretty(name),
      x: rows.map((row) => row.key),
      y: rows.map((row) => row.cost),
      line: { color: colors[name], width: 2 },
      hovertemplate:
        `<b>${pretty(name)}</b><br>%{x}<br>Spend %{y:$,.2f}<extra></extra>`,
    };
  });
});

const spendLayout = computed(() =>
  theme.layout({ height: 300, yaxis: { title: { text: "Daily spend" } } }),
);

/** Spend against reported sales per touchpoint. */
const byTouchpoint = computed(() =>
  sortBy(
    groupSum(scoped.value, "touchpoint", ["cost", "sales", "impressions", "clicks"]),
    "cost",
    "desc",
  ),
);

const touchpointTraces = computed(() => {
  const rows = byTouchpoint.value;
  const largestVolume = Math.max(1, ...rows.map((row) => Number(row.impressions) + Number(row.clicks)));
  return [{
    type: "scatter",
    mode: "markers+text",
    x: rows.map((row) => row.cost),
    y: rows.map((row) => row.sales),
    text: rows.map((row) => shortTouchpoint(row.key)),
    textposition: "top center",
    textfont: { size: 9, color: theme.MUTED },
    customdata: rows.map((row) => [row.key, row.impressions, row.clicks,
      row.cost ? row.sales / row.cost : 0]),
    marker: {
      color: theme.SERIES[0], opacity: 0.74,
      size: rows.map((row) => 10 + 24 * Math.sqrt(
        (Number(row.impressions) + Number(row.clicks)) / largestVolume,
      )),
      line: { color: theme.SURFACE, width: 1 },
    },
    hovertemplate:
      "<b>%{customdata[0]}</b><br>Spend %{x:$,.2f}<br>Reported sales %{y:$,.2f}<br>" +
      "ROAS %{customdata[3]:.2f}x<br>%{customdata[1]:,.0f} impressions · " +
      "%{customdata[2]:,.0f} clicks<extra></extra>",
  }];
});

const touchpointLayout = computed(() => {
  const highest = Math.max(1, ...byTouchpoint.value.flatMap((row) => [row.cost, row.sales].map(Number)));
  return theme.layout({
    height: 440, legend: false,
    xaxis: { title: { text: "Spend" }, range: [0, highest * 1.08] },
    yaxis: { title: { text: "Reported sales" }, range: [0, highest * 1.08] },
    shapes: [{
      type: "line", x0: 0, y0: 0, x1: highest, y1: highest,
      line: { color: theme.AXIS, width: 1.5, dash: "dash" },
    }],
  });
});

const touchpointColumns = [
  { key: "key", label: "Touchpoint", format: (value) => shortTouchpoint(value) },
  { key: "cost", label: "Spend", format: "money" },
  { key: "sales", label: "Sales", format: "money" },
  { key: "impressions", label: "Impressions", format: "number" },
  { key: "clicks", label: "Clicks", format: "number" },
];

const scopedColumns = [
  { key: "report_date", label: "Date", format: (value) => shortDate(value) },
  { key: "touchpoint", label: "Touchpoint", format: (value) => shortTouchpoint(value) },
  { key: "impressions", label: "Impressions", format: "number" },
  { key: "clicks", label: "Clicks", format: "number" },
  { key: "cost", label: "Cost", format: "money" },
  { key: "purchases", label: "Purchases", format: "number" },
  { key: "sales", label: "Sales", format: "money" },
];

// ---------------------------------------------------------------------------
// Campaign bridge
// ---------------------------------------------------------------------------

const campaignFilter = ref("");
const adGroupFilter = ref("");

const bridge = computed(() =>
  data.value.entityBridge.filter((row) => {
    if (campaignFilter.value && row.campaign_id !== campaignFilter.value) return false;
    if (adGroupFilter.value && row.ad_group_id !== adGroupFilter.value) return false;
    return true;
  }),
);

const campaignIds = computed(() => distinct(data.value.entityBridge, "campaign_id"));
const adGroupIds = computed(() => distinct(data.value.entityBridge, "ad_group_id"));

const bridgeTraces = computed(() => {
  const rows = groupSum(bridge.value, "campaign_id", ["assisted_revenue"]);
  return [
    {
      type: "bar",
      x: rows.map((row) => row.key),
      y: rows.map((row) => row.assisted_revenue),
      name: "Assisted revenue",
      marker: { color: theme.SERIES[0], line: { color: theme.SURFACE, width: 2 } },
      hovertemplate: "<b>%{x}</b><br>Assisted revenue %{y:$,.2f}<extra></extra>",
    },
  ];
});

const bridgeLayout = computed(() =>
  theme.layout({
    height: 300,
    legend: false,
    yaxis: { title: { text: "Assisted revenue" } },
  }),
);

/** Five-segment interaction vocabulary, nested and sized only by additive cost. */
const touchpointTreemap = computed(() => {
  const nodes = new Map();
  for (const row of bridge.value) {
    const segments = String(row.touchpoint ?? "").split(":");
    if (segments.length !== 5) continue;
    for (let depth = 0; depth < segments.length; depth += 1) {
      const id = segments.slice(0, depth + 1).join(":");
      const parent = depth ? segments.slice(0, depth).join(":") : "";
      if (!nodes.has(id)) nodes.set(id, { id, parent, label: pretty(segments[depth]), value: 0 });
      nodes.get(id).value += Number(row.cost ?? 0);
    }
  }
  const rows = [...nodes.values()];
  return rows.length ? [{
    type: "treemap",
    ids: rows.map((row) => row.id),
    labels: rows.map((row) => row.label),
    parents: rows.map((row) => row.parent),
    values: rows.map((row) => row.value),
    branchvalues: "total",
    marker: { colorscale: theme.SEQUENTIAL },
    hovertemplate: "<b>%{label}</b><br>Spend %{value:$,.2f}<br>%{percentParent:.1%} of parent<extra></extra>",
  }] : [];
});
const touchpointTreemapLayout = computed(() => theme.layout({
  height: 440, legend: false, margin: { l: 4, r: 4, t: 4, b: 4 },
}));

const bridgeColumns = [
  { key: "campaign_id", label: "Campaign" },
  { key: "ad_group_id", label: "Ad Group" },
  { key: "touchpoint", label: "Touchpoint", format: (value) => shortTouchpoint(value) },
  { key: "keyword_text", label: "Keyword" },
  { key: "match_type", label: "Match" },
  { key: "unique_users", label: "Users", format: "number" },
  { key: "journey_count", label: "Journeys", format: "number" },
  { key: "cost", label: "Cost", format: "money" },
  { key: "assisted_converted_users", label: "Assisted users", format: "number" },
  { key: "assisted_purchase_count", label: "Assisted purchases", format: "number" },
  { key: "assisted_revenue", label: "Assisted revenue", format: "money" },
];

// ---------------------------------------------------------------------------
// Conversion paths
// ---------------------------------------------------------------------------

const paths = computed(() => data.value.pathReport);

/**
 * Highest revenue first. Filtering used to live here too; `EntityTable` owns it
 * now, so this only decides the order the table pages through.
 */
const sortedPaths = computed(() => sortBy(paths.value, "revenue", "desc"));

const pathTiles = computed(() => [
  { label: "Distinct paths", value: theme.count(paths.value.length) },
  { label: "Users", value: theme.count(sum(paths.value, "users")) },
  { label: "Converted users", value: theme.count(sum(paths.value, "converted_users")) },
  { label: "Revenue", value: theme.compactMoney(sum(paths.value, "revenue")) },
]);

const byLength = computed(() =>
  groupSum(paths.value, "path_length", ["users", "converted_users", "revenue"])
    .map((row) => ({
      ...row,
      conversion_rate: row.users ? row.converted_users / row.users : 0,
    }))
    .sort((a, b) => a.key - b.key),
);

const lengthTraces = computed(() => [
  {
    type: "funnel",
    orientation: "h",
    y: byLength.value.map((row) => `${row.key} touchpoint${row.key === 1 ? "" : "s"}`),
    x: byLength.value.map((row) => row.users),
    customdata: byLength.value.map((row) => [row.converted_users, row.conversion_rate]),
    text: byLength.value.map((row) =>
      `${theme.count(row.users)} users · ${(row.conversion_rate * 100).toFixed(1)}% converted`,
    ),
    textinfo: "text",
    textposition: "inside",
    textfont: { size: 11, color: theme.MUTED },
    marker: { color: theme.SEQUENTIAL.slice(2, 2 + byLength.value.length) },
    hovertemplate:
      "<b>%{y}</b><br>Users %{x:,.0f}<br>Converted %{customdata[0]:,.0f}<br>" +
      "Conversion rate %{customdata[1]:.1%}<extra></extra>",
  },
]);

const lengthLayout = computed(() =>
  theme.layout({
    height: 300,
    legend: false,
    xaxis: { title: { text: "Users (labels retain conversion rate)" } },
    yaxis: { title: { text: "Path length" } },
  }),
);

/** Position-layered graph avoids the cycles present in raw touchpoint transitions. */
const journeyTraces = computed(() => {
  const links = new Map();
  const nodeIds = new Set();
  for (const row of paths.value) {
    const path = String(row.path ?? "").split(/\s*>\s*/).filter(Boolean);
    if (!path.length) continue;
    const first = `First|${path[0]}`;
    const midLabel = path.length === 3 ? path[1] : path.length === 2 ? "Direct" : "Single touch";
    const mid = `Middle|${midLabel}`;
    const last = `Last|${path[path.length - 1]}`;
    nodeIds.add(first); nodeIds.add(mid); nodeIds.add(last);
    for (const [source, target] of [[first, mid], [mid, last]]) {
      const key = `${source}\u0000${target}`;
      links.set(key, (links.get(key) ?? 0) + Number(row.converted_users ?? 0));
    }
  }
  const ids = [...nodeIds];
  const index = new Map(ids.map((id, position) => [id, position]));
  const rows = [...links.entries()].map(([key, value]) => {
    const [source, target] = key.split("\u0000");
    return { source: index.get(source), target: index.get(target), value };
  }).filter((row) => row.value > 0);
  return rows.length ? [{
    type: "sankey",
    arrangement: "snap",
    node: {
      label: ids.map((id) => shortTouchpoint(id.split("|")[1])),
      color: ids.map((id) => id.startsWith("First|") ? theme.SERIES[0]
        : id.startsWith("Middle|") ? theme.SERIES[2] : theme.SERIES[1]),
      pad: 12, thickness: 13,
    },
    link: {
      source: rows.map((row) => row.source), target: rows.map((row) => row.target),
      value: rows.map((row) => row.value), color: "rgba(42,120,214,0.20)",
      hovertemplate: "%{source.label} → %{target.label}<br>%{value:,.0f} converted users<extra></extra>",
    },
  }] : [];
});
const journeyLayout = computed(() => theme.layout({
  height: 620, legend: false, margin: { l: 8, r: 8, t: 30, b: 8 },
  annotations: [
    { x: 0, y: 1.04, xref: "paper", yref: "paper", text: "First touch", showarrow: false },
    { x: 0.5, y: 1.04, xref: "paper", yref: "paper", text: "Middle", showarrow: false },
    { x: 1, y: 1.04, xref: "paper", yref: "paper", text: "Last touch", showarrow: false },
  ],
}));

const pathColumns = [
  { key: "path", label: "Path", width: "40%" },
  { key: "path_length", label: "Length", format: "number" },
  { key: "users", label: "Users", format: "number" },
  { key: "converted_users", label: "Converted", format: "number" },
  { key: "purchase_count", label: "Purchases", format: "number" },
  { key: "revenue", label: "Revenue", format: "money" },
];

// ---------------------------------------------------------------------------
// Row identity
// ---------------------------------------------------------------------------

/**
 * These lists are read-only, so a row key exists for paging and rendering
 * rather than for selection: `EntityTable` keys its rows by it, and a key that
 * collides would make two distinct rows share one DOM node. Each is therefore
 * composed from the fields that actually distinguish a record, not from its
 * index.
 */
const historyRowKey = (row) =>
  [row.run_id, row.campaign_id, row.product_id, row.report_date, row.budget_level]
    .filter((part) => part !== null && part !== undefined && part !== "")
    .join(":");

const bridgeRowKey = (row) =>
  [row.campaign_id, row.ad_group_id, row.touchpoint, row.sku_id, row.target_id,
    row.audience_id, row.keyword_id]
    .filter(Boolean)
    .join(":");

const pathRowKey = (row) => String(row.path);

const touchpointRowKey = (row) => String(row.key ?? row.touchpoint);

const scopedRowKey = (row) =>
  [row.report_date, row.touchpoint, row.interaction_type].filter(Boolean).join(":");
</script>

<template>
  <section class="page-grid">
    <p class="caption">
      Observed performance and the entity bridge that links touchpoints to
      Campaigns and Ad Groups.
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

    <!-- Campaign budget and spend history -->
    <template v-if="tab === 'history'">
      <article class="card">
        <div class="card-head">
          <h2>Budget history filters</h2>
          <button @click="similarityOpen = true">Find similar history</button>
        </div>
        <div class="card-body">
          <div class="filter-row">
            <div class="field"><label for="history-provider">Provider</label><select id="history-provider" v-model="historyProvider"><option value="">All</option><option v-for="value in historyProviders" :key="value">{{ value }}</option></select></div>
            <div class="field"><label for="history-product">Product</label><select id="history-product" v-model="historyProduct"><option value="">All</option><option v-for="value in historyProducts" :key="value">{{ value }}</option></select></div>
            <div class="field"><label for="history-campaign">Campaign</label><select id="history-campaign" v-model="historyCampaign"><option value="">All</option><option v-for="value in historyCampaigns" :key="value">{{ value }}</option></select></div>
            <div class="field"><label for="history-ad-product">Ad product</label><select id="history-ad-product" v-model="historyAdProduct"><option value="">All</option><option v-for="value in historyAdProducts" :key="value">{{ pretty(value) }}</option></select></div>
            <div class="field"><label for="history-marketplace">Marketplace</label><select id="history-marketplace" v-model="historyMarketplace"><option value="">All</option><option v-for="value in historyMarketplaces" :key="value">{{ value }}</option></select></div>
            <div v-if="diagnosticsOn" class="field"><label for="history-run">Data run</label><select id="history-run" v-model="historyRun"><option value="">All</option><option v-for="value in historyRuns" :key="value">{{ value }}</option></select></div>
            <div class="field"><label for="history-from">From</label><select id="history-from" v-model="historyFrom"><option value="">Earliest</option><option v-for="value in historyDates" :key="value">{{ value }}</option></select></div>
            <div class="field"><label for="history-to">To</label><select id="history-to" v-model="historyTo"><option value="">Latest</option><option v-for="value in historyDates" :key="value">{{ value }}</option></select></div>
          </div>
        </div>
      </article>

      <template v-if="scopedHistory.length">
        <MetricRow :items="historyTiles" />
        <article class="card">
          <div class="card-head"><h2>Budget delivery response</h2><span class="sub">Configured budget vs actual spend · dashed line is full delivery</span></div>
          <div class="card-body">
            <PlotlyChart :traces="budgetHistoryTraces" :layout="budgetHistoryLayout" label="Configured Campaign budget compared with actual spend" />
            <EntityTable
              :columns="historicalColumns"
              :rows="scopedHistory"
              :row-key="historyRowKey"
              noun="observation"
              empty="No observations match the current filters."
            />
          </div>
        </article>
        <article class="card">
          <div class="card-head"><h2>Interaction-aware delivery</h2><span class="sub">IMPRESSION and CLICK remain distinct</span></div>
          <div class="card-body">
            <PlotlyChart :traces="interactionHistoryTraces" :layout="interactionHistoryLayout" label="Spend and event counts split by interaction type" />
            <p class="caption">Ordered path frequencies, path length, and transition evidence remain available in Conversion paths; no Multi-Touch Attribution is recomputed here.</p>
          </div>
        </article>
        <article class="card">
          <div class="card-head"><h2>Attribution evidence</h2></div>
          <div class="card-body">
            <p v-if="data.attributionResults.length">Existing attribution output is available in Campaign Optimizer; this explorer does not recompute it.</p>
            <p v-else class="table-empty">Attribution not available.</p>
          </div>
        </article>
      </template>
      <article v-else class="card empty-card">
        <h2>No Campaign budget history</h2>
        <p>
          No Campaign has a recorded budget-versus-spend history in the current
          reporting window. Budget planning is available in Budget Manager.
        </p>
      </article>
    </template>

    <!--
      Daily performance. This has to be `v-else-if`, not a second `v-if`: the
      chain ends in a `v-else` for Conversion paths, and a fresh chain here
      would let that `v-else` render underneath the Budget history tab.
    -->
    <template v-else-if="tab === 'performance'">
      <article class="card">
        <div class="card-head">
          <h2>Filters</h2>
          <span class="sub">Every panel below shows this slice</span>
        </div>
        <div class="card-body">
          <div class="filter-row">
            <div class="field">
              <label for="filter-from">From</label>
              <select id="filter-from" v-model="from">
                <option value="">Earliest</option>
                <option v-for="date in dates" :key="date" :value="date">{{ date }}</option>
              </select>
            </div>
            <div class="field">
              <label for="filter-to">To</label>
              <select id="filter-to" v-model="to">
                <option value="">Latest</option>
                <option v-for="date in dates" :key="date" :value="date">{{ date }}</option>
              </select>
            </div>
            <div class="field">
              <label for="filter-product">Ad product</label>
              <select id="filter-product" v-model="product">
                <option value="">All</option>
                <option v-for="name in products" :key="name" :value="name">
                  {{ pretty(name) }}
                </option>
              </select>
            </div>
            <div class="field">
              <label for="filter-placement">Placement</label>
              <select id="filter-placement" v-model="placement">
                <option value="">All</option>
                <option v-for="name in placements" :key="name" :value="name">
                  {{ pretty(name) }}
                </option>
              </select>
            </div>
            <div class="field">
              <label for="filter-interaction">Interaction type</label>
              <select id="filter-interaction" v-model="interaction">
                <option value="">All</option>
                <option v-for="name in interactions" :key="name" :value="name">
                  {{ pretty(name) }}
                </option>
              </select>
            </div>
          </div>
        </div>
      </article>

      <MetricRow :items="performanceTiles" />

      <p v-if="scoped.length === 0" class="table-empty">
        No rows match the current filters.
      </p>

      <template v-else>
        <article class="card">
          <div class="card-head"><h2>Daily spend by ad product</h2></div>
          <div class="card-body">
            <PlotlyChart
              :traces="spendByProduct"
              :layout="spendLayout"
              label="Daily spend, one line per ad product"
            />
          </div>
        </article>

        <article class="card">
          <div class="card-head">
            <h2>Touchpoint efficiency</h2>
            <span class="sub">{{ byTouchpoint.length }} touchpoints · size is interaction volume</span>
          </div>
          <div class="card-body">
            <PlotlyChart
              :traces="touchpointTraces"
              :layout="touchpointLayout"
              label="Spend against reported sales by touchpoint with a break-even line"
            />
            <p class="caption">The table below carries every touchpoint.</p>
            <EntityTable
              :columns="touchpointColumns"
              :rows="byTouchpoint"
              :row-key="touchpointRowKey"
              noun="touchpoint"
              empty="No touchpoints match the current filters."
            />
          </div>
        </article>

        <article class="card">
          <div class="card-head">
            <h2>Daily rows</h2>
            <span class="sub">{{ scoped.length.toLocaleString() }} filtered</span>
          </div>
          <div class="card-body">
            <EntityTable
              :columns="scopedColumns"
              :rows="scoped"
              :row-key="scopedRowKey"
              noun="row"
              empty="No rows match the current filters."
            />
          </div>
        </article>
      </template>
    </template>

    <!-- Campaign bridge -->
    <template v-else-if="tab === 'bridge'">
      <article class="card">
        <div class="card-head">
          <h2>Assisted outcomes by Campaign</h2>
        </div>
        <div class="card-body">
          <div class="filter-row">
            <div class="field">
              <label for="filter-campaign">Campaign</label>
              <select id="filter-campaign" v-model="campaignFilter">
                <option value="">All</option>
                <option v-for="id in campaignIds" :key="id" :value="id">{{ id }}</option>
              </select>
            </div>
            <div class="field">
              <label for="filter-adgroup">Ad Group</label>
              <select id="filter-adgroup" v-model="adGroupFilter">
                <option value="">All</option>
                <option v-for="id in adGroupIds" :key="id" :value="id">{{ id }}</option>
              </select>
            </div>
          </div>

          <p v-if="bridge.length === 0" class="table-empty">
            No rows match the current filters.
          </p>
          <template v-else>
            <PlotlyChart
              :traces="touchpointTreemap"
              :layout="touchpointTreemapLayout"
              label="Five-segment touchpoint hierarchy sized by spend"
            />
            <PlotlyChart
              :traces="bridgeTraces"
              :layout="bridgeLayout"
              label="Assisted revenue by Campaign"
            />
            <p class="caption">
              Assisted outcomes credit every touchpoint on a converting journey,
              so they sum to more than the reported total. They apportion, not
              add.
            </p>
            <EntityTable
              :columns="bridgeColumns"
              :rows="bridge"
              :row-key="bridgeRowKey"
              noun="bridge row"
              empty="No rows match the current filters."
            />
          </template>
        </div>
      </article>
    </template>

    <!-- Conversion paths -->
    <template v-else>
      <MetricRow :items="pathTiles" />

      <article class="card">
        <div class="card-head">
          <h2>Journey graph</h2>
        </div>
        <div class="card-body">
          <PlotlyChart
            :traces="journeyTraces"
            :layout="journeyLayout"
            label="Position-layered journey graph from first through middle to last touch"
          />
          <PlotlyChart
            :traces="lengthTraces"
            :layout="lengthLayout"
            label="Conversion rate by the number of touchpoints on the path"
          />
          <p class="caption">
            Link width is converted-user volume. The funnel keeps path volume
            and conversion rate together, so a higher rate cannot be mistaken
            for a larger addressable audience.
          </p>

          <!--
            The table's own search replaces the separate field this panel used
            to carry: `EntityTable` filters across the rendered text of every
            declared column, which is a superset of what searching the path
            string alone matched.
          -->
          <EntityTable
            :columns="pathColumns"
            :rows="sortedPaths"
            :row-key="pathRowKey"
            noun="path"
            empty="No conversion paths available."
          />
        </div>
      </article>
    </template>

    <div v-if="similarityOpen" class="modal-backdrop" @click.self="similarityOpen = false">
      <section class="modal" role="dialog" aria-modal="true" aria-label="Historical similarity reference">
        <div class="modal-head"><h2>Historical similarity reference</h2><button @click="similarityOpen = false">Close</button></div>
        <div class="modal-body">
          <p><b>Historical reference only. Not used by attribution or strategy optimization.</b></p>
          <div class="filter-row">
            <div class="field"><label for="similar-campaign">Query Campaign</label><select id="similar-campaign" v-model="similarityCampaign"><option value="">Temporary profile</option><option v-for="value in historyCampaigns" :key="value">{{ value }}</option></select></div>
            <div class="field"><label for="similar-product">Product</label><select id="similar-product" v-model="similarityProduct"><option value="">Any</option><option v-for="value in historyProducts" :key="value">{{ value }}</option></select></div>
            <div class="field"><label for="similar-provider">Provider</label><select id="similar-provider" v-model="similarityProvider"><option value="">From Campaign / any</option><option v-for="value in historyProviders" :key="value">{{ value }}</option></select></div>
            <div class="field"><label for="similar-ad-product">Ad product</label><select id="similar-ad-product" v-model="similarityAdProduct"><option value="">From Campaign / any</option><option v-for="value in historyAdProducts" :key="value">{{ value }}</option></select></div>
            <div class="field"><label for="similar-budget">Configured budget</label><input id="similar-budget" v-model="similarityBudget" type="number" min="0" step="1" /></div>
            <div class="field"><label for="similar-threshold">Threshold {{ Number(similarityThreshold).toFixed(2) }}</label><input id="similar-threshold" v-model.number="similarityThreshold" type="range" min="0" max="1" step="0.05" /></div>
          </div>
          <DataTable :columns="similarityColumns" :rows="similarityMatches" empty="No historical references meet this threshold." />
        </div>
      </section>
    </div>
  </section>
</template>
