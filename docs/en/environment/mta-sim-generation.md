---
title: Generate MTA-SIM Data
description: Run the pinned ZheyuanWu generator and adapt its output for local models
compact: "Governs `script/generate_mta_sim_dataset.py` with `--variant baseline|regional`, `--config`, `--output`, the `external/mta_sim_dataset` submodule, and the files written to `generated/mta_sim/`: `amc_path_report.csv`, `dataset_manifest.json`, `validation_report.json`, `model_input_amc_path_report.csv`, `model_evaluation_ground_truth.csv`. Read when generating new synthetic data."
lang: en-US
---

# Generate MTA-SIM Data

## Source and boundary <span class="status-label status-verified" aria-label="Verified"></span>

The primary synthetic data source is the [Trance-0/MTA-SIM-dataset](https://github.com/Trance-0/MTA-SIM-dataset) Git submodule at `external/mta_sim_dataset`. The submodule is pinned to a reviewed commit; updating it is a separate, reviewable Git change.

The integration uses the public generator under `ZheyuanWu/`. The external generator owns simulation, validation, and CSV storage. This repository owns only the explicit contract adapter and model processing that follow generation.

The adapter flow is:

1. read the `external/mta_sim_dataset/ZheyuanWu` configuration;
2. run the ZheyuanWu baseline or regional generator;
3. receive the original four-segment path, performance, and ground-truth tables;
4. adapt them through `mta_sim_generator_adapter` into a single-scope path report with explicit CPC/CPM interaction mapping; and
5. load the result as `MtaSimDataset` for the locally registered models.

Simulation ground truth remains evaluation-only. It is normalized into a compatible reporting scope but is never attached to `MtaSimDataset` or passed to `fit()` or `attribute()`.

## Initialize the submodule <span class="status-label status-recommendation" aria-label="Recommendation"></span>

From the project root:

```sh
git submodule update --init --recursive
```

For a new clone, `git clone --recurse-submodules` performs the same initialization while cloning.

## Generate the public toy dataset <span class="status-label status-verified" aria-label="Verified"></span>

```sh
uv sync --locked
uv run python -X utf8 -B script/generate_mta_sim_dataset.py
```

The default command uses `external/mta_sim_dataset/ZheyuanWu/examples/baseline.toy.json` and writes to the ignored `generated/mta_sim/` directory. It prints the generator version, report scope, path count, performance count, and touchpoint count after local adaptation succeeds.

Use caller-owned paths for another approved configuration:

```sh
uv run python -X utf8 -B script/generate_mta_sim_dataset.py \
  --variant baseline \
  --config path/to/config.json \
  --output path/to/generated-data
```

`--variant regional` selects the ZheyuanWu regional pipeline. The current standardized model accepts one marketplace and advertiser per run; use a single-marketplace configuration or split a multi-marketplace generated bundle before model processing.

## Generated files <span class="status-label status-verified" aria-label="Verified"></span>

| File | Owner | Role |
| --- | --- | --- |
| `amc_path_report.csv` | ZheyuanWu | Original daily-window four-segment path report |
| `amazon_ads_daily_touchpoint_performance.csv` | ZheyuanWu | Original daily delivery and cost table |
| `simulation_ground_truth.csv` | ZheyuanWu | Original evaluation-only truth table |
| `dataset_manifest.json` | ZheyuanWu | Reproducibility metadata and source hashes |
| `validation_report.json` | ZheyuanWu | Generator contract validation result |
| `model_input_amc_path_report.csv` | Local adapter | Daily windows aggregated into one model scope |
| `model_evaluation_ground_truth.csv` | Local adapter | Ground-truth scope normalized for separate evaluation |

The original generator files are never rewritten by the adapter. Generated output is ignored by Git; only deliberately reviewed synthetic public fixtures may be committed.

## External verification note <span class="status-label status-external" aria-label="External"></span>

At the pinned revision, the submodule's 10 baseline tests and six regional tests pass. Its contributor instructions also name a root `scripts/check_public_release.py` command, but that file is not present in the pinned repository tree, so that specific upstream check cannot be executed. This repository records the limitation rather than substituting a different check.

## Legacy compatibility commands <span class="status-label status-historical" aria-label="Historical"></span>

The root `script/generate_simulated_*.py` and `script/regenerate_simulated_dataset.py` commands retain the behavior of the earlier repository-specific five-segment fixture generator. They exist to reproduce the committed historical sample and its strategy bridge. New data-generation work should use `script/generate_mta_sim_dataset.py`.
