---
status: done
baseline_commit: 5d218b1
title: Select source-consistent data
compact: "Story 1-2 acceptance, developer context and verification record for the approved analysis workbench."
---

# Story 1.2: Select source-consistent data

Terms used below: Application Programming Interface (API).

Status: done

## Story

As an analyst, I want select source-consistent data, so that the selected evidence is understandable and trustworthy.

## Acceptance Criteria

1. Selecting a registered identifier clears every old resource and loads only that identity; legacy is explicit.
2. Late success, error, progress and reload cannot overwrite a newer context.
3. Selector shows metadata/capability reasons and remains available outside page errors; selection persists only as an identifier.
4. Client list/import/run operations preserve errors and static refusals.

## Tasks / Subtasks

- [x] Verify source-owning specs and new control contract before implementation.
- [x] Add failing reordered selection/reload tests for non-windowed resources.
- [x] Implement backend registered resource projection and dispatch before legacy database health, returning empty missing results with no fallback.
- [x] Implement client boundary and context generation guards, retaining existing window behavior.
- [x] Implement shared workbench catalogue and accessible selector; mount before resource errors.
- [x] Verify frontend regression/build and integrated two-dataset selection after story 1.1.

## Dev Notes

Depends on 1.1 for integrated acceptance. Independent client tests may use the
frozen API contract while server implementation proceeds. `useDashboard.js`
currently keys only history windows, merges shallow immutable snapshots, and
reload waits before invalidating; all resources need a generation token.
`App.vue` owns lazy route loading and Settings has no resource prerequisite.
Do not couple the selector to routeLoaded. Existing tests import source with
stubbed client modules; preserve this meaningful race-test technique.
Owning pages: dashboard/index.md, navigation.md, workbench-controls.md.

## Dev Agent Record

### Completion Notes

Implementation pending.

### File List

See the owning specification named in Dev Notes and [release verification](../verification.md).

## Change Log

2026-09-08: Context created from approved architecture, design and owning specifications.

## Release Review

Implementation passed code and acceptance review. Review patches and evidence
are recorded in [release verification](../verification.md).

### Review Findings

- [x] [Review][Patch] Apply source, lifecycle, input and presentation corrections identified by the three review lanes; regression checks pass.
