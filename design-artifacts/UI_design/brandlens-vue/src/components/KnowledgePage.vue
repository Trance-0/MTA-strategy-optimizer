<script setup>
import { computed, ref } from 'vue'
import { queryKnowledge } from '../api/client'

defineProps({
  knowledgeAssets: {
    type: Array,
    default: () => [],
  },
  knowledgeHealth: {
    type: Array,
    default: () => [],
  },
})

const promptTemplates = [
  'Why is DSP prospecting missing coverage?',
  'Which rule should I review next for budget risk?',
  'What evidence supports the recommended reallocation?',
  'Show me the highest-risk knowledge gap in this portfolio.',
]

const initialAssistantMessage = {
  role: 'assistant',
  title: 'Coverage gap for DSP Prospecting',
  status: 'Needs governance approval',
  severity: 'High Priority',
  category: 'Audience coverage',
  subject: 'DSP Prospecting — US',
  confidence: '89%',
  decision: {
    label: 'Conclusion',
    value: 'Stop expansion until the audience coverage rule is approved.',
  },
  risk: {
    label: 'Risk',
    value: 'Unapproved audience exposure creates policy and brand risk.',
  },
  action: {
    label: 'Action',
    value: 'Request a coverage rule or limit activation to verified segments.',
  },
  decisionState: 'Awaiting governance approval',
  fallback: 'Continue with approved audience classes only.',
  contextMemory: ['Previous: DSP coverage review', 'Follow-up: budget guardrail check', 'Current: approval workflow pending'],
  rule: {
    code: 'GOV-031',
    name: 'Audience coverage policy',
    scope: 'DSP prospecting',
  },
  summary:
    'There is no approved rule covering third-party prospecting audiences in the current knowledge layer. This is a governance issue rather than a media performance problem, and it should be resolved before expansion.',
  evidence: [
    { label: 'System state', value: 'NO_COVERAGE', source: 'Governance status', weight: 'High', confidence: '96%' },
    { label: 'Impact', value: 'Lookalike and lifestyle segments are outside the active approval scope', source: 'Audience taxonomy', weight: 'High', confidence: '91%' },
    { label: 'Risk', value: 'Expansion could proceed without policy validation', source: 'Decision guardrail', weight: 'Critical', confidence: '94%' },
  ],
  recommendation: {
    action: 'Request a coverage rule or restrict prospecting to approved audience classes before broader activation.',
    rationale: 'This closes the governance gap before further scaling.',
    impact: 'Prevents unapproved audience exposure while preserving campaign flexibility.',
  },
  relatedRules: ['DSP Prospecting coverage', 'Audience approval standard', 'Brand safety policy'],
}

const historyEntries = ref([
  {
    id: 'initial',
    question: 'Why is DSP prospecting missing coverage?',
    answer: initialAssistantMessage,
  },
])
const selectedHistoryId = ref('initial')
const draft = ref('')

const selectedEntry = computed(() => {
  return historyEntries.value.find((entry) => entry.id === selectedHistoryId.value) || historyEntries.value[0]
})

function normalizeEvidence(items = []) {
  return items.map((item) => ({
    label: item.label || 'Evidence',
    value: item.value || 'Not available',
    source: item.source || 'System signal',
    weight: item.weight || item.priority || 'Medium',
    confidence: item.confidence || item.trust || 'N/A',
  }))
}

function mapKnowledgeResponse(response) {
  const result = response?.result || response || {}
  const confidenceValue = typeof result.confidence === 'number' ? `${Math.round(result.confidence * 100)}%` : String(result.confidence || 'N/A')

  return {
    role: 'assistant',
    title: result.rule?.name || 'Knowledge result',
    status: result.rule?.severity || 'Review required',
    severity: result.rule?.severity || 'Medium Priority',
    category: result.rule?.category || 'Governance',
    subject: result.subject?.entity_name || 'Portfolio overview',
    confidence: confidenceValue,
    decision: {
      label: 'Conclusion',
      value: result.decision?.value || result.summary || 'Governance review is required.',
    },
    risk: {
      label: 'Risk',
      value: result.risk?.value || 'Potential policy exposure remains unresolved.',
    },
    action: {
      label: 'Action',
      value: result.recommendation?.action || 'Review the related governance rule.',
    },
    decisionState: result.decision_state || result.decisionState || 'Review pending',
    fallback: result.fallback || 'Continue with the currently approved rule set.',
    contextMemory: Array.isArray(result.context_memory || result.contextMemory)
      ? (result.context_memory || result.contextMemory)
      : ['Previous question reviewed', 'Follow-up route available'],
    rule: {
      code: result.rule?.code || 'N/A',
      name: result.rule?.name || 'Governance rule',
      scope: result.rule?.scope || 'Portfolio',
    },
    summary: result.summary || 'No summary available.',
    evidence: normalizeEvidence(Array.isArray(result.evidence) ? result.evidence : []),
    recommendation: {
      action: result.recommendation?.action || 'Review the related governance rule.',
      rationale: result.recommendation?.rationale || 'No rationale provided.',
      impact: result.recommendation?.impact || 'No impact recorded.',
    },
    relatedRules: Array.isArray(result.related_rules) ? result.related_rules : [],
  }
}

async function submitPrompt(promptOverride = null) {
  const valueFromEvent =
    promptOverride && typeof promptOverride === 'object' && 'target' in promptOverride
      ? String(promptOverride.target.value || '')
      : null

  const raw = String(valueFromEvent ?? promptOverride ?? draft.value ?? '').trim()
  if (!raw) return

  try {
    const response = await queryKnowledge({
      query: raw,
      campaign_id: null,
      context: {
        portfolio: 'brandlens',
        user_role: 'marketing_manager',
      },
    })

    const answer = mapKnowledgeResponse(response)
    const entry = {
      id: `entry-${Date.now()}-${Math.random().toString(16).slice(2)}`,
      question: raw,
      answer,
    }
    historyEntries.value.unshift(entry)
    selectedHistoryId.value = entry.id
  } catch (error) {
    const answer = {
      role: 'assistant',
      title: 'Knowledge lookup unavailable',
      status: 'System error',
      severity: 'Low Priority',
      category: 'API status',
      subject: 'Knowledge service',
      confidence: 'N/A',
      decision: {
        label: 'Conclusion',
        value: 'The knowledge service is temporarily unavailable.',
      },
      risk: {
        label: 'Risk',
        value: 'Decision support remains limited until the service recovers.',
      },
      action: {
        label: 'Action',
        value: 'Retry the query or continue with the local governance snapshot.',
      },
      decisionState: 'Service unavailable',
      fallback: 'Continue using the last approved governance state.',
      contextMemory: ['Previous review available', 'Retry recommended'],
      rule: { code: 'SYS-ERR', name: 'Service error', scope: 'Portal' },
      summary: 'The knowledge API is unavailable. The UI is still showing the last known governance result.',
      evidence: [],
      recommendation: {
        action: 'Retry the query or continue with the local governance snapshot.',
        rationale: 'This keeps the decision flow active while the service endpoint recovers.',
        impact: 'Maintains continuity of the governance review experience.',
      },
      relatedRules: [],
    }
    const entry = {
      id: `entry-${Date.now()}-${Math.random().toString(16).slice(2)}`,
      question: raw,
      answer,
    }
    historyEntries.value.unshift(entry)
    selectedHistoryId.value = entry.id
  }

  draft.value = ''
}

function askTemplate(template) {
  draft.value = template
  submitPrompt(template)
}
</script>

<template>
  <section class="page-grid knowledge-page">
    <article class="card knowledge-card">
      <div class="card-head">
        <h2>Knowledge assistant</h2>
        <span class="tag blue">Business QA</span>
      </div>

      <div class="card-body knowledge-shell">
        <aside class="knowledge-sidebar">
          <div class="assistant-search">
            <label>Ask BrandLens</label>
            <div class="search-box">
              <input v-model="draft" type="text" placeholder="Search rules, campaigns, or governance" @keydown.enter.prevent="submitPrompt" />
              <button class="btn primary small" @click="submitPrompt">Ask</button>
            </div>
          </div>

          <div class="assistant-panel-block">
            <h3>Common questions</h3>
            <div class="quick-prompts">
              <button v-for="template in promptTemplates" :key="template" class="prompt-chip" @click="askTemplate(template)">
                {{ template }}
              </button>
            </div>
          </div>

          <div class="assistant-panel-block compact">
            <h3>Priority signals</h3>
            <div class="signal-list">
              <div>
                <strong>93%</strong>
                <span>coverage</span>
              </div>
              <div>
                <strong>3</strong>
                <span>active conflicts</span>
              </div>
              <div>
                <strong>2</strong>
                <span>budget risks</span>
              </div>
            </div>
          </div>
        </aside>

        <div class="conversation-panel">
          <div class="assistant-header-panel">
            <div>
              <span class="eyebrow">Governance assistant</span>
              <h3>Portfolio knowledge support</h3>
            </div>
            <div class="header-status">
              <span class="dot" />
              Live insight feed
            </div>
          </div>

          <div class="history-layout">
            <aside class="history-list-panel">
              <div class="history-header">
                <h4>Question history</h4>
              </div>
              <button
                v-for="entry in historyEntries"
                :key="entry.id"
                class="history-item"
                :class="{ active: selectedEntry && selectedEntry.id === entry.id }"
                @click="selectedHistoryId = entry.id"
              >
                <span class="history-question">{{ entry.question }}</span>
                <span class="history-status">{{ entry.answer.status }}</span>
              </button>
            </aside>

            <div v-if="selectedEntry" class="detail-panel">
              <div class="detail-question-header">
                <div class="bubble-tag assistant">Assistant</div>
                <span class="mini-tag" :class="selectedEntry.answer.severity === 'High Priority' ? 'amber' : selectedEntry.answer.severity === 'Low Priority' ? 'green' : 'red'">{{ selectedEntry.answer.status }}</span>
              </div>

              <div class="detail-question-text">
                <label>Question</label>
                <strong>{{ selectedEntry.question }}</strong>
              </div>

              <div class="answer-header">
                <strong>{{ selectedEntry.answer.title }}</strong>
                <span>{{ selectedEntry.answer.confidence }} confidence</span>
              </div>

              <div class="answer-decision-grid">
                <div class="decision-block primary">
                  <label>{{ selectedEntry.answer.decision?.label || 'Conclusion' }}</label>
                  <strong>{{ selectedEntry.answer.decision?.value || selectedEntry.answer.title }}</strong>
                </div>
                <div class="decision-block amber">
                  <label>{{ selectedEntry.answer.risk?.label || 'Risk' }}</label>
                  <strong>{{ selectedEntry.answer.risk?.value || 'Review required' }}</strong>
                </div>
                <div class="decision-block green">
                  <label>{{ selectedEntry.answer.action?.label || 'Action' }}</label>
                  <strong>{{ selectedEntry.answer.action?.value || selectedEntry.answer.recommendation.action }}</strong>
                </div>
              </div>

              <div class="decision-meta-row">
                <div>
                  <label>Decision state</label>
                  <span>{{ selectedEntry.answer.decisionState }}</span>
                </div>
                <div>
                  <label>Fallback</label>
                  <span>{{ selectedEntry.answer.fallback }}</span>
                </div>
              </div>

              <div class="rule-meta">
                <div><label>Rule</label><strong>{{ selectedEntry.answer.rule.code }}</strong></div>
                <div><label>Category</label><strong>{{ selectedEntry.answer.category }}</strong></div>
                <div><label>Subject</label><strong>{{ selectedEntry.answer.subject }}</strong></div>
              </div>

              <p class="answer-summary">{{ selectedEntry.answer.summary }}</p>

              <div v-if="selectedEntry.answer.relatedRules?.length" class="rule-pills">
                <span v-for="rule in selectedEntry.answer.relatedRules" :key="rule">{{ rule }}</span>
              </div>

              <div v-if="selectedEntry.answer.evidence?.length" class="evidence-box">
                <label>Evidence</label>
                <ul>
                  <li v-for="item in selectedEntry.answer.evidence" :key="item.label + item.value">
                    <div class="evidence-head">
                      <strong>{{ item.label }}</strong>
                      <span>— {{ item.value }}</span>
                    </div>
                    <div class="evidence-meta">
                      <em>{{ item.source }}</em>
                      <b>{{ item.weight }}</b>
                      <i>{{ item.confidence }}</i>
                    </div>
                  </li>
                </ul>
              </div>

              <div v-if="selectedEntry.answer.contextMemory?.length" class="context-memory-box">
                <label>Context memory</label>
                <ul>
                  <li v-for="item in selectedEntry.answer.contextMemory" :key="item">{{ item }}</li>
                </ul>
              </div>

              <div class="recommendation-box">
                <label>Recommended action</label>
                <p>{{ selectedEntry.answer.recommendation.action }}</p>
                <small>{{ selectedEntry.answer.recommendation.rationale }}</small>
                <small>{{ selectedEntry.answer.recommendation.impact }}</small>
              </div>
            </div>
          </div>
        </div>

        <aside class="insight-rail">
          <div class="insight-card highlight">
            <span class="insight-label">Current focus</span>
            <strong>DSP Prospecting</strong>
            <p>Coverage is active but lacks approved governance.</p>
          </div>

          <div class="insight-card">
            <span class="insight-label">Related rules</span>
            <ul>
              <li>DSP Prospecting coverage</li>
              <li>Protected discovery minimum</li>
              <li>Portfolio reallocation guardrail</li>
            </ul>
          </div>

          <div class="insight-card">
            <span class="insight-label">Action snapshot</span>
            <ul>
              <li>Request coverage approval</li>
              <li>Stabilize learning minimums</li>
              <li>Review pilot scope</li>
            </ul>
          </div>
        </aside>
      </div>
    </article>

    <article class="card">
      <div class="card-head">
        <h2>Concepts & rules requiring attention</h2>
        <span class="tag gray">Simulated data</span>
      </div>
      <div class="card-body list-stack">
        <div v-for="item in knowledgeAssets" :key="item[0]" class="attention-item">
          <b>{{ item[0] }}</b>
          <span>{{ item[1] }}</span>
          <span>{{ item[2] }}</span>
          <span>{{ item[3] }}</span>
          <span class="tag" :class="item[5]">{{ item[4] }}</span>
        </div>
      </div>
    </article>

    <article class="card">
      <div class="card-head">
        <h2>Ontology health</h2>
        <span class="sub">Computed demo snapshot</span>
      </div>
      <div class="card-body">
        <div class="health-grid">
          <div v-for="item in knowledgeHealth" :key="item[0]" class="health-card">
            <b>{{ item[0] }}</b>
            <span>{{ item[1] }}</span>
          </div>
        </div>
      </div>
    </article>
  </section>
</template>
