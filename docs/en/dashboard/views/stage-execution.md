---
title: "Running a Stage from the Dashboard"
compact: "StageRunner model options, server phases, dataset selection, queued execution, and artifact transfer."
source_files: dashboard/src/lib/useJobs.js, dashboard/src/components/StageRunner.vue, dashboard/src/components/LoadingProgress.vue
---

# Running a Stage from the Dashboard

Campaign Optimizer carries one tab per model — MTA attribution, MTA strategy optimization, MTA strategy evaluation — and Optimization Log carries the same three beside the provenance it already showed. Each model tab has its own runner, and each log tab its own output.

Every runner begins with a **Data** selector populated by its stage descriptor
from `GET /api/jobs`. Attribution choices name an available dashboard report
scope. Optimization choices name a research run and marketplace. Evaluation
choices name either current strategy observations or a research run and
marketplace. The client never invents a filesystem path or assumes that the
first marketplace is intended. A run cannot start until an available choice
is selected, and the server revalidates the identifier immediately before
preparing inputs.

**The dashboard runs the project's own command.** A run started here and one started in a terminal execute the same script with the same arguments, so the dashboard cannot drift from the pipeline it reports on. The command is shown verbatim beneath the log, so a reader who wants to reproduce a run, or to check what the dashboard actually did, can copy it.

### Progress reports a phase, not a timer

`run_pipeline()` and `run_attribution_models()` take an optional `progress` callback and print a line as each stage begins; the server matches those lines to advance the bar. A slow Shapley fit therefore shows as a slow phase rather than a bar that reaches ninety percent and stops. The bar is monotonic by construction: a later line naming an earlier stage never walks it backwards, which a last-match-wins rule would do as soon as a summary mentions a previous stage. A test asserts every declared phase pattern matches a line the scripts actually print, so a phase cannot silently stop matching.

The callback defaults to `None`, so importing either function produces no output the caller did not ask for; only the command-line entry points pass a printer.

### Polling, because the run outlives the request

The response returns as soon as the child process is spawned and the client polls for the rest. The runs are minutes rather than milliseconds, and a dropped connection partway through a fit should not abandon it. Polling stops when nothing is running.

New results are loaded on request rather than automatically: a finished run swapping the numbers under a reader mid-read would be worse than a button.

### Refusals happen before anything is spawned

Running a stage needs a Python backend and a writable runtime directory. The
published static build has neither and keeps Run disabled. A file-mode backend
uses fixed server-owned files and allows the resulting artifacts to be
downloaded. Database mode additionally offers explicit import into the active
schema. Strategy optimization still needs a research snapshot to fit against,
because fitting a budget-to-revenue curve needs the same Campaign observed at
several budget levels and a single reporting window carries one. Every reason
is checked before the spawn, so a refusal never leaves a half-started run behind,
and each names its remedy rather than only the fault.

Options are validated at the same boundary: a date must be a plain ISO date, a total budget a positive number, and a budget usage policy one the `BudgetUsagePolicy` enum declares. Arguments are passed as a vector with `shell: false`, never as a string a shell would re-parse.

Configuration protection does not block runs. A database-backed AppStack
deployment may keep credentials read-only while enabling pipeline execution;
the server's job capability is authoritative. The deployment uses one pod and
one application process because job progress is process-local.

### Strategy evaluation is a runnable model stage

The evaluation tab starts `modules/mta_strategy_evaluation/src/evaluate_strategies.py` through the same job
runner as attribution and optimization. The script projects both strategy
artifacts, checks conservation, compares only allocations whose Campaigns are
observed, and publishes `strategyEvaluation`. The current view explains those
layers and exposes the run; it does not yet render the report fields.

`StageRunner.vue` is one stage's controls, dataset selector, progress bar, log,
and artifact transfer surface, and is mounted once per model tab in both
Campaign Optimizer and Optimization Log — so the two views cannot show a run
differently. It takes the stage descriptor whole rather than a set of flags, so
available datasets, artifact filenames, and capabilities come from the server
without a view edit. The selected dataset identifier is emitted as `datasetId`
beside declared extra options. **The bar reads `job.percent` for both
`aria-valuenow` and the visible percentage**, so a screen reader and the bar
cannot report different progress, and the command is rendered verbatim beside
it. The log follows its tail only while the run is going. A blocked stage or a
stage with no dataset renders its reason in place of an enabled control rather
than failing when pressed. Valid outputs have fixed download links. A file input
uploads one complete stage set to the backend for validation and parsing, and
the database-import action is shown only when the server declares it.

`LoadingProgress.vue` is the corresponding reader for dataset loads rather
than model runs. It accepts the shared progress object, uses a determinate
width and `aria-valuenow` only when a backend milestone or total bytes are known,
otherwise renders an indeterminate bar, and states server phase, elapsed time,
and received versus total bytes where possible. The store makes it visible
immediately and owns timing so two mounted views cannot disagree about the same
request.

## Source Files

### `src/lib/useJobs.js`

Source: `dashboard/src/lib/useJobs.js`

- Responsibility: Hold the single shared copy of every stage's run state and poll it while anything is running.
- Inputs: `GET /api/jobs`, through `src/api/client.js`.
- Outputs: `useJobs()` returning `stages`, read-only `busy` and `error`, `running`, `ensureLoaded()`, `refresh()`, `start()`, `stop()`, `uploadOutputs()`, `importOutputs()`, and `reloadAfterRun()`.
- Behavior contract: One module-level store rather than a fetch per tab: the optimizer shows three stages at once, and three components polling for themselves would be three times the requests to paint one screen, with three answers free to disagree about which stage is running. **Polling stops when nothing is running** — a dashboard left open on an idle pipeline must not issue a request every second forever — and a stage started from this browser restarts the poll itself. `schedule()` clears the timer before setting one, so a manual refresh landing beside a scheduled one cannot leave two timers polling in parallel. A refusal from the server is surfaced rather than swallowed. Upload refreshes parsed dashboard data after backend validation; database import refreshes capability after its backend transaction. `reloadAfterRun()` remains reader-controlled so a finished stage does not swap numbers mid-read.
- Dependencies: Vue's reactivity, `src/api/client.js`, and `src/lib/useDashboard.js`.
- Verification: `dashboard/tests/dashboard.test.js` covers the server contract this module polls — `GET /api/jobs`, the refusals, and the progress shape. The store itself, its poll scheduling, and its stop-when-idle rule are exercised in a real browser against a running stage.


### `StageRunner.vue`, `LoadingProgress.vue`

Source: `dashboard/src/components/StageRunner.vue`, `dashboard/src/components/LoadingProgress.vue`

- Responsibility: Implement the reader-facing contract on this page.
- Inputs and outputs: Stage descriptors and form values produce backend job requests and progress displays.
- Dependencies: Vue and the shared client.
- Verification: `npm --prefix dashboard test`; production build and browser navigation.
