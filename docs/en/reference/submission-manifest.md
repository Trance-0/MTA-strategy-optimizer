---
title: AMC MTA Submission Manifest
compact: "Defines what is included in and excluded from the standalone `mta_attribution` submission package. Read only when assembling or reviewing an archival submission; it changes no runtime path or CSV contract."
lang: en-US
---

# AMC MTA Submission Manifest

`mta_attribution/` is the only core submission. Use that directory as the working directory after extraction. The boundaries below are for code review, demonstration, and archival; they do not change any runtime path or CSV contract.

## Required: Core Package

- `README.md` and `SUBMISSION_MANIFEST.md`;
- module `src/` and `config.py`, plus the project-level commands under `script/`;
- `tests/`;
- `docs/`, including the complete usage guide and canonical output index;
- `docs/en/introduction/data-flow.drawio` and its generated light/dark SVG renders;
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

### Core entry point, complete guide, and output index are reachable

- **Status:** Complete
- **Notes:** Reachable step by step from the module README

### Standalone data-flow diagram

- **Status:** Complete
- **Notes:** PNG and SVG are stored separately and not embedded in the complete usage guide

### Automatic window and both publishing boundaries are documented

- **Status:** Complete
- **Notes:** Complete simulation regeneration atomically publishes ten items; the canonical run publishes six derived artifacts from two inputs

### `official`, reliability, and causal boundaries are documented

- **Status:** Complete
- **Notes:** See the output index and governance specification

### Boundaries among core package, optional attachments, and process archive are documented

- **Status:** Complete
- **Notes:** See this manifest

### Module tests

- **Status:** Complete
- **Notes:** Module tests run on 2026-07-29: 107/107 passed

### Markdown relative-link check

- **Status:** Complete
- **Notes:** No broken links in current non-frozen documentation for the core package and supporting material; protected paths excluded

### Canonical CSV contract

- **Status:** Preserved
- **Notes:** All five physical headers match the schema exactly; no difference from the approved baseline

Before final submission, reviewers should confirm that working-tree differences contain only approved content and run independent tests and link validation according to project rules.
