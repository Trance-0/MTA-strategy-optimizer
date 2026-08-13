---
title: Workspace Architecture
compact: "Three-layer workspace model covering the business pipeline, knowledge base, and non-runtime tooling, plus the technology stack, data and security boundaries, and known architecture gaps."
lang: en-US
---

# Workspace Architecture

## Architectural Positioning

This repository has three layers—a business-data pipeline, a versioned knowledge base, and an embedded development toolchain. It is not a web service, database application, or deployment platform.

<DrawioDiagram base="/en/reference/module-ownership" alt="Parallel module ownership and data flow" />

Historical tool outputs are reference material only. Trance-0 development does not use the BMad workflow unless a future task explicitly requests it, and neither `.agents` nor `_bmad` enters the runtime calculation path.

## Business Execution Architecture

AMC MTA is a Python-standard-library data pipeline:

1. local simulation derives anonymous conceptual events, an Ads daily report, and touchpoint-entity aggregates from a synthetic user-event fact table;
2. conceptual events become AMC-style anonymous aggregate paths after strict five-segment-key validation;
3. Markov and path-level Shapley run independently;
4. attribution joins the aligned five-segment Amazon Ads cost and platform metrics;
5. the pipeline produces touchpoint comparisons, overall summaries, and governed recommendations, while the entity aggregate remains available to the Strategy Initializer.

The module has no network requests, database, API endpoint, authentication, background job, or user interface. See [AMC MTA architecture](./amc-mta-architecture.md) for detailed algorithms and data flow.

The Strategy Initializer also uses only the Python standard library. It retains the MTA five-segment key, treats Campaign Group as the top level, reads a strategy request and candidate-count JSON, calculates new Ad Group counts for four fixed Campaigns, rolls all MTA touchpoints through the AMC entity bridge into Campaign budgets, and divides each Campaign's share equally among anonymous new groups. The generator produces the result deterministically. Each Campaign carries one `ad_product`; the output does not allocate specific Keywords, SKUs, or Targeting.

## Knowledge Architecture

The authority order is:

Authority descends from runtime code and tests, through module data and governance contracts, reproducible outputs, current architecture and capability assessments, project introductions, research notes, and finally historical product documents and frozen specifications.

This order resolves cases where an early vision is broader than the implementation or an old specification records superseded fields and grains. [Workspace file-location management](file-management.md) defines file responsibilities, stable entry points, and archival flow.

## Development Boundary

Trance-0 development uses the repository's root commands, package imports, unit tests, and documentation build. `_bmad`, `_bmad-output`, and `.agents` are preserved for historical traceability only; their workflow scripts are not used for future development unless a task explicitly opts in. Runtime code does not import any of them.

## Technology Stack

| Area | Technology | Purpose |
| --- | --- | --- |
| AMC MTA | Python 3.10+ standard library | CSV data pipeline, algorithms, and tests |
| Preserved historical tools | TOML, YAML, CSV, Markdown, scripts | reference only; not a development dependency |
| Documentation helpers | Node.js JavaScript, Draw.io | site build and editable architecture assets |
| Documentation | CommonMark, SVG, JSON, PDF, DOCX | project knowledge and research |
| Version control | Git | the audited state had no continuous integration/deployment configuration |

## Data and Security Boundaries

- Current business inputs and outputs are repository-contained synthetic CSV and JSON files.
- `.env`, local overrides, caches, and ordinary generated output are isolated by `.gitignore`.
- The recorded audit found no real API keys, private keys, or credentials; password/token strings in skill knowledge were examples.
- The synthetic user-event source and AMC conceptual events are local demonstrations, not evidence that AMC exports user-level events.
- The repository has no production deployment, secret management, data-retention implementation, or AMC privacy-enforcement implementation.

## Architecture Gaps

- The recorded audit found no dependency lock for Python, unified task entry point, or continuous integration.
- There is no real AMC query definition or evidence of executing privacy thresholds.
- There is no rolling-window, resampling, or cross-time stability data layer.
- Tool tests do not share one environment declaration; at least one recorded test required `pytest` that was not installed.
- The standalone-module scaffold had a recorded plugin-naming mismatch between implementation and test expectations.
