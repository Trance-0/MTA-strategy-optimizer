---
title: Generate MTA-SIM Data
description: Run the pinned ZheyuanWu generator and adapt its output for local models
compact: "Governs `modules/mta_standard/src/generate_mta_sim_dataset.py` with `--variant baseline|regional`, `--config`, `--output`, the `external/mta_sim_dataset` submodule, the KFC scenario configurations under `config/mta_sim/` including the merged `kfc-global.json`, and the generated output files. Read when generating new synthetic data."
lang: en-US
source_files: modules/mta_standard/src/generate_mta_sim_dataset.py
---

# Generate MTA-SIM Data

## Source and boundary <span class="status-label status-verified" aria-label="Verified"></span>

The primary synthetic data source is the [Trance-0/MTA-SIM-dataset](https://github.com/Trance-0/MTA-SIM-dataset) Git submodule at `external/mta_sim_dataset`. The submodule is pinned to a reviewed commit; updating it is a separate, reviewable Git change.

The integration uses the public generator under `ZheyuanWu/`. The external generator owns simulation, validation, and CSV storage. This repository owns only the explicit contract adapter and model processing that follow generation.

The adapter flow is:

1. read the `external/mta_sim_dataset/ZheyuanWu` configuration;
2. run the ZheyuanWu baseline or regional generator;
3. receive the original CSV schemas carrying native five-segment path, performance, and ground-truth values;
4. preserve the interaction-aware values through `mta_sim_generator_adapter` while aggregating a single-scope path report; and
5. load the result as `MtaSimDataset` for the locally registered models.

Simulation ground truth remains evaluation-only. It is normalized into a compatible reporting scope but is never attached to `MtaSimDataset` or passed to `fit()` or `attribute()`.

## Initialize the submodule <span class="status-label status-recommendation" aria-label="Recommendation"></span>

From the project root:

```sh
git submodule update --init
```

Initialize one level only. `external/campaign-optimizer-llm-integration` declares this repository as one of its own submodules, so `--recursive` re-enters the project and retrieves a stale copy of itself: about 62 megabytes instead of 8, with a second copy of this generator inside it.

For a new clone, `git clone --recurse-submodules` would recurse the same way; clone normally and run the command above instead.

## Generate the public toy dataset <span class="status-label status-verified" aria-label="Verified"></span>

```sh
uv sync --locked
uv run python -X utf8 -B -m modules.mta_standard.src.generate_mta_sim_dataset
```

The default command uses `external/mta_sim_dataset/ZheyuanWu/examples/baseline.toy.json` and writes to the ignored `generated/mta_sim/` directory. It prints the generator version, report scope, path count, performance count, and touchpoint count after local adaptation succeeds.

Use caller-owned paths for another approved configuration:

```sh
uv run python -X utf8 -B -m modules.mta_standard.src.generate_mta_sim_dataset \
  --variant baseline \
  --config path/to/config.json \
  --output path/to/generated-data
```

`--variant regional` selects the ZheyuanWu regional pipeline. The current standardized model accepts one marketplace and advertiser per run; use a single-marketplace configuration or split a multi-marketplace generated bundle before model processing.

## Generated files <span class="status-label status-verified" aria-label="Verified"></span>

### `amc_path_report.csv`

Owner: ZheyuanWu. Role: Original daily-window path report with native five-segment values and unchanged columns.

### `amazon_ads_daily_touchpoint_performance.csv`

Owner: ZheyuanWu. Role: Original daily delivery and cost table.

### `simulation_ground_truth.csv`

Owner: ZheyuanWu. Role: Original evaluation-only truth table.

### `dataset_manifest.json`

Owner: ZheyuanWu. Role: Reproducibility metadata and source hashes.

### `validation_report.json`

Owner: ZheyuanWu. Role: Generator contract validation result.

### `model_input_amc_path_report.csv`

Owner: Local adapter. Role: Daily windows aggregated into one model scope.

### `model_evaluation_ground_truth.csv`

Owner: Local adapter. Role: Ground-truth scope normalized for separate evaluation.

The original generator files are never rewritten by the adapter. Generated output is ignored by Git; only deliberately reviewed synthetic public fixtures may be committed.

## KFC scenario configurations

The tracked configurations under `config/mta_sim/` define the synthetic KFC
scenario family. `kfc-multi-provider.base.json` carries the shared campaigns,
providers, touchpoints, products, and path scenarios; the regional files
`kfc-us.json`, `kfc-europe.json`, and `kfc-asia.json` extend it with one
marketplace and currency each, keeping the three-level scheduled budget
experiment (`0.75, 1.0, 1.25`). Three levels satisfy the fitter's minimum
distinct-budget requirement but give the response curve almost no support
between and beyond them, which is why strategies fitted from the regional
schemes are weak.

`kfc-global.json` is the merged single-scope scheme for strategy optimization:
one `GLOBAL` marketplace in United States Dollars (USD), the same six
campaigns across the three provider families, and a nine-level randomized
budget experiment (`0.5` through `1.6`, `assignment_type: RANDOMIZED`). Each
day draws one arm per Campaign, so a year of history observes every Campaign
at nine distinct budgets with dozens of days each — dense support for the
budget-response fit. The canonical data model holds one advertiser, one
marketplace, and one currency per scope, so this merged scheme replaces the
three regional schemes for cross-provider optimization rather than combining
their differently denominated observations.

## Latest integration check (2026-09-18)

The documented baseline toy command was run from an empty caller-owned output
directory. The pinned generator produced 12 performance rows, 4 aggregated
paths, and 4 five-segment touchpoints for marketplace `TOY` from 2025-01-01
through 2025-01-03. The local adapter created
`model_input_amc_path_report.csv` and `model_evaluation_ground_truth.csv`; the
ground-truth file remained separate from `MtaSimDataset`.

The generated bundle was then registered through the upload path as an
immutable `generated` dataset. Registration validated all performance, path,
and research rows and reported performance, attribution, and history as
available. Attribution ran through the registered-workbench command and
published Markov, Shapley, comparison, and recommended-attribution outputs.

The three-day toy research snapshot has one budget level per Campaign, so the
response optimizer correctly returned `is_optimized: false` with an
insufficient-support reason. That is a valid strategy refusal, not an
allocation of zero. A direct evaluation run therefore records the optimizer as
skipped; the evaluation artifact is still written with the refusal reason and
the optional contributed model reports `insufficient_data` for its three-row
panel.

The larger `research-10k.json` preset was also checked. It generates multiple
marketplaces, and the standardized local model intentionally refuses that
bundle until a marketplace is selected or the reports are split. This is the
documented single-scope boundary, not a parser failure.

## Dashboard generation workflow <span class="status-label status-verified" aria-label="Verified"></span>

The [Data Generator dashboard view](/en/dashboard/data-generator.md) calls the
same pinned generator boundary. It accepts only a self-contained configuration
object, writes it under the ignored runtime directory, and exposes two bounded
previews. PostgreSQL credentials are accepted only by the backend export route
and are never stored or returned to Vue.

## External verification note <span class="status-label status-external" aria-label="External"></span>

At the pinned revision, the submodule's 10 baseline tests and six regional tests pass. Its contributor instructions also name a root `scripts/check_public_release.py` command, but that file is not present in the pinned repository tree, so that specific upstream check cannot be executed. This repository records the limitation rather than substituting a different check.

## Legacy compatibility commands <span class="status-label status-historical" aria-label="Historical"></span>

The root `modules/mta_attribution/src/generate_simulated_*.py` and `modules/mta_attribution/src/regenerate_simulated_dataset.py` commands retain the behavior of the earlier repository-specific five-segment fixture generator. They exist to reproduce the committed historical sample and its strategy bridge. New data-generation work should use `modules/mta_standard/src/generate_mta_sim_dataset.py`.

## Source Files

### `generate_mta_sim_dataset.py`

Source: `modules/mta_standard/src/generate_mta_sim_dataset.py`

- Responsibility: Expose the pinned generator adapter through `main(arguments=None)`
  and `build_argument_parser()` using the flags documented above.
- Inputs: `--submodule`, `--config`, `--output`, and `--variant baseline|regional`.
  Defaults point to the pinned generator toy preset and ignored `generated/mta_sim/`.
- Outputs: Generated artifacts and a JSON summary containing generator identity,
  output directory, counts, report dates, marketplace and evaluation-only ground-truth role.
- Errors: Missing input, runtime and validation errors print a bounded diagnostic
  and return one; successful generation and adaptation return zero.
- Dependencies: `mta_sim_generator_adapter.py` and Python standard library;
  execution uses `python -m` without changing import paths.
- Verification: `modules/mta_standard/tests/test_mta_sim_generator_adapter.py`
  and the documented toy-generation command.
