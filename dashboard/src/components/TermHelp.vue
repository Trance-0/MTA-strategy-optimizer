<script setup>
/** Keyboard- and pointer-accessible definition popover for one declared term. */
import { computed, ref } from "vue";

import { IS_STATIC } from "../api/client.js";
import { DOCS_URL } from "../pages.js";

const props = defineProps({
  term: { type: Object, required: true },
});

const open = ref(false);
const identifier = `term-help-${Math.random().toString(36).slice(2)}`;
const href = computed(() =>
  IS_STATIC ? `./docs${props.term.href}` : `${DOCS_URL}${props.term.href}`,
);

function onFocusOut(event) {
  if (!event.currentTarget.contains(event.relatedTarget)) open.value = false;
}
</script>

<template>
  <span
    class="term-help"
    @mouseenter="open = true"
    @mouseleave="open = false"
    @focusin="open = true"
    @focusout="onFocusOut"
    @keydown.esc="open = false"
  >
    <button
      type="button"
      class="term-help-button"
      :aria-expanded="open"
      :aria-describedby="identifier"
      aria-label="Explain this term"
      @click="open = !open"
    >?</button>
    <span v-show="open" :id="identifier" class="term-help-popover" role="tooltip">
      {{ term.definition }}
      <a :href="href" target="_blank" rel="noopener">Read the specification</a>
    </span>
  </span>
</template>
