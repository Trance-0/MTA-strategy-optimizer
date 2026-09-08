<script setup>
/** Render formal assurance evidence without inventing aggregate scores. */
import { computed } from "vue";
import KeyValuePanel from "./KeyValuePanel.vue";
const props = defineProps({ report: { type: Object, default: () => ({}) }, run: { type: Object, default: () => ({}) } });
const hasReport = computed(() => Object.keys(props.report ?? {}).length > 0);
const rows = value => Object.entries(value ?? {}).map(([key, item]) => ({ label: key.replaceAll("_", " "), value: item == null ? "--" : typeof item === "object" ? JSON.stringify(item) : item }));
</script>
<template>
  <article class="card">
    <div class="card-head"><h2>Formal strategy evaluation</h2><span class="sub">Production assurance report</span></div>
    <div class="card-body">
      <p v-if="!hasReport" class="notice">Not run. Select a completed optimization run and evaluate it to publish this report.</p>
      <template v-else>
        <p v-if="run.id">Evaluation {{ run.id }} · Strategy run {{ run.strategyRunId ?? '--' }} · Process {{ run.state }}</p>
        <p>Contract checks describe validity. Baseline comparison uses observed evidence and does not guarantee future revenue. Missing optimal-allocation truth remains unavailable.</p>
        <KeyValuePanel title="Evaluation summary" :rows="rows(report.summary)" />
        <article v-for="(strategy, index) in (report.strategies ?? [])" :key="strategy.strategy_id ?? index" class="panel">
          <h3>{{ strategy.strategy_id ?? `Strategy ${index + 1}` }} · {{ strategy.allocation_type }}</h3>
          <KeyValuePanel title="Decision" :rows="rows(strategy.decision)" />
          <KeyValuePanel title="Contract and conservation" :rows="rows(strategy.contract)" />
          <KeyValuePanel title="Observed baseline comparison" :rows="rows(strategy.baseline_comparison)" />
          <KeyValuePanel title="Truth availability" :rows="rows(strategy.ground_truth)" />
        </article>
        <details v-for="(model, index) in (report.contributed_models ?? [])" :key="index"><summary>Contributed model {{ model.model_name ?? model.model_id ?? index + 1 }}</summary><KeyValuePanel title="Contributed model evidence" :rows="rows(model)" /></details>
        <details><summary>All report fields and skipped reasons</summary><pre class="workbench-json">{{ JSON.stringify(report, null, 2) }}</pre></details>
      </template>
    </div>
  </article>
</template>
