---
title: Budget Plans and Retained Runs
compact: "Revisioned budget plan persistence, frozen dataset inputs, isolated queued model runs, evaluation lineage, artifact access and restart interruption; owns workbench service and routes."
source_files: backend/services/workbench.py, backend/api/workbench.py
---

# Budget Plans and Retained Runs

A budget plan is a named set of options for one registered dataset. Saving a
plan does not execute a model. Starting a run freezes a saved revision so later
edits cannot change queued or completed work. Other master-entity drafts remain
future configuration and are not implicitly read by these runs.

## Plan contract

Plan fields are `id`, `revision`, `name`, `datasetId`, `totalBudget`,
`budgetUsagePolicy`, `createdAt`, `updatedAt`. The budget is finite and strictly
positive. Policy is `SPEND_FULL_BUDGET` or `SPEND_UP_TO_BUDGET`. The server validates
the referenced dataset. Identifiers are `plan_` followed by 32 hexadecimal digits.

`GET/POST /api/workbench/plans` list or create; creation returns 201.
`GET/PUT /api/workbench/plans/<id>` read or revise. Updating requires the expected
`revision`; a stale update returns 409. Each saved revision is immutable under
`PIPELINE_OUTPUT_DIR/workbench/plans/<id>/`; atomically replaced metadata points
to the current revision. Editing does not mutate the dataset or earlier revisions.

## Run admission and frozen inputs

`POST /api/workbench/runs` accepts `datasetId`, `stage` (`attribution`,
`optimization`, `evaluation`), stage options, optional `planId`/`revision` and
`strategyRunId`. Plan starts use the stored revision, never mutable browser
parameters. Admission checks the hosted and pipeline-execution switches on the
server and returns 403 when execution is disabled. Dataset capabilities are
checked again at admission. Evaluation requires a completed optimization run
whose dataset and fingerprint match the evaluation inputs.

Each identifier is `run_` followed by 32 hexadecimal digits. Store `run.json`,
`inputs/` and `outputs/` beneath `workbench/runs/<id>/`. The record captures input
fingerprint, dataset identity, stage/model, options, plan revision, target strategy
run, timestamps, state, task identity and a bounded log. Copy immutable inputs
before enqueueing. Use the existing single-worker task manager and model commands
with explicit per-run paths; never mutate global data directories. Attribution
uses the existing path aggregation adapter. Optimization consumes research only
from its registered dataset. Evaluation consumes only its target's strategy file.

## Execution and recovery

Persist every queue transition, including cancellation before execution. States
are queued, running, stopping and the existing terminal success/failure/stopped
states; public spelling matches the shared task manager. A service startup marks
formerly active persisted records `interrupted`. It never automatically reruns
them. Explicit retry is a new run with the same supported parameters and a new
identity. The transient task identifier is not a substitute for the persistent ID.
If writing an interrupted record fails, application startup still completes.
Reads expose an in-memory interrupted record with `recoveryPersisted=false` and
a safe `recoveryError`; they must not present the stale persisted state as active.
Workbench collection capabilities report storage and execution unavailable until
recovery successfully persists that record. Recovery can be retried after storage
is repaired, including on the next application startup; it never executes a model.
New run admission returns 503 while such a recovery failure remains unresolved.

Successful process exit is necessary but insufficient for completion: required
artifacts must exist and pass their existing parser/contract checks. A valid
`is_optimized=false` report is complete with a refusal reason; it is not a budget
recommendation. Failed, stopped and interrupted records expose no partial result.
The latest successful matching run is the default display, named visibly; history
can inspect older runs without changing dataset selection.

## Evaluation lineage

Evaluation receives explicit synthetic provenance from the dataset and currency
from the target strategy. It must not read or copy the default initializer or
sample research. Independent initializer comparison is skipped when absent.
The parsed `strategyEvaluation` report preserves contract/conservation checks,
baseline comparisons, skipped models/reasons and truth availability. Missing
optimal-allocation truth remains unavailable. Comparison to observed history
does not claim future causal revenue. Contributed Willow output remains a separate
labeled demonstration.

## History and artifact routes

`GET /api/workbench/runs?datasetId=<id>` returns `{runs: [...]}` newest first;
`GET /api/workbench/runs/<id>` returns one record and parsed `result` only when
complete. `POST /api/workbench/runs/<id>/stop` requests queued cancellation or
process termination. `GET /api/workbench/runs/<id>/files/<filename>` only serves
declared completed output basenames. Reject traversal, unknown artifacts and
partial outputs. No private path appears in responses.

Plan lists use `{plans: [...]}`; singular resources return the object directly.
Both collection responses include `storageAvailable`, `executionAvailable`,
`storageReason` and `executionReason` so Settings can explain storage separately
from execution permission without starting a job or exposing a private path.
Application Programming Interface (API) errors are `{error,message,issues?}`:
400 malformed input, 403 disabled execution, 404 unknown identity, 409 revision
or state conflict, 503 unavailable runtime storage. Local read/write support is
independent from model-execution permission. Static clients make no mutation
requests and explain the live-backend requirement.

## Source Files

### workbench.py service

Source: `backend/services/workbench.py`

Responsibility: immutable plan revisions, frozen run preparation, persistent
queue adapter, interruption recovery and artifact validation/access. Inputs and
outputs follow the contracts above. Dependencies are dataset service, task
manager and package-native model entry points. No new optimization mathematics
is implemented here. Tests cover stale revision rejection, two isolated datasets,
queued cancellation, target-run matching and reconstruction after restart.

Public entry points: `create_plan(payload)`, `get_plan(id, revision=None)`,
`update_plan(id, payload)`, `list_plans(dataset_id=None)`, `start_run(payload)`,
`get_run(id)`, `list_runs(dataset_id=None)`, `stop_run(id)` and
`run_artifact_path(id, filename)`. `recover_runs()` reconciles persisted active
records at application startup while preserving operations owned by this process.
Damaged history records are ignored during startup recovery so health and
Settings remain reachable; explicit reads still report invalid records.
`latest_run(dataset_id, stage)` returns the newest complete matching record or
null; `latest_result(dataset_id, stage)` returns its parsed result or an empty
object. Attribution results use the existing four snapshot keys; optimization
and evaluation return their native artifact objects. No helper reads a legacy
fallback. All list ties use identifier order after creation time.

Run options accept a nested `options` object or the existing top-level option
fields; duplicate conflicting values are rejected. Only optimization consumes
`totalBudget` and `budgetUsagePolicy`; saved plan revision values take precedence
over supplied form options. Result records use `datasetDigest`, `state`,
`startedAt`, `finishedAt`, `percent`, `phase`, `taskId`, `logs` and `artifacts`.
Logs retain at most 200 entries of 500 characters, replacing private runtime
paths. Artifacts are named objects with `name`, `mimeType` and a content digest;
only declared complete unchanged files are downloadable. Run detail adds `result`;
list records omit parsed payloads. Metadata and parsed results contain no local
storage paths, including evaluation skip messages and command output.
`recovery_storage_error()` returns a safe reason when the configured runtime has
unpersisted recovery transitions, otherwise null. Transport capability checks
use this result in addition to filesystem access checks.

### workbench.py transport

Source: `backend/api/workbench.py`

Responsibility: route the plan and run operations above with explicit errors and
server-side execution permission. Inputs are validated request objects and issued
identifiers; outputs are descriptors and allowlisted artifacts. Depends on Flask,
backend configuration and workbench service. Verify through backend integration
tests using temporary runtime storage and the documented model commands.
