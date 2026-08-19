---
title: Dashboard Views and Visual Contract
compact: "Six Vue views and shared components: deployment capability drives accent and data operations, canonical entities render as paged selectable tables with confirmed deletion, generated-history filters, presentation-only similarity, read-only attribution, chart/table accessibility, and SettingsDialog behavior."
lang: en-US
source_files: dashboard/src/theme.js, dashboard/src/style.css, dashboard/src/lib/deployment.js, dashboard/src/views/CommandCenter.vue, dashboard/src/views/BudgetManager.vue, dashboard/src/views/Campaigns.vue, dashboard/src/views/CampaignOptimizer.vue, dashboard/src/views/OptimizationLog.vue, dashboard/src/views/KnowledgeBase.vue, dashboard/src/components/SidebarNav.vue, dashboard/src/components/TopBar.vue, dashboard/src/components/SettingsDialog.vue, dashboard/src/components/PlotlyChart.vue, dashboard/src/components/DataTable.vue, dashboard/src/components/EntityTable.vue, dashboard/src/components/ConfirmDialog.vue, dashboard/src/components/TableView.vue, dashboard/src/components/MetricRow.vue, dashboard/src/components/KeyValuePanel.vue, dashboard/src/components/ReliabilityBanner.vue, dashboard/src/lib/common.js
---

# Dashboard Views and Visual Contract

The six views are listed on [Dashboard](./index.md#the-six-views). This page specifies what they share beyond the question each one answers: how the two prototype views without backing data were repointed, the reliability rule every view honors, and the colour, chart, and formatting system every one of them draws from.

Two of the prototype's views had no backing data in this project. Rather than ship placeholder content, each was pointed at the real record that answers the same question: Optimization Log shows run provenance and pipeline stage state; Knowledge Base is populated from the data in use, so it cannot drift from the charts beside it.

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

Deletion archives a future-run draft. It never removes a generated historical observation, which no route mutates in either mode.

### An empty section names its cause

These records come from a generated MTA-SIM run, which the committed sample artifacts do not carry. The published build therefore shows every entity section empty, and this is the expected state rather than a fault. Each empty section says so and names the remedy — `MTA_SIM_DATA_DIR` for a file-mode run, `script/import_to_database.py` for a database — because "No records loaded" alone reads as a broken deployment.

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

Data operations render only where `useDeployment().writable` is true. Generated
delivery, spend, outcomes, and paths are never editable in any deployment.
Missing economics remain unavailable rather than becoming zero: a blank
contribution margin is rendered `--`, and missing Cost of Goods Sold is never
treated as zero.

#### `Campaigns.vue`

Generated historical evidence filtered by Provider, Product, Campaign, ad
product, marketplace, date, and simulation run. Detail includes configured
budget against actual spend, delivery and outcome metrics, Product economics,
interaction frequencies, path frequencies, length, and transitions. A modal
finds presentation-only historical similarity references at a selected
threshold and states that they are not used by attribution or strategy. When
no attribution artifact exists, the view displays “Attribution not available.”

#### `CampaignOptimizer.vue`

Markov against Shapley per touchpoint, the governed recommendation, and the budget shift the recommendation implies.

#### `OptimizationLog.vue`

Run identifiers, the report window, the input digests, the pipeline stage trail, the optimized Campaign budget plan, and the per-touchpoint reliability flags.

Reads `campaignStrategy.optimized_strategy` from the snapshot. The optimized-budget card renders only when the artifact carries a `recommendation_type`, so an absent artifact produces no empty card. A plan with `is_optimized=true` shows the authorized, allocated, and expected-revenue tiles, one row per Campaign with its initial and optimized budget, expected revenue and delta, marginal return, evidence label, and extrapolation flag, followed by named warnings for extrapolated and pooled Campaigns and the two Ad Group disclosure fields. A plan with `is_optimized=false` shows its `recommendation_type` and every `infeasibility_reasons` entry in place of an allocation. Expected revenue is labelled a model estimate, never a realized or guaranteed uplift.

#### `KnowledgeBase.vue`

The five-segment vocabulary, the reliability contract, the Outcomes, capacity rules, the hierarchy, and the artifacts in use.

- Inputs: None. Each component takes no props and reads the shared snapshot through `useDashboard()`, so a view never holds a file path, a Structured Query Language (SQL) statement, or a `fetch` call.
- Outputs: The rendered page. Nothing is returned and nothing is written.
- Behavior contract: **No view recomputes attribution or predicts an outcome.** The Campaigns and Budget Manager views may aggregate displayed generated observations into descriptive totals and ratios such as Click-Through Rate (CTR), Cost Per Click (CPC), and Cost Per Mille (CPM); they do not alter source rows. The similarity modal uses only a transparent, equal-weight selector heuristic and its objects follow the presentation-only `SimilarityReference` fields. `CampaignOptimizer.vue` retains its labelled constant-total-budget restatement and refuses it for an unreliable Outcome. Generated history is immutable, filters scope every related panel, and charts retain a table or direct-label alternative.
- Dependencies: Vue 3 and Plotly, through `src/lib/useDashboard.js`, `src/lib/common.js`, `src/theme.js`, and the shared components.
- Verification: Rendered in a real browser in all three deployments — the API against PostgreSQL, the API against the committed files, and the static build — with no console error, no failed request, and no error card in any of the six.

### The shared components

Source: `dashboard/src/components/SidebarNav.vue`, `dashboard/src/components/TopBar.vue`, `dashboard/src/components/SettingsDialog.vue`, `dashboard/src/components/PlotlyChart.vue`, `dashboard/src/components/DataTable.vue`, `dashboard/src/components/EntityTable.vue`, `dashboard/src/components/ConfirmDialog.vue`, `dashboard/src/components/TableView.vue`, `dashboard/src/components/MetricRow.vue`, `dashboard/src/components/KeyValuePanel.vue`, `dashboard/src/components/ReliabilityBanner.vue`

- Responsibility: Hold the chrome and the repeated display shapes, so two views cannot render the same thing differently.
- Inputs: Props from the view that mounts them.
- Outputs: The rendered fragment, plus events for the rail's navigation, reload, and settings actions.
- Behavior contract: `SidebarNav.vue` draws the rail from `src/pages.js` and pins the settings module to the foot, ruled off from the view navigation above it, so it never reads as a seventh destination. `SettingsDialog.vue` never renders a stored password and never sends one back; in the published build it replaces both forms with the local-run instructions, while a protected team-server deployment replaces the credential form with the server-configuration instruction and disables every logging mutation. `PlotlyChart.vue` is the only component that touches Plotly, so the chart defaults in `src/theme.js` cannot be bypassed, and it disposes the plot on unmount so switching views does not leak a chart instance. `TableView.vue` exists so that every chart can be paired with the values behind it, which is what keeps a tooltip an enhancement rather than the only way to read a number. `ReliabilityBanner.vue` always renders the status word beside its colour. `TopBar.vue` leads its tag row with the deployment, because which deployment this is governs how every other number on the page may be used.

`EntityTable.vue` owns paging, page size, free-text filtering, selection, and the two row controls, and owns nothing about what a row means: columns are declared by the mounting view exactly as `DataTable`'s are. Its default page size is 15, offering 15, 30, 50, and 100. **Selection is keyed by a caller-supplied row identity rather than by page index**, so a batch action cannot act on whatever record happens to occupy that index after the page turns; the selection Set is reassigned rather than mutated, because a Set mutated in place is the same object and Vue's reactivity would not repaint the checkboxes. The header checkbox acts on the current page, which is what it can show. Both components read `renderCell` from `src/lib/common.js`, so one column declaration cannot mean two things in two tables.

`ConfirmDialog.vue` is the only route to a deletion. It **names the affected identifiers rather than reporting a count alone**, because a count is not something a reader can check and a batch selected across several pages is exactly the case where a reader cannot see their own selection. The list is capped at twelve with the remainder stated rather than dropped, and the dialog stays open on failure carrying the reason.
- Dependencies: Vue 3 and `plotly.js-dist-min`.
- Verification: Exercised in a real browser through the six views that mount them.

### `src/lib/common.js`

Source: `dashboard/src/lib/common.js`

- Responsibility: Hold the label vocabulary and the small aggregations more than one view needs, so two views cannot name the same thing differently.
- Inputs: Rows from the snapshot, plus the reader's selections.
- Outputs: The `OUTCOME_LABELS`, `OUTCOME_SHARE_COLUMNS`, and `OUTCOME_VALUE_COLUMNS` maps; `NUMERIC_FORMATS` and `renderCell()`; `currencySymbol()`, `pretty()`, `shortTouchpoint()`, `shortDate()`, `statusTone()`; and the `sum()`, `groupSum()`, `distinct()`, and `sortBy()` helpers.
- Behavior contract: Only presentation lives here; **nothing in this module computes an attribution or budget number** — the values are read from the snapshot and these helpers group, sort, and format them. The three `OUTCOME_*` maps are the single binding between an Outcome key as the pipeline writes it, its display label, and the fields that carry it, so a renamed field is corrected in one place. `shortTouchpoint()` drops the `UNSPECIFIED` segments, which carry no information and would otherwise make every axis label the same length and unreadable. `groupSum()` returns an array in first-seen order rather than a Map, so a chart's category order is stable across reloads. `sortBy()` sorts a copy and pushes non-finite values last, so a missing number never wins a comparison. `renderCell()` is the **single** cell renderer behind both `DataTable` and `EntityTable`, so one column declaration cannot render two ways; it returns `--` for an absent value so a missing number is visibly missing rather than blank, and it flattens an array to a comma-joined list and an object to JSON — the canonical entity records carry both, and `String(value)` renders the first correctly only by accident and the second as `[object Object]`.
- Dependencies: `src/theme.js`, for the four value formatters `renderCell()` dispatches to.
- Verification: Exercised through the views that call it.
