<script setup>
defineProps({
  overviewRows: {
    type: Array,
    default: () => [],
  },
  tone: {
    type: Function,
    default: () => 'gray',
  },
})

const emit = defineEmits(['go'])
</script>

<template>
  <section class="page-grid two-up">
    <article class="card">
      <div class="card-head">
        <h2>Optimizer impact</h2>
        <span class="tag blue">Last 90 days</span>
      </div>
      <div class="card-body">
        <div class="result-pill">
          <div><small>Before</small><b>4.18x</b></div>
          <div class="arrow">→</div>
          <div><small>After</small><b>4.83x</b></div>
        </div>
        <div class="impact-grid">
          <div><b>+15.6%</b><span>ROAS lift</span></div>
          <div><b>+$1.9M</b><span>Incremental revenue</span></div>
          <div><b>12</b><span>Campaigns optimized</span></div>
        </div>
      </div>
    </article>

    <article class="card">
      <div class="card-head">
        <h2>Recent results</h2>
        <button class="btn link small" @click="emit('go', 'log')">View log</button>
      </div>
      <div class="card-body list-stack">
        <div v-for="item in overviewRows" :key="item[0]" class="activity-row">
          <div>
            <strong>{{ item[0] }}</strong>
            <span>{{ item[1] }}</span>
          </div>
          <span class="tag" :class="tone(item[2])">{{ item[2] }}</span>
        </div>
      </div>
    </article>
  </section>
</template>
