---
status: done
baseline_commit: 5d218b1
title: Retrieve run history and recover
compact: "Story 5.1 context, acceptance and verification record for the approved registered analysis workflow."
---

# Story 5.1: Retrieve run history and recover

Terms used below: Non-Functional Requirement (NFR), User Experience (UX), Application Programming Interface (API), Functional Requirement (FR).

Status: done

## Story and Acceptance Criteria

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

Implementation passed code and acceptance review. Review patches and evidence
are recorded in [release verification](../verification.md).

### Review Findings

- [x] [Review][Patch] Apply source, lifecycle, input and presentation corrections identified by the three review lanes; regression checks pass.
