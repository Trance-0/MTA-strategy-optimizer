<script setup>
/**
 * The navigation rail: brand, grouped view buttons, and the settings module.
 *
 * The layout is the reference prototype's
 * (`external/UI_design/brandlens-vue/src/components/SidebarNav.vue`, by Rouxin
 * Jin): a navy column of stacked icon buttons with the active item filled. The
 * six items are this project's own six views rather than the prototype's, and
 * the foot carries the settings module the prototype has no counterpart for --
 * the source status, the reload control, and the links out of the app.
 */
import { PAGES, PAGE_GROUPS } from "../pages.js";

defineProps({
  current: { type: String, required: true },
  /** `{ label, colour, detail }` describing the active data source. */
  status: { type: Object, default: () => ({}) },
  loggingOn: { type: Boolean, default: false },
  docsHref: { type: String, required: true },
  repoHref: { type: String, required: true },
});

const emit = defineEmits(["go", "reload", "settings"]);
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
      <template v-for="group in PAGE_GROUPS" :key="group.label">
        <div class="nav-label">{{ group.label }}</div>
        <!--
          The label is hidden by CSS on a narrow screen, so the title and the
          accessible name are carried on the button itself rather than by the
          visible text alone.
        -->
        <button
          v-for="key in group.pages"
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
      </template>
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

      <button
        class="nav-item foot"
        aria-label="Settings"
        title="Settings"
        @click="emit('settings')"
      >
        <svg viewBox="0 0 24 24" fill="none" aria-hidden="true" v-html="PAGES.settings.icon" />
        <span>Settings</span>
      </button>
      <button
        class="nav-item foot"
        aria-label="Reload data"
        title="Reload data"
        @click="emit('reload')"
      >
        <svg viewBox="0 0 24 24" fill="none" aria-hidden="true" v-html="PAGES.reload.icon" />
        <span>Reload data</span>
      </button>

      <div class="rail-links">
        <a :href="docsHref" target="_blank" rel="noopener">Docs</a>
        <span>·</span>
        <a :href="repoHref" target="_blank" rel="noopener">Repo</a>
      </div>
    </div>
  </aside>
</template>
