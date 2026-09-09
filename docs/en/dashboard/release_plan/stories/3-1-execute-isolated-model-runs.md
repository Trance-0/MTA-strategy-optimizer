---
title: "Story 3.1 Execute isolated model runs"
compact: "Implementation context for execute isolated model runs, including frozen provenance, existing service reuse, verification and owning specifications."
status: done
baseline_commit: 5d218b1d37e37498ec7f17ee695b240ac027af7b
story_id: "3.1"
---

# Story 3.1: Execute isolated model runs

Terms used below: Command-Line Interface (CLI).

Status: done

## Story

As the requesting analyst, I want runs bound to frozen input and parameters,
so that queued execution cannot mix sources or overwrite earlier results.

## Acceptance Criteria

**Given** a registered dataset and eligible attribution or optimization stage,
**when** `/api/workbench/runs` admits it, **then** dedicated input/output paths
and immutable options are captured before the existing queue executes,
**and** no default input is copied. Server execution refusal remains enforced.

**Given** success, failure, queued cancellation or restart, **when** records are
read, **then** every transition is durable and only exit-success plus validated
complete artifacts exposes result/downloads. A valid optimizer refusal remains
a report. Formerly active runs become interrupted, without automatic execution.

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

Use TaskManager ManagedOperation append transition persistence; immutable run input/output directories; frozen validated datasets; reuse native attribution reader, single-scope path aggregation and module CLI. No global model_outputs publication. Validate complete fixed artifacts before success; expose pure parsed results. Test two queued runs, missing artifacts, disabled server execution, queued cancellation, safe paths and restart interruption.

Work in backend/services/workbench.py, backend/api/workbench.py, backend/tests/test_workbench.py; app blueprint wiring. Use existing Python 3.12+ environment and Flask dependency;
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

Implemented frozen native inputs, existing queue execution with durable transitions, complete artifact validation, safe downloads and restart interruption. Real native attribution execution passes. App integration is coordinated by the parent agent; final adversarial review is pending.

### File List

Implemented files: backend/services/workbench.py, backend/api/workbench.py, backend/tests/test_workbench.py; app blueprint wiring.

## Change Log

2026-09-08: Developer context prepared from approved architecture and epics.

2026-09-08: Implementation and regression verification completed; status review pending adversarial integration review.

2026-09-08: Adversarial review correction keeps application startup and truthful interrupted history available when recovery writes fail; storage capabilities report unavailable, new runs are refused and repaired storage can persist recovery on retry. Focused dataset/workbench/evaluation verification: 40 tests passed.

## Release Review

Implementation passed code and acceptance review. Review patches and evidence
are recorded in [release verification](../verification.md).

### Review Findings

- [x] [Review][Patch] Apply source, lifecycle, input and presentation corrections identified by the three review lanes; regression checks pass.
