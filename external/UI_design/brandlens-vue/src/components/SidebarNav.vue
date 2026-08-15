<script setup>
defineProps({
  currentPage: {
    type: String,
    default: 'overview',
  },
})

const emit = defineEmits(['navigate'])

const items = [
  { key: 'overview', label: 'Command Center', icon: 'grid' },
  { key: 'budget', label: 'Budget Manager', icon: 'budget' },
  { key: 'campaigns', label: 'Campaigns', icon: 'campaigns' },
  { key: 'optimizer', label: 'Campaign Optimizer', icon: 'optimizer' },
  { key: 'log', label: 'Optimization Log', icon: 'log' },
  { key: 'knowledge', label: 'Knowledge Base', icon: 'knowledge' },
]
</script>

<template>
  <aside class="sidebar">
    <div class="brand">
      <div class="logo">B</div>
      <div>
        <b>BrandLens</b>
      </div>
    </div>

    <nav class="nav">
      <div class="nav-label">OVERVIEW</div>
      <button
        v-for="item in items"
        :key="item.key"
        class="nav-item"
        :class="{ active: currentPage === item.key }"
        @click="emit('navigate', item.key)"
      >
        <svg v-if="item.icon === 'grid'" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path d="M4 4h6v6H4V4zm10 0h6v10h-6V4zM4 14h6v6H4v-6zm10 4h6v2h-6v-2z" stroke="currentColor" stroke-width="1.6"/>
        </svg>
        <svg v-else-if="item.icon === 'budget'" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path d="M4 6h16v12H4V6zm0 4h16M8 15h4" stroke="currentColor" stroke-width="1.6"/>
        </svg>
        <svg v-else-if="item.icon === 'campaigns'" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path d="M4 12l15-7v14L4 13v-1zm4 3v4l4 1" stroke="currentColor" stroke-width="1.6"/>
        </svg>
        <svg v-else-if="item.icon === 'optimizer'" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path d="M5 17l4-5 3 2 6-8M15 6h3v3" stroke="currentColor" stroke-width="1.7"/>
        </svg>
        <svg v-else-if="item.icon === 'log'" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path d="M5 5h14v14H5V5zm3 4h8m-8 3h8m-8 3h5" stroke="currentColor" stroke-width="1.6"/>
        </svg>
        <svg v-else viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path d="M4 5h7v14H4V5zm9 0h7v14h-7V5zM7 9h1m8 0h1" stroke="currentColor" stroke-width="1.6"/>
        </svg>
        <span>{{ item.label }}</span>
      </button>
    </nav>

    <div class="side-foot">
      <b>Alex Morgan</b>
      <span>Marketing</span>
    </div>
  </aside>
</template>
