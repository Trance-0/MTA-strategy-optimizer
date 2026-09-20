---
title: Guided Tutorial
compact: "Specifies the interactive walkthrough in dashboard/src/lib/useTutorial.js, GuidedTour.vue and TutorialLauncher.vue: three sections, action steps masking one real data-tour control, input steps advancing on a READINESS check, recover remedies instead of dead ends, DEMO_NOTICE, spotlight geometry and mta.tutorialDone."
lang: en-US
source_files: dashboard/src/lib/useTutorial.js, dashboard/src/components/GuidedTour.vue, dashboard/src/components/TutorialLauncher.vue
---

# Guided Tutorial

The tutorial teaches the application by having the reader operate it. It is
launched from the Settings page's General tab, specified in
[Navigation Rail and Settings](./navigation.md#general), and it runs over every
page rather than inside one.

## Sections rather than one sequence

The tutorial is a set of independent sections, because a reader who wants to
know how to run attribution should not have to walk database setup first.
Opening it presents a picker, running a section walks that section's steps, and
finishing records the section and returns to the picker to choose another or
leave. Three sections are published:

#### Set up a data source

Opening the Data source tab, the database doctor, the schema that decides every
number, reloading the source for real, and confirming the Command Center reads.
The example scenario is the synthetic KFC advertiser, named as an example only:
any valid schema behaves the same way, and the lesson says so rather than
depending on that scenario being present.

#### Run the attribution model

Opening the attribution tab, choosing the data to run against, starting the real
stage on the server, and then reading the reliability verdict, the two models'
disagreement, and the governed recommendation.

#### Run the optimization model

Opening the optimization tab, choosing a campaign and its marketplace, choosing
which history to learn from, entering the budget to compare against, computing
the strategy for real, and then reading the response curve, the touchpoint
budget split, and the refusal case. The campaign selection is an input step
gating the **Recompute strategy** action, so the reader reaches that button
only once it is enabled.

## The data is for demonstration

Every step that has the reader look at or choose real records carries `demo`,
and the card states beneath it that the data is synthetic: the scenarios shipped
with this project are simulated, and the KFC example is a recognisable label on
simulated records rather than real advertising data. The notice is shown at the
moment the reader is looking at those numbers rather than in a footnote
elsewhere, because a reader being taught to trust a figure must be told what it
is while they are reading it.

If a deployment has no readable schema at all, the data-source section points at
the Settings **Schema setup** group, which builds one: **Initialize sample
model** writes the committed synthetic account into an empty schema, and
**Parse all scenarios** derives one dashboard schema per scenario from a
simulator source schema, which is how the KFC example scenarios are produced.
The tutorial points at those controls rather than carrying a bootstrap of its
own, so there is one way to build a schema and the lesson teaches it.

## Step kinds

A step is one of three kinds, and the distinction is the whole design.

An **action** step names a control the reader must actually press. The overlay
listens for that click in the capture phase without cancelling it, so the
application's own handler still runs: one click both performs the operation and
advances the tutorial. Action steps include opening the Data source tab,
**Reload data**, both stage **Run** buttons, and **Recompute strategy** —
pressing them performs the real operation against this deployment, including the
server runs. An action step therefore offers no **Continue** button, and the
right arrow key will not skip it, because a walkthrough that advances past the
thing it is teaching has taught nothing.

An **input** step asks the reader to set something up, and carries an `until`
naming a readiness check in `READINESS`. The overlay polls that check and
advances by itself the moment it passes, so the reader is never asked to press
Continue for work the page can already see is done. An input step preceding an
action step is what keeps the action's control from being dead: the reader
cannot arrive at "press Recompute" until the selection that enables Recompute
exists. Readiness checks read the rendered controls rather than application
state, because the overlay sits outside every view and must not reach into one;
what the reader can see is exactly what they check.

A **note** step explains something with no button to press and is acknowledged
with **Continue**.

## A blocked control is never a dead end

An action step whose control is missing or disabled does not report that the
step cannot be completed and stop. Every action step carries a `recover.hint`
saying what the control needs, and the card shows it in place of the fault.
Where the missing setup lives a known number of steps back, `recover.steps`
adds **Set that up first**, which returns there so the reader can supply it and
be led forward again. Where the deployment simply cannot offer the operation —
no writable runtime directory, no executable stage — the step is also marked
`optional` and offers **Skip this step**, so a read-only deployment is never
trapped mid-section.

While an action step is blocked the overlay keeps re-checking its control, so a
prerequisite the reader satisfies without leaving the step clears the message
and re-arms the click as soon as the button enables.

## The spotlight

A step highlights a real element rather than describing where it is. Its
`target` names a `data-tour` attribute, the overlay finds that element, scrolls
it into view when it is off screen, and cuts it out of the dimming mask.

The mask is four opaque panels drawn around the element rather than one
translucent sheet with a transparent hole. Two things follow, and both are the
point: the highlighted control keeps its own colours, focus ring, and hover
states because nothing is drawn over it, and the panels swallow every click
outside the cutout, so during an action step the highlighted control is the only
thing on the page the reader can press. A ring traces the cutout and pulses
while an action is outstanding.

The panels, the ring, and the card animate between positions, so moving to the
next control reads as the spotlight travelling rather than the page flickering.
The card measures its own height and takes the side of the highlight with room
for it — below, else above, else pinned within the viewport — so it never covers
the thing it points at.

A step with no `target` dims the whole page, which is what a step introducing a
page rather than a control wants. Because a step runs immediately after its
route change, the overlay retries for about three seconds while the page mounts
before reporting the control unavailable.

## The anchors

The anchors are `data-tour` attributes on the elements the lessons teach. Those
naming a region carry an explanation: the top bar's dataset selector, the
Settings tab strip, the database doctor, the active-source group, the stage
runner panels, the Campaign Optimizer's model tab strip, its campaign card,
history-source row and budget rows, and the reliability banner, disagreement
chart, recommended-attribution table, response curve, and touchpoint budget
plan.

Those naming a single control are what action steps require the reader to press:
`settings-tab-source`, `reload-data`, `run-<stage>` on each stage runner's Run
button, `model-tab-<key>` on each optimizer tab, and `optimizer-recompute`.

An attribute exists for the tutorial to point at and for no other purpose;
removing one breaks the test that requires it.

## What the tutorial never does

The tutorial itself calls nothing. It presses no control for the reader and
makes no request of its own: the state module references no job, settings,
reload, or dataset-selection function. Every operation that happens during a
lesson happens because the reader clicked the application's own button, which is
what makes the lesson worth taking.

Advancing writes the step's route to the location hash, so the tutorial drives
the real application through the same public route contract every other control
uses.

## Chrome and persistence

A bar across the top carries the section name, the step count, a segmented
progress strip, and the **All sections** and **Quit tutorial** controls. **Back**
steps backwards, `Escape` quits, and the left arrow key steps back.

Completed section keys are kept in `localStorage` under `mta.tutorialDone`, so
the picker marks what has been finished and the launcher counts it. A browser
refusing storage still runs the tutorial.

## Why the state lives outside the page

The tutorial's state lives in `src/lib/useTutorial.js` and its overlay is
rendered once by `App.vue`, never by a routed view. A tutorial owned by Settings
would be unmounted by its own first step as soon as that step navigated away,
which is exactly how an earlier revision became invisible the moment it started.

## Source Files <span class="status-label status-verified" aria-label="Verified"></span>

### `src/lib/useTutorial.js`, `src/components/GuidedTour.vue`, and `src/components/TutorialLauncher.vue`

Source: `dashboard/src/lib/useTutorial.js`, `dashboard/src/components/GuidedTour.vue`, `dashboard/src/components/TutorialLauncher.vue`

- Responsibility: Hold the tutorial's content and state outside any routed view, render its overlay once from the shell, and offer the launch control from Settings.
- Inputs: None from the application; completed section keys are read from `localStorage` under `mta.tutorialDone`.
- Outputs: `TUTORIAL_SECTIONS` and the `useTutorial()` accessor; the spotlight mask, top bar, section picker, and step card; and location-hash writes that navigate the shell.
- Behavior contract: `TUTORIAL_SECTIONS` is an array of sections, each with `key`, `title`, `summary`, and an ordered `steps` array of `kind`, `title`, `hash`, `target`, `body`, `hint`, and the optional `until`, `recover`, `optional`, and `demo`. `kind` is `action`, `input`, or `note`; every `action` step must name a `target` and must carry either a `recover` remedy or `optional`, and every `input` step must name an `until` that exists in the exported `READINESS` map. Every `hash` must name a registered page and subsection and every non-empty `target` must exist as a `data-tour` attribute in a component, all of which `tests/dashboard.test.js` asserts. The overlay binds a capture-phase click listener to an action step's target and never calls `preventDefault()`, so the application's own handler runs and the same click advances the step. An input step's readiness check is polled every 250ms and advances the step 420ms after it first passes; a blocked action step's control is polled on the same interval so it re-arms when it enables. `DEMO_NOTICE` is rendered under any step carrying `demo`. State is module-level, so the overlay `App.vue` renders survives the navigation each step performs; `TutorialLauncher.vue` contributes only the Settings row and owns no tutorial state. `open()` presents the picker, `startSection()` navigates to a section's first step, `next()` advances and on the last step records the section key as completed and returns to the picker, `previous()` retreats without leaving the section, `backToSections()` abandons it, and `quit()` closes the overlay. Navigation writes a step's hash only when it differs from the current one. The overlay measures its target with `getBoundingClientRect()`, calls `scrollIntoView()` when the element sits outside the comfortable viewport band, re-measures on scroll and resize through a single animation frame, and retries roughly twenty-five times at 120ms while a freshly navigated page mounts. Nothing here acts on the deployment: no job, settings, reload, or dataset-selection call appears, and the test asserts those names are absent. `.tutorial-mask` takes pointer events so clicks outside the cutout are swallowed; `.tutorial-ring` sets `pointer-events: none` so the framed control stays clickable. Storage failures are swallowed so a browser refusing `localStorage` still runs the tutorial.
- Dependencies: Vue 3; the tutorial rules in `src/style.css`; the `data-tour` anchors in `TopBar`/`DatasetContext`, `Settings.vue`, `StageRunner.vue`, `WorkbenchRunner.vue`, and `CampaignOptimizer.vue`.
- Verification: `dashboard/tests/dashboard.test.js`; the walkthrough is verified in a real browser.

## Verification

- **Scope:** The tutorial's content contract, its action-step behavior, and its anchors.
- **Cases:** Every step names a registered route; every named anchor exists in a component; every action step names a control and carries a remedy or a skip; every input step names a readiness check that exists; the overlay binds a non-cancelling click listener, offers no Continue on an action or input step, and does not let the arrow key skip one; the demo notice exists and is rendered.
- **Command:** `npm test --prefix dashboard`.
- **Limitations:** The spotlight geometry and the animations are verified in a browser, not by the file tests.
