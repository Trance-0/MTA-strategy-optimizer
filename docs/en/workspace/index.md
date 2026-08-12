---
title: Complete Workspace Documentation Index
lang: en-US
---

# Complete Workspace Documentation Index

This index covers the complete workspace: current business implementations, project knowledge, research originals, historical artifacts, and the local Agent/BMad toolchain. The current business chain consists of [`modules/mta_attribution`](../attribution/amc-mta-module.md) and [`modules/mta_strategy_recommendation`](../strategy/module-overview.md). `.agents` and `_bmad` are development tools, not marketing-product features.

## Recommended Reading Order

1. [Workspace overview and current assessment](project-overview.md): overall conclusions, health, and risks.
2. [Source-tree analysis](source-tree-analysis.md): all top-level directories and boundaries.
3. [Workspace file-location management](file-management.md): adding, moving, and archiving files.
4. [Workspace architecture](architecture.md): the business, knowledge, and tool layers.
5. [Component and asset inventory](component-inventory.md): code, data, research, and skill assets.
6. [Development and verification guide](development-guide.md): run the project and reproduce verification.
7. [Implementation specification catalog](../introduction/specifications.md): categorized implementation intent and historical verification records.
8. [Development history](development-history.md): English translation of the complete preserved work log.
9. [AMC MTA capability assessment](../product/amc-mta/capability-assessment.md): detailed assessment of attribution capabilities.

## Current Entry Points and Authority

| Topic | Recommended entry point |
| --- | --- |
| Complete workspace status | [Workspace overview and current assessment](project-overview.md) |
| Full file-by-file inventory | [Workspace file inventory](../../workspace-file-inventory.json) |
| Top-level architecture and partitions | [Workspace architecture](architecture.md) |
| Current architecture diagrams and editable sources | [Workspace architecture](architecture.md) |
| File locations and movement rules | [Workspace file-location management](file-management.md) |
| Runnable modules and commands | [AMC MTA module](../attribution/amc-mta-module.md) |
| Campaign Group initial strategy | [Strategy Initializer](../strategy/module-overview.md) |
| Initial-strategy plan and contract | [Overall model plan](../strategy/model-plan.md) |
| Current budget calculation | [Step-by-step Ad Group initial-budget calculation](../strategy/current-budget-calculation.md) |
| Future budget optimization research | [Problem definition and research plan](../strategy/optimization-plan.md) |
| Input fields, paths, and cost rules | [AMC MTA data contract](../datasets/amc-data-contract.md) |
| Markov/Shapley gaps and decision status | [Model-comparison governance](../attribution/model-governance.md) |
| Individual-touchpoint reliability | [Touchpoint reliability guide](../attribution/reliability.md) |
| Code structure and data flow | [AMC MTA architecture](../product/amc-mta/architecture.md) |
| Project maturity and priorities | [AMC MTA capability assessment](../product/amc-mta/capability-assessment.md) |
| Implementation specifications | [Project-level specification catalog](../introduction/specifications.md) |
| Historical work log | [Development history](development-history.md) |
| Campaign Group data hierarchy | [Campaign Group hierarchy and finest performance grain](../research/campaign-data-hierarchy.md) |
| Deferred AMC MTA technical work | `_bmad-output/implementation-artifacts/amc_mta/deferred/deferred-work.md` |

Authority order is: runtime code and tests, module data/governance contracts, reproducible artifacts, current architecture and capability assessments, project introductions, research notes, then historical product documents. Architecture and assessment pages are current explanations derived from code and artifacts; they do not replace source contracts.

## Workspace Partitions

| Workspace path | Responsibility |
| --- | --- |
| `.agents/` | Installed skills |
| `_bmad/` | Historical/optional BMad configuration, manifests, and shared tools |
| `_bmad-output/` | Completed specifications and deferred work |
| `design-artifacts/` | Historical product vision |
| `docs/` | English documentation, preserved Chinese sources, and research originals; Draw.io sources and renders are co-located with the pages that use them |
| `external/` | Pinned external repositories |
| `script/` | Maintained project command-line entry points |
| `modules/` | Attribution, standard adapter, and strategy modules |

`modules/mta_attribution/` contains `src/` for path and attribution logic, `tests/` for automated checks, `data/` for the simulated source and derived datasets, and `outputs/` for canonical generated CSVs. `modules/mta_strategy_recommendation/` uses the same standard layout for its inputs, count/budget implementation, tests, and canonical initial-budget JSON.

Within `docs/`, `index.md` redirects to the active English site, `en/` contains complete published English documentation, `zh/` preserves unpublished Chinese sources, the two language trees retain their respective specification catalogs, and `research/` holds external binary originals that are not runtime inputs.

See [Source-tree analysis](source-tree-analysis.md) for the annotated structure.

## Content Status

- **Current:** this index, architecture, capability assessment, [product-document status](../product/), AMC MTA introduction, and module documentation.
- **Research support:** MTA and Amazon research material.
- **Future validation:** A/B-testing research.
- **Background:** ontology and industry material.
- **Historical vision:** `design-artifacts/`, including the model-function and relationship guide.
- **Historical implementation record:** `_bmad-output/implementation-artifacts/`; frozen specifications record their original context and do not automatically describe current capability.
- **Installed tools:** `.agents` and `_bmad`; their self-contained distribution structure is not deduplicated as business documentation.

## Current Verification: 2026-08-07

The migrated repository was verified with its locked Python 3.12 environment after the upstream documentation reconciliation:

- 107 attribution tests, 138 standardized-interface tests, and 34 strategy tests passed;
- the complete attribution pipeline reproduced all five governed outputs;
- 17 Amazon Marketing Cloud and Amazon Ads touchpoints aligned across the 90-day window, account, marketplace, and currency;
- the strategy initializer reproduced the canonical `1/1/1/1` Ad Group count and budget seed;
- the English VitePress site built successfully while all preserved Chinese routes remained unpublished placeholders.

These checks establish repository reproducibility only. They do not establish causal validity or production readiness.

## Current Verification Baseline

The historical baseline recorded on 2026-07-30 used the unified synthetic user-event source, its four derived datasets, and deterministic output now reproduced through `uv run python -X utf8 -B script/run_pipeline.py`:

- 107 AMC MTA tests passed, with 34 additional Strategy Initializer tests;
- 17 five-segment touchpoints aligned completely with the Amazon Ads report;
- the reporting window covered every day from 2026-01-01 through 2026-03-31;
- the source held 11,147 events, 2,400 synthetic users, and 3,547 journeys;
- AMC Outcomes totaled 920 converted users, 1,023 purchases, and 87,802.83 revenue;
- all five attribution artifacts were deterministically reproducible;
- the three dual-model artifacts contained `51 RELIABLE / 0 UNRELIABLE` decisions;
- all 51 recommendation rows were `RELIABLE` and retained only official/reference shares, gaps, and reliability fields.

These figures demonstrate internal consistency of that sample pipeline. They do not demonstrate real-campaign validity, causal incrementality, or current test counts after later changes.

The same audit recorded 119 registered and installed skills, syntax success for 108 Python and seven JavaScript files, and no broken local links in project-authored Markdown. See [Workspace overview](project-overview.md) for the tool-layer limitations recorded by that audit.
