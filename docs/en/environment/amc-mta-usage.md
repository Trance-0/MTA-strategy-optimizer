---
title: AMC MTA Usage
lang: en-US
---

# AMC MTA Usage

Run all commands below from the repository root. See the [data contract](../datasets/amc-data-contract.md) for field and path rules. This module is for attribution analysis only; it does not allocate budgets or optimize activation.

## Run

Complete pipeline:

```bash
uv run python -X utf8 -B script/run_pipeline.py
```

Replace only the events and Amazon Ads input files, then run the command again. The canonical pipeline automatically uses the earliest through latest Ads `reportDate` as its window; `config.py` does not need to be changed. The path report and all five model outputs are completed and validated in a temporary directory before being published together. If input validation fails, no valid paths exist, or publishing fails, the six existing derived artifacts remain unchanged. The program never overwrites raw inputs.

Use custom input and output locations:

```bash
uv run python -X utf8 -B script/run_pipeline.py \
  --events-file path/to/amc_touchpoint_events.csv \
  --amazon-ads-report path/to/amazon_ads_report.csv \
  --path-report path/to/amc_path_report.csv \
  --output-dir path/to/attribution_outputs
```

Build only the aggregated paths:

```bash
uv run python -X utf8 -B script/build_path_report.py
```

This command also detects its window from the Ads input by default. Override any file path separately when necessary:

```bash
uv run python -X utf8 -B script/build_path_report.py \
  --events-file path/to/amc_touchpoint_events.csv \
  --amazon-ads-report path/to/amazon_ads_report.csv \
  --output-file path/to/amc_path_report.csv
```

Atomically rebuild all ten simulated and attribution artifacts from the same user-event master table:

```bash
uv run python -X utf8 -B script/regenerate_simulated_dataset.py
```

You can run `script/generate_simulated_synthetic_user_events.py`, `script/generate_simulated_amc_touchpoint_events.py`, `script/generate_simulated_amazon_ads_report.py`, or `script/generate_simulated_touchpoint_entity_aggregate.py` separately to inspect an individual legacy data layer. These compatibility commands reproduce the committed five-segment fixture. New synthetic datasets should use the pinned ZheyuanWu command documented in [Generate MTA-SIM data](mta-sim-generation.md).

Run attribution only on an existing aggregated path report:

```bash
uv run python -X utf8 -B script/run_attribution_models.py
```

Strictly recompute the three comparison artifacts from existing Markov/Shapley files:

```bash
uv run python -X utf8 -B script/compare_attribution_models.py
```

This command removes leading and trailing whitespace from field names and values while preserving spaces inside strings. Empty or duplicate headers after cleanup, missing or extra columns, schema mismatches, invalid model names, inconsistent touchpoint sets, non-finite values, negative values, or non-conserving shares/attribution values still raise errors immediately.

Optional parameters:

```bash
uv run python -X utf8 -B script/run_attribution_models.py \
  --amc-report path/to/report.csv \
  --amazon-ads-report path/to/amazon_ads_report.csv \
  --output-dir path/to/output
```

Validate the window, account, currency, touchpoint set, and daily coverage of five-segment interactions across AMC and Amazon Ads:

```bash
uv run python -X utf8 -B script/validate_data_alignment.py
```

## Default Inputs and Outputs

Inputs are under `modules/mta_attribution/data/simulated/`; see [AMC MTA simulated data](../datasets/amc-simulated-data.md) for each file's role.

Each run accepts exactly one marketplace, account, and currency scope. Ads data must be non-empty, dates must be continuous, the same five-segment touchpoint set must appear every day, and date/key combinations must be unique. Events must contain conversions; all conversions must fall inside the Ads window and yield at least one valid path. Violations raise an error immediately: the program does not crop, zero-fill, or publish. Every CSV input consistently ignores leading and trailing whitespace in field names and values while preserving spaces inside strings. The five canonical outputs continue to use a normalized physical format without leading or trailing whitespace.

```text
modules/mta_attribution/outputs/attribution/amc_markov_attribution_results.csv
modules/mta_attribution/outputs/attribution/amc_shapley_attribution_results.csv
modules/mta_attribution/outputs/attribution/amc_mta_model_comparison_touchpoints.csv
modules/mta_attribution/outputs/attribution/amc_mta_model_comparison_summary.csv
modules/mta_attribution/outputs/attribution/amc_mta_recommended_attribution.csv
```

Both result files use the five-segment `AD_PRODUCT:FORMAT:PLACEMENT:CREATIVE:INTERACTION_TYPE` granularity and contain `interaction_type`, all three sets of attribution values, Amazon Ads performance and cost, `roas`, `roi`, `cpa`, and `cost_per_converted_user`. Cost per click (CPC) cost appears only on CLICK rows, and cost per mille (CPM) cost only on IMPRESSION rows; costs and efficiency metrics on non-billable rows are 0/empty.

The touchpoint-comparison file has a fixed 14-column schema and `17 × 3 = 51` rows. It stores only the two model shares, `gap_pp`, `relative_gap`, the three raw support values, and reliability. The summary has a fixed 13-column schema with one row for each of the three Outcomes. It stores the window, touchpoint count, total variation distance (TVD), Spearman correlation, Top-K overlap, and reliability. The recommendation file has a fixed 15-column schema and 51 rows; it stores the official Markov display value, Shapley reference value, final recommended value, gap, and reliability. All three artifacts include `calculation_valid`, `data_support_sufficient`, `models_consistent`, `reliability_status`, and `reliability_reason`; neither single-model result contains these fields. A row is `RELIABLE` only when all three Boolean values are `true`. For each Outcome, the summary aggregates each Boolean with an AND over all touchpoints. Markov is the official displayed attribution, while Shapley is used to judge model sensitivity. Legacy cost, efficiency, gap-grade, and status fields do not belong to these three dual-model schemas.

`recommended_value` is a textual union type. For a nonzero Outcome, a `RELIABLE` row contains the single `official_share`; an `UNRELIABLE` row contains an ascending closed interval of the two model shares, `[low,high]`. It is empty for a zero Outcome. If both shares are zero under a nonzero Outcome, `[0.0,0.0]` is a valid interval.

The current 90-day sample contains `51 RELIABLE / 0 UNRELIABLE`. Results can only be interpreted as exploratory attribution within the current window; they must not be used to adjust budgets automatically.

For how to decide whether attribution for one touchpoint is reliable and how to interpret it, see [Single-touchpoint attribution reliability](../attribution/reliability.md).
