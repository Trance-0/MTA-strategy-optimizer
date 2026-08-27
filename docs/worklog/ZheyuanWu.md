---
title: Zheyuan Wu (Trance-0)
description: Project manager work log covering pipeline development, integration, and algorithm testing
compact: "Zheyuan Wu's project-management work log: MTA-SIM integration, attribution and strategy pipelines, canonical models, PostgreSQL schema selection and setup, Vue/Flask delivery, specification-oriented documentation, GitHub Pages, and deployment automation."
order: 10
lang: en-US
---

# Work Log — Zheyuan Wu

> Project: Marketing ROI Analysis
> Handle: `Trance-0`
> Role: Project manager — pipeline development, data simulation and integration, algorithm testing
> Last updated: 2026-08-27

Entries are reconstructed from Git history. They record the change set behind each commit, not a separate narrative.

---

## 2026-08-27

### Completed

- Made which schema of the PostgreSQL instance the dashboard reads a selection rather than an assumption, now that the instance holds this project's tables in `public` and three simulation scenarios behind `mta`. `PG_SCHEMA` pins every connection through one libpq connect option, so statements built from `models.py` and reflective reads of the external tables both follow it without a second definition of where a table lives. Wrote the fallback first and reverted it: `-csearch_path=mta,public` would let a schema holding history but not this project's tables resolve the rest from `public`, putting one scenario's attribution beside another's history with nothing on the page saying so. A census over `pg_namespace`, filtered by `has_schema_privilege`, decides selectability by whether all fourteen loader tables are present; a schema that fails is listed and disabled rather than hidden, carrying what it lacks and the command that would populate it. Extended that census into a discovery-driven setup menu rather than hard-coding `public` and `mta`: empty or new schemas can initialize the committed model, complete uploaded sources can be parsed read-only into one schema per scenario, partial and unrelated schemas remain visible but cannot start an unsafe command, and future readable schemas appear automatically. Protected asynchronous backend operations recheck the live capability before spawning the maintained root command, require explicit confirmed replacement, stream a bounded timestamped log with termination and exit state, and refresh caches and the selector after success. The name is validated as an identifier at every edge, since a schema names an object and cannot be a bound parameter; 68 backend tests, 30 dashboard tests, and both production documentation and client builds pass.
- Made the `mta` schema readable rather than merely explained, with `script/derive_scenario_schemas.py`. It held three scenarios of real data and none of the dashboard's tables, and the importer could not be pointed at it: that command writes the committed sample's advertiser and Campaigns, so it would have attached the demo account's entities to another account's observations — which is what my own first draft of the settings dialog told a reader to do. The command derives the model from each scenario's own rows into its own schema, summing 365 daily windows per path into the one window the comparison requires, and reusing the published attribution code rather than restating it. The one quantity with no direct source, the touchpoint-to-entity bridge, splits a shared touchpoint's outcome by each Campaign's share of its cost; total cost reconciles to the Ads report to the cent. Counts the simulator does not establish are written as zero rather than invented, so the Budget Manager stands empty in all three scenarios and the command prints every reason why.
- Chased the same corrupting instruction through the two other places it had been written. `database_available()` told a reader who reached a research-only schema to run the importer against it, and `setups.md` and the census specification repeated it; a reader who bypassed the dialog's disabled option would have been given advice the dialog itself now refuses. Fixed a second reporting defect in the census while there: `tableCount` returned the matched subset rather than the schema's own relation count, describing `public` as holding fourteen tables when it holds fifty-three, which would lead a reader to conclude the connection was pointing somewhere else entirely.

### Next

- Decide whether the Budget Manager should be filled for the derived scenarios. It cannot be done honestly from what the simulator records: the strategy module reaches a Campaign only through its ad product and models a group of exactly four, while the simulator runs six across four, and sizing a Campaign additionally needs keyword, legal-pair, target, and audience counts it does not model at all. Either the simulator gains targeting inventory, or someone accepts fabricated counts — which would make the recommendation a statement about a Campaign Group that was never run.
- The derivation has no test file of its own; it is verified by running it against the live instance, which proves the current data rather than the contract. The window aggregation, the cost-weighted bridge split, and the blocker report are the parts worth covering.

---

## 2026-08-26

### Completed

- Built `deploy/docker/`, a two-container test stack tagging both images from `VERSION`, and made its data source detected rather than configured: a tracked `defaults.env` under the optional root `.env`, so a clean checkout serves the committed files and a configured one reaches its database with no extra step. Credentials reach the API container alone and only at run time — verified that neither image contains one and that the API has no `.env` on disk — while the client is a static bundle behind NGINX given a URL and nothing else. Removed the dashboard's Node server component in the same change, after porting the coverage that would have gone with it: `dashboard/server/` and the parity verifier are deleted along with `express`, `pg`, and `dotenv`, and the backend suite went from 15 tests to 32 including a case the Node suite never had. Fixed a pre-existing defect the browser verification surfaced, where a literal `:IMPRESSION` inside a `text()` statement read as a bind parameter and failed every database-mode snapshot before a row was read. Corrected the commit-message rule in `AGENTS.md`, which said 300 **words** where 300 characters was meant, making it no constraint at all.
- Fixed the navigation rail losing its grouping on a narrow viewport, a defect left by my own 0.9.26 bar layout: hiding the group headings was supposed to leave the grouping carried "by order alone", which meant it was not carried at all, and the six views read as one flat strip below `1024px`. Each multi-page group is now a labelled disclosure, with the state owned by `SidebarNav.vue` through `matchMedia` since CSS cannot hold it, and the breakpoint asserted against the stylesheet's so the two cannot drift. Verified at three widths in a real browser with no console error. Published the two stack images to GHCR as `mta-backend` and `mta-dashboard`, triggered by a `VERSION` change rather than by every commit — a published image is identified by the version it was built from, so rebuilding per push would leave the tag meaning "whichever build ran last". The workflow tests, builds, then proves the result by pulling both on a runner that never built them and running the stack; `deploy/docker/` gained a matching `pull` mode. Fixed `run.bat` failing on a label that was plainly there: `cmd.exe` seeks labels by byte offset, adding `pull` mode moved them, and the file was LF only because `.gitattributes` covered every text type but `.bat`.

---

## 2026-08-25

### Completed

- Audited the strategy-evaluation module against its specification and fixed the naming defect it turned up: `contrib/` folders were named after their authors, so renamed them `mlp` and `classical` after the kind of model each holds. A person's name is the wrong identifier for a path that code, tests, documentation, and the report schema all cite, because a contribution can change hands; the report field `contributor` became `contrib_folder` for the same reason, and authorship stays in the work log and Git history. All 19 contributed files stayed `R100` renames.
- Deleted an untracked, un-ignored second copy of the contribution sitting under `docs/zh/strategy-evaluation/asin-gmv-nn/`, which the next `git add -A` would have committed — compared it file by file first, every one matching. Fixed two defects the audit found: the artifact emitted a Windows-separator path, breaking its own determinism guarantee, and the contributed-model page claimed a 19-column design matrix where canonical mode builds 18, since the market indicator is sized by the marketplaces present.
- Corrected stale status claims across the documentation: the introduction called the strategy optimizer unimplemented, the progress page still listed the delivered response model and optimizer as todo, and the data-model page said no `EvaluationEpisode` consumer existed. Updated the two contributors' Scope lines, which still described the module as an empty placeholder, at the project manager's direction.

### Next

- Ask Yi Liu and Tianle Chen to record their own first dated entries; the Scope corrections were made on their behalf and their pages otherwise remain theirs.

---

## 2026-08-24

### Completed

- Built the strategy-evaluation module from its English specification: one `StrategyOutput` contract for both recommendation artifacts, conservation and observed-baseline layers, explicit unavailable ground truth, isolated `contrib/` folders holding each contribution verbatim, and a project adapter that runs the unchanged budget-to-revenue networks while retaining their negative held-out fit as a blocking caveat.
- Added the train-on-demand `evaluate_strategies.py` stage, its deterministic ignored report, Flask job and snapshot integration, dashboard and JavaScript parity updates, and the matching glossary, module inventory, backend, dashboard, command, version, and contributor-boundary documentation. Verified 590 Python tests, 61 dashboard tests, both production builds, and the end-to-end contributed-model refusal on the current insufficient panel.

### Next

- Add a dashboard report view for `strategyEvaluation`, and obtain a research snapshot whose observed Campaign identifiers overlap the deterministic seed before interpreting its baseline layer.

---

## 2026-08-20

### Completed

- Gave Budget Manager's Add/Edit modal a Form view beside the existing JSON editor: `masterObjectFields.js` declares each section's fields against the canonical vocabulary in `mta_common`, and `MasterObjectForm.vue` renders one row per field — plain input for free text, three-way select for a boolean, chip list for a multiselect, and a search-filterable `<datalist>` combobox for every enum-backed or suggested field, the one pattern a non-technical reader already knows from a country selector. Also fixed both views opening a new record on a bare `{}` by merging it over a full field template first. Separately reviewed and committed a prior working session's deploy-bundle restructuring — a single `run.sh` beside `.env` embedding `enqueue_deploy.sh` and `deploy_worker.sh` as checksummed, `bash -n`-verified payloads under one `deploy/installation/{config,app,state,systemd}` tree — where the review caught the embedded `deploy_worker.sh` still carrying the pre-fix `dashboard_healthy()` from earlier today, which would have silently redeployed the health-check bug just fixed; regenerated the payload and confirmed a byte-for-byte match. From the same session, committed the English docs homepage pipeline diagram, filled into VitePress's `#home-hero-image` slot on that page only.
- Diagnosed a production deploy where a freshly activated release and the rollback to the previously active one failed the identical health check — impossible from a per-release code difference, since the rollback restores code that was already running. Found `dashboard_healthy()` was gating activation on `GET /api/dashboard`, which returns `503` whenever the host's configured database is unreachable or empty; that setting is shared across every release on the host, so it fails every release alike. Added a `GET /api/health` liveness route independent of database state and repointed the health check at it, verified locally against a real PostgreSQL instance with 47 dashboard tests passing.
- Made the dashboard read as the production tool it is, then let it drive the pipeline it reports on. Derived the entity catalogue from the committed Ads and bridge reports rather than an optional sidecar, so the sections that stood empty in every default deployment now describe the account — and, checking the derived numbers rather than trusting them, found click-through rates of 0.98 to 1.15 coming from dividing impressions and clicks that share no denominator, so those are now reported as observed counts instead of a computed rate. Rebuilt the sub-`1024px` rail as a sticky horizontal bar, and replaced every generated/simulated/MTA-SIM phrase with reported-performance wording, with pipeline-run detail behind a diagnostics preference. Then added a stage runner that spawns the project's own documented commands with streamed output and progress matched to lines the scripts print, one tab per model across Campaign Optimizer and Optimization Log. Making the attribution stage's date range real took the most care: narrowing the Ads report alone fails validation, so both inputs are filtered, and inside a window under about three weeks a touchpoint can take delivery while its journeys convert outside — that unmatched delivery is now reconciled and named rather than raised as a data fault. Writing the per-file specifications for the five new modules then caught me claiming test coverage `master_data.js` did not have, so I wrote that test rather than softening the sentence; `useJobs.js` genuinely has none it can have without a browser, and its entry says so. Verified an unfiltered run still reproduces the committed artifacts byte-for-byte; 61 dashboard and 476 Python tests pass.

### Next

- Confirm on the target host whether the database configured in `${ETC_ROOT}/dashboard.env` is actually reachable now that activation no longer blocks on it; the earlier `503`s may point to a network or credential problem worth fixing independently.
- Build `modules/mta_strategy_evaluation/` and `script/evaluate_strategies.py`. The optimizer's third tab is declared with the reason it cannot run rather than hidden, so the gap is now visible in the product and not only in the specification.

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
