---
title: Zheyuan Wu (Trance-0)
description: Project manager work log covering pipeline development, integration, and algorithm testing
compact: "Work log of Trance-0 (Zheyuan Wu), project manager: Multi-Touch Attribution Simulator (MTA-SIM) integration, research-scale persistence, module restructuring, specification-oriented documentation, Vue dashboard delivery, public release, GitHub Pages, and Gitee plus self-hosted Gitea mirroring."
order: 10
lang: en-US
---

# Work Log — Zheyuan Wu

> Project: Marketing ROI Analysis
> Handle: `Trance-0`
> Role: Project manager — pipeline development, data simulation and integration, algorithm testing
> Last updated: 2026-08-20

Entries are reconstructed from Git history. They record the change set behind each commit, not a separate narrative.

---

## 2026-08-20

### Completed

- Gave Budget Manager's Add/Edit modal a Form view beside the existing JSON editor: `masterObjectFields.js` declares each section's fields against the canonical vocabulary in `mta_common`, and `MasterObjectForm.vue` renders one row per field — plain input for free text, three-way select for a boolean, chip list for a multiselect, and a search-filterable `<datalist>` combobox for every enum-backed or suggested field, the one pattern a non-technical reader already knows from a country selector. Also fixed both views opening a new record on a bare `{}` by merging it over a full field template first.
- Diagnosed a production deploy where a freshly activated release and the rollback to the previously active one failed the identical health check — impossible from a per-release code difference, since the rollback restores code that was already running. Found `dashboard_healthy()` was gating activation on `GET /api/dashboard`, which returns `503` whenever the host's configured database is unreachable or empty; that setting is shared across every release on the host, so it fails every release alike. Added a `GET /api/health` liveness route independent of database state and repointed the health check at it, verified locally against a real PostgreSQL instance with 47 dashboard tests passing.

### Next

- Confirm on the target host whether the database configured in `${ETC_ROOT}/dashboard.env` is actually reachable now that activation no longer blocks on it; the earlier `503`s may point to a network or credential problem worth fixing independently.

## 2026-08-19

### Completed

- Built out the Campaign budget optimizer to a documented, verified state: the response dataset with its enforced attribution and ground-truth exclusion, the two-stage saturating budget-to-spend-to-revenue fit with target-history, pooled-transfer, and insufficient-support labelling, the shadow-price solver that equalizes marginal expected revenue under both budget usage policies, and the structured refusals it returns instead of a fabricated optimum. Verified end to end against freshly generated MTA-SIM output: 40 observations, 2 fitted Campaigns, full budget allocated, marginal returns equal to seven decimal places.
- Wrote `docs/en/strategy-recommendation/campaign-budget-optimizer.md` as the owning specification, including the code-level contract for all five source files, and corrected every page that still described the optimizer as unimplemented — the strategy index, module inventory, data-flow reference (new Layer 9), and five canonical data-model pages whose "no optimizer exists yet" claims had become false. Added six supporting definitions, and taught the Draw.io exporter to skip `-human` sources so a hand-authored diagram can sit beside its agent-authored counterpart without the site publishing two pictures of one subject.
- Surfaced the plan in the dashboard by reusing the existing loader pattern rather than adding a parallel one: `loadCampaignStrategy()` beside `loadBudgetRecommendation()`, mode-independent because the artifact is command-produced, and replaced the Optimization Log's hard-coded `NOT RUN` fifth stage with the real allocation, its evidence, and named extrapolation and pooled-transfer warnings. 476 Python tests pass.
- Ran down the reported local-versus-published layout difference and found it was data emptiness rather than a design divergence: the published snapshot is exported with `DATABASE=false` and no `MTA_SIM_DATA_DIR`, so every canonical entity section is genuinely empty there, which I confirmed by probing both deployments (0 records against 40 Campaigns and 40 Ad Groups). Made the deployment itself explicit instead — capability derived from the snapshot's data source rather than the build flag, so a local file-mode run is correctly read-only too; Excel green for the deployments that cannot write against brand blue for the connected one, applied by overriding the tokens the stylesheet already reads; and an empty section that names its own cause rather than reading as a fault. Replaced Budget Manager's seven stacked `<details>` lists with a 1Panel-style entity table in the same pass: declared summary columns as the row abstract, the whole record behind the row's Edit control, 15/30/50/100 paging, filtering, batch selection keyed by row identity rather than page index, and every deletion behind a confirmation that names what it will archive — a batch that fails part-way reports where it stopped rather than claiming success. 47 dashboard tests pass, 13 new.

### Next

- Extend the response model below the Campaign once an Ad Group feature table exists; the optimizer deliberately reports `NOT_AD_GROUP_OPTIMIZED` until candidate features can distinguish one new Ad Group from another.
- Decide whether the published build should carry a committed MTA-SIM sample run so its entity sections demonstrate the list rather than only its empty state.

## 2026-08-18

### Completed

- Restructured the doc site's nav bar — dropped the redundant Home item, moved Dashboard to second position, and merged Versions and Work Log into a Logs dropdown — renamed the Datasets section to Market Simulation across the config, directory, and roughly twenty cross-references, fixed `docs/version/0.9/` not collapsing by default, and loosened the AGENTS.md work-log rule so an agent writes today's entry automatically instead of asking first; this entry is the first written under that rule.
- Followed through on the data-representation unification plan: built and documented `modules/mta_common/`, then integrated an independent MTA-SIM domain across native five-segment interaction generation, Provider missingness, Products/Campaigns, budget experiments, organic/incremental outcomes, deterministic 10k CSV and direct 100k PostgreSQL modes; rewired standard loading, attribution and strategy boundaries to canonical adapters; and expanded the Vue dashboard with canonical master-data drafts, full Touchpoint/config inspection, historical Campaign exploration, and presentation-only similarity, with 459 automated tests passing.
- Recorded the `external/UI_design/` reference prototype's move to `design-artifacts/UI_design/`, matching the documented split between `external/` for pinned third-party repositories and `design-artifacts/` for historical product vision, and added a project-wide rule restricting documentation tables to strict two-item comparisons, decomposing 135 non-comparison tables into sub-level headings across 45 files under `docs/en`, `docs/version`, and `docs/worklog` (`docs/en/strategy-evaluation/` was excluded, out of scope for this pass).

### Next

- Revisit the canonical class-index dependency diagram after those runtime integrations establish the adopted relationships; adjust its grouping or topology if the implemented dependency graph differs from the current foundation.

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
