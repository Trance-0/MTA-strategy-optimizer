<script setup lang="ts">
import { computed } from "vue";
import { withBase } from "vitepress";

const props = withDefaults(
  defineProps<{
    base: string;
    alt: string;
    sourceLabel?: string;
  }>(),
  { sourceLabel: "Edit the Draw.io source" },
);

const assetPath = (suffix: string) => {
  const path = `${props.base}${suffix}`;
  return props.base.startsWith("/") ? withBase(path) : path;
};

const lightSvg = computed(() => assetPath(".light.drawio.svg"));
const darkSvg = computed(() => assetPath(".dark.drawio.svg"));
const drawioSource = computed(() => assetPath(".drawio"));
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
