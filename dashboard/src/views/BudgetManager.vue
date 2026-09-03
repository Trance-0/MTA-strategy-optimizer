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
import { computed, ref, watch } from "vue";

import ConfirmDialog from "../components/ConfirmDialog.vue";
import DataTable from "../components/DataTable.vue";
import EntityTable from "../components/EntityTable.vue";
import KeyValuePanel from "../components/KeyValuePanel.vue";
import MasterObjectForm from "../components/MasterObjectForm.vue";
import MetricRow from "../components/MetricRow.vue";
import PlotlyChart from "../components/PlotlyChart.vue";
import ReliabilityBanner from "../components/ReliabilityBanner.vue";
import { OUTCOME_LABELS, currencySymbol, sortBy } from "../lib/common.js";
import { buildTemplate } from "../lib/masterObjectFields.js";
import { useDashboard } from "../lib/useDashboard.js";
import { useDeployment } from "../lib/deployment.js";
import { useDiagnostics } from "../lib/diagnostics.js";
import {
  archiveMasterObject,
  saveMasterObject,
} from "../api/client.js";
import * as theme from "../theme.js";

const props = defineProps({ section: { type: String, default: "overview" } });
const emit = defineEmits(["navigate"]);
const { data, reload } = useDashboard();
const { writable, readOnlyReason } = useDeployment();
const { diagnosticsOn } = useDiagnostics();
const research = computed(() => data.value.simulationResearch ?? {});
const ROUTE_TO_SECTION = {
  overview: "overview", providers: "providers", products: "products",
  campaigns: "campaigns", "ad-groups": "adGroups", touchpoints: "touchpoints",
  "product-economics": "productEconomics", "generation-configs": "generationConfigs",
};
const SECTION_TO_ROUTE = Object.fromEntries(
  Object.entries(ROUTE_TO_SECTION).map(([route, key]) => [key, route]),
);
const section = computed(() => ROUTE_TO_SECTION[props.section] ?? "overview");
const navigateSection = (key) => emit("navigate", SECTION_TO_ROUTE[key] ?? "overview");

/**
 * The catalogue sections, in the order a reader works down the account.
 *
 * `generationConfigs` describes how a data run was produced, which is a
 * diagnostic concern rather than a marketing one, so it appears only when
 * diagnostics are switched on in Settings. A reader planning budget never
 * meets it.
 */
const BASE_SECTIONS = [
  ["overview", "Overview"],
  ["providers", "Ad Providers"],
  ["products", "Products"],
  ["campaigns", "Campaigns"],
  ["adGroups", "Ad Groups"],
  ["touchpoints", "Touchpoints"],
  ["productEconomics", "Product Economics"],
];
const SECTIONS = computed(() =>
  diagnosticsOn.value
    ? [...BASE_SECTIONS, ["generationConfigs", "Data Run Diagnostics"]]
    : BASE_SECTIONS,
);

// Switching diagnostics off while its section is open would otherwise leave
// the reader on a tab that no longer has a button, with no way back.
watch(SECTIONS, (sections) => {
  if (!sections.some(([key]) => key === section.value)) navigateSection("overview");
}, { immediate: true });
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
const editorMode = ref("form");
const editorRecord = ref({});
const editorText = ref("");
const editorError = ref("");
const uploadedConfig = ref(null);

/**
 * Editing is allowed only where there is a database to write to. The published
 * build and a local file-mode run are both read-only, for the same reason.
 */
const databaseEditing = writable;

const sectionDrafts = computed(() =>
  (research.value.masterObjects ?? []).filter(
    (item) => item.entity_type === entityTypes[section.value],
  ),
);

// ---------------------------------------------------------------------------
// The row abstracts
// ---------------------------------------------------------------------------

/**
 * The summary columns for each entity section.
 *
 * A row is an abstract, not the record: these are the fields a reader scans a
 * list by. Everything else about a record is behind that row's Edit control,
 * which shows the whole object. The detail formerly rendered as stacked
 * paragraphs is therefore still reachable, but it no longer competes with the
 * list for the page.
 */
const SECTION_COLUMNS = {
  providers: [
    { key: "provider", label: "Provider" },
    { key: "supported_ad_products", label: "Supported ad products" },
    { key: "format_availability", label: "Format" },
    { key: "placement_availability", label: "Placement" },
    { key: "creative_availability", label: "Creative" },
    { key: "interaction_type_availability", label: "Interaction" },
    {
      key: "active",
      label: "State",
      format: (value) => (value === false ? "Archived" : "Active"),
      tone: (value) => (value === false ? "gray" : "green"),
    },
  ],
  products: [
    { key: "product_id", label: "Product" },
    { key: "name", label: "Name" },
    { key: "sku_id", label: "SKU" },
    { key: "advertised_asin", label: "ASIN" },
    { key: "category", label: "Category" },
    { key: "brand", label: "Brand" },
    { key: "inventory_units", label: "Inventory", format: "number" },
    { key: "salable", label: "Salable", format: "flag" },
    { key: "status", label: "Status" },
  ],
  campaigns: [
    { key: "campaign_id", label: "Campaign" },
    { key: "campaign_name", label: "Name" },
    { key: "provider", label: "Provider" },
    { key: "ad_product", label: "Ad product" },
    {
      key: "baseline_daily_budget",
      label: "Baseline daily budget",
      format: "money",
    },
    { key: "observed_cost", label: "Reported spend", format: "money" },
    { key: "product_count", label: "Products", format: "number" },
    { key: "ad_group_count", label: "Ad Groups", format: "number" },
    { key: "status", label: "Status" },
  ],
  adGroups: [
    { key: "ad_group_id", label: "Ad Group" },
    { key: "name", label: "Name" },
    { key: "campaign_id", label: "Campaign" },
    { key: "keyword_count", label: "Keywords", format: "number" },
    { key: "target_count", label: "Targets", format: "number" },
    { key: "audience_count", label: "Audiences", format: "number" },
    {
      key: "initial_daily_budget",
      label: "Initial daily budget",
      format: "money",
    },
    { key: "status", label: "Status" },
  ],
  touchpoints: [
    { key: "identifier", label: "Identifier" },
    { key: "provider", label: "Provider" },
    { key: "ad_product", label: "Ad product" },
    { key: "format", label: "Format" },
    { key: "placement", label: "Placement" },
    { key: "creative", label: "Creative" },
    { key: "supported_interactions", label: "Interactions" },
    { key: "billing_type", label: "Billing" },
    { key: "cost_per_click", label: "CPC", format: "money" },
    { key: "cost_per_thousand_impressions", label: "CPM", format: "money" },
    { key: "observed_impressions", label: "Impressions", format: "number" },
    { key: "observed_clicks", label: "Clicks", format: "number" },
    { key: "observed_cost", label: "Spend", format: "money" },
  ],
  productEconomics: [
    { key: "product_id", label: "Product" },
    { key: "currency", label: "Currency" },
    { key: "observed_purchases", label: "Purchases", format: "number" },
    { key: "observed_revenue", label: "Revenue", format: "money" },
    { key: "unit_price", label: "Price", format: "money" },
    { key: "unit_cogs", label: "COGS", format: "money" },
    {
      key: "variable_cost_per_unit",
      label: "Variable cost",
      format: "money",
    },
    {
      key: "unit_contribution_margin",
      label: "Contribution margin",
      // Missing economics stay missing. `renderCell` shows `--` for null, and
      // treating it as zero here would invent a margin the data does not have.
      format: "money",
    },
    { key: "margin_source", label: "Source" },
  ],
  generationConfigs: [
    { key: "run_id", label: "Run" },
    { key: "seed", label: "Seed", format: "number" },
    { key: "configuration_sha256", label: "Configuration SHA-256" },
  ],
};

/** The rows behind each section, with the counts a summary column needs. */
const SECTION_ROWS = {
  providers: () => research.value.providers ?? [],
  products: () => research.value.products ?? [],
  campaigns: () =>
    (research.value.campaigns ?? []).map((item) => ({
      ...item,
      product_count: (research.value.campaignProductLinks ?? []).filter(
        (link) => link.campaign_id === item.campaign_id,
      ).length,
      ad_group_count: (research.value.adGroups ?? []).filter(
        (group) => group.campaign_id === item.campaign_id,
      ).length,
    })),
  adGroups: () => research.value.adGroups ?? [],
  touchpoints: () => research.value.touchpoints ?? [],
  productEconomics: () => research.value.productEconomics ?? [],
  generationConfigs: () => research.value.generationConfigs ?? [],
};

const sectionColumns = computed(() => SECTION_COLUMNS[section.value] ?? []);
const sectionRows = computed(() => SECTION_ROWS[section.value]?.() ?? []);

/**
 * Why a section is empty, rather than only that it is.
 *
 * The catalogue is read from the account's own reports, so a section stands
 * empty only when those reports carry no record of that kind -- not because
 * the dashboard failed to load. Naming the cause is what separates "nothing
 * to show here" from "something broke".
 */
const emptyMessage = computed(() => {
  const label = SECTIONS.value.find(([key]) => key === section.value)?.[1] ?? "record";
  if (writable.value) {
    return `No ${label} records in the connected database. The reporting ` +
      `window may predate this part of the account.`;
  }
  return `No ${label} records in the current reporting window.`;
});

/**
 * A row's stable identity.
 *
 * Composed with the run identifier where one record is unique only within its
 * run, which is exactly the keying the old `v-for` used. Selection and paging
 * both depend on this being stable across a reload.
 */
function rowKeyFor(sectionKey, row) {
  const idField = entityIds[sectionKey];
  const base = String(row[idField] ?? "");
  if (sectionKey === "generationConfigs") return base;
  if (sectionKey === "productEconomics") {
    return [row.run_id, base, row.currency].filter(Boolean).join(":");
  }
  return [row.run_id, base].filter(Boolean).join(":");
}

const rowKey = (row) => rowKeyFor(section.value, row);

const draftColumns = [
  { key: "entity_id", label: "Identifier" },
  {
    key: "active",
    label: "State",
    format: (value) => (value ? "Active draft" : "Archived draft"),
    tone: (value) => (value ? "green" : "gray"),
  },
  { key: "updated_at", label: "Updated" },
];

// ---------------------------------------------------------------------------
// Editing
// ---------------------------------------------------------------------------

function openEditor(sectionKey, item = {}) {
  const idField = entityIds[sectionKey];
  editor.value = {
    sectionKey,
    entityType: entityTypes[sectionKey],
    entityId: item[idField] ?? "",
    /** A new draft has no identifier yet; the modal titles itself from this. */
    creating: !item[idField],
  };
  // Every recognized field is present from the start, blank rather than
  // absent, so the Form editor never has to explain a missing row and the
  // JSON editor never starts a new draft from a bare `{}`.
  const record = { ...buildTemplate(sectionKey), ...item };
  editorRecord.value = record;
  editorText.value = JSON.stringify(record, null, 2);
  editorMode.value = "form";
  editorError.value = "";
}

/** Bring the JSON view up to date with whatever the Form view holds. */
function switchToJsonMode() {
  editorText.value = JSON.stringify(editorRecord.value, null, 2);
  editorMode.value = "json";
  editorError.value = "";
}

/** Parse the JSON view back into the Form view, refusing to lose edits. */
function switchToFormMode() {
  try {
    editorRecord.value = JSON.parse(editorText.value);
    editorMode.value = "form";
    editorError.value = "";
  } catch (error) {
    editorError.value = `Fix the JSON before switching to the Form view: ${error.message}`;
  }
}

/** Open the editor on a row, dropping the columns the table added for display. */
function editRow(row) {
  const record = { ...row };
  delete record.product_count;
  delete record.ad_group_count;
  openEditor(section.value, record);
}

async function persistEditor() {
  try {
    const payload =
      editorMode.value === "json" ? JSON.parse(editorText.value) : editorRecord.value;
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

// ---------------------------------------------------------------------------
// Deletion, always behind a confirmation
// ---------------------------------------------------------------------------

/**
 * The pending deletion: which section, and which identifiers.
 *
 * Held as identifiers rather than as rows, because the confirmation is what
 * the reader checks and the request is what the server receives, and both are
 * expressed in identifiers.
 */
const pendingDelete = ref(null);
const deleteBusy = ref(false);
const deleteError = ref("");

function identifierOf(sectionKey, row) {
  return String(row[entityIds[sectionKey]] ?? "");
}

function requestDelete(row) {
  deleteError.value = "";
  pendingDelete.value = {
    sectionKey: section.value,
    ids: [identifierOf(section.value, row)],
  };
}

function requestBatchDelete(rows) {
  deleteError.value = "";
  pendingDelete.value = {
    sectionKey: section.value,
    ids: rows.map((row) => identifierOf(section.value, row)),
  };
}

const entityTable = ref(null);

/**
 * Archive every pending identifier, then reload once.
 *
 * Sequential rather than concurrent: each archive clears the server's caches,
 * and a batch fired in parallel would have them racing each other. A failure
 * stops the run and reports which identifier failed, leaving the dialog open —
 * reporting "done" after a partial batch would be a false statement about what
 * is now in the database.
 */
async function confirmDelete() {
  if (!pendingDelete.value) return;
  deleteBusy.value = true;
  deleteError.value = "";
  const { sectionKey, ids } = pendingDelete.value;
  try {
    for (const [index, id] of ids.entries()) {
      try {
        await archiveMasterObject(entityTypes[sectionKey], id);
      } catch (error) {
        throw new Error(
          `${error.message} — archived ${index} of ${ids.length}; ` +
            `stopped at ${id}.`,
        );
      }
    }
    pendingDelete.value = null;
    entityTable.value?.clearSelection();
    await reload();
  } catch (error) {
    deleteError.value = error.message;
  } finally {
    deleteBusy.value = false;
  }
}

function cancelDelete() {
  pendingDelete.value = null;
  deleteError.value = "";
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
  anchor.download = "data-run-configuration.json";
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

/**
 * The observation range the totals above were summed over.
 *
 * The backend answers an unbounded history request with its recent-quarter
 * default, so these totals are a period's, not the account's whole record. A
 * tile that says "Actual spend" over a slice the reader did not choose and
 * cannot see is a wrong number, so the period is stated beneath them.
 */
const historyWindow = computed(() => research.value.historyWindow ?? {});
const historyPeriod = computed(() => {
  const { start, end, earliest, latest } = historyWindow.value;
  if (!earliest || !latest) return "";
  const from = start || earliest;
  const to = end || latest;
  if (from === earliest && to === latest) {
    return `Covering the complete recorded history, ${earliest} to ${latest}.`;
  }
  return `Covering ${from} to ${to}. The account's recorded history runs ` +
    `${earliest} to ${latest}; Campaign history can be read over any range.`;
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
        @click="navigateSection(key)"
      >
        {{ label }}
      </button>
    </div>

    <div v-show="section === 'overview'" class="page-grid">
      <template v-if="(research.history ?? []).length">
        <MetricRow :items="researchTiles" />
        <p class="caption">
          Reported performance is a record of what the account already
          delivered, so it is read-only. Plan changes apply to future spend.
          {{ historyPeriod }}
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

    <!--
      Every entity section is one paged table. The section decides the columns,
      the rows, and the identity of a row; the table itself is identical in all
      seven, so a reader learns one list and reads them all.
    -->
    <template v-if="section !== 'overview'">
      <article class="card">
        <div class="card-head">
          <h2>{{ SECTIONS.find(([key]) => key === section)?.[1] }}</h2>
          <span class="sub">
            {{ databaseEditing
              ? "Editing writes a planned change; reported performance is immutable."
              : "Read-only in this deployment." }}
          </span>
        </div>
        <div class="card-body">
          <div v-if="!databaseEditing" class="notice">
            {{ readOnlyReason }}
          </div>

          <template v-if="section === 'generationConfigs'">
            <p class="caption">
              Diagnostic only: how the current data run was produced. Uploading
              a configuration affects future runs; records already loaded keep
              the snapshot they were read under.
            </p>
            <div class="rec-actions">
              <label class="btn button-like">
                Upload and validate JSON
                <input
                  type="file"
                  accept="application/json,.json"
                  @change="uploadConfiguration"
                />
              </label>
              <button
                v-if="uploadedConfig"
                class="btn"
                @click="downloadConfiguration(uploadedConfig)"
              >
                Download uploaded config
              </button>
            </div>
          </template>

          <EntityTable
            ref="entityTable"
            :key="section"
            :columns="sectionColumns"
            :rows="sectionRows"
            :row-key="rowKey"
            :selectable="databaseEditing"
            :editable="databaseEditing"
            :deletable="databaseEditing"
            :noun="section === 'generationConfigs' ? 'config' : 'record'"
            :empty="emptyMessage"
            @edit="editRow"
            @delete="requestDelete"
            @delete-many="requestBatchDelete"
          >
            <template v-if="databaseEditing" #toolbar-start>
              <button class="btn primary" @click="openEditor(section)">
                Add {{ SECTIONS.find(([key]) => key === section)?.[1] }} draft
              </button>
            </template>
          </EntityTable>

          <p v-if="section === 'productEconomics'" class="caption">
            A blank contribution margin means the economics are incomplete;
            missing Cost of Goods Sold is never treated as zero.
          </p>
          <p v-if="editorError && !editor" class="error-detail">{{ editorError }}</p>
        </div>
      </article>

      <article v-if="databaseEditing && sectionDrafts.length" class="card">
        <div class="card-head">
          <h2>Planned changes</h2>
          <span class="sub">{{ sectionDrafts.length }} in this section</span>
        </div>
        <div class="card-body">
          <DataTable :columns="draftColumns" :rows="sectionDrafts" />
          <p class="caption">
            A planned change applies to future spend. Archiving one never
            alters reported performance.
          </p>
        </div>
      </article>
    </template>

    <div v-if="editor" class="modal-backdrop" @click.self="editor = null">
      <section class="modal" role="dialog" aria-modal="true" aria-label="Master configuration editor">
        <div class="modal-head">
          <h2>
            {{ editor.creating ? "New" : "Edit" }} planned
            {{ editor.entityType }} change
          </h2>
          <button class="btn small" @click="editor = null">Close</button>
        </div>
        <div class="modal-body">
          <p>
            Reported performance is read-only. Saving this object records a
            separate planned change that applies to future spend.
          </p>

          <div class="tabs editor-mode-tabs" role="tablist" aria-label="Editor mode">
            <button
              class="tab"
              role="tab"
              type="button"
              :aria-selected="editorMode === 'form'"
              :class="{ active: editorMode === 'form' }"
              @click="editorMode === 'json' ? switchToFormMode() : null"
            >
              Form
            </button>
            <button
              class="tab"
              role="tab"
              type="button"
              :aria-selected="editorMode === 'json'"
              :class="{ active: editorMode === 'json' }"
              @click="editorMode === 'form' ? switchToJsonMode() : null"
            >
              JSON
            </button>
          </div>

          <MasterObjectForm
            v-if="editorMode === 'form'"
            v-model="editorRecord"
            :section-key="editor.sectionKey"
          />
          <textarea
            v-else
            v-model="editorText"
            rows="20"
            spellcheck="false"
          ></textarea>

          <p v-if="editorError" class="error-detail">{{ editorError }}</p>
          <div class="rec-actions">
            <button class="btn" @click="editor = null">Cancel</button>
            <button class="btn primary" @click="persistEditor">
              Validate and save
            </button>
          </div>
        </div>
      </section>
    </div>

    <ConfirmDialog
      :open="Boolean(pendingDelete)"
      :title="
        pendingDelete && pendingDelete.ids.length > 1
          ? `Archive ${pendingDelete.ids.length} drafts?`
          : 'Archive this draft?'
      "
      :items="pendingDelete?.ids ?? []"
      :busy="deleteBusy"
      :error="deleteError"
      confirm-label="Archive"
      @confirm="confirmDelete"
      @cancel="cancelDelete"
    />
  </section>
</template>
