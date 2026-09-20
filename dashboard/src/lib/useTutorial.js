/**
 * The guided tutorial's content and state, held outside any routed view.
 *
 * The tutorial navigates between pages, so it cannot live inside the page that
 * starts it: a component rendered by `Settings.vue` is unmounted the moment
 * the first step leaves Settings, taking the tutorial with it. The state is
 * module-level here and the overlay is rendered once by `App.vue`, so a
 * lesson survives every navigation it performs.
 *
 * The tutorial is driven by the reader doing the work, not by a Next button.
 * A step of kind `action` names a real control, the overlay masks everything
 * except that control, and the step is only satisfied when the reader clicks
 * it -- which performs the real operation, including the server runs. A step
 * of kind `input` asks the reader to set something up and carries an `until`
 * condition describing what a correct setup looks like; the overlay watches
 * for it and moves on by itself the moment the reader gets there, so a lesson
 * never waits on a Continue button for work the page can see is done. A step
 * of kind `note` explains something that has no button to press and is
 * dismissed by acknowledging it. Nothing in this module calls the backend
 * itself: it points at the application's own controls and lets them act.
 *
 * An `input` step preceding an `action` step is what keeps the action's
 * control from being dead: the reader cannot arrive at "press Recompute"
 * until the selection that enables Recompute exists.
 *
 * The content is a set of independent sections rather than one fixed
 * sequence, so a reader who wants to know how to run attribution need not
 * walk database setup first.
 *
 * Data flow: `Settings.vue` (launch) -> here -> `GuidedTour.vue` (overlay),
 * with each step writing `window.location.hash`, which is the same public
 * route contract `App.vue` reads.
 */
import { computed, ref } from "vue";

const STORAGE_KEY = "mta.tutorialDone";

/**
 * Shown under any step marked `demo`, wherever the lesson has the reader look
 * at or choose real records. The data behind this dashboard is synthetic, and
 * a reader being taught to trust these numbers must be told so at the moment
 * they are looking at them, not in a footnote somewhere else.
 */
export const DEMO_NOTICE =
  "This data is for demonstration only. The scenarios shipped with this " +
  "project are synthetic — the KFC example is a recognisable label on " +
  "simulated records, not real advertising data.";

/**
 * How an `input` step knows the reader has set things up correctly.
 *
 * Each returns true once the page shows a valid selection. They read the
 * rendered controls rather than application state, because the overlay is
 * deliberately outside every view and must not reach into one; what the
 * reader can see is exactly what these check.
 */
export const READINESS = {
  /** A campaign is chosen and a marketplace is filled, so Recompute enables. */
  optimizerSelection() {
    const campaign = document.querySelector("#optimizer-campaign");
    const marketplace = document.querySelector("#optimizer-marketplace");
    const button = document.querySelector('[data-tour="optimizer-recompute"]');
    return Boolean(
      campaign?.value?.trim() &&
        marketplace?.value?.trim() &&
        button &&
        !button.disabled,
    );
  },
  /** A runnable stage has a dataset selected, so its Run button enables. */
  stageRunnable() {
    const button = document.querySelector('[data-tour="run-attribution"]');
    return Boolean(button && !button.disabled);
  },
};

/**
 * The sections, each a self-contained lesson.
 *
 * A step carries `hash` (the route it needs), `target` (the `data-tour`
 * attribute of the control it unmasks), `kind`, and the prose. `action` steps
 * wait for a real click on the target; `input` steps wait for their `until`
 * readiness check to pass and then advance by themselves; `note` steps are
 * acknowledged. `optional` marks a step the reader may skip when the
 * deployment cannot offer it, so a read-only server does not trap the tour.
 */
export const TUTORIAL_SECTIONS = [
  {
    key: "database",
    title: "Set up a data source",
    summary: "Point the dashboard at a database or dataset and reload it, by doing it.",
    steps: [
      {
        kind: "note",
        title: "Every number comes from one source",
        hash: "#/settings/general",
        target: "dataset-selector",
        body: "Two kinds of source exist: the legacy source, which is the PostgreSQL database or sample files this deployment was configured with, and registered datasets, which are generated or imported bundles kept beside it. The highlighted selector names the active one.",
        hint: "This is the control you would use to switch sources. Read it, then continue.",
      },
      {
        kind: "action",
        title: "Open the Data source tab",
        hash: "#/settings/general",
        target: "settings-tab-source",
        body: "Everything about the legacy connection lives on the Data source tab: the connection fields, the schema selection, and Reload data.",
        hint: "Click the highlighted Data source tab to continue.",
        recover: {
          hint: "The Settings tabs have not rendered yet. Go to Settings from the navigation rail, and this step will find them.",
        },
      },
      {
        kind: "note",
        title: "The doctor numbers the setup",
        hash: "#/settings/source",
        target: "database-doctor",
        body: "The doctor marks which step you are on, so a failure says which stage failed rather than only that something did. Beneath it, enter the host, port, database, user, and password, then use Test connection before Save to .env. If this server is protected, those fields are replaced by an instruction and the connection is set outside the browser.",
        hint: "Read the highlighted step strip, then continue.",
      },
      {
        kind: "note",
        title: "One schema is one scenario",
        hash: "#/settings/source",
        target: "active-source",
        body: "A database can hold several scenarios, each in its own schema. The highlighted group names the active source; the schema list beneath it names each candidate and what selecting it does. Any valid schema works the same way — the tutorial does not depend on a particular one.",
        hint: "Read the highlighted group, then continue.",
        demo: true,
      },
      {
        kind: "note",
        title: "If there is no schema to read yet",
        hash: "#/settings/source",
        target: "schema-setup",
        body: "This group builds one. Initialize sample model writes the committed synthetic account into an empty schema, and Parse all scenarios reads a simulator source schema and derives one dashboard schema per scenario — that is how the KFC example scenarios are produced. Replacement is a separate confirmed choice, because it destroys what is already there.",
        hint: "Read the highlighted group. Use it only if the schema list above offered nothing ready.",
        demo: true,
      },
      {
        kind: "action",
        optional: true,
        title: "Reload the source for real",
        hash: "#/settings/source",
        target: "reload-data",
        body: "Reload data clears the backend and client caches and re-reads the selected schema, without restarting the server. This is a real operation: clicking it now actually reloads this deployment's data.",
        hint: "Click the highlighted Reload data button.",
        recover: {
          hint: "Reload is busy or unavailable on this deployment right now. Skip this step; nothing later in the section depends on it.",
        },
      },
      {
        kind: "note",
        title: "Confirm the source reads",
        hash: "#/overview/summary",
        target: "",
        body: "The Command Center is the check: if spend, attributed outcomes, and a budget recommendation appear here, the source is connected and readable. An empty or erroring page names what is missing and links to the setting that fixes it.",
        hint: "Look over the page, then finish this section.",
      },
    ],
  },
  {
    key: "attribution",
    title: "Run the attribution model",
    summary: "Actually start the attribution stage on the server and read its verdict.",
    steps: [
      {
        kind: "action",
        title: "Open the attribution tab",
        hash: "#/optimizer/optimization",
        target: "model-tab-attribution",
        body: "The Campaign Optimizer holds the pipeline in three tabs, in the order it runs: attribution, then optimization, then evaluation. Attribution divides credit for conversions that already happened; it does not predict what a budget change would do.",
        hint: "Click the highlighted MTA attribution tab to continue.",
        recover: {
          hint: "The optimizer tabs have not rendered yet. Open Campaign Optimizer from the navigation rail, and this step will find them.",
        },
      },
      {
        kind: "note",
        title: "Choose the data to run on",
        hash: "#/optimizer/attribution",
        target: "stage-runner",
        body: "This runner starts the model on the server. Its Data list offers the datasets this deployment can run against; pick the advertiser, marketplace, and window you want before starting. The list comes from the connected source, so whatever it offers is real data this deployment can read.",
        hint: "Set the Data selector in the highlighted panel if you want a different one, then continue.",
        demo: true,
      },
      {
        kind: "action",
        optional: true,
        title: "Run it",
        hash: "#/optimizer/attribution",
        target: "run-attribution",
        body: "This starts the real stage on the server. It streams its output while it works and writes five result files when it finishes. Clicking here performs an actual run.",
        hint: "Click the highlighted Run button.",
        recover: {
          hint: "This deployment cannot start the stage — it needs a writable runtime output directory and a compatible dataset. The run record on the Optimization Log names the remedy. Skip this step to carry on with the lesson.",
        },
      },
      {
        kind: "note",
        title: "The reliability verdict governs everything",
        hash: "#/optimizer/attribution",
        target: "attribution-verdict",
        body: "RELIABLE rows carry the official model's point value. UNRELIABLE rows carry the interval between the two models instead and grant no budgeting authority — a deliberate refusal, not a missing number. The implied budget shift further down is withheld entirely when this reads UNRELIABLE.",
        hint: "Read the highlighted banner, then continue.",
      },
      {
        kind: "note",
        title: "Two models, shown side by side",
        hash: "#/optimizer/attribution",
        target: "attribution-disagreement",
        body: "Markov measures what removing a touchpoint would cost; Shapley measures average marginal contribution. They disagree by construction, so both are shown per touchpoint rather than picking one and hiding the disagreement. Connector length is the size of the disagreement.",
        hint: "Read the highlighted chart, then continue.",
      },
      {
        kind: "note",
        title: "The governed recommendation",
        hash: "#/optimizer/attribution",
        target: "attribution-recommended",
        body: "This is the value the rest of the dashboard is allowed to use: the official model's share where the verdict permits, and an interval where it does not. Each row carries its own reliability status.",
        hint: "Read the highlighted table, then finish this section.",
      },
    ],
  },
  {
    key: "optimization",
    title: "Run the optimization model",
    summary: "Ask the optimizer for a budget on a real campaign and read the answer.",
    steps: [
      {
        kind: "action",
        title: "Open the optimization tab",
        hash: "#/optimizer/attribution",
        target: "model-tab-optimization",
        body: "Optimization answers the budget question: given what you are willing to spend, how much should this campaign get to earn the most. It learns from the campaign's own history of budgets, spend, and revenue. Attribution is not an input — credit for the past is a different question from response to a change.",
        hint: "Click the highlighted MTA strategy optimization tab to continue.",
        recover: {
          hint: "The optimizer tabs have not rendered yet. Open Campaign Optimizer from the navigation rail, and this step will find them.",
        },
      },
      {
        kind: "input",
        until: "optimizerSelection",
        title: "Pick a campaign and its marketplace",
        hash: "#/optimizer/optimization",
        target: "optimizer-campaign-card",
        body: "The optimizer needs two things before it can fit anything: a campaign from this source, and the marketplace that campaign runs in. Click the Campaign box and pick one of the suggestions — the list comes from the data you are connected to — then check the marketplace code beneath it matches.",
        hint: "Choose a campaign from the suggestions and make sure the marketplace is filled. This step continues by itself once the selection is valid.",
        demo: true,
      },
      {
        kind: "note",
        title: "Choose which history to learn from",
        hash: "#/optimizer/optimization",
        target: "optimizer-history-mode",
        body: "This Campaign only uses the selected campaign's own records. Full dataset also borrows from comparable campaigns — same advertiser, marketplace, currency, provider, and ad product — when its own history is too thin to fit a curve. A borrowed curve is always labelled POOLED_TRANSFER, so a transferred estimate is never passed off as the campaign's own behaviour.",
        hint: "Set the highlighted History source if you want to change it, then continue.",
      },
      {
        kind: "note",
        title: "Enter the budget to compare against",
        hash: "#/optimizer/optimization",
        target: "optimizer-budget",
        body: "The initial daily budget is the baseline the optimized figure is measured against; leaving it blank uses the campaign's own historical baseline. It does not change the authorized cap. The similarity threshold beside it decides how close a comparable campaign's budget must be before its records may be borrowed.",
        hint: "Enter a budget in the highlighted rows if you want one, then continue.",
      },
      {
        kind: "action",
        title: "Compute the strategy",
        hash: "#/optimizer/optimization",
        target: "optimizer-recompute",
        body: "This sends your selection to the server, which fits the response and returns the plan. It is a real request. Nothing is written: this is a preview computed from history, not a stage that publishes an artifact.",
        hint: "Click the highlighted Recompute strategy button.",
        recover: {
          hint: "The button needs a campaign and a marketplace before it will enable. Step back once to set them, and this step will be ready.",
          steps: 1,
        },
      },
      {
        kind: "note",
        title: "Read the response curve",
        hash: "#/optimizer/optimization",
        target: "response-curve",
        body: "The optimizer fits two curves — budget to spend, then spend to revenue — and allocates so the last unit of budget earns the same everywhere. Amber shading marks budgets outside the range the fit actually observed; a decision there is extrapolated, and is shown that way rather than hidden behind a flag.",
        hint: "Read the highlighted chart, then continue.",
      },
      {
        kind: "note",
        title: "How the budget splits across touchpoints",
        hash: "#/optimizer/optimization",
        target: "touchpoint-plan",
        body: "This takes the decided daily budget and divides it across the campaign's own touchpoints by recommended attributed credit. It is the answer to how much money to put where, stated in currency rather than shares. If any row is UNRELIABLE the split is indicative only, and says so.",
        hint: "Read the highlighted card, then continue.",
      },
      {
        kind: "note",
        title: "When the optimizer refuses",
        hash: "#/optimizer/optimization",
        target: "",
        body: "A campaign observed at fewer than three distinct budget levels cannot support a fitted curve. Rather than invent one, the optimizer returns a historical baseline: the observed budget that earned the most, labelled an observed reference and never a predicted uplift. TARGET_HISTORY is the campaign's own evidence; POOLED_TRANSFER is a borrowed curve.",
        hint: "Read this, then finish the section.",
      },
    ],
  },
];

const active = ref(false);
const sectionKey = ref("");
const stepIndex = ref(0);
const completed = ref(readCompleted());

function readCompleted() {
  try {
    const value = JSON.parse(window.localStorage.getItem(STORAGE_KEY) ?? "[]");
    return Array.isArray(value) ? value.filter((item) => typeof item === "string") : [];
  } catch {
    // A browser refusing storage must not stop the tutorial from running.
    return [];
  }
}

function storeCompleted(value) {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(value));
  } catch {
    // Remembering finished sections is a convenience, not a requirement.
  }
}

const section = computed(() =>
  TUTORIAL_SECTIONS.find((item) => item.key === sectionKey.value) ?? null,
);
const step = computed(() => section.value?.steps[stepIndex.value] ?? null);
const stepCount = computed(() => section.value?.steps.length ?? 0);

/** Steer the real application through its public route contract. */
function navigate(hash) {
  if (hash && window.location.hash !== hash) window.location.hash = hash;
}

export function useTutorial() {
  return {
    active,
    section,
    sectionKey,
    step,
    stepIndex,
    stepCount,
    completed,

    /** Open the tutorial on its section picker. */
    open() {
      active.value = true;
      sectionKey.value = "";
      stepIndex.value = 0;
    },

    /** Begin one section, navigating to its first step. */
    startSection(key) {
      const chosen = TUTORIAL_SECTIONS.find((item) => item.key === key);
      if (!chosen) return;
      sectionKey.value = key;
      stepIndex.value = 0;
      navigate(chosen.steps[0].hash);
    },

    /** Advance, or return to the picker when the section ends. */
    next() {
      if (!section.value) return;
      if (stepIndex.value >= stepCount.value - 1) {
        if (!completed.value.includes(sectionKey.value)) {
          completed.value = [...completed.value, sectionKey.value];
          storeCompleted(completed.value);
        }
        sectionKey.value = "";
        stepIndex.value = 0;
        return;
      }
      stepIndex.value += 1;
      navigate(step.value?.hash);
    },

    previous() {
      if (stepIndex.value === 0) return;
      stepIndex.value -= 1;
      navigate(step.value?.hash);
    },

    /** Leave the current section without finishing it. */
    backToSections() {
      sectionKey.value = "";
      stepIndex.value = 0;
    },

    /** Close the tutorial entirely. */
    quit() {
      active.value = false;
      sectionKey.value = "";
      stepIndex.value = 0;
    },
  };
}
