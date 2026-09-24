<script setup>
/**
 * Ontology Review Pipeline — integrated from BrandLens.
 * Five sub-tabs: Plan Data → Review → Explain → Feedback → History
 */
import { computed, onMounted, reactive, ref } from "vue";

const plan = ref(null);
const review = ref(null);
const ruleCards = ref([]);
const explanation = ref(null);
const explanationLoading = ref(true);
const convo = ref(null);

// ── Session (localStorage) ──
const FB_KEY = "brandlens.feedback.v1";
const DEC_KEY = "brandlens.decision.v1";
const loadArr = (k) => { try { return JSON.parse(localStorage.getItem(k) || "[]"); } catch { return []; } };
const loadOne = (k) => { try { return JSON.parse(localStorage.getItem(k) || "null"); } catch { return null; } };

const session = reactive({ feedback: loadArr(FB_KEY), decision: loadOne(DEC_KEY) });

function recordDecision(d) {
  session.decision = { decision: d, plan_id: review.value?.plan_id || "unknown", review_id: review.value?.review_id || "unknown", created_at: new Date().toISOString() };
  localStorage.setItem(DEC_KEY, JSON.stringify(session.decision));
}
function addFeedback(entry) {
  const r = { feedback_id: `fb_${Date.now()}`, created_at: new Date().toISOString(), ...entry };
  session.feedback.unshift(r);
  localStorage.setItem(FB_KEY, JSON.stringify(session.feedback));
}

// ── Sub-tabs ──
const subTab = ref("plan");
const subTabs = Object.freeze([
  { key: "plan", label: "Plan Data" },
  { key: "review", label: "Review" },
  { key: "explain", label: "Explain" },
  { key: "feedback", label: "Feedback" },
  { key: "history", label: "History" },
]);

// ── Labels ──
const ACTION_L = { increase_budget: "Increase", decrease_budget: "Decrease", maintain_budget: "Maintain" };
const PERIOD_L = { next_14_days: "Next 14 days", current_snapshot: "Current snapshot" };
const SOURCE_L = { demo_mta_output: "MTA Attribution", demo_mta_comparison: "MTA Comparison", demo_platform_output: "Platform Spend", demo_prediction_output: "Optimizer Prediction" };
const CLAIM_L = { PLAN_FIELD: "Plan field", REVIEW_FIELD: "Review field", FACT_VALUE: "Fact value", RULE_FIELD: "Rule field", PLAN_PERIOD_FIELD: "Plan period" };
const VERDICT_L = { SUPPORT: "Support", CONFLICT: "Conflict", NOT_APPLICABLE: "N/A", INSUFFICIENT_EVIDENCE: "Insufficient evidence", UNVERIFIED: "Unverified" };
const RATING_T = { good: "Good", normal: "Average", bad: "Poor" };
const ASPECTS = ["Accurate numbers", "Easy to understand", "Limitations disclosed"];

function fmtVal(f) { return f.unit === "ratio" ? `${(f.value * 100).toFixed(0)}%` : String(f.value); }
function fmtTime(iso) { return new Date(iso).toLocaleString("en-US", { hour12: false }); }
function vTone(v) { return v === "SUPPORT" ? "verdict-support" : v === "CONFLICT" ? "verdict-conflict" : v === "INSUFFICIENT_EVIDENCE" ? "verdict-warning" : "verdict-neutral"; }

// ── Feedback form ──
const fbForm = reactive({ rating: null, aspects: [], comment: "" });
const fbError = ref("");
const fbOk = ref(false);
function onSubmitFb() {
  fbError.value = "";
  if (fbForm.rating === null) { fbError.value = "Please select a rating."; return; }
  addFeedback({ rating: fbForm.rating, aspects: [...fbForm.aspects], comment: fbForm.comment });
  Object.assign(fbForm, { rating: null, aspects: [], comment: "" });
  fbOk.value = true;
  setTimeout(() => (fbOk.value = false), 2500);
}

// ── API Base ──
const API_BASE = ""; // Vite proxy handles /api → backend

// ── API Calls ──
async function fetchWithFallback(url, mockPath) {
  try {
    const res = await fetch(url);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (err) {
    console.warn(`API call failed: ${url}, using mock data`, err);
    const mod = await import(`../mock/brandlens/${mockPath}`);
    return mod.default;
  }
}

// ── Load data ──
onMounted(async () => {
  const [planData, reviewData, rulesData, explainData, reqData] = await Promise.all([
    fetchWithFallback("/api/plan", "final_plan.demo.json"),
    fetchWithFallback("/api/review", "ontology_review.demo.json"),
    fetchWithFallback("/api/rules", "llm_context.demo.json"),
    fetchWithFallback("/api/explain", "llm_workflow_output.demo.json"),
    fetchWithFallback("/api/llm_request", "llm_request.demo.json"),
  ]);

  plan.value = planData;
  review.value = reviewData;

  // Transform rules to expected format
  if (Array.isArray(rulesData)) {
    ruleCards.value = rulesData.map(r => ({
      rule_id: r.rule_id,
      name: r.name,
      rule_version: r.version_history?.[r.version_history.length - 1]?.version || r.rule_version || "unknown",
      status: r.status,
      definition: r.diagnosis || r.definition,
      review_policy: r.review_policy,
      limitations: r.known_limitations || r.limitations || [],
    }));
  } else if (rulesData.public_rule_context) {
    ruleCards.value = rulesData.public_rule_context.map(r => ({
      rule_id: r.rule_id,
      name: r.name,
      rule_version: r.rule_version,
      status: r.status,
      definition: r.definition,
      review_policy: r.review_policy,
      limitations: r.limitations || [],
    }));
  }

  explanation.value = {
    answer: explainData.answer,
    status: explainData.status,
    intent: explainData.intent,
    model: explainData.model || "qwen3.7-max",
    prompt_version: explainData.prompt_version,
    workflow_version: explainData.workflow_version,
    fallback_used: explainData.fallback_used,
    claims: explainData.claims || [],
    facts_used: explainData.facts_used || [],
  };
  explanationLoading.value = false;
  convo.value = { request: reqData, output: explainData };
});
</script>

<template>
  <div class="blp">
    <div class="blp-tabs" role="tablist">
      <button v-for="t in subTabs" :key="t.key" class="blp-tab" :class="{ active: subTab === t.key }" role="tab" :aria-selected="subTab === t.key" @click="subTab = t.key">{{ t.label }}</button>
    </div>
    <!-- Plan Data -->
    <div v-show="subTab === 'plan'" class="blp-panel">
      <div v-if="!plan" class="blp-loading">Loading plan data…</div>
      <template v-else>
        <div class="blp-card">
          <h3>Optimizer Final Plan</h3>
          <p class="blp-sub">plan_id: {{ plan.plan_id }} · Source: {{ plan.source }} · Ontology reviews only</p>
          <div class="blp-kv"><dt>Period</dt><dd>{{ PERIOD_L[plan.period.type] || plan.period.type }} ({{ plan.period.start_date }} to {{ plan.period.end_date }})</dd></div>
          <table class="blp-table" style="margin-top:12px">
            <thead><tr><th>Channel</th><th>Action</th><th>Delta</th><th>Current</th><th>Recommended</th><th>Currency</th></tr></thead>
            <tbody><tr v-for="item in plan.items" :key="item.plan_item_id"><td>{{ item.entity_id }}</td><td>{{ ACTION_L[item.action] || item.action }}</td><td>{{ item.delta_pct > 0 ? "+" : "" }}{{ item.delta_pct }}%</td><td>{{ item.current_budget }}</td><td>{{ item.recommended_budget }}</td><td>{{ item.currency }}</td></tr></tbody>
          </table>
        </div>
        <div class="blp-card">
          <h3>Decision Evidence</h3>
          <p class="blp-sub">Public facts the optimizer referenced</p>
          <table class="blp-table">
            <thead><tr><th>Metric</th><th>Value</th><th>Period</th><th>Source</th></tr></thead>
            <tbody><tr v-for="f in plan.decision_evidence" :key="f.fact_id"><td>{{ f.name }}</td><td>{{ fmtVal(f) }}</td><td>{{ PERIOD_L[f.period] || f.period }}</td><td>{{ SOURCE_L[f.source] || f.source }}</td></tr></tbody>
          </table>
        </div>
        <div class="blp-card">
          <h3>Review Evidence</h3>
          <p class="blp-sub">Input facts for ontology review</p>
          <table class="blp-table">
            <thead><tr><th>Metric</th><th>Value</th><th>Period</th><th>Source</th><th>fact_id</th></tr></thead>
            <tbody><tr v-for="f in plan.review_evidence" :key="f.fact_id"><td>{{ f.name }}</td><td>{{ fmtVal(f) }}</td><td>{{ PERIOD_L[f.period] || f.period }}</td><td>{{ SOURCE_L[f.source] || f.source }}</td><td class="blp-muted">{{ f.fact_id }}</td></tr></tbody>
          </table>
        </div>
      </template>
    </div>

    <!-- Review -->
    <div v-show="subTab === 'review'" class="blp-panel">
      <div v-if="!review" class="blp-loading">Loading review…</div>
      <template v-else>
        <div class="blp-banner">
          <span class="blp-banner-label">Overall Verdict</span>
          <span class="blp-verdict" :class="vTone(review.overall_verdict)">{{ review.overall_verdict }} · {{ VERDICT_L[review.overall_verdict] }}</span>
          <span class="blp-banner-meta">{{ review.review_id }} · v{{ review.ontology_version }}</span>
        </div>
        <div v-for="rule in ruleCards" :key="rule.rule_id" class="blp-card">
          <h3>Rule {{ rule.rule_id }}: {{ rule.name }}</h3>
          <p class="blp-sub">v{{ rule.rule_version }} · {{ rule.status }}</p>
          <p>{{ rule.definition }}</p>
          <div class="blp-kv">
            <dt>Mode</dt><dd>{{ rule.review_policy.mode }}</dd>
            <dt>Supported</dt><dd>{{ rule.review_policy.supported_plan_actions.join(", ") }}</dd>
            <dt>Conflicting</dt><dd>{{ rule.review_policy.conflicting_plan_actions.join(", ") }}</dd>
            <dt>Otherwise</dt><dd>{{ rule.review_policy.otherwise }}</dd>
          </div>
          <p class="blp-muted" style="margin-top:10px">Limitations:</p>
          <ul class="blp-muted" style="margin:4px 0 0;padding-left:20px"><li v-for="(l, i) in rule.limitations" :key="i">{{ l }}</li></ul>
        </div>
        <div class="blp-card">
          <h3>Item-level Results</h3>
          <p class="blp-sub">{{ review.items.length }} item(s)</p>
          <div v-for="item in review.items" :key="item.review_item_id" class="blp-review-item">
            <p style="margin:0"><span class="blp-verdict" :class="vTone(item.verdict)">{{ item.verdict }} · {{ VERDICT_L[item.verdict] }}</span> <span style="margin-left:10px">Rule {{ item.rule_id }} ({{ item.rule_version }}) · Base {{ item.base_confidence }} · Runtime {{ item.runtime_confidence }}</span></p>
            <p class="blp-muted" style="margin:6px 0 0">Matched: <span v-for="fid in item.matched_fact_ids" :key="fid" class="blp-tag">{{ fid }}</span></p>
            <ul v-if="item.limitations?.length" class="blp-muted" style="margin:6px 0 0;padding-left:20px"><li v-for="(l, i) in item.limitations" :key="i">{{ l }}</li></ul>
          </div>
        </div>
        <div class="blp-card">
          <h3>Plan Decision (Human)</h3>
          <p class="blp-sub">Ontology only reviews; accept/reject recorded locally.</p>
          <div style="display:flex;align-items:center;gap:10px;margin-top:8px">
            <button class="blp-btn" :disabled="session.decision?.decision === 'ACCEPT'" @click="recordDecision('ACCEPT')">Accept</button>
            <button class="blp-btn blp-btn-ghost" :disabled="session.decision?.decision === 'REJECT'" @click="recordDecision('REJECT')">Reject</button>
            <span v-if="session.decision" class="blp-muted">{{ session.decision.decision === "ACCEPT" ? "Accepted" : "Rejected" }} ({{ fmtTime(session.decision.created_at) }})</span>
          </div>
        </div>
      </template>
    </div>

    <!-- Explain -->
    <div v-show="subTab === 'explain'" class="blp-panel">
      <div v-if="explanationLoading" class="blp-loading">Generating LLM explanation…</div>
      <template v-else-if="explanation">
        <div class="blp-card">
          <h3>LLM Explanation</h3>
          <p class="blp-sub">Judgments from ontology review; LLM only translates</p>
          <p v-for="(para, i) in explanation.answer.split('\n')" :key="i" style="margin:8px 0;line-height:1.7">{{ para }}</p>
          <div class="blp-kv" style="margin-top:14px;border-top:1px dashed var(--line);padding-top:12px">
            <dt>Model</dt><dd>{{ explanation.model }} ({{ explanation.fallback_used ? "fallback" : "normal" }})</dd>
            <dt>Status / Intent</dt><dd>{{ explanation.status }} / {{ explanation.intent }}</dd>
            <dt>Prompt</dt><dd>{{ explanation.prompt_version }} (workflow {{ explanation.workflow_version }})</dd>
          </div>
        </div>
        <div class="blp-card">
          <h3>Traceable Claims</h3>
          <p class="blp-sub">{{ explanation.claims.length }} claim(s)</p>
          <table class="blp-table">
            <thead><tr><th>Type</th><th>Source</th><th>Field</th><th>Value</th></tr></thead>
            <tbody><tr v-for="c in explanation.claims" :key="c.claim_id"><td>{{ CLAIM_L[c.claim_type] || c.claim_type }}</td><td class="blp-muted">{{ c.source_id }}</td><td>{{ c.field }}</td><td>{{ c.value }}</td></tr></tbody>
          </table>
        </div>
      </template>
    </div>

    <!-- Feedback -->
    <div v-show="subTab === 'feedback'" class="blp-panel">
      <div class="blp-card">
        <h3>Feedback on This Explanation</h3>
        <p class="blp-sub">Stored locally</p>
        <p style="margin:6px 0">How was this explanation?</p>
        <label class="blp-choice"><input v-model="fbForm.rating" type="radio" name="blp-rating" value="good" /> Good</label>
        <label class="blp-choice"><input v-model="fbForm.rating" type="radio" name="blp-rating" value="normal" /> Average</label>
        <label class="blp-choice"><input v-model="fbForm.rating" type="radio" name="blp-rating" value="bad" /> Poor</label>
        <p style="margin:12px 0 4px">What was done well?</p>
        <label v-for="a in ASPECTS" :key="a" class="blp-choice"><input v-model="fbForm.aspects" type="checkbox" :value="a" /> {{ a }}</label>
        <p style="margin:12px 0 4px">Comments (optional)</p>
        <textarea v-model="fbForm.comment" rows="3" placeholder="e.g. which number was unclear…"></textarea>
        <p v-if="fbError" style="color:#dc2626;margin:8px 0 0">{{ fbError }}</p>
        <p v-if="fbOk" style="color:#16a34a;margin:8px 0 0">Submitted, thanks!</p>
        <p style="margin:12px 0 0"><button class="blp-btn" @click="onSubmitFb">Submit</button></p>
      </div>
      <div class="blp-card">
        <h3>Submitted Feedback</h3>
        <p class="blp-sub">{{ session.feedback.length }} entry/entries</p>
        <p v-if="!session.feedback.length" class="blp-muted">No feedback yet.</p>
        <div v-for="fb in session.feedback" :key="fb.feedback_id" style="margin-bottom:12px">
          <p style="margin:0"><span class="blp-rating" :class="`blp-rating-${fb.rating}`">{{ RATING_T[fb.rating] || fb.rating }}</span> <span class="blp-muted" style="margin-left:8px">{{ fmtTime(fb.created_at) }}</span></p>
          <p v-if="fb.aspects?.length" style="margin:4px 0 0"><span v-for="a in fb.aspects" :key="a" class="blp-tag">{{ a }}</span></p>
          <p v-if="fb.comment" style="margin:4px 0 0">{{ fb.comment }}</p>
        </div>
      </div>
    </div>

    <!-- History -->
    <div v-show="subTab === 'history'" class="blp-panel">
      <div v-if="!convo" class="blp-loading">Loading…</div>
      <template v-else>
        <div class="blp-card">
          <h3>Conversation</h3>
          <p class="blp-sub">request_id: {{ convo.request.request_id }} · {{ convo.request.mode }} · intents: {{ convo.request.allowed_intents.join(", ") }}</p>
          <div class="blp-bubble blp-bubble-user"><div class="blp-bubble-role">User</div>{{ convo.request.question }}</div>
          <div class="blp-bubble blp-bubble-assistant"><div class="blp-bubble-role">Review Assistant ({{ convo.output.intent }})</div>{{ convo.output.answer }}</div>
          <p class="blp-muted" style="margin-top:10px;font-size:12px">Workflow {{ convo.output.workflow_version }} · Prompt {{ convo.output.prompt_version }} · Fallback: {{ convo.output.fallback_used ? "Yes" : "No" }}</p>
        </div>
        <div class="blp-card">
          <h3>Session Feedback</h3>
          <p v-if="session.decision" style="margin:0 0 10px">
            <span class="blp-verdict" :class="session.decision.decision === 'ACCEPT' ? 'verdict-support' : 'verdict-conflict'">{{ session.decision.decision === "ACCEPT" ? "Plan Accepted" : "Plan Rejected" }}</span>
            <span class="blp-muted" style="margin-left:8px">{{ fmtTime(session.decision.created_at) }}</span>
          </p>
          <p v-if="!session.feedback.length" class="blp-muted">No feedback yet.</p>
          <div v-for="fb in session.feedback" :key="fb.feedback_id" style="margin-bottom:10px">
            <span class="blp-rating" :class="`blp-rating-${fb.rating}`">{{ RATING_T[fb.rating] || fb.rating }}</span>
            <span class="blp-muted" style="margin-left:8px">{{ fmtTime(fb.created_at) }}</span>
            <p v-if="fb.comment" style="margin:4px 0 0">{{ fb.comment }}</p>
          </div>
        </div>
      </template>
    </div>
  </div>
</template>


<style scoped>
.blp-tabs { display: flex; gap: 2px; border-bottom: 1px solid var(--line); margin-bottom: 16px; }
.blp-tab { padding: 8px 16px; background: none; border: none; border-bottom: 2px solid transparent; color: var(--muted); font: inherit; font-size: 13px; font-weight: 500; cursor: pointer; transition: color 0.15s, border-color 0.15s; }
.blp-tab:hover { color: var(--text); }
.blp-tab.active { color: var(--blue); border-bottom-color: var(--blue); }
.blp-card { background: var(--card-bg, #fff); border: 1px solid var(--line); border-radius: 10px; padding: 16px 20px; margin-bottom: 14px; }
.blp-card h3 { margin: 0 0 4px; font-size: 14px; font-weight: 600; }
.blp-sub { color: var(--muted); font-size: 12px; margin: 0 0 12px; }
.blp-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.blp-table th, .blp-table td { text-align: left; padding: 8px 10px; border-bottom: 1px solid var(--line); vertical-align: top; }
.blp-table th { color: var(--muted); font-weight: 500; white-space: nowrap; }
.blp-table tr:last-child td { border-bottom: none; }
.blp-table tbody tr:hover { background: var(--bg); }
.blp-kv { display: grid; grid-template-columns: 150px 1fr; gap: 4px 12px; font-size: 13px; }
.blp-kv dt { color: var(--muted); }
.blp-kv dd { margin: 0; }
.blp-verdict { display: inline-block; padding: 2px 10px; border-radius: 999px; font-size: 12px; font-weight: 600; white-space: nowrap; }
.verdict-support { background: #dcfce7; color: #16a34a; }
.verdict-conflict { background: #fee2e2; color: #dc2626; }
.verdict-warning { background: #fef3c7; color: #d97706; }
.verdict-neutral { background: #f1f5f9; color: #64748b; }
.blp-banner { display: flex; align-items: center; gap: 14px; border-radius: 10px; padding: 14px 20px; margin-bottom: 14px; border: 1px solid var(--line); background: var(--card-bg, #fff); }
.blp-banner-label { font-weight: 600; font-size: 13px; }
.blp-banner-meta { color: var(--muted); font-size: 12px; }
.blp-tag { display: inline-block; background: var(--blue2, #eaf1fb); color: var(--blue, #2456a6); border-radius: 6px; padding: 1px 8px; font-size: 12px; margin: 2px 4px 2px 0; }
.blp-btn { display: inline-block; border: 1px solid var(--blue); background: var(--blue); color: #fff; padding: 7px 16px; border-radius: 8px; font-size: 13px; cursor: pointer; transition: opacity 0.15s; }
.blp-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.blp-btn:hover:not(:disabled) { opacity: 0.9; }
.blp-btn-ghost { background: transparent; color: var(--blue); }
.blp-btn-ghost:hover:not(:disabled) { background: var(--blue2, #eaf1fb); }
.blp-choice { display: flex; align-items: center; gap: 6px; margin: 4px 0; cursor: pointer; font-size: 13px; }
textarea { width: 100%; border: 1px solid var(--line); border-radius: 8px; padding: 8px 10px; font: inherit; font-size: 13px; background: var(--card-bg, #fff); resize: vertical; }
.blp-rating { display: inline-block; padding: 2px 10px; border-radius: 999px; font-size: 12px; font-weight: 600; }
.blp-rating-good { background: #dcfce7; color: #16a34a; }
.blp-rating-normal { background: #fef3c7; color: #d97706; }
.blp-rating-bad { background: #fee2e2; color: #dc2626; }
.blp-bubble { border-radius: 10px; padding: 12px 14px; margin-top: 10px; font-size: 13px; line-height: 1.6; }
.blp-bubble-role { font-weight: 600; font-size: 12px; margin-bottom: 4px; color: var(--muted); }
.blp-bubble-user { background: var(--blue2, #eaf1fb); }
.blp-bubble-assistant { background: var(--bg); border: 1px solid var(--line); }
.blp-review-item { margin-bottom: 14px; padding-bottom: 14px; border-bottom: 1px solid var(--line); }
.blp-review-item:last-child { border-bottom: none; margin-bottom: 0; padding-bottom: 0; }
.blp-muted { color: var(--muted); font-size: 12px; }
.blp-loading { color: var(--muted); padding: 40px 0; text-align: center; font-size: 13px; }
</style>
