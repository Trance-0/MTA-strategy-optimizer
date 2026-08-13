---
title: Zheyuan Wu (Trance-0)
description: Project manager work log covering pipeline development, integration, and algorithm testing
compact: "Work log of Trance-0 (Zheyuan Wu), project manager since 2026-08-03: standardized MTA-SIM interface and DNN credit model, bilingual documentation migration, module restructuring, script centralization, public release with Gitee mirror, GitHub Pages, and specification-oriented documentation rules."
order: 10
lang: en-US
---

# Work Log — Zheyuan Wu

> Project: Marketing ROI Analysis
> Handle: `Trance-0`
> Role: Project manager — pipeline development, data simulation and integration, algorithm testing
> Last updated: 2026-08-13

Entries are reconstructed from Git history. They record the change set behind each commit, not a separate narrative.

---

## 2026-08-13

### Completed

- Separated the two logs: renamed `docs/logs/` to `docs/version/` for per-patch descriptions, and added `docs/worklog/` for per-person progress, each with its own navigation entry.
- Added the contributor roster recording all five people, their handles, areas, and active periods, and moved the original root `log.md` to `docs/worklog/JiahaoYao.md` with its Chinese text preserved.
- Recorded the work-log rules in the repository instructions, including the three-bullet-per-day limit, page ownership, and the requirement that an agent confirm today's entry with its owner before committing.

### Next

- Collect first dated entries from Tianle Chen, Yi Liu, and Yayu Yu.

## 2026-08-12

### Completed

- Established specification-oriented programming as a repository rule, added the `compact` routing field to all 98 documentation pages, and merged the Workspace and Product sections into Overview.
- Reconciled documented behavior with shipped code: corrected the touchpoint key, replaced stale comparison statistics with the values in the published summary, fixed dead module paths, and removed an orphaned duplicate pipeline entry point.
- Prepared the public release: published to `Trance-0/MTA-strategy-optimizer`, activated GitHub Pages with base-aware deployment paths, and made Gitee an exact monitored one-way mirror.

### Next

- Continue reviewing the strategy model inherited from the previous developer.

## 2026-08-11

### Completed

- Separated concrete attribution models from the MTA framework, so `mta_attribution` owns every model and the shared interface while `mta_standard` stays framework-only.
- Migrated implementation documentation to one page per Python file.

### Next

- Complete the abbreviation and definition pass across the documentation set.

## 2026-08-07

### Completed

- Integrated the pinned MTA-SIM generator and centralized every maintained command under the project-root `script/` directory.
- Migrated upstream specifications and the preserved project history into the restructured repository, then merged the refactoring branch into `main`.
- Locked the Python environment with `uv`.

## 2026-08-04

### Completed

- Renamed modules after their responsibility rather than their data source, and split an 872-line combined file so each attribution model can be read and replaced on its own.
- Documented the data flow and added a module docstring to every Python file stating its place in the pipeline.

## 2026-08-03

### Completed

- Added the standardized MTA-SIM interface and the Deep Neural Network (DNN) credit model, giving every attribution algorithm one loading, execution, and comparison path.
- Made simulation ground-truth isolation structural: the model-facing dataset has no field that can hold it, and both loaders reject a table whose header carries a ground-truth column.
- Completed the bilingual documentation migration, publishing English by default and serving a construction placeholder for every `/zh/` route.

### Next

- Restructure the module layout so directory names state their responsibility.
