---
title: Analysis Workbench Implementation Readiness
compact: "Independent critical self-audit of release requirements, design, architecture, story coverage and dependencies before sprint admission; records resolved gaps and the limits of planning readiness."
stepsCompleted: [1, 2, 3, 4, 5, 6]
inputDocuments: [prd.md, architecture.md, epics.md, DESIGN.md, EXPERIENCE.md, review-prd.md, decision-log.md]
status: ready
date: 2026-09-08
---

# Analysis Workbench Implementation Readiness

Terms used below: User Experience (UX), User Interface (UI), Functional Requirement (FR).

## Document discovery

The approved workspace contains one requirements document (`prd.md`), one
architecture (`architecture.md`), one complete epic document (`epics.md`) and
the paired visual/behavioral design (`DESIGN.md`, `EXPERIENCE.md`). All are whole
documents, not shards. `review-prd.md` is review evidence, not a competing
requirements source. No duplicate or missing required document was found.

The design filenames are explicit workflow bindings rather than `*ux*` matches.
`decision-log.md` resolves language, authorship assumptions and historical
planning-directory conflicts. Existing user approval covers these exact inputs.
This is a fresh critical self-audit after story drafting, not a claim of an
independent reviewer or of tested implementation.

## Requirements analysis

The complete fifteen requirements are extracted below to preserve acceptance
meaning during coverage review.

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

### Cross-cutting acceptance and constraints

Charts name units, date range, source and sample size, and have readable tables.
Missing values differ from zero. A zero denominator is unavailable, not a zero
ratio. One axis per plot and stable entity colors remain the visual contract.
Keyboard and narrow layouts must remain usable; 100,000-row history retains paging,
bounded chart marks, lazy resources and protection from stale responses.

Success is demonstrated by two visibly different datasets and two saved budget
revisions, equivalent results through each ingestion channel, report/plot/export
agreement, and recovery after restart. Test counts alone do not prove browser
interaction. No success metric claims real-world causal lift or optimality.

No arbitrary file mapping, direct third-party connector, cross-dataset analysis,
new attribution/optimization mathematics, automated activation, or live ontology
review. Existing Vue, Plotly, Flask, English UI and Python model contracts stay.
Standard templates reuse existing report and research contracts. The approved
storage default is a persistent backend runtime directory; no mandatory business
database migration is introduced. There are no unresolved product-scope questions.

## Epic coverage validation

#### FR-1

Covered by stories 1.3; acceptance retains the source requirement.

#### FR-2

Covered by stories 1.1, 1.4; acceptance retains the source requirement.

#### FR-3

Covered by stories 1.1, 1.2, 1.3, 1.4; acceptance retains the source requirement.

#### FR-4

Covered by stories 1.1, 1.2, 1.3, 3.1; acceptance retains the source requirement.

#### FR-5

Covered by stories 1.1, 1.2, 3.1, 4.1; acceptance retains the source requirement.

#### FR-6

Covered by stories 2.1; acceptance retains the source requirement.

#### FR-7

Covered by stories 2.2; acceptance retains the source requirement.

#### FR-8

Covered by stories 2.3, 3.3; acceptance retains the source requirement.

#### FR-9

Covered by stories 3.2; acceptance retains the source requirement.

#### FR-10

Covered by stories 3.1, 3.3, 4.1; acceptance retains the source requirement.

#### FR-11

Covered by stories 4.1, 4.2; acceptance retains the source requirement.

#### FR-12

Covered by stories 5.1; acceptance retains the source requirement.

#### FR-13

Covered by stories 3.1, 5.1; acceptance retains the source requirement.

#### FR-14

Covered by stories 5.2; acceptance retains the source requirement.

#### FR-15

Covered by stories 1.2, 1.4, 3.1, 5.2; acceptance retains the source requirement.

All 15 requirements have specific story coverage: 15 of 15 (100%). No extra
functional requirement or missing requirement was found. Final story 5.3
rechecks all requirements as an integrated session rather than replacing their
individual acceptance. Coverage entries use headings instead of a matrix table
in accordance with repository documentation rules.

## Design alignment

Both design spines exist and cover the four approved user flows. Dataset
context outside the resource-failure boundary, saved plan conflicts, explicit
result selection, separate report/check status and static refusals align with
architecture services and requirements. No unimplemented external platform
integration is assumed.

Two small story-acceptance omissions were found and corrected before this gate:
story 2.2 now explicitly retains underlying rows for Other ranking groups;
story 5.3 explicitly validates design contrast, reduced motion and non-stealing
background focus. The remaining layout, keyboard, zoom and component behaviors
are assigned through UX-1 through UX-12 and final browser verification.

These corrections restore documented experience requirements; they add no new
scope. Visual correctness remains to be demonstrated in the running browser.

## Epic quality review

Six approved workstreams contain 16 uniquely numbered stories, including one
completed planning prerequisite and 15 product stories. A dependency scan checked
each declared predecessor against earlier story identifiers; every dependency
points backward and there are no cycles. E2 works with existing result contracts
and honest empty states, without requiring E3's new run service.

E0 is deliberately a completed baseline prerequisite from the approved plan,
not a future infrastructure epic or a claim of user-facing implementation.
E1 delivers observable data registration/import and selection; E2 delivers
readable analysis; E3 delivers runnable plans; E4 delivers evaluable strategies;
E5 delivers retrievable sessions and recovery. These are complete user outcomes.

Each story has a requesting analyst, a concrete benefit and Given/When/Then
acceptance including relevant refusal or missing-data states. Story 3.1 is the
largest integration unit but remains confined to a queue adapter and existing
module execution; plan editing and client controls are separate stories. No
story creates future business tables, changes model mathematics or scaffolds a
new application. Shared API/store changes require explicit ownership when
independent later stories run concurrently; the dependency graph alone does not
authorize simultaneous edits to the same file.

No unresolved critical or major planning violation was found. Product code must
still satisfy its owning English behavior specification before implementation;
this gate does not permit substituting an epic summary for field-level contracts.

## Summary and recommendations

**READY for sprint admission.** This September 8 critical self-audit found two
minor acceptance omissions in one category (design coverage), both corrected
before the verdict. There are no unresolved critical or major findings. The
earlier requirements and architecture review findings remain resolved.

Create the complete sprint inventory, then prepare story 1.1 with the owning
dataset specification and existing input adapters. Keep every other unimplemented
story in backlog until its context is created; never count a story as complete
because its description exists. Require focused backend/frontend checks per
story and the four real-browser flows before release completion.

This assessment establishes planning consistency. It is neither code review nor
evidence of a successful product build, model execution or deployment.
