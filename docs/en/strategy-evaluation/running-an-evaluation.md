---
title: Running an Evaluation
description: The evaluation pipeline stage, its command, its output artifact, and how the dashboard reads it
compact: "Specifies script/evaluate_strategies.py, the strategy_evaluation.json artifact, the dashboard `evaluation` stage with runtime output precedence and phase patterns, and the strategyEvaluation snapshot key. Explains why training runs on demand instead of shipping checkpoints."
lang: en-US
source_files: script/evaluate_strategies.py, backend/repository/evaluation.py
---

# Running an Evaluation

## Purpose <span class="status-label status-verified" aria-label="Verified"></span>

The strategy evaluation layer runs as one of the dashboard's three model stages, beside attribution and optimization, and is started the same way they are: as a documented command in a terminal, or from the dashboard's Campaign Optimizer, which spawns that identical command. This page specifies the command, the artifact, and the wiring.

## Why Train on Demand <span class="status-label status-verified" aria-label="Verified"></span>

A contributed model has to be fitted before it can predict, so the layer needs a fitting step somewhere. There were three plausible places to put it, and the choice shapes the rest of this page.

Shipping a **pretrained checkpoint** built at release time would mean committing a binary weight file. That is a generated artifact — the thing the repository's ignore rules exist to keep out — and it would be a second copy of the model free to disagree with the code that produced it, with nothing to say which was authoritative. It would also need a serialization format, a version field, and a compatibility policy for when the feature list changes.

Adding **upload and download endpoints** for checkpoints would mean accepting an arbitrary binary from a browser and deserializing it on the server. Every deserialization format that can restore a Python object can also execute code, so that endpoint would need its own authentication story, its own format validation, and its own threat model — a substantial security surface for a research model with a negative held-out fit.

**Training on demand** avoids both. The stage fits the model when it runs, from data already in the repository, and writes a JSON report. There is no checkpoint format to version, no upload endpoint to secure, and no binary in Git. The cost is that a run takes as long as the fit does; for these NumPy networks on a few hundred rows, that is seconds, and the stage runner already streams progress for runs measured in minutes.

The mechanism is the existing one. `backend/services/jobs.py` spawns a stage as a child process, streams its output, and matches phase patterns against what the script prints. The evaluation entry in that same `STAGES` dictionary therefore inherits the streaming, progress bar, Stop control, database-mode and execution-capability checks, runtime output isolation, and cache invalidation on success without any of them being written again.

## The Command <span class="status-label status-verified" aria-label="Verified"></span>

```bash
uv run python -X utf8 -B script/evaluate_strategies.py
```

With the contributed model, which needs the numerical stack:

```bash
uv sync --extra strategy-evaluation
uv run python -X utf8 -B script/evaluate_strategies.py --fit-contributed-model
```

#### `--strategy-directory`

Where the two strategy artifacts are read from. Defaults to `modules/mta_strategy_recommendation/outputs/`.

#### `--research-snapshot`

An optional Multi-Touch Attribution Simulator (MTA-SIM) `simulation_research.json`. When supplied, the observed Campaign episodes are built from it and layer two can run. When omitted, the observations recorded inside `campaign_strategy.json` are used instead, so the stage still runs on a checkout with no simulator data.

#### `--marketplace`

Optional exact marketplace code used to partition a multi-marketplace research
snapshot. Dashboard jobs always pass the marketplace of the advertiser in the
connected schema. Evaluation also matches episodes to each projected
strategy's marketplace and currency, so Campaign identifiers reused across
markets can never attach the wrong observations to a decision.

#### `--fit-contributed-model`

Fit and score the contributed network as well. Off by default, because it requires the optional extra and, on the current data, returns an insufficient-data result. When the extra is missing, the stage reports the model as unavailable and names the `uv sync` command rather than failing.

#### `--output`

Destination for the artifact. Defaults to `modules/mta_strategy_evaluation/outputs/strategy_evaluation.json`.

The stage writes exactly one file, to a path matched by the root `.gitignore`'s `modules/*/outputs/` rule with no negation, so its output is never committed. It writes nothing into `modules/mta_strategy_evaluation/contrib/`.

## The Artifact <span class="status-label status-verified" aria-label="Verified"></span>

`strategy_evaluation.json` holds one entry per evaluated strategy plus a run summary:

#### `strategies`

One object per projected `StrategyOutput` — the deterministic seed and the optimized plan — each carrying its `strategy_id`, `allocation_type`, its serialized decision, and the three layer results from [Evaluation Layers](./evaluation-layers.md): `contract`, `baseline_comparison`, and `ground_truth`, the last always a not-run marker.

#### `contributed_models`

One object per contributed model that was asked to run, carrying its identifier, whether it was usable, its measured metrics, and its caveat text. Present and empty when `--fit-contributed-model` was not passed.

#### `summary`

The run's counts: how many strategies were projected, how many conserved, and how many were skipped with the reason.

A strategy that fails its conservation check appears in the artifact with its violations listed and is not scored further. A strategy that could not be projected at all — an optimizer run that refused, for instance — is recorded in `summary.skipped` with the refusal's own reasons, never as an allocation of zero.

## Backend Wiring <span class="status-label status-verified" aria-label="Verified"></span>

### The stage

The `evaluation` entry in `backend/services/jobs.py` previously carried `"script": None` and an `unavailableReason` explaining that the layer was specified but unbuilt. It now names the real script and its phase patterns, so `jobs_state()` reports it available and `start_refusal()` no longer returns `stage_unavailable`. `POST /api/jobs/evaluation` runs it.

The stage declares no `requiresResearchSnapshot`, because it falls back to the observations inside `campaign_strategy.json` and therefore has an honest run available on any checkout. Its phase patterns match the lines the script prints, in order: projecting strategies, checking conservation, comparing against baselines, fitting the contributed model, and writing the artifact.

### The snapshot key

`backend/repository/evaluation.py` adds `strategy_evaluation()`, registered as `strategyEvaluation` in the `LOADERS` dictionary in `backend/repository/snapshot.py`. Like `campaignStrategy`, it is read in its own shape in both file and database modes, because the artifact is produced by a research command rather than by the import pipeline and has no table. When configured, a completed `PIPELINE_OUTPUT_DIR/evaluation/strategy_evaluation.json` takes precedence over the baseline artifact. An absent runtime and baseline file returns an empty object, which the dashboard reads as "the evaluation has not run" — the honest reading in both modes.

The key set is asserted exactly by `backend/tests/test_snapshot.py`, so adding it there is part of the same change rather than a follow-up. `dashboard/src/api/client.js` returns the payload whole without enumerating keys, so the client needs no change to receive it.

## Source Files <span class="status-label status-verified" aria-label="Verified"></span>

### `evaluate_strategies.py`

Source: `script/evaluate_strategies.py`

- Responsibility: Command-line entry point for the strategy evaluation layer. Projects the committed strategy artifacts, runs the three evaluation layers over each, optionally fits the contributed model, and writes one JSON artifact.
- Inputs: `initial_budget_recommendation.json` and `campaign_strategy.json`;
  optionally a marketplace-scoped MTA-SIM research snapshot.
- Outputs: `modules/mta_strategy_evaluation/outputs/strategy_evaluation.json`, and progress lines on standard output that the stage runner matches phases against.
- Public entry points: `main() -> int`, returning `0` on success and `1` when no strategy could be projected at all.
- Error handling: a strategy that cannot be projected is reported and skipped, not fatal. A missing NumPy is reported as an unavailable contributed model naming the `uv sync` remedy, not as a failed run. Only an empty result set is an error.
- Determinism: strategies are processed in artifact order; the artifact is written with `sort_keys=True` and a trailing newline, matching `generate_campaign_strategy.py`.
- Dependencies: `modules/mta_strategy_evaluation/src/*`, `modules/mta_strategy_evaluation/adapters/asin_gmv_nn_adapter.py`, `modules/mta_strategy_recommendation/src/response_dataset.py`, `modules/mta_standard/src/mta_sim_research_adapter.py`.
- Verification: `modules/mta_strategy_evaluation/tests/test_evaluate_strategies.py`.

### `evaluation.py`

Source: `backend/repository/evaluation.py`

- Responsibility: Serve the evaluation artifact as one snapshot key, preferring a completed runtime result and returning an empty object when the stage has not run.
- Inputs: `PIPELINE_OUTPUT_DIR/evaluation/strategy_evaluation.json`, then `modules/mta_strategy_evaluation/outputs/strategy_evaluation.json` as fallback.
- Outputs: `strategy_evaluation() -> dict`, registered as `strategyEvaluation`.
- Dependencies: `backend/config.py`, `backend/repository/coercion.py`.
- Verification: `backend/tests/test_snapshot.py`.

## Current Availability <span class="status-label status-verified" aria-label="Verified"></span>

The stage runs and writes its artifact. Both committed strategies project and both conserve. Layer three does not run, for the reason given in [Evaluation Layers](./evaluation-layers.md), and the contributed model returns insufficient data on the current artifact.

## Known Limitations <span class="status-label status-verified" aria-label="Verified"></span>

- Without a research snapshot the observed episodes come from `campaign_strategy.json`, so the evaluation covers only the two Campaigns the optimizer ran on, not the four in the deterministic seed. Those two are reported and the rest are named as unobserved.
- The stage refits on every run rather than caching, which is the cost of holding no checkpoint.
- The dashboard's evaluation tab explains and runs the evaluation stage. Willow Sakura's native forecast panel is a separate contributed demonstration; it does not render or modify the production `strategyEvaluation` artifact.

## References

- [Strategy output](./strategy-output.md)
- [Evaluation layers](./evaluation-layers.md)
- [Contributed models](./contributed-models/index.md)
- [Dashboard deployment](/en/dashboard/deployment.md)
