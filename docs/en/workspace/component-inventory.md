---
title: Workspace Component and Asset Inventory
lang: en-US
---

# Workspace Component and Asset Inventory

## Business Components

| Component | Entry point | Responsibility |
| --- | --- | --- |
| Five-segment touchpoint key | `modules/amc_mta/src/touchpoint_key.py` | Normalize ad product, format, placement, creative, and interaction type |
| Synthetic event-data factory | `modules/amc_mta/src/synthetic_event_pipeline.py` | User-event fact source, three aggregate derivations, privacy, and conservation checks |
| Path construction | `modules/amc_mta/src/amc_path_builder.py` | Convert events to AMC-style anonymous aggregate paths |
| Attribution engine | `modules/amc_mta/src/amc_mta_attribution.py` | Markov, Shapley, cost, and efficiency metrics |
| Model governance | `modules/amc_mta/src/model_comparison.py` | Five-segment support, gaps, three reliability criteria, overall diagnostics, and recommendation status |
| Complete AMC entry point | `modules/amc_mta/run_pipeline.py` | Rebuild derived inputs and the five model/governance outputs |
| AMC command-line scripts | `modules/amc_mta/scripts/` | Stepwise generation, attribution, comparison, and validation |
| AMC tests | `modules/amc_mta/tests/` | Unit, contract, and end-to-end verification |
| Ad Group count and budget generator | `modules/mta_strategy_recommender/src/budget_recommender.py` | Calculate capacity counts, derive Campaign shares from MTA plus the AMC bridge, and divide them among anonymous new groups |
| Campaign Group budget validator | `modules/mta_strategy_recommender/src/hierarchy_validator.py` | Read-only AMC hash/scope validation, capacity regeneration, bridge checks, budget conservation, and budget-only schema validation |
| Initial-budget inputs | `modules/mta_strategy_recommender/data/simulated/` | Two JSON files defining the Group, four Campaigns, AMC lineage, candidate counts, capacities, and minimum budgets |
| Canonical initial-budget output | `modules/mta_strategy_recommender/outputs/initial_budget_recommendation.json` | Reproducible `INITIAL_SEED` result and the test baseline |

## Data Assets

| Type | Recorded count | Location |
| --- | ---: | --- |
| Synthetic fact source and derived CSV files | 5 | `modules/amc_mta/data/simulated/` |
| Canonical attribution CSV files | 5 | `modules/amc_mta/outputs/attribution/` |
| Strategy initialization input JSON files | 2 | `modules/mta_strategy_recommender/data/simulated/` |
| Canonical Strategy Initializer output | 1 | `modules/mta_strategy_recommender/outputs/` |
| External PDFs | 7 | `docs/research/` |
| External DOCX files | 2 | `docs/research/amazon/research/` |
| Amazon Ads OpenAPI JSON | 1 | `docs/research/amazon/research/` |
| Research explanations and notes | multiple | bilingual pages under `docs/en/research/` and `docs/zh/research/` |

## Documentation Assets

- Active project entry and assessment: `docs/en/workspace/`.
- File-location and movement rules: `docs/en/workspace/file-management.md` and its Chinese source counterpart.
- Published business architecture and contracts: the English Attribution, Datasets, Environment, Strategy, Product, and Workspace sections; Chinese sources are preserved under `docs/zh/` but not published.
- Historical AMC MTA product vision: `design-artifacts/amc_mta/A-Product-Brief/`.
- Completed implementation specifications: `_bmad-output/implementation-artifacts/amc_mta/`.
- Full machine inventory: `docs/workspace-file-inventory.json`.
- Research classification and source indexes: bilingual Research sections; binary originals remain under `docs/research/`.

## Agent/BMad Components

| Module | Recorded version/channel | Main role |
| --- | --- | --- |
| Core | 6.8.0 | general review, indexing, specifications, collaboration |
| BMM | 6.8.0 | product, architecture, development, documentation workflows |
| TEA | v1.19.0 | test architecture and quality governance |
| BMB | v2.0.0 | Agent, workflow, and module building |
| Automator | main/next | Story automation |
| CIS | v0.2.1 | creativity and problem solving |
| GDS | v0.6.0 | game-development workflows |
| WDS | v0.4.3 | web and user-experience design workflows |

The recorded audit found 119 manifest entries and 119 first-level skill directories with matching names. One nested setup-skill template produced 120 total `SKILL.md` files.

## Code and Executables

The recorded workspace audit found:

- 108 Python files, all passing syntax parsing;
- seven JavaScript files, all passing Node.js syntax checks;
- one Bash Story Automator entry point passing `bash -n`;
- 15 Git executables, all inside installed tool-script areas;
- no third-party Python dependency in AMC MTA business code.

These are time-stamped audit facts, not timeless repository counts.

## Duplicate-File Explanation

The recorded audit found 127 identical SHA-256 groups involving 621 files. Most were under the self-contained `resources/knowledge/` directories of `bmad-tea` and `bmad-testarch-*` skills. Because each skill copies the knowledge it needs for independent loading and distribution, these files are:

- not deleted;
- not replaced with symbolic links;
- not moved into business documentation;
- updated only through a coordinated BMad module upgrade or repackaging.
