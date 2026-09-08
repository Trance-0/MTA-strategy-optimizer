---
title: Analysis Workbench Requirements
compact: "Incremental product requirements FR-1 through FR-15 for persistent data ingestion, source-consistent charts, budget revisions, isolated model runs, formal evaluation reports, recovery and static capability boundaries."
status: final
created: 2026-09-08
updated: 2026-09-08
---

# Analysis Workbench Requirements

Terms used below: User Interface (UI).

## Purpose and user

This Product Requirements Document (PRD) turns the approved September 8 release
plan into testable capabilities for the existing analysis Dashboard. The user
is an analyst or developer operating a local or deployed backend to validate
advertising strategies. Historical product briefs remain historical; existing
English specifications govern the business mathematics.

The release succeeds when an operator can generate or import data, select that
dataset, inspect observed performance, save a budget plan, run supported models,
read their evaluation, and retrieve the inputs and results after a restart.

## Working session

The operator generates data or imports a standard report, reviews validation,
and explicitly selects it for analysis. The overview states source and scope.
The operator filters observations, inspects the values behind a chart, saves a
budget plan and starts optimization where the data supports a fit. Evaluation
describes checks and limitations. A previous dataset or run remains available
without changing the currently selected data or rewriting history.

This is the session approved by the user, not a fabricated persona study.

## Vocabulary

#### Dataset

An immutable validated set of observed inputs, identified independently from
the generator's temporary operation. It has a source, scope, digest and declared
analysis capabilities.

#### Budget plan

A named set of future-run optimization options for one dataset. Editing creates
a revision; a model run freezes the chosen revision.

#### Model run

One execution with immutable input identity and options, terminal status and
declared output artifacts. An evaluation identifies the strategy run it checks.

#### Demonstration

An explicitly labeled existing sample or contributed forecast. It is never a
fallback for absent results from another dataset.

## Data and scope requirements

The following Functional Requirements (FR) use stable identifiers for story
creation and acceptance review.

#### FR-1: Register generated data

A successful generator run registers its public observations and available
research context as a persistent dataset. The operator can choose Use for
analysis. Registration does not automatically replace the active selection.
Generator configuration, previews and export behavior remain available.

#### FR-2: Import standard files and pushed data

The operator can download templates, preview and validate standard
Comma-Separated Values (CSV) or JavaScript Object Notation (JSON), and import a
dataset. An external caller can push the same documented contract through the
Application Programming Interface (API). The same validation rules govern both.
Invalid content reports its field or row, creates no selectable partial dataset,
and leaves the active selection untouched. Arbitrary column mapping is excluded.

#### FR-3: Persist and select datasets

Each successful import or generation has a stable identifier, source, display
name, creation time, scope, digest and row counts. Datasets survive backend
restart on the same persistent storage. Selection is browser-owned, not a
global environment-variable change. Exactly one dataset is analyzed at a time.

#### FR-4: Declare supported capabilities

Observed performance supports overview charts; matched paths and performance
enable attribution; research observations enable Campaign history and potentially
response fitting. Presence of a file is not evidence of a supported fit: existing
model eligibility rules remain authoritative.
Each disabled stage states its missing input or evidence. No Campaign identity,
candidate capacity, margin or model score is fabricated. A dataset has one
account, marketplace and currency; mixed scope is rejected with a split remedy.

#### FR-5: Isolate observations and results

Every displayed model result must match its dataset digest and selected run.
Missing results display Not run. They never load an unrelated baseline artifact.
Switching data invalidates the selected resources and ignores late responses.
Simulation truth remains outside ordinary charts and model-facing inputs.

## Analysis requirements

#### FR-6: Explain overview metrics

Command Center states data source and scope; shows available spend, sales,
purchases, impressions, clicks and return metrics; and exposes next available
actions. Amounts and ratios use separate plots. Daily, weekly and monthly
grouping sums additive values and recomputes ratios from those totals.

#### FR-7: Explore historical detail

Campaigns derives filters from the selected data. Rankings lead to the matching
detail with a reset and return path. Trends, budget delivery density and path
distributions appear only with their required fields. Charts retain readable
value tables and export the current filtered values.

#### FR-8: Explain model evidence

Campaign Optimizer presents attribution differences and reliability, initial
and recommended budgets, adjustment amounts and existing backend response
evidence. Extrapolation, pooled evidence and insufficient support are visible.
Historical filters never imply that a model was refitted; result scope is stated.

## Plans, evaluation and recovery

#### FR-9: Save revisioned budget plans

Budget Manager saves a name, dataset, positive total budget and a supported
budget-usage policy. Editing creates a new immutable revision. A run uses the
saved revision, not mutable browser fields. Other entity drafts remain clearly
unconnected to model execution. Candidate data is never invented to fill a seed.

#### FR-10: Execute and retain isolated model runs

The existing task queue executes supported models using the selected dataset.
Inputs, parameters, model identity, time, state and completed artifacts are
retained by run. A failed or cancelled run publishes no partial result. Earlier
successful runs remain inspectable. Independent models do not gain false
prerequisite relationships.

#### FR-11: Read formal strategy evaluation

The evaluation page renders contract/conservation checks, baseline comparison,
skipped strategies and reasons from the production evaluation artifact. Not run,
insufficient evidence, failure and success remain distinct. The evaluation names
its strategy run. Observed baseline comparison is not promised future revenue.
Absent optimal-allocation truth remains Not run; Willow is a separate demo.

#### FR-12: Trace and export a result

Optimization Log filters dataset/run history and exposes input digest, plan
revision, execution state and declared output downloads. Reading an older result
does not silently replace the current dataset or newest result.

#### FR-13: Recover after errors and restart

Completed datasets, plans and run records survive restart. Previously active
runs are marked interrupted and can be explicitly retried; they are not silently
rerun. Settings remains accessible when a data resource fails, and distinguishes
data-source, runtime-storage and model availability problems.

#### FR-14: Keep references source-aware

Knowledge Base vocabulary, entities and source information follow the dataset.
The separate fixed Ontology Review examples remain labeled synthetic examples,
not current-plan approval. No new live review service is implied.

#### FR-15: Preserve deployment boundaries

The static site presents a labeled read-only demonstration and disables new
backend operations without issuing requests. Existing database reading remains
available; new imports do not overwrite database tables by default. Backend
operations use the existing deployment access boundary, not a new public service.

## Cross-cutting acceptance

Charts name units, date range, source and sample size, and have readable tables.
Missing values differ from zero. A zero denominator is unavailable, not a zero
ratio. One axis per plot and stable entity colors remain the visual contract.
Keyboard and narrow layouts must remain usable; 100,000-row history retains paging,
bounded chart marks, lazy resources and protection from stale responses.

Success is demonstrated by two visibly different datasets and two saved budget
revisions, equivalent results through each ingestion channel, report/plot/export
agreement, and recovery after restart. Test counts alone do not prove browser
interaction. No success metric claims real-world causal lift or optimality.

## Exclusions and defaults

No arbitrary file mapping, direct third-party connector, cross-dataset analysis,
new attribution/optimization mathematics, automated activation, or live ontology
review. Existing Vue, Plotly, Flask, English UI and Python model contracts stay.
Standard templates reuse existing report and research contracts. The approved
storage default is a persistent backend runtime directory; no mandatory business
database migration is introduced. There are no unresolved product-scope questions.

## Baseline reconciliation

The accepted release keeps the already implemented five Knowledge Base tabs and
runnable evaluation stage. Outdated overview descriptions are corrected to this
explicitly approved intent before implementation. The response optimizer remains
an existing capability rather than a proposed new algorithm. Main's command
relocations are retained; this release introduces no new command wrapper.
