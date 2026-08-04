---
title: Workspace Source-Tree Analysis
lang: en-US
---

# Workspace Source-Tree Analysis

## Overall Structure

```text
marketing-roi-analysis/
├── README.md                         # workspace and business entry point
├── log.md                            # protected human work record
├── .gitignore                        # cache, secret, and generated-output rules
├── .markdownlint.json                # Markdown lint exceptions
├── modules/
│   ├── mta_attribution/             # five-segment attribution implementation
│   ├── mta_standard/                # MTA-SIM interface, adapter, evaluator
│   └── mta_strategy_recommendation/ # Campaign Group initial-strategy module
├── docs/                             # bilingual knowledge and external research
├── design-artifacts/                 # historical product vision
├── _bmad-output/                     # completed specifications and deferred work
├── .agents/
│   └── skills/                       # installed skills
└── _bmad/                            # installation metadata, configuration, shared tools
```

`.git/` is inspected only for repository health; its object database is not evaluated file by file as project content.

## Current Business Area

```text
modules/mta_attribution/
├── config.py                         # windows, thresholds, field constants
├── run_pipeline.py                   # complete pipeline entry point
├── src/
│   ├── touchpoint_key.py                # five-segment parsing and validation
│   ├── synthetic_event_pipeline.py      # synthetic users and AMC/Ads/entity derivation
│   ├── path_report_builder.py           # conceptual events to anonymous paths
│   ├── attribution_contract.py          # CSV IO, row validation, result shaping
│   ├── markov_attribution_model.py      # removal-effect model
│   ├── shapley_attribution_model.py     # path-level Shapley model
│   └── attribution_model_comparison.py  # gaps, support, reliability, recommendations
├── scripts/                             # step-specific command-line interfaces
├── tests/                               # automated tests
├── data/simulated/                      # one source and four derived datasets
└── outputs/attribution/                 # five canonical generated outputs
```

One file per model is deliberate. `attribution_contract.py` owns everything both
models share — the CSV boundary, row validation, and result shaping — so each
model file contains only its own mathematics and can be read, reviewed, or
replaced on its own.

Dependency direction is:

```text
config + touchpoint_key + simulated_touchpoints
          ↓
synthetic_event_pipeline (simulation only)
          ├─ Ads / touchpoint-entity aggregates
          └─ anonymous conceptual events
                    ↓
            path_report_builder
                    ↓
           attribution_contract
            ↓                ↓
markov_attribution   shapley_attribution
     _model               _model
            ↓                ↓
        attribution_model_comparison
                    ↓
       run_pipeline / scripts / outputs
```

The Strategy Initializer is:

```text
modules/mta_strategy_recommendation/
├── data/simulated/                   # strategy request and candidate pool
├── outputs/initial_budget_recommendation.json
├── src/
│   ├── budget_recommender.py         # counts, MTA bridge, budget generation
│   └── hierarchy_validator.py        # AMC lineage and result regeneration
├── scripts/
│   ├── generate_initial_budget.py
│   └── validate_simulated_hierarchy.py
└── tests/                            # contract, compatibility, boundary tests
```

## Knowledge and Traceability Area

```text
docs/
├── index.md                          # redirect to the active English site
├── en/                               # complete active English documentation
├── zh/                               # complete preserved Chinese source documentation
├── assets/                           # shared diagrams and images
├── research/                         # external PDF/DOCX/JSON/TXT originals only
├── workspace-file-inventory.json     # machine-generated inventory
└── project-scan-report.json          # scan state

design-artifacts/
└── amc_mta/A-Product-Brief/          # early vision, PRD, explanations, decisions

_bmad-output/
└── implementation-artifacts/         # completed remediation and deferred work
```

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
