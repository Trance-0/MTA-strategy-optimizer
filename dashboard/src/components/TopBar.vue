<script setup>
/**
 * The page header: the view's title, its breadcrumb, and the report window.
 *
 * The layout is the reference prototype's TopBar (by Rouxin Jin). The tags on
 * the right carry the deployment, the report window, and the marketplace,
 * which are read from the data rather than fixed, so the header cannot claim a
 * window the charts beneath it do not cover.
 *
 * The deployment tag leads, because which deployment this is governs how every
 * other number on the page may be used.
 */
defineProps({
  title: { type: String, required: true },
  crumb: { type: String, default: "" },
  window: { type: String, default: "" },
  marketplace: { type: String, default: "" },
  /** How this deployment names itself, e.g. "Published build". */
  deploymentLabel: { type: String, default: "" },
  /** Whether data operations are available here. */
  writable: { type: Boolean, default: false },
});
</script>

<template>
  <header class="topbar">
    <div>
      <h1>{{ title }}</h1>
      <div class="crumb">{{ crumb }}</div>
    </div>
    <div class="top-right">
      <span
        v-if="deploymentLabel"
        class="tag"
        :class="writable ? 'blue' : 'green'"
        :title="writable
          ? 'Connected to a database; data operations are available.'
          : 'Reading committed files; data operations are unavailable.'"
      >
        {{ deploymentLabel }}
      </span>
      <span v-if="window" class="tag blue">{{ window }}</span>
      <span v-if="marketplace" class="tag gray">{{ marketplace }}</span>
    </div>
  </header>
</template>
