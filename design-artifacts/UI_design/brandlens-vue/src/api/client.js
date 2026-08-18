const API_BASE = '/api'

export const KNOWLEDGE_QUERY_SCHEMA = {
  query: 'string',
  campaign_id: 'string | null',
  context: {
    portfolio: 'string',
    user_role: 'string',
  },
}

export const KNOWLEDGE_RESPONSE_SCHEMA = {
  status: 'success | error',
  result: {
    query: 'string',
    rule: {
      code: 'string',
      name: 'string',
      scope: 'string',
      category: 'string',
      severity: 'string',
    },
    subject: {
      entity_type: 'string',
      entity_id: 'string',
      entity_name: 'string',
    },
    summary: 'string',
    confidence: 'number',
    decision: {
      value: 'string',
    },
    risk: {
      value: 'string',
    },
    decision_state: 'string',
    fallback: 'string',
    context_memory: ['string'],
    evidence: [
      {
        label: 'string',
        value: 'string',
        source: 'string',
        weight: 'string',
        confidence: 'string',
      },
    ],
    recommendation: {
      action: 'string',
      rationale: 'string',
      impact: 'string',
    },
    related_rules: ['string'],
  },
}

const knowledgeCatalog = [
  {
    query: 'coverage',
    status: 'success',
    result: {
      query: 'Why is DSP prospecting missing coverage?',
      rule: {
        code: 'GOV-031',
        name: 'Audience coverage policy',
        scope: 'DSP prospecting',
        category: 'Audience coverage',
        severity: 'High Priority',
      },
      subject: {
        entity_type: 'Campaign',
        entity_id: 'dsp-prospecting',
        entity_name: 'DSP Prospecting — US',
      },
      summary: 'There is no approved rule covering third-party prospecting audiences in the current knowledge layer. This is a governance issue rather than a media performance problem, and it should be resolved before expansion.',
      confidence: 0.89,
      decision: {
        value: 'Stop expansion until the audience coverage rule is approved.',
      },
      risk: {
        value: 'Unapproved audience exposure creates brand and compliance risk.',
      },
      decision_state: 'Awaiting governance approval',
      fallback: 'Continue using approved audience classes only.',
      context_memory: ['Previous: DSP coverage review', 'Follow-up: budget guardrail check', 'Current: approval workflow pending'],
      evidence: [
        { label: 'System state', value: 'NO_COVERAGE', source: 'Governance status', weight: 'High', confidence: '96%' },
        { label: 'Impact', value: 'Lookalike and lifestyle segments are outside the active approval scope', source: 'Audience taxonomy', weight: 'High', confidence: '91%' },
        { label: 'Risk', value: 'Expansion could proceed without policy validation', source: 'Decision guardrail', weight: 'Critical', confidence: '94%' },
      ],
      recommendation: {
        action: 'Request a coverage rule or temporarily limit activation to verified audience classes.',
        rationale: 'This closes the governance gap before further scaling.',
        impact: 'Prevents unapproved audience exposure while preserving campaign flexibility.',
      },
      related_rules: ['DSP Prospecting coverage', 'Audience approval standard', 'Brand safety policy'],
    },
  },
  {
    query: 'budget',
    status: 'success',
    result: {
      query: 'Which rule should I review next for budget risk?',
      rule: {
        code: 'GOV-118',
        name: 'Protected discovery minimum',
        scope: 'Learning budget',
        category: 'Budget governance',
        severity: 'Medium Priority',
      },
      subject: {
        entity_type: 'Campaign',
        entity_id: 'shave-us',
        entity_name: 'Shave Care — US',
      },
      summary: 'The portfolio shows a concentrated risk in Shave Care, where lower discovery budget has created a rule conflict and requires a formal review before optimization is expanded.',
      confidence: 0.84,
      decision: {
        value: 'Review learning budget before expanding reallocation.',
      },
      risk: {
        value: 'Low discovery spend could reduce test quality and violate learning minimums.',
      },
      decision_state: 'Budget guardrail active',
      fallback: 'Preserve the current allocation while protecting brand defense spend.',
      context_memory: ['Previous: budget risk triage', 'Follow-up: confirm learning minimums', 'Current: limited reallocation allowed'],
      evidence: [
        { label: 'Check', value: 'Minimum learning budget is not satisfied in two ad groups', source: 'Optimization log', weight: 'High', confidence: '88%' },
        { label: 'Allocation', value: 'Reallocation remains within the total budget envelope', source: 'Budget manager', weight: 'Medium', confidence: '85%' },
        { label: 'Cause', value: 'Risk is tied to learning balance rather than overspend', source: 'Forecast model', weight: 'Medium', confidence: '82%' },
      ],
      recommendation: {
        action: 'Shift a modest portion of spend toward brand defense and retention to restore learning minimums.',
        rationale: 'This resolves the rule conflict without over-committing the portfolio.',
        impact: 'Stabilizes campaign learning before adding incremental reach.',
      },
      related_rules: ['Discovery minimum', 'Reallocation guardrail', 'Learning balance threshold'],
    },
  },
  {
    query: 'evidence',
    status: 'success',
    result: {
      query: 'What evidence supports the recommended reallocation?',
      rule: {
        code: 'GOV-208',
        name: 'Evidence validation checkpoint',
        scope: 'Recommendation approval',
        category: 'Decision validation',
        severity: 'Low Priority',
      },
      subject: {
        entity_type: 'Portfolio',
        entity_id: 'portfolio',
        entity_name: 'Portfolio recommendation',
      },
      summary: 'The recommendation is supported by recent ROAS trends, a stable budget envelope, and the current rule state. Confidence remains moderate because one governance rule remains open.',
      confidence: 0.81,
      decision: {
        value: 'Proceed with a limited adjustment and recheck after the next cycle.',
      },
      risk: {
        value: 'A lingering governance exception could reduce confidence if the rule remains open.',
      },
      decision_state: 'Conditional approval',
      fallback: 'Pause before scale-up if evidence degrades in the next cycle.',
      context_memory: ['Previous: evidence validation', 'Follow-up: confirm open governance issue', 'Current: one exception remains active'],
      evidence: [
        { label: 'Performance', value: 'Forecasted ROAS is above baseline objective', source: 'Optimizer model', weight: 'High', confidence: '87%' },
        { label: 'Scope', value: 'Rule conflict is limited to a subset of ad groups', source: 'Campaign review', weight: 'Medium', confidence: '84%' },
        { label: 'Control', value: 'Control performance validates the direction of the adjustment', source: 'Experiment baseline', weight: 'High', confidence: '90%' },
      ],
      recommendation: {
        action: 'Monitor after one optimization cycle and confirm the open governance issue is resolved before additional scaling.',
        rationale: 'This preserves momentum while retaining compliance certainty.',
        impact: 'Maintains optimization velocity without creating governance drift.',
      },
      related_rules: ['Forecast quality check', 'Reallocation validation', 'Exception review'],
    },
  },
]

function matchKnowledgeResponse(query) {
  const normalized = query.toLowerCase()

  if (normalized.includes('coverage') || normalized.includes('dsp')) {
    return knowledgeCatalog[0]
  }

  if (normalized.includes('budget') || normalized.includes('realloc') || normalized.includes('risk')) {
    return knowledgeCatalog[1]
  }

  if (normalized.includes('evidence') || normalized.includes('support')) {
    return knowledgeCatalog[2]
  }

  return {
    status: 'success',
    result: {
      query,
      rule: {
        code: 'GOV-001',
        name: 'Portfolio knowledge triage',
        scope: 'Portfolio overview',
        category: 'Governance review',
        severity: 'High Priority',
      },
      subject: {
        entity_type: 'Portfolio',
        entity_id: 'portfolio',
        entity_name: 'Portfolio overview',
      },
      summary: 'The current knowledge layer identifies three key issues: missing DSP coverage, a discovery budget conflict, and an unassigned regional pilot definition. These need to be resolved in sequence before further scaling.',
      confidence: 0.78,
      decision: {
        value: 'Prioritize coverage and budget governance before scale-up.',
      },
      risk: {
        value: 'Execution risk stays elevated until the top governance blockers are resolved.',
      },
      decision_state: 'Review in sequence',
      fallback: 'Keep the current portfolio baseline while maintaining active compliance review.',
      context_memory: ['Previous: broad portfolio review', 'Follow-up: inspect coverage and budget blockers', 'Current: scale-up paused'],
      evidence: [
        { label: 'Coverage', value: 'Rule coverage is 93% with three active conflicts', source: 'Knowledge status', weight: 'High', confidence: '90%' },
        { label: 'Budget', value: 'Two campaign groups require governance review', source: 'Budget manager', weight: 'High', confidence: '88%' },
        { label: 'Pilot', value: 'The pilot concept exists but is not assigned to a formal taxonomy', source: 'Pilot definition', weight: 'Medium', confidence: '82%' },
      ],
      recommendation: {
        action: 'Prioritize the coverage gap and discovery minimum before stepping into scale-up.',
        rationale: 'This resolves the highest-risk blockers in the correct sequence.',
        impact: 'Improves governance readiness before pilot expansion.',
      },
      related_rules: ['Coverage governance', 'Budget threshold', 'Pilot definition'],
    },
  }
}

export async function fetchDashboard() {
  const response = await fetch(`${API_BASE}/dashboard`)
  if (!response.ok) throw new Error('Failed to load dashboard data')
  return response.json()
}

export async function saveFeedback(payload) {
  const response = await fetch(`${API_BASE}/feedback`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!response.ok) throw new Error('Failed to save feedback')
  return response.json()
}

export async function queryKnowledge(payload = {}) {
  const query = typeof payload === 'string' ? payload : payload.query || ''
  const normalized = matchKnowledgeResponse(query)
  return normalized
}
