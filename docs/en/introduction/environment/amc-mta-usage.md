---
title: AMC MTA Usage
compact: "Command reference for `run_pipeline.py`, `run_attribution_models.py`, comparison, regeneration, and alignment flags; native MTA-SIM performance annotation; and the five attribution CSV outputs, their governed schemas, reliability fields, and recommended_value semantics."
lang: en-US
source_files: modules/mta_attribution/src/build_path_report.py, modules/mta_attribution/src/compare_attribution_models.py, modules/mta_attribution/src/run_attribution_models.py, modules/mta_attribution/src/run_pipeline.py, modules/mta_attribution/src/validate_data_alignment.py, modules/mta_attribution/src/regenerate_simulated_dataset.py
---

# AMC MTA Usage

Run all commands below from the repository root. See the [data contract](../../market-simulation/amc-data-contract.md) for field and path rules. This module is for attribution analysis only; it does not allocate budgets or optimize activation.

## Run

Complete pipeline:

```bash
uv run python -X utf8 -B -m modules.mta_attribution.src.run_pipeline
```

Replace only the events and Amazon Ads input files, then run the command again. The canonical pipeline automatically uses the earliest through latest Ads `reportDate` as its window; `config.py` does not need to be changed. The path report and all five model outputs are completed and validated in a temporary directory before being published together. If input validation fails, no valid paths exist, or publishing fails, the six existing derived artifacts remain unchanged. The program never overwrites raw inputs.

Use custom input and output locations:

```bash
uv run python -X utf8 -B -m modules.mta_attribution.src.run_pipeline \
  --events-file path/to/amc_touchpoint_events.csv \
  --amazon-ads-report path/to/amazon_ads_report.csv \
  --path-report path/to/amc_path_report.csv \
  --output-dir path/to/attribution_outputs
```

Build only the aggregated paths:

```bash
uv run python -X utf8 -B -m modules.mta_attribution.src.build_path_report
```

This command also detects its window from the Ads input by default. Override any file path separately when necessary:

```bash
uv run python -X utf8 -B -m modules.mta_attribution.src.build_path_report \
  --events-file path/to/amc_touchpoint_events.csv \
  --amazon-ads-report path/to/amazon_ads_report.csv \
  --output-file path/to/amc_path_report.csv
```

Atomically rebuild all ten simulated and attribution artifacts from the same user-event master table:

```bash
uv run python -X utf8 -B -m modules.mta_attribution.src.regenerate_simulated_dataset
```

You can run `modules/mta_attribution/src/generate_simulated_synthetic_user_events.py`, `modules/mta_attribution/src/generate_simulated_amc_touchpoint_events.py`, `modules/mta_attribution/src/generate_simulated_amazon_ads_report.py`, or `modules/mta_attribution/src/generate_simulated_touchpoint_entity_aggregate.py` separately to inspect an individual legacy data layer. These compatibility commands reproduce the committed five-segment fixture. New synthetic datasets should use the pinned ZheyuanWu command documented in [Generate MTA-SIM data](mta-sim-generation.md).

Run attribution only on an existing aggregated path report:

```bash
uv run python -X utf8 -B -m modules.mta_attribution.src.run_attribution_models
```

The Amazon Ads input may use either the maintained attribution-report schema,
which carries explicit `interaction_type` and `cost_type`, or the native
MTA-SIM daily-performance schema. Native rows carry the interaction in the
fifth segment of `normalizedTouchpoint`; the command restores that field and
the project's Click/Cost Per Click (CPC) or Impression/Cost Per Mille (CPM)
pairing before validation. It then rebuilds the key from `adProduct`, the
product-specific format column, placement, creative, and restored interaction,
and refuses a stored key that disagrees. This is deterministic annotation of
fields already encoded in the row, not a guessed touchpoint.

Native MTA-SIM `amc_path_report.csv` contains multiple daily windows. A
dashboard run first calls the standard generator adapter to sum every row per
path into one scope whose start and end come from the accompanying performance
report. The original upload is never rewritten. A direct invocation of
`run_attribution_models.py` still requires its `--amc-report` to be that
single-scope model input.

Strictly recompute the three comparison artifacts from existing Markov/Shapley files:

```bash
uv run python -X utf8 -B -m modules.mta_attribution.src.compare_attribution_models
```

This command removes leading and trailing whitespace from field names and values while preserving spaces inside strings. Empty or duplicate headers after cleanup, missing or extra columns, schema mismatches, invalid model names, inconsistent touchpoint sets, non-finite values, negative values, or non-conserving shares/attribution values still raise errors immediately.

Optional parameters:

```bash
uv run python -X utf8 -B -m modules.mta_attribution.src.run_attribution_models \
  --amc-report path/to/report.csv \
  --amazon-ads-report path/to/amazon_ads_report.csv \
  --output-dir path/to/output
```

Validate the window, account, currency, touchpoint set, and daily coverage of five-segment interactions across AMC and Amazon Ads:

```bash
uv run python -X utf8 -B -m modules.mta_attribution.src.validate_data_alignment
```

## Default Inputs and Outputs

Inputs are under `modules/mta_attribution/data/simulated/`; see [AMC MTA simulated data](../../market-simulation/amc-simulated-data.md) for each file's role.

Each run accepts exactly one marketplace, account, and currency scope. Ads data must be non-empty, dates must be continuous, the same five-segment touchpoint set must appear every day, and date/key combinations must be unique. Events must contain conversions; all conversions must fall inside the Ads window and yield at least one valid path. Violations raise an error immediately: the program does not crop, zero-fill, or publish. Every CSV input consistently ignores leading and trailing whitespace in field names and values while preserving spaces inside strings. The five canonical outputs continue to use a normalized physical format without leading or trailing whitespace.

- `modules/mta_attribution/outputs/attribution/amc_markov_attribution_results.csv`
- `modules/mta_attribution/outputs/attribution/amc_shapley_attribution_results.csv`
- `modules/mta_attribution/outputs/attribution/amc_mta_model_comparison_touchpoints.csv`
- `modules/mta_attribution/outputs/attribution/amc_mta_model_comparison_summary.csv`
- `modules/mta_attribution/outputs/attribution/amc_mta_recommended_attribution.csv`

Both result files use the five-segment `AD_PRODUCT:FORMAT:PLACEMENT:CREATIVE:INTERACTION_TYPE` granularity and contain `interaction_type`, all three sets of attribution values, Amazon Ads performance and cost, `roas`, `roi`, `cpa`, and `cost_per_converted_user`. Cost per click (CPC) cost appears only on CLICK rows, and cost per mille (CPM) cost only on IMPRESSION rows; costs and efficiency metrics on non-billable rows are 0/empty.

The touchpoint-comparison file has a fixed 14-column schema and `17 × 3 = 51` rows. It stores only the two model shares, `gap_pp`, `relative_gap`, the three raw support values, and reliability. The summary has a fixed 13-column schema with one row for each of the three Outcomes. It stores the window, touchpoint count, total variation distance (TVD), Spearman correlation, Top-K overlap, and reliability. The recommendation file has a fixed 15-column schema and 51 rows; it stores the official Markov display value, Shapley reference value, final recommended value, gap, and reliability. All three artifacts include `calculation_valid`, `data_support_sufficient`, `models_consistent`, `reliability_status`, and `reliability_reason`; neither single-model result contains these fields. A row is `RELIABLE` only when all three Boolean values are `true`. For each Outcome, the summary aggregates each Boolean with an AND over all touchpoints. Markov is the official displayed attribution, while Shapley is used to judge model sensitivity. Legacy cost, efficiency, gap-grade, and status fields do not belong to these three dual-model schemas.

`recommended_value` is a textual union type. For a nonzero Outcome, a `RELIABLE` row contains the single `official_share`; an `UNRELIABLE` row contains an ascending closed interval of the two model shares, `[low,high]`. It is empty for a zero Outcome. If both shares are zero under a nonzero Outcome, `[0.0,0.0]` is a valid interval.

The current 90-day sample contains `51 RELIABLE / 0 UNRELIABLE`. Results can only be interpreted as exploratory attribution within the current window; they must not be used to adjust budgets automatically.

For how to decide whether attribution for one touchpoint is reliable and how to interpret it, see [Single-touchpoint attribution reliability](../../attribution/reliability.md).

## Source Files

### `build_path_report.py`

Source: `modules/mta_attribution/src/build_path_report.py`

Aggregate event rows into the five-segment path report using the existing path builder. `build_path_report(...)` accepts event/performance input paths and an output path; `main()` supplies documented defaults. Reject invalid dates, keys and path inputs before writing the governed report.

Run from the repository root with `uv run python -X utf8 -B -m modules.mta_attribution.src.build_path_report`.
Dependencies are the owning attribution modules and Python standard library;
package imports do not modify `sys.path`. Verification uses the existing
`modules/mta_attribution/tests/test_end_to_end_pipeline.py` suite, with window,
key and comparison cases in the adjacent owning test files.

### `compare_attribution_models.py`

Source: `modules/mta_attribution/src/compare_attribution_models.py`

Read the Markov and Shapley model files strictly and publish comparison, summary and recommendation files. `compare_model_files(...)` accepts model paths and output destinations. Missing or malformed columns fail instead of silently filling values; model ordering and reliability rules are those of the comparison contract.

Run from the repository root with `uv run python -X utf8 -B -m modules.mta_attribution.src.compare_attribution_models`.
Dependencies are the owning attribution modules and Python standard library;
package imports do not modify `sys.path`. Verification uses the existing
`modules/mta_attribution/tests/test_end_to_end_pipeline.py` suite, with window,
key and comparison cases in the adjacent owning test files.

### `run_attribution_models.py`

Source: `modules/mta_attribution/src/run_attribution_models.py`

Run the existing attribution models over supplied path and performance reports. `run_attribution_models(...)` loads reports and writes the five governed model/comparison artifacts; `main()` parses the documented overrides. Inputs, field ordering and rounding follow the model and output contracts linked above.

Run from the repository root with `uv run python -X utf8 -B -m modules.mta_attribution.src.run_attribution_models`.
Dependencies are the owning attribution modules and Python standard library;
package imports do not modify `sys.path`. Verification uses the existing
`modules/mta_attribution/tests/test_end_to_end_pipeline.py` suite, with window,
key and comparison cases in the adjacent owning test files.

### `run_pipeline.py`

Source: `modules/mta_attribution/src/run_pipeline.py`

Derive the observed report window, validate inputs, run path building and attribution, then publish all six artifacts together. `run_pipeline(...)` accepts optional input/output paths and a report window; `parse_args()` supplies the command interface. Stage complete outputs first and restore earlier files on publication failure.

Run from the repository root with `uv run python -X utf8 -B -m modules.mta_attribution.src.run_pipeline`.
Dependencies are the owning attribution modules and Python standard library;
package imports do not modify `sys.path`. Verification uses the existing
`modules/mta_attribution/tests/test_end_to_end_pipeline.py` suite, with window,
key and comparison cases in the adjacent owning test files.

### `validate_data_alignment.py`

Source: `modules/mta_attribution/src/validate_data_alignment.py`

Validate the event/performance interface without publishing outputs. `validate_data_alignment_rows(amc_rows, ads_rows)` returns the reconciled scope or raises on invalid columns, keys, windows, billing or totals. `infer_ads_report_window(...)` derives a contiguous daily window from actual report dates. The command prints the validation result.

Run from the repository root with `uv run python -X utf8 -B -m modules.mta_attribution.src.validate_data_alignment`.
Dependencies are the owning attribution modules and Python standard library;
package imports do not modify `sys.path`. Verification uses the existing
`modules/mta_attribution/tests/test_end_to_end_pipeline.py` suite, with window,
key and comparison cases in the adjacent owning test files.

### `regenerate_simulated_dataset.py`

Source: `modules/mta_attribution/src/regenerate_simulated_dataset.py`

Reproduce the historical synthetic fixture and all dependent artifacts. `regenerate(destinations=None)` uses fixed templates, validates every derived file and publishes the ten-file set with rollback. Default destinations are the committed sample locations; repeat runs over unchanged inputs produce identical bytes.

Run from the repository root with `uv run python -X utf8 -B -m modules.mta_attribution.src.regenerate_simulated_dataset`.
Dependencies are the owning attribution modules and Python standard library;
package imports do not modify `sys.path`. Verification uses the existing
`modules/mta_attribution/tests/test_end_to_end_pipeline.py` suite, with window,
key and comparison cases in the adjacent owning test files.
