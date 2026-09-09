---
title: Analysis Workbench Experience
name: Analysis Workbench
compact: "Behavioral contract for dataset ingestion and selection, source-aware analysis, revisioned budgets, isolated runs, formal evaluation, history, recovery, keyboard access and narrow layouts; covers FR-1 through FR-15."
status: final
updated: 2026-09-08
sources: [prd.md, decision-log.md, DESIGN.md, ../navigation.md, ../views/stage-execution.md, ../../strategy-evaluation/evaluation-layers.md]
---

# Analysis Workbench Experience

Terms used below: Application Programming Interface (API).

## Foundation

Responsive browser application, primarily used on a desktop. Inherit the
existing Vue components, Plotly chart system and [visual identity](./DESIGN.md).
The approved Product Requirements Document (PRD) owns release scope through
Functional Requirements (FR); existing model specifications own mathematics.
This contract defines the new behavior
and necessary changes to existing interaction. It does not claim those changes
are already implemented.

One dataset is active per browser context. Saved inputs, plans and runs have
separate identities. Source selection changes the displayed observations;
historical filters change their presentation; running a model creates a new
result. These are three explicit actions and must remain distinguishable.

## Information Architecture

Keep the eight existing destinations and existing subsection links. Add only
`generator/import` for Import Data and `budget/plans` for Budget Plans. Global
dataset context remains outside the page resource-loading boundary.

#### Command Center

Dataset scope, available performance totals, time grouping, contribution
rankings, and next available model action. Registered observations without a
model result still have a usable overview.

#### Data Generator

Configure retains the complete generator editor and its configuration guards.
Successful generation adds dataset registration status and Use for analysis.
Import Data hosts template download, file roles, validation, preview and import.

#### Budget Manager

Budget Plans lists and edits saved revisions; Overview retains observed history
and existing initial allocation evidence. The other master-data sections remain
draft editors, explicitly unconnected to model execution.

#### Campaigns

Existing performance, history, entity bridge and paths tabs gain source-aware
filters, groupings, rankings, readable values and exports where input supports
them. Detail stays in the current page and preserves the filter context.

#### Campaign Optimizer

Existing attribution, optimization and evaluation tabs retain independent stage
entry points. Each shows its selected dataset and chosen result identity.
Formal evaluation sits above the separately labeled Willow demonstration.

#### Optimization Log

Provenance and stage tabs expose run history, stage status, inputs, parameters,
plan revision, target strategy and available downloads. Opening an older record
does not switch global dataset selection.

#### Knowledge Base

Dataset vocabulary, entities and source references follow the current dataset.
Fixed Ontology Review remains a distinct demonstration. No current-plan
approval is inferred from those cases.

#### Settings

General, Data source, Logging and Tasks stay independently reachable. Add runtime
storage and model readiness to their appropriate existing sections; Tasks links
to persisted run records and interrupted status. Do not duplicate credential
configuration in dataset import.

## Voice and Tone

Use English, direct action labels and business terms. Explain abbreviations in
existing term help. Use Not run for absent results; No observations in this
range for an empty filter; Insufficient evidence with the actual missing input
for an unavailable model. Failed describes an operation or named check, not
the dataset as a whole. A transport failure says the request failed and offers
Retry; it never announces that a background job definitely failed.

Import errors identify the input role and row or field. Budget policy labels
reuse the backend's supported vocabulary. Baseline comparison states that it
measures agreement with observed efficiency, not promised future revenue.
Metadata text uses {colors.muted}; essential limitations use {colors.text}.

## Component Patterns

#### Dataset context

The selector shows registered datasets plus explicit existing-source choices.
Persist the selected identifier in browser storage. Selecting a dataset clears
prior model selections and replaces observations through a fresh load; late
responses from older context cannot merge. Missing stored identifiers produce
an explanatory selection state, never an automatic sample substitution.
Show source, market, currency, dates, counts and capability reasons beneath the
name using {components.dataset-context.background}.

Changing context does not erase unsaved generator or plan edits. Bind drafts
to their original dataset and explain the mismatch; save or discard explicitly
before running them. Generator edits remain independent of analysis selection.

#### Import panel

Choose a name and required performance file, with optional paths and research
files. Standard Comma-Separated Values (CSV) and JavaScript Object Notation
(JSON) templates describe input roles; no arbitrary column mapping is offered.
Validate returns limited preview, counts, scope, issues and capabilities. Any
input edit invalidates that validation. Import is an explicit action and
revalidates server-side. Successful import offers Use for analysis and keeps
the existing selection until pressed. External Application Programming
Interface (API) pushes appear in the same dataset list after refresh.

#### Analysis card

Group by day, week or month; sum additive values and recompute ratios from
their totals. Amount and ratio figures stay separate on
{components.analysis-card.background}. Show source, scope, units and sample
size. A table exposes the same grouped or filtered values with full precision;
Export downloads the current selection. Missing measures remain unavailable.
Ranking selection opens matching detail, with Back to ranking and Reset filters.
Provide an equivalent table action for every plot selection. Category colors
remain stable; overflow categories group as Other with underlying rows reachable.

#### Plan editor

Select or create a named plan bound to the active dataset. Edit positive total
budget and a supported usage policy, then Save revision. Show saved revision
and unsaved changes separately. Run saved revision consumes the server's saved
record, not the current form. A stale revision conflict preserves local input
and offers Reload latest; it never overwrites another edit. A changed dataset
does not retarget the plan. Display Not connected to model runs on other entity
drafts near their edit controls.

#### Stage runner

For registered data, show the shared dataset and server-reported eligibility;
do not offer a second unrelated legacy dataset choice. Keep legacy runners
only within explicit legacy context. Optimization accepts a saved plan revision
or the stage's existing validated options. Evaluation requires a successful
same-dataset strategy run, visibly named before Run. Invalid prerequisites
disable Run with a remedy, without blocking independent models.

Progress uses reported phases and actual percentage only; keep log, stop and
result actions in the existing order. Completion offers View results rather
than silently swapping currently read values. Display input range on every
result; changing a historical date filter does not refit it.

#### Evaluation report

Read the production `strategyEvaluation` artifact belonging to the selected
evaluation run. Present each strategy's conservation and contract violations,
baseline comparisons, skipped strategies and reasons. Missing optimal-allocation
truth displays Not run. Check failures do not hide remaining layers. A successful
process may contain failed checks: show both. Use the status word beside
{colors.success}, {colors.warning} or {colors.error}; do not construct a new
combined score or interpret historical baselines as causal benefit.

#### Run history

Filter by dataset, model, date and state. Opening a run shows its immutable
input summary, digest, options, plan revision, execution times and result files.
Explicitly label historical selection. Only completed, declared artifacts have
download actions. Retry creates a new run identity and preserves the original.
Show interrupted after restart for work that was active, never a fabricated
success or silent rerun. Use {components.run-history.background}.

#### Recovery panel

Keep source selection and Settings available while data loading fails. Explain
whether the source, storage or model capability caused the problem. Retry a
failed read explicitly; retain drafts after write failure. Generation whose
registration fails retains existing previews and downloads and reports that no
analysis dataset was registered. Database mutations retain existing protection
and confirmation behavior; import does not imply database replacement.

#### Reference panel

Dataset-owned vocabulary and entities label their current source. Missing
reference data displays unavailable rather than fixed filler content. Ontology
Review and Willow explicitly name their demonstration identity and retain it
through dataset switches. Use {components.reference-panel.background}.

## State Patterns

All data surfaces distinguish initial loading, loaded, empty, failed and stale
requests. Initial loading uses the existing progress component; no previous
dataset's figures appear under a new dataset label. Empty capabilities replace
only their affected card. A failed resource does not disable unrelated routes.
Background completion and refreshed history do not steal keyboard focus.

Generator and import additionally distinguish editing, validating, valid,
invalid, submitting and complete. Plans distinguish unsaved, saving, saved and
revision conflict. Runners distinguish unavailable, queued, running, stopping,
completed, failed, cancelled and interrupted according to actual server state.
Reports separately retain check-level passed, failed, skipped and not-run states.
History and reference tabs have explicit no-records states.

An offline or unreachable backend disables new dependent operations after an
error and offers Retry; do not promise local queued writes or automatic sync.
Denied or protected operations explain the existing deployment restriction.
Static mode labels the demonstration and disables backend mutations locally
without issuing requests. Read-only is a deployment capability, not a reason
to treat all simulated datasets as immutable demonstration content.

## Interaction Primitives

Buttons and native selectors perform primary actions. Enter submits only the
focused form action; it does not accidentally start a run from an input.
Tabs preserve canonical links and browser Back/Forward. Ranking detail preserves
filters and returns focus to the invoking row. Plot hover is supplementary.
Only existing destructive operations require confirmation; data selection,
validation and saving a new revision do not add blanket approval dialogs.

Dialogs keep focus inside, Escape closes the topmost dismissible dialog, and
closing restores the trigger. Critical error summaries receive focus after a
submitted invalid form; background polling never moves focus. Live status
announces phase or terminal changes without reading every log line aloud.

## Accessibility Floor

Every input has a persistent label and field errors linked to it. Disabled
actions have adjacent readable reasons. Selected navigation and tabs expose
their state; lists and tables use actual headings, captions and sortable-column
state. Use existing focus treatment with a visible 3:1 boundary rather than
removing outlines. Contrast targets live in DESIGN.md.

Keyboard operation covers dataset selection, import, plan editing, running,
stopping, result selection, sorting, pagination, export and recovery. All graph
values and drill-down actions are available without hover. At 200% zoom no
essential control or limitation is clipped. Reduced motion suppresses optional
transitions; progress information remains readable. No new global key bindings
override browser or assistive-technology shortcuts.

## Responsive & Platform

Inherit the existing rail-to-horizontal-bar change at 1024 pixels. At 760 pixels
and below, new filters, paired cards and editor fields stack with
{spacing.narrow-inset}; action labels wrap instead of disappearing. Wide data
tables scroll inside their container and keep paging controls reachable. The
same operations work at a 375-pixel viewport; this release adds no native app,
offline editing system or alternate mobile information architecture.

## Key Flows

The protagonist is **the requesting analyst** from the approved working session;
this role names a test actor, not a fabricated biography or persona study.

### Flow 1 — Register generated data and inspect source-consistent results

1. The requesting analyst configures and runs Data Generator (FR-1).
2. On successful registration, they select Use for analysis (FR-3).
3. Command Center shows that dataset's scope, totals and capability reasons
   (FR-4, FR-5, FR-6).
4. They group history, select a ranking item and export its readable values
   (FR-7).
5. **Climax:** changing the dataset produces different observations and clearly
   shows Not run for missing model results, rather than reusing the first set.

Failure: invalid configuration retains edits; failed registration retains
generated downloads and reports the missing dataset. No active data is replaced.

### Flow 2 — Import external observations and verify their meaning

1. The requesting analyst opens Import Data and downloads the standard template.
2. They choose files, validate, inspect preview and correct field issues (FR-2).
3. They import and explicitly select the new dataset; an externally pushed
   dataset can instead be selected from the refreshed list (FR-3).
4. They inspect its capabilities and Knowledge Base source references
   (FR-4, FR-14).
5. **Climax:** overview and historical detail reflect the imported observations,
   while fixed reference examples remain visibly separate demonstrations.

Failure: mixed scope or invalid references prevent publication and name the
input to fix. A performance-only dataset still supports available charts.

### Flow 3 — Save a budget, run a strategy and read its evidence

1. The requesting analyst opens Budget Plans, saves a named revision and sees
   that other entity drafts remain unconnected (FR-9).
2. They run the saved revision against eligible observations; independent
   attribution is available without a false sequence requirement (FR-10).
3. They explicitly open completed results and inspect model limitations
   alongside allocations (FR-8).
4. They select that strategy run for evaluation (FR-11).
5. **Climax:** the report identifies exactly which strategy passed or failed
   each check and which evidence is absent; it makes no future-revenue promise.

Failure: missing fitting evidence explains the requirement before submission.
A failed run publishes no partial result. Editing the plan creates a new
revision without changing the earlier run's inputs.

### Flow 4 — Retrieve and recover a prior analysis

1. The requesting analyst returns after backend restart and reselects a saved
   dataset (FR-3, FR-13).
2. They open Optimization Log, filter history and inspect a run's source,
   revision and downloads without switching current context (FR-12).
3. If a run was interrupted, they explicitly retry it; if storage or source
   fails, Settings remains reachable for diagnosis (FR-13).
4. **Climax:** previous completed results remain accessible and a retry is a
   separate traceable execution.

Failure: in static deployment the analyst reads the labeled demonstration;
backend actions state their limitation and do not issue requests (FR-15).

## Handoff and Coverage

All eight destinations and shared components are spine-only, as authorized for
the existing-theme Fast path. No new visual assets or external mock references
exist to reconcile. The four flows cover FR-1 through FR-15, including failure
and capability boundaries. No product questions remain open. Browser validation
must prove source switching, stale-response protection, keyboard actions,
375-pixel layout, zoom, chart/table/export agreement and Settings recovery;
document review alone is not evidence that these behaviors work.
