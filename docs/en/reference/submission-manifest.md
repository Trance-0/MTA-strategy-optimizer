---
title: AMC MTA Submission Manifest
lang: en-US
---

# AMC MTA Submission Manifest

`mta_attribution/` is the only core submission. Use that directory as the working directory after extraction. The boundaries below are for code review, demonstration, and archival; they do not change any runtime path or CSV contract.

## Required: Core Package

- `README.md` and `SUBMISSION_MANIFEST.md`;
- `src/`, `scripts/`, `run_pipeline.py`, and `config.py`;
- `tests/`;
- `docs/`, including the complete usage guide and canonical output index;
- `docs/assets/amc-mta-data-flow.png` and its editable SVG source;
- demonstration inputs and descriptions under `data/simulated/`;
- the five canonical display results under `outputs/attribution/`.

## Excluded: Material External to the Project

- The original project's `docs/`: project knowledge, background research, and management rules.
- The original project's `design-artifacts/`: historical product visions explicitly marked unimplemented.

These materials do not accompany the standalone package, are not runtime dependencies, and must not override module contracts.

## Not Submitted with the Core Package

- The original project's `_bmad-output/`: workflow specifications, implementation status, and deferred items.
- The original project's `.agents/` and `_bmad/`: locally installed development tools.
- Personal environment overrides, caches, and temporary files.

## Acceptance Status

| Check | Status | Notes |
| --- | --- | --- |
| Core entry point, complete guide, and output index are reachable | Complete | Reachable step by step from the module README |
| Standalone data-flow diagram | Complete | PNG and SVG are stored separately and not embedded in the complete usage guide |
| Automatic window and both publishing boundaries are documented | Complete | Complete simulation regeneration atomically publishes ten items; the canonical run publishes six derived artifacts from two inputs |
| `official`, reliability, and causal boundaries are documented | Complete | See the output index and governance specification |
| Boundaries among core package, optional attachments, and process archive are documented | Complete | See this manifest |
| Module tests | Complete | Module tests run on 2026-07-29: 107/107 passed |
| Markdown relative-link check | Complete | No broken links in current non-frozen documentation for the core package and supporting material; protected paths excluded |
| Canonical CSV contract | Preserved | All five physical headers match the schema exactly; no difference from the approved baseline |

Before final submission, reviewers should confirm that working-tree differences contain only approved content and run independent tests and link validation according to project rules.
