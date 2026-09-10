<script>
/** Shared operational log formatting and browser clipboard support. */
export function normalizeLogRecord(record) {
  return {
    at: String(record.at ?? record.when ?? ""),
    text: String(record.text ?? record.message ?? ""),
    level: String(record.level ?? ""),
    source: String(record.source ?? record.stream ?? ""),
    duration: record.durationMs == null ? "" : `duration_ms=${record.durationMs}`,
  };
}

export function logCopyText(records, context = [], command = "", droppedLines = 0) {
  return [
    ...context,
    command ? `$ ${command}` : "",
    droppedLines ? `${droppedLines} earlier log line(s) dropped; retained output follows.` : "",
    ...records.map((record) => {
      const line = normalizeLogRecord(record);
      return [line.at, line.level, line.source, line.text, line.duration].filter(Boolean).join(" ");
    }),
  ].filter(Boolean).join("\n");
}

export async function copyLogText(text) {
  // Clipboard access can reject even when present (permissions or insecure
  // deployment). Try the selectable-text fallback in both cases.
  try {
    if (globalThis.navigator?.clipboard?.writeText) {
      await globalThis.navigator.clipboard.writeText(text);
      return;
    }
  } catch { /* Continue with the same text and the browser's legacy copy. */ }
  const previousFocus = document.activeElement;
  const field = document.createElement("textarea");
  try {
    field.value = text;
    field.setAttribute("readonly", "");
    field.style.position = "fixed";
    field.style.opacity = "0";
    document.body.appendChild(field);
    field.select();
    if (!document.execCommand("copy")) throw new Error("Browser copy was refused.");
  } finally {
    field.remove();
    previousFocus?.focus({ preventScroll: true });
  }
}
</script>

<script setup>
/** Render caller-filtered logs, copy complete context, and follow active tails. */
import { computed, nextTick, ref, watch } from "vue";

const props = defineProps({
  records: { type: Array, default: () => [] },
  context: { type: Array, default: () => [] },
  command: { type: String, default: "" },
  droppedLines: { type: Number, default: 0 },
  running: { type: Boolean, default: false },
  copyLabel: { type: String, default: "Copy log" },
  emptyText: { type: String, default: "No log records yet." },
});

const viewport = ref(null);
const following = ref(true);
const copying = ref(false);
const feedback = ref("");
const copyFailed = ref(false);
const rows = computed(() => props.records.map(normalizeLogRecord));
const content = computed(() => logCopyText(props.records, props.context, props.command, props.droppedLines));

function trackScroll() {
  const element = viewport.value;
  if (element) following.value = element.scrollHeight - element.scrollTop - element.clientHeight < 32;
}

// Observe the records themselves: a bounded buffer replaces old lines without
// changing its length. Scroll only this container, never the whole page.
watch(() => props.records, async () => {
  if (!props.running || !following.value) return;
  await nextTick();
  if (props.running && following.value && viewport.value) {
    viewport.value.scrollTop = viewport.value.scrollHeight;
  }
}, { deep: true });

async function copy() {
  copying.value = true;
  feedback.value = "";
  try {
    await copyLogText(content.value);
    copyFailed.value = false;
    feedback.value = "Log copied.";
  } catch (error) {
    copyFailed.value = true;
    feedback.value = `Could not copy log: ${error.message}`;
  } finally {
    copying.value = false;
  }
}
</script>

<template>
  <section class="log-viewer" aria-label="Log output">
    <div class="rec-actions">
      <button class="btn small" :disabled="copying || !content" @click="copy">{{ copyLabel }}</button>
      <span role="status" class="caption" :class="{ 'copy-failed': copyFailed }">{{ feedback }}</span>
    </div>
    <p v-if="droppedLines" class="caption">{{ droppedLines.toLocaleString() }} earlier log line(s) dropped; retained output follows.</p>
    <pre v-if="command" class="schema-command"><code>{{ command }}</code></pre>
    <div ref="viewport" class="log-stream" role="log" :aria-live="running ? 'polite' : 'off'" @scroll="trackScroll">
      <p v-if="!rows.length" class="caption">{{ emptyText }}</p>
      <div v-for="(line, index) in rows" :key="index" class="log-row" :class="`log-${line.source}`">
        <span class="log-when">{{ line.at }}</span>
        <span v-if="line.level" class="log-level" :class="line.level.toLowerCase()">{{ line.level }}</span>
        <span v-if="line.source" class="log-source">{{ line.source }}</span>
        <span class="log-message">{{ line.text }}<template v-if="line.duration"> · {{ line.duration }}</template></span>
      </div>
    </div>
  </section>
</template>
