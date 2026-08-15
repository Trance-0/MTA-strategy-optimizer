<script setup>
/**
 * The page header: the view's title, its breadcrumb, and the report window.
 *
 * The layout is the reference prototype's TopBar (by Rouxin Jin). The two tags
 * on the right carry the report window and the marketplace, which are read
 * from the data rather than fixed, so the header cannot claim a window the
 * charts beneath it do not cover.
 */
defineProps({
  title: { type: String, required: true },
  crumb: { type: String, default: "" },
  window: { type: String, default: "" },
  marketplace: { type: String, default: "" },
});
</script>

<template>
  <header class="topbar">
    <div>
      <h1>{{ title }}</h1>
      <div class="crumb">{{ crumb }}</div>
    </div>
    <div class="top-right">
      <span v-if="window" class="tag blue">{{ window }}</span>
      <span v-if="marketplace" class="tag gray">{{ marketplace }}</span>
    </div>
  </header>
</template>
