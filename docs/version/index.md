---
title: Version Log
description: Release history and material changes for the maintained project
compact: "Routes release history from `VERSION` to one page per patch, keeping the latest four patches flat and older patches in minor-version folders; includes dates, summaries, historical group links, and planned follow-ups."
order: 1
---

# Version Log

The project version is recorded in the repository-root `VERSION` file. Each page here is one small patch description covering a coherent change set, rather than a reproduction of every commit message. Every patch keeps its own permanent page; older minor versions are grouped into a collapsed folder per minor version instead of being compacted away.

This section records **what** changed. See the [work log](../worklog/) for **who** did the work and when.

## [0.9.33](0.9.33.md)

- Date: 2026-08-27
- Summary: Added a deployment-identity block to Settings that compares the dashboard and backend project versions and full Git commit identifiers, reports detected Python and Flask versions, and makes incomplete or mismatched independently deployed artifacts visible

## [0.9.32](0.9.32.md)

- Date: 2026-08-27
- Summary: Added discovery-driven dashboard controls and protected backend operations to initialize empty or new PostgreSQL schemas and parse complete source schemas into one dashboard schema per scenario, with explicit replacement confirmation, bounded timestamped polling logs, termination, and automatic cache and census refresh

## [0.9.31](0.9.31.md)

- Date: 2026-08-27
- Summary: Selected which schema of the PostgreSQL instance the dashboard reads and `import_to_database.py` writes, through a `PG_SCHEMA` dropdown backed by a privilege-filtered census that lists the schemas which cannot serve the dashboard as disabled options carrying what they lack and the command that would populate them, and added `derive_scenario_schemas.py`, which computes the dashboard model from a simulator-populated schema into one self-contained schema per scenario

## [0.9.30](0.9.30.md)

- Date: 2026-08-26
- Summary: Fixed the navigation rail flattening its three sections into one undifferentiated row below the wide breakpoint, and published `mta-backend` and `mta-dashboard` to the GitHub Container Registry from a workflow triggered by a `VERSION` change rather than by every commit, with a `pull` mode on the Docker stack that runs those images

## [0.9.29](0.9/0.9.29.md)

- Date: 2026-08-26
- Summary: Added a two-container Docker test stack tagged from `VERSION` that detects the data source automatically and gives credentials to the API alone, removed the dashboard's Node server component after porting its coverage to the backend suite, and fixed a bind-parameter defect that made every database-mode snapshot fail

## [0.9.28](0.9/0.9.28.md)

- Date: 2026-08-25
- Summary: Built runnable strategy evaluation contracts and layers, preserved the contributed budget-to-revenue networks verbatim under model-named `contrib/` folders with an adapter, added the train-on-demand evaluation stage and snapshot, and completed the Flask/AppStack runtime migration

## [0.9.27](0.9/0.9.27.md)

- Date: 2026-08-20
- Summary: Ran pipeline stages from the dashboard with streamed logs and phase-matched progress, split the optimizer and its logs into one tab per model, gave `run_pipeline.py` a working report date range that filters and reconciles both inputs, and converted Campaigns to the paged entity table

## [0.9.26](0.9/0.9.26.md)

- Date: 2026-08-20
- Summary: Derived the entity catalogue from the committed reports so every deployment populates it, rebuilt the narrow-viewport rail as a horizontal bar, and revised the dashboard to describe reported market performance rather than generated data

## [0.9.25](0.9/0.9.25.md)

- Date: 2026-08-20
- Summary: Added a pipeline architecture diagram to the English documentation homepage hero, replacing VitePress's default circular logo slot on that page only

## [0.9.24](0.9/0.9.24.md)

- Date: 2026-08-20
- Summary: Restructured the Linux deploy bundle so a single `run.sh` uploaded beside `.env` embeds and checksum-verifies its runtime helpers and consolidates install paths under `deploy/installation/`, and fixed a stale embedded worker payload that would have reintroduced the 0.9.23 health-check bug

## [0.9.23](0.9/0.9.23.md)

- Date: 2026-08-20
- Summary: Added Budget Manager's Form/JSON dual-mode master-object editor with template pre-fill, and decoupled the deploy worker's activation health check from database readiness by adding `GET /api/health`

## [0.9.22](0.9/0.9.22.md)

- Date: 2026-08-19
- Summary: Derived write capability from the snapshot's data source rather than the build flag, themed the read-only and database-connected deployments apart, and replaced Budget Manager's detail lists with paged, selectable entity tables carrying row edit and confirmed deletion

## [0.9.21](0.9/0.9.21.md)

- Date: 2026-08-19
- Summary: Specified the implemented Campaign budget response model and constrained optimizer, corrected the pages that still called them unimplemented, and surfaced the optimized plan in the dashboard's Optimization Log

## [0.9.20](0.9/0.9.20.md)

- Date: 2026-08-18
- Summary: Integrated independent Multi-Touch Attribution Simulator (MTA-SIM) domain records through `mta_common`, adopted native five-segment interactions, added 10k CSV and 100k PostgreSQL research modes, and expanded the dashboard's canonical master-data and historical-analysis views

## [0.9.19](0.9/0.9.19.md)

- Date: 2026-08-18
- Summary: Grouped the canonical data-model class reference into eight ordered subsections and added a vertical topological Draw.io dependency map with arrows reserved for foreign-key-style identifiers

## [0.9.18](0.9/0.9.18.md)

- Date: 2026-08-18
- Summary: Added a project-wide documentation table-usage rule to `AGENTS.md` and decomposed 135 non-comparison tables into sub-level headings across 45 files under `docs/en`, `docs/version`, and `docs/worklog`

## [0.9.17](0.9/0.9.17.md)

- Date: 2026-08-18
- Summary: Added the `modules/mta_common` canonical data-model foundation and its legacy compatibility bridge, with full documentation

## [0.9.16](0.9/0.9.16.md)

- Date: 2026-08-18
- Summary: Recorded the UI_design reference prototype's move from `external/` to `design-artifacts/`

## [0.9.15](0.9/0.9.15.md)

- Date: 2026-08-18
- Summary: Restructured the nav bar, renamed Datasets to Market Simulation, fixed version-folder default collapse, and loosened the work-log confirmation rule

## [0.9.14](0.9/0.9.14.md)

- Date: 2026-08-17
- Summary: Fixed nested sidebar folder titles, reversed version-log compaction into per-minor-version folders, and fixed the sidebar's alphabetical version sort

## [0.9.13](0.9/0.9.13.md)

- Date: 2026-08-17
- Summary: Moved Environment under Introduction and renamed Strategy Recommendation, fixed the resulting sidebar and cross-link breakage, and hardened the docs launcher against silent failures

## [0.9.12](0.9/0.9.12.md)

- Date: 2026-08-17
- Summary: Split the monolithic dashboard documentation page into `index.md`, `views.md`, `navigation.md`, `deployment.md`, and `database-import.md`

## [0.9.11](0.9/0.9.11.md)

- Date: 2026-08-15
- Summary: Vue client over a Node API replacing the Streamlit and stlite dashboard, three dual-source parity defects and five cold-start launcher defects fixed, and the parity command and test suite the repository was missing

## [0.9](0.9/)

- Date: 2026-08-12 to 2026-08-14
- Summary: GitHub Pages activation, then patches 0.9.1–0.9.10: base-aware deployment paths, an exact Gitee mirror, version and work-log separation, the local Streamlit dashboard and its PostgreSQL mirror, GitHub Pages publication, self-hosted Gitea mirroring, and the boot-splash and Gitea work-log fixes

## [0.8](0.8/)

- Date: 2026-08-12
- Summary: Published the repository publicly with GitHub-to-Gitee mirroring and GitHub Pages documentation

## [0.7](0.7/)

- Date: 2026-08-11
- Summary: Separated concrete attribution models from the standardized MTA framework

## [0.6](0.6/)

- Date: 2026-08-07
- Summary: Integrated the pinned MTA-SIM dataset generator and the four-to-five touchpoint-segment adapter

## [0.5](0.5/)

- Date: 2026-08-03
- Summary: Expanded the demonstration dataset and consolidated the runnable campaign strategy initializer

## [0.4](0.4/)

- Date: 2026-07-30
- Summary: Unified synthetic event generation and added Multi-Touch Attribution-driven Ad Group budgets

## [0.3](0.3/)

- Date: 2026-07-28
- Summary: Added the initial Multi-Touch Attribution-informed campaign strategy initializer

## [0.2](0.2/)

- Date: 2026-07-22
- Summary: Reduced the governed attribution output set and added reliability-aware recommended values

## [0.1](0.1/)

- Date: 2026-07-16
- Summary: Established Amazon Marketing Cloud Multi-Touch Attribution as the active implementation focus

These versions were reconstructed from first-parent Git history and the preserved project work log. They are documentation milestones, not retroactively created Git tags.

## Planned

Not yet started; recorded here so the next session can pick this up.

- Done in 0.9.20: native five-segment MTA-SIM loading, canonical runtime adaptation in `modules/mta_standard`, canonical touchpoint reuse in attribution and strategy boundaries, research-scale PostgreSQL persistence, and dashboard canonical-data/history views. Still not started: `modules/mta_strategy_evaluation` and a final response-based optimizer.
- Move `dashboard/config.py` and `dashboard/models.py` into `modules/mta_standard`, and move `docs/en/dashboard/database-import.md` into `docs/en/attribution/standardized-interface/` to match.
- Implement a full runnable optimizer module built on the consolidated data structures — would read `StrategyObjective`, `BudgetUsagePolicy`, and `CampaignEpisode` from `modules/mta_common`, none of which is consumed by an optimizer yet.

See the matching goal in the work log at [`docs/worklog/ZheyuanWu.md`](../worklog/ZheyuanWu.md).
