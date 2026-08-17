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
import { computed } from "vue";

import DataTable from "../components/DataTable.vue";
import KeyValuePanel from "../components/KeyValuePanel.vue";
import MetricRow from "../components/MetricRow.vue";
import PlotlyChart from "../components/PlotlyChart.vue";
import ReliabilityBanner from "../components/ReliabilityBanner.vue";
import { OUTCOME_LABELS, currencySymbol, sortBy } from "../lib/common.js";
import { useDashboard } from "../lib/useDashboard.js";
import * as theme from "../theme.js";

const { data } = useDashboard();

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
  </section>
</template>
