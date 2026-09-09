---
title: "Story 3.2 Save immutable budget revisions"
compact: "Implementation context for save immutable budget revisions, including frozen provenance, existing service reuse, verification and owning specifications."
status: done
story_id: "3.2"
---

# Story 3.2: Save immutable budget revisions

Status: done

## Story

As the requesting analyst, I want to save named budgets and revisions,
so that a changed draft cannot rewrite a strategy I already ran.

## Acceptance Criteria

**Given** a selected dataset, **when** a named positive budget and supported
policy are saved, **then** `/api/workbench/plans` stores a revision,
**and** Run saved revision reads server-owned values even if browser fields changed.

**Given** a stale expected revision or switched dataset, **when** saving or
running, **then** conflicts preserve drafts and explain Reload latest or original
scope. Other entity drafts remain visibly Not connected to model runs.

## Tasks / Subtasks

- [x] Add failing tests for the service behavior and failure boundaries.
- [x] Implement the owning contract using existing model/service boundaries.
- [x] Run focused tests and backend regression checks; resolve failures.
- [x] Update source specification and actual verification record for review.

## Dev Notes

Owning contract: [Budget Plans and Retained Runs](../../budget-plans.md).
Dataset contract: [Registered Analysis Datasets](../../datasets.md).
Architecture: [Release architecture](../architecture.md).
Experience: [Release experience](../EXPERIENCE.md).
The existing source evidence has been read, including the app, task manager,
artifact parser and relevant module entry points. No previous implementation
story in this epic is claimed complete; contract-first parallel work must pass
integration against its predecessors before review.

Build on run admission. Persist immutable plan revisions and atomically replace latest plan metadata. Require expected revision for update; dataset cannot change. Validate positive finite total and exact enum. Plan start overrides browser total/policy from stored revision. Test concurrent stale updates, revision-specific run input and invalid budgets. Frontend plan screen is owned by root; backend acceptance remains independently testable.

Work in backend/services/workbench.py, backend/api/workbench.py, backend/tests/test_workbench.py. Use existing Python 3.12+ environment and Flask dependency;
no new packages or command wrappers. Tests use temporary runtime roots and
patched environment providers. App wiring must retain existing routes, access
checks and structured errors. Service callbacks persist all terminal transitions.
No browser model math, no source environment mutation and no sample fallback.

The applicable create-story checklist has been applied: file ownership, existing
interfaces, failure cases and testing are explicit. There are no latest-version
questions or dependency upgrades; source/lockfile behavior is authoritative.

## Dev Agent Record

### Agent Model Used

Codex implementation agent.

### Debug Log References

`uv run --extra backend python -m unittest backend.tests.test_workbench modules.mta_strategy_evaluation.tests.test_evaluate_strategies`: 19 tests passed.
`uv run --extra backend python -m unittest discover -s backend/tests`: 183 tests passed.
The focused suite executes real attribution, optimization and evaluation commands in temporary runtime storage; no model output is checked into the repository.

### Completion Notes List

Implemented immutable plan revisions with atomic latest metadata, stale revision conflicts, dataset binding, finite budget validation and stored revision precedence. Focused tests prove later edits cannot change queued run parameters. Frontend review is coordinated by the parent agent.

### File List

Implemented files: backend/services/workbench.py, backend/api/workbench.py, backend/tests/test_workbench.py.

## Change Log

2026-09-08: Developer context prepared from approved architecture and epics.

2026-09-08: Implementation and regression verification completed; status review pending adversarial integration review.

## Release Review

Implementation passed code and acceptance review. Review patches and evidence
are recorded in [release verification](../verification.md).

### Review Findings

- [x] [Review][Patch] Apply source, lifecycle, input and presentation corrections identified by the three review lanes; regression checks pass.
