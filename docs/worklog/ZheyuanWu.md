---
title: Zheyuan Wu (Trance-0)
description: Project manager work log covering pipeline development, integration, and algorithm testing
compact: "Work log of Trance-0 (Zheyuan Wu), project manager: MTA-SIM integration, module restructuring, public release, specification-oriented documentation, dashboard delivery from Streamlit through stlite to the Vue client over a Node API, GitHub Pages, and Gitee plus self-hosted Gitea mirroring."
order: 10
lang: en-US
---

# Work Log — Zheyuan Wu

> Project: Marketing ROI Analysis
> Handle: `Trance-0`
> Role: Project manager — pipeline development, data simulation and integration, algorithm testing
> Last updated: 2026-08-15

Entries are reconstructed from Git history. They record the change set behind each commit, not a separate narrative.

---

## 2026-08-15

### Completed

- Replaced the Streamlit and stlite dashboard with a Vue 3 client over an Express JSON API, keeping the six views, the navigation rail, and the `DATABASE=true/false` contract unchanged in behavior, and published it as a static build reading a snapshot exported from the committed artifacts.
- Fixed three defects that broke the promise that no view can tell which source it is reading: SQL row order against artifact order, a `Date` formatted into a weekday and a month name, and a CSV blank arriving where PostgreSQL sends NULL — 1,281 differences across four loaders, now none. Added the parity command and the twenty-seven-test suite the repository had been missing.
- Rewrote both launchers for a one-click cold start and fixed five failures only a clean machine reaches, the sharpest being a Node version floor written as a major number where Vite's range turns on the minor: its bundler binding is optional, so npm skipped it in silence and the build failed minutes later naming neither Node nor the version.

### Next

- Collect first dated entries from Tianle Chen, Yi Liu, and Yayu Yu.
- This week: define a minimal, class-based, object-oriented set of data structures shared across the project's modules and the dashboard's database schema, and implement a full runnable optimizer module built on them. See [Planned](../version/#planned) in the version log.

## 2026-08-14

### Completed

- Published the dashboard to GitHub Pages at the site root and moved the documentation to `/docs/`, running the same `dashboard/` sources in the browser through stlite because Pages cannot host a Streamlit server, then fixed the boot splash, which lifted when the runtime started rather than when the dashboard painted and so showed the stylesheet as text for the twenty seconds in between.
- Made the published build honest about its data: `DASHBOARD_HOSTED` forces file mode, since WebAssembly has no socket to reach PostgreSQL, and the settings modal shows the local-run instructions instead of a credential form that could never connect.
- Added `dashboard/run.sh` and `run.bat`, the rail's **Docs** and **Repo** links, and generalized the GitHub-to-Gitea mirror to support validated self-hosted HTTPS destinations such as `git.trance-0.com`.

### Next

- Collect first dated entries from Tianle Chen, Yi Liu, and Yayu Yu.

## 2026-08-13

### Completed

- Separated the two logs into `docs/version/` for per-patch descriptions and `docs/worklog/` for per-person progress, added the contributor roster, and recorded the work-log ownership rules in the repository instructions.
- Built the Streamlit dashboard: six views over the pipeline's own artifacts, a `DATABASE=true/false` dual-source contract verified by `script/verify_source_parity.py`, and the PostgreSQL import into an eighteen-table schema.
- Rebuilt the sidebar as the reference design's navigation rail with a settings module for database credentials and streaming logs, and restructured the documentation to match: implementation pages merged into their owning sections and the dashboard data model documented.

### Next

- Publish the dashboard so reviewers can open it without a local Python environment.

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
