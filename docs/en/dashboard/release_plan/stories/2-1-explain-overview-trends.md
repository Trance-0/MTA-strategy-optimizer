---
status: done
baseline_commit: 5d218b1
title: Explain overview trends
compact: "Story 2-1 acceptance, developer context and verification record for the approved analysis workbench."
---

# Story 2.1: Explain overview trends

Status: done

## Story

As an analyst, I want explain overview trends, so that the selected evidence is understandable and trustworthy.

## Acceptance Criteria

1. Day, Monday-week and month grouping sum additive values and recompute ratios from totals.
2. Amount and ratio plots remain separate, with source/currency/window/count and matching values/exports.
3. Missing numbers and zero denominators stay unavailable. Performance remains usable without model output.

## Tasks / Subtasks

- [x] Verify visual-contract.md and page-behavior.md before code.
- [x] Write failing calendar/weighted-ratio/missing/export/100,000-row tests.
- [x] Implement pure chartData helper and TableView export.
- [x] Replace Command Center spend-background scaling with separate amount/ratio plots and grouping.
- [x] Verify unit suite, production build and selected-data browser behavior after 1.2.

## Dev Notes

Depends on 1.2 for source integration; pure presentation work can be tested on
existing snapshots independently. `CommandCenter.vue` currently rescales spend
into the ratio axis and defaults unavailable budget to zero. Replace these
approved defects without changing attribution math. `TableView.vue` owns the
collapsed DataTable, making it the shared export location. `theme.js` formats
missing values as --; never coerce null with Number. Use installed Vue/Plotly,
no upgrades or latest-version assumptions. Tests live dashboard/tests.
Owning pages: visual-contract.md, page-behavior.md, entity-lists.md.

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
