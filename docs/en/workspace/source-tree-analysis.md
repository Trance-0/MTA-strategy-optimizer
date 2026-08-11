---
title: Workspace Source-Tree Analysis
lang: en-US
---

# Workspace Source-Tree Analysis

## Overall Structure

| Path | Responsibility |
| --- | --- |
| `README.md` | Workspace and business entry point |
| `log.md` | Protected human work record |
| `.gitignore`, `.markdownlint.json` | Ignore and Markdown-lint rules |
| `modules/mta_attribution/` | Model interface and concrete attribution implementations |
| `modules/mta_standard/` | MTA-SIM framework, adapter, execution, and evaluation |
| `modules/mta_strategy_recommendation/` | Campaign Group initial-strategy module |
| `external/mta_sim_dataset/` | Pinned ZheyuanWu data-generator submodule |
| `script/` | All maintained project commands |
| `docs/` | Published English knowledge, preserved Chinese sources, and external research |
| `design-artifacts/`, `_bmad-output/` | Historical product vision, completed specifications, and deferred work |
| `.agents/skills/`, `_bmad/` | Installed or historical/optional development tooling |

`.git/` is inspected only for repository health; its object database is not evaluated file by file as project content.

## Current Business Area

The `mta_attribution` module contains `config.py` for windows, thresholds, and field constants; `src/` for touchpoint validation, simulation, path construction, shared contracts, concrete models, and comparison; `tests/` for automation; `data/simulated/` for the source and derived datasets; and `outputs/attribution/` for the five canonical outputs.

One file per model is deliberate. `attribution_contract.py` owns everything both
models share — the CSV boundary, row validation, and result shaping — so each
model file contains only its own mathematics and can be read, reviewed, or
replaced on its own.

Dependency direction is:

The dependency direction starts with configuration, touchpoint validation, and simulated touchpoints. The simulation-only event pipeline derives Ads/entity aggregates and anonymous conceptual events. `path_report_builder` converts those events into paths, `attribution_contract` provides the shared validated representation, Markov and Shapley run independently, and `attribution_model_comparison` combines only their outputs before project-level scripts publish the artifacts.

The Strategy Initializer is:

The Strategy Initializer contains `data/simulated/` for its request and candidate pool, `src/budget_recommender.py` for counts, the MTA bridge, and budget generation, `src/hierarchy_validator.py` for AMC lineage and deterministic regeneration, `tests/` for contract and boundary checks, and `outputs/initial_budget_recommendation.json` as its canonical result.

The corresponding command entry points are `script/run_pipeline.py`,
`script/generate_initial_budget.py`, and
`script/validate_simulated_hierarchy.py`. Reusable code remains in each
module's `src/` directory; source modules do not import command wrappers.

Strategy descriptions were migrated out of the runtime module and into the project-level `docs/en/strategy/` section. `model-plan.md`, `output-data-contract.md`, `strategy-output-contract.md`, and `current-budget-calculation.md` describe the implemented initializer. `optimization-plan.md` records the future optimization problem and research plan without presenting it as current capability. Preserved Chinese counterparts remain under `docs/zh/strategy/` for future publication.

## Knowledge and Traceability Area

The knowledge area consists of `docs/index.md` for the active-language redirect, `docs/en/` for published English pages, `docs/zh/` for preserved Chinese sources, and `docs/research/` for external PDF/DOCX/JSON/TXT originals. Editable Draw.io files and their light/dark SVG renders live beside the English pages that embed them. `workspace-file-inventory.json` and `project-scan-report.json` hold machine-generated inventory state. Historical vision remains under `design-artifacts/amc_mta/A-Product-Brief/`, while completed remediation records and deferred work remain under `_bmad-output/implementation-artifacts/`.

## Installed Tool Area

`.agents/skills/` is the flat Codex skill installation. The source audit recorded 119 first-level skill directories containing `SKILL.md`, plus one nested setup-skill template. Identical knowledge files are part of a self-contained skill-distribution design and are not ordinary duplicates.

`_bmad/` was recorded as containing installation versions and sources, a 2,075-entry installed-file manifest, a 119-entry skill manifest, module help tables, project/personal configuration, shared WDS data and seven JavaScript scripts, plus configuration parsing and tests. Runtime skill files live under `.agents/skills/`; source paths in `_bmad/_config/skill-manifest.csv` do not imply that a second skill copy must exist inside the workspace.

## File-Organization Assessment

- The source audit found no empty file, symbolic link, submodule, cache file, or misplaced business asset.
- Generated output retained only the five canonical AMC CSV files and one canonical Strategy Initializer JSON; other `modules/*/outputs/` content was ignored.
- The personal `_bmad/custom/config.user.toml` override was correctly ignored.
- Research binaries were concentrated under `docs/research/` and did not enter runtime directories.
- Historical files were preserved but isolated from current capability by indexes and status explanations.

New and moved files must follow [workspace file-location management](file-management.md). Multi-file bilingual documentation sections use `index.md` under their language tree. External binary research assets retain their publication names under `docs/research/`. Historical model-function descriptions remain under `design-artifacts/amc_mta/A-Product-Brief/` rather than current product documentation.
