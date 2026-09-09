---
title: Analysis Workbench Epics and Stories
compact: "Six approved workstreams decomposed into 16 dependent stories, with requirement coverage and acceptance criteria for dataset ingestion, source-aware analysis, budget revisions, evaluation and recovery."
stepsCompleted: [1, 2, 3, 4]
inputDocuments: [prd.md, architecture.md, DESIGN.md, EXPERIENCE.md, decision-log.md]
status: complete
---

# Analysis Workbench Epics and Stories

Terms used below: Non-Functional Requirement (NFR), User Experience (UX), Application Programming Interface (API), Functional Requirement (FR).

## Overview

These stories implement the approved comprehensive release in the existing
application. The [Product Requirements Document](./prd.md), [architecture](./architecture.md),
[visual design](./DESIGN.md) and [experience](./EXPERIENCE.md) are the complete
input set. The user's strict-execution authorization covers routine Continue
menus and the approved six workstreams; no new discovery decision is introduced.
Owning English behavior pages must be updated before their code changes.

## Requirements inventory

#### Functional requirements

- FR-1: Register generated observations and available research persistently.
- FR-2: Validate, preview and import matching standard files or pushed data.
- FR-3: Persist datasets and select exactly one in browser-owned context.
- FR-4: Declare capabilities from matched inputs and actual model support.
- FR-5: Isolate data, results and simulation truth; reject stale responses.
- FR-6: Explain overview metrics with additive and ratio-correct grouping.
- FR-7: Explore historical rankings, distributions, details and exports.
- FR-8: Explain attribution, budget response and reliability evidence.
- FR-9: Save immutable budget-plan revisions and run stored options.
- FR-10: Queue isolated runs and retain complete results without false dependencies.
- FR-11: Render the formal strategy evaluation and missing evidence accurately.
- FR-12: Filter run history and trace/download a selected result.
- FR-13: Recover records after restart and preserve accessible diagnostics.
- FR-14: Bind knowledge references to data; keep demonstrations distinct.
- FR-15: Preserve read-only static and legacy database boundaries.

#### Non-functional requirements

- NFR-1: Validate 100,000 historical rows with paging, bounded plot marks and lazy resources.
- NFR-2: Atomic publication and immutable provenance prevent partial or mixed results.
- NFR-3: Late payloads, progress and failures cannot mutate a newer browser context.
- NFR-4: All operations support keyboard use, 375-pixel layout and 200% zoom.
- NFR-5: Units, scope, samples and readable values accompany charts; zero differs from missing.
- NFR-6: Existing access controls, transport limits and persistent runtime boundaries apply.

#### Architecture requirements

- No starter, dependency upgrade or new model mathematics; reuse existing commands.
- Dataset identifiers are `ds_` plus 32 hex characters and immutable input manifests.
- Public reports retain simulator fields; internal projection may normalize names.
- Dataset routes use `/api/datasets`; run/plan routes use `/api/workbench`.
- Resources take explicit `datasetId` before legacy database readiness checks.
- Runs use separate directories and the existing single-worker task manager.
- Complete results require successful exit and validation of declared artifacts.
- Evaluation names its target optimization, synthetic source and currency explicitly.
- Run records survive restart; transient task identifiers are not persistent run identities.
- Plans use optimistic revision checks and two existing budget-usage policies.

#### User experience requirements

- UX-1: DatasetContext remains outside page failure boundaries and preserves bound drafts.
- UX-2: DatasetImport provides role-specific templates, invalidatable preview and explicit selection.
- UX-3: Analysis cards separate amount/ratio axes and retain value tables and filtered export.
- UX-4: BudgetPlans separates Save revision from Run saved revision and handles conflicts.
- UX-5: WorkbenchRunner shows identity, eligibility, phases, stop and explicit View results.
- UX-6: EvaluationReport separates execution status, individual checks and demonstration content.
- UX-7: RunHistory reveals older results inline without switching global context.
- UX-8: Recovery keeps Settings/source selection accessible and drafts intact after errors.
- UX-9: Reference panels follow dataset entities while labeling fixed cases Demonstration.
- UX-10: Reuse design tokens; stable entity colors; contrast targets 4.5:1 text and 3:1 controls.
- UX-11: At 760 pixels cards stack; at 375 pixels controls remain usable without page overflow.
- UX-12: Focus restoration, labeled errors and status announcements work without plot hover.

## Requirements coverage

- FR-1: Epic 1, generated dataset registration.
- FR-2: Epic 1, standard import and push interface.
- FR-3: Epic 1, persistent registration and browser context.
- FR-4: Epics 1 and 3, observed input and model evidence eligibility.
- FR-5: Epics 1 and 3, scoped observations and isolated results.
- FR-6: Epic 2, understandable overview.
- FR-7: Epic 2, historical detail and exports.
- FR-8: Epics 2 and 3, evidence presentation and matching results.
- FR-9: Epic 3, saved plan revisions.
- FR-10: Epic 3, durable isolated execution.
- FR-11: Epic 4, selected-target evaluation.
- FR-12: Epic 5, result history and export.
- FR-13: Epics 3 and 5, durable records and recovery interaction.
- FR-14: Epic 5, source-aware references.
- FR-15: Epics 1, 3 and 5, compatibility and static verification.
- NFR-1 through NFR-6 and UX-1 through UX-12: story-specific checks and final integration acceptance.

## Epic list

Workstreams E0 through E5 retain the approved meaning; dependency-safe ordering
within the stories does not narrow their scope.

- E0: Trust the development baseline and release intent; verified planning prerequisite.
- E1: Bring and select analysis data; usable generation and import through all supported channels.
- E2: Understand observed performance and model evidence; meaningful charts and readable values.
- E3: Save budgets and run reproducible strategies; immutable options and isolated execution.
- E4: Read the selected strategy's formal evaluation; independent check and process status.
- E5: Retrieve, diagnose and validate an analysis; durable history and complete deployment experience.

Shared client and backend boundaries are extended sequentially within each
story, not rewritten by separate technical-layer epics. E2 uses existing result
contracts and honest empty states; new registered results arrive through E3.
Independent history-chart work may proceed after E1 alongside E3 only when
ownership of shared stores and API files is kept explicit.

## Epic 0: Trust the release baseline

The analyst can distinguish current capabilities from the approved new release.

### Story 0.1: Confirm release baseline

As the requesting analyst, I want a reviewed starting point, so that accepted
generator work and current deployment commands remain part of the release.

Dependencies: none. Coverage: all requirements' scope; E0 prerequisite.

**Acceptance Criteria:**

**Given** main 0.9.47 and the approved replacement plan, **when** the release is
initialized, **then** the isolated branch retains existing commands and completed
generator behavior, **and** requirement, architecture and design reviews identify
new behavior separately from current functionality.

Evidence: `decision-log.md`, final `prd.md`, `review-prd.md`, `architecture.md`,
`DESIGN.md` and `EXPERIENCE.md`. This documentation-only prerequisite is complete;
its completion is not a claim that any product story below is implemented.

## Epic 1: Bring and select analysis data

The analyst can register, generate or import their own observations and inspect
them without unrelated sample results.

### Story 1.1: Register validated datasets

As the requesting analyst, I want to push and retrieve validated datasets,
so that the backend preserves my inputs independently from temporary jobs.

Dependencies: 0.1. Coverage: FR-2, FR-3, FR-4, FR-5; NFR-2, NFR-6.

**Acceptance Criteria:**

**Given** matching report arrays, **when** `/api/datasets/validate` is called,
**then** bounded preview, scope, counts and capabilities are returned without
publication, **and** `/api/datasets` creates an immutable server-issued identity
whose detail and inputs survive process restart.

**Given** invalid or mixed-scope inputs, **when** either action is submitted,
**then** bounded role/row/field issues are returned and no partial dataset is
listed, **and** model truth is excluded from public observations and inputs.

### Story 1.2: Select source-consistent observations

As the requesting analyst, I want to select a dataset above every page,
so that charts and source labels describe the same input.

Dependencies: 1.1. Coverage: FR-3, FR-4, FR-5, FR-15; UX-1, UX-8; NFR-3.

**Acceptance Criteria:**

**Given** two datasets, **when** selection changes, **then** scoped resource
requests bypass legacy database checks, return existing snapshot shapes and
replace observations, **and** absent model outputs are empty with Not run.

**Given** late progress, failures or payloads, **when** a newer context exists,
**then** they cannot overwrite it, **and** an unknown persisted identity retains
an explanatory selector instead of silently loading a sample. Drafts retain
their original dataset; explicit legacy context remains usable.

### Story 1.3: Analyze a generated dataset

As the requesting analyst, I want Use for analysis after generation,
so that the data I configured becomes the data shown in the workbench.

Dependencies: 1.1, 1.2. Coverage: FR-1, FR-3, FR-4; UX-1, UX-8.

**Acceptance Criteria:**

**Given** successful generation, **when** registration finishes, **then**
validated performance, original paths and available research context persist
outside temporary generator retention, **and** analysis selection changes only
when Use for analysis is pressed.

**Given** a registration failure, **when** generation completed successfully,
**then** previews/downloads remain usable and the page explains that no analysis
dataset was registered. Existing configuration guards and exports still work.

### Story 1.4: Import standard files

As the requesting analyst, I want templates and validated file preview,
so that external observations can enter the same analysis workflow.

Dependencies: 1.1, 1.2. Coverage: FR-2, FR-3, FR-15; UX-2, UX-12.

**Acceptance Criteria:**

**Given** the import tab, **when** simulator-format performance and optional
path/research files are selected, **then** shared multipart validation gives the
same normalized content as pushed arrays, **and** template roles match those
fields. Any input edit invalidates prior preview before explicit import.

**Given** invalid fields or oversized input, **when** submitted, **then** the
bounded error is accessible, no selection changes and no partial dataset is
published. Static mode refuses import locally without a network mutation.

## Epic 2: Understand performance and evidence

The analyst can read, compare and inspect values without confusing amounts,
ratios, absent data or model predictions.

### Story 2.1: Explain overview trends

As the requesting analyst, I want clear totals and grouped trends,
so that I can understand this dataset before running a model.

Dependencies: 1.2. Coverage: FR-6; UX-3, UX-10; NFR-5.

**Acceptance Criteria:**

**Given** observed performance, **when** day/week/month grouping changes,
**then** amounts and counts sum, ratios recompute from totals, and amount/ratio
plots remain separate, **and** source, units, dates, sample size and precise
value tables agree. Missing values and zero denominators remain unavailable.

**Given** a source with no model result, **when** overview opens, **then** valid
performance charts remain usable and next actions reflect server capabilities.

### Story 2.2: Explore filtered historical detail

As the requesting analyst, I want rankings, distributions and drill-down,
so that I can identify the observations behind a change.

Dependencies: 2.1. Coverage: FR-7; UX-3, UX-11, UX-12; NFR-1, NFR-5.

**Acceptance Criteria:**

**Given** matching history or paths, **when** filters or rankings are used,
**then** options derive from current data and detail preserves filter context,
**and** Back restores invoking-row focus and Reset clears filters explicitly.

**Given** required observations exist, **when** trends, budget density, path
lengths or common paths are shown, **then** tables and filtered exports agree,
**and** 100,000-row history uses bounded marks and paging. Missing research
disables only affected plots; a keyboard table action substitutes for plot click.
Overflow categories group as Other with underlying rows still reachable and
stable colors across filtering.

### Story 2.3: Clarify model evidence displays

As the requesting analyst, I want clear attribution and response evidence,
so that I can distinguish historical credit from predicted budget behavior.

Dependencies: 2.1. Coverage: FR-8; UX-3, UX-10; NFR-5.

**Acceptance Criteria:**

**Given** existing result contracts, **when** evidence is displayed, **then**
Markov/Shapley differences, reliability, original/recommended budgets and
adjustments retain backend values and show scope, **and** pooled support,
extrapolation and unavailable predictions remain explicit.

**Given** a changed historical date filter or missing registered result,
**when** the page renders, **then** it does not imply model refitting or fabricate
values. Existing legacy results work; the empty registered state needs no
future run service to function.

## Epic 3: Save budgets and run reproducible strategies

The analyst can run supported models with durable inputs and saved options.

### Story 3.1: Execute isolated model runs

As the requesting analyst, I want runs bound to frozen input and parameters,
so that queued execution cannot mix sources or overwrite earlier results.

Dependencies: 1.1. Coverage: FR-4, FR-5, FR-10, FR-13, FR-15; NFR-2, NFR-6.

**Acceptance Criteria:**

**Given** a registered dataset and eligible attribution or optimization stage,
**when** `/api/workbench/runs` admits it, **then** dedicated input/output paths
and immutable options are captured before the existing queue executes,
**and** no default input is copied. Server execution refusal remains enforced.

**Given** success, failure, queued cancellation or restart, **when** records are
read, **then** every transition is durable and only exit-success plus validated
complete artifacts exposes result/downloads. A valid optimizer refusal remains
a report. Formerly active runs become interrupted, without automatic execution.

### Story 3.2: Save immutable budget revisions

As the requesting analyst, I want to save named budgets and revisions,
so that a changed draft cannot rewrite a strategy I already ran.

Dependencies: 3.1. Coverage: FR-9; UX-4, UX-12; NFR-2.

**Acceptance Criteria:**

**Given** a selected dataset, **when** a named positive budget and supported
policy are saved, **then** `/api/workbench/plans` stores a revision,
**and** Run saved revision reads server-owned values even if browser fields changed.

**Given** a stale expected revision or switched dataset, **when** saving or
running, **then** conflicts preserve drafts and explain Reload latest or original
scope. Other entity drafts remain visibly Not connected to model runs.

### Story 3.3: Operate registered model stages

As the requesting analyst, I want consistent run controls and explicit results,
so that background computation does not replace data while I read it.

Dependencies: 3.1, 3.2. Coverage: FR-8, FR-10; UX-5, UX-12; NFR-3.

**Acceptance Criteria:**

**Given** registered context, **when** a stage opens, **then** shared identity,
capability reasons and validated options replace unrelated legacy selectors,
**and** Run, progress, log, Stop and View results reflect actual server states.

**Given** completion or connection failure, **when** polling updates,
**then** existing displayed results do not silently change, read failures do not
claim job failure and stale responses cannot change the new context. Attribution
is not required before optimization.

## Epic 4: Read a strategy's formal evaluation

The analyst can evaluate and understand the exact selected strategy.

### Story 4.1: Evaluate a selected strategy run

As the requesting analyst, I want evaluation bound to my strategy,
so that checks cannot accidentally score a default or another dataset.

Dependencies: 3.1. Coverage: FR-5, FR-10, FR-11; NFR-2.

**Acceptance Criteria:**

**Given** a completed optimization run, **when** evaluation is admitted,
**then** only a same-dataset target is accepted, its artifact and optional matched
research are frozen, **and** explicit synthetic provenance/currency replace
default initializer inputs. Missing independent seed is reported skipped.

**Given** absent truth or failed contract checks, **when** the command completes,
**then** not-run and failed-check states remain in the complete report rather
than fabricated scores or a false process failure.

### Story 4.2: Display formal evaluation evidence

As the requesting analyst, I want readable evaluation layers,
so that I can understand validity, baselines and missing evidence without files.

Dependencies: 3.3, 4.1. Coverage: FR-11; UX-6, UX-12; NFR-5.

**Acceptance Criteria:**

**Given** a selected evaluation run, **when** its report opens, **then** strategy
identity, conservation, violations, baseline values, skipped reasons and
unavailable truth are rendered, **and** process state is distinct from check state.

**Given** missing evidence or the Willow panel, **when** displayed, **then**
Not run/Insufficient evidence is explicit and the demonstration stays separate.
No new aggregate score or future-revenue promise is introduced.

## Epic 5: Retrieve and recover a complete analysis

The analyst can trust provenance, recover work and use the appropriate deployment.

### Story 5.1: Retrieve run history and recover

As the requesting analyst, I want filtered persistent history and clear recovery,
so that I can reopen results and retry interrupted work safely.

Dependencies: 3.3, 4.2. Coverage: FR-12, FR-13; UX-7, UX-8; NFR-2.

**Acceptance Criteria:**

**Given** multiple stored runs, **when** filtering by dataset, stage, date or state,
**then** inline detail shows input digest, parameters, plan revision, target and
declared downloads, **and** opening old records does not switch global selection.

**Given** restart, failed source or storage, **when** returning to the application,
**then** completed records remain accessible, interrupted retry creates a new
identity and Settings/source controls remain reachable. Failed writes retain drafts.

### Story 5.2: Explain references and deployment capabilities

As the requesting analyst, I want trustworthy source references and diagnostics,
so that fixed demonstrations never imply approval of my dataset or strategy.

Dependencies: 1.2, 3.3. Coverage: FR-14, FR-15; UX-8, UX-9, UX-10.

**Acceptance Criteria:**

**Given** selected data, **when** Knowledge Base opens, **then** entities,
vocabulary and sources follow it and missing references are unavailable,
**and** fixed ontology cases keep a persistent Demonstration label.

**Given** static or disabled execution, **when** relevant pages open,
**then** local mutations are disabled without requests and backend controls also
refuse execution. Settings distinguishes source, storage and model readiness;
legacy database reading and existing protected operations remain intact.

### Story 5.3: Validate the complete analysis session

As the requesting analyst, I want proven end-to-end behavior,
so that the release can be used and reproduced beyond unit-test fixtures.

Dependencies: 1.3, 1.4, 2.2, 2.3, 5.1, 5.2. Coverage: all requirements;
UX-10, UX-11, UX-12; NFR-1 through NFR-6.

**Acceptance Criteria:**

**Given** two distinct datasets and two saved revisions, **when** the four
experience flows run in a real browser, **then** inputs, charts, exports, model
results, evaluation and restart history agree, **and** console/request errors,
stale-response races and missing-input remedies are verified.

**Given** keyboard-only operation, 375-pixel viewport, 200% zoom and 100,000-row
history, **when** navigating/importing/saving/running/exporting/recovering,
**then** required controls, focus and limits remain usable. Text/control contrast
meets DESIGN.md targets; reduced motion preserves progress without optional
transitions and background updates do not steal focus. Backend/frontend
tests and connected/static production builds pass; runtime outputs remain
ignored and owning specifications describe all delivered behavior.
