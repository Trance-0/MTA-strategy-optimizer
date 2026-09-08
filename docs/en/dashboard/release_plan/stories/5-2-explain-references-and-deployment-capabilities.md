---
status: done
baseline_commit: 5d218b1
title: Explain references and deployment capabilities
compact: "Story 5.2 context, acceptance and verification record for the approved registered analysis workflow."
---

# Story 5.2: Explain references and deployment capabilities

Terms used below: User Experience (UX), Application Programming Interface (API), Functional Requirement (FR).

Status: done

## Story and Acceptance Criteria

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
