<script setup>
/**
 * The navigation rail: eight flat destinations and a status-only foot.
 *
 * In the wide layout the rail is one navy column of stacked buttons with no
 * grouping of any kind -- every destination is visible and one click away.
 *
 * Below the bar breakpoint (`1024px`, in `style.css`) the column has nowhere
 * to put eight buttons, so the whole list collapses behind one menu button
 * that opens the same flat list as a dropdown. One menu, not one per section:
 * the reader opens it, sees every destination, and picks one.
 *
 * Only the open/closed state lives here. Which pages exist, and their order,
 * is registered once in `pages.js`.
 */
import { ref, watch } from "vue";
import { PAGES, PAGE_KEYS } from "../pages.js";

const props = defineProps({
  current: { type: String, required: true },
  status: { type: Object, default: () => ({}) },
  loggingOn: { type: Boolean, default: false },
  docsHref: { type: String, required: true },
  repoHref: { type: String, required: true },
});

const emit = defineEmits(["go"]);

/** Whether the narrow layout's single menu is open. Ignored when wide. */
const menuOpen = ref(false);

function choose(key) {
  menuOpen.value = false;
  emit("go", key);
}

/** Navigating away closes the menu; leaving it open would cover the new page. */
watch(() => props.current, () => { menuOpen.value = false; });

function onKeydown(event) {
  if (event.key === "Escape" && menuOpen.value) menuOpen.value = false;
}
</script>

<template>
  <aside class="sidebar" @keydown="onKeydown">
    <div class="brand">
      <div>
        <div class="logo">M</div>
        <b>AI-MTA</b>
        <span>MARKETING ROI</span>
      </div>
    </div>

    <!--
      Rendered only in the narrow layout, where the stylesheet reveals it and
      hides the list behind it. In the wide column the list is the navigation
      and this button does not exist.
    -->
    <button
      class="nav-menu-trigger"
      :class="{ open: menuOpen }"
      aria-controls="rail-destinations"
      :aria-expanded="menuOpen"
      @click="menuOpen = !menuOpen"
    >
      <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <path d="M4 7h16M4 12h16M4 17h16" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" />
      </svg>
      <span>{{ PAGES[current].title }}</span>
      <svg class="nav-chevron" viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <path d="M6 9l6 6 6-6" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
      </svg>
    </button>

    <nav
      id="rail-destinations"
      class="nav"
      :class="{ open: menuOpen }"
      aria-label="Views"
    >
      <button
        v-for="key in PAGE_KEYS"
        :key="key"
        class="nav-item"
        :class="{ active: current === key }"
        :aria-current="current === key ? 'page' : undefined"
        :aria-label="PAGES[key].title"
        :title="PAGES[key].title"
        @click="choose(key)"
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
      <div class="rail-links">
        <a :href="docsHref" target="_blank" rel="noopener">Docs</a>
        <span>·</span>
        <a :href="repoHref" target="_blank" rel="noopener">Repo</a>
      </div>
    </div>
  </aside>
</template>
