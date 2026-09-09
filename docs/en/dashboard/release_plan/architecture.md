---
title: Analysis Workbench Architecture
compact: "Data ownership and integration decisions for persistent registered datasets, isolated model runs, revisioned budget plans, scoped dashboard resources, compatibility sources, restart recovery and incremental verification."
stepsCompleted: [1, 2, 3, 4, 5, 6, 7, 8]
inputDocuments: [prd.md, decision-log.md, review-prd.md, DESIGN.md, EXPERIENCE.md]
workflowType: architecture
status: complete
lastStep: 8
completedAt: 2026-09-08
---

# Analysis Workbench Architecture

Terms used below: User Interface (UI), Application Programming Interface (API).

## Initialization

The finalized incremental requirements and reviewed existing-code evidence are
the inputs. The approved implementation plan supplies the technology choices,
scope and data lifecycle. Existing owning English specifications remain the
contracts for business algorithms. The two design spines inherit the existing
Dashboard theme and will be checked before story extraction.

## Project context

Fifteen functional requirements span ingestion, observation delivery, model
execution, budget plans and recovery. This is an existing full-stack internal
analysis tool, not a new platform. It remains single-process for queued work;
browser selection must not mutate server-wide dataset state. A 100,000-row
history requires bounded plots and shallow reactive observations.

The critical risk is source mixing: existing loaders read global configuration,
prepared model input is stage-wide, and absent evaluation input may be restored
from samples. Dataset and run identities must therefore be carried through
the entire new path. Existing compatible routes stay explicitly separate.

Reuse simulator and model contracts; do not add new business mathematics,
database drivers in the browser, mandatory business-schema migrations, or a
new chart library. English owning pages are updated before their implementation.

## Existing foundation

The user selected the existing Vue/Plotly client, Flask backend and Python model
modules. No starter or dependency upgrade is evaluated or installed: scaffolding
a new application would contradict the approved brownfield scope. Installed
versions and lockfiles, not a claim about latest releases, establish the build.
Existing Node tests, Python unit/integration tests and browser verification are
retained. The current feature branch isolates work from main.

## Core decisions

#### Persistent datasets

Use `PIPELINE_OUTPUT_DIR/workbench/datasets/<datasetId>/` with an immutable
manifest and validated inputs. Identifiers are server-issued `ds_` plus 32
hexadecimal characters. Dataset metadata is committed by atomic directory
publication after validation. No path is accepted from the browser. The manifest
contains `id`, `name`, `source`, `createdAt`, `digest`, `scope`, `counts` and
`capabilities`. Scope holds `advertiserId`, `marketplace`, `currency`, `start`
and `end`; each capability has `available` and `reason`.

The push body is `{name, performance, paths?, research?}`. Performance and paths
are arrays using the documented report fields; research is the existing
simulation research object. File mode uses multipart fields with the same
three names. Public templates reuse the existing simulator performance fields
(`reportDate`, `accountId`, `unitsSold` and companions) and path format.
Repository projection normalizes fields internally; both transports share
the same public validator. Unknown file roles, non-finite values,
invalid dates, mixed scope, invalid counts and inconsistent references fail
before publication. Validation returns at most 20 preview rows per input and
bounded field issues. Reuse the existing 26 MiB transport ceiling.

Generate canonical model input files from validated observations, preserving
original daily path windows for display and adapting them to a single report
scope only when preparing attribution. Research context is optional and
validated through the existing adapter. Truth is never copied into public
resources or used as a response-model feature.

#### Scoped resource delivery

`GET /api/dashboard/resources/<resource>?datasetId=...` delegates to the
registered-dataset repository before legacy database availability checks. It
returns the existing snapshot key shapes, including empty arrays/objects for
missing model results. Unregistered identifiers fail; they never enter legacy
loaders. No dataset parameter retains the explicit legacy source behavior.
Responses carry dataset metadata, and cache keys include identity and bounds.
The Vue store persists only the selected identifier in browser storage and
increments its generation on dataset changes and reloads, rejecting old merges.

#### Model runs and plans

Keep the legacy job routes for compatibility. Registered-dataset runs use a
dedicated service that shares the existing task manager and single worker but
stores inputs, outputs and `run.json` beneath `workbench/runs/<runId>/`.
Identifiers are `run_` plus 32 hexadecimal characters. A run captures dataset
digest, stage, options, plan/revision and optional `strategyRunId`; only a
completed same-dataset optimization run may be evaluated. Existing module
commands receive run-specific paths and never copy default strategies.

Budget plans are stored under `workbench/plans/<planId>/`, with immutable
revision records and a listing manifest. Identifiers are `plan_` plus 32
hexadecimal characters. Inputs are `name`, `datasetId`, positive `totalBudget`
and `budgetUsagePolicy` using the existing two enum values. Updates include
the expected revision; a stale edit conflicts rather than overwriting. Starting
a plan reads the stored revision on the server. Other master drafts are not
consumed by this service.

The service persists state at queue admission and transitions, plus a bounded
log. Startup marks formerly active records interrupted without restarting
them. Retry creates a new identity. Only successful complete output manifests
are exposed as results. Selecting an older run is explicit; the default is
the newest successful matching run, with its identity visible.

#### Public surface and errors

Dataset routes are `GET /api/datasets`, `GET /api/datasets/<id>`,
`GET /api/datasets/templates`, `POST /api/datasets/validate` and
`POST /api/datasets`. Generator completion adds `datasetId` or a bounded
registration error without losing its existing preview/download actions.

Workbench routes are `GET/POST /api/workbench/plans`,
`GET/PUT /api/workbench/plans/<id>`, `GET/POST /api/workbench/runs`,
`GET /api/workbench/runs/<id>`, `POST /api/workbench/runs/<id>/stop` and
`GET /api/workbench/runs/<id>/files/<filename>`. Starting a run accepts a
registered dataset and stage, optional saved plan/revision, and target strategy
run for evaluation. Detail includes parsed `result` only for complete runs.
Errors use bounded `{error,message,issues?}` with 400 validation, 404 unknown
identity, 409 incompatible/stale state and 503 unavailable runtime. Existing
413 payload limits and 403 hosted/disabled execution rules apply server-side.

The API client remains the sole network boundary. Static mode returns an
unavailable capability or rejects mutations locally. Existing deployment access
protection and process-count restrictions remain; there is no new public host.

#### Browser ownership

The shared dataset context appears above page content; it must remain usable
when a dataset resource fails. Generator, Budget Manager, optimizer and log use
the same selection and workbench state. Registered data never enters legacy
model runners or implicit legacy downloads. Existing database and demo views
remain explicitly selectable. Route tab keys stay compatible.

## Consistency patterns

Python uses snake_case, Vue components PascalCase and public metadata camelCase
to match the existing client; observation fields retain their declared report
names. Lists use `{datasets: [...]}`, `{plans: [...]}` and `{runs: [...]}`;
single objects are returned directly. Dates are `YYYY-MM-DD`, timestamps use
UTC ISO strings, booleans are booleans, and missing numeric values are null.

Persistence uses atomic replacements and a service lock, not serialization of
thread objects. IDs must match their exact prefix/hex pattern before filesystem
resolution. Reads never expose local paths. Complete markers, not file presence
alone, govern results. Tests use temporary runtime roots and cannot mutate a
developer's configured source or launch database operations accidentally.

The client replaces immutable observation snapshots, and independent resource
requests share in-flight work. Selection/reload generation changes invalidate
late progress, errors and payloads. Keep network operations in `client.js`;
views emit user intent and read shared stores. UI filters do not rewrite stored
data, invoke models implicitly or average ratios. Tests belong in the existing
backend and dashboard test directories with their behavior-owning specs.

## Component boundaries

The existing repository tree is retained. New cohesive runtime boundaries are:

#### Data ingestion and observation projection

`backend/services/datasets.py` owns validation, registration and immutable reads;
`backend/api/datasets.py` owns transport; `backend/repository/datasets.py` owns
the existing snapshot shape for selected datasets. Their owning English page
is `docs/en/dashboard/datasets.md`. Existing generator completion calls this
service and existing resource routes dispatch to its repository explicitly.

#### Plans and model execution

`backend/services/workbench.py` owns revisioned plans, run records and the
existing queue adapter; `backend/api/workbench.py` owns transport. Their owning
English page is `docs/en/dashboard/budget-plans.md`. It uses the existing module
commands and dataset service; module mathematics imports neither service.

#### Client context and views

`client.js` and `useDashboard.js` retain their existing owners. A shared
`useWorkbench.js` store and `DatasetContext.vue`, `DatasetImport.vue`,
`BudgetPlans.vue`, `WorkbenchRunner.vue`, `RunHistory.vue`, and
`EvaluationReport.vue` present the new contracts in existing routes. New
components are added only where they represent a reusable behavior boundary.
Common chart aggregation/export belongs in one pure helper with unit tests;
existing views keep their current owning page.

#### Verification and build

Backend tests cover durable isolation and real model execution with temporary
datasets; dashboard tests cover aggregation, context races and user operations.
Builds use current package commands without new wrappers. Runtime datasets,
records and generated previews remain ignored and outside site builds.

## Validation and handoff

Independent source review found three integration gaps, now resolved: public
import fields reuse simulator contracts; run admission inherits server execution
switches; evaluation receives explicit synthetic provenance and currency from
its target optimization, never from a default initializer. Missing independent
initializer evidence is skipped. Extend the existing evaluation command for
these explicit inputs without changing evaluation mathematics.

The queue adapter persists on every `append()` transition, including queued
cancellation, and records both persistent run and transient task identities.
Completion requires exit success and validated required artifacts; an
`is_optimized=false` artifact remains a valid refusal report, displayed honestly.
The design preserves existing responsive tokens and makes dataset selection
available during page-resource failure. Requirements, architecture and design
are ready for story extraction; this status does not claim implementation.
