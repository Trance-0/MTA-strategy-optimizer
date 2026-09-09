---
status: done
baseline_commit: 5d218b1
title: Validate the complete analysis session
compact: "Story 5.3 context, acceptance and verification record for the approved registered analysis workflow."
---

# Story 5.3: Validate the complete analysis session

Terms used below: Non-Functional Requirement (NFR), User Experience (UX), Application Programming Interface (API).

Status: done

## Story and Acceptance Criteria

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

## Tasks / Subtasks

- [x] Update owning behavior specification before implementing the story.
- [x] Implement the declared control and backend integration with context identity preserved.
- [x] Verify meaningful edge/failure cases with tests and browser interactions.
- [x] Review result/source lineage and mark only verified acceptance complete.

## Dev Notes

Read architecture.md and EXPERIENCE.md for the exact workflow; user-authorized
scope is fixed. New browser controls and store are specified by
../../workbench-controls.md; generator by ../../data-generator.md; routes and
existing views keep their current owning pages. Preserve existing Vue/Plotly
and Flask commands, no dependencies or new model math. API calls only client.js.
Use immutable metadata and stale-response tokens. Static operations refuse
locally. Existing snapshots remain available only as explicitly selected legacy
source. Registered observations never use legacy results. Own tests belong in
backend/tests or dashboard/tests; final integrated acceptance belongs 5.3.
Generated completion stores datasetId, preserves preview if registration fails,
and selection changes only through Use for analysis. Local files and generated
runtime data remain ignored; no outputs committed.

## Dev Agent Record

### Completion Notes

Implemented and reviewed. See [release verification](../verification.md) for actual tests, browser evidence and remaining release acceptance limits.

### File List

See the owning specification named in Dev Notes and [release verification](../verification.md).

## Change Log

2026-09-08: Context created from accepted stories and owning service/control specifications.

## Release Review

Functional implementation, automated checks, 375-pixel reflow, native Safari
200-percent zoom, real file download and the 100,000-observation browser flow
passed. See [release verification](../verification.md) for the exact evidence.

### Review Findings

- [x] [Review][Patch] Apply source, lifecycle, input and presentation corrections identified by the three review lanes; regression checks pass.
- [x] Native Safari 200-percent zoom acceptance completed; original zoom restored.
