---
title: Analysis Workbench Controls
compact: "Dataset selection/import, revisioned plan forms, retained run controls, formal evaluation and history components; shared workbench store cold-route hydration, race protection, offline capability recovery and static refusals."
source_files: dashboard/src/lib/useWorkbench.js, dashboard/src/components/DatasetContext.vue, dashboard/src/components/DatasetImport.vue, dashboard/src/components/BudgetPlans.vue, dashboard/src/components/WorkbenchRunner.vue, dashboard/src/components/RunHistory.vue, dashboard/src/components/EvaluationReport.vue
---

# Analysis Workbench Controls

These controls connect the [dataset](./datasets.md) and
[budget plan](./budget-plans.md) contracts to existing Dashboard routes. The
browser requests no database credentials and never computes model results.

## Source Files

### useWorkbench.js

Source: `dashboard/src/lib/useWorkbench.js`

Responsibility: shared dataset catalogue, selected-data plan/run lists, detail
loading and mutation state through `api/client.js`. Inputs are user actions and
server descriptors; outputs are reactive loading/error/available states and
immutable records. A context generation discards stale lists and errors after
selection changes. The list scope is reactive: opening a direct route with a
persisted dataset identifier may initially read empty lists, but the first
matching refresh must expose its plans, runs and errors without another dataset
selection. Refresh preserves the selected dataset; mutation completion
must not overwrite another selection. Failed refresh retains a readable error,
with an explicit retry. Dependencies: Vue, client and dashboard store.
When the current-context list request fails, disable runtime writes and model
execution with the request error until an explicit successful refresh restores
those capabilities. An older context's failure cannot revoke newer capabilities.
Runtime writability and catalogue readability are separate fields; retry checks
both. Capability probes omit the dataset filter; a blank browser selection must not
be sent as an invalid dataset identity. Verification: transport and reordered-response tests.

### DatasetContext.vue and DatasetImport.vue

Source: `dashboard/src/components/DatasetContext.vue`, `dashboard/src/components/DatasetImport.vue`

Responsibility: accessible dataset selector and standard-file import journey.
Inputs are list/detail/template/validation/publication responses. Outputs are
explicit selection or import requests. Selector lists legacy source separately,
states name/source/window/currency/row counts and capability reasons, and remains
outside route error branches. Import lets the user supply performance and optional
paths/research, download templates, preview at most 20 rows per role, inspect
field issues and per-stage capability reasons before publication, then import. Editing an input invalidates its earlier preview.
An invalid or partial import never becomes selected. Success offers Use for
analysis as a separate action. Static operations are disabled with the reason.
Dependencies: shared stores, client and existing table components. Verification:
file validation/publication browser flow, two dataset switches, keyboard/narrow layout.

### BudgetPlans.vue

Source: `dashboard/src/components/BudgetPlans.vue`

Responsibility: list, create and revise plans for the selected dataset. Inputs
are name, total budget and the existing policy enum. Editing holds the revision
from the loaded record and sends it for conflict detection. A conflict retains
the user's fields and offers an explicit Load latest revision action that
replaces the draft only on request. Context changes retain the original draft
and dataset binding, show a mismatch notice and disable save until the user
returns to that dataset or explicitly starts a new plan. A mismatched form
does not label its amount with the newly selected dataset currency. Starting uses a saved revision and states
dataset/budget/currency. Unsaved edits do not affect a run. Existing master drafts
are separately labeled future configuration. Dependencies: client and shared
stores. Verification: two revisions, stale update, saved-revision execution.

### WorkbenchRunner.vue

Source: `dashboard/src/components/WorkbenchRunner.vue`

Responsibility: execute one stage and show its persisted state. Inputs are a
stage, selected dataset, applicable options or saved plan and evaluation target.
Unsupported capabilities show their exact reason. Evaluation lists only completed
same-dataset optimizations. Polling is disposed on unmount and context change;
late responses cannot switch the result. Success offers an explicitly labeled refresh of the latest dataset results;
another completed run may be newer. The saved run identifier, complete record
and artifact downloads remain independently inspectable. Failure/stopped/interrupted
does not publish partial outputs. Stop
and explicit retry use the persistent identity; retries create a new run.
Dependencies: client, stores. Verification: real model run and reordered polling.

### RunHistory.vue

Source: `dashboard/src/components/RunHistory.vue`

Responsibility: show dataset/stage-scoped retained history, inspect older records
and download declared complete artifacts. Detail includes fingerprint, dataset,
timestamps, options, plan revision, evaluation target and status. Inspection does
not replace active dataset or latest-result selection. Empty, failure and
interrupted states are distinct, with retry for supported terminal runs.
Record selection and retry are disabled while submitting a retry and on unavailable execution; date filters
include all process states, including stopping. Display at most 20 matching
records per page, with page/count labels and Previous/Next controls. A selected
older record is labeled Historical record and never replaces the latest result.
History identifiers and metadata stack on narrow screens, and download labels
wrap within the panel.
Dependencies: client, stores and existing tables. Verification: restart and
earlier-run selection; download rejection for partial output.

### EvaluationReport.vue

Source: `dashboard/src/components/EvaluationReport.vue`

Responsibility: render the production strategy-evaluation object, including
contract/conservation checks, baseline comparisons, contributed-model summaries,
skipped strategies and reasons, and truth availability. Inputs are `report` and
run metadata; output is readable labeled evidence with no invented scores.
No report shows Not run, unsupported evidence is distinct from a failed run,
and numerical zero is retained. Expand nested fields through existing readable
tables/details, with raw report download alongside retained runs. State that
baseline comparison is not guaranteed future revenue. Dependencies: existing
presentation helpers only. Verification: complete, skipped, zero and absent reports.

## Layout and accessibility

All controls use existing theme tokens, native labels, buttons, selects and
status/error text. Submitted errors focus a tabindex-minus-one summary after
rendering; inputs reference that summary through accessible descriptions.
Controls stack below 760 pixels and remain usable at 375
pixels and 200 percent zoom. Chart values remain keyboard accessible. Selection
and pending operations are communicated in text as well as color.
