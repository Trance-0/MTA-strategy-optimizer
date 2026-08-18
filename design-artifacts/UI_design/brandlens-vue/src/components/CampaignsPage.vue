<script setup>
defineProps({
  campaigns: {
    type: Array,
    default: () => [],
  },
  money: {
    type: Function,
    default: () => '$0K',
  },
  tone: {
    type: Function,
    default: () => 'gray',
  },
  budgetState: {
    type: Function,
    default: () => ['On track', 'green'],
  },
})

const emit = defineEmits(['openOptimizer'])
</script>

<template>
  <section class="page-grid">
    <article class="card">
      <div class="card-head">
        <h2>Campaign groups</h2>
        <select class="btn small">
          <option>All statuses</option>
          <option>Needs optimization</option>
        </select>
      </div>
      <div class="card-body stack">
        <div v-for="item in campaigns" :key="item.id" class="group-card">
          <div class="group-main">
            <div class="name"><strong>{{ item.name }}</strong><span>US · Amazon</span></div>
            <div><label>Budget</label><span class="value">{{ money(item.budget) }}</span></div>
            <div><label>Spend</label><span class="value">{{ money(item.spend) }}</span></div>
            <div><label>ROAS</label><span class="value">{{ item.roas.toFixed(2) }}x</span></div>
            <div><label>Status</label><span class="tag" :class="tone(item.status)">{{ item.status }}</span></div>
            <button class="btn primary small" @click="emit('openOptimizer', item.id)">Optimize</button>
          </div>
          <div class="ad-list">
            <div v-for="group in item.groups" :key="group[0]" class="ad-row">
              <div class="name"><strong>{{ group[0] }}</strong><span>Ad group</span></div>
              <div><label>Budget</label><span class="value">{{ money(group[1]) }}</span></div>
              <div><label>ROAS</label><span class="value">{{ group[3].toFixed(1) }}x</span></div>
              <div><label>Status</label><span class="tag" :class="budgetState(item)[1]">{{ budgetState(item)[0] }}</span></div>
            </div>
          </div>
        </div>
      </div>
    </article>
  </section>
</template>
