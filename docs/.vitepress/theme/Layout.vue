<script setup lang="ts">
import { computed } from "vue";
import DefaultTheme from "vitepress/theme";
import { useData } from "vitepress";
import DrawioDiagram from "./components/DrawioDiagram.vue";

const { page } = useData();
const isEnHome = computed(() => page.value.relativePath === "en/index.md");
</script>

<template>
  <DefaultTheme.Layout>
    <template v-if="isEnHome" #home-hero-image>
      <DrawioDiagram
        base="/en/mta-optimizer-pipeline"
        alt="Campaign optimizer pipeline: New Campaign and Data Collection feed MTA Calculation, which drives a Campaign Strategy Recommendation refined against Performance Prediction, then published through A/B Testing, Operational Data Collection, and ROI Calculation and Reporting"
        source-label="Edit the pipeline diagram source"
      />
    </template>
  </DefaultTheme.Layout>
</template>
