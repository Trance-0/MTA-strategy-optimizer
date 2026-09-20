<script setup>
/**
 * The Settings row that opens the guided tutorial.
 *
 * Only the launch control lives here. The tutorial itself is rendered by
 * `App.vue` through `GuidedTour.vue`, because a tour owned by this page would
 * be unmounted the moment its first step navigated away from Settings.
 */
import { TUTORIAL_SECTIONS, useTutorial } from "../lib/useTutorial.js";

const { open, completed } = useTutorial();
</script>

<template>
  <div class="setting-row">
    <div class="setting-label">
      <span>Guided tutorial</span>
      <small>
        Walks you through setting up a data source, running the attribution
        model, and running the optimization model, on the real pages. Choose a
        section to start; it only navigates and explains, and never runs a job
        or changes your data or settings.
      </small>
    </div>
    <div class="setting-control">
      <button class="btn primary" @click="open">
        {{ completed.length ? "Open tutorial" : "Start tutorial" }}
      </button>
    </div>
  </div>
  <p class="setting-block caption">
    {{ completed.length }} of {{ TUTORIAL_SECTIONS.length }} sections completed.
  </p>
</template>
