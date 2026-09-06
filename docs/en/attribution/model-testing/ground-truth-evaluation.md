---
title: "Layer 3 — Ground-Truth Evaluation"
compact: "Isolated simulator truth and standard credit error, rank, overlap, conservation and runtime metrics."
source_files: modules/mta_standard/src/evaluation.py
test_files: modules/mta_standard/tests/test_evaluation.py
---

# Layer 3 — Ground-Truth Evaluation

`evaluation.py` scores any registered model against MTA-SIM's `simulation_ground_truth`, under identical conditions.

```python
from modules.mta_standard.src.dataloader import load_mta_sim_dataset
from modules.mta_standard.src.evaluation import compare_models, load_simulation_ground_truth
from modules.mta_standard.src.model_registry import MODEL_REGISTRY, build_model
from modules.mta_standard.src.touchpoint_adapter import SimulatorConfig

config = SimulatorConfig.from_mapping({
    "AMAZON_DSP:OTT:UNSPECIFIED:VIDEO": "CPM",
    "SPONSORED_PRODUCTS:PRODUCT_AD:TOP_OF_SEARCH:UNSPECIFIED": "CPC",
    "SPONSORED_BRANDS:VIDEO_AD:TOP_OF_SEARCH:UNSPECIFIED": "CPC",
})

dataset = load_mta_sim_dataset(
    "/data/mta-sim/amc_path_report.csv",
    "/data/mta-sim/amazon_ads_daily_touchpoint_performance.csv",
    config=config,
)
ground_truth = load_simulation_ground_truth(
    "/data/mta-sim/simulation_ground_truth.csv", scope=dataset.scope
)

for report in compare_models(
    [build_model(model_id) for model_id in sorted(MODEL_REGISTRY)],
    dataset,
    ground_truth,
):
    metrics = report.metrics["converted_users"]
    print(
        f"{report.model_id:24s}"
        f" mae={metrics.credit_share_mae:.6f}"
        f" tvd={metrics.total_variation_distance:.6f}"
        f" rho={metrics.spearman_rho}"
        f" runtime={report.runtime_seconds * 1000:.2f}ms"
    )
```

On the shipped test fixture this produces:

### `dnn_credit`

- Mean Absolute Error (MAE): 0.035294
- Root Mean Squared Error (RMSE): 0.037512
- Total Variation Distance (TVD): 0.052941
- Spearman's Rho (ρ): 1.00
- Top-K overlap: 1.00

### `markov_removal_effect`

- Mean Absolute Error (MAE): 0.044444
- Root Mean Squared Error (RMSE): 0.047140
- Total Variation Distance (TVD): 0.066667
- Spearman's Rho (ρ): 1.00
- Top-K overlap: 1.00

### `path_level_shapley`

- Mean Absolute Error (MAE): 0.035294
- Root Mean Squared Error (RMSE): 0.037512
- Total Variation Distance (TVD): 0.052941
- Spearman's Rho (ρ): 1.00
- Top-K overlap: 1.00

### `uniform_credit`

- Mean Absolute Error (MAE): 0.111111
- Root Mean Squared Error (RMSE): 0.124722
- Total Variation Distance (TVD): 0.166667
- Spearman's Rho (ρ): `None`
- Top-K overlap: 1.00

### `credit_share_mae`

- Meaning: [Mean Absolute Error (MAE)](/en/reference/definitions#mae-mean-absolute-error) against ground-truth shares
- Better: Lower

### `credit_share_rmse`

- Meaning: [Root Mean Squared Error (RMSE)](/en/reference/definitions#rmse-root-mean-squared-error); penalises large single errors
- Better: Lower

### `total_variation_distance`

- Meaning: [Total Variation Distance (TVD)](/en/reference/definitions#tvd-total-variation-distance) — half the L1 distance between share vectors
- Better: Lower

### `spearman_rho`

- Meaning: [Spearman's Rho (ρ)](/en/reference/definitions#spearmans-rho-spearman-rank-correlation-ρ) — rank correlation; `None` when undefined
- Better: Higher

### `top_k_overlap`

- Meaning: [Top-K overlap](/en/reference/definitions#top-k-overlap) — overlap of the leading `k` touchpoints
- Better: Higher

### `conservation_error`

- Meaning: [Conservation error](/en/reference/definitions#conservation-error) — deviation of the share sum from its required total
- Better: Zero

### `runtime_seconds`

- Meaning: Wall-clock duration of `attribute`
- Better: Lower

### Reading that table honestly

> [!CAUTION]
> `dnn_credit` matches `path_level_shapley` exactly because it is **trained on Shapley shares**. Its agreement is not independent corroboration — it is the training objective being met. Treat the pair as one method, not two.

> [!NOTE]
> `uniform_credit` returns `spearman_rho = None` by design. Every share is identical, so there is no ranking to correlate, and reporting `0.0` would imply a measured absence of correlation rather than an undefined one.

> [!TIP]
> `uniform_credit` is the baseline that makes the other numbers meaningful. A model that cannot beat an equal split on MAE has not earned its complexity, whatever its other properties.

Evaluation is deterministic — the same dataset produces byte-identical metrics on every run, which is asserted directly:

```python
def test_metrics_are_deterministic_across_runs(self) -> None:
    first = evaluate_model(build_model("markov_removal_effect"), self.dataset, self.ground_truth)
    second = evaluate_model(build_model("markov_removal_effect"), self.dataset, self.ground_truth)
    self.assertEqual(dict(first.metrics), dict(second.metrics))
```

`runtime_seconds` is excluded from that comparison, being the one value that legitimately varies.

---

## Source Files

### `evaluation.py`

Source: `modules/mta_standard/src/evaluation.py`

- Responsibility: Load simulation ground truth separately and score standard model output.
- Inputs: Standard rows and evaluation-only ground truth.
- Outputs: Error, rank, overlap, conservation, and runtime metrics.
- Dependencies: Dataloader scope, native touchpoint-key validation, output contract, attribution Spearman calculation, `read_csv_normalized` from `attribution_contract.py`, and `MtaAttributionModel` from `attribution_model_interface.py`.
- Verification: `modules/mta_standard/tests/test_evaluation.py`.


## Verification

- **Scope:** The assurance behavior specified on this page.
- **Cases:** Normal, missing, invalid and deterministic outputs; evaluation truth remains isolated.
- **Command:** `uv run python -X utf8 -B -m unittest modules.mta_standard.tests.test_evaluation`.
- **Limitations:** The generator integration requires the pinned checkout; no production database is used.
