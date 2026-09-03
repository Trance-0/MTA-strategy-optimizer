<script setup>
/**
 * Preserve the backend-owned Knowledge Base boundary and display separately
 * imported, checksum-verified canonical R5 review fixtures.
 */
import { computed, nextTick, onUnmounted, ref, watch } from "vue";

import {
  DEFAULT_ONTOLOGY_REVIEW_SCENARIO,
  loadOntologyReviewFixtures,
} from "../lib/ontologyReviewFixtures.js";

const props = defineProps({ section: { type: String, default: "notice" } });
const emit = defineEmits(["navigate"]);
const tabs = Object.freeze([
  { key: "notice", label: "Knowledge status" },
  { key: "ontology-review", label: "Ontology Review" },
]);

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
  emit("navigate", tabs[nextIndex].key);
  await nextTick();
  document.getElementById(`knowledge-tab-${tabs[nextIndex].key}`)?.focus();
}
</script>

<template>
  <section class="page-grid">
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

    <article
      v-show="props.section === 'notice'"
      id="knowledge-panel-notice"
      class="card empty-card knowledge-tab-panel"
      role="tabpanel"
      aria-labelledby="knowledge-tab-notice"
    >
      <h2>Knowledge Base is not connected</h2>
      <p>
        The previous browser-derived vocabulary has been removed. This area remains
        unavailable until a backend knowledge contract is specified and implemented.
      </p>
      <p>The Ontology Review tab is a separate, display-only canonical fixture release.</p>
    </article>

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
