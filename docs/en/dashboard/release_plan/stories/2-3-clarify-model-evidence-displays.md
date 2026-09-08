---
status: done
title: Clarify model evidence displays
compact: "Story 2-3 acceptance, implementation context and verification for model scope, reliability and response availability."
baseline_commit: 5d218b1d37e37498ec7f17ee695b240ac027af7b
---

# Story 2.3: Clarify model evidence displays

Status: done

## Story

As the requesting analyst, I want clarify model evidence displays, so that the selected evidence is understandable and trustworthy.

## Acceptance Criteria

1. Attribution differences, reliability, original/recommended budgets and adjustments retain backend values and state scope.
2. Pooled support, extrapolation and unavailable predictions are explicit; response observations use bounded marks with full value access.
3. Historical date filters never imply refitting; empty registered results say Not run and legacy evidence remains usable.

## Tasks / Subtasks

- [x] Update owning evidence specification before code.
- [x] Write failing evidence tests for missing parameters, unscaled percentage-point differences and bounded observations.
- [x] Clarify stored scope, currency, response support and unavailable values without modifying model algorithms or runner/evaluation sections.
- [x] Run dashboard regressions and production compilation; record browser integration handoff.

## Dev Notes

CampaignOptimizer.vue renders comparison fractions and already-scaled gap_pp, reliability, a presentation-only budget restatement and backend optimization allocations. Its existing expectedRevenue helper projects the serialized exponential fit; incomplete parameters currently silently become zero. Keep the existing formula with strict availability guards. Preserve root-owned runner and evaluation sections. Reuse TableView for chart values and EntityTable for potentially large observations. Root implements registered execution and selected-run identity. No model refit is caused by historical filters. Depend on story 2.1 for shared safe values and export; use installed Vue/Plotly without upgrades.

### References

- [Epic 2](../epics.md#epic-2-understand-performance-and-evidence)
- [Architecture](../architecture.md) and [Experience](../EXPERIENCE.md)
- [Page behavior](../../views/page-behavior.md) and [Visual contract](../../views/visual-contract.md)
- [Entity lists](../../views/entity-lists.md)

## Dev Agent Record

### Completion Notes

Preserved backend allocation/reliability values, clarified stored evidence scope and historical-filter independence, labeled percentages and percentage points correctly, removed zero defaults for unavailable model totals, guarded incomplete fitted parameters and retained available observations independently. Response plots use at most 500 deterministic observations with all rows in a paged exportable table; fitted values, attribution recommendations and allocations are readable/exportable.

Validation: seven new behavioral tests passed, including 100,000-row ranking, density and path fixtures, focus invocation order, weighted calendar ratio, euro-denominated export headers, searched/sorted export and model availability. Full dashboard suite: 156 tests passed, zero failed. `npm --prefix dashboard run build` passed; existing Plotly chunk-size warning remains. Browser keyboard/layout verification is assigned to the integrating task and has not been claimed here. No model mathematics, dependency upgrades, commits or sprint-status edits were made.

### File List

- `docs/en/dashboard/views/page-behavior.md`
- `dashboard/tests/analysis_views.test.js`
- `docs/en/dashboard/release_plan/stories/2-3-clarify-model-evidence-displays.md`
- `dashboard/src/views/CampaignOptimizer.vue`

## Change Log

2026-09-08: Story context created from approved Epic 2 and existing specifications.

2026-09-08: Implemented and verified; ready for integrated review.

## Release Review

Implementation passed code and acceptance review. Review patches and evidence
are recorded in [release verification](../verification.md).

### Review Findings

- [x] [Review][Patch] Apply source, lifecycle, input and presentation corrections identified by the three review lanes; regression checks pass.
