---
title: Page Behavior
compact: "CommandCenter, BudgetManager, Campaigns, CampaignOptimizer, and OptimizationLog display contracts; bounded date windows, density grids, stable ordering and route-owned data loading."
source_files: dashboard/src/views/CommandCenter.vue, dashboard/src/views/BudgetManager.vue, dashboard/src/views/Campaigns.vue, dashboard/src/views/CampaignOptimizer.vue, dashboard/src/views/OptimizationLog.vue
---

# Page Behavior

Each view presents one question using backend-owned artifacts. These contracts
define the evidence and controls that appear when the reader selects a route.


## Source Files

### The five view components

Source: `dashboard/src/views/CommandCenter.vue`, `dashboard/src/views/BudgetManager.vue`, `dashboard/src/views/Campaigns.vue`, `dashboard/src/views/CampaignOptimizer.vue`, `dashboard/src/views/OptimizationLog.vue`

The five share one contract and are specified together.

- Responsibility: Render the five pages of the dashboard, one component per view, in the prototype's navigation order.

#### `CommandCenter.vue`

Five headline tiles, spend against return over time, the per-Outcome reliability verdict, and attributed revenue by ad product for both models.

#### `BudgetManager.vue`

Progressive sub-navigation for Overview, Providers, Products, Campaigns, Ad
Groups, Touchpoints, Product Economics, and Generation Configs. Each of the
seven entity sections renders as one `EntityTable`, per [Canonical entities are
lists, not prose](./entity-lists.md): declared summary
columns as the row abstract, the whole record behind the row's Edit control,
and deletion behind a confirmation that names what it will archive.

The view supplies each section's columns, its rows, and its row identity, and
nothing else about the list. Summary columns are chosen for scanning — a
Campaign shows its Provider, ad product, baseline budget, and its Product and
Ad Group counts; a Touchpoint its five segments, billing, and response
parameters; a Product its `sku_id`, inventory, and salable state. Every
remaining field stays reachable through the editor, which renders the record
whole.

Budget Overview reads the same windowed observation resource as Campaign
History, so its spend, impression, revenue, and margin tiles describe the loaded
period rather than the account's whole record. That period is stated beneath
them: a total labelled "Actual spend" over a slice the reader did not choose and
cannot see is a wrong number, not a partial one.

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
by attribution or strategy. That modal pages through `EntityTable` like every
other list here: a selected Campaign matches every observation sharing its
Provider, which reaches thousands of rows, and an unpaged table would render all
of them into a dialog. Attribution output belongs to Campaign Optimizer, which
owns the models that produce it, and is not restated here.

Database histories may contain 100,000 rows and the view renders that complete
selected history. Chart extrema therefore scan rows and fields iteratively with
constant call-stack usage. They must never spread a history-sized array into
`Math.max()` or `Math.min()`: JavaScript engines impose an argument limit below
the supported history size, and exceeding it aborts the Vue render with a
`RangeError` after the snapshot has loaded.

The same size governs how that history is drawn. Configured budget against
actual spend is a density grid, not a scatter: observations are merged into
`resolution × resolution` cells and the cell's colour is how many fell in it.
A scatter drew one mark per observation, and at a hundred thousand marks roughly
eighty-five per cent landed where another had already drawn, so the ink said
only "something is here" across forty overlapping series whose colours could no
longer be told apart. The count the overplotting hid is the thing worth showing,
so it is the encoded value, and the drawn marks are bounded by the grid rather
than by the row count. The reader chooses the grid from `DENSITY_RESOLUTIONS` —
10, 40, or 100 a side — because a coarse grid reads as shape and a fine one
resolves where a dense band separates. The dashed full-delivery diagonal is
retained; both axes share one bound, since a step along x must be the same
amount as a step along y for that diagonal to mean anything.

`densityGrid` returns a dense row-major matrix with `null` for the cells nothing
fell in, beside `x0`, `dx`, `y0`, and `dy`. That is Plotly's unambiguous heatmap
form: given only the coordinates of the occupied cells it infers brick widths
from the spacing between them, which on a sparse grid draws bricks of uneven
size that misstate where an observation sat. An empty cell is `null` and
`hoverongaps` is false, so "nothing here" is never drawn as the palette's
lightest colour and read as "a few here". A row whose measure is absent is
dropped rather than coerced: `Number(null)` is zero, which would pile absent
observations onto the origin cell.

Series that remain lines or bars are grouped in one pass over the rows rather
than filtered once per Campaign, because a filter per series rescans the whole
history and forty Campaigns therefore mean forty full scans on every filter
change.

The history slice is also bounded before it is sent. The Loaded history window
card requests a `report_date` range from the backend, which appends whole
predicates and binds the dates as SQL parameters — a bound never reaches a query
as text. Narrowing the range therefore shrinks the transfer, which the view's
other filters cannot do: they select within rows the reader has already waited
for. A request naming no range is answered with the most recent quarter rather
than the whole history, which is 36,000 rows and 17.5 MB against 100,000 rows
and 48.6 MB for a first view of a chart. Load everything is a deliberate action
and appears only while the loaded slice is partial; it asks for the observed
range explicitly, because asking for no window is what produced the default.
The payload reports both the window it was read under and the full recorded
range, because a reader cannot infer what was excluded from the rows that
survived it, and the card names the difference whenever the loaded slice is
narrower. `useDashboard` keys its cache by resource and window together, so
widening refetches instead of being answered from the narrower slice, and only
the windowed resources reload — the entity catalogues beside them do not vary
with a date. A static host has whole files and no query to bound, so the same
window is applied to the payload after it arrives and reported the same way; a
view never asks which deployment it is running in.

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

The stream is newline-delimited, and its terminal result frame carries the whole
resource on one line — tens of megabytes for a full Campaign history. The reader
must therefore scan only each newly decoded chunk, holding the pieces of the
line in progress and joining them once its newline arrives. Appending each chunk
to one growing buffer and splitting that buffer per chunk rescans every byte
already received, which makes the cost quadratic in the frame size: a 48 MB
history took tens of seconds of blocked main thread, and because the thread is
blocked the progress report it feeds cannot repaint — so the load appears both
slow and silent. Byte counts are republished per `PROGRESS_BYTE_STEP` rather
than per chunk, since each republish is a reactive write that repaints the bar
and a reader cannot perceive a counter moving every 16 KiB.

Static builds continue to read generated resource files directly, but show the
same immediate transition and byte progress. A failed load replaces the transition
with the existing actionable error card. Navigating away makes an old progress
report irrelevant without invalidating the shared backend cache. The report is
reset when the last in-flight resource finishes rather than left standing: a
route that reuses cached resources starts no request of its own, so a retained
final bar would never be overwritten and would show a stale reading from an
unrelated load.

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
