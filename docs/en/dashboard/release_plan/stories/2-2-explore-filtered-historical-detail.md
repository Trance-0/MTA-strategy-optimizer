---
status: done
title: Explore filtered historical detail
compact: "Story 2-2 acceptance, implementation context and verification for filtered Campaign evidence and exports."
baseline_commit: 5d218b1d37e37498ec7f17ee695b240ac027af7b
---

# Story 2.2: Explore filtered historical detail

Status: done

## Story

As the requesting analyst, I want explore filtered historical detail, so that the selected evidence is understandable and trustworthy.

## Acceptance Criteria

1. Current-data filters and rankings retain context in detail; Back restores the invoking-row focus and Reset explicitly clears filters.
2. Budget density, grouped trends, path lengths and common paths expose matching value tables and filtered exports.
3. 100,000 observations use paging and bounded marks; seven leading categories plus Other retain accessible underlying rows and stable entity colors.
4. Missing research only disables history evidence; missing numbers remain unavailable and all amounts use the source currency.

## Tasks / Subtasks

- [x] Update owning page behavior and shared table export specification before implementation.
- [x] Write failing tests for bounded rankings, drill-down context, missing measures, grouping and export.
- [x] Implement current-data filters, seven-plus-Other rankings, accessible detail/reset, grouped chart values and consistent paths.
- [x] Add shared EntityTable filtered/sorted export and accessible search.
- [x] Run dashboard regression suite and production compilation; record browser integration handoff.

## Dev Notes

Campaigns.vue already owns densityGrid, window requests, performance/bridge/path tabs and paged EntityTable instances. Preserve density resolutions and the single tab conditional chain. Reuse chartData.aggregatePerformance, safeRatio and downloadCsv; do not add a library or attribution mathematics. EntityTable export must consume sorted before pageRows so its internal search agrees. Tests evaluate the view script with Vue reactivity and scoped fixture stores. Source context derives from dataset.scope before legacy dashboard context. Root owns source store and ChartData; only this story edits Campaigns and the agreed EntityTable export.

### References

- [Epic 2](../epics.md#epic-2-understand-performance-and-evidence)
- [Architecture](../architecture.md) and [Experience](../EXPERIENCE.md)
- [Page behavior](../../views/page-behavior.md) and [Visual contract](../../views/visual-contract.md)
- [Entity lists](../../views/entity-lists.md)

## Dev Agent Record

### Completion Notes

Implemented one-pass missing-aware category aggregation, seven-plus-Other touchpoint ranking with full underlying detail, native keyboard controls with focus restoration, explicit reset, source currency headers, calendar trend values, density-cell/interaction tables, shared path filtering and bounded path graphs. EntityTable exports its complete searched/sorted selection before paging.

Validation: seven new behavioral tests passed, including 100,000-row ranking, density and path fixtures, focus invocation order, weighted calendar ratio, euro-denominated export headers, searched/sorted export and model availability. Full dashboard suite: 156 tests passed, zero failed. `npm --prefix dashboard run build` passed; existing Plotly chunk-size warning remains. Browser keyboard/layout verification is assigned to the integrating task and has not been claimed here. No model mathematics, dependency upgrades, commits or sprint-status edits were made.

### File List

- `docs/en/dashboard/views/page-behavior.md`
- `dashboard/tests/analysis_views.test.js`
- `docs/en/dashboard/release_plan/stories/2-2-explore-filtered-historical-detail.md`
- `dashboard/src/views/Campaigns.vue`
- `dashboard/src/components/EntityTable.vue`
- `docs/en/dashboard/views/entity-lists.md`

## Change Log

2026-09-08: Story context created from approved Epic 2 and existing specifications.

2026-09-08: Implemented and verified; ready for integrated review.

## Release Review

Implementation passed code and acceptance review. Review patches and evidence
are recorded in [release verification](../verification.md).

### Review Findings

- [x] [Review][Patch] Apply source, lifecycle, input and presentation corrections identified by the three review lanes; regression checks pass.
