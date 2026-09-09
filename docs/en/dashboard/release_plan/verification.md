---
title: Analysis Workbench Verification
compact: "September 8 verification evidence: 187 backend, 168 frontend and 100 evaluation tests; connected/static builds, real generator/import/optimization/evaluation and restart flows, fixed review findings, 375-pixel reflow, native 200-percent Safari zoom and download verification."
status: passed
updated: 2026-09-08
---

# Analysis Workbench Verification

The implementation is on `feat/dashboard-workbench`, based on main
`5d218b1d37e37498ec7f17ee695b240ac027af7b` (0.9.47). All implementation stories
have code review, automated verification and integrated browser evidence.
The native browser and large-data checks below close story 5.3. No commit, push or
publication is represented by this report.

## Automated verification

#### Backend

`uv run --extra backend python -X utf8 -B -m unittest discover -s backend/tests -t . -p 'test_*.py'`
passed 187 tests. Dataset/workbench cases exercise duplicate natural keys,
complete reporting-window joins, malformed sidecars, frozen inputs, independent
run directories, stale plan revisions, cancellation, partial artifact refusal,
server capability refusal and recovery write failure. Real native attribution,
optimization and evaluation commands execute against temporary registered data.

#### Frontend

`npm --prefix dashboard test` passed 168 tests. New behavior checks cover
source switching and reordered responses, missing versus zero, weighted ratios,
100,000-row bounded ranking/density/curve projections, sorted filtered exports,
original-dataset draft retention, stale save responses, revision conflicts,
submitted-error focus, history pagination and read/write capability recovery.

#### Evaluation module

`uv run --extra strategy-evaluation python -X utf8 -B -m unittest discover -s modules/mta_strategy_evaluation/tests -t . -p 'test_*.py'`
passed 100 tests. Explicit observed/synthetic lineage and selected-strategy
scope are included; the existing model mathematics is unchanged.

#### Production builds

`npm --prefix dashboard run build` and `npm --prefix dashboard run build:static`
passed, including published Ontology Review fixture verification. The existing
large Plotly chunk warning remains. Static transport tests prove that
registered mutations refuse before a network request. `npm --prefix docs run build` passed. Modified-page compact metadata, length,
table shape and one-page implementation ownership checks passed.

## Browser sessions

The connected test server used an isolated ignored runtime with database mode
disabled. The browser interacted with actual routes and models, not mocked
requests. Temporary review inputs and results are not product fixtures.

#### Source selection and ingestion

Two standard interface imports with spend 12.50 and 50.00 produced distinct
Overview totals and return-on-spend ratios (2.40 and 0.60). Switching discarded
old data. Weekly grouping and displayed values agreed with the selected rows.
A standard file was validated, previewed, imported and selected with the
separate Use for analysis action; publication itself did not change selection.
The Toy generator passed preflight, completed simulation and registered a
12-row performance dataset. Its source, scope and unsupported-stage reasons
were visible after selection; no fallback supplied an ineligible model result.

#### Budget, optimization and evaluation

The browser saved plan revisions, retained an unsaved draft across a dataset
switch, disabled saving the mismatched draft and restored its original context.
A four-period ordinary research fixture ran real budget-response optimization.
The result displayed four observations, their fitted support range, the
allocation and the exact loaded run identity. Formal evaluation selected that
optimization and reported one projected, conserving strategy, omitted a missing
initializer with a reason and preserved unavailable optimal-allocation truth.
Success required an explicit latest-results refresh. The fixed Willow forecast
remained separately labeled as a demonstration.

#### Retention and responsive behavior

A full backend stop/start preserved dataset selection, saved plans, completed
optimization and its matching formal evaluation. New writes and run admission
remained available on the restarted writable runtime. Automated tests separately
prove active-record interruption and honest recovery-write failure.
At 375 pixels the long-identifier overflow found in the evaluation page was
fixed; the document width equaled the viewport width and required controls
stayed within it. Keyboard Enter operated navigation, plan save and saved-run
execution. A saved second revision ran with budget 140 and retained its plan
identity in history. Final-page console inspection returned no errors. Error-focus and detail-focus restoration have behavior tests.

## Review corrections

BMad's blind, edge-case and acceptance lanes reviewed the current change set.
No decision-needed or deferred code findings remained. These are fixed patches:

- Omit blank dataset filters in global runtime capability requests.
- Label result refresh as latest-dataset refresh, independently of a saved run.
- Preserve startup after recovery writes fail and refuse new execution honestly.
- Reject duplicate research observation natural keys before publication.
- Join research outcomes on both reporting start and end dates.
- Preserve drafts with their original dataset and explicitly reload conflicts.
- Bind displayed model provenance to loaded result records rather than runner state.
- Separate catalogue readability, runtime writability and execution capability.
- Show import-stage capabilities before publication.
- Keep empty-window monetary values unavailable rather than zero.
- Page retained runs and identify historical selections.
- Focus submitted-error summaries and associate them with inputs.
- Revoke stale writable capabilities after a current-context network failure.
- Keep long identifiers and native controls within a narrow page grid.
- Make retained-list scope reactive so a cold direct route renders stored runs and errors.

The relevant stories link this review and record their fixes. Retry submission
is also disabled while pending, and monetary tables follow the selected currency.

## Native browser and scale acceptance

#### Native 200-percent browser zoom

A separate Safari window selected the visible 200% entry in its page-zoom menu;
the menu then displayed 200%. Import fields and download controls, dataset
selection, saved-plan revision editing, evaluation-target selection, enabled
run controls, retained history and exact-record inspection remained operable.
A native template download completed and its saved file contained one row and
all 16 required fields. The helper attaches a temporary download link and
retains its object address through browser handoff before cleanup. Safari was
returned to its initial 100% zoom and the temporary window was closed.

#### 100,000 actual browser observations

A 12,700,449-byte standard multipart Comma-Separated Values (CSV) upload
registered 100,000 observations through the real ingestion route. The browser
loaded that identity and displayed spend 200,000, sales 600,000, 1,000,000
impressions, measured zero clicks and return on ad spend 3.00. It rendered
two plots and only 38 table rows, with the daily-row table stating 10,000
pages at ten rows per page. At 375 pixels the document matched viewport width.
A date filter reduced the slice to 1,000 observations, spend 2,000 and sales
6,000; Other exposed exactly 993 observations, retained the filter and moved
keyboard focus to its detail heading. These are actual browser results,
complementing the automated grouping, sorting, export and density tests.

## Verification limits

No external advertising service was connected and no public site was deployed.
The data push, file import and generated-source contracts were exercised with
local review inputs. Model predictions remain estimates with their stated
support limits. The existing large Plotly bundle warning remains; this change
does not upgrade or split the plotting dependency.
