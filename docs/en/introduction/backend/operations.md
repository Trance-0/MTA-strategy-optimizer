---
title: Backend Jobs and Settings
description: Pipeline job polling and protected runtime settings contracts
compact: "Specifies `/api/jobs` and `/api/settings`: validated subprocess argument vectors, bounded logs and history, three runnable model stages including strategy evaluation, stop semantics, cache invalidation, connection testing, protected `.env` writes, read-only AppStack behavior, and diagnostics."
lang: en-US
source_files: backend/api/jobs.py, backend/api/settings.py, backend/services/jobs.py, backend/services/settings.py
---

# Backend Jobs and Settings

## Pipeline Jobs

`GET /api/jobs` returns all three dashboard-runnable model stage definitions,
current runs, and the six
most recent completed runs. `POST /api/jobs/<stage>` validates options before
spawning a fixed argument vector with no shell. `DELETE` requests termination
of a running stage. Output keeps at most 600 lines and reports the number
dropped.

Attribution runs `script/run_pipeline.py`. Optimization runs
`script/generate_campaign_strategy.py` and requires a research snapshot.
Strategy evaluation runs `script/evaluate_strategies.py` without requiring a
research snapshot,
because it can use the response observations in `campaign_strategy.json`.
Read-only or file-mode deployments cannot start publishing jobs.

## Settings

`GET /api/settings` returns non-secret connection state, source status, logging
state, and bounded diagnostics. It never returns the stored password.

`POST /api/settings` supports `logging`, `clearLog`, `test`, and `save` actions.
Connection tests use submitted values without persisting them. Save writes the
root `.env` atomically, preserves a stored password when the form submits an
empty password, disposes the old pool, invalidates configuration caches, and
clears the snapshot.

AppStack sets `DASHBOARD_CONFIG_READ_ONLY=true`, so deployed save and test
actions return `403`; operators change environment variables through AppStack
and roll the Deployment.

## Source Files

### `backend/api/jobs.py` and `backend/services/jobs.py`

Source: `backend/api/jobs.py`, `backend/services/jobs.py`

- Responsibility: Validate stage requests, expose polling state, spawn fixed
  `uv run python` commands, capture bounded output, advance regex-based phases,
  stop processes, and clear caches after success.
- Inputs: Stage key, International Organization for Standardization (ISO)
  date range, positive budget, and declared budget policy.
- Outputs: `202` start responses, job snapshots, or specific refusal objects.
- Dependencies: Root scripts, subprocess, research snapshot configuration.
- Verification: Backend route tests plus direct job-service unit tests when a
  stage contract changes.

### `backend/api/settings.py` and `backend/services/settings.py`

Source: `backend/api/settings.py`, `backend/services/settings.py`

- Responsibility: Serve protected settings actions, atomic environment-file
  changes, database probes, and a 400-entry in-memory diagnostic ring.
- Inputs: Logging settings or connection fields; stored credentials are never echoed.
- Outputs: Sanitized settings state, probe result, or action-specific refusal.
- Dependencies: Shared dashboard configuration, database pool disposal, and
  snapshot cache invalidation.
- Verification: Flask settings requests in writable and read-only test environments.
