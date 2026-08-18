---
title: Dashboard Views and Visual Contract
compact: "The six views' shared contract: the two prototype views repointed at real records, the reliability verdict shown beside every attributed share, and the colour, chart, and formatting system in `theme.js`/`style.css`. Specifies the six view components, the shared components, and `lib/common.js`."
lang: en-US
source_files: dashboard/src/theme.js, dashboard/src/style.css, dashboard/src/views/CommandCenter.vue, dashboard/src/views/BudgetManager.vue, dashboard/src/views/Campaigns.vue, dashboard/src/views/CampaignOptimizer.vue, dashboard/src/views/OptimizationLog.vue, dashboard/src/views/KnowledgeBase.vue, dashboard/src/components/SidebarNav.vue, dashboard/src/components/TopBar.vue, dashboard/src/components/SettingsDialog.vue, dashboard/src/components/PlotlyChart.vue, dashboard/src/components/DataTable.vue, dashboard/src/components/TableView.vue, dashboard/src/components/MetricRow.vue, dashboard/src/components/KeyValuePanel.vue, dashboard/src/components/ReliabilityBanner.vue, dashboard/src/lib/common.js
---

# Dashboard Views and Visual Contract

The six views are listed on [Dashboard](./index.md#the-six-views). This page specifies what they share beyond the question each one answers: how the two prototype views without backing data were repointed, the reliability rule every view honors, and the colour, chart, and formatting system every one of them draws from.

Two of the prototype's views had no backing data in this project. Rather than ship placeholder content, each was pointed at the real record that answers the same question: Optimization Log shows run provenance and pipeline stage state, including the fact that the optimisation stage has **not** run; Knowledge Base is populated from the data in use, so it cannot drift from the charts beside it.

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

### The six view components

Source: `dashboard/src/views/CommandCenter.vue`, `dashboard/src/views/BudgetManager.vue`, `dashboard/src/views/Campaigns.vue`, `dashboard/src/views/CampaignOptimizer.vue`, `dashboard/src/views/OptimizationLog.vue`, `dashboard/src/views/KnowledgeBase.vue`

The six share one contract and are specified together.

- Responsibility: Render the six pages of the dashboard, one component per view, in the prototype's navigation order.

#### `CommandCenter.vue`

Five headline tiles, spend against return over time, the per-Outcome reliability verdict, and attributed revenue by ad product for both models.

#### `BudgetManager.vue`

Handoff state, the recommended daily budget per Campaign against its required minimum, the derivation that produced it, the score composition, and the Ad Group slots.

#### `Campaigns.vue`

Three tabs over the historical record: filterable daily performance, the Campaign and Ad Group bridge, and searchable conversion paths.

#### `CampaignOptimizer.vue`

Markov against Shapley per touchpoint, the governed recommendation, and the budget shift the recommendation implies.

#### `OptimizationLog.vue`

Run identifiers, the report window, the input digests, the pipeline stage trail, and the per-touchpoint reliability flags.

#### `KnowledgeBase.vue`

The five-segment vocabulary, the reliability contract, the Outcomes, capacity rules, the hierarchy, and the artifacts in use.

- Inputs: None. Each component takes no props and reads the shared snapshot through `useDashboard()`, so a view never holds a file path, a Structured Query Language (SQL) statement, or a `fetch` call.
- Outputs: The rendered page. Nothing is returned and nothing is written.
- Behavior contract: **No view computes an attribution share or a budget figure.** Every value displayed is read. The single exception is `CampaignOptimizer.vue`'s implied budget shift, which restates the recommended attribution as a spend split at constant total budget; it is labelled as a restatement, does not predict the result of acting on it, never overrides the allocation in `BudgetManager.vue`, and is refused outright when the Outcome's verdict is UNRELIABLE, because an interval cannot carry a spend split. Every view that shows an attributed share shows its reliability verdict beside it. Filters sit in one row above everything they scope, so all panels on a page show the same slice, and every chart is paired with a table view or direct labels, so no value is reachable only by hovering. `OptimizationLog.vue` and `KnowledgeBase.vue` back the two prototype views that had no data of their own: the first reports the real run record and states plainly that the optimisation stage has not run, and the second is populated from the data in use, so it cannot drift from the charts beside it.
- Dependencies: Vue 3 and Plotly, through `src/lib/useDashboard.js`, `src/lib/common.js`, `src/theme.js`, and the shared components.
- Verification: Rendered in a real browser in all three deployments — the API against PostgreSQL, the API against the committed files, and the static build — with no console error, no failed request, and no error card in any of the six.

### The shared components

Source: `dashboard/src/components/SidebarNav.vue`, `dashboard/src/components/TopBar.vue`, `dashboard/src/components/SettingsDialog.vue`, `dashboard/src/components/PlotlyChart.vue`, `dashboard/src/components/DataTable.vue`, `dashboard/src/components/TableView.vue`, `dashboard/src/components/MetricRow.vue`, `dashboard/src/components/KeyValuePanel.vue`, `dashboard/src/components/ReliabilityBanner.vue`

- Responsibility: Hold the chrome and the repeated display shapes, so two views cannot render the same thing differently.
- Inputs: Props from the view that mounts them.
- Outputs: The rendered fragment, plus events for the rail's navigation, reload, and settings actions.
- Behavior contract: `SidebarNav.vue` draws the rail from `src/pages.js` and pins the settings module to the foot, ruled off from the view navigation above it, so it never reads as a seventh destination. `SettingsDialog.vue` never renders a stored password and never sends one back; in the published build it replaces both forms with the local-run instructions rather than offering controls that could not take effect. `PlotlyChart.vue` is the only component that touches Plotly, so the chart defaults in `src/theme.js` cannot be bypassed, and it disposes the plot on unmount so switching views does not leak a chart instance. `TableView.vue` exists so that every chart can be paired with the values behind it, which is what keeps a tooltip an enhancement rather than the only way to read a number. `ReliabilityBanner.vue` always renders the status word beside its colour.
- Dependencies: Vue 3 and `plotly.js-dist-min`.
- Verification: Exercised in a real browser through the six views that mount them.

### `src/lib/common.js`

Source: `dashboard/src/lib/common.js`

- Responsibility: Hold the label vocabulary and the small aggregations more than one view needs, so two views cannot name the same thing differently.
- Inputs: Rows from the snapshot, plus the reader's selections.
- Outputs: The `OUTCOME_LABELS`, `OUTCOME_SHARE_COLUMNS`, and `OUTCOME_VALUE_COLUMNS` maps; `currencySymbol()`, `pretty()`, `shortTouchpoint()`, `shortDate()`, `statusTone()`; and the `sum()`, `groupSum()`, `distinct()`, and `sortBy()` helpers.
- Behavior contract: Only presentation lives here; **nothing in this module computes an attribution or budget number** — the values are read from the snapshot and these helpers group, sort, and format them. The three `OUTCOME_*` maps are the single binding between an Outcome key as the pipeline writes it, its display label, and the fields that carry it, so a renamed field is corrected in one place. `shortTouchpoint()` drops the `UNSPECIFIED` segments, which carry no information and would otherwise make every axis label the same length and unreadable. `groupSum()` returns an array in first-seen order rather than a Map, so a chart's category order is stable across reloads. `sortBy()` sorts a copy and pushes non-finite values last, so a missing number never wins a comparison.
- Dependencies: None.
- Verification: Exercised through the views that call it.
