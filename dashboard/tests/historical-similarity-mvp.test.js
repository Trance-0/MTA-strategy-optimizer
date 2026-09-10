/** Exercise the actual Campaigns setup script against reactive historical fixtures. */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import { computed, ref } from 'vue';
import * as common from '../src/lib/common.js';
import * as theme from '../src/theme.js';

const source = readFileSync(new URL('../src/views/Campaigns.vue', import.meta.url), 'utf8');
const script = source.split('<script setup>')[1].split('</script>')[0]
  .replace(/import[\s\S]*?from\s+["'][^"']+["'];/g, '');
const names = ['similaritySearch', 'similarityVisibleSections', 'similarityHasPendingChanges', 'similarityResetSection', 'similarityDraftFilters', 'similarityAppliedFilters', 'similarityBudget',
  'similarityThreshold', 'similarityCampaign', 'similarityMatches', 'similarityAllMatches',
  'similarityMissingFields', 'similarityError', 'similarityClearSection', 'similaritySelectAll',
  'similarityResetFilters', 'similarityApplyFilters', 'similarityFilterSections'];
function setup(history = []) {
  const data = ref({ simulationResearch: { history, campaigns: [] } });
  const bindings = { computed, ref, ...common, theme,
    defineProps: () => ({ section: 'history' }), defineEmits: () => () => {},
    useDashboard: () => ({ data, errorFor: () => null }),
    useDiagnostics: () => ({ diagnosticsOn: ref(false) }), window: { setTimeout: (fn) => fn() } };
  return { data, ...new Function(...Object.keys(bindings), `${script}\nreturn {${names.join(',')}};`)(...Object.values(bindings)) };
}
const row = (overrides = {}) => ({ run_id: 'r', campaign_id: 'c', marketplace: 'UK',
  advertiser_id: 'a', product_id: 'p', budget_level: 1, report_date: '2026-09-04',
  provider: 'A', ad_product: 'SP', configured_budget: 100, actual_spend: 80, ...overrides });

test('real setup reset clears budget, subject and checkbox selections', () => {
  const s = setup([row()]); s.similarityBudget.value = '1000'; s.similarityThreshold.value = .9;
  s.similarityCampaign.value = 'c'; s.similaritySelectAll('provider'); s.similarityApplyFilters();
  s.similarityResetFilters();
  assert.equal(s.similarityBudget.value, ''); assert.equal(s.similarityThreshold.value, .6);
  assert.equal(s.similarityCampaign.value, '');
  assert.deepEqual(s.similarityAppliedFilters.value, {provider: [], product_id: [], ad_product: []});
  assert.deepEqual(s.similarityDraftFilters.value, s.similarityAppliedFilters.value);
});

test('draft waits for apply; same group OR, cross group AND; ad product retained', () => {
  const s = setup([row(), row({campaign_id:'d',provider:'B'}), row({campaign_id:'e',provider:'C'}), row({campaign_id:'f',ad_product:'SD'})]);
  s.similarityThreshold.value = 0;
  assert.equal(s.similarityMatches.value.length, 4);
  s.similarityDraftFilters.value.provider = ['A','B']; s.similarityDraftFilters.value.ad_product = ['SP'];
  assert.equal(s.similarityMatches.value.length, 4);
  s.similarityApplyFilters();
  assert.deepEqual(s.similarityMatches.value.map(x=>x.campaign_id).sort(), ['c','d']);
  assert.ok(s.similarityMatches.value.every(x=>x.similarity_score === 1 && x.ad_product === 'SP'));
  s.similarityClearSection('provider'); s.similarityApplyFilters();
  assert.equal(s.similarityMatches.value.length, 3);
  s.similaritySelectAll('provider'); assert.deepEqual(s.similarityDraftFilters.value.provider, ['A','B','C']);
});

test('strict identities remain separate and incomplete records are excluded', () => {
  const s = setup([row(), row({marketplace:'US'}), row({advertiser_id:'b'}), row({budget_level:2}), row({advertiser_id:null})]);
  s.similarityThreshold.value = 0;
  assert.equal(s.similarityMatches.value.length, 4);
  assert.equal(new Set(s.similarityMatches.value.map(x=>x.identity)).size, 4);
  assert.ok(!s.similarityMissingFields.value.some(x=>x.startsWith('advertiser_id')));
});

test('cap preserves actual total and ordering is deterministic', () => {
  const rows = Array.from({length:25}, (_,i)=>row({product_id:`p${String(i).padStart(2,'0')}`}));
  const s=setup(rows.slice().reverse()); s.similarityThreshold.value=0;
  assert.equal(s.similarityAllMatches.value.length,25); assert.equal(s.similarityMatches.value.length,20);
  assert.equal(s.similarityMatches.value[0].product_id,'p00');
});

test('empty and malformed histories are safe and expose appropriate state', () => {
  const s=setup(); assert.equal(s.similarityFilterSections.value.length,3);
  assert.equal(s.similarityMatches.value.length,0); assert.equal(s.similarityError.value,false);
  s.data.value.simulationResearch.history={broken:true};
  assert.equal(s.similarityError.value,true); assert.equal(s.similarityMatches.value.length,0);
});

test('budget zero is scored and threshold filters actual results', () => {
  const s=setup([row({configured_budget:0}),row({campaign_id:'d',configured_budget:100})]);
  s.similarityBudget.value='0'; assert.equal(s.similarityMatches.value.length,1);
  assert.equal(s.similarityMatches.value[0].campaign_id,'c');
});

test('search preserves selections and select all adds only visible options', () => {
  const s=setup([row(),row({provider:'Beta'}),row({provider:'Gamma'})]);
  s.similarityDraftFilters.value.provider=['A'];
  s.similaritySearch.value.provider=' beTA ';
  assert.deepEqual(s.similarityVisibleSections.value[0].visibleValues,['Beta']);
  s.similaritySelectAll('provider');
  assert.deepEqual(s.similarityDraftFilters.value.provider,['A','Beta']);
  assert.equal(s.similarityHasPendingChanges.value,true);
  s.similarityApplyFilters(); assert.equal(s.similarityHasPendingChanges.value,false);
  s.similarityDraftFilters.value.provider=['Beta','A'];
  assert.equal(s.similarityHasPendingChanges.value,false);
  s.similaritySearch.value.provider='not found';
  assert.equal(s.similarityVisibleSections.value[0].visibleValues.length,0);
  s.similarityResetSection('provider');
  assert.equal(s.similaritySearch.value.provider,'');
  assert.deepEqual(s.similarityDraftFilters.value.provider,[]);
});

test('report fallback uses original performance fields and preserves report grain', () => {
  const s=setup();
  s.data.value.entityBridge=[{campaign_id:'c',sku_id:'SKU1',marketplace:'US',advertiser_id:'adv',
    report_start_date:'2026-01-01',report_end_date:'2026-03-31',touchpoint:'SPONSORED_PRODUCTS:SEARCH:TOP:UNSPECIFIED:CLICK',
    cost:23,reported_sales:70,assisted_revenue:900},
    {campaign_id:'d',sku_id:'SKU2',marketplace:'US',advertiser_id:'adv',report_start_date:'2026-01-01',report_end_date:'2026-03-31',
    touchpoint:'AMAZON_DSP:AUDIO:UNSPECIFIED:UNSPECIFIED:IMPRESSION',cost:10,reported_sales:0}];
  assert.equal(s.similarityMatches.value.length,2);
  const first=s.similarityMatches.value.find(x=>x.campaign_id==='c');
  assert.equal(first.budget,null); assert.equal(first.spend,23); assert.equal(first.revenue,70);
  assert.equal(first.similarity_score,null); assert.equal(first.historical_period,'2026-01-01 → 2026-03-31');
  s.similarityBudget.value='1000';
  assert.equal(s.similarityMatches.value.length,2);
  s.similarityDraftFilters.value.product_id=['SKU2']; s.similarityApplyFilters();
  assert.equal(s.similarityMatches.value.length,1); assert.equal(s.similarityMatches.value[0].revenue,0);
  assert.equal(s.similarityMatches.value[0].campaign_id,'d');
  s.similarityResetFilters(); s.similarityCampaign.value='c';
  assert.ok(s.similarityMatches.value.every(x=>x.campaign_id!=='c'));
});

test('malformed report rows show an error instead of a misleading empty result', () => {
  const s=setup(); s.data.value.entityBridge=[null];
  assert.equal(s.similarityError.value,true);
  assert.equal(s.similarityMatches.value.length,0);
});
