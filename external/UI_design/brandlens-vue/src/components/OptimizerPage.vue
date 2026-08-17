<script setup>
defineProps({
  activeCampaign: {
    type: Object,
    default: () => ({}),
  },
  currentCampaignId: {
    type: String,
    default: null,
  },
  optimizerReady: {
    type: Boolean,
    default: false,
  },
  review: {
    type: Object,
    default: () => ({}),
  },
  reviewToneClass: {
    type: String,
    default: 'gray',
  },
  feedbackChoices: {
    type: Array,
    default: () => [],
  },
  feedbackNote: {
    type: String,
    default: '',
  },
  noteOpen: {
    type: Boolean,
    default: false,
  },
  feedbackAction: {
    type: String,
    default: '',
  },
  money: {
    type: Function,
    default: () => '$0K',
  },
  pilotState: {
    type: String,
    default: 'Texas',
  },
  pilotControls: {
    type: String,
    default: 'Oklahoma + Louisiana',
  },
  pilotDuration: {
    type: String,
    default: '4 weeks',
  },
  pilotMetric: {
    type: String,
    default: 'ROAS',
  },
  pilotShare: {
    type: String,
    default: '10%',
  },
})

const emit = defineEmits(['clearCampaign', 'runOptimizer', 'adopt', 'toggleNote', 'submitFeedback', 'startPilot', 'update:feedbackNote', 'update:pilotState', 'update:pilotControls', 'update:pilotDuration', 'update:pilotMetric', 'update:pilotShare'])
</script>

<template>
  <section class="page-grid optimizer-page">
    <div class="optimizer-bar card">
      <div>
        <strong>{{ activeCampaign.name }}</strong>
        <span>{{ activeCampaign.id === 'portfolio' ? 'Portfolio view' : 'Campaign' }} · Fixed budget {{ money(activeCampaign.budget) }}</span>
      </div>
      <div class="actions">
        <button v-if="currentCampaignId" class="btn small" @click="emit('clearCampaign')">Portfolio</button>
        <button class="btn primary" @click="emit('runOptimizer')">{{ optimizerReady ? 'Run again' : 'Run Optimizer' }}</button>
      </div>
    </div>

    <div v-if="!optimizerReady && !activeCampaign.adopted" class="card empty-card">
      <h2>Optimizer pending</h2>
      <p>Run the optimizer to compare current and recommended ad-group allocation.</p>
    </div>

    <div v-else class="optimizer-grid">
      <article class="card recommendation">
        <div class="card-head">
          <h2>Recommended allocation</h2>
          <span class="tag blue">Total preserved</span>
        </div>
        <div class="card-body">
          <div class="rec-summary">
            <div>
              <b>Reallocate budget across {{ activeCampaign.groups.length }} ad groups</b>
              <p>Expected blended ROAS: {{ activeCampaign.roas.toFixed(2) }}x → {{ activeCampaign.recRoas.toFixed(2) }}x</p>
            </div>
            <b>{{ money(activeCampaign.groups.reduce((sum, item) => sum + item[1], 0)) }} → {{ money(activeCampaign.groups.reduce((sum, item) => sum + item[2], 0)) }}</b>
          </div>
          <div class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Ad group</th>
                  <th class="num">Current</th>
                  <th class="num">Recommended</th>
                  <th class="num">Change</th>
                  <th class="num">Expected ROAS</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="group in activeCampaign.groups" :key="group[0]">
                  <td class="name"><strong>{{ group[0] }}</strong></td>
                  <td class="num">{{ money(group[1]) }}</td>
                  <td class="num"><b>{{ money(group[2]) }}</b></td>
                  <td class="num" :class="group[2] - group[1] >= 0 ? 'up' : 'down'">{{ group[2] - group[1] >= 0 ? '+' : '' }}{{ money(group[2] - group[1]) }}</td>
                  <td class="num">{{ group[3].toFixed(1) }}x</td>
                </tr>
              </tbody>
            </table>
          </div>
          <div class="rec-actions">
            <button v-if="activeCampaign.id !== 'portfolio'" class="btn primary" @click="emit('adopt')">Adopt recommendation</button>
            <button v-else class="btn primary" @click="emit('clearCampaign')">Choose campaign to adopt</button>
            <button class="btn" @click="emit('runOptimizer')">Adjust allocation</button>
          </div>
        </div>
      </article>

      <aside class="card review-card">
        <div class="card-head">
          <h2>Ontology review</h2>
        </div>
        <div class="card-body">
          <div class="review-head">
            <strong>{{ review.outcome }}</strong>
            <span class="tag" :class="reviewToneClass">{{ review.risk }} risk</span>
          </div>
          <div class="review-rule">
            <label>{{ review.outcome === 'CONFLICT' ? 'Violated rule' : review.outcome === 'NO_COVERAGE' ? 'Coverage gap' : 'Matched rule' }}</label>
            <b>{{ review.rule }}</b>
            <p>{{ review.message }}</p>
          </div>

          <div v-if="feedbackAction" class="feedback-confirm">
            <strong>Feedback recorded</strong>
            <p>{{ feedbackAction }}</p>
          </div>
          <div v-else class="feedback-area">
            <div class="feedback-actions">
              <button v-for="choice in feedbackChoices" :key="choice" class="btn small" @click="emit('submitFeedback', choice)">{{ choice }}</button>
            </div>
            <button class="btn link small" @click="emit('toggleNote')">Add evidence or comment</button>
            <div v-if="noteOpen" class="feedback-note">
              <textarea :value="feedbackNote" @input="emit('update:feedbackNote', $event.target.value)" rows="3" placeholder="Optional note"></textarea>
            </div>
          </div>
        </div>
      </aside>
    </div>

    <section v-if="activeCampaign.id !== 'portfolio' && activeCampaign.adopted" class="card pilot-card">
      <div class="card-head">
        <h2>Regional pilot</h2>
        <span class="sub">Pilot state vs control states</span>
        <span class="tag green">Completed</span>
      </div>
      <div class="card-body">
        <div class="pilot-form">
          <div class="field">
            <label>Pilot state</label>
            <select :value="pilotState" @change="emit('update:pilotState', $event.target.value)">
              <option>Texas</option>
              <option>California</option>
              <option>Florida</option>
            </select>
          </div>
          <div class="field">
            <label>Control states</label>
            <select :value="pilotControls" @change="emit('update:pilotControls', $event.target.value)">
              <option>Oklahoma + Louisiana</option>
              <option>Nevada + Arizona</option>
              <option>Georgia + Alabama</option>
            </select>
          </div>
          <div class="field">
            <label>Duration</label>
            <select :value="pilotDuration" @change="emit('update:pilotDuration', $event.target.value)">
              <option>4 weeks</option>
              <option>6 weeks</option>
            </select>
          </div>
          <div class="field">
            <label>Success metric</label>
            <select :value="pilotMetric" @change="emit('update:pilotMetric', $event.target.value)">
              <option>ROAS</option>
              <option>CPA</option>
            </select>
          </div>
          <div class="field">
            <label>Variant budget</label>
            <select :value="pilotShare" @change="emit('update:pilotShare', $event.target.value)">
              <option>10%</option>
              <option>15%</option>
              <option>20%</option>
            </select>
          </div>
        </div>
        <button class="btn primary" @click="emit('startPilot')">Run again</button>
      </div>
    </section>
  </section>
</template>
