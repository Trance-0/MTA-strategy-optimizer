/** Verify bounded Campaign presentation and model evidence with real Vue reactivity. */
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { computed, ref, watch, nextTick } from 'vue';
import * as common from '../src/lib/common.js';
import * as charts from '../src/lib/chartData.js';
import * as theme from '../src/theme.js';

// Evaluate the existing single-file view's script with a fixture resource store.
function view(name, snapshot, exposed, overrides = {}) {
  const text = readFileSync(new URL(`../src/views/${name}.vue`, import.meta.url), 'utf8');
  const script = text.split('<script setup>')[1].split('</script>')[0]
    .replace(/import[\s\S]*?from\s+["'][^"']+["'];/g, '');
  const env = { ...common, ...charts, computed, ref, watch, nextTick, theme,
    window: { location: { search: "" } }, URLSearchParams, onBeforeUnmount() {},
    defineProps: () => ({ section: 'performance' }), defineEmits: () => () => {},
    useDashboard: () => ({ data: ref(snapshot), selectedDatasetId: ref(""), historyWindow: ref({}), setHistoryWindow() {} }),
    useDiagnostics: () => ({ diagnosticsOn: ref(false) }), onMounted() {},
    useJobs: () => ({ stages: ref({}) }), ...overrides,
  };
  return new Function(...Object.keys(env), `${script}\nreturn { ${exposed} };`)(...Object.values(env));
}
const base = { simulationResearch: { campaigns: [{ campaign_id: "A" }] }, adsDaily: [], entityBridge: [], pathReport: [], comparisonTouchpoints: [], comparisonSummary: [], recommendedAttribution: [], attributionResults: [] };

test('ranking folds 100,000 categories into seven plus Other without losing observations', () => {
  const rows = Array.from({ length: 100000 }, (_, i) => ({ touchpoint: `T${i}`, cost: i, sales: i * 2 }));
  const v = view('Campaigns', { ...base, adsDaily: rows }, 'rankCategories, aggregateCategories');
  const ranked = v.rankCategories(v.aggregateCategories(rows, 'touchpoint', ['cost', 'sales']), 'cost');
  assert.equal(ranked.length, 8);
  assert.equal(ranked[7].key, 'Other');
  assert.equal(ranked[7].members.length, 99993);
  assert.equal(ranked.reduce((sum, r) => sum + r.cost, 0), 4999950000);
  assert.equal(v.aggregateCategories([{ touchpoint: 'A', cost: null }], 'touchpoint', ['cost'])[0].cost, null);
});

test('rank drill-down retains filters and Other exposes every omitted row', async () => {
  const adsDaily = Array.from({ length: 12 }, (_, i) => ({ report_date: '2026-01-01', ad_product: 'P', touchpoint: `T${i}`, cost: i, sales: i }));
  const v = view('Campaigns', { ...base, adsDaily }, 'product, touchpointRanking, selectRanking, rankingDetailRows, backToRanking, resetFilters, rankingSelection');
  v.product.value = 'P';
  await v.selectRanking(v.touchpointRanking.value.at(-1));
  assert.equal(v.rankingDetailRows.value.length, 5);
  assert.equal(v.product.value, 'P');
  await v.backToRanking();
  assert.equal(v.rankingSelection.value, null);
  assert.equal(v.product.value, 'P');
  v.resetFilters();
  assert.equal(v.product.value, '');
});

test('incomplete fitted response is unavailable; complete fit preserves formula and observations cap', () => {
  const response_observations = Array.from({ length: 100000 }, (_, i) => ({ campaign_id: 'A', configured_budget: i, total_revenue: i * 2 }));
  const campaignStrategy = { response_models: { campaign_models: { A: { campaign_id: 'A' } } }, response_observations };
  const v = view('CampaignOptimizer', { ...base, campaignStrategy }, 'expectedRevenue, responsePlotObservations, responseObservations, comparisonColumns');
  assert.equal(v.expectedRevenue({}, 10), null);
  assert.equal(v.expectedRevenue({ spend_response: { capacity: 0, scale: 1 }, revenue_response: { baseline: 0, alpha: 0, kappa: 1 } }, 10), 0);
  assert.equal(v.responsePlotObservations.value.length, 500);
  assert.equal(v.responseObservations.value.length, 100000);
  assert.equal(v.comparisonColumns.find(c => c.key === 'gap_pp').format, 'number');
});

test('density exports preserve occupied cell counts, and EUR headers retain currency', () => {
  const history = Array.from({ length: 100000 }, (_, i) => ({ currency: 'EUR', configured_budget: i % 80, actual_spend: i % 70 }));
  history.push({ configured_budget: null, actual_spend: 0 });
  const v = view('Campaigns', { ...base, simulationResearch: { history } }, 'densityValues, historyDensity, moneyColumns, currencyCode');
  assert.equal(v.historyDensity.value.total, 100000);
  assert.equal(v.densityValues.value.reduce((total, row) => total + row.observations, 0), 100000);
  assert.ok(v.densityValues.value.length <= 1600);
  assert.equal(v.currencyCode.value, 'EUR');
  const columns = v.moneyColumns([{ key: 'cost', label: 'Spend', format: 'money' }]);
  assert.equal(columns[0].label, 'Spend (EUR)');
  assert.equal(charts.rowsToCsv(columns, [{ cost: null }, { cost: 0 }]), 'Spend (EUR)\r\n\r\n0\r\n');
});

test('Back restores invoking focus after detail focus and grouped ratios use totals', async () => {
  const adsDaily = [
    { report_date: '2026-01-01', touchpoint: 'A', cost: 10, sales: 100 },
    { report_date: '2026-01-02', touchpoint: 'A', cost: 90, sales: 90 },
  ];
  const v = view('Campaigns', { ...base, adsDaily }, 'grain, trendValues, selectRanking, backToRanking, detailHeading, touchpointRanking');
  v.grain.value = 'month';
  assert.equal(v.trendValues.value[0].roas, 1.9);
  const focus = [];
  v.detailHeading.value = { focus: () => focus.push('detail') };
  await v.selectRanking(v.touchpointRanking.value[0], { currentTarget: { focus: () => focus.push('row') } });
  await v.backToRanking();
  assert.deepEqual(focus, ['detail', 'row']);
});

test('path plots bound high-cardinality rows and filter every path surface together', () => {
  const pathReport = Array.from({ length: 100000 }, (_, i) => ({ path: `A${i} > B${i} > C${i} > D${i}`, path_length: i + 1, users: 10, converted_users: 2, revenue: 4 }));
  const v = view('Campaigns', { ...base, pathReport }, 'lengthTraces, journeyTraces, paths, pathSearch');
  assert.equal(v.lengthTraces.value[0].x.length, 8);
  assert.equal(v.lengthTraces.value[0].x.reduce((sum, value) => sum + value, 0), 1000000);
  assert.ok(v.journeyTraces.value[0].node.label.length <= 24);
  assert.ok(v.journeyTraces.value[0].node.label.some(label => /multiple touches/i.test(label)));
  v.pathSearch.value = 'A99999 >';
  assert.equal(v.paths.value.length, 1);
  assert.equal(v.lengthTraces.value[0].x[0], 10);
});

test('EntityTable export uses all searched and sorted rows before paging', () => {
  const text = readFileSync(new URL('../src/components/EntityTable.vue', import.meta.url), 'utf8');
  const script = text.split('<script setup>')[1].split('</script>')[0].replace(/import[\s\S]*?from\s+["'][^"']+["'];/g, '');
  const env = { ...common, computed, ref, watch, defineExpose() {}, defineEmits: () => () => {},
    defineProps: () => ({ columns: [{ key: 'name', label: 'Name' }, { key: 'cost', label: 'Spend', format: 'number' }],
      rows: Array.from({ length: 25 }, (_, i) => ({ name: i < 20 ? 'match' : 'omit', cost: i })), rowKey: row => row.cost }),
  };
  const table = new Function(...Object.keys(env), `${script}\nreturn { search, sort, sorted, pageRows };`)(...Object.values(env));
  table.search.value = 'match';
  table.sort.value = { key: 'cost', direction: 'desc' };
  assert.equal(table.sorted.value.length, 20);
  assert.equal(table.pageRows.value.length, 10);
  assert.equal(table.sorted.value[0].cost, 19);
  assert.equal(table.sorted.value.at(-1).cost, 0);
  assert.match(text, /downloadCsv\(columns, sorted,/);
});


test('similarity grouping distinguishes mean and strict thresholds and rejects invalid values', () => {
  const v = view('Campaigns', { ...base, simulationResearch: { history: [
    { campaign_id: 'B', provider: 'AMAZON_ADS', ad_product: 'Other', configured_budget: 100 },
  ] } }, 'similarityProvider, similarityAdProduct, similarityThreshold, clusteringMethod, similarityMatches');
  v.similarityProvider.value = 'AMAZON_ADS';
  v.similarityAdProduct.value = 'Search';
  v.similarityThreshold.value = 0.5;
  assert.equal(v.similarityMatches.value.length, 1);
  v.clusteringMethod.value = 'strict';
  assert.equal(v.similarityMatches.value.length, 0);
  v.similarityThreshold.value = -1;
  assert.equal(v.similarityMatches.value.length, 0);
  v.similarityThreshold.value = '';
  assert.equal(v.similarityMatches.value.length, 0);
});


test('campaign navigation encodes identity and automatic preview ignores late results after source change', async () => {
  const { campaignOptimizerHref } = await import('../src/pages.js');
  const href = campaignOptimizerHref('A&B', 'US', 'ds_one');
  assert.equal(new URLSearchParams(href.split('#')[0]).get('campaignId'), 'A&B');
  assert.ok(href.endsWith('#/optimizer/optimization'));
  const selected = ref('ds_one');
  let resolve;
  let submitted;
  const v = view('CampaignOptimizer', base, 'preview, previewError, previewBusy', {
    window: { location: { search: '?campaignId=A&marketplace=US&campaignSource=ds_one' } },
    defineProps: () => ({ section: 'optimization' }),
    useDashboard: () => ({ data: ref(base), selectedDatasetId: selected }),
    optimizeCampaign: body => { submitted = body; return new Promise(done => { resolve = done; }); },
  });
  assert.deepEqual(submitted, { campaignId: 'A', marketplace: 'US', historyMode: 'full', similarityThreshold: 0, datasetId: 'ds_one' });
  selected.value = 'ds_two';
  await nextTick();
  resolve({ campaign_id: 'A' });
  await Promise.resolve();
  assert.equal(v.preview.value, null);
  assert.equal(v.previewError.value, '');
  assert.equal(v.previewBusy.value, false);
});


test('a zero budget query matches observed zero but never absent budget', () => {
  const v = view('Campaigns', { ...base, simulationResearch: { history: [
    { campaign_id: 'zero', configured_budget: 0 }, { campaign_id: 'missing', configured_budget: null },
  ] } }, 'similarityBudget, similarityThreshold, similarityMatches');
  v.similarityBudget.value = '0'; v.similarityThreshold.value = 1;
  assert.deepEqual(v.similarityMatches.value.map(row => row.campaign_id), ['zero']);
});


test('history-source changes recompute and invalidate older previews', async () => {
  const calls = [];
  const v = view('CampaignOptimizer', base, 'historyMode, preview', {
    window: { location: { search: '?campaignId=A&marketplace=CA&campaignSource=legacy' } },
    defineProps: () => ({ section: 'optimization' }),
    optimizeCampaign: body => new Promise(resolve => calls.push({ body, resolve })),
  });
  assert.equal(calls[0].body.historyMode, 'full');
  v.historyMode.value = 'campaign';
  await nextTick();
  assert.equal(calls[1].body.historyMode, 'campaign');
  calls[1].resolve({ observation_count: 2 }); await Promise.resolve();
  calls[0].resolve({ observation_count: 100 }); await Promise.resolve();
  assert.equal(v.preview.value.observation_count, 2);
});

test('transferred model evidence retains donor campaign identity', () => {
  const campaignStrategy = { response_models: { campaign_models: { B: {
    campaign_id: 'B', diagnostics: { support: 'POOLED_TRANSFER', pooled_campaign_ids: ['A'] },
  } } }, response_observations: [ { campaign_id: 'A', configured_budget: 100 }, { campaign_id: 'unrelated' } ] };
  const v = view('CampaignOptimizer', { ...base, campaignStrategy }, 'responseObservations');
  assert.deepEqual(v.responseObservations.value.map(row => row.campaign_id), ['A']);
});


test('optimizer inputs validate, submit and invalidate in-flight results', async () => {
  const calls = [];
  const v = view('CampaignOptimizer', base, 'initialBudget, similarityThreshold, inputError, computeCampaign, preview', {
    window: { location: { search: '?campaignId=A&marketplace=US&campaignSource=legacy' } },
    defineProps: () => ({ section: 'optimization' }),
    optimizeCampaign: body => new Promise(resolve => calls.push({ body, resolve })),
  });
  v.initialBudget.value = 150; v.similarityThreshold.value = 0.8;
  calls[0].resolve({ observation_count: 999 }); await Promise.resolve();
  assert.equal(v.preview.value, null);
  const pending = v.computeCampaign();
  assert.equal(calls[1].body.initialBudget, 150);
  assert.equal(calls[1].body.similarityThreshold, 0.8);
  calls[1].resolve({ observation_count: 2 }); await pending;
  v.similarityThreshold.value = 2;
  assert.equal(v.preview.value, null);
  assert.match(v.inputError.value, /between 0 and 1/);
  await v.computeCampaign(); assert.equal(calls.length, 2);
  v.similarityThreshold.value = 0; v.initialBudget.value = -1;
  assert.match(v.inputError.value, /greater than zero/);
});


test('Campaign selector matches on typing and changing target ignores old results', async () => {
  const calls = [];
  const snapshot = { ...base, simulationResearch: { campaigns: [
    { campaign_id: 'A', campaign_name: 'Alpha', provider: 'AMAZON_ADS' },
    { campaign_id: 'B', campaign_name: 'Bravo', ad_product: 'Search' },
  ] } };
  const v = view('CampaignOptimizer', snapshot, 'selectedCampaign, campaignSearch, matchingCampaigns, campaignSearchError, chooseCampaign, preview, initialBudget', {
    window: { location: { search: '?campaignId=A&marketplace=US&campaignSource=legacy' } },
    defineProps: () => ({ section: 'optimization' }),
    optimizeCampaign: body => new Promise(resolve => calls.push({ body, resolve })),
  });
  v.campaignSearch.value = 'bRa';
  assert.deepEqual(v.matchingCampaigns.value.map(row => row.campaign_id), ['B']);
  assert.equal(v.selectedCampaign.value, 'A');
  v.initialBudget.value = 150;
  v.selectedCampaign.value = 'B'; v.chooseCampaign(); await nextTick();
  assert.equal(v.initialBudget.value, '');
  assert.equal(calls[1].body.campaignId, 'B');
  calls[1].resolve({ campaign_id: 'B' }); await Promise.resolve();
  calls[0].resolve({ campaign_id: 'A' }); await Promise.resolve();
  assert.equal(v.preview.value.campaign_id, 'B');
  v.campaignSearch.value = 'missing'; assert.equal(v.matchingCampaigns.value.length, 0);
  assert.match(v.campaignSearchError.value, /No Campaign matches/);
  v.campaignSearch.value = 'alpha'; assert.equal(v.campaignSearchError.value, '');
});


test('country-style Campaign autocomplete filters without hiding settings or submitting partial text', async () => {
  const calls = [];
  const snapshot = { ...base, simulationResearch: { campaigns: [
    { campaign_id: 'US', campaign_name: 'United States' },
    { campaign_id: 'FR', campaign_name: 'France' },
  ] } };
  const v = view('CampaignOptimizer', snapshot, 'onCampaignInput, matchingCampaigns, selectedCampaign, campaignSearchError, scopedPreview, initialBudget', {
    window: { location: { search: '?marketplace=US' } },
    defineProps: () => ({ section: 'optimization' }),
    optimizeCampaign: body => { calls.push(body); return Promise.resolve({}); },
  });
  v.initialBudget.value = 150;
  v.onCampaignInput({ target: { value: 'uni' } }); await nextTick();
  assert.deepEqual(v.matchingCampaigns.value.map(row => row.campaign_id), ['US']);
  assert.equal(v.scopedPreview.value, true);
  assert.equal(calls.length, 0);
  v.onCampaignInput({ target: { value: 'unixxxx' } }); await nextTick();
  assert.equal(v.matchingCampaigns.value.length, 0);
  assert.match(v.campaignSearchError.value, /No Campaign matches/);
  assert.equal(v.scopedPreview.value, true);
  assert.equal(v.initialBudget.value, 150);
  assert.equal(calls.length, 0);
  v.onCampaignInput({ target: { value: 'US' } }); await nextTick();
  assert.equal(v.selectedCampaign.value, 'US');
  assert.equal(calls[0].campaignId, 'US');
});

test('historical recommendation exposes a plotted budget marker', () => {
  const v = view('CampaignOptimizer', {
    ...base,
    campaignStrategy: { historical_recommendation: {
      recommended_budget: 520, mean_observed_revenue: 3100,
    } },
  }, 'historicalBaselineTraces');
  assert.equal(v.historicalBaselineTraces.value[0].x[0], 520);
  assert.equal(v.historicalBaselineTraces.value[0].y[0], 3100);
});
