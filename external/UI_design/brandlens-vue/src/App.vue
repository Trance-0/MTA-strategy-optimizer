<script setup>
import { computed, onMounted, ref } from 'vue'
import { campaigns as mockCampaigns, portfolioScenario, meta, overviewRows as mockOverviewRows, logRows as mockLogRows, knowledgeAssets as mockKnowledgeAssets, knowledgeHealth as mockKnowledgeHealth } from './data/mockData'
import SidebarNav from './components/SidebarNav.vue'
import TopBar from './components/TopBar.vue'
import OverviewPage from './components/OverviewPage.vue'
import BudgetPage from './components/BudgetPage.vue'
import CampaignsPage from './components/CampaignsPage.vue'
import OptimizerPage from './components/OptimizerPage.vue'
import LogPage from './components/LogPage.vue'
import KnowledgePage from './components/KnowledgePage.vue'
import { fetchDashboard, saveFeedback } from './api/client'

const validPages = ['overview', 'budget', 'campaigns', 'optimizer', 'log', 'knowledge']
const currentPage = ref('overview')
const currentCampaignId = ref(null)
const optimizerReady = ref(false)
const noteOpen = ref(false)
const toastMessage = ref('')
const feedbackNote = ref('')
const feedbackAction = ref('')
const pilotState = ref('Texas')
const pilotControls = ref('Oklahoma + Louisiana')
const pilotDuration = ref('4 weeks')
const pilotMetric = ref('ROAS')
const pilotShare = ref('10%')

const campaigns = ref([...mockCampaigns])
const overviewRows = ref([...mockOverviewRows])
const logRows = ref([...mockLogRows])
const knowledgeAssets = ref([...mockKnowledgeAssets])
const knowledgeHealth = ref([...mockKnowledgeHealth])

let toastTimer = null
let runToken = 0

const currentCampaign = computed(() => campaigns.value.find((item) => item.id === currentCampaignId.value) || null)
const activeCampaign = computed(() => currentCampaign.value || portfolioScenario)
const pageTitle = computed(() => meta[currentPage.value]?.[0] || 'Command Center')
const pageCrumb = computed(() => meta[currentPage.value]?.[1] || 'BrandLens / Overview')

function money(value) {
  return `${value < 0 ? '−$' : '$'}${Math.abs(value)}K`
}

function pct(a, b) {
  return `${Math.round((a / b) * 100)}%`
}

function tone(value) {
  if (['MATCH', 'Verified', 'On track'].includes(value)) return 'green'
  if (['CONFLICT', 'At risk', 'Needs optimization'].includes(value)) return 'red'
  if (['NO_COVERAGE', 'Review', 'Opportunity', 'Underspending'].includes(value)) return 'amber'
  return 'gray'
}

function budgetState(item) {
  if (item.forecast > item.budget * 1.03) return ['At risk', 'red']
  if (item.spend / item.budget < 0.62) return ['Underspending', 'amber']
  return ['On track', 'green']
}

function normalizePage(page) {
  return validPages.includes(page) ? page : 'overview'
}

function syncHash(page) {
  const nextPage = normalizePage(page)
  const hash = `#${nextPage}`
  if (window.location.hash !== hash) {
    window.history.replaceState(null, '', hash)
  }
  currentPage.value = nextPage
}

function go(page) {
  const nextPage = normalizePage(page)
  currentPage.value = nextPage
  syncHash(nextPage)
  feedbackNote.value = ''
  feedbackAction.value = ''
  window.scrollTo(0, 0)
}

function openOptimizer(id) {
  runToken += 1
  currentCampaignId.value = id
  optimizerReady.value = false
  noteOpen.value = false
  feedbackNote.value = ''
  feedbackAction.value = ''
  go('optimizer')
}

function clearCampaign() {
  runToken += 1
  currentCampaignId.value = null
  optimizerReady.value = false
  noteOpen.value = false
  feedbackNote.value = ''
  feedbackAction.value = ''
  go('optimizer')
}

function runOptimizer() {
  const token = ++runToken
  const id = currentCampaignId.value
  setTimeout(() => {
    if (token !== runToken || id !== currentCampaignId.value) return
    optimizerReady.value = true
    if (currentPage.value === 'optimizer') {
      go('optimizer')
    }
    toast('Recommendation ready')
  }, 450)
}

function adopt() {
  const campaign = activeCampaign.value
  if (!campaign || campaign.id === 'portfolio') {
    toast('Choose a campaign before adoption')
    return
  }
  campaign.adopted = true
  optimizerReady.value = true
  go('optimizer')
  toast('Recommendation adopted')
}

function toggleNote() {
  noteOpen.value = !noteOpen.value
}

async function submitFeedback(action) {
  const campaign = activeCampaign.value
  if (!campaign) return
  const payload = { action, note: feedbackNote.value.trim(), campaignId: campaign.id }
  campaign.feedback = payload
  feedbackAction.value = action
  try {
    await saveFeedback(payload)
    toast('Feedback recorded for ontology review')
  } catch (error) {
    toast('Saved locally; API unavailable')
  }
}

function startPilot() {
  const campaign = activeCampaign.value
  if (!campaign || campaign.id === 'portfolio') {
    toast('Select a campaign before starting a regional pilot')
    return
  }
  if (pilotControls.value.split(' + ').includes(pilotState.value)) {
    toast('Pilot and control regions must be different')
    return
  }
  campaign.pilot = {
    state: pilotState.value,
    controls: pilotControls.value,
    duration: pilotDuration.value,
    metric: pilotMetric.value,
    share: pilotShare.value,
    ran: true,
  }
  go('optimizer')
  toast('Regional pilot completed in demo')
}

function toast(message) {
  toastMessage.value = message
  clearTimeout(toastTimer)
  toastTimer = setTimeout(() => {
    toastMessage.value = ''
  }, 2100)
}

const review = computed(() => {
  const campaign = activeCampaign.value
  if (!campaign?.review) return { outcome: 'NO_COVERAGE', rule: 'No applicable rule', message: 'No approved rule covers this recommendation.', risk: 'Medium' }
  return ['MATCH', 'CONFLICT', 'NO_COVERAGE'].includes(campaign.review.outcome)
    ? campaign.review
    : { outcome: 'NO_COVERAGE', rule: 'No applicable rule', message: 'No approved rule covers this recommendation.', risk: 'Medium' }
})

const reviewToneClass = computed(() => {
  if (review.value.outcome === 'MATCH') return 'green'
  if (review.value.outcome === 'CONFLICT') return 'red'
  return 'amber'
})

const feedbackChoices = computed(() => {
  return review.value.outcome === 'MATCH'
    ? ['Looks right', 'Flag an issue']
    : review.value.outcome === 'CONFLICT'
      ? ['Accept adjustment', 'Challenge rule']
      : ['Request coverage', 'Not applicable']
})

async function loadDashboard() {
  try {
    const data = await fetchDashboard()
    campaigns.value = data.campaigns || campaigns.value
    overviewRows.value = data.overviewRows || overviewRows.value
    logRows.value = data.logRows || logRows.value
    knowledgeAssets.value = data.knowledgeAssets || knowledgeAssets.value
    knowledgeHealth.value = data.knowledgeHealth || knowledgeHealth.value
    toast('Dashboard data loaded')
  } catch (error) {
    toast('Using local mock data')
  }
}

onMounted(() => {
  const initialHash = window.location.hash.replace('#', '').trim()
  currentPage.value = normalizePage(initialHash || currentPage.value)
  syncHash(currentPage.value)
  loadDashboard()
  window.addEventListener('hashchange', () => {
    const nextPage = normalizePage(window.location.hash.replace('#', '').trim())
    currentPage.value = nextPage
  })
})
</script>

<template>
  <div class="app-shell">
    <SidebarNav :current-page="currentPage" @navigate="go" />

    <main class="main">
      <TopBar :title="pageTitle" :crumb="pageCrumb" />

      <div class="content">
        <OverviewPage v-if="currentPage === 'overview'" :overview-rows="overviewRows" :tone="tone" @go="go" />
        <BudgetPage v-else-if="currentPage === 'budget'" :campaigns="campaigns" :money="money" :pct="pct" :budget-state="budgetState" @open-optimizer="openOptimizer" />
        <CampaignsPage v-else-if="currentPage === 'campaigns'" :campaigns="campaigns" :money="money" :tone="tone" :budget-state="budgetState" @open-optimizer="openOptimizer" />
        <OptimizerPage
          v-else-if="currentPage === 'optimizer'"
          :active-campaign="activeCampaign"
          :current-campaign-id="currentCampaignId"
          :optimizer-ready="optimizerReady"
          :review="review"
          :review-tone-class="reviewToneClass"
          :feedback-choices="feedbackChoices"
          :feedback-note="feedbackNote"
          :note-open="noteOpen"
          :feedback-action="feedbackAction"
          :money="money"
          :pilot-state="pilotState"
          :pilot-controls="pilotControls"
          :pilot-duration="pilotDuration"
          :pilot-metric="pilotMetric"
          :pilot-share="pilotShare"
          @clear-campaign="clearCampaign"
          @run-optimizer="runOptimizer"
          @adopt="adopt"
          @toggle-note="toggleNote"
          @submit-feedback="submitFeedback"
          @start-pilot="startPilot"
          @update:feedback-note="(value) => (feedbackNote = value)"
          @update:pilot-state="(value) => (pilotState = value)"
          @update:pilot-controls="(value) => (pilotControls = value)"
          @update:pilot-duration="(value) => (pilotDuration = value)"
          @update:pilot-metric="(value) => (pilotMetric = value)"
          @update:pilot-share="(value) => (pilotShare = value)"
        />
        <LogPage v-else-if="currentPage === 'log'" :log-rows="logRows" :tone="tone" @export="() => toast('Export prepared')" />
        <KnowledgePage v-else-if="currentPage === 'knowledge'" :knowledge-assets="knowledgeAssets" :knowledge-health="knowledgeHealth" />
      </div>
    </main>

    <div class="toast" :class="{ show: toastMessage }">{{ toastMessage }}</div>
  </div>
</template>
