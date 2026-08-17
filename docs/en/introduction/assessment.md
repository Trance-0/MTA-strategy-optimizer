---
title: Workspace Overview and Current Assessment
compact: "Dated audit of workspace health, scale, and per-partition assessment with recorded test and verification counts. Historical evidence of a point-in-time state; do not treat its counts as current."
lang: en-US
---

# Workspace Overview and Current Assessment

This repository is a compound workspace containing business modules, a local Agent/BMad toolchain, project knowledge, and historical records. AMC MTA is a runnable attribution implementation. The MTA Strategy Initializer generates new Ad Group counts and budgets at Campaign Group level, produces a canonical result, and validates its cross-module lineage. More detailed activation strategy and later optimization are outside the initializer's scope.

## Conclusion

The source audit characterized the workspace as **clearly structured, reproducible, and suitable for continued development, while the business models remain validation-oriented demonstrations**.

- The synthetic AMC fact source, four derived datasets, five canonical outputs, documentation, and 107 recorded tests were consistent and deterministically reproducible.
- Current facts, historical vision, external research, and implementation records were partitioned so unimplemented features were no longer presented as current capability.
- `.agents` and `_bmad` were installed development tools, not marketing-product source; 119 declared skills matched 119 direct skill directories.
- The scan found no empty files, symbolic links, cached bytecode, macOS `.DS_Store`, new temporary files, or misplaced business files.
- It recorded 44 current/research/module Markdown documents with 217 valid local links, plus syntax success for 108 Python and seven JavaScript files.
- One upstream tool assertion mismatch was confirmed, and another tool test required unavailable `pytest`; neither affected AMC MTA execution.

These figures describe the dated source audit and must not replace current verification results.

## Workspace Scale

File and byte counts change as tool packages and implementation records evolve; use the machine inventory for exact values. That inventory excludes Git internals, itself, ignored personal configuration, and protected files.

| Partition | File count | Size | Role |
| --- | ---: | ---: | --- |
| `.agents` | machine inventory | machine inventory | installed Agent/workflow skills |
| `_bmad` | machine inventory | machine inventory | BMad installation configuration, manifests, and shared WDS runtime material |
| `_bmad-output` | machine inventory | machine inventory | completed specifications, organization records, and deferred work |
| `design-artifacts` | machine inventory | machine inventory | early product vision, model descriptions, and decisions |
| `docs` | machine inventory | machine inventory | current bilingual documentation, research originals, and scan state |
| `modules` | machine inventory | machine inventory | AMC MTA and Strategy Initializer modules |
| root files | machine inventory | machine inventory | navigation, ignore rules, and formatting configuration |

The file-by-file paths, sizes, permissions, and SHA-256 digests are recorded in [`docs/workspace-file-inventory.json`](../../workspace-file-inventory.json).

## Partition Assessment

### Business Implementation: `modules/mta_attribution`

This is an AMC anonymous-aggregate-path, five-segment multi-touch-attribution diagnostic demonstration. Its strengths are an explicit contract, complete outputs, distinct Markov and path-level Shapley governance, and strong test coverage. Its principal limits are synthetic data, no rolling-window or resampling stability evidence, no real AMC privacy-execution validation, and no causal-incrementality or automatic-budget capability.

See [AMC MTA capability assessment](./amc-mta-capability.md).

### Strategy Initialization: `modules/mta_strategy_recommendation`

This module deterministically generates `Campaign Group -> Campaign -> new Ad Group count and budget` and performs read-only cross-module AMC validation. Two JSON inputs provide candidate counts, product capacities, minimum budgets, and AMC lineage. The audited sample's real capacity calculation yielded `1/1/1/1`. All 17 MTA touchpoints rolled through the AMC `assisted_*` bridge into Campaign shares, which were divided equally among anonymous new groups in the same Campaign. The output contains no specific candidate, Targeting, or action and makes no claim of maximum return on investment, causal incrementality, or global optimality.

The [step-by-step calculation](../strategy-recommendation/current-budget-calculation.md) reproduces the current budget result. Moving from MTA evidence to Ad Group budget optimization remains a [problem definition and research plan](../strategy-recommendation/optimization-plan.md), not a capability of the current generator.

### Project Knowledge: `docs`

Current facts, module architecture, capability boundaries, research originals, and historical vision are layered. [Workspace file-location management](file-management.md) defines their placement. The recorded seven PDFs, two DOCX files, and Amazon Ads OpenAPI JSON are research inputs, not runtime dependencies.

### Historical Traceability: `design-artifacts` and `_bmad-output`

- `design-artifacts` preserves the early marketing-optimization-platform vision.
- `_bmad-output` preserves completed remediation specifications and deferred work.

They should not be deleted or allowed to override current source and contracts. Four-segment grains, `units_sold`, or removed `modules/mta` paths in old specifications belong to historical context rather than current implementation.

### Development Tools: `.agents` and `_bmad`

The recorded installation included BMad 6.8.0 and extensions: Core/BMM 6.8.0, TEA v1.19.0, BMad Builder v2.0.0, Automator `main`, CIS v0.2.1, GDS v0.6.0, and WDS v0.4.3.

The 127 identical-content groups were mainly knowledge files copied into test-architecture skills for self-contained distribution, not ordinary duplicates to remove. Placeholder links, TOML, and `TODO` examples in templates are generator inputs rather than unfinished business documentation.

## Verification Results

| Verification recorded by the source audit | Result |
| --- | --- |
| AMC MTA unit and end-to-end tests | 107/107 passed |
| Ad Group count and budget model tests | 34/34 passed |
| Complete AMC pipeline | passed; five outputs rebuilt |
| AMC/Ads alignment | 17/17 touchpoints; window, account, country, and currency aligned |
| `_bmad` configuration parsing | 1/1 passed |
| installed skill directories versus manifest | 119/119 matched |
| Python syntax | 108/108 passed |
| JavaScript syntax | 7/7 passed |
| Bash entry-point syntax | 1/1 passed |
| local project-Markdown links | 44 documents, 217 links, no broken links |
| real JSON/TOML configuration | parsed successfully |

Tool-test qualifications:

- `test-scaffold-standalone-module.py` recorded eight passes and one failure because implementation emitted plugin name `exc` while the test expected `bmad-exc`.
- `test_memlog.py` required `pytest`, which had neither a repository dependency declaration nor an installed environment, so it was not run and was not classified as a business regression.

## Risks and Priorities

1. **Add model evidence first:** executable real-AMC SQL, rolling windows, resampling, and model-stability validation.
2. **Add the engineering baseline next:** dependency locking, one test entry point, and continuous integration; the source audit found no continuous integration/deployment configuration.
3. **Isolate tool issues:** do not alter AMC MTA to repair upstream skill tests. If the standalone-module scaffold is used, repair its plugin-naming contract separately and provide the `pytest` environment.
4. **Preserve partition boundaries:** runtime code and module contracts define current facts; research, historical vision, and old specifications remain traceability material.
