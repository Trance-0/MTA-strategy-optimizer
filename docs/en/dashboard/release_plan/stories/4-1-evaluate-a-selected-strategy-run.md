---
title: "Story 4.1 Evaluate a selected strategy run"
compact: "Implementation context for evaluate a selected strategy run, including frozen provenance, existing service reuse, verification and owning specifications."
status: done
story_id: "4.1"
---

# Story 4.1: Evaluate a selected strategy run

Terms used below: Command-Line Interface (CLI).

Status: done

## Story

As the requesting analyst, I want evaluation bound to my strategy,
so that checks cannot accidentally score a default or another dataset.

## Acceptance Criteria

**Given** a completed optimization run, **when** evaluation is admitted,
**then** only a same-dataset target is accepted, its artifact and optional matched
research are frozen, **and** explicit synthetic provenance/currency replace
default initializer inputs. Missing independent seed is reported skipped.

**Given** absent truth or failed contract checks, **when** the command completes,
**then** not-run and failed-check states remain in the complete report rather
than fabricated scores or a false process failure.

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

Build on durable runs. Require same-dataset/digest optimization output. Copy only target campaign_strategy.json to run inputs; no initializer fallback. Add CLI synthetic-source, currency and advertiser options with legacy defaults preserved; explicit invocation does not consult default initializer metadata. Constrain evaluation observations to target scope and preserve not-run truth. Test cross-dataset rejection, explicit real provenance, no default reads and missing seed skip.

Work in backend/services/workbench.py, modules/mta_strategy_evaluation/src/evaluate_strategies.py, backend/tests/test_workbench.py, modules/mta_strategy_evaluation/tests/test_evaluate_strategies.py. Use existing Python 3.12+ environment and Flask dependency;
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

Implemented matching dataset/digest strategy selection, frozen target output, explicit source/currency/advertiser evaluation arguments and optional matched research. Real optimization and evaluation use the same registered inputs; absent initializer is skipped and external input remains non-synthetic. CLI regression verifies no default initializer read.

### File List

Implemented files: backend/services/workbench.py, modules/mta_strategy_evaluation/src/evaluate_strategies.py, backend/tests/test_workbench.py, modules/mta_strategy_evaluation/tests/test_evaluate_strategies.py.

## Change Log

2026-09-08: Developer context prepared from approved architecture and epics.

2026-09-08: Implementation and regression verification completed; status review pending adversarial integration review.

## Release Review

Implementation passed code and acceptance review. Review patches and evidence
are recorded in [release verification](../verification.md).

### Review Findings

- [x] [Review][Patch] Apply source, lifecycle, input and presentation corrections identified by the three review lanes; regression checks pass.
