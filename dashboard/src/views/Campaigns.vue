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
import MetricRow from "../components/MetricRow.vue";
import PlotlyChart from "../components/PlotlyChart.vue";
import TableView from "../components/TableView.vue";
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
import * as theme from "../theme.js";

const { data } = useDashboard();

const tab = ref("performance");
const TABS = [
  { key: "performance", label: "Daily performance" },
  { key: "bridge", label: "Campaign bridge" },
  { key: "paths", label: "Conversion paths" },
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
  const top = byTouchpoint.value.slice(0, 12).reverse();
  return [
    {
      type: "bar",
      orientation: "h",
      name: "Spend",
      y: top.map((row) => shortTouchpoint(row.key)),
      x: top.map((row) => row.cost),
      marker: { color: theme.SERIES[0], line: { color: theme.SURFACE, width: 2 } },
      hovertemplate: "<b>%{y}</b><br>Spend %{x:$,.2f}<extra></extra>",
    },
  ];
});

const touchpointLayout = computed(() =>
  theme.layout({ height: 380, legend: false, xaxis: { title: { text: "Spend" } } }),
);

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

const search = ref("");

const paths = computed(() => data.value.pathReport);

const listedPaths = computed(() => {
  const needle = search.value.trim().toLowerCase();
  const rows = needle
    ? paths.value.filter((row) => String(row.path).toLowerCase().includes(needle))
    : paths.value;
  return sortBy(rows, "revenue", "desc");
});

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
    type: "bar",
    x: byLength.value.map((row) => row.key),
    y: byLength.value.map((row) => row.conversion_rate),
    marker: { color: theme.SERIES[0], line: { color: theme.SURFACE, width: 2 } },
    text: byLength.value.map((row) => `${(row.conversion_rate * 100).toFixed(1)}%`),
    textposition: "outside",
    textfont: { size: 11, color: theme.MUTED },
    hovertemplate:
      "<b>%{x} touchpoints</b><br>Conversion rate %{y:.2%}<extra></extra>",
  },
]);

const lengthLayout = computed(() =>
  theme.layout({
    height: 300,
    legend: false,
    xaxis: { title: { text: "Touchpoints on the path" }, dtick: 1 },
    yaxis: { title: { text: "Conversion rate" }, tickformat: ".0%" },
  }),
);

const pathColumns = [
  { key: "path", label: "Path", width: "40%" },
  { key: "path_length", label: "Length", format: "number" },
  { key: "users", label: "Users", format: "number" },
  { key: "converted_users", label: "Converted", format: "number" },
  { key: "purchase_count", label: "Purchases", format: "number" },
  { key: "revenue", label: "Revenue", format: "money" },
];
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

    <!-- Daily performance -->
    <template v-if="tab === 'performance'">
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
            <h2>Spend and return by touchpoint</h2>
            <span class="sub">Top 12 of {{ byTouchpoint.length }} by spend</span>
          </div>
          <div class="card-body">
            <PlotlyChart
              :traces="touchpointTraces"
              :layout="touchpointLayout"
              label="Spend by touchpoint, highest first"
            />
            <p class="caption">The table below carries every touchpoint.</p>
            <TableView
              label="View all touchpoints as a table"
              :columns="touchpointColumns"
              :rows="byTouchpoint"
            />
            <TableView
              :label="`View all ${scoped.length.toLocaleString()} filtered rows as a table`"
              :columns="scopedColumns"
              :rows="scoped"
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
              :traces="bridgeTraces"
              :layout="bridgeLayout"
              label="Assisted revenue by Campaign"
            />
            <p class="caption">
              Assisted outcomes credit every touchpoint on a converting journey,
              so they sum to more than the reported total. They apportion, not
              add.
            </p>
            <DataTable :columns="bridgeColumns" :rows="bridge" />
          </template>
        </div>
      </article>
    </template>

    <!-- Conversion paths -->
    <template v-else>
      <MetricRow :items="pathTiles" />

      <article class="card">
        <div class="card-head">
          <h2>Conversion paths</h2>
        </div>
        <div class="card-body">
          <PlotlyChart
            :traces="lengthTraces"
            :layout="lengthLayout"
            label="Conversion rate by the number of touchpoints on the path"
          />
          <p class="caption">
            Longer paths convert more often here, which is why last-touch
            attribution understates the touchpoints that open a journey.
          </p>

          <div class="field">
            <label for="path-search">Search paths</label>
            <input
              id="path-search"
              v-model="search"
              type="search"
              placeholder="e.g. SPONSORED_PRODUCTS, or CLICK"
            />
          </div>

          <DataTable :columns="pathColumns" :rows="listedPaths" />
          <p class="caption">
            {{ listedPaths.length.toLocaleString() }} of
            {{ paths.length.toLocaleString() }} paths shown.
          </p>
        </div>
      </article>
    </template>
  </section>
</template>
