export const campaigns = [
  {
    id: 'shave-us',
    name: 'Shave Care — US',
    budget: 500,
    spend: 374,
    forecast: 492,
    roas: 4.18,
    recRoas: 4.83,
    controlRoas: 4.31,
    status: 'Needs optimization',
    review: { outcome: 'CONFLICT', rule: 'Protected Discovery Minimum', message: 'Two ad groups fall below the required learning budget.', risk: 'High' },
    groups: [['Brand Defense', 120, 155, 6.1], ['Generic Search', 180, 150, 3.2], ['Retargeting', 90, 100, 4.5], ['Discovery', 110, 95, 2.6]],
    adopted: false,
    pilot: null,
    feedback: null,
  },
  {
    id: 'stv-launch',
    name: 'Streaming TV — Spring',
    budget: 360,
    spend: 249,
    forecast: 352,
    roas: 3.90,
    recRoas: 4.32,
    controlRoas: 3.90,
    status: 'Opportunity',
    review: { outcome: 'MATCH', rule: 'Upper-funnel Investment Cap', message: 'The proposed pilot stays within the approved 25% launch cap.', risk: 'Low' },
    groups: [['Texas Pilot', 70, 95, 4.6], ['Southeast Control', 90, 80, 3.7], ['National Awareness', 140, 130, 3.9], ['Retargeting', 60, 55, 4.1]],
    adopted: true,
    pilot: { state: 'Texas', controls: 'Oklahoma + Louisiana', duration: '4 weeks', metric: 'ROAS', share: '15%', ran: true },
    feedback: null,
  },
  {
    id: 'dsp-prospecting',
    name: 'DSP Prospecting — US',
    budget: 420,
    spend: 238,
    forecast: 361,
    roas: 2.10,
    recRoas: 2.56,
    controlRoas: 2.23,
    status: 'Review',
    review: { outcome: 'NO_COVERAGE', rule: 'No applicable prospecting rule', message: 'Third-party prospecting audiences are not covered by an approved rule.', risk: 'Medium' },
    groups: [['In-market Audiences', 150, 130, 2.4], ['Lifestyle Audiences', 105, 95, 2.0], ['Contextual', 85, 110, 2.8], ['Lookalike', 80, 85, 2.3]],
    adopted: false,
    pilot: null,
    feedback: null,
  },
]

export const portfolioScenario = {
  id: 'portfolio',
  name: 'Portfolio example',
  budget: 500,
  roas: 4.18,
  recRoas: 4.83,
  controlRoas: 4.31,
  adopted: false,
  feedback: null,
  pilot: null,
  review: { outcome: 'MATCH', rule: 'Fixed-budget Reallocation', message: 'The recommendation preserves total approved spend.', risk: 'Low' },
  groups: [['Brand Search', 150, 175, 5.8], ['Generic Search', 140, 120, 3.1], ['Retargeting', 100, 115, 4.4], ['Prospecting', 110, 90, 2.3]],
}

export const meta = {
  overview: ['Command Center', 'BrandLens / Overview'],
  budget: ['Budget Manager', 'BrandLens / Planning / Budget'],
  campaigns: ['Campaigns', 'BrandLens / Planning / Campaigns'],
  optimizer: ['Campaign Optimizer', 'BrandLens / Planning / Optimizer'],
  log: ['Optimization Log', 'BrandLens / Insights / Results'],
  knowledge: ['Knowledge Base', 'BrandLens / Insights / Governance'],
}

export const overviewRows = [
  ['Streaming TV — Texas pilot', 'ROAS +10.8%', 'Verified'],
  ['Shave Care — US', '$65K reallocated', 'Review'],
  ['DSP Prospecting — US', 'Coverage requested', 'NO_COVERAGE'],
]

export const logRows = [
  ['Jul 20', 'Streaming TV — Spring', 'Texas +15%', 'MATCH', 'Texas', 'ROAS +10.8%', 'Verified'],
  ['Jul 18', 'Shave Care — US', '$65K reallocated', 'CONFLICT', '—', 'Pending', 'Review'],
  ['Jul 14', 'DSP Prospecting — US', 'Coverage requested', 'NO_COVERAGE', '—', '—', 'Open'],
]

export const knowledgeAssets = [
  ['DSP Prospecting', 'Rule', 'Coverage gap', 'Programmatic COE', 'Needs review', 'red'],
  ['Discovery Minimum', 'Rule', '3 user challenges', 'Search COE', 'Review', 'amber'],
  ['Regional Pilot', 'Concept', 'Missing definition', 'Unassigned', 'Draft', 'gray'],
]

export const knowledgeHealth = [
  ['93%', 'Rule coverage'],
  ['3', 'Rule conflicts'],
  ['6', 'Expiring assets'],
  ['4', 'Golden Test failures'],
]
