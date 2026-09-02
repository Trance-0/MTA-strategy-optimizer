---
title: Dashboard Views and Visual Contract
compact: "Vue visual contract: seven route-controlled views, immediate backend-phased lazy-loading transitions, accessible terms, server-declared model selectors, artifact transfer, unified queued tasks, large-history-safe charts, and native Willow forecasting."
lang: en-US
source_files: dashboard/src/theme.js, dashboard/src/style.css, dashboard/src/lib/deployment.js, dashboard/src/lib/diagnostics.js, dashboard/src/lib/useJobs.js, dashboard/src/lib/willowGmvModel.js, dashboard/src/lib/terms.js, dashboard/src/views/CommandCenter.vue, dashboard/src/views/BudgetManager.vue, dashboard/src/views/Campaigns.vue, dashboard/src/views/CampaignOptimizer.vue, dashboard/src/views/OptimizationLog.vue, dashboard/src/views/KnowledgeBase.vue, dashboard/src/components/SidebarNav.vue, dashboard/src/components/TopBar.vue, dashboard/src/components/StageRunner.vue, dashboard/src/components/LoadingProgress.vue, dashboard/src/components/TermHelp.vue, dashboard/src/components/WillowGmvForecast.vue, dashboard/src/components/PlotlyChart.vue, dashboard/src/components/DataTable.vue, dashboard/src/components/EntityTable.vue, dashboard/src/components/ConfirmDialog.vue, dashboard/src/components/TableView.vue, dashboard/src/components/MetricRow.vue, dashboard/src/components/KeyValuePanel.vue, dashboard/src/components/ReliabilityBanner.vue, dashboard/src/lib/common.js
---

# Dashboard Views and Visual Contract

The seven views are listed on [Dashboard](./index.md#the-seven-views). This page specifies what they share beyond the question each one answers: the reliability rule every data view honors and the colour, chart, formatting, and key-term help system they draw from.

Optimization Log is backed by run provenance and pipeline stage state.
Knowledge Base has no backend-owned knowledge contract yet, so its former
snapshot-derived ontology is removed. The view renders one unavailable notice
and no vocabulary, rules, entity, or artifact tabs until a backend endpoint is
specified and implemented.

## Key-Term Help <span class="status-label status-verified" aria-label="Verified"></span>

`TermHelp.vue` adds an accessible help button after declared key terms in metric
labels, key/value labels, and table headers. Hover, focus, or activation reveals
a short definition. When the term needs more context, the popover links to the
specific English definition or owning specification page; a generic Docs link
is not substituted for a precise reference.

`src/lib/terms.js` is the only term registry. Each entry contains a normalized
label, plain-language definition, and optional documentation path. The initial
registry covers Return on Ad Spend (ROAS), Click-Through Rate (CTR), Cost Per
Click (CPC), Cost Per Mille (CPM), attribution, touchpoint, reliability,
configured budget, actual spend, contribution profit, conversion path,
database schema, and ground truth. The visible label remains in the page, so a
tooltip is never the only source of a value or column name.

The button uses `aria-describedby`; the popover opens on keyboard focus as well
as pointer hover; Escape and focus departure close it. Documentation links open
normally and remain keyboard reachable. Tests assert every registered path is
an English documentation path.

Optimization Log's fifth stage now reports the [Campaign budget optimizer](/en/strategy-recommendation/campaign-budget-optimizer.md) from its artifact rather than from a constant. When `outputs/campaign_strategy.json` is absent — the state of any checkout that has not run the research command — the stage reads `NOT RUN` and the initializer's seed remains the current recommendation. When the artifact is present the view shows the optimized allocation beside its evidence, and when the optimizer refused it shows the refusal and its reasons instead of an allocation. Every Campaign optimized outside the budget range its fit observed, and every Campaign whose curve was pooled from comparable Campaigns rather than its own history, is named rather than left implicit in a number.

## Deployment Capability Governs the Interface <span class="status-label status-verified" aria-label="Verified"></span>

The dashboard ships in three deployments and only one of them can change data. Which one a reader is looking at governs how every number on the page may be used, so it is carried by the whole interface rather than by one badge in a corner.

**Capability is derived from the snapshot's own `mode`, never from the build flag.** A local run reading the committed files is read-only for exactly the same reason the published build is: there is no database behind it to write to. Deriving the answer from `VITE_STATIC_BUILD` would wrongly offer editing controls to that local run. `src/lib/deployment.js` is the single place the question is asked, and `writable` is true only when the server reports `mode === "database"`.

### The two accents

A deployment that cannot write wears Microsoft Excel's own green, `#217346`, which is the association a reader already has for a spreadsheet: this is a table of committed values. A deployment connected to PostgreSQL keeps the reference prototype's brand blue. Both sets live in `theme.js` beside every other colour, and `App.vue` applies the selected one by overriding the custom properties `style.css` already reads — so one override repaints the rail, the tabs, the primary buttons, and the selection highlight, and no component needs a deployment variant class.

**The chart series palette is deliberately excluded.** A series colour follows its entity, so the same Campaign must keep its colour across both deployments; a reader comparing the published site with a local run would otherwise see one Campaign in two colours. `tests/dashboard.test.js` asserts the deployment accents and the categorical palette never intersect.

### Read-only is stated, not merely enforced

A read-only deployment renders a notice above every view naming why it is read-only and the remedy that applies to it: the published build points at running the dashboard locally, and a local file-mode run points at `DATABASE=true` and the Settings dialog. The two are named apart rather than collapsed into one label, because a reader can act on one and not the other.

Hiding the controls alone would not be enough. A reader should learn that editing is unavailable from the page, not by hunting for a button that is not there. The server enforces the same rule independently: `PUT` and `DELETE /api/master/…` are refused outside database mode regardless of what the client rendered.

## Canonical Entities Are Lists, Not Prose <span class="status-label status-verified" aria-label="Verified"></span>

Budget Manager's seven entity sections each render as one paged table, in the manner of a 1Panel resource list. A row is an **abstract** — a handful of declared summary columns — and the whole record sits behind that row's own Edit control.

This replaces a detail list that rendered every field of every record as stacked paragraphs. That layout put hundreds of lines of prose on one page, offered no way to scan a column or compare two records, and grew without bound with the data behind it.

`EntityTable.vue` owns paging, page size, selection, and the two row controls; it does not own what a row means. Columns are declared by the view exactly as `DataTable`'s are, so a new field in the snapshot cannot silently widen a table.

### Paging and page size

Fifteen rows per page by default, with 15, 30, 50, and 100 offered. A section therefore opens at one screen rather than at a hundred rows. A free-text filter narrows across the rendered text of the declared columns, so what a reader searches is what a reader sees, and the page is clamped rather than reset when the filter narrows.

### Selection survives paging

Selection is keyed by a caller-supplied row identity, not by page index. Keyed by index, a batch action would act on whatever record happened to sit at that index after the page turned. The header checkbox acts on the current page, which is what it can show, and the count of everything selected is stated beside it.

### Deletion always asks, and names what it will remove

Every deletion — one row or a batch — routes through one confirmation that lists the affected identifiers rather than reporting a count alone. A count is not something a reader can check, and a batch selected across several pages is exactly the case where a reader cannot see what they picked. The list is capped at twelve with the remainder stated, so a large selection cannot produce an unreadable dialog.

A batch archives sequentially rather than concurrently, because each archive clears the server's caches and a parallel batch would have them racing. **A failure stops the run and reports which identifier it stopped at**, leaving the dialog open: reporting success after a partial batch would be a false statement about what is now in the database.

Deletion archives a planned change. It never removes reported performance, which no route mutates in either mode.

### Every deployment populates its entity sections

These records were previously read only from an optional research sidecar, so every default and published deployment showed all seven sections empty. `server/master_data.js` now derives the catalogue — Ad Providers, Products, Campaigns, Ad Groups, touchpoints, product economics, and Campaign-Product links — from the Amazon Ads report, entity bridge, and strategy request the repository already tracks. A sidecar, when one is configured, still takes precedence.

Derivation rather than a second committed catalogue file: a tracked catalogue sitting beside the reports can drift from them, while one read out of them cannot.

**Only what the reports support is reported.** A touchpoint's impressions and clicks arrive as separate per-interaction rows sharing no denominator, so `click_through_rate` is `null` and the observed impressions, clicks, and cost are reported instead — dividing one by the other yielded rates between 0.98 and 1.15. A rate is reported only where both its cost and its denominator are above zero, so a touchpoint whose impression rows carry no cost shows no CPM rather than a CPM of exactly zero. Unit COGS and contribution margin stay `null` rather than becoming zero, since no committed report carries them. Four touchpoints bill CPC on clicks and CPM on impressions at once; cost is accumulated per billing type and the billing type reported as `CPC + CPM`.

A section that is genuinely empty still names its cause — no records in the current reporting window — because "No records loaded" alone reads as a broken deployment.

### The dashboard describes market performance

No view names a data generator, a simulator, or synthesis. A reader of this dashboard is reading reported performance from the platform, and the interface says so throughout: reported performance is read-only, an editable row is a planned change, and a filter that answers which pipeline run wrote a row is diagnostic detail rather than something a marketing reader is shown by default.

Pipeline-run detail therefore sits behind one preference, `Show data run diagnostics` in Settings, persisted in `localStorage` and off by default. It gates Budget Manager's data-run section and the Campaigns data-run filter. `tests/dashboard.test.js` asserts no dashboard source presents its data as generated or simulated.

## Running a Stage from the Dashboard <span class="status-label status-verified" aria-label="Verified"></span>

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

The evaluation tab starts `script/evaluate_strategies.py` through the same job
runner as attribution and optimization. The script projects both strategy
artifacts, checks conservation, compares only allocations whose Campaigns are
observed, and publishes `strategyEvaluation`. The current view explains those
layers and exposes the run; it does not yet render the report fields.

### Willow Sakura forecast is a native panel

The evaluation tab embeds Willow Sakura's contributed Gross Merchandise Value
(GMV) forecast as dashboard widgets, not as a plain HyperText Markup Language
(HTML) page in an `iframe`. The panel includes all four ad-product budgets,
marketplace, day of week, weekend state, all seven placement and creative cost
shares, placement-type count, the run control, predicted attributed revenue,
total daily budget, the all-budgets-plus-ten-percent scenario, revenue delta,
and held-out model metrics.

`WillowGmvForecast.vue` owns the inputs and accessible labels.
`willowGmvModel.js` owns only pure Extended-27 feature construction and forward
inference using the contributor's exported JSON weights. Editing any input or
pressing **Run prediction** recomputes both scenarios. The panel names the
prediction as Amazon-attributed sales rather than organic GMV and reports the
held-out error alongside it; it never feeds this forecast into the project's
optimizer or presents it as realized uplift.

## Reliability is never a footnote <span class="status-label status-verified" aria-label="Verified"></span>

Every view that displays an attributed share displays its reliability verdict beside it, because an UNRELIABLE share must not be read as a fact. The verdict is the AND of the three flags, one false flag is enough to fail a row, and an UNRELIABLE Outcome carries an interval rather than a point value. The Campaign Optimizer refuses to show a budget shift for such an Outcome at all: an interval cannot carry a spend split.

## Visual Contract <span class="status-label status-recommendation" aria-label="Recommendation"></span>

`dashboard/src/theme.js` holds every colour, chart default, and value format, and `dashboard/src/style.css` reads the same values as custom properties, so a change lands everywhere at once and no view invents its own styling. The brand palette — navy rail, blue accent, light plane — is the prototype's. The series palette is a separate validated set, because the prototype contains no real charts and so could not supply one; it passes the lightness band, chroma floor, colourblind-separation, and normal-vision checks against the dashboard's white chart surface.

Three rules the views depend on:

- **Colour follows the entity, never its rank.** Markov is always the same blue and Shapley always the same orange, so filtering a chart never repaints the rows that survive and a reader who learned one association is never contradicted.
- **Status colour is reserved and never carries meaning alone.** A reliability pill always shows the status word itself.
- **One axis per chart.** Where two measures differ by orders of magnitude, as spend and sales do, both are indexed to their own window average and share one scale. A second y-axis would invent a correlation the data does not contain.

Every chart is paired with the values behind it — a table view, direct labels, or both — so no number is reachable only by hovering.

## Source Files <span class="status-label status-verified" aria-label="Verified"></span>

The code-level specification for the files this page describes. Each entry states responsibility, inputs, outputs, dependencies, and the test that verifies it.

### `src/theme.js` and `src/style.css`

Source: `dashboard/src/theme.js`, `dashboard/src/style.css`

- Responsibility: Hold every colour, chart default, and value format the dashboard uses, so a change lands everywhere at once and no view invents its own styling.
- Inputs: None. Constants and pure display helpers.
- Outputs: The brand constants, the reserved status colours and their tone classes, the `SERIES`, `SEQUENTIAL`, and `DIVERGING` palettes, the fixed `MODEL_COLORS` and `OUTCOME_COLORS` maps, `seriesColors()`, `layout()`, `PLOT_CONFIG`, and the `money()`, `compactMoney()`, `count()`, `percent()`, and `ratio()` formatters. `style.css` exposes the same brand values as custom properties for the markup.
- Behavior contract: `SERIES` is a fixed order assigned by slot and **never cycled**; a ninth series folds into "Other" rather than receiving a generated hue, which under colourblind simulation would be indistinguishable from an existing slot. `MODEL_COLORS` and `OUTCOME_COLORS` bind a colour to an entity rather than to a rank, so filtering a chart never repaints the rows that survive. The status colours are reserved for reliability state, are never reused as a series colour, and are always rendered with the status word beside them. `layout()` sets a hairline grid, solid axes, and a height that includes the axis band, so a chart card never grows an inner scrollbar; every chart is titled by the heading above it, so no figure carries a title of its own. Each formatter returns `--` for a value that is not finite, so a missing number is visibly missing rather than rendered as `NaN`. The series palette is not the prototype's: that design contains no real charts, so its three brand colours could not supply one.
- Dependencies: None.
- Verification: Rendered visually. The palette is checked with the data-visualisation validator against the white chart surface; three light-mode hues fall below 3:1 contrast, which is why every chart also ships direct labels or a table view.

`theme.js` additionally exports `DEPLOYMENT_THEMES`, the two accent sets described above. They live here because they are colours, and `tests/dashboard.test.js` asserts they never intersect `SERIES`, `MODEL_COLORS`, or `OUTCOME_COLORS`.

### `src/lib/deployment.js`

Source: `dashboard/src/lib/deployment.js`

- Responsibility: Answer which deployment this is, and therefore whether data operations are available and which accent the interface wears.
- Inputs: The shared snapshot's `mode`, through `useDashboard()`. The build flag, read lazily, for naming only.
- Outputs: `THEMES`, re-exported from `theme.js`; and `useDeployment()` returning the computed `writable`, `theme`, `label`, `readOnlyReason`, and `isStatic`.
- Behavior contract: **`writable` is derived from `mode === "database"` and never from the build flag**, because a local file-mode run is read-only for the same reason the published build is. The build flag decides only how a read-only deployment names itself — "Published build" against "Local files" — and which remedy it offers, since a reader can act on one and not the other. Every value is returned as a computed ref rather than a plain value: the mode is unknown until the first snapshot resolves, so a component reading a plain boolean at setup time would fix itself to the pre-load default and never correct. The accent sets are re-exported rather than declared, because a colour declared twice is free to disagree with itself. The build flag is read through a function rather than imported from `src/api/client.js`, because `import.meta.env` exists only under Vite and importing that module would make this file unloadable in the Node test runner — which is where the capability contract is asserted.
- Dependencies: Vue's reactivity, `src/theme.js`, and `src/lib/useDashboard.js`.
- Verification: `dashboard/tests/dashboard.test.js`, which asserts capability follows the snapshot mode rather than the build flag, that the two accents differ, that neither leaks into the chart palette, that both read-only deployments name a remedy, and that the rail's status dot matches the read-only accent.

### `src/lib/diagnostics.js`

Source: `dashboard/src/lib/diagnostics.js`

- Responsibility: Answer whether the surfaces that describe the pipeline rather than the account are shown.
- Inputs: `localStorage`, read once at module load under the key `mta-dashboard.diagnostics`.
- Outputs: `useDiagnostics()` returning the computed `diagnosticsOn` and `setDiagnostics(on)`.
- Behavior contract: **Off by default.** The dashboard's subject is an advertising account; a surface naming which run wrote a number, under which configuration and seed, answers an engineering question, and a reader planning budget should not have to walk past it. The surfaces are gated rather than deleted, because the question is real when a number looks wrong and removing them would mean reaching for a database client instead. The preference is per-browser rather than server-side: it is a property of who is looking, not of the deployment, and two people reading one hosted dashboard can want different answers. Every `localStorage` access is wrapped and falls back to off, because the Node test runner and a privacy-restricted browser have none, and an unguarded read would throw at import time rather than at use.
- Dependencies: Vue's reactivity.
- Verification: `dashboard/tests/dashboard.test.js`, which asserts the stored value must read exactly `"true"` to enable, that the guard falls back to off, that Budget Manager's diagnostic section exists only while the preference is on, and that the settings dialog is what sets it.

### `src/lib/useJobs.js`

Source: `dashboard/src/lib/useJobs.js`

- Responsibility: Hold the single shared copy of every stage's run state and poll it while anything is running.
- Inputs: `GET /api/jobs`, through `src/api/client.js`.
- Outputs: `useJobs()` returning `stages`, read-only `busy` and `error`, `running`, `ensureLoaded()`, `refresh()`, `start()`, `stop()`, `uploadOutputs()`, `importOutputs()`, and `reloadAfterRun()`.
- Behavior contract: One module-level store rather than a fetch per tab: the optimizer shows three stages at once, and three components polling for themselves would be three times the requests to paint one screen, with three answers free to disagree about which stage is running. **Polling stops when nothing is running** — a dashboard left open on an idle pipeline must not issue a request every second forever — and a stage started from this browser restarts the poll itself. `schedule()` clears the timer before setting one, so a manual refresh landing beside a scheduled one cannot leave two timers polling in parallel. A refusal from the server is surfaced rather than swallowed. Upload refreshes parsed dashboard data after backend validation; database import refreshes capability after its backend transaction. `reloadAfterRun()` remains reader-controlled so a finished stage does not swap numbers mid-read.
- Dependencies: Vue's reactivity, `src/api/client.js`, and `src/lib/useDashboard.js`.
- Verification: `dashboard/tests/dashboard.test.js` covers the server contract this module polls — `GET /api/jobs`, the refusals, and the progress shape. The store itself, its poll scheduling, and its stop-when-idle rule are exercised in a real browser against a running stage.

### The six view components

Source: `dashboard/src/views/CommandCenter.vue`, `dashboard/src/views/BudgetManager.vue`, `dashboard/src/views/Campaigns.vue`, `dashboard/src/views/CampaignOptimizer.vue`, `dashboard/src/views/OptimizationLog.vue`, `dashboard/src/views/KnowledgeBase.vue`

The six share one contract and are specified together.

- Responsibility: Render the six pages of the dashboard, one component per view, in the prototype's navigation order.

#### `CommandCenter.vue`

Five headline tiles, spend against return over time, the per-Outcome reliability verdict, and attributed revenue by ad product for both models.

#### `BudgetManager.vue`

Progressive sub-navigation for Overview, Providers, Products, Campaigns, Ad
Groups, Touchpoints, Product Economics, and Generation Configs. Each of the
seven entity sections renders as one `EntityTable`, per [Canonical entities are
lists, not prose](#canonical-entities-are-lists-not-prose): declared summary
columns as the row abstract, the whole record behind the row's Edit control,
and deletion behind a confirmation that names what it will archive.

The view supplies each section's columns, its rows, and its row identity, and
nothing else about the list. Summary columns are chosen for scanning — a
Campaign shows its Provider, ad product, baseline budget, and its Product and
Ad Group counts; a Touchpoint its five segments, billing, and response
parameters; a Product its `sku_id`, inventory, and salable state. Every
remaining field stays reachable through the editor, which renders the record
whole.

Data operations render only where `useDeployment().writable` is true. Reported
delivery, spend, outcomes, and paths are never editable in any deployment.
Missing economics remain unavailable rather than becoming zero: a blank
contribution margin is rendered `--`, and missing Cost of Goods Sold is never
treated as zero. Generation Configs is a diagnostic section and renders only
where `useDiagnostics().diagnosticsOn` is true.

#### `Campaigns.vue`

Reported performance filtered by Provider, Product, Campaign, ad product,
marketplace, date, and reporting run. Detail includes configured budget against
actual spend, delivery and outcome metrics, Product economics, interaction
frequencies, path frequencies, length, and transitions. Each list renders as one
`EntityTable`, the same component and the same paging, page size, and filtering
Budget Manager uses, with a row key composed from the fields that distinguish a
record rather than the row's index. A modal finds presentation-only historical
similarity references at a selected threshold and states that they are not used
by attribution or strategy; that modal is the view's one remaining `DataTable`,
because it is a fixed short list inside a dialog rather than a page of records.
When no attribution artifact exists, the view displays “Attribution not
available.”

Database histories may contain 100,000 rows and the view renders that complete
selected history. Chart extrema therefore scan rows and fields iteratively with
constant call-stack usage. They must never spread a history-sized array into
`Math.max()` or `Math.min()`: JavaScript engines impose an argument limit below
the supported history size, and exceeding it aborts the Vue render with a
`RangeError` after the snapshot has loaded.

Budget Manager and Campaigns do not request research observations on component
entry. Their selected deep-link subsection controls the request before the
component mounts. Budget Overview and Campaign Budget History declare the
history slice; entity, performance, bridge, and path tabs declare their own
smaller resources. Navigating between routes reuses completed or in-flight
resources, while a sibling resource remains absent until its route is opened.

The shell mounts a transition card as soon as a route requires an uncached
resource; it never waits three seconds before acknowledging the click. For a live
backend, the resource response streams server milestones — checking the configured
source, reading metadata, reading history, preparing JavaScript Object Notation
(JSON), and transferring bytes. Elapsed time is always visible. The Campaign
History message names that filters and charts are held until the complete,
consistent history slice is ready.

Static builds continue to read generated resource files directly, but show the
same immediate transition and byte progress. A failed load replaces the transition
with the existing actionable error card. Navigating away makes an old progress
report irrelevant without invalidating the shared backend cache.

The four tabs are one `v-if`/`v-else-if`/`v-else` chain, not several. A second
`v-if` opened mid-way ends the first chain, and the trailing `v-else` then
renders under whichever tab is selected — which is exactly the defect 0.9.27
fixed, with the Conversion Paths panel appearing beneath Budget history.

#### `CampaignOptimizer.vue`

One tab per model — MTA attribution, MTA strategy optimization, MTA strategy
evaluation — each carrying its own `StageRunner` above that model's evidence.
The attribution tab shows Markov against Shapley per touchpoint, the governed
recommendation, and the budget shift the recommendation implies; the
optimization tab shows the allocation, its evidence, and its extrapolation and
pooled-transfer warnings; the evaluation tab states why the stage cannot run
yet. Each tab declares the run options its stage accepts — a report window for
attribution, a budget usage policy and total budget for optimization — and
those option values are the same names `normalizeOptions()` validates on the
server, so the offered controls and the accepted arguments cannot diverge
silently.

#### `OptimizationLog.vue`

Run identifiers, the report window, the input digests, the pipeline stage trail, the optimized Campaign budget plan, and the per-touchpoint reliability flags, plus one log tab per model beside them.

Reads `campaignStrategy.optimized_strategy` from the snapshot. The optimized-budget card renders only when the artifact carries a `recommendation_type`, so an absent artifact produces no empty card. A plan with `is_optimized=true` shows the authorized, allocated, and expected-revenue tiles, one row per Campaign with its initial and optimized budget, expected revenue and delta, marginal return, evidence label, and extrapolation flag, followed by named warnings for extrapolated and pooled Campaigns and the two Ad Group disclosure fields. A plan with `is_optimized=false` shows its `recommendation_type` and every `infeasibility_reasons` entry in place of an allocation. Expected revenue is labelled a model estimate, never a realized or guaranteed uplift.

#### `KnowledgeBase.vue`

The five-segment vocabulary, the reliability contract, the Outcomes, capacity rules, the hierarchy, and the artifacts in use.

- Inputs: The tabbed components take a validated `section` prop and emit `navigate` with a declared section key; single-panel components take no route prop. Every component reads data through `useDashboard()`, so a view never holds a path, Structured Query Language (SQL) statement, or `fetch` call.
- Outputs: The rendered page. Nothing is returned and nothing is written.
- Behavior contract: **No production view recomputes attribution or predicts an outcome.** The Campaigns and Budget Manager views may aggregate displayed reported performance into descriptive totals and ratios such as Click-Through Rate (CTR), Cost Per Click (CPC), and Cost Per Mille (CPM); they do not alter source rows. The labelled Willow Sakura contribution is the one isolated exception: its browser-only forecast demonstrates the contributed network and never enters a production artifact or recommendation. The similarity modal uses only a transparent, equal-weight selector heuristic and its objects follow the presentation-only `SimilarityReference` fields. `CampaignOptimizer.vue` retains its labelled constant-total-budget restatement and refuses it for an unreliable Outcome. Reported performance is immutable, filters scope every related panel, and charts retain a table or direct-label alternative. A view may **start** a stage that rewrites those artifacts, through `StageRunner.vue`, but never computes their contents itself: the numbers still come from the pipeline. No view names the research simulator or calls its data generated — a test asserts this against the view sources — because a production deployment reads a live account and a reader told the numbers are invented cannot act on them.
- Dependencies: Vue 3 and Plotly, through `src/lib/useDashboard.js`, `src/lib/common.js`, `src/theme.js`, and the shared components.
- Verification: Rendered in a real browser in all three deployments — the API against PostgreSQL, the API against the committed files, and the static build — with no console error, no failed request, and no error card in any of the six.

### The shared components

Source: `dashboard/src/components/SidebarNav.vue`, `dashboard/src/components/TopBar.vue`, `dashboard/src/components/WillowGmvForecast.vue`, `dashboard/src/components/PlotlyChart.vue`, `dashboard/src/components/DataTable.vue`, `dashboard/src/components/EntityTable.vue`, `dashboard/src/components/ConfirmDialog.vue`, `dashboard/src/components/TableView.vue`, `dashboard/src/components/MetricRow.vue`, `dashboard/src/components/KeyValuePanel.vue`, `dashboard/src/components/ReliabilityBanner.vue`

- Responsibility: Hold the chrome and the repeated display shapes, so two views cannot render the same thing differently.
- Inputs: Props from the view that mounts them.
- Outputs: The rendered fragment, plus events for the rail's navigation, reload, and settings actions.
- Behavior contract: `SidebarNav.vue` draws the flat seven-view rail from `src/pages.js` and pins the settings module to the foot. It renders no section label, group container, disclosure, or reload button. Below `1024px` the same order becomes a horizontally scrollable bar. `SettingsDialog.vue` owns reload and confirmed runtime schema switching; it never renders a stored password or sends one back. In the published build it replaces backend operations with local-run instructions, while a protected team-server deployment keeps credential mutation unavailable. `SchemaRecovery.vue` replaces terminal-only advice on a database load error with backend-declared select, derive, or initialize buttons; it never offers replacement and polls the existing bounded operation log. `TermHelp.vue` and `src/lib/terms.js` provide keyboard-accessible definitions and precise English documentation links without hiding the original labels. `PlotlyChart.vue` is the only component that touches Plotly, so chart defaults in `src/theme.js` cannot be bypassed, and it disposes the plot on unmount. `TableView.vue` keeps every chart paired with readable values. `ReliabilityBanner.vue` always renders the status word beside its colour. `TopBar.vue` leads its tag row with the deployment.

`EntityTable.vue` owns paging, page size, free-text filtering, selection, and the two row controls, and owns nothing about what a row means: columns are declared by the mounting view exactly as `DataTable`'s are. Its default page size is 15, offering 15, 30, 50, and 100. **Selection is keyed by a caller-supplied row identity rather than by page index**, so a batch action cannot act on whatever record happens to occupy that index after the page turns; the selection Set is reassigned rather than mutated, because a Set mutated in place is the same object and Vue's reactivity would not repaint the checkboxes. The header checkbox acts on the current page, which is what it can show. Both components read `renderCell` from `src/lib/common.js`, so one column declaration cannot mean two things in two tables.

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

`ConfirmDialog.vue` is the only route to a deletion. It **names the affected identifiers rather than reporting a count alone**, because a count is not something a reader can check and a batch selected across several pages is exactly the case where a reader cannot see their own selection. The list is capped at twelve with the remainder stated rather than dropped, and the dialog stays open on failure carrying the reason.

`SettingsDialog.vue` separates active selection from setup. Its **Dashboard
schema** field is a dropdown over the census returned by `/api/settings` and
refreshed by a connection test, described in [Backend Jobs and
Settings](../introduction/backend/operations.md#schema-selection). **A schema
that cannot serve the dashboard is listed and disabled rather than omitted**:
omitting it would leave a reader who knows the schema exists with no account
of its absence, while disabling it puts the reason at the moment they would
have chosen it. Each option carries the server's own `detail` as its `title`,
and the same explanation — the reason and tables the schema lacks — is
rendered as help text under the field. The stored selection stays in the list
when the census is empty, so an unreachable database cannot make the dialog
display a schema the reader never chose and then save it.

A protected team-server deployment does not hide that census. It renders a
separate **Database schemas** dropdown whose choices name the active schema,
capability kind, and database structure version. Choosing another
dashboard-ready schema opens the same confirmation window as the editable
selector and reloads actual data without rewriting `PG_SCHEMA` in deployment
configuration. Until a migration ledger exists, the version is displayed as
**not tracked**.

The **Schema setup** menu lists every censused schema, including disabled
active-schema choices, and labels its detected kind and available action.
Simulator sources expose **Parse all scenarios**; empty schemas expose
**Initialize sample model**; a valid new name can initialize a new schema.
Replacement is an explicit checkbox followed by browser confirmation. While
an operation runs, the dialog polls `/api/schema-operations` and shows its
status, exact command, bounded timestamped output, dropped-line count, and stop
control. Success refreshes the census so new targets immediately appear in the
Dashboard schema selector.

**Setup is a sibling of the protected connection form, not a child of it.**
It renders on every deployment with a backend, because writing tables into the
database the platform already named is not the same act as rewriting the
credential that names it; nesting it inside the editable-configuration branch
is what previously made it unreachable on exactly the deployment whose readers
have no other way to prepare a schema. Whether the buttons are enabled comes
from the `available` and `reason` fields the server returns beside the
operation record, so the dialog cannot offer an action the route would refuse,
and a withheld one is explained rather than silently absent. Each option's
summary is the census `remedy`, written for a reader; the `detail` command
stays in the dropdown's `title` for an operator.

Settings begins with a **Deployment identity** block. It renders the dashboard
bundle's project version and full commit
[Secure Hash Algorithm (SHA)](/en/reference/definitions#secure-hash-algorithm-sha-commit-identifier),
followed by the backend's independently detected project version and commit SHA and its
Python and Flask runtime versions. The status is **Builds match** only when both
project versions and both commit values are present and equal. Any unequal
value is **Build mismatch**; a missing or `unknown` value is **Identity
incomplete**. The values are selectable monospace text so an operator can copy
them into a deployment report. A static build states that no backend is
connected rather than comparing the dashboard against itself.

`WillowGmvForecast.vue` renders the contributed forecast inside the evaluation
tab using the dashboard's cards, fields, and metric treatments. It contains no
`iframe`, `srcdoc`, global event handler, or copied navigation shell. Every
control has a stable label and every output updates through Vue state while
remaining independent from the production strategy artifacts.

### `src/lib/willowGmvModel.js`

Source: `dashboard/src/lib/willowGmvModel.js`

- Responsibility: Build the contributor's 27-feature vector and run its two
  hidden rectified-linear layers and capped output entirely in the browser.
- Inputs: The exported model JSON and Willow forecast form values.
- Outputs: Deterministic predicted attributed revenue for the requested budget
  scale, plus the exact feature vector for verification.
- Behavior contract: Budget inputs are non-negative; day and marketplace are
  one-hot encoded in the model's declared order; zero standard deviations are
  treated as one; matrix dimensions must match or throw a named error. The
  ten-percent comparison changes only the four budgets.
- Dependencies: JavaScript standard library only.
- Verification: `dashboard/tests/willow_gmv_model.test.js` and the production
  Vue build.

- Dependencies: Vue 3 and `plotly.js-dist-min`.
- Verification: Exercised in a real browser through the seven views that mount them. `EntityTable.vue`'s paging, page sizes, and identity-keyed selection, `ConfirmDialog.vue`'s named rows, `SettingsDialog.vue`'s schema-selection and census contracts, `TermHelp.vue`'s registry, and `StageRunner.vue`'s progressbar contract are covered by `dashboard/tests/dashboard.test.js`.

### `src/lib/common.js`

Source: `dashboard/src/lib/common.js`

- Responsibility: Hold the label vocabulary and the small aggregations more than one view needs, so two views cannot name the same thing differently.
- Inputs: Rows from the snapshot, plus the reader's selections.
- Outputs: The `OUTCOME_LABELS`, `OUTCOME_SHARE_COLUMNS`, and `OUTCOME_VALUE_COLUMNS` maps; `NUMERIC_FORMATS` and `renderCell()`; `currencySymbol()`, `pretty()`, `shortTouchpoint()`, `shortDate()`, `statusTone()`; and the `sum()`, `maxOf()`, `groupSum()`, `distinct()`, and `sortBy()` helpers.
- Behavior contract: Only presentation lives here; **nothing in this module computes an attribution or budget number** — the values are read from the snapshot and these helpers group, sort, and format them. The three `OUTCOME_*` maps are the single binding between an Outcome key as the pipeline writes it, its display label, and the fields that carry it, so a renamed field is corrected in one place. `shortTouchpoint()` drops the `UNSPECIFIED` segments, which carry no information and would otherwise make every axis label the same length and unreadable. `maxOf()` scans iteratively, ignores non-finite results, and retains its finite floor, so a chart may find an extremum across a 100,000-row history without turning the rows into function arguments. `groupSum()` returns an array in first-seen order rather than a Map, so a chart's category order is stable across reloads. `sortBy()` sorts a copy and pushes non-finite values last, so a missing number never wins a comparison. `renderCell()` is the **single** cell renderer behind both `DataTable` and `EntityTable`, so one column declaration cannot render two ways; it returns `--` for an absent value so a missing number is visibly missing rather than blank, and it flattens an array to a comma-joined list and an object to JSON — the canonical entity records carry both, and `String(value)` renders the first correctly only by accident and the second as `[object Object]`.
- Dependencies: `src/theme.js`, for the four value formatters `renderCell()` dispatches to.
- Verification: Exercised through the views that call it.
