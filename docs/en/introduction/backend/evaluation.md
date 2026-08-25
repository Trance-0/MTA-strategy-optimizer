---
title: Evaluation Endpoint Configuration
description: Attribution model scoring against isolated simulation ground truth
compact: "Configures attribution scoring at `POST /api/models/evaluate`: model selection, isolated ground truth, optional report paths, positive Top-K, error, distance, rank, overlap, and conservation metrics; distinguishes the independently runnable strategy-evaluation pipeline stage."
lang: en-US
---

# Evaluation Endpoint Configuration

## Request

Call `POST /api/models/evaluate` with `modelId` or a non-empty `modelIds` list.
`groundTruth` may name a simulator ground-truth Comma-Separated Values (CSV)
file; otherwise the endpoint
uses `MTA_SIM_DATA_DIR/simulation_ground_truth.csv`. `pathReport` and
`adsReport` configure the model-facing dataset exactly as they do for
attribution. `topK` defaults to `5` and must resolve to a positive integer.

The model-facing dataset type has no ground-truth field, and its loader accepts
no ground-truth path. The service opens ground truth only after loading model
input, then passes it to the evaluator. This structural separation prevents a
model from training on its answer key.

## Response

Each report contains model identity, version, scope, runtime, missing
touchpoints, and metrics per Outcome. Metrics are Mean Absolute Error (MAE),
Root Mean Squared Error (RMSE), Total Variation Distance (TVD), Spearman rank
correlation (Rho), Top-K overlap, and conservation error. All abbreviations use
the project definitions in [Terms and Abbreviations](/en/reference/definitions).

## Availability

Committed platform reports do not contain causal ground truth, so evaluation
returns `409 model_unavailable` until a simulator file is configured or named.
The catalogue reports this before a request is made.

This route evaluates attribution models. Strategy evaluation is a separate
pipeline concern: `POST /api/jobs/evaluation` runs
`script/evaluate_strategies.py`, and the resulting report is returned under
the `strategyEvaluation` dashboard snapshot key. The model catalogue reports
that capability independently from whether attribution ground truth is
configured.
