<script setup>
/**
 * Budget Manager: the recommended allocation and how it was derived.
 *
 * Shows the initial daily budget the strategy module proposes for each
 * Campaign, the MTA score that produced each share, and the Ad Group slots the
 * budget is divided into. The derivation is on the page rather than behind a
 * link, because a budget number without its basis invites the reader to trust
 * it blindly.
 */
import { computed, ref } from "vue";

import DataTable from "../components/DataTable.vue";
import KeyValuePanel from "../components/KeyValuePanel.vue";
import MetricRow from "../components/MetricRow.vue";
import PlotlyChart from "../components/PlotlyChart.vue";
import ReliabilityBanner from "../components/ReliabilityBanner.vue";
import { OUTCOME_LABELS, currencySymbol, sortBy } from "../lib/common.js";
import { useDashboard } from "../lib/useDashboard.js";
import {
  archiveMasterObject,
  saveMasterObject,
} from "../api/client.js";
import * as theme from "../theme.js";

const { data, reload } = useDashboard();
const research = computed(() => data.value.simulationResearch ?? {});
const section = ref("overview");
const SECTIONS = [
  ["overview", "Overview"],
  ["providers", "Ad Providers"],
  ["products", "Products"],
  ["campaigns", "Campaigns"],
  ["adGroups", "Ad Groups"],
  ["touchpoints", "Touchpoints"],
  ["productEconomics", "Product Economics"],
  ["generationConfigs", "Generation Configs"],
];
const entityTypes = {
  providers: "provider",
  products: "product",
  campaigns: "campaign",
  adGroups: "ad_group",
  touchpoints: "touchpoint",
  productEconomics: "product_economics",
  generationConfigs: "generation_config",
};
const entityIds = {
  providers: "provider",
  products: "product_id",
  campaigns: "campaign_id",
  adGroups: "ad_group_id",
  touchpoints: "identifier",
  productEconomics: "product_id",
  generationConfigs: "run_id",
};
const editor = ref(null);
const editorText = ref("");
const editorError = ref("");
const uploadedConfig = ref(null);

const databaseEditing = computed(() => data.value.mode === "database");
const sectionDrafts = computed(() =>
  (research.value.masterObjects ?? []).filter(
    (item) => item.entity_type === entityTypes[section.value],
  ),
);

function openEditor(sectionKey, item = {}) {
  const idField = entityIds[sectionKey];
  editor.value = {
    sectionKey,
    entityType: entityTypes[sectionKey],
    entityId: item[idField] ?? "",
  };
  editorText.value = JSON.stringify(item, null, 2);
  editorError.value = "";
}

async function persistEditor() {
  try {
    const payload = JSON.parse(editorText.value);
    const idField = entityIds[editor.value.sectionKey];
    const entityId = String(payload[idField] ?? editor.value.entityId ?? "").trim();
    if (!entityId) throw new Error(`${idField} is required`);
    await saveMasterObject(editor.value.entityType, entityId, payload);
    editor.value = null;
    await reload();
  } catch (error) {
    editorError.value = error.message;
  }
}

async function archiveDraft(sectionKey, item) {
  const entityId = typeof item === "string"
    ? item
    : String(item[entityIds[sectionKey]] ?? "");
  await archiveMasterObject(entityTypes[sectionKey], entityId);
  await reload();
}

async function uploadConfiguration(event) {
  const file = event.target.files?.[0];
  if (!file) return;
  try {
    const payload = JSON.parse(await file.text());
    if (!Array.isArray(payload.touchpoints) || !Number.isInteger(payload.seed)) {
      throw new Error("Configuration requires an integer seed and touchpoints array.");
    }
    uploadedConfig.value = payload;
    editorError.value = "";
  } catch (error) {
    editorError.value = error.message;
  }
}

function downloadConfiguration(configuration) {
  const blob = new Blob([`${JSON.stringify(configuration, null, 2)}\n`], {
    type: "application/json",
  });
  const anchor = document.createElement("a");
  anchor.href = URL.createObjectURL(blob);
  anchor.download = "mta-sim-configuration.json";
  anchor.click();
  URL.revokeObjectURL(anchor.href);
}

const historicalTotals = computed(() => {
  const history = research.value.history ?? [];
  const delivery = research.value.delivery ?? [];
  const completeProfit = history.length > 0 && history.every(
    (row) => row.contribution_profit !== null && row.contribution_profit !== undefined,
  );
  return {
    configuredBudget: history.reduce((total, row) => total + Number(row.configured_budget ?? 0), 0),
    actualSpend: history.reduce((total, row) => total + Number(row.actual_spend ?? 0), 0),
    impressions: delivery.reduce((total, row) => total + Number(row.impressions ?? 0), 0),
    clicks: delivery.reduce((total, row) => total + Number(row.clicks ?? 0), 0),
    purchases: delivery.reduce((total, row) => total + Number(row.reported_purchases ?? 0), 0),
    units: history.reduce((total, row) => total + Number(row.total_units ?? 0), 0),
    revenue: history.reduce((total, row) => total + Number(row.total_revenue ?? 0), 0),
    contributionProfit: completeProfit
      ? history.reduce((total, row) => total + Number(row.contribution_profit), 0)
      : null,
  };
});

const researchTiles = computed(() => [
  { label: "Providers", value: theme.count((research.value.providers ?? []).length) },
  { label: "Products", value: theme.count((research.value.products ?? []).length) },
  { label: "Campaigns", value: theme.count((research.value.campaigns ?? []).length) },
  { label: "Ad Groups", value: theme.count((research.value.adGroups ?? []).length) },
  { label: "Touchpoints", value: theme.count((research.value.touchpoints ?? []).length) },
  { label: "Configured budget", value: theme.compactMoney(historicalTotals.value.configuredBudget) },
  { label: "Actual spend", value: theme.compactMoney(historicalTotals.value.actualSpend) },
  { label: "Impressions", value: theme.count(historicalTotals.value.impressions) },
  { label: "Clicks", value: theme.count(historicalTotals.value.clicks) },
  { label: "Purchases", value: theme.count(historicalTotals.value.purchases) },
  { label: "Units", value: theme.count(historicalTotals.value.units) },
  { label: "Revenue", value: theme.compactMoney(historicalTotals.value.revenue) },
  { label: "Contribution margin", value: historicalTotals.value.contributionProfit === null
    ? "Unavailable — economics incomplete"
    : theme.compactMoney(
        historicalTotals.value.contributionProfit + historicalTotals.value.actualSpend,
      ) },
  { label: "Advertising contribution profit", value: historicalTotals.value.contributionProfit === null
    ? "Unavailable — economics incomplete"
    : theme.compactMoney(historicalTotals.value.contributionProfit) },
]);

const budget = computed(() => data.value.budgetRecommendation ?? {});
const request = computed(() => data.value.strategyRequest ?? {});
const group = computed(() => request.value.campaign_group ?? {});
const currency = computed(() => currencySymbol(group.value.currency ?? "USD"));

const hasBudget = computed(() => (budget.value.campaigns ?? []).length > 0);

/** Flatten the nested recommendation into one row per Campaign. */
const campaigns = computed(() =>
  (budget.value.campaigns ?? []).map((entry) => {
    const contributions = entry.outcome_contributions ?? {};
    const bridge = entry.bridge_summary ?? {};
    return {
      campaign_id: entry.campaign_id,
      mta_score: Number(entry.campaign_mta_score ?? 0),
      budget_share: Number(entry.budget_seed_share ?? 0),
      daily_budget: Number(entry.campaign_budget_seed ?? 0),
      minimum_required: Number(entry.minimum_required_daily_budget ?? 0),
      ad_groups: Number(entry.recommended_ad_group_count ?? 0),
      converted_users: Number(contributions.converted_users ?? 0),
      purchase_count: Number(contributions.purchase_count ?? 0),
      revenue: Number(contributions.revenue ?? 0),
      historical_ad_groups: Number(bridge.historical_ad_group_count ?? 0),
      touchpoints: Number(bridge.touchpoint_count ?? 0),
      fallback_used: Boolean(bridge.fallback_used),
      execution_status: entry.execution_status ?? "",
    };
  }),
);

const handoff = computed(() => budget.value.handoff_status ?? "UNKNOWN");

const executable = computed(
  () => campaigns.value.filter((row) => row.execution_status === "EXECUTABLE").length,
);

const tiles = computed(() => [
  {
    label: "Total daily budget",
    value: theme.money(budget.value.budget_seed_total ?? 0, currency.value),
  },
  { label: "Campaigns", value: theme.count(campaigns.value.length) },
  {
    label: "New Ad Group slots",
    value: theme.count(campaigns.value.reduce((total, row) => total + row.ad_groups, 0)),
  },
  {
    label: "Group budget",
    value: theme.money(group.value.total_daily_budget ?? 0, currency.value),
    note: "From the strategy request",
  },
]);

/** Recommended daily budget per Campaign, against the required minimum. */
const allocationTraces = computed(() => {
  const ordered = sortBy(campaigns.value, "daily_budget");
  if (ordered.length === 0) return [];
  return [
    {
      type: "bar",
      orientation: "h",
      name: "Recommended",
      y: ordered.map((row) => row.campaign_id),
      x: ordered.map((row) => row.daily_budget),
      marker: { color: theme.SERIES[0], line: { color: theme.SURFACE, width: 2 } },
      text: ordered.map((row) => theme.money(row.daily_budget, currency.value)),
      textposition: "outside",
      textfont: { size: 11, color: theme.MUTED },
      hovertemplate: "<b>%{y}</b><br>Recommended %{x:,.2f}<extra></extra>",
    },
    {
      type: "scatter",
      mode: "markers",
      name: "Required minimum",
      y: ordered.map((row) => row.campaign_id),
      x: ordered.map((row) => row.minimum_required),
      marker: {
        color: theme.SERIES[7],
        size: 13,
        symbol: "line-ns-open",
        line: { color: theme.SERIES[7], width: 3 },
      },
      hovertemplate: "Minimum required %{x:,.2f}<extra></extra>",
    },
  ];
});

const allocationLayout = computed(() =>
  theme.layout({
    height: 300,
    xaxis: { title: { text: `Daily budget (${currency.value.trim()})` } },
  }),
);

const derivation = computed(() => budget.value.budget_derivation ?? {});

const weights = computed(() => {
  const source =
    Object.keys(derivation.value.outcome_weights ?? {}).length > 0
      ? derivation.value.outcome_weights
      : (request.value.outcome_weights ?? {});
  return Object.entries(source).map(([key, value]) => ({
    label: OUTCOME_LABELS[key] ?? key,
    value: Number(value).toFixed(2),
  }));
});

const formulaRows = computed(() => [
  { label: "Version", value: derivation.value.formula_version ?? "--" },
  { label: "Normalisation", value: derivation.value.normalization_universe ?? "--" },
  { label: "Optimised", value: budget.value.is_optimized ? "Yes" : "No" },
  { label: "Schema", value: budget.value.schema_version ?? "--" },
]);

/** How each outcome contributed to each Campaign's score. */
const scoreTraces = computed(() => {
  const ordered = sortBy(campaigns.value, "mta_score", "desc");
  return Object.entries(OUTCOME_LABELS).map(([key, label]) => ({
    type: "bar",
    name: label,
    x: ordered.map((row) => row.campaign_id),
    y: ordered.map((row) => row[key]),
    marker: {
      color: theme.OUTCOME_COLORS[key],
      line: { color: theme.SURFACE, width: 2 },
    },
    hovertemplate: `<b>${label}</b><br>%{x}<br>Contribution %{y:.4f}<extra></extra>`,
  }));
});

const scoreLayout = computed(() =>
  theme.layout({
    height: 300,
    barmode: "stack",
    yaxis: { title: { text: "Normalised outcome contribution" } },
  }),
);

const campaignRows = computed(() => sortBy(campaigns.value, "mta_score", "desc"));

const campaignColumns = [
  { key: "campaign_id", label: "Campaign" },
  { key: "mta_score", label: "MTA score", format: "share", digits: 6 },
  { key: "budget_share", label: "Share", format: "share" },
  { key: "daily_budget", label: "Daily budget", format: "money" },
  { key: "minimum_required", label: "Minimum", format: "money" },
  { key: "ad_groups", label: "New slots", format: "number" },
  { key: "historical_ad_groups", label: "Historical", format: "number" },
  { key: "touchpoints", label: "Touchpoints", format: "number" },
  { key: "execution_status", label: "Status" },
];

/** The anonymous Ad Group slots the Campaign budget is divided into. */
const slots = computed(() =>
  (budget.value.campaigns ?? []).flatMap((entry) =>
    (entry.recommended_ad_groups ?? []).map((slot) => ({
      campaign_id: entry.campaign_id,
      slot: slot.ad_group_slot_id ?? "",
      basis: slot.allocation_basis ?? "",
      share: Number(slot.budget_seed_share ?? 0),
      daily_budget: Number(slot.initial_daily_budget ?? 0),
    })),
  ),
);

const slotColumns = [
  { key: "campaign_id", label: "Campaign" },
  { key: "slot", label: "Slot" },
  { key: "basis", label: "Allocation basis" },
  { key: "share", label: "Share", format: "share" },
  { key: "daily_budget", label: "Daily budget", format: "money" },
];
</script>

<template>
  <section class="page-grid">
    <p class="caption">
      Deterministic initial allocation derived from historical attribution. This
      is a seed, not an optimiser result.
    </p>

    <div class="tabs" role="tablist" aria-label="Budget Manager sections">
      <button
        v-for="[key, label] in SECTIONS"
        :key="key"
        class="tab"
        role="tab"
        :aria-selected="section === key"
        :class="{ active: section === key }"
        @click="section = key"
      >
        {{ label }}
      </button>
    </div>

    <div v-show="section === 'overview'" class="page-grid">
      <template v-if="(research.history ?? []).length">
        <MetricRow :items="researchTiles" />
        <p class="caption">
          Historical observations are immutable. Change a future-run
          configuration and regenerate data to alter these values.
        </p>
      </template>

    <template v-if="hasBudget">
      <ReliabilityBanner
        :status="handoff === 'READY_FOR_OPTIMIZATION' ? 'RELIABLE' : 'PARTIAL'"
      >
        Handoff status <b>{{ handoff }}</b> · {{ executable }} of
        {{ campaigns.length }} Campaigns executable · recommendation type
        <b>{{ budget.recommendation_type || "--" }}</b>.
      </ReliabilityBanner>

      <MetricRow :items="tiles" />

      <div class="page-grid two-up">
        <article class="card">
          <div class="card-head">
            <h2>Recommended daily budget</h2>
            <span class="sub">Against each Campaign's required minimum</span>
          </div>
          <div class="card-body">
            <PlotlyChart
              :traces="allocationTraces"
              :layout="allocationLayout"
              label="Recommended daily budget per Campaign against its required minimum"
            />
            <p class="caption">
              Every recommended budget clears its Campaign's required minimum,
              which is the per-Ad-Group floor times the recommended slot count.
            </p>
          </div>
        </article>

        <article class="card">
          <div class="card-head">
            <h2>Derivation</h2>
          </div>
          <div class="card-body">
            <KeyValuePanel title="Formula" :rows="formulaRows" />
            <KeyValuePanel title="Outcome weights" :rows="weights" />
            <p class="caption">
              The MTA score is the weighted sum of a Campaign's three normalised
              outcome contributions. Budget share is that score, renormalised.
            </p>
          </div>
        </article>
      </div>

      <article class="card">
        <div class="card-head">
          <h2>Score composition</h2>
          <span class="sub">Stacked contributions before weighting</span>
        </div>
        <div class="card-body">
          <PlotlyChart
            :traces="scoreTraces"
            :layout="scoreLayout"
            label="Each Campaign's normalised outcome contributions, stacked"
          />
          <p class="caption">
            A Campaign leading on revenue but trailing on converted users is
            visible here, not in the total.
          </p>
          <DataTable :columns="campaignColumns" :rows="campaignRows" />
        </div>
      </article>

      <article class="card">
        <div class="card-head">
          <h2>Ad Group slots</h2>
        </div>
        <div class="card-body">
          <DataTable
            :columns="slotColumns"
            :rows="slots"
            empty="No Ad Group slots in this recommendation."
          />
          <p class="caption">
            Slots are anonymous: a proposed Ad Group has no history yet, so it
            carries no historical identifier.
          </p>
        </div>
      </article>
    </template>

    <article v-else class="card empty-card">
      <h2>No budget recommendation</h2>
      <p>
        No budget recommendation is available from the current data source. Run
        the pipeline, or switch <code>DATABASE</code> in <code>.env</code>.
      </p>
    </article>
    </div>

    <article v-if="section === 'providers'" class="card">
      <div class="card-head">
        <h2>Ad Providers</h2>
        <button v-if="databaseEditing" @click="openEditor('providers')">Add Provider draft</button>
      </div>
      <div class="card-body detail-list">
        <details v-for="item in research.providers ?? []" :key="`${item.run_id}:${item.provider}`">
          <summary>{{ item.provider }} <span class="sub">{{ item.active === false ? 'Archived' : 'Active' }}</span></summary>
          <p><b>Supported ad products:</b> {{ (item.supported_ad_products ?? []).join(', ') || 'None declared' }}</p>
          <p><b>Field capabilities:</b> format {{ item.format_availability }}, placement {{ item.placement_availability }}, creative {{ item.creative_availability }}, interaction {{ item.interaction_type_availability }}</p>
          <p v-if="item.provider !== 'AMAZON_ADS'" class="caption">Synthetic research Provider; it is not a claim about a commercial API.</p>
          <button v-if="databaseEditing" @click="openEditor('providers', item)">Create editable draft</button>
        </details>
        <p v-if="!(research.providers ?? []).length" class="table-empty">No simulator Provider configuration loaded.</p>
      </div>
    </article>

    <article v-if="section === 'products'" class="card">
      <div class="card-head"><h2>Products</h2><button v-if="databaseEditing" @click="openEditor('products')">Add Product draft</button></div>
      <div class="card-body detail-list">
        <details v-for="item in research.products ?? []" :key="`${item.run_id}:${item.product_id}`">
          <summary>{{ item.name || item.product_id }} <span class="sub">{{ item.sku_id || 'SKU unavailable' }}</span></summary>
          <p><b>Category / brand:</b> {{ item.category || 'Unavailable' }} / {{ item.brand || 'Unavailable' }}</p>
          <p><b>Inventory:</b> {{ item.inventory_units ?? 'Unavailable' }} · <b>Salable:</b> {{ item.salable ?? 'Unavailable' }} · <b>Status:</b> {{ item.status || 'Unavailable' }}</p>
          <p><b>Provider identifiers:</b> {{ JSON.stringify(item.provider_ad_identifiers ?? {}) }}</p>
          <button v-if="databaseEditing" @click="openEditor('products', item)">Create editable draft</button>
        </details>
        <p v-if="!(research.products ?? []).length" class="table-empty">No simulator Products loaded.</p>
      </div>
    </article>

    <article v-if="section === 'campaigns'" class="card">
      <div class="card-head"><h2>Campaign master configuration</h2><button v-if="databaseEditing" @click="openEditor('campaigns')">Add Campaign draft</button></div>
      <div class="card-body detail-list">
        <details v-for="item in research.campaigns ?? []" :key="`${item.run_id}:${item.campaign_id}`">
          <summary>{{ item.campaign_name || item.campaign_id }} <span class="sub">{{ item.status }}</span></summary>
          <p><b>Provider / ad product:</b> {{ item.provider }} / {{ item.ad_product }}</p>
          <p><b>Baseline daily budget:</b> {{ item.baseline_daily_budget ?? 'Unavailable' }}</p>
          <p><b>Products:</b> {{ (research.campaignProductLinks ?? []).filter((link) => link.campaign_id === item.campaign_id).map((link) => link.product_id).join(', ') || 'None' }}</p>
          <p><b>Ad Groups:</b> {{ (research.adGroups ?? []).filter((group) => group.campaign_id === item.campaign_id).map((group) => group.ad_group_id).join(', ') || 'None' }}</p>
          <p><b>Touchpoint configs:</b> {{ (item.touchpoint_identifiers ?? []).join(', ') || 'None' }}</p>
          <button v-if="databaseEditing" @click="openEditor('campaigns', item)">Create editable draft</button>
        </details>
        <p v-if="!(research.campaigns ?? []).length" class="table-empty">No simulator Campaigns loaded.</p>
      </div>
    </article>

    <article v-if="section === 'adGroups'" class="card">
      <div class="card-head"><h2>Ad Groups</h2><button v-if="databaseEditing" @click="openEditor('adGroups')">Add Ad Group draft</button></div>
      <div class="card-body detail-list">
        <details v-for="item in research.adGroups ?? []" :key="`${item.run_id}:${item.ad_group_id}`">
          <summary>{{ item.name || item.ad_group_id }} <span class="sub">Campaign {{ item.campaign_id }}</span></summary>
          <p><b>Status:</b> {{ item.status || 'Unavailable' }} · <b>Initial daily budget:</b> {{ item.initial_daily_budget ?? 'Unavailable' }}</p>
          <button v-if="databaseEditing" @click="openEditor('adGroups', item)">Create editable draft</button>
        </details>
        <p v-if="!(research.adGroups ?? []).length" class="table-empty">No simulator Ad Groups loaded.</p>
      </div>
    </article>

    <article v-if="section === 'touchpoints'" class="card">
      <div class="card-head"><h2>Structured Touchpoints</h2><button v-if="databaseEditing" @click="openEditor('touchpoints')">Add Touchpoint draft</button></div>
      <div class="card-body detail-list">
        <details v-for="item in research.touchpoints ?? []" :key="`${item.run_id}:${item.identifier}`">
          <summary>{{ item.identifier }} <span class="sub">{{ item.provider }} · {{ item.ad_product }}</span></summary>
          <p><b>Format:</b> {{ item.format }} · <b>Placement:</b> {{ item.placement ?? 'Unavailable' }} ({{ item.placement_availability }}) · <b>Creative:</b> {{ item.creative ?? 'Unavailable' }} ({{ item.creative_availability }})</p>
          <p><b>Interactions:</b> {{ (item.supported_interactions ?? [item.impression_enabled && 'IMPRESSION', item.click_enabled && 'CLICK'].filter(Boolean)).join(', ') }} · availability {{ item.interaction_type_availability }}</p>
          <p><b>Billing:</b> {{ item.billing_type }} · CPC {{ item.cost_per_click ?? 'N/A' }} · CPM {{ item.cost_per_thousand_impressions ?? 'N/A' }}</p>
          <p><b>Generation:</b> base impressions {{ item.base_impressions }}, CTR {{ item.click_through_rate }}, platform conversion rate {{ item.platform_conversion_rate }}, conversion effect {{ item.conversion_log_odds_effect }}</p>
          <p><b>Five-segment display keys:</b> <code>{{ (item.compatibility_keys ?? []).join(' · ') }}</code></p>
          <button v-if="databaseEditing" @click="openEditor('touchpoints', item)">Create editable draft</button>
        </details>
        <p v-if="!(research.touchpoints ?? []).length" class="table-empty">No simulator Touchpoint configuration loaded.</p>
      </div>
    </article>

    <article v-if="section === 'productEconomics'" class="card">
      <div class="card-head"><h2>Product Economics</h2><button v-if="databaseEditing" @click="openEditor('productEconomics')">Add economics draft</button></div>
      <div class="card-body detail-list">
        <details v-for="item in research.productEconomics ?? []" :key="`${item.run_id}:${item.product_id}:${item.currency}`">
          <summary>{{ item.product_id }} · {{ item.currency }}</summary>
          <p><b>Price:</b> {{ item.unit_price ?? 'Unavailable' }} · <b>COGS:</b> {{ item.unit_cogs ?? 'Unavailable' }} · <b>Aggregate variable cost:</b> {{ item.variable_cost_per_unit ?? 'Unavailable' }}</p>
          <p><b>Fulfillment:</b> {{ item.variable_fulfillment_cost_per_unit ?? 'Unavailable' }} · <b>Platform fee:</b> {{ item.variable_platform_fee_per_unit ?? 'Unavailable' }} · <b>Other variable cost:</b> {{ item.other_variable_cost_per_unit ?? 'Unavailable' }}</p>
          <p><b>Contribution margin:</b> {{ item.unit_contribution_margin ?? 'Unavailable — economics incomplete' }} · {{ item.margin_source || 'No source' }}</p>
          <button v-if="databaseEditing" @click="openEditor('productEconomics', item)">Create editable draft</button>
        </details>
        <p v-if="!(research.productEconomics ?? []).length" class="table-empty">Product economics are unavailable; missing COGS is not treated as zero.</p>
      </div>
    </article>

    <article v-if="section === 'generationConfigs'" class="card">
      <div class="card-head"><h2>Generation Configs</h2></div>
      <div class="card-body detail-list">
        <p class="caption">Uploaded or edited configurations apply only to a future run. Existing historical records retain their immutable run snapshot.</p>
        <label class="button-like">Upload and validate JSON <input type="file" accept="application/json,.json" @change="uploadConfiguration" /></label>
        <button v-if="uploadedConfig" @click="downloadConfiguration(uploadedConfig)">Download uploaded config</button>
        <details v-for="item in research.generationConfigs ?? []" :key="item.run_id">
          <summary>{{ item.run_id }} <span class="sub">seed {{ item.seed }}</span></summary>
          <p><b>Configuration SHA-256:</b> <code>{{ item.configuration_sha256 }}</code></p>
          <pre><code>{{ JSON.stringify(item.effective_configuration, null, 2) }}</code></pre>
          <button @click="downloadConfiguration(item.effective_configuration)">Download snapshot</button>
          <button v-if="databaseEditing" @click="openEditor('generationConfigs', { run_id: `${item.run_id}-future`, ...item.effective_configuration })">Edit as future-run draft</button>
        </details>
        <p v-if="editorError" class="error-detail">{{ editorError }}</p>
      </div>
    </article>

    <article
      v-if="databaseEditing && section !== 'overview' && sectionDrafts.length"
      class="card"
    >
      <div class="card-head"><h2>Editable future-run drafts</h2></div>
      <div class="card-body detail-list">
        <details v-for="draft in sectionDrafts" :key="`${draft.entity_type}:${draft.entity_id}`">
          <summary>{{ draft.entity_id }} <span class="sub">{{ draft.active ? 'Active draft' : 'Archived draft' }}</span></summary>
          <pre><code>{{ JSON.stringify(draft.payload, null, 2) }}</code></pre>
          <button v-if="draft.active" @click="archiveDraft(section, draft.entity_id)">Archive draft</button>
        </details>
      </div>
    </article>

    <div v-if="editor" class="modal-backdrop" @click.self="editor = null">
      <section class="modal" role="dialog" aria-modal="true" aria-label="Master configuration editor">
        <div class="modal-head"><h2>Future-run {{ editor.entityType }} draft</h2><button @click="editor = null">Close</button></div>
        <div class="modal-body">
          <p>Generated observations are read-only. Saving this object creates or updates a separate future-run draft.</p>
          <textarea v-model="editorText" rows="20" spellcheck="false"></textarea>
          <p v-if="editorError" class="error-detail">{{ editorError }}</p>
          <button @click="persistEditor">Validate and save</button>
        </div>
      </section>
    </div>
  </section>
</template>
