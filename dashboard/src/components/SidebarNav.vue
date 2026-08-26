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
 *
 * Below the wide breakpoint the column becomes a horizontal bar, and each
 * multi-page group collapses into a labelled disclosure rather than spilling
 * its items into the row. See the `collapsed` computation below.
 */
import { computed, onMounted, onUnmounted, ref } from "vue";

import { PAGES, PAGE_GROUPS } from "../pages.js";

const props = defineProps({
  current: { type: String, required: true },
  /** `{ label, colour, detail }` describing the active data source. */
  status: { type: Object, default: () => ({}) },
  loggingOn: { type: Boolean, default: false },
  docsHref: { type: String, required: true },
  repoHref: { type: String, required: true },
});

const emit = defineEmits(["go", "reload", "settings"]);

/*
 * The bar layout's breakpoint, stated here as well as in `style.css` because
 * collapsing a group is a change of behaviour, not only of appearance: the
 * items move behind a disclosure that has to open and close, and CSS alone
 * cannot hold that state. `matchMedia` is what keeps the two in step -- the
 * one width below is the same width the stylesheet switches at, and
 * `tests/dashboard.test.js` asserts they have not drifted apart.
 */
const BAR_BREAKPOINT = "(max-width: 1024px)";

/** True while the rail is drawn as a bar, so groups collapse. */
const collapsed = ref(false);
/** The label of the open group, or `""`. One at a time: a bar has one row. */
const openGroup = ref("");
const nav = ref(null);

let query = null;

/**
 * A single-page group is not worth a disclosure -- opening a list to choose
 * the only thing in it is friction, so that item stays on the bar itself.
 */
function isCollapsible(group) {
  return collapsed.value && group.pages.length > 1;
}

function panelId(group) {
  return `nav-group-${group.label.toLowerCase()}`;
}

/** The group holding the current page, so a closed disclosure still says so. */
const currentGroup = computed(
  () => PAGE_GROUPS.find((group) => group.pages.includes(props.current))?.label ?? "",
);

function toggle(label) {
  openGroup.value = openGroup.value === label ? "" : label;
}

function choose(key) {
  openGroup.value = "";
  emit("go", key);
}

function onViewportChange(event) {
  collapsed.value = event.matches;
  // Widening re-expands every group, so a disclosure left open cannot survive
  // as a stray panel over a column that is already showing its items.
  if (!event.matches) openGroup.value = "";
}

function onDocumentPointerDown(event) {
  if (!openGroup.value) return;
  if (!nav.value?.contains(event.target)) openGroup.value = "";
}

function onDocumentKeydown(event) {
  if (event.key === "Escape") openGroup.value = "";
}

onMounted(() => {
  query = window.matchMedia(BAR_BREAKPOINT);
  collapsed.value = query.matches;
  query.addEventListener("change", onViewportChange);
  document.addEventListener("pointerdown", onDocumentPointerDown);
  document.addEventListener("keydown", onDocumentKeydown);
});

onUnmounted(() => {
  query?.removeEventListener("change", onViewportChange);
  document.removeEventListener("pointerdown", onDocumentPointerDown);
  document.removeEventListener("keydown", onDocumentKeydown);
});
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

    <nav ref="nav" class="nav" aria-label="Views">
      <div
        v-for="group in PAGE_GROUPS"
        :key="group.label"
        class="nav-group"
        :class="{ collapsible: isCollapsible(group), open: openGroup === group.label }"
      >
        <!--
          The heading is a static label in the column and the disclosure's
          control in the bar. It is only a button when it does something, so a
          reader who tabs through the column is not offered a control that has
          no effect.
        -->
        <div v-if="!isCollapsible(group)" class="nav-label">{{ group.label }}</div>
        <button
          v-else
          class="nav-group-trigger"
          :class="{ current: currentGroup === group.label }"
          :aria-expanded="openGroup === group.label"
          :aria-controls="panelId(group)"
          @click="toggle(group.label)"
        >
          <span>{{ group.label }}</span>
          <svg class="nav-chevron" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path
              d="M7 10l5 5 5-5"
              stroke="currentColor"
              stroke-width="1.8"
              stroke-linecap="round"
              stroke-linejoin="round"
            />
          </svg>
        </button>

        <!--
          The label is hidden by CSS on a narrow screen, so the title and the
          accessible name are carried on the button itself rather than by the
          visible text alone.
        -->
        <div
          :id="panelId(group)"
          class="nav-group-items"
          :hidden="isCollapsible(group) && openGroup !== group.label"
        >
          <button
            v-for="key in group.pages"
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
        </div>
      </div>
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
