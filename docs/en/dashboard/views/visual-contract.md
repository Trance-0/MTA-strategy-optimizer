---
title: "Visual Contract"
compact: "Theme palettes, fixed entity colors, chart axes and paired readable values, shared LogViewer styling, option-row primitives, safe ratios, calendar aggregation and exported chart values."
source_files: dashboard/src/theme.js, dashboard/src/style.css, dashboard/src/lib/common.js, dashboard/src/lib/chartData.js
---

# Visual Contract

`dashboard/src/theme.js` holds every colour, chart default, and value format, and `dashboard/src/style.css` reads the same values as custom properties, so a change lands everywhere at once and no view invents its own styling. The brand palette — navy rail, blue accent, light plane — is the prototype's. The series palette is a separate validated set, because the prototype contains no real charts and so could not supply one; it passes the lightness band, chroma floor, colourblind-separation, and normal-vision checks against the dashboard's white chart surface.

Single-column page grids shrink below long identifiers; source fingerprints,
run labels and report text wrap without enlarging the viewport. Download
links are temporarily attached to the document; their object address remains
valid through browser handoff before cleanup. Native selects
fit their fields and model tabs wrap on narrow screens.

Three rules the views depend on:

- **Colour follows the entity, never its rank.** Markov is always the same blue and Shapley always the same orange, so filtering a chart never repaints the rows that survive and a reader who learned one association is never contradicted.
- **Status colour is reserved and never carries meaning alone.** A reliability pill always shows the status word itself.
- **One axis per chart.** Amount and ratio measures use separate plots with their own units. Spend and sales may share a currency axis; return on ad spend uses a separate ratio axis. No amount is rescaled into a ratio background.

Every chart is paired with the values behind it — a table view, direct labels, or both — so no number is reachable only by hovering.

## Option Rows

The dashboard has exactly two form shapes, and which one a control takes is decided by what the control is for.

**An option is one row: its name on the left, the control that changes it on the right.** This holds for every control type — a select, a text field, a toggle, a button that carries out the option's action, or a read-only value. A reader who has learned where the name is and where the control is on one page finds both in the same place on the next, so the shape is a single set of primitives rather than a per-view layout:

#### `.setting-group`

A titled section. Its `> header` carries the heading and the sentence that qualifies the rows below it.

#### `.setting-row`

One option. A `<label>` when it wraps its own control, so the whole row is the hit target.

#### `.setting-label`

The option's name, with its helper sentence in a nested `<small>`.

#### `.setting-control`

The control, held to `min(300px, 46%)` and aligned to the row's right edge.

#### `.setting-block`

Content in a group that is not an option: a notice, an action bar, a command block.

Each option carries a helper sentence under its name saying what the setting changes and what the alternative does. It is held back only where the label already says everything — a standard connection parameter, a field whose name is its own definition — because a sentence under every row buries the rows that carry a real consequence.

`.field` inside `.filter-row` is the other shape, and it is not a settings shape. It is a toolbar: a strip of compact controls that narrow or parameterise the content directly below them, read left to right, each label stacked above its control. A filter strip is scanned; an option row is filled in. The same field is never rendered as a stacked `.field` in one view and a `.setting-row` in another — the PostgreSQL connection parameters appear on both Settings and the Data Generator export, and both are option rows.

Two consequences the views depend on:

- **A control is never aligned to the opposite side of the one beside it.** A row puts its control on the right; a standalone action bar (`.rec-actions`) aligns left, everywhere, with the primary action last. A button split to the far edge of the title it belongs to moves with the length of that title, so no two cards agree on where their buttons are. An empty or `&nbsp;` `<label>` is never used to align a button with the fields beside it: a label wrapping no control is a defect a screen reader reports.
- **A replaced native control keeps the native input.** `.switch` restyles a checkbox through `appearance: none` and an `::after` knob while the `<input type="checkbox">` stays in the markup, so focus, keyboard operation, and assistive-technology behaviour are the browser's rather than reimplemented.

Below 760px a row stacks and its control takes the full width. The reading order does not change: the name is still first.

`tests/dashboard.test.js` asserts that every view carrying options uses these classes, that no second row primitive exists beside them, and that no component ships a private stylesheet — a scoped block cannot read the custom properties `theme.js` writes, so a deployment's accent would not reach it.

All operational log surfaces use `LogViewer.vue` and the shared `.log-viewer`,
`.log-stream`, `.log-row` and metadata classes. Log controls form a left-aligned
`.rec-actions` row directly above output. Messages preserve whitespace, wrap
long lines and remain selectable; one light log surface replaces separate run,
task and schema themes. Metadata remains subordinate and stderr is distinguished
without claiming every stderr message is a failure.

## Source Files

### `src/theme.js` and `src/style.css`

Source: `dashboard/src/theme.js`, `dashboard/src/style.css`

- Responsibility: Hold every colour, chart default, and value format the dashboard uses, so a change lands everywhere at once and no view invents its own styling.
- Inputs: None. Constants and pure display helpers.
- Outputs: The brand constants, the reserved status colours and their tone classes, the `SERIES`, `SEQUENTIAL`, and `DIVERGING` palettes, the fixed `MODEL_COLORS` and `OUTCOME_COLORS` maps, `seriesColors()`, `layout()`, `PLOT_CONFIG`, and the `money()`, `compactMoney()`, `count()`, `percent()`, and `ratio()` formatters. `style.css` exposes the same brand values as custom properties for the markup, and holds the option-row primitives above.
- Behavior contract: `style.css` is the **only** stylesheet in the client — no component carries a `<style>` block, because a scoped block cannot read the custom properties `theme.js` sets and would silently keep its own colours when a deployment changes accent. There is one row primitive for options and one for toolbars, and a view uses the shared class rather than restating the shape. `SERIES` is a fixed order assigned by slot and **never cycled**; a ninth series folds into "Other" rather than receiving a generated hue, which under colourblind simulation would be indistinguishable from an existing slot. `MODEL_COLORS` and `OUTCOME_COLORS` bind a colour to an entity rather than to a rank, so filtering a chart never repaints the rows that survive. The status colours are reserved for reliability state, are never reused as a series colour, and are always rendered with the status word beside them. `layout()` sets a hairline grid, solid axes, and a height that includes the axis band, so a chart card never grows an inner scrollbar; every chart is titled by the heading above it, so no figure carries a title of its own. Each formatter returns `--` for a value that is not finite, so a missing number is visibly missing rather than rendered as `NaN`. The series palette is not the prototype's: that design contains no real charts, so its three brand colours could not supply one.
- Dependencies: None.
- Verification: Rendered visually. The palette is checked with the data-visualisation validator against the white chart surface; three light-mode hues fall below 3:1 contrast, which is why every chart also ships direct labels or a table view.

`theme.js` additionally exports `DEPLOYMENT_THEMES`, the two accent sets described above. They live here because they are colours, and `tests/dashboard.test.js` asserts they never intersect `SERIES`, `MODEL_COLORS`, or `OUTCOME_COLORS`.


### `src/lib/common.js`

Source: `dashboard/src/lib/common.js`

- Responsibility: Hold the label vocabulary and the small aggregations more than one view needs, so two views cannot name the same thing differently.
- Inputs: Rows from the snapshot, plus the reader's selections.
- Outputs: The `OUTCOME_LABELS`, `OUTCOME_SHARE_COLUMNS`, and `OUTCOME_VALUE_COLUMNS` maps; `NUMERIC_FORMATS`, `renderCell()`, `nextTableSort()`, and `sortTableRows()`; `currencySymbol()`, `pretty()`, `shortTouchpoint()`, `shortDate()`, `statusTone()`; and the `sum()`, `maxOf()`, `densityGrid()`, `groupSum()`, `distinct()`, and `sortBy()` helpers.
- Behavior contract: Only presentation lives here; **nothing in this module computes an attribution or budget number** — the values are read from the snapshot and these helpers group, sort, and format them. The three `OUTCOME_*` maps are the single binding between an Outcome key as the pipeline writes it, its display label, and the fields that carry it, so a renamed field is corrected in one place. `shortTouchpoint()` drops the `UNSPECIFIED` segments, which carry no information and would otherwise make every axis label the same length and unreadable. `maxOf()` scans iteratively, ignores non-finite results, and retains its finite floor, so a chart may find an extremum across a 100,000-row history without turning the rows into function arguments. `densityGrid()` merges rows into a `resolution × resolution` count matrix in one pass, so the marks a chart draws are bounded by the grid rather than by the row count; it clamps a value sitting exactly on the bound into the last cell rather than addressing one past the end, leaves an empty cell `null` so it is never drawn as a low count, and drops a row whose measure is absent rather than coercing it to the origin. `groupSum()` returns an array in first-seen order rather than a Map, so a chart's category order is stable across reloads. `sortBy()` sorts a numeric copy and pushes non-finite values last, so a missing number never wins a comparison. `nextTableSort()` owns the ascending, descending, and unsorted cycle; `sortTableRows()` compares numeric columns numerically and all other displayed values with a case-insensitive natural alphabetic order, keeps missing values last, preserves source order for equal values, and returns source order unchanged in the unsorted state. `renderCell()` is the **single** cell renderer behind both `DataTable` and `EntityTable`, so one column declaration cannot render two ways; it returns `--` for an absent value so a missing number is visibly missing rather than blank, and it flattens an array to a comma-joined list and an object to JSON — the canonical entity records carry both, and `String(value)` renders the first correctly only by accident and the second as `[object Object]`.
- Dependencies: `src/theme.js`, for the four value formatters `renderCell()` dispatches to.
- Verification: Exercised through the views that call it.

### `src/lib/chartData.js`

Source: `dashboard/src/lib/chartData.js`

Responsibility: pure chart aggregation and export, without attribution or
optimization mathematics. Inputs are observation rows, daily/weekly/monthly
calendar grouping and declared columns. Outputs are sorted additive totals and
ratios recomputed from those totals; weeks start Monday in coordinated universal
time. Missing numerators/denominators or zero denominators produce null. Empty
datasets remain empty. Export uses exactly the displayed filtered/grouped rows,
raw finite values and blank unavailable values, with correct comma, quote and
newline escaping. Text beginning with spreadsheet formula characters is escaped.
Dependencies: none. Verification: `dashboard/tests/chart_data.test.js`, including
calendar boundaries, unequal spend weights, missing versus zero and 100,000 rows.
