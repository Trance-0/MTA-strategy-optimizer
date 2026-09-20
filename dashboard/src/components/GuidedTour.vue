<script setup>
/**
 * The guided tutorial's overlay: a blocking spotlight mask, the step card
 * beside it, the section picker, and the progress bar above them.
 *
 * Rendered once by `App.vue`, outside every routed view, because the tutorial
 * navigates between pages and a component owned by one page would be
 * unmounted by its own first step. All content and state live in
 * `lib/useTutorial.js`; this file is the presentation and the input handling.
 *
 * The mask is four opaque panels drawn around the highlighted element rather
 * than one translucent sheet with a transparent hole. Two things follow from
 * that, and both are the point: the element keeps its own colours, focus ring
 * and hover states because nothing is drawn over it, and the panels
 * themselves swallow clicks, so during an `action` step the only clickable
 * thing on the page is the control the step is teaching. The reader advances
 * by doing the real thing -- which runs the real operation -- rather than by
 * pressing a Next button beside a description of it.
 *
 * The panels and the card animate between positions, so moving from one
 * control to the next reads as the spotlight travelling rather than the page
 * flickering, and the card flips to whichever side of the highlight has room
 * so it never covers what it points at.
 */
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import {
  DEMO_NOTICE,
  READINESS,
  TUTORIAL_SECTIONS,
  useTutorial,
} from "../lib/useTutorial.js";

const {
  active,
  section,
  step,
  stepIndex,
  stepCount,
  completed,
  startSection,
  next,
  previous,
  backToSections,
  quit,
} = useTutorial();

/** The highlighted element's viewport rectangle, or null when none is found. */
const spot = ref(null);
/** True once the step's target has been located, so the card can say so. */
const found = ref(false);
/** Set when an action step's control cannot be found or is disabled. */
const blocked = ref("");

let findTimer = null;
let readyTimer = null;
let frame = 0;
let watched = null;

const PADDING = 8;

function clearTimers() {
  clearTimeout(findTimer);
  clearInterval(readyTimer);
  cancelAnimationFrame(frame);
}

const isAction = computed(() => step.value?.kind === "action");
const isInput = computed(() => step.value?.kind === "input");
/** An input step is satisfied by the page reaching a state, not by a click. */
const awaitsSetup = computed(() => isInput.value && Boolean(step.value?.until));

/**
 * What to tell a reader whose action control is missing or disabled.
 *
 * Every action step that can plausibly be blocked carries its own remedy, so
 * the overlay never falls back on naming the problem and offering nothing,
 * which strands the reader mid-lesson.
 */
const recoveryHint = computed(
  () =>
    step.value?.recover?.hint ??
    "This control is not ready yet. Step back to set up what it needs, or skip this step.",
);

/** How many steps back the fields this action depends on live, if any. */
const recoverSteps = computed(() => step.value?.recover?.steps ?? 0);

function targetElement() {
  const name = step.value?.target;
  return name ? document.querySelector(`[data-tour="${name}"]`) : null;
}

/** Step back to the setup this action needs, then let it lead here again. */
function recover() {
  for (let index = 0; index < Math.max(recoverSteps.value, 1); index += 1) {
    previous();
  }
}

/**
 * The reader clicked the control the step was teaching, so the step is done.
 *
 * The listener runs in the capture phase and does not prevent the event, so
 * the application's own handler still fires: the click that advances the
 * tutorial is the same click that starts the run.
 */
function onTargetClick() {
  if (!isAction.value) return;
  // Let the application handle the click first, then move on.
  setTimeout(() => next(), 260);
}

function bindTarget(element) {
  unbindTarget();
  if (!element || !isAction.value) return;
  watched = element;
  element.addEventListener("click", onTargetClick, { capture: true });
}

/**
 * Watch for an input step's setup to become valid, and move on when it does.
 *
 * Polling rather than binding to the inputs: the controls a step asks the
 * reader to set differ per step, several of them are native elements inside
 * components this overlay must not reach into, and a check every quarter
 * second is imperceptible next to typing.
 */
function watchReadiness() {
  clearInterval(readyTimer);
  if (!awaitsSetup.value) return;
  const check = READINESS[step.value.until];
  if (typeof check !== "function") return;
  readyTimer = setInterval(() => {
    let ready = false;
    try {
      ready = check();
    } catch {
      // A control that has not rendered yet is simply not ready.
      ready = false;
    }
    if (!ready) return;
    clearInterval(readyTimer);
    setTimeout(() => next(), 420);
  }, 250);
}

/**
 * Re-check a disabled action control, and clear the remedy once it enables.
 *
 * The reader may fix the prerequisite without leaving the step -- typing a
 * marketplace, say -- and the card must stop telling them it is blocked the
 * moment it is not.
 */
function watchEnablement(element) {
  clearInterval(readyTimer);
  if (!isAction.value || !element?.disabled) return;
  readyTimer = setInterval(() => {
    const current = targetElement();
    if (!current) return;
    if (!current.disabled) {
      clearInterval(readyTimer);
      blocked.value = "";
      bindTarget(current);
      measure(current);
    }
  }, 250);
}

function unbindTarget() {
  if (watched) watched.removeEventListener("click", onTargetClick, { capture: true });
  watched = null;
}

/**
 * Locate the current step's target, scroll it into view, and watch it.
 *
 * A step runs immediately after a route change, so the element it names may
 * not exist yet; this retries briefly. An action step whose control never
 * appears, or which is disabled, reports itself blocked so the card can offer
 * a way past instead of trapping the reader.
 */
function locate(attempt = 0) {
  clearTimers();
  if (!active.value || !section.value) {
    spot.value = null;
    return;
  }
  if (!step.value?.target) {
    spot.value = null;
    found.value = false;
    blocked.value = "";
    return;
  }
  const element = targetElement();
  if (!element) {
    if (attempt < 25) {
      findTimer = setTimeout(() => locate(attempt + 1), 120);
      return;
    }
    spot.value = null;
    found.value = false;
    blocked.value = isAction.value ? recoveryHint.value : "";
    return;
  }
  found.value = true;
  // A disabled control is not a dead end: the step says what is missing and
  // offers the way to supply it, because naming the fault alone teaches
  // nothing and strands the reader mid-lesson.
  blocked.value = isAction.value && element.disabled ? recoveryHint.value : "";
  bindTarget(element);
  // A disabled action may become usable while the reader reads the remedy.
  watchEnablement(element);
  const box = element.getBoundingClientRect();
  if (box.top < 96 || box.bottom > window.innerHeight - 40) {
    element.scrollIntoView({ behavior: "smooth", block: "center" });
    // Measure after the smooth scroll settles, not while it is running.
    findTimer = setTimeout(() => measure(element), 420);
    return;
  }
  measure(element);
}

function measure(element) {
  const box = element.getBoundingClientRect();
  spot.value = {
    top: Math.max(box.top - PADDING, 0),
    left: Math.max(box.left - PADDING, 0),
    width: box.width + PADDING * 2,
    height: box.height + PADDING * 2,
  };
}

/** Keep the cutout on its element while the page scrolls or resizes. */
function track() {
  cancelAnimationFrame(frame);
  frame = requestAnimationFrame(() => {
    const element = targetElement();
    if (element) measure(element);
  });
}

/** The four blocking panels that surround the highlight. */
const panels = computed(() => {
  const area = spot.value;
  if (!area) return null;
  return {
    top: { top: 0, left: 0, width: "100%", height: `${area.top}px` },
    bottom: { top: `${area.top + area.height}px`, left: 0, width: "100%", bottom: 0 },
    left: { top: `${area.top}px`, left: 0, width: `${area.left}px`, height: `${area.height}px` },
    right: {
      top: `${area.top}px`,
      left: `${area.left + area.width}px`,
      right: 0,
      height: `${area.height}px`,
    },
  };
});

const ring = computed(() =>
  spot.value
    ? {
        top: `${spot.value.top}px`,
        left: `${spot.value.left}px`,
        width: `${spot.value.width}px`,
        height: `${spot.value.height}px`,
      }
    : null,
);

/**
 * Place the card on whichever side of the highlight has room for it.
 *
 * The card is measured rather than assumed: a long step beside a tall control
 * needs to know its own height before it can decide which side fits.
 */
const cardHeight = ref(220);
const cardBox = ref(null);

const cardStyle = computed(() => {
  const area = spot.value;
  if (!area) return null;
  const width = Math.min(440, window.innerWidth - 32);
  const gap = 14;
  const below = window.innerHeight - (area.top + area.height);
  const above = area.top;
  const left = Math.min(
    Math.max(area.left + area.width / 2 - width / 2, 16),
    Math.max(window.innerWidth - width - 16, 16),
  );
  // Prefer below, then above, and fall back to pinning inside the viewport.
  if (below >= cardHeight.value + gap + 16) {
    return { top: `${area.top + area.height + gap}px`, left: `${left}px`, width: `${width}px` };
  }
  if (above >= cardHeight.value + gap + 16) {
    return { top: `${area.top - cardHeight.value - gap}px`, left: `${left}px`, width: `${width}px` };
  }
  const top = Math.min(
    Math.max(area.top + area.height + gap, 96),
    Math.max(window.innerHeight - cardHeight.value - 16, 96),
  );
  return { top: `${top}px`, left: `${left}px`, width: `${width}px` };
});

function measureCard() {
  if (cardBox.value) cardHeight.value = cardBox.value.offsetHeight || 220;
}

function onKeydown(event) {
  if (!active.value) return;
  if (event.key === "Escape") quit();
  else if (!section.value) return;
  else if (event.key === "ArrowLeft") previous();
  // An action or input step is completed by doing it, so the arrow key does
  // not skip past the work the step exists to teach.
  else if (event.key === "ArrowRight" && !isAction.value && !isInput.value) next();
}

// A new step may also be a new route, so wait for the render it triggers.
watch([step, active, section], () => {
  unbindTarget();
  if (!active.value) {
    clearTimers();
    spot.value = null;
    return;
  }
  found.value = false;
  blocked.value = "";
  nextTick(() => {
    measureCard();
    locate();
    watchReadiness();
  });
});

watch([spot, step], () => nextTick(measureCard));

onMounted(() => {
  document.addEventListener("keydown", onKeydown);
  window.addEventListener("scroll", track, true);
  window.addEventListener("resize", track);
});

onBeforeUnmount(() => {
  clearTimers();
  unbindTarget();
  document.removeEventListener("keydown", onKeydown);
  window.removeEventListener("scroll", track, true);
  window.removeEventListener("resize", track);
});
</script>

<template>
  <div v-if="active" class="tutorial-root">
    <!--
      With a target, four panels surround it: they dim the page, and because
      they are real elements they also swallow clicks, so during an action
      step the highlighted control is the only thing the reader can press.
    -->
    <template v-if="panels">
      <div class="tutorial-mask" :style="panels.top"></div>
      <div class="tutorial-mask" :style="panels.bottom"></div>
      <div class="tutorial-mask" :style="panels.left"></div>
      <div class="tutorial-mask" :style="panels.right"></div>
      <div class="tutorial-ring" :class="{ action: isAction }" :style="ring" aria-hidden="true"></div>
    </template>
    <div v-else class="tutorial-mask tutorial-mask-full"></div>

    <div class="tutorial-bar" role="dialog" aria-modal="false" aria-label="Guided tutorial">
      <div class="tutorial-bar-head">
        <span class="tutorial-eyebrow">Guided tutorial</span>
        <b v-if="section">{{ section.title }}</b>
        <b v-else>Choose what to learn</b>
        <span v-if="section" class="tutorial-count">
          Step {{ stepIndex + 1 }} of {{ stepCount }}
        </span>
        <div class="tutorial-bar-actions">
          <button v-if="section" class="btn small" @click="backToSections">All sections</button>
          <button class="btn small" @click="quit">Quit tutorial</button>
        </div>
      </div>
      <div v-if="section" class="tutorial-progress" aria-hidden="true">
        <span
          v-for="(entry, position) in section.steps"
          :key="entry.title"
          :class="{ done: position <= stepIndex }"
        ></span>
      </div>
    </div>

    <div v-if="!section" class="tutorial-panel tutorial-picker">
      <p class="caption">
        Each section walks the real pages and has you press the real controls,
        including the runs that reach the server. Nothing is simulated, and
        nothing is pressed for you.
      </p>
      <button
        v-for="entry in TUTORIAL_SECTIONS"
        :key="entry.key"
        class="tutorial-section"
        @click="startSection(entry.key)"
      >
        <span class="tutorial-section-head">
          <b>{{ entry.title }}</b>
          <span v-if="completed.includes(entry.key)" class="tutorial-done">Completed</span>
          <span class="tutorial-minutes">{{ entry.steps.length }} steps</span>
        </span>
        <small>{{ entry.summary }}</small>
      </button>
    </div>

    <div
      v-else
      ref="cardBox"
      class="tutorial-panel tutorial-step"
      :class="{ anchored: Boolean(cardStyle) }"
      :style="cardStyle"
    >
      <span v-if="isAction || isInput" class="tutorial-kind">Your turn</span>
      <h3>{{ step.title }}</h3>
      <p>{{ step.body }}</p>
      <p class="tutorial-hint" :class="{ act: isAction || isInput }">{{ step.hint }}</p>
      <p v-if="blocked" class="tutorial-blocked" role="status">{{ blocked }}</p>
      <p v-if="step.demo" class="tutorial-demo">{{ DEMO_NOTICE }}</p>
      <div class="rec-actions">
        <button class="btn" :disabled="stepIndex === 0" @click="previous">Back</button>
        <!--
          A blocked action offers the way to unblock itself rather than only a
          way out, so the reader learns what the control needed.
        -->
        <button
          v-if="isAction && blocked && recoverSteps"
          class="btn"
          @click="recover"
        >
          Set that up first
        </button>
        <button
          v-if="isAction && step.optional && blocked"
          class="btn"
          @click="next"
        >
          Skip this step
        </button>
        <!--
          Neither an action nor an input step carries Continue: each is
          completed by the reader doing the thing it teaches.
        -->
        <button v-if="!isAction && !isInput" class="btn primary" @click="next">
          {{ stepIndex === stepCount - 1 ? "Finish section" : "Continue" }}
        </button>
      </div>
    </div>
  </div>
</template>
