<script setup>
/** The flat navigation rail and its Settings-only foot module. */
import { PAGES, PAGE_KEYS } from "../pages.js";

defineProps({
  current: { type: String, required: true },
  status: { type: Object, default: () => ({}) },
  loggingOn: { type: Boolean, default: false },
  docsHref: { type: String, required: true },
  repoHref: { type: String, required: true },
});

const emit = defineEmits(["go", "settings"]);
</script>

<template>
  <aside class="sidebar">
    <div class="brand">
      <div>
        <div class="logo">M</div>
        <b>AI-MTA</b>
        <span>MARKETING ROI</span>
      </div>
    </div>
    <nav class="nav" aria-label="Views">
      <button
        v-for="key in PAGE_KEYS"
        :key="key"
        class="nav-item"
        :class="{ active: current === key }"
        :aria-current="current === key ? 'page' : undefined"
        :aria-label="PAGES[key].title"
        :title="PAGES[key].title"
        @click="emit('go', key)"
      >
        <svg viewBox="0 0 24 24" fill="none" aria-hidden="true" v-html="PAGES[key].icon" />
        <span>{{ PAGES[key].title }}</span>
      </button>
    </nav>
    <div class="side-foot">
      <div class="rail-status">
        <span class="rail-dot" :style="{ background: status.colour || '#9db7e8' }"></span>
        <span class="rail-status-label">{{ status.label || "Loading" }}</span>
      </div>
      <div class="rail-status-detail" :title="status.detail">{{ status.detail }}</div>
      <div class="rail-log" :class="{ on: loggingOn }">
        LOGGING {{ loggingOn ? "ON" : "OFF" }}
      </div>
      <button class="nav-item foot" aria-label="Settings" title="Settings" @click="emit('settings')">
        <svg viewBox="0 0 24 24" fill="none" aria-hidden="true" v-html="PAGES.settings.icon" />
        <span>Settings</span>
      </button>
      <div class="rail-links">
        <a :href="docsHref" target="_blank" rel="noopener">Docs</a>
        <span>·</span>
        <a :href="repoHref" target="_blank" rel="noopener">Repo</a>
      </div>
    </div>
  </aside>
</template>
