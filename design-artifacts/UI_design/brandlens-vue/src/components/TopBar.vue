<script setup>
defineProps({
  title: {
    type: String,
    default: 'Command Center',
  },
  crumb: {
    type: String,
    default: 'BrandLens / Overview',
  },
})
</script>

<template>
  <header class="topbar">
    <div>
      <h1>{{ title }}</h1>
      <div class="crumb">{{ crumb }}</div>
    </div>
    <div class="top-right">
      <span class="tag blue">FY25–26</span>
      <span class="tag gray">Amazon · US</span>
    </div>
  </header>
</template>
