---
title: Version Log
description: Release history and material changes for the maintained project
compact: "Index of all version pages with dates and one-line summaries. Read to locate when a change landed or to add a new version page; not a specification of current behavior."
order: 1
---

# Version Log

The project version is recorded in the repository-root `VERSION` file. Each page here is one small patch description covering a coherent change set, rather than a reproduction of every commit message. Every patch keeps its own permanent page; older minor versions are grouped into a collapsed folder per minor version instead of being compacted away.

This section records **what** changed. See the [work log](../worklog/) for **who** did the work and when.

| Version | Date | Summary |
| --- | --- | --- |
| [0.9.14](0.9.14.md) | 2026-08-17 | Fixed nested sidebar folder titles, reversed version-log compaction into per-minor-version folders, and fixed the sidebar's alphabetical version sort |
| [0.9.13](0.9.13.md) | 2026-08-17 | Moved Environment under Introduction and renamed Strategy Recommendation, fixed the resulting sidebar and cross-link breakage, and hardened the docs launcher against silent failures |
| [0.9.12](0.9.12.md) | 2026-08-17 | Split the monolithic dashboard documentation page into `index.md`, `views.md`, `navigation.md`, `deployment.md`, and `database-import.md` |
| [0.9.11](0.9.11.md) | 2026-08-15 | Vue client over a Node API replacing the Streamlit and stlite dashboard, three dual-source parity defects and five cold-start launcher defects fixed, and the parity command and test suite the repository was missing |
| [0.9](0.9/) | 2026-08-12 to 2026-08-14 | GitHub Pages activation, then patches 0.9.1–0.9.10: base-aware deployment paths, an exact Gitee mirror, version and work-log separation, the local Streamlit dashboard and its PostgreSQL mirror, GitHub Pages publication, self-hosted Gitea mirroring, and the boot-splash and Gitea work-log fixes |
| [0.8](0.8/) | 2026-08-12 | Published the repository publicly with GitHub-to-Gitee mirroring and GitHub Pages documentation |
| [0.7](0.7/) | 2026-08-11 | Separated concrete attribution models from the standardized MTA framework |
| [0.6](0.6/) | 2026-08-07 | Integrated the pinned MTA-SIM dataset generator and the four-to-five touchpoint-segment adapter |
| [0.5](0.5/) | 2026-08-03 | Expanded the demonstration dataset and consolidated the runnable campaign strategy initializer |
| [0.4](0.4/) | 2026-07-30 | Unified synthetic event generation and added Multi-Touch Attribution-driven Ad Group budgets |
| [0.3](0.3/) | 2026-07-28 | Added the initial Multi-Touch Attribution-informed campaign strategy initializer |
| [0.2](0.2/) | 2026-07-22 | Reduced the governed attribution output set and added reliability-aware recommended values |
| [0.1](0.1/) | 2026-07-16 | Established Amazon Marketing Cloud Multi-Touch Attribution as the active implementation focus |

These versions were reconstructed from first-parent Git history and the preserved project work log. They are documentation milestones, not retroactively created Git tags.

## Planned

Not yet started; recorded here so the next session can pick this up.

- Consolidate a minimal, class-based set of data structures shared across `modules/mta_attribution`, `modules/mta_standard`, `modules/mta_strategy_recommendation`, `modules/mta_strategy_evaluation`, and the dashboard's database schema.
- Move `dashboard/config.py` and `dashboard/models.py` into `modules/mta_standard`, and move `docs/en/dashboard/database-import.md` into `docs/en/attribution/standardized-interface/` to match.
- Implement a full runnable optimizer module built on the consolidated data structures.

See the matching goal in the work log at [`docs/worklog/ZheyuanWu.md`](../worklog/ZheyuanWu.md).
