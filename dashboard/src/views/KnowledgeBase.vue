<script setup>
/**
 * Display four snapshot-backed operational references beside the separately
 * imported, checksum-verified canonical R5 review fixtures.
 */
import { computed, nextTick, onUnmounted, ref, watch } from "vue";
import DataTable from "../components/DataTable.vue";
import KeyValuePanel from "../components/KeyValuePanel.vue";
import {
  OUTCOME_LABELS,
  OUTCOME_SHARE_COLUMNS,
  OUTCOME_VALUE_COLUMNS,
  currencySymbol,
  distinct,
  pretty,
  shortTouchpoint,
} from "../lib/common.js";
import { useDashboard } from "../lib/useDashboard.js";
import { routeResources } from "../pages.js";
import { money } from "../theme.js";

import {
  DEFAULT_ONTOLOGY_REVIEW_SCENARIO,
  loadOntologyReviewFixtures,
} from "../lib/ontologyReviewFixtures.js";

const props = defineProps({ section: { type: String, default: "vocabulary" } });
const emit = defineEmits(["navigate"]);
const { data, ensureResources } = useDashboard();

const tabs = Object.freeze([
  { key: "vocabulary", label: "Touchpoint vocabulary" },
  { key: "rules", label: "Rules" },
  { key: "entities", label: "Entities" },
  { key: "sources", label: "Data sources" },
  { key: "ontology-review", label: "Ontology Review" },
]);

/**
 * What each segment of the touchpoint key means. The values are read from the
 * data; these are the definitions that give them meaning.
 */
const SEGMENT_NOTES = {
  ad_product: "Which Amazon ad product served the impression or click.",
  format: "The ad or inventory type. UNSPECIFIED when the product has none.",
  placement: "Where it appeared. UNSPECIFIED for products without placement.",
  creative: "The creative type. UNSPECIFIED when not reported.",
  interaction_type: "IMPRESSION or CLICK. Decides which cost type applies.",
};

const attribution = computed(() =>
  Array.isArray(data.value.attributionResults) ? data.value.attributionResults : [],
);

const segments = computed(() =>
  Object.entries(SEGMENT_NOTES).map(([segment, meaning]) => {
    const values = distinct(attribution.value, segment);
    return {
      segment: pretty(segment),
      meaning,
      distinct: values.length,
      values: values.join(", "),
    };
  }),
);

const segmentColumns = [
  { key: "segment", label: "Segment" },
  { key: "meaning", label: "Meaning", width: "34%" },
  { key: "distinct", label: "Values", format: "number" },
  { key: "values", label: "Observed", width: "34%" },
];

const touchpoints = computed(() =>
  distinct(attribution.value, "touchpoint").map((key) => ({
    touchpoint: key,
    reads_as: shortTouchpoint(key),
  })),
);

const touchpointColumns = [
  { key: "touchpoint", label: "Key", width: "56%" },
  { key: "reads_as", label: "Reads as" },
];

const outcomeRows = computed(() =>
  Object.entries(OUTCOME_LABELS).map(([key, label]) => ({
    outcome: label,
    key,
    share_column: OUTCOME_SHARE_COLUMNS[key],
    attributed_column: OUTCOME_VALUE_COLUMNS[key],
  })),
);

const outcomeColumns = [
  { key: "outcome", label: "Outcome" },
  { key: "key", label: "Key" },
  { key: "share_column", label: "Share column" },
  { key: "attributed_column", label: "Attributed column" },
];

const request = computed(() => data.value.strategyRequest ?? {});
const group = computed(() => request.value.campaign_group ?? {});
const pool = computed(() => data.value.candidatePool ?? {});

const capacityRules = computed(() => {
  const rules = request.value.capacity_rules ?? {};
  return Object.entries(rules).map(([adProduct, values]) => ({
    ad_product: adProduct,
    ...values,
  }));
});

const capacityColumns = computed(() => {
  const first = capacityRules.value[0];
  if (!first) return [];
  return Object.keys(first).map((key) => ({
    key,
    label: pretty(key),
    format: key === "ad_product" ? undefined : "number",
  }));
});

const groupRows = computed(() => {
  const totalDailyBudget = group.value.total_daily_budget;
  const hasTotalDailyBudget =
    totalDailyBudget !== null &&
    totalDailyBudget !== undefined &&
    totalDailyBudget !== "" &&
    Number.isFinite(Number(totalDailyBudget));
  return [
    { label: "Identifier", value: group.value.campaign_group_id || "--" },
    { label: "Name", value: group.value.group_name || "--" },
    { label: "Platform", value: group.value.platform || "--" },
    { label: "Marketplace", value: group.value.marketplace || "--" },
    { label: "Advertiser", value: group.value.advertiser_id || "--" },
    {
      label: "Total daily budget",
      value: hasTotalDailyBudget
        ? money(totalDailyBudget, currencySymbol(group.value.currency ?? "USD"))
        : "--",
    },
  ];
});

const campaignColumns = [
  { key: "campaign_id", label: "Campaign" },
  { key: "campaign_name", label: "Name", width: "30%" },
  { key: "ad_product", label: "Ad product" },
  { key: "status", label: "Status" },
];

const candidateCounts = computed(() => pool.value.campaign_candidate_counts ?? []);

const candidateColumns = computed(() => {
  const first = candidateCounts.value[0];
  if (!first) return [];
  return Object.keys(first).map((key) => ({
    key,
    label: pretty(key),
    format: key === "campaign_id" ? undefined : "number",
  }));
});

const sourceRows = computed(() => {
  const mode = data.value.mode;
  return [
    {
      label: "DATABASE",
      value: mode === "database" ? "true" : mode ? "false" : "--",
    },
    { label: "Reading from", value: data.value.source || "--" },
  ];
});

const capacityRulesEmpty = computed(() => {
  if (data.value.mode === "database") {
    return "Capacity rules are pipeline configuration and are not stored in database mode.";
  }
  if (data.value.mode === "local files") {
    return "No capacity rules are present in the current strategy_request.json.";
  }
  return "Capacity rules are unavailable because the Dashboard source has not been identified.";
});

const ARTIFACTS = [
  {
    artifact: "amazon_ads_report_sample.csv",
    layer: "History",
    provides: "Daily spend, impressions, clicks, and reported sales",
  },
  {
    artifact: "amc_mta_path_report_raw_sample.csv",
    layer: "History",
    provides: "Aggregated conversion paths",
  },
  {
    artifact: "amc_touchpoint_entity_aggregate_sample.csv",
    layer: "History",
    provides: "Touchpoint to Campaign and Ad Group bridge",
  },
  {
    artifact: "amc_markov_attribution_results.csv",
    layer: "Model output",
    provides: "Markov shares, attributed totals, efficiency",
  },
  {
    artifact: "amc_shapley_attribution_results.csv",
    layer: "Model output",
    provides: "Shapley shares, attributed totals, efficiency",
  },
  {
    artifact: "amc_mta_model_comparison_touchpoints.csv",
    layer: "Model output",
    provides: "Per-touchpoint gaps and reliability flags",
  },
  {
    artifact: "amc_mta_model_comparison_summary.csv",
    layer: "Model output",
    provides: "Per-outcome diagnostics and verdict",
  },
  {
    artifact: "amc_mta_recommended_attribution.csv",
    layer: "Model output",
    provides: "The governed value per touchpoint",
  },
  {
    artifact: "strategy_request.json",
    layer: "Entity",
    provides: "Campaign Group, Campaigns, weights, capacity rules",
  },
  {
    artifact: "candidate_pool.json",
    layer: "Entity",
    provides: "Eligible targeting object counts",
  },
  {
    artifact: "initial_budget_recommendation.json",
    layer: "Strategy",
    provides: "Campaign budgets and Ad Group slots",
  },
];

const artifactColumns = [
  { key: "artifact", label: "Artifact", width: "30%" },
  { key: "layer", label: "Layer" },
  { key: "provides", label: "Provides", width: "44%" },
];

const ontologyScenarioKey = ref(DEFAULT_ONTOLOGY_REVIEW_SCENARIO);
const ontologyReviewState = ref("idle");
const ontologyReviewError = ref("");
const ontologyScenarios = ref([]);
let ontologyReviewAbortController = null;
let ontologyReviewRequest = 0;
let disposed = false;

const ontologyScenario = computed(() =>
  ontologyScenarios.value.find(({ key }) => key === ontologyScenarioKey.value),
);
const ontologyScenarioOptions = computed(() =>
  ontologyScenarios.value.map(({ key, label }) => ({ key, label })),
);
const ontologyVerdictTone = computed(() => {
  if (ontologyScenario.value?.review.verdict === "CONFLICT") return "status-bad";
  if (ontologyScenario.value?.review.verdict === "INSUFFICIENT_EVIDENCE") {
    return "status-warning";
  }
  return "status-neutral";
});

async function loadCanonicalReview() {
  const request = ++ontologyReviewRequest;
  ontologyReviewAbortController?.abort();
  const controller = new AbortController();
  ontologyReviewAbortController = controller;
  ontologyReviewState.value = "loading";
  ontologyReviewError.value = "";

  try {
    const scenarios = await loadOntologyReviewFixtures({ signal: controller.signal });
    if (disposed || request !== ontologyReviewRequest) return;
    ontologyScenarios.value = scenarios;
    ontologyReviewState.value = scenarios.length ? "ready" : "empty";
    if (!ontologyScenario.value && scenarios.length) ontologyScenarioKey.value = scenarios[0].key;
  } catch (error) {
    if (disposed || request !== ontologyReviewRequest) return;
    ontologyScenarios.value = [];
    ontologyReviewState.value = "error";
    ontologyReviewError.value = error instanceof Error ? error.message : String(error);
  }
}

watch(
  () => props.section,
  (section) => {
    if (
      section === "ontology-review" &&
      ["idle", "error"].includes(ontologyReviewState.value)
    ) {
      loadCanonicalReview();
    }
  },
  { immediate: true },
);

onUnmounted(() => {
  disposed = true;
  ontologyReviewRequest += 1;
  ontologyReviewAbortController?.abort();
});
async function moveTabFocus(event, index) {
  const moves = { ArrowRight: 1, ArrowLeft: -1, Home: -index, End: tabs.length - 1 - index };
  if (!Object.hasOwn(moves, event.key)) return;
  event.preventDefault();
  const nextIndex = (index + moves[event.key] + tabs.length) % tabs.length;
  const target = tabs[nextIndex];
  try {
    await ensureResources(routeResources("knowledge", target.key));
  } catch {
    // The store records the failure; navigation exposes the route-level error.
  }
  emit("navigate", target.key);
  await nextTick();
  document.getElementById(`knowledge-tab-${target.key}`)?.focus();
}
</script>

<template>
  <section class="page-grid">
    <p class="caption">
      The first four tabs are operational references derived from the current
      Dashboard snapshot, not a backend-owned ontology. Ontology Review uses a
      separate, checksum-verified canonical fixture source.
    </p>
    <div class="tabs knowledge-tabs" role="tablist" aria-label="Knowledge Base sections">
      <button
        v-for="(entry, index) in tabs"
        :id="`knowledge-tab-${entry.key}`"
        :key="entry.key"
        class="tab"
        role="tab"
        :aria-selected="props.section === entry.key"
        :aria-controls="`knowledge-panel-${entry.key}`"
        :tabindex="props.section === entry.key ? 0 : -1"
        :class="{ active: props.section === entry.key }"
        @click="emit('navigate', entry.key)"
        @keydown="moveTabFocus($event, index)"
      >
        {{ entry.label }}
      </button>
    </div>

    <!-- Touchpoint vocabulary -->
    <div
      v-show="props.section === 'vocabulary'"
      id="knowledge-panel-vocabulary"
      class="knowledge-tab-panel"
      role="tabpanel"
      aria-labelledby="knowledge-tab-vocabulary"
    >
      <article class="card">
        <div class="card-head"><h2>The five-segment touchpoint key</h2></div>
        <div class="card-body">
          <div class="panel">
            <code class="key-formula">
              AD_PRODUCT : FORMAT : PLACEMENT : CREATIVE : INTERACTION_TYPE
            </code>
            <p class="caption">
              One key identifies one kind of interaction. Every attributed value,
              every spend row, and every path step is expressed in these keys, so
              attribution and spend can be compared without a join key of their
              own.
            </p>
          </div>
          <DataTable :columns="segmentColumns" :rows="segments" />
        </div>
      </article>

      <article class="card">
        <div class="card-head">
          <h2>Touchpoints in the current window</h2>
          <span class="sub">{{ touchpoints.length }} distinct keys</span>
        </div>
        <div class="card-body">
          <DataTable :columns="touchpointColumns" :rows="touchpoints" />
        </div>
      </article>
    </div>

    <!-- Rules -->
    <div
      v-show="props.section === 'rules'"
      id="knowledge-panel-rules"
      class="knowledge-tab-panel"
      role="tabpanel"
      aria-labelledby="knowledge-tab-rules"
    >
      <article class="card">
        <div class="card-head"><h2>Reliability contract</h2></div>
        <div class="card-body">
          <div class="panel">
            <div class="kv">
              <span>calculation_valid</span>
              <span>The arithmetic held: shares are finite and sum to one.</span>
            </div>
            <div class="kv">
              <span>data_support_sufficient</span>
              <span>Enough observed journeys to support the estimate.</span>
            </div>
            <div class="kv">
              <span>models_consistent</span>
              <span>Markov and Shapley agree within tolerance.</span>
            </div>
            <div class="kv">
              <span>Verdict</span>
              <span><b>AND of all three.</b> One false flag means UNRELIABLE.</span>
            </div>
          </div>
          <p class="caption">
            Diagnostics — total variation distance, Spearman correlation, Top-K
            overlap — inform the reader but never change the verdict. An
            UNRELIABLE row carries an interval instead of a point value and
            grants no budgeting authority.
          </p>
        </div>
      </article>

      <article class="card">
        <div class="card-head"><h2>Outcomes</h2></div>
        <div class="card-body">
          <DataTable :columns="outcomeColumns" :rows="outcomeRows" />
          <p class="caption">
            Every outcome is attributed independently. A touchpoint can lead on
            revenue and trail on converted users; neither is derived from the
            other.
          </p>
        </div>
      </article>

      <article class="card">
        <div class="card-head"><h2>Capacity rules</h2></div>
        <div class="card-body">
          <DataTable
            v-if="capacityRules.length"
            :columns="capacityColumns"
            :rows="capacityRules"
          />
          <div v-else class="notice">{{ capacityRulesEmpty }}</div>
          <p v-if="capacityRules.length" class="caption">
            These caps decide how many Ad Groups a Campaign can support, which in
            turn sets its minimum required daily budget.
          </p>
        </div>
      </article>
    </div>

    <!-- Entities -->
    <div
      v-show="props.section === 'entities'"
      id="knowledge-panel-entities"
      class="knowledge-tab-panel"
      role="tabpanel"
      aria-labelledby="knowledge-tab-entities"
    >
      <article class="card">
        <div class="card-head"><h2>Advertising hierarchy</h2></div>
        <div class="card-body">
          <KeyValuePanel title="Campaign Group" :rows="groupRows" />
          <DataTable
            :columns="campaignColumns"
            :rows="request.campaigns ?? []"
            empty="No Campaigns in the strategy request."
          />
          <p class="caption">
            A Campaign carries exactly one ad product, which is why the ad
            product is the level at which attribution evidence is bridged into
            budget shares.
          </p>
        </div>
      </article>

      <article class="card">
        <div class="card-head"><h2>Eligible targeting candidates</h2></div>
        <div class="card-body">
          <DataTable
            :columns="candidateColumns"
            :rows="candidateCounts"
            empty="No candidate counts available."
          />
          <p v-if="candidateCounts.length" class="caption">
            Usage policy: <b>{{ pool.candidate_usage_policy || "--" }}</b>. These
            counts drive the capacity calculation that decides how many new Ad
            Groups each Campaign can support.
          </p>
        </div>
      </article>
    </div>

    <!-- Data sources -->
    <div
      v-show="props.section === 'sources'"
      id="knowledge-panel-sources"
      class="knowledge-tab-panel"
      role="tabpanel"
      aria-labelledby="knowledge-tab-sources"
    >
      <article class="card">
        <div class="card-head"><h2>Active source</h2></div>
        <div class="card-body">
          <KeyValuePanel title="Mode" :rows="sourceRows" />
        </div>
      </article>

      <article class="card">
        <div class="card-head"><h2>File-mode artifact contract</h2></div>
        <div class="card-body">
          <DataTable :columns="artifactColumns" :rows="ARTIFACTS" />
          <p class="caption">
            These filenames describe the committed file-mode contract. Database
            mode reports current data through backend resources; this list is not
            provenance for the active database.
          </p>
        </div>
      </article>
    </div>

    <article
      v-show="props.section === 'ontology-review'"
      id="knowledge-panel-ontology-review"
      class="card ontology-review knowledge-tab-panel"
      role="tabpanel"
      aria-labelledby="knowledge-tab-ontology-review"
    >
      <div class="card-head ontology-review-head">
        <div><span class="eyebrow">CANONICAL RELEASE</span><h2>Ontology Review</h2></div>
        <div class="ontology-source-badges" aria-label="Review data source">
          <span class="badge warn">Synthetic fixtures</span>
          <span class="badge">No Review API connected</span>
        </div>
      </div>
      <div class="card-body ontology-review-body">
        <div class="ontology-review-toolbar">
          <label for="ontology-review-scenario">Canonical scenario</label>
          <select
            id="ontology-review-scenario"
            v-model="ontologyScenarioKey"
            :disabled="ontologyReviewState !== 'ready'"
          >
            <option v-for="option in ontologyScenarioOptions" :key="option.key" :value="option.key">
              {{ option.label }}
            </option>
          </select>
          <p>Verified release data for display only. No request is sent and no verdict is calculated here.</p>
        </div>

        <div v-if="ontologyReviewState === 'loading'" class="ontology-empty ontology-loading" role="status">
          <div class="empty-icon" aria-hidden="true">…</div>
          <h3>Loading canonical review fixtures</h3>
          <p>No review verdict is shown until every fixture passes validation.</p>
        </div>
        <div v-else-if="ontologyReviewState === 'error'" class="ontology-empty ontology-error" role="alert">
          <div class="empty-icon" aria-hidden="true">!</div>
          <h3>Canonical review data is unavailable</h3>
          <p>{{ ontologyReviewError }}</p>
          <strong>No review result can be displayed. Re-import the canonical fixture release.</strong>
          <button class="btn" type="button" @click="loadCanonicalReview">Try again</button>
        </div>
        <div v-else-if="ontologyReviewState === 'empty' || !ontologyScenario" class="ontology-empty" role="status">
          <div class="empty-icon" aria-hidden="true">∅</div>
          <h3>No canonical review fixtures</h3>
          <p>The verified fixture set contains no displayable review result.</p>
        </div>

        <template v-else>
          <div class="ontology-identity-grid">
            <section class="ontology-section" aria-labelledby="plan-identity-heading">
              <h3 id="plan-identity-heading">Plan identity</h3>
              <dl class="ontology-fields">
                <div><dt>Client ID</dt><dd>{{ ontologyScenario.clientId }}</dd></div>
                <div><dt>Plan ID</dt><dd>{{ ontologyScenario.plan.id }}</dd></div>
                <div><dt>Plan item</dt><dd>{{ ontologyScenario.plan.itemId }}</dd></div>
                <div><dt>Campaign</dt><dd>{{ ontologyScenario.plan.campaign }}</dd></div>
                <div><dt>Source</dt><dd>{{ ontologyScenario.plan.source }} · {{ ontologyScenario.plan.sourceVersion }}</dd></div>
              </dl>
            </section>
            <section class="ontology-section" aria-labelledby="release-identity-heading">
              <h3 id="release-identity-heading">Release identity</h3>
              <dl class="ontology-fields">
                <div><dt>Suite</dt><dd>{{ ontologyScenario.suiteId }}</dd></div>
                <div><dt>Ontology</dt><dd>{{ ontologyScenario.release.ontology_version }}</dd></div>
                <div><dt>Engine</dt><dd>{{ ontologyScenario.release.engine_version }}</dd></div>
                <div><dt>Source commit</dt><dd class="mono wrap-anywhere">{{ ontologyScenario.release.source_commit }}</dd></div>
                <div><dt>Release commit</dt><dd class="mono wrap-anywhere">{{ ontologyScenario.release.release_commit }}</dd></div>
                <div><dt>Package checksum</dt><dd class="mono wrap-anywhere">{{ ontologyScenario.release.package_checksum }}</dd></div>
              </dl>
            </section>
            <section class="ontology-section" aria-labelledby="rule-identity-heading">
              <h3 id="rule-identity-heading">Review and rule</h3>
              <dl class="ontology-fields">
                <div><dt>Review ID</dt><dd class="mono wrap-anywhere">{{ ontologyScenario.review.id }}</dd></div>
                <div><dt>Review source</dt><dd>{{ ontologyScenario.review.source }}</dd></div>
                <div><dt>Rule</dt><dd>{{ ontologyScenario.rule.id }}</dd></div>
                <div><dt>Version</dt><dd>{{ ontologyScenario.rule.version }}</dd></div>
                <div><dt>Outcome</dt><dd>{{ ontologyScenario.rule.outcome }}</dd></div>
                <div><dt>Triggered</dt><dd>{{ ontologyScenario.rule.triggered ?? "Undefined" }}</dd></div>
              </dl>
            </section>
          </div>

          <section class="ontology-verdict" aria-labelledby="ontology-verdict-heading">
            <div>
              <span class="eyebrow">Canonical review verdict</span>
              <h3 id="ontology-verdict-heading"><span class="status-label" :class="ontologyVerdictTone">{{ ontologyScenario.review.verdict }}</span></h3>
              <small class="ontology-review-id">Item verdict: {{ ontologyScenario.review.itemVerdict }}</small>
            </div>
            <p>{{ ontologyScenario.explanation }}</p>
            <dl class="ontology-policy-fields">
              <div><dt>Current budget</dt><dd>{{ ontologyScenario.policy.currentBudget ?? "Unavailable" }} {{ ontologyScenario.policy.currency ?? "" }}</dd></div>
              <div><dt>Recommended budget</dt><dd>{{ ontologyScenario.policy.recommendedBudget ?? "Unavailable" }} {{ ontologyScenario.policy.currency ?? "" }}</dd></div>
              <div><dt>Absolute change ratio</dt><dd>{{ ontologyScenario.policy.absoluteChangeRatio ?? "Undefined" }}</dd></div>
              <div><dt>Authorization limit</dt><dd>{{ ontologyScenario.policy.authorizationLimit ?? "Unavailable" }}</dd></div>
              <div><dt>Policy source</dt><dd>{{ ontologyScenario.policy.source ?? "Unavailable" }}</dd></div>
            </dl>
          </section>

          <div class="ontology-result-grid">
            <section class="ontology-section" aria-labelledby="review-evidence-heading">
              <h3 id="review-evidence-heading">Evidence</h3>
              <ol class="ontology-list">
                <li v-for="item in ontologyScenario.evidence" :key="item.id">
                  <strong>{{ item.name }}</strong><span>{{ item.value }} {{ item.unit }}</span><small>{{ item.source }} · {{ item.scope }}</small>
                </li>
              </ol>
            </section>
            <section class="ontology-section" aria-labelledby="review-limitations-heading">
              <h3 id="review-limitations-heading">Limitations</h3>
              <ul class="ontology-list"><li v-for="item in ontologyScenario.limitations" :key="item">{{ item }}</li></ul>
            </section>
            <section class="ontology-section ontology-risk-section" aria-labelledby="review-availability-heading">
              <h3 id="review-availability-heading">Risks and availability</h3>
              <ul class="ontology-list">
                <li v-for="item in ontologyScenario.availability" :key="item">{{ item }}</li>
                <li v-if="ontologyScenario.policy.insufficiencyReason">Insufficiency reason: {{ ontologyScenario.policy.insufficiencyReason }}</li>
              </ul>
            </section>
          </div>
          <div class="ontology-next-step"><span>NEXT STEP</span><strong>{{ ontologyScenario.nextStep }}</strong></div>
        </template>
      </div>
    </article>
  </section>
</template>
