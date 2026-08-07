---
title: Workspace File-Location Management
lang: en-US
---

# Workspace File-Location Management

This page defines each workspace partition's sole responsibility, stable paths, and safe movement process. Runtime code, tests, and module contracts remain the authority for current business facts.

## Responsibility Partitions

| Partition | Sole responsibility | Allowed content |
| --- | --- | --- |
| repository root | workspace entry and a small set of global configuration | `README.md`, ignore/format rules, and protected human-maintained `log.md` |
| `modules/mta_attribution/` | five-segment touchpoint attribution | source, scripts, tests, module input, and five canonical outputs; no Markdown documentation |
| `modules/mta_strategy_recommendation/` | Campaign Group count and budget initialization | synthetic run-condition data, generator, canonical budget output, validator, and tests; no Markdown documentation |
| `docs/en/` and `docs/zh/` | current project knowledge | mirrored language documentation for contracts, architecture, assessments, management rules, product introductions, and research explanations |
| `docs/research/` | external research originals | PDFs, DOCX, JSON, TXT, and other source binaries; no project-authored Markdown after migration |
| `design-artifacts/` | historical product vision | Product Brief, PRD, model concepts, addenda, and decision records |
| `_bmad-output/` | workflow traceability | approved specifications, implementation status, and deferred work |
| `.agents/`, `_bmad/` | installed development tools | skills, manifests, configuration, templates, and shared runtime material |

Research papers and platform originals are not AMC MTA inputs. Historical design/workflow files do not describe current delivered capability. Duplicate resources inside installed tools are self-contained distribution assets and are not cleaned as ordinary duplicates.

## Stable Paths and Entry Points

- The repository entry remains `README.md`; `docs/index.md` redirects to the active English site.
- All maintained commands run from project-level `script/`; reusable module logic stays under the owning `src/` directory. Module explanations and contracts live in the bilingual Attribution, Datasets, and Environment sections.
- Strategy Initializer documentation lives in the bilingual Strategy section. Its two inputs remain in `modules/mta_strategy_recommendation/data/simulated/`; the single canonical budget result remains `modules/mta_strategy_recommendation/outputs/initial_budget_recommendation.json` and is reused directly by tests.
- Current strategy contracts and the reproducible calculation belong under `docs/en/strategy/` with preserved Chinese counterparts under `docs/zh/strategy/`. Future research such as `optimization-plan.md` must remain explicitly marked as unimplemented and must not be placed in runtime `outputs/` or presented as current capability.
- Bilingual multi-page sections use `index.md`. External binary originals are linked from bilingual research indexes.
- Historical vision remains under `design-artifacts/`; implementation records remain under `_bmad-output/`.
- `docs/.archive/` is reserved for historical scan output and is not a current documentation entry point.
- Installed or historical paths under `.agents/`, `_bmad/`, and `_bmad-output/implementation-artifacts/` remain stable unless a separately approved upgrade or migration changes them.

## Naming and Archival Rules

- Bilingual section entry points use `index.md`; other Markdown uses descriptive kebab-case English filenames in both language trees.
- External research originals retain publication names and extensions by default. Correct only clear spelling errors, verify SHA-256 before and after a move, and never rewrite binary content as part of a rename.
- Current facts and module contracts live under the language trees. Superseded but traceable scan output belongs in `docs/.archive/`; historical product vision belongs in `design-artifacts/`.
- Do not create symbolic links to imitate old paths. Update current indexes and links when paths change; frozen specifications retain old paths as historical evidence.

## Move and Addition Process

1. Select the destination by sole responsibility and confirm it does not already exist.
2. Inspect Git status and preserve all unrelated uncommitted user changes.
3. Record source SHA-256 for external originals and binary files.
4. Move only explicitly approved paths; avoid broad recursive deletion and ambiguous globs.
5. Update the repository entry, section indexes, relative links, and current-path explanations.
6. Recheck binary hashes, Markdown links, and reachability from the active documentation entry.
7. Refresh `docs/project-scan-report.json` and `docs/workspace-file-inventory.json` when those generated audits are intentionally maintained, then run tests and diff checks.
8. Deleting content, changing business semantics, or moving stable runtime paths requires separate authorization.

## `log.md` Protection Rule

`log.md` is a human work record. Automated organization, formatting, movement, content inspection, and summary calculation exclude it. Inventories and scans must omit its contents and hash unless the user later authorizes that path explicitly.

## Derived-Inventory Rules

`docs/workspace-file-inventory.json` records relative path, size, Unix permissions, and SHA-256 for ordinary workspace files. It explicitly excludes:

- `.git/` internals;
- the inventory file itself;
- ignored `_bmad/custom/*.user.toml` personal overrides;
- protected `log.md`;
- `docs/系统架构图-07.drawio` when a task explicitly protects it.

The inventory is path-sorted and should reconcile both ways with disk. `docs/project-scan-report.json` records scan scope, final counts, verification, and exclusions. Both are derived state and do not replace runtime source or contracts.
