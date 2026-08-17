<script setup>
/**
 * The governing reliability verdict, stated at the top of a view.
 *
 * The verdict sits beside the numbers it governs rather than in a footnote,
 * because an unreliable share must not be read as a fact. The status word is
 * always present, so the colour is a second encoding rather than the only one.
 */
import { computed } from "vue";

import { statusTone } from "../lib/common.js";

const props = defineProps({
  status: { type: String, default: "UNKNOWN" },
  reason: { type: String, default: "" },
});

const tone = computed(() => statusTone(props.status));
const label = computed(() => String(props.status ?? "UNKNOWN").toUpperCase());
</script>

<template>
  <div class="reliability" :class="tone">
    <span class="tag" :class="tone">{{ label }}</span>
    <span class="reliability-reason"><slot>{{ reason }}</slot></span>
  </div>
</template>
