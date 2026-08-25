---
title: Backend API
description: Flask service boundary and model route family
compact: "Backend service map for `backend/`: Flask owns runtime data access, serves the Vue client contract, runs three model jobs including strategy evaluation, and exposes synchronous attribution, recommendation, and attribution-evaluation endpoints. Routes share JSON error rules."
lang: en-US
source_files: backend/api/models.py, backend/services/models.py, backend/tests/test_models.py
---

# Backend API

The backend is one Flask process serving the built Vue client and a JavaScript
Object Notation (JSON) Application Programming Interface (API). The browser
never connects to PostgreSQL and never issues Structured Query Language (SQL):
it fetches `/api/*`, and Python alone selects, writes, or computes the answer.

The existing browser contract is preserved. `dashboard/src/api/client.js` uses
the same addresses and response shapes in a local run, an AppStack deployment,
and the file-only static build. The static build has no live server; its
snapshot is exported at build time through the same Python repositories.

Read [setups](./setups.md) for local and Alibaba Cloud operation,
[dashboard data](./dashboard-data.md) for the snapshot and master-object
routes, and [operations](./operations.md) for jobs and protected settings.
The three model families have separate request configuration pages:

- [Attribution](./attribution.md) fits one or more registered attribution models.
- [Recommendation](./recommendation.md) initializes or optimizes budgets.
- [Evaluation](./evaluation.md) scores attribution output against isolated simulator ground truth.

## Shared Model Route Rules

`GET /api/models` reports availability before a caller submits work. A `400`
response means the identifier or input violates the request contract. A `409`
response means the request is valid but this deployment lacks required
research evidence. Unexpected model failures return `500` with a bounded type
and message and are also written to the in-memory diagnostic log.

Model routes are synchronous and do not write output artifacts. Pipeline job
routes are the only backend calls that run publishing commands. Request bodies
are limited to 256 kibibytes because model routes accept configuration and
paths, not uploaded datasets.

## Source Files

### `backend/api/models.py`

Source: `backend/api/models.py`

- Responsibility: Registers `GET /api/models`, attribution, comparison,
  recommendation, optimization, and evaluation routes and maps service
  exceptions to JSON status contracts.
- Inputs: Route identifiers and JSON objects no larger than 256 kibibytes.
- Outputs: Model result objects or `{error, message}` refusals.
- Dependencies: `backend/services/models.py` and diagnostic logging.
- Verification: `uv run --extra backend python -X utf8 -B -m unittest discover -s backend/tests -t . -p "test_*.py"`.

### `backend/services/models.py`

Source: `backend/services/models.py`

- Responsibility: Loads model-facing data without a ground-truth field, runs
  registered attribution models, invokes the strategy initializer or
  optimizer, and passes ground truth only to the evaluator.
- Inputs: The fields specified on the three endpoint configuration pages;
  omitted paths resolve to committed reports or `MTA_SIM_DATA_DIR`.
- Outputs: JSON-serializable standard attribution rows, budget plans, and
  evaluation reports; no files are written.
- Dependencies: `modules/mta_standard`, `modules/mta_strategy_recommendation`,
  and read-only backend repositories for default recommendation inputs.
- Verification: `backend/tests/test_models.py` exercises a real uniform model,
  comparison, recommendation, evaluation success, and unavailable states.

### `backend/tests/test_models.py`

Source: `backend/tests/test_models.py`

- Responsibility: Holds the model route acceptance tests, including the
  structural isolation of evaluation input from training input.
- Inputs: Committed local fixtures plus a temporary ground-truth file.
- Outputs: `unittest` assertions only; temporary data is removed automatically.
- Dependencies: Flask test client and the public backend service loader.
- Verification: The backend discovery command above.
