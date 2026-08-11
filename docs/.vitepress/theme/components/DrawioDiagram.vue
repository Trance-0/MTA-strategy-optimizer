<script setup lang="ts">
import { computed } from "vue";

const props = withDefaults(
  defineProps<{
    base: string;
    alt: string;
    sourceLabel?: string;
  }>(),
  { sourceLabel: "Edit the Draw.io source" },
);

const lightSvg = computed(() => `${props.base}.light.drawio.svg`);
const darkSvg = computed(() => `${props.base}.dark.drawio.svg`);
const drawioSource = computed(() => `${props.base}.drawio`);
</script>

<template>
  <figure class="drawio-diagram">
    <a class="drawio-diagram__render drawio-diagram__render--light" :href="lightSvg">
      <img :src="lightSvg" :alt="alt" />
    </a>
    <a class="drawio-diagram__render drawio-diagram__render--dark" :href="darkSvg">
      <img :src="darkSvg" :alt="alt" />
    </a>
    <figcaption>
      <a :href="drawioSource">{{ sourceLabel }}</a>
    </figcaption>
  </figure>
</template>
