---
title: Version Log
description: Release history and material changes for the maintained project
compact: "Index of all version pages with dates and one-line summaries. Read to locate when a change landed or to add a new version page; not a specification of current behavior."
order: 1
---

# Version Log

The project version is recorded in the repository-root `VERSION` file. Each page here is one small patch description covering a coherent change set, rather than a reproduction of every commit message. Every patch keeps its own permanent page; older minor versions are grouped into a collapsed folder per minor version instead of being compacted away.

This section records **what** changed. See the [work log](../worklog/) for **who** did the work and when.

## [0.9.19](0.9.19.md)

- Date: 2026-08-18
- Summary: Grouped the canonical data-model class reference into eight ordered subsections and added a vertical topological Draw.io dependency map with arrows reserved for foreign-key-style identifiers

## [0.9.18](0.9.18.md)

- Date: 2026-08-18
- Summary: Added a project-wide documentation table-usage rule to `AGENTS.md` and decomposed 135 non-comparison tables into sub-level headings across 45 files under `docs/en`, `docs/version`, and `docs/worklog`

## [0.9.17](0.9.17.md)

- Date: 2026-08-18
- Summary: Added the `modules/mta_common` canonical data-model foundation and its legacy compatibility bridge, with full documentation

## [0.9.16](0.9.16.md)

- Date: 2026-08-18
- Summary: Recorded the UI_design reference prototype's move from `external/` to `design-artifacts/`

## [0.9.15](0.9.15.md)

- Date: 2026-08-18
- Summary: Restructured the nav bar, renamed Datasets to Market Simulation, fixed version-folder default collapse, and loosened the work-log confirmation rule

## [0.9.14](0.9.14.md)

- Date: 2026-08-17
- Summary: Fixed nested sidebar folder titles, reversed version-log compaction into per-minor-version folders, and fixed the sidebar's alphabetical version sort

## [0.9.13](0.9.13.md)

- Date: 2026-08-17
- Summary: Moved Environment under Introduction and renamed Strategy Recommendation, fixed the resulting sidebar and cross-link breakage, and hardened the docs launcher against silent failures

## [0.9.12](0.9.12.md)

- Date: 2026-08-17
- Summary: Split the monolithic dashboard documentation page into `index.md`, `views.md`, `navigation.md`, `deployment.md`, and `database-import.md`

## [0.9.11](0.9.11.md)

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

- Done in 0.9.17: the canonical, provider-independent data-model foundation itself — `modules/mta_common/` — with a legacy-to-canonical compatibility bridge. See [Canonical Data Model](../en/introduction/data-models/index.md). Still not started: wiring `modules/mta_attribution`, `modules/mta_standard`, `modules/mta_strategy_recommendation`, `modules/mta_strategy_evaluation`, and the dashboard's database schema to actually consume it instead of their current native shapes — nothing outside `modules/mta_common`'s own test suite calls it yet.
- Move `dashboard/config.py` and `dashboard/models.py` into `modules/mta_standard`, and move `docs/en/dashboard/database-import.md` into `docs/en/attribution/standardized-interface/` to match.
- Implement a full runnable optimizer module built on the consolidated data structures — would read `StrategyObjective`, `BudgetUsagePolicy`, and `CampaignEpisode` from `modules/mta_common`, none of which is consumed by an optimizer yet.

See the matching goal in the work log at [`docs/worklog/ZheyuanWu.md`](../worklog/ZheyuanWu.md).
