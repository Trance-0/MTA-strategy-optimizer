<script setup>
/**
 * Native Willow Sakura Gross Merchandise Value forecast widgets.
 *
 * The contributed model remains an isolated demonstration: this component
 * runs its exported weights in the browser and never writes a strategy or
 * feeds a value into the production optimizer.
 */
import { reactive, ref, watch } from "vue";

import willowModel from "../../../docs/en/strategy-evaluation/asin-gmv-nn-v1/results/demo_mlp_extended27.json";
import { predictWillowGmv, STRUCTURE_KEYS } from "../lib/willowGmvModel.js";
import * as theme from "../theme.js";

const DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
const BUDGET_FIELDS = [
  ["budget_sp", "Sponsored Products budget"],
  ["budget_sb", "Sponsored Brands budget"],
  ["budget_sd", "Sponsored Display budget"],
  ["budget_dsp", "Amazon Demand-Side Platform budget"],
];
const STRUCTURE_LABELS = {
  share_cost_top_of_search: "Top-of-search cost share",
  share_cost_product_page: "Product-page cost share",
  share_cost_sb_headline: "Sponsored Brands headline cost share",
  share_cost_sp_product_ad: "Sponsored Products product-ad cost share",
  share_cost_dsp_video: "Demand-Side Platform video cost share",
  share_cost_dsp_image: "Demand-Side Platform image cost share",
  share_cost_dsp_unspecified_creative: "Unspecified creative cost share",
  n_placement_types: "Placement-type count",
};

const form = reactive({
  budget_sp: willowModel.defaults.budget_sp,
  budget_sb: willowModel.defaults.budget_sb,
  budget_sd: willowModel.defaults.budget_sd,
  budget_dsp: willowModel.defaults.budget_dsp,
  country: willowModel.defaults.country,
  dow: willowModel.defaults.dow,
  is_weekend: Boolean(willowModel.defaults.is_weekend),
  struct: { ...willowModel.defaults.struct },
});
const prediction = ref(null);
const comparison = ref(null);
const error = ref("");

function refreshPrediction() {
  try {
    prediction.value = predictWillowGmv(willowModel, form);
    comparison.value = predictWillowGmv(willowModel, form, 1.1);
    error.value = "";
  } catch (cause) {
    prediction.value = null;
    comparison.value = null;
    error.value = cause instanceof Error ? cause.message : String(cause);
  }
}

function money(value) {
  return theme.money(value, "$");
}

function metricPercent(value) {
  return `${(Number(value) * 100).toFixed(1)}%`;
}

function totalBudget() {
  return BUDGET_FIELDS.reduce((sum, [key]) => sum + Math.max(0, Number(form[key]) || 0), 0);
}

watch(form, refreshPrediction, { deep: true, immediate: true });
</script>

<template>
  <article class="card willow-forecast">
    <div class="card-head">
      <div>
        <h2>Willow Sakura attributed revenue forecast</h2>
        <span class="sub">SK-II Extended-27 multilayer perceptron · contributed demonstration</span>
      </div>
      <span class="tag blue">Live network</span>
    </div>

    <div class="card-body willow-forecast-body">
      <!--
        These are model inputs a reader sets, not filters over a table, so they
        are option rows: the input named on the left, the number on the right.
        The action bar is below the rows it belongs to rather than opposite the
        heading, so the button starts on the same edge as everything else.
      -->
      <section class="willow-inputs" aria-label="Willow Sakura forecast inputs">
        <div class="setting-group">
          <header>
            <div>
              <h3>Budget and calendar</h3>
              <p class="caption">Every edit reruns the browser model.</p>
            </div>
          </header>

          <label v-for="([key, label]) in BUDGET_FIELDS" :key="key" class="setting-row">
            <span class="setting-label">
              {{ label }}
              <small>Daily spend on this ad product, in dollars.</small>
            </span>
            <span class="setting-control">
              <input
                :id="`willow-${key}`"
                v-model.number="form[key]"
                type="number"
                min="0"
                step="10"
              />
            </span>
          </label>

          <label class="setting-row">
            <span class="setting-label">
              Marketplace
              <small>The country the model predicts for.</small>
            </span>
            <span class="setting-control">
              <select id="willow-country" v-model="form.country">
                <option v-for="country in willowModel.country_classes" :key="country">
                  {{ country }}
                </option>
              </select>
            </span>
          </label>
          <label class="setting-row">
            <span class="setting-label">Day of week</span>
            <span class="setting-control">
              <select id="willow-day" v-model.number="form.dow">
                <option v-for="(day, index) in DAY_NAMES" :key="day" :value="index">
                  {{ day }}
                </option>
              </select>
            </span>
          </label>
          <label class="setting-row">
            <span class="setting-label">
              Weekend
              <small>Set separately from the day, because the model reads both.</small>
            </span>
            <span class="setting-control">
              <select id="willow-weekend" v-model="form.is_weekend">
                <option :value="false">No</option>
                <option :value="true">Yes</option>
              </select>
            </span>
          </label>

          <div class="setting-block rec-actions">
            <button class="btn primary" type="button" @click="refreshPrediction">
              Run prediction
            </button>
          </div>
        </div>

        <div class="setting-group">
          <header>
            <div>
              <h3>Placement and creative structure</h3>
              <p class="caption">Editable cost mix used by the contributed model.</p>
            </div>
          </header>
          <label v-for="key in STRUCTURE_KEYS" :key="key" class="setting-row">
            <span class="setting-label">
              {{ STRUCTURE_LABELS[key] }}
              <small v-if="key !== 'n_placement_types'">Share of total cost, from 0 to 1.</small>
              <small v-else>How many distinct placement types the spend covers.</small>
            </span>
            <span class="setting-control">
              <input
                :id="`willow-${key}`"
                v-model.number="form.struct[key]"
                type="number"
                min="0"
                :max="key === 'n_placement_types' ? 10 : 1"
                :step="key === 'n_placement_types' ? 0.1 : 0.01"
              />
            </span>
          </label>
        </div>
      </section>

      <aside class="willow-prediction" aria-live="polite">
        <h3>Prediction</h3>
        <div v-if="error" class="notice bad">{{ error }}</div>
        <template v-else-if="prediction && comparison">
          <div class="willow-primary-result">
            <span>Predicted attributed revenue</span>
            <b>{{ money(prediction.revenue) }}</b>
          </div>
          <div class="willow-metrics">
            <div>
              <b>{{ money(totalBudget()) }}</b>
              <span>Total daily budget</span>
            </div>
            <div>
              <b>{{ money(comparison.revenue) }}</b>
              <span>If all budgets increase 10%</span>
            </div>
            <div>
              <b>{{ money(comparison.revenue - prediction.revenue) }}</b>
              <span>Predicted revenue difference</span>
            </div>
          </div>
          <div class="willow-model-metrics">
            <span>Held-out mean absolute percentage error</span>
            <b>{{ metricPercent(willowModel.test_metrics['MAPE_gmv>=10']) }}</b>
            <span>Held-out R-squared</span>
            <b>{{ Number(willowModel.test_metrics.R2).toFixed(2) }}</b>
            <span>Evaluation rows</span>
            <b>{{ willowModel.test_metrics.n }}</b>
          </div>
        </template>
        <p class="caption">
          Label: Amazon-attributed sales, not organic Gross Merchandise Value.
          This contributed browser forecast is not a realized uplift and does
          not change the production optimizer's recommendation.
        </p>
      </aside>
    </div>
  </article>
</template>
