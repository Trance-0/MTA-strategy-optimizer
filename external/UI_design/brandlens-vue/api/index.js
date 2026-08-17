import express from 'express'

const app = express()
app.use(express.json())

app.get('/api/dashboard', (_req, res) => {
  res.json({
    overviewRows: [
      ['Streaming TV — Texas pilot', 'ROAS +10.8%', 'Verified'],
      ['Shave Care — US', '$65K reallocated', 'Review'],
      ['DSP Prospecting — US', 'Coverage requested', 'NO_COVERAGE'],
    ],
    campaigns: [
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
    ],
    logRows: [
      ['Jul 20', 'Streaming TV — Spring', 'Texas +15%', 'MATCH', 'Texas', 'ROAS +10.8%', 'Verified'],
      ['Jul 18', 'Shave Care — US', '$65K reallocated', 'CONFLICT', '—', 'Pending', 'Review'],
    ],
    knowledgeAssets: [
      ['DSP Prospecting', 'Rule', 'Coverage gap', 'Programmatic COE', 'Needs review', 'red'],
      ['Discovery Minimum', 'Rule', '3 user challenges', 'Search COE', 'Review', 'amber'],
    ],
    knowledgeHealth: [['93%', 'Rule coverage'], ['3', 'Rule conflicts'], ['6', 'Expiring assets']],
  })
})

app.post('/api/feedback', (req, res) => {
  res.json({ ok: true, payload: req.body })
})

app.listen(3001, () => {
  console.log('BrandLens API listening on http://127.0.0.1:3001')
})
