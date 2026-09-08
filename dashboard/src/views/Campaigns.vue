<script setup>
/**
 * Campaigns: historical performance, filterable and queryable.
 *
 * The one place a reader can interrogate the raw record -- daily platform
 * performance, the Campaign and Ad Group bridge, and the conversion paths. All
 * filters sit in a single row above the charts, so every panel on the page
 * shows the same slice.
 */
import { computed, nextTick, ref, watch } from "vue";

import { aggregatePerformance, safeRatio, downloadCsv } from "../lib/chartData.js";
import EntityTable from "../components/EntityTable.vue";
import MetricRow from "../components/MetricRow.vue";
import PlotlyChart from "../components/PlotlyChart.vue";
import {
  currencySymbol,
  densityGrid,
  distinct,
  maxOf,
  pretty,
  shortDate,
  shortTouchpoint,
  sortBy,
  sum,
} from "../lib/common.js";
import { useDashboard } from "../lib/useDashboard.js";
import { useDiagnostics } from "../lib/diagnostics.js";
import * as theme from "../theme.js";

const props = defineProps({ section: { type: String, default: "history" } });
const emit = defineEmits(["navigate"]);
const { data, setHistoryWindow } = useDashboard();
const { diagnosticsOn } = useDiagnostics();

const tab = computed(() => props.section);
const TABS = [
  { key: "history", label: "Budget history" },
  { key: "performance", label: "Daily performance" },
  { key: "bridge", label: "Campaign bridge" },
  { key: "paths", label: "Conversion paths" },
];


// Aggregate a presentation category in one scan, preserving absent measures.
function aggregateCategories(rows, field, fields) {
  const groups = new Map();
  for (const row of rows) {
    const key = row[field] ?? "Unavailable";
    if (!groups.has(key)) groups.set(key, { key, members: [key], rows: 0,
      ...Object.fromEntries(fields.map(name => [name, null])) });
    const group = groups.get(key);
    group.rows += 1;
    for (const name of fields) if (typeof row[name] === "number" && Number.isFinite(row[name])) {
      group[name] = (group[name] ?? 0) + row[name];
    }
  }
  return [...groups.values()];
}

// Seven named categories plus one neutral overflow preserve a fixed mark cap.
function rankCategories(rows, field) {
  const ordered = [...rows].sort((a, b) =>
    (b[field] ?? -Infinity) - (a[field] ?? -Infinity) || String(a.key).localeCompare(String(b.key)));
  if (ordered.length <= 7) return ordered;
  const remaining = ordered.slice(7);
  const fields = Object.keys(rows[0]).filter(key => !["key", "members"].includes(key));
  const other = { key: "Other", members: remaining.flatMap(row => row.members ?? [row.key]) };
  for (const name of fields) {
    const values = remaining.filter(row => typeof row[name] === "number" && Number.isFinite(row[name]));
    other[name] = values.length ? values.reduce((total, row) => total + row[name], 0) : null;
  }
  return [...ordered.slice(0, 7), other];
}
const currencyCode = computed(() => data.value.dataset?.scope?.currency ??
  data.value.dashboardContext?.currency ?? data.value.adsDaily?.[0]?.currency ?? data.value.simulationResearch?.history?.[0]?.currency ?? data.value.strategyRequest?.campaign_group?.currency ?? "USD");
const currency = computed(() => currencySymbol(currencyCode.value));
const sourceLabel = computed(() => data.value.dataset?.name ?? data.value.dashboardContext?.source ?? data.value.source ?? "Current source");
const moneyColumns = columns => columns.map(column => column.format === "money"
  ? { ...column, label: `${column.label} (${currencyCode.value})`, currency: currency.value } : column);
const observedSum = (rows, field) => rows.some(row => typeof row[field] === "number" && Number.isFinite(row[field]))
  ? sum(rows, field) : null;
const grain = ref("day");
const rankingSelection = ref(null);
const detailHeading = ref(null);
let rankingTrigger = null;
async function selectRanking(row, event) {
  rankingTrigger = event?.currentTarget ?? null;
  rankingSelection.value = row;
  await nextTick();
  detailHeading.value?.focus();
}
async function backToRanking() {
  rankingSelection.value = null;
  await nextTick();
  rankingTrigger?.focus();
}
function resetFilters() {
  const fields = tab.value === "history"
    ? [historyProvider, historyProduct, historyCampaign, historyAdProduct, historyMarketplace, historyRun, historyFrom, historyTo]
    : tab.value === "performance" ? [from, to, product, placement, interaction]
      : tab.value === "bridge" ? [campaignFilter, adGroupFilter] : [pathSearch];
  for (const field of fields) field.value = "";
  rankingSelection.value = null;
}

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

/**
 * The window the loaded rows were read under, and the full range they came
 * from. The server reports both, because a reader cannot tell from the rows
 * that survived a window what range was excluded by it.
 */
const loadedWindow = computed(() => research.value.historyWindow ?? {});

/** Whether the loaded slice is narrower than the range the source holds. */
const windowIsPartial = computed(() => {
  const window = loadedWindow.value;
  return Boolean(
    (window.start && window.start > (window.earliest ?? window.start)) ||
    (window.end && window.end < (window.latest ?? window.end)),
  );
});

const windowStartRequest = ref("");
const windowEndRequest = ref("");

/**
 * Ask the backend for a different slice of history.
 *
 * The date controls request a window rather than filtering rows already in the
 * browser, so narrowing a range shrinks the transfer instead of only hiding
 * what was already paid for. The remaining filters stay client-side: they
 * select within the loaded window, which needs no round trip. Leaving both
 * dates empty asks for nothing in particular, which the backend answers with
 * its recent-quarter default.
 */
function applyWindow() {
  setHistoryWindow({
    start: windowStartRequest.value || null,
    end: windowEndRequest.value || null,
  });
}

/**
 * Load the whole recorded history.
 *
 * Requested as the observed range rather than as no window at all: no window is
 * what the backend answers with its default, so clearing the dates would ask
 * for the same slice already loaded. The full range is above fifty megabytes,
 * which is why it is a deliberate action and not what a first view does.
 */
function loadEverything() {
  const { earliest, latest } = loadedWindow.value;
  if (!earliest || !latest) return;
  windowStartRequest.value = "";
  windowEndRequest.value = "";
  setHistoryWindow({ start: earliest, end: latest });
}

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
  const spend = observedSum(scopedHistory.value, "actual_spend");
  const impressions = observedSum(scopedDelivery.value, "impressions");
  const clicks = observedSum(scopedDelivery.value, "clicks");
  const deliveryCost = observedSum(scopedDelivery.value, "cost");
  const economicsComplete = scopedHistory.value.length > 0 && scopedHistory.value.every(
    (row) => row.contribution_profit !== null && row.contribution_profit !== undefined,
  );
  return [
    { label: "Configured budget", value: theme.compactMoney(observedSum(scopedHistory.value, "configured_budget"), currency.value) },
    { label: "Actual spend", value: theme.compactMoney(spend, currency.value) },
    { label: "Impressions", value: theme.count(impressions) },
    { label: "Clicks", value: theme.count(clicks) },
    { label: "CTR", value: theme.percent(safeRatio(clicks, impressions)) },
    { label: "CPC", value: theme.money(safeRatio(deliveryCost, clicks), currency.value) },
    { label: "CPM", value: theme.money(safeRatio(deliveryCost == null ? null : deliveryCost * 1000, impressions), currency.value) },
    { label: "Purchases", value: theme.count(observedSum(scopedDelivery.value, "reported_purchases")) },
    { label: "Units", value: theme.count(observedSum(scopedHistory.value, "total_units")) },
    { label: "Revenue", value: theme.compactMoney(observedSum(scopedHistory.value, "total_revenue"), currency.value) },
    { label: "Contribution profit", value: economicsComplete
      ? theme.compactMoney(observedSum(scopedHistory.value, "contribution_profit"), currency.value)
      : "Unavailable" },
  ];
});

const interactionValues = computed(() => aggregateCategories(scopedDelivery.value, "interaction_type", [
  "impressions", "clicks", "cost", "reported_purchases", "reported_sales",
]));
const interactionColumns = [
  { key: "key", label: "Interaction" }, { key: "impressions", label: "Impressions", format: "number" },
  { key: "clicks", label: "Clicks", format: "number" }, { key: "cost", label: "Spend", format: "money" },
  { key: "reported_purchases", label: "Purchases", format: "number" }, { key: "reported_sales", label: "Sales", format: "money" },
];
const interactionHistoryTraces = computed(() => {
  const rows = interactionValues.value;
  return [{
    type: "bar",
    x: rows.map((row) => row.key || "Unavailable"),
    y: rows.map((row) => row.cost),
    text: rows.map((row) => `${theme.count(row.impressions)} imp · ${theme.count(row.clicks)} clicks`),
    textposition: "outside",
    marker: { color: theme.SERIES[2] },
    hovertemplate: "%{x}<br>Spend %{y:,.2f}<br>%{text}<extra></extra>",
  }];
});
const interactionHistoryLayout = computed(() => theme.layout({
  height: 300, legend: false, yaxis: { title: { text: "Spend" } },
}));

/**
 * The grid sizes offered for the delivery-response chart.
 *
 * The reader chooses how finely observations are merged. A coarse grid reads
 * as shape and is quick to scan; a fine one resolves where a dense band
 * actually separates. Both draw at most `resolution²` marks regardless of how
 * many observations were merged into them, which is what keeps the chart
 * drawable at the supported history size.
 */
const DENSITY_RESOLUTIONS = [10, 40, 100];
const densityResolution = ref(40);

const historyHighest = computed(() =>
  maxOf(scopedHistory.value, ["configured_budget", "actual_spend"], 1),
);

/**
 * Observations merged into a fixed grid, coloured by how many share a cell.
 *
 * This replaces a per-Campaign scatter. That drew one marker per observation
 * -- 100,000 of them for a full history, of which roughly 85% landed where
 * another had already drawn -- across 40 overlapping series whose colours could
 * no longer be told apart at that density. The count the overplotting was
 * hiding is the thing worth showing, so it is the encoded value here.
 */
const historyDensity = computed(() =>
  densityGrid(
    scopedHistory.value,
    "configured_budget",
    "actual_spend",
    historyHighest.value,
    densityResolution.value,
  ),
);

const densityValues = computed(() => {
  const grid = historyDensity.value;
  const values = [];
  for (let y = 0; y < grid.z.length; y += 1) for (let x = 0; x < grid.z[y].length; x += 1) {
    if (grid.z[y][x] == null) continue;
    values.push({ key: `${x}:${y}`, budget_from: x * grid.dx, budget_to: (x + 1) * grid.dx,
      spend_from: y * grid.dy, spend_to: (y + 1) * grid.dy, observations: grid.z[y][x] });
  }
  return values;
});
const densityColumns = [
  { key: "budget_from", label: "Budget from", format: "money" }, { key: "budget_to", label: "Budget to", format: "money" },
  { key: "spend_from", label: "Spend from", format: "money" }, { key: "spend_to", label: "Spend to", format: "money" },
  { key: "observations", label: "Observations", format: "number" },
];
const budgetHistoryTraces = computed(() => {
  const grid = historyDensity.value;
  if (!grid.total) return [];
  return [{
    type: "heatmap",
    z: grid.z,
    x0: grid.x0,
    dx: grid.dx,
    y0: grid.y0,
    dy: grid.dy,
    colorscale: theme.SEQUENTIAL.map((color, index) => [
      index / (theme.SEQUENTIAL.length - 1),
      color,
    ]),
    // An empty cell is left as the plane rather than drawn as the palette's
    // lightest colour, so "nothing here" is not read as "a few here".
    hoverongaps: false,
    colorbar: {
      title: { text: "Observations", side: "right", font: { size: 11 } },
      thickness: 12,
      outlinewidth: 0,
      tickfont: { size: 10, color: theme.MUTED },
    },
    hovertemplate:
      "Budget %{x:,.2f}<br>Spend %{y:,.2f}<br>" +
      "%{z:,.0f} observations in this cell<extra></extra>",
  }];
});

const budgetHistoryLayout = computed(() => {
  const highest = historyHighest.value;
  return theme.layout({
    height: 360,
    legend: false,
    xaxis: { title: { text: "Configured budget" }, range: [0, highest * 1.04] },
    yaxis: { title: { text: "Actual spend" }, range: [0, highest * 1.04] },
    shapes: [{
      type: "line", x0: 0, y0: 0, x1: highest, y1: highest,
      line: { color: theme.AXIS, width: 1.5, dash: "dash" },
    }],
  });
});

/** What the grid merged, for the card's subtitle. */
const densitySummary = computed(() => {
  const { total, occupied, densest } = historyDensity.value;
  if (!total) return "No observations to plot";
  return `${total.toLocaleString()} observation${total === 1 ? "" : "s"} merged into ` +
    `${occupied.toLocaleString()} cell${occupied === 1 ? "" : "s"} · ` +
    `densest holds ${densest.toLocaleString()}`;
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
  const spend = observedSum(scoped.value, "cost");
  const sales = observedSum(scoped.value, "sales");
  return [
    { label: "Spend", value: theme.compactMoney(spend, currency.value) },
    { label: "Sales", value: theme.compactMoney(sales, currency.value) },
    { label: "Impressions", value: theme.count(observedSum(scoped.value, "impressions")) },
    { label: "Clicks", value: theme.count(observedSum(scoped.value, "clicks")) },
    { label: "ROAS", value: theme.ratio(safeRatio(sales, spend)) },
  ];
});

/** Calendar grouping bounds long daily histories without averaging ratios. */
const trendValues = computed(() => aggregatePerformance(scoped.value, grain.value));
const trendPlotValues = computed(() => trendValues.value.length <= 500 ? trendValues.value
  : Array.from({ length: 500 }, (_, index) => trendValues.value[Math.floor(index * (trendValues.value.length - 1) / 499)]));
const spendByProduct = computed(() => [{ type: "scatter", mode: "lines", name: "Spend",
  x: trendPlotValues.value.map(row => row.key), y: trendPlotValues.value.map(row => row.cost),
  line: { color: theme.SERIES[0], width: 2 },
  hovertemplate: `%{x}<br>Spend ${currency.value}%{y:,.2f}<extra></extra>` }]);
const spendLayout = computed(() => theme.layout({ height: 300,
  yaxis: { title: { text: `Spend (${currencyCode.value})` } } }));
const trendColumns = [
  { key: "key", label: "Period" }, { key: "rows", label: "Observations", format: "number" },
  { key: "cost", label: "Spend", format: "money" }, { key: "sales", label: "Sales", format: "money" },
  { key: "roas", label: "Return on ad spend", format: "ratio" },
];

/** Spend against reported sales per touchpoint. */
const byTouchpoint = computed(() => sortBy(
  aggregateCategories(scoped.value, "touchpoint", ["cost", "sales", "impressions", "clicks"]), "cost", "desc"));
const touchpointRanking = computed(() => rankCategories(byTouchpoint.value, "cost"));
const rankingDetailRows = computed(() => {
  const members = new Set(rankingSelection.value?.members ?? []);
  return scoped.value.filter(row => members.has(row.touchpoint ?? "Unavailable"));
});
// Resolve colors from the complete source vocabulary, independent of ranking/filter order.
const touchpointColors = computed(() => theme.seriesColors(distinct(ads.value, "touchpoint").sort().slice(0, 7)));
const rankingColor = row => row.members.length > 1 ? theme.MUTED : touchpointColors.value[row.key] ?? theme.MUTED;
watch([from, to, product, placement, interaction], () => { rankingSelection.value = null; }, { flush: "sync" });

const touchpointTraces = computed(() => {
  const rows = touchpointRanking.value;
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
      safeRatio(row.sales, row.cost)]),
    marker: {
      color: rows.map(rankingColor), opacity: 0.74,
      size: rows.map((row) => 10 + 24 * Math.sqrt(
        (Number(row.impressions) + Number(row.clicks)) / largestVolume,
      )),
      line: { color: theme.SURFACE, width: 1 },
    },
    hovertemplate:
      "<b>%{customdata[0]}</b><br>Spend %{x:,.2f}<br>Reported sales %{y:,.2f}<br>" +
      "ROAS %{customdata[3]:.2f}x<br>%{customdata[1]:,.0f} impressions · " +
      "%{customdata[2]:,.0f} clicks<extra></extra>",
  }];
});

const touchpointLayout = computed(() => {
  const highest = maxOf(touchpointRanking.value, ["cost", "sales"], 1);
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
  const rows = rankCategories(aggregateCategories(bridge.value, "campaign_id", ["assisted_revenue"]), "assisted_revenue");
  return [
    {
      type: "bar",
      x: rows.map((row) => row.key),
      y: rows.map((row) => row.assisted_revenue),
      name: "Assisted revenue",
      marker: { color: theme.SERIES[0], line: { color: theme.SURFACE, width: 2 } },
      hovertemplate: "<b>%{x}</b><br>Assisted revenue %{y:,.2f}<extra></extra>",
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
  const ranked = rankCategories(aggregateCategories(bridge.value, "touchpoint", ["cost"]), "cost");
  for (const row of ranked) {
    const segments = String(row.key === "Other" ? "Other:Other:Other:Other:Other" : row.key ?? "").split(":");
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
    hovertemplate: "<b>%{label}</b><br>Spend %{value:,.2f}<br>%{percentParent:.1%} of parent<extra></extra>",
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

const pathSearch = ref("");
const paths = computed(() => data.value.pathReport.filter(row =>
  String(row.path ?? "").toLowerCase().includes(pathSearch.value.trim().toLowerCase())));

/**
 * Highest revenue first. Filtering used to live here too; `EntityTable` owns it
 * now, so this only decides the order the table pages through.
 */
const sortedPaths = computed(() => sortBy(paths.value, "revenue", "desc"));

const pathTiles = computed(() => [
  { label: "Distinct paths", value: theme.count(paths.value.length) },
  { label: "Users", value: theme.count(observedSum(paths.value, "users")) },
  { label: "Converted users", value: theme.count(observedSum(paths.value, "converted_users")) },
  { label: "Revenue", value: theme.compactMoney(observedSum(paths.value, "revenue"), currency.value) },
]);

const byLength = computed(() =>
  aggregateCategories(paths.value, "path_length", ["users", "converted_users", "revenue"])
    .map((row) => ({
      ...row,
      conversion_rate: safeRatio(row.converted_users, row.users),
    }))
    .sort((a, b) => a.key - b.key),
);

const lengthPlotValues = computed(() => rankCategories(byLength.value, "users").map(row => ({
  ...row, conversion_rate: safeRatio(row.converted_users, row.users),
})));
const lengthTraces = computed(() => [
  {
    type: "funnel",
    orientation: "h",
    y: lengthPlotValues.value.map((row) => row.key === "Other" ? "Other lengths" : `${row.key} touchpoint${row.key === 1 ? "" : "s"}`),
    x: lengthPlotValues.value.map((row) => row.users),
    customdata: lengthPlotValues.value.map((row) => [row.converted_users, row.conversion_rate]),
    text: lengthPlotValues.value.map((row) =>
      `${theme.count(row.users)} users · ${theme.percent(row.conversion_rate)} converted`,
    ),
    textinfo: "text",
    textposition: "inside",
    textfont: { size: 11, color: theme.MUTED },
    marker: { color: lengthPlotValues.value.map(() => theme.SERIES[0]) },
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
  const vocabulary = new Map();
  for (const row of paths.value) for (const touch of String(row.path ?? "").split(/\s*>\s*/).filter(Boolean)) {
    vocabulary.set(touch, (vocabulary.get(touch) ?? 0) + (row.converted_users ?? 0));
  }
  const retained = new Set([...vocabulary].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0])).slice(0, 7).map(([key]) => key));
  const links = new Map();
  const nodeIds = new Set();
  for (const row of paths.value) {
    const path = String(row.path ?? "").split(/\s*>\s*/).filter(Boolean).map(touch => retained.has(touch) ? touch : "Other");
    if (!path.length) continue;
    const first = `First|${path[0]}`;
    const midLabel = path.length === 3 ? path[1] : path.length === 2 ? "Direct" : path.length > 3 ? "Multiple touches" : "Single touch";
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

const similarityRowKey = (row) =>
  [row.run_id, row.campaign_id, row.product_id, row.historical_period]
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
    <p class="caption" role="status">{{ sourceLabel }} · {{ currencyCode }} · {{ tab === 'performance' ? `${windowStart} to ${windowEnd} · ${scoped.length.toLocaleString()} observations` : tab === 'history' ? `${historyFrom || loadedWindow.start || loadedWindow.earliest || 'Start unavailable'} to ${historyTo || loadedWindow.end || loadedWindow.latest || 'End unavailable'} · ${scopedHistory.length.toLocaleString()} observations` : tab === 'paths' ? `${paths.length.toLocaleString()} paths` : `${bridge.length.toLocaleString()} bridge rows` }}</p>
    <button class="btn small" @click="resetFilters">Reset filters</button>
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
        @click="emit('navigate', entry.key)"
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

      <article class="card">
        <div class="card-head">
          <h2>Loaded history window</h2>
          <span class="sub">Requests a slice from the backend rather than filtering what is already here</span>
        </div>
        <div class="card-body">
          <div class="filter-row">
            <div class="field">
              <label for="window-start">Load from</label>
              <input id="window-start" v-model="windowStartRequest" type="date" :min="loadedWindow.earliest" :max="loadedWindow.latest" />
            </div>
            <div class="field">
              <label for="window-end">Load to</label>
              <input id="window-end" v-model="windowEndRequest" type="date" :min="loadedWindow.earliest" :max="loadedWindow.latest" />
            </div>
            <div class="field">
              <label>&nbsp;</label>
              <button class="btn" @click="applyWindow">Load this window</button>
            </div>
            <div v-if="windowIsPartial" class="field">
              <label>&nbsp;</label>
              <button class="btn small" @click="loadEverything">Load everything</button>
            </div>
          </div>
          <p class="caption">
            <template v-if="windowIsPartial">
              Showing {{ loadedWindow.start || loadedWindow.earliest }} to
              {{ loadedWindow.end || loadedWindow.latest }}. The source holds
              {{ loadedWindow.earliest }} to {{ loadedWindow.latest }}; every
              figure on this page describes the loaded window only. Loading the
              complete history transfers considerably more.
            </template>
            <template v-else-if="loadedWindow.earliest">
              Showing the complete recorded history, {{ loadedWindow.earliest }}
              to {{ loadedWindow.latest }}.
            </template>
          </p>
        </div>
      </article>

      <template v-if="scopedHistory.length">
        <MetricRow :items="historyTiles" />
        <article class="card">
          <div class="card-head">
            <h2>Configured budget vs actual spend</h2>
            <span class="sub">{{ densitySummary }} · dashed line is full delivery</span>
          </div>
          <div class="card-body">
            <div class="filter-row">
              <div class="field">
                <label for="density-resolution">Grid resolution</label>
                <select id="density-resolution" v-model.number="densityResolution">
                  <option v-for="size in DENSITY_RESOLUTIONS" :key="size" :value="size">
                    {{ size }} × {{ size }}
                  </option>
                </select>
              </div>
            </div>
            <PlotlyChart :traces="budgetHistoryTraces" :layout="budgetHistoryLayout" label="Observation density by configured Campaign budget against actual spend" />
            <p class="caption">
              Colour is how many observations fall in a cell, so a dense band
              reads as density rather than as overlapping marks. Per-observation
              values are in the table below.
            </p>
            <details><summary>View density cell values</summary><EntityTable :columns="moneyColumns(densityColumns)" :rows="densityValues" :row-key="row => row.key" noun="density cell" /></details>
            <EntityTable
              :columns="moneyColumns(historicalColumns)"
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
            <EntityTable :columns="moneyColumns(interactionColumns)" :rows="interactionValues" :row-key="row => row.key" noun="interaction" />
            <p class="caption">Ordered path frequencies, path length, and transition evidence remain available in Conversion paths; no Multi-Touch Attribution is recomputed here.</p>
          </div>
        </article>
      </template>
      <article v-else class="card empty-card">
        <h2>No Campaign budget history</h2>
        <p>
          Research observations are unavailable or no observations match these filters. Reset filters or select a dataset with budget history. Daily performance and Conversion paths remain independently available.
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

      <div class="field"><label for="campaign-grain">Group by</label><select id="campaign-grain" v-model="grain"><option value="day">Day</option><option value="week">Week</option><option value="month">Month</option></select></div>
      <MetricRow :items="performanceTiles" />

      <p v-if="scoped.length === 0" class="table-empty">
        No rows match the current filters.
      </p>

      <template v-else>
        <article class="card">
          <div class="card-head"><h2>Spend by period</h2></div>
          <div class="card-body">
            <PlotlyChart
              :traces="spendByProduct"
              :layout="spendLayout"
              label="Spend by selected calendar period"
            />
            <p v-if="trendValues.length > 500" class="caption">500 evenly spaced periods plotted; the table and export retain all {{ trendValues.length }} periods.</p>
            <EntityTable :columns="moneyColumns(trendColumns)" :rows="trendValues" :row-key="row => row.key" noun="period" />
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
            <p class="caption">Seven leading touchpoints by spend plus Other. Select a row for its observations; the full table retains every touchpoint.</p>
            <div class="table-wrap"><table><caption>Touchpoint ranking · {{ currencyCode }}</caption><thead><tr><th>Touchpoint</th><th>Spend</th><th>Sales</th><th>Observations</th></tr></thead><tbody>
              <tr v-for="row in touchpointRanking" :key="JSON.stringify(row.members)"><td><button class="btn small" @click="selectRanking(row, $event)">{{ row.key === 'Other' && row.members.length > 1 ? `Other (${row.members.length} touchpoints)` : shortTouchpoint(row.key) }}</button></td><td>{{ theme.money(row.cost, currency) }}</td><td>{{ theme.money(row.sales, currency) }}</td><td>{{ row.rows }}</td></tr>
            </tbody></table></div>
            <button class="btn small" @click="downloadCsv(moneyColumns(touchpointColumns), touchpointRanking, 'touchpoint-ranking.csv')">Export ranking CSV</button>
            <section v-if="rankingSelection" class="card-body">
              <h3 ref="detailHeading" tabindex="-1">Observations: {{ rankingSelection.key }}</h3>
              <button class="btn small" @click="backToRanking">Back to ranking</button>
              <p class="caption">{{ rankingDetailRows.length.toLocaleString() }} observations · outer filters retained · {{ currencyCode }}</p>
              <EntityTable :columns="moneyColumns(scopedColumns)" :rows="rankingDetailRows" :row-key="scopedRowKey" noun="detail row" />
            </section>
            <EntityTable
              :columns="moneyColumns(touchpointColumns)"
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
              :columns="moneyColumns(scopedColumns)"
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
              :columns="moneyColumns(bridgeColumns)"
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
      <div class="field"><label for="path-search">Filter paths</label><input id="path-search" v-model="pathSearch" type="search" /></div>
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

          <EntityTable :row-key="row => row.key" noun="path length" :columns="moneyColumns([{ key: 'key', label: 'Length' }, { key: 'users', label: 'Users', format: 'number' }, { key: 'converted_users', label: 'Converted users', format: 'number' }, { key: 'conversion_rate', label: 'Conversion rate', format: 'percent' }, { key: 'revenue', label: 'Revenue', format: 'money' }])" :rows="byLength" />
          <p class="caption">Each position retains seven leading touchpoints and Other. Longer paths label intervening steps Multiple touches. Filtered path rows below retain the full sequence.</p>
          <!--
            The table's own search replaces the separate field this panel used
            to carry: `EntityTable` filters across the rendered text of every
            declared column, which is a superset of what searching the path
            string alone matched.
          -->
          <EntityTable
            :columns="moneyColumns(pathColumns)"
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
          <!--
            Paged rather than rendered whole. A selected Campaign makes every
            observation sharing its Provider score 1.0, so the match list is
            thousands of rows long at a low threshold, not the fixed short list
            a plain table can afford inside a dialog.
          -->
          <EntityTable
            :columns="moneyColumns(similarityColumns)"
            :rows="similarityMatches"
            :row-key="similarityRowKey"
            noun="reference"
            empty="No historical references meet this threshold."
          />
        </div>
      </section>
    </div>
  </section>
</template>
