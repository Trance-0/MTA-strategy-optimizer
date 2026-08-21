<script setup>
/**
 * A modal that names what is about to be removed, before it is removed.
 *
 * Deletion is the one action in the dashboard with no undo, so it is the one
 * action that asks. The dialog names the affected records rather than
 * reporting a count alone: "Delete 12 rows?" is not something a reader can
 * check, and a batch selection made across several pages is exactly the case
 * where a reader cannot see what they picked.
 *
 * The list is capped, because a thousand-row selection would otherwise produce
 * a thousand-line dialog; the remainder is stated rather than dropped
 * silently.
 */
import { computed } from "vue";

const props = defineProps({
  open: { type: Boolean, default: false },
  title: { type: String, default: "Confirm" },
  /** The identifiers about to be affected, for the reader to check. */
  items: { type: Array, default: () => [] },
  confirmLabel: { type: String, default: "Delete" },
  busy: { type: Boolean, default: false },
  /** Set when the action failed, so the dialog stays open and says why. */
  error: { type: String, default: "" },
});

const emit = defineEmits(["confirm", "cancel"]);

const LISTED = 12;

const shown = computed(() => props.items.slice(0, LISTED));
const remainder = computed(() => Math.max(0, props.items.length - LISTED));
</script>

<template>
  <div v-if="open" class="modal-backdrop" @click.self="emit('cancel')">
    <section
      class="modal confirm-modal"
      role="alertdialog"
      aria-modal="true"
      :aria-label="title"
    >
      <div class="modal-head">
        <h2>{{ title }}</h2>
      </div>

      <div class="modal-body">
        <p>
          This archives
          {{ items.length === 1 ? "this planned change" : `these ${items.length} planned changes` }}.
          Reported performance is never removed.
        </p>

        <ul v-if="shown.length" class="confirm-list">
          <li v-for="item in shown" :key="item"><code>{{ item }}</code></li>
        </ul>
        <p v-if="remainder" class="caption">
          and {{ remainder.toLocaleString() }} more.
        </p>

        <div v-if="error" class="notice bad">{{ error }}</div>

        <div class="rec-actions">
          <button class="btn" :disabled="busy" @click="emit('cancel')">
            Cancel
          </button>
          <button class="btn danger" :disabled="busy" @click="emit('confirm')">
            {{ busy ? "Working…" : confirmLabel }}
          </button>
        </div>
      </div>
    </section>
  </div>
</template>
