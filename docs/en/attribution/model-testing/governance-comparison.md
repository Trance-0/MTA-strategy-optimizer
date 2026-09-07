---
title: "Layer 2 — Governance Comparison"
compact: "Per-run Markov and Shapley agreement, reliability thresholds and publication behavior."
---

# Layer 2 — Governance Comparison

`attribution_model_comparison.py` compares Markov against Shapley on every pipeline run and decides whether a point estimate can be published.

```bash
uv run python -X utf8 -B -m modules.mta_attribution.src.run_pipeline
```

Three artifacts result:

### `amc_mta_model_comparison_touchpoints.csv`

- Grain: Touchpoint × outcome

### `amc_mta_model_comparison_summary.csv`

- Grain: Outcome

### `amc_mta_recommended_attribution.csv`

- Grain: Touchpoint × outcome, with the value to use

Current shipped sample:

### `converted_users`

- Touchpoints: 17
- Total Variation Distance (TVD): 0.019451
- Spearman's Rho (ρ): 0.889025305
- Top-K overlap: 0.6
- Reliability: `RELIABLE`

### `purchase_count`

- Touchpoints: 17
- Total Variation Distance (TVD): 0.019750
- Spearman's Rho (ρ): 0.911097657
- Top-K overlap: 0.6
- Reliability: `RELIABLE`

### `revenue`

- Touchpoints: 17
- Total Variation Distance (TVD): 0.020585
- Spearman's Rho (ρ): 0.931372549
- Top-K overlap: 0.8
- Reliability: `RELIABLE`

Reliability requires all three criteria:

### `calculation_valid`

- Threshold: Conservation and efficiency checks passed

### `data_support_sufficient`

- Threshold: ≥30 purchases, ≥20 converted users, ≥5 unique paths

### `models_consistent`

- Threshold: Gap ≤1.0 pp **and** relative gap ≤0.20

> [!IMPORTANT]
> When a touchpoint is unreliable, `recommended_value` becomes the **interval** between the two model shares, written as `[low,high]`, instead of the Markov point estimate. Publishing a single number would hide a disagreement the data cannot resolve.

To re-compare two stored model CSVs without re-running attribution:

```bash
uv run python -X utf8 -B -m modules.mta_attribution.src.compare_attribution_models \
  --markov-file  modules/mta_attribution/outputs/attribution/amc_markov_attribution_results.csv \
  --shapley-file modules/mta_attribution/outputs/attribution/amc_shapley_attribution_results.csv \
  --amc-report   modules/mta_attribution/data/simulated/amc_mta_path_report_raw_sample.csv \
  --output-dir   /tmp/comparison
```

> [!WARNING]
> Agreement is not accuracy. Two models built on the same observational paths can agree closely and still both be wrong about causal contribution. `RELIABLE` means "safe to publish as a point estimate", not "correct".

---
