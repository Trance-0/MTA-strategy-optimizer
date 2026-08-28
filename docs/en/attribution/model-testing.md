---
title: Model Testing and Comparison
description: How each attribution model is tested, and how the four are compared against each other
compact: "Attribution assurance layers: shared model conformance, per-run Markov versus Shapley governance, evaluation against simulation_ground_truth, and the generator adapter that preserves uploads while producing one aggregated model path scope for pipeline execution."
lang: en-US
source_files: modules/mta_standard/src/evaluation.py, modules/mta_standard/src/mta_sim_generator_adapter.py
---

# Model Testing and Comparison

Four models ship in this repository. This page explains how each one is verified in isolation, how two of them are compared in production, and how all four are scored against a known answer.

## `markov_removal_effect`

- Implementation: `mta_attribution/src/markov_standard_attribution_model.py`
- Compared in production: Yes — official basis
- Scored against ground truth: Yes

## `path_level_shapley`

- Implementation: `mta_attribution/src/shapley_standard_attribution_model.py`
- Compared in production: Yes — sensitivity reference
- Scored against ground truth: Yes

## `uniform_credit`

- Implementation: `mta_attribution/src/uniform_attribution_model.py`
- Compared in production: No
- Scored against ground truth: Yes — baseline

## `dnn_credit`

- Implementation: `mta_attribution/src/dnn_attribution_model.py`
- Compared in production: No
- Scored against ground truth: Yes

## Three Layers of Assurance <span class="status-label status-verified" aria-label="Verified"></span>

The three layers answer different questions, and none substitutes for another.

<DrawioDiagram base="./model-testing-layers" alt="Three layers of model assurance" />

### Unit and contract

- Question: Is one model internally correct and conserving?
- Where it runs: `modules/*/tests/`
- Needs ground truth: No

### Governance comparison

- Question: Do Markov and Shapley agree enough to publish a point estimate?
- Where it runs: Every pipeline run
- Needs ground truth: No

### Ground-truth evaluation

- Question: Does a model recover the simulator's mechanism?
- Where it runs: On demand, MTA-SIM data
- Needs ground truth: Yes

> [!IMPORTANT]
> Layer 2 runs on **every** pipeline run because it gates what gets published. Layer 3 cannot: real reports have no ground truth. That is why reliability governance is built on cross-model agreement rather than on accuracy.

---

## Layer 1 — Unit and Contract Tests <span class="status-label status-verified" aria-label="Verified"></span>

284 deterministic tests, no third-party runner, and no runtime network access after the submodule is initialized.

### `mta_attribution/tests/test_attribution_contract.py`

- Tests: 18
- Focus: Result shaping, spend aggregation, conservation-preserving rounding, row adapters, and both models' removal-effect and coalition behaviour

### `mta_attribution/tests/test_path_report_builder.py`

- Tests: 24
- Focus: Window boundaries, gap rules, journey segmentation

### `mta_attribution/tests/test_attribution_model_comparison.py`

- Tests: 29
- Focus: Reliability contract, gap metrics, atomic publication and rollback

### `mta_attribution/tests/test_auto_report_window.py`

- Tests: 8
- Focus: Window inferred from Ads data, never from config

### `mta_attribution/tests/test_touchpoint_key.py`

- Tests: 6
- Focus: Key component rules and data alignment

### `mta_attribution/tests/test_end_to_end_pipeline.py`

- Tests: 22
- Focus: Byte-reproducible dataset, six-artifact atomicity, outcome conservation

### `mta_standard/tests/test_touchpoint_adapter.py`

- Tests: 23
- Focus: Four ↔ five segment reversibility, rejected mappings

### `mta_standard/tests/test_dataloader.py`

- Tests: 21
- Focus: External paths, header validation, ground-truth isolation

### `mta_attribution/tests/test_attribution_model_interface.py`

- Tests: 17
- Focus: Interface conformance and the standard-model regression guarantee

### `mta_attribution/tests/test_markov_standard_attribution_model.py`

- Tests: 1
- Focus: Markov adapter ownership and standard output

### `mta_attribution/tests/test_shapley_standard_attribution_model.py`

- Tests: 1
- Focus: Shapley adapter ownership and standard output

### `mta_attribution/tests/test_uniform_attribution_model.py`

- Tests: 1
- Focus: Uniform baseline ownership and standard output

### `mta_standard/tests/test_output_contract.py`

- Tests: 22
- Focus: The four output invariants and the zero-outcome rule

### `mta_standard/tests/test_evaluation.py`

- Tests: 20
- Focus: Ground-truth grains, metric bounds, determinism

### `mta_attribution/tests/test_dnn_attribution_model.py`

- Tests: 33
- Focus: Features, unknown bucket, convergence, persistence

### `mta_standard/tests/test_model_pipeline.py`

- Tests: 2
- Focus: Registry-driven execution and immutable run collection

### `mta_standard/tests/test_mta_sim_generator_adapter.py`

- Tests: 2
- Focus: Pinned generator invocation and adapted output

### `mta_strategy_recommendation/tests/test_hierarchy_validator.py`

- Tests: 34
- Focus: Lineage, capacity, budget split, output boundary

Run them:

```bash
python -X utf8 -B -m unittest discover -s modules/mta_attribution/tests -t . -p 'test_*.py'
python -X utf8 -B -m unittest discover -s modules/mta_standard/tests -t . -p 'test_*.py'
python -X utf8 -B -m unittest discover -s modules/mta_strategy_recommendation/tests -t . -p 'test_*.py'
```

One file at a time:

```bash
python -X utf8 -B -m unittest discover \
  -s modules/mta_attribution/tests \
  -p 'test_dnn_attribution_model.py' \
  -t .
```

> [!TIP]
> Use `-t .` so `unittest` imports tests and runtime code through their repository package paths.

### The wrapper regression guarantee

The most load-bearing test asserts that standardizing a model changed none of its numbers:

```python
def test_markov_matches_a_direct_call_exactly(self) -> None:
    standard = self._standard_shares(MarkovRemovalEffectModel())
    for result in run_markov_attribution(list(self.dataset.path_rows)):
        for outcome in SUPPORTED_OUTCOMES:
            share_field, value_field = OUTCOME_FIELDS[outcome]
            row = standard[(result.touchpoint, outcome)]
            self.assertEqual(row.attribution_share, getattr(result, share_field))
            self.assertEqual(row.attributed_value, getattr(result, value_field))
```

Note `assertEqual`, not `assertAlmostEqual`. The wrapper forwards and relabels; it computes nothing, so exact float equality is the correct assertion.

A second test pins the fixture's expected values:

```python
EXPECTED_MARKOV_CONVERTED_USER_SHARES = {
    fixtures.DISPLAY: 0.36666666666666664,
    fixtures.BRAND:   0.1666666666666667,
    fixtures.SEARCH:  0.46666666666666673,
}
```

> [!NOTE]
> The two tests catch different failures. The first catches a **wrapper** that alters results; the second catches a change to the **model mathematics** itself. Without the pinned values, editing the Markov solver would still pass, because the wrapper would faithfully reproduce the new, wrong number.

---

## Layer 2 — Governance Comparison <span class="status-label status-verified" aria-label="Verified"></span>

`attribution_model_comparison.py` compares Markov against Shapley on every pipeline run and decides whether a point estimate can be published.

```bash
uv run python -X utf8 -B script/run_pipeline.py
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
uv run python -X utf8 -B script/compare_attribution_models.py \
  --markov-file  modules/mta_attribution/outputs/attribution/amc_markov_attribution_results.csv \
  --shapley-file modules/mta_attribution/outputs/attribution/amc_shapley_attribution_results.csv \
  --amc-report   modules/mta_attribution/data/simulated/amc_mta_path_report_raw_sample.csv \
  --output-dir   /tmp/comparison
```

> [!WARNING]
> Agreement is not accuracy. Two models built on the same observational paths can agree closely and still both be wrong about causal contribution. `RELIABLE` means "safe to publish as a point estimate", not "correct".

---

## Layer 3 — Ground-Truth Evaluation <span class="status-label status-verified" aria-label="Verified"></span>

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

## Adding a Model to the Comparison <span class="status-label status-verified" aria-label="Verified"></span>

A new model joins all three layers by satisfying one interface and being registered.

1. Implement `MtaAttributionModel` — `fit`, `attribute`, and a `ModelCapabilities` declaration.
2. Add it to `MODEL_REGISTRY` in `model_registry.py`.
3. Nothing else. The interface, output-contract, and evaluation suites iterate the registry, so the new model is immediately covered by every registry-driven test.

```python
for model_id in MODEL_REGISTRY:
    rows = build_model(model_id).fit(dataset).attribute(dataset)
    validate_standard_output(
        rows,
        outcome_totals=dataset.outcome_totals,
        expected_touchpoints=dataset.touchpoints,
    )
```

> [!TIP]
> Registry-driven tests are why `dnn_credit` required no new conformance tests when it was added. Write tests for what is unique about a model; the shared contract is already enforced for everything registered.

## Source Files <span class="status-label status-verified" aria-label="Verified"></span>

The code-level specification for the Python files this page describes. Each entry states responsibility, inputs, outputs, dependencies, and the test that verifies it.

### `evaluation.py`

Source: `modules/mta_standard/src/evaluation.py`

- Responsibility: Load simulation ground truth separately and score standard model output.
- Inputs: Standard rows and evaluation-only ground truth.
- Outputs: Error, rank, overlap, conservation, and runtime metrics.
- Dependencies: Dataloader scope, native touchpoint-key validation, output contract, attribution Spearman calculation, `read_csv_normalized` from `attribution_contract.py`, and `MtaAttributionModel` from `attribution_model_interface.py`.
- Verification: `modules/mta_standard/tests/test_evaluation.py`.

### `mta_sim_generator_adapter.py`

Source: `modules/mta_standard/src/mta_sim_generator_adapter.py`

- Responsibility: Invoke the pinned ZheyuanWu generator and prepare
  framework-compatible model/evaluation views. Public
  `prepare_single_scope_reports(source_path_report, performance_report,
  destination_path_report, destination_performance_report, marketplace)` also
  partitions and aggregates an existing uploaded daily report without invoking
  the generator. It refuses an ambiguous multi-marketplace upload when no
  marketplace is supplied. Current provider-aware configurations receive their
  matching ProviderCapabilities when compatibility keys are requested;
  historical configuration objects retain the no-argument key path.
- Inputs: Submodule path, configuration, output directory, and generator
  variant; or explicit uploaded path, performance, destination paths, and an
  optional exact marketplace selection.
- Outputs: Generated manifest, model dataset, and evaluation-only ground truth
  path; or deterministic matching single-scope path and performance reports
  that preserve both source uploads.
- Dependencies: External generator, dataloader, and touchpoint adapter.
- Verification: `modules/mta_standard/tests/test_mta_sim_generator_adapter.py`.

## References

- [Standardized MTA interface](./standardized-interface/)
- [Model comparison governance](./model-governance.md)
- [Touchpoint reliability](./reliability.md)
- [Module and script data flow](../reference/data-flow.md)
