/** Verify bounded Campaign presentation and model evidence with real Vue reactivity. */
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { computed, ref, watch, nextTick } from 'vue';
import * as common from '../src/lib/common.js';
import * as charts from '../src/lib/chartData.js';
import * as theme from '../src/theme.js';

// Evaluate the existing single-file view's script with a fixture resource store.
function view(name, snapshot, exposed) {
  const text = readFileSync(new URL(`../src/views/${name}.vue`, import.meta.url), 'utf8');
  const script = text.split('<script setup>')[1].split('</script>')[0]
    .replace(/import[\s\S]*?from\s+["'][^"']+["'];/g, '');
  const env = { ...common, ...charts, computed, ref, watch, nextTick, theme,
    defineProps: () => ({ section: 'performance' }), defineEmits: () => () => {},
    useDashboard: () => ({ data: ref(snapshot), historyWindow: ref({}), setHistoryWindow() {} }),
    useDiagnostics: () => ({ diagnosticsOn: ref(false) }), onMounted() {},
    useJobs: () => ({ stages: ref({}) }),
  };
  return new Function(...Object.keys(env), `${script}\nreturn { ${exposed} };`)(...Object.values(env));
}
const base = { adsDaily: [], entityBridge: [], pathReport: [], comparisonTouchpoints: [], comparisonSummary: [], recommendedAttribution: [], attributionResults: [] };

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
