---
title: Standardized MTA Interface
description: The framework boundary between mta_standard and the concrete models in mta_attribution
lang: en-US
---

# Standardized MTA Interface

## What This Layer Solves <span class="status-label status-verified" aria-label="Verified"></span>

Before this layer existed, running an attribution model against MTA-SIM data meant hand-editing paths, guessing an interaction type, and comparing results that had no common schema. The framework in `modules/mta_standard/` closes that gap, while the model interface and every concrete attribution implementation remain in their owning `modules/mta_attribution/` package.

This split lets contributors work on loading, execution, individual models, evaluation, and strategy recommendation independently. Package imports express the dependency directly; reusable modules do not edit `sys.path`.

| Component | File | Objective |
| --- | --- | --- |
| Generator adapter | `src/mta_sim_generator_adapter.py` | Run the pinned ZheyuanWu generator, aggregate daily scopes, and load model inputs |
| Key adapter | `src/touchpoint_adapter.py` | Convert between MTA-SIM's four-segment key and this repository's five-segment key |
| Dataloader | `src/dataloader.py` | Load `amc_path_report` and `amazon_ads_daily_touchpoint_performance` from any path |
| Model interface | `modules/mta_attribution/src/attribution_model_interface.py` | Define `fit`/`attribute`/`save`/`load` and capability metadata |
| Markov standard model | `modules/mta_attribution/src/markov_standard_attribution_model.py` | Adapt the existing Markov estimator to the shared contract |
| Shapley standard model | `modules/mta_attribution/src/shapley_standard_attribution_model.py` | Adapt the existing Shapley estimator to the shared contract |
| Uniform model | `modules/mta_attribution/src/uniform_attribution_model.py` | Provide the equal-credit reference baseline |
| DNN model | `modules/mta_attribution/src/dnn_attribution_model.py` | Provide the learned model and new-campaign prediction |
| Generator adapter | `modules/mta_standard/src/mta_sim_generator_adapter.py` | Run the pinned generator and load its outputs |
| Key adapter | `modules/mta_standard/src/touchpoint_adapter.py` | Resolve the four-to-five segment boundary |
| Dataloader | `modules/mta_standard/src/dataloader.py` | Load MTA-SIM tables from explicit paths |
| Model registry | `modules/mta_standard/src/model_registry.py` | Expose shipped models without implementing them |
| Model pipeline | `modules/mta_standard/src/model_pipeline.py` | Execute registered models and validate their outputs |
| Output contract | `modules/mta_standard/src/output_contract.py` | Define the standard row and validate its four invariants |
| Evaluator | `modules/mta_standard/src/evaluation.py` | Load ground truth and score models against it |

## Ground-Truth Isolation Is Structural <span class="status-label status-verified" aria-label="Verified"></span>

`simulation_ground_truth` is valid only for the synthetic mechanism and is prohibited as a training feature. That rule is enforced by types rather than by convention:

- `MtaSimDataset` has no field that can hold ground truth.
- `load_mta_sim_dataset()` accepts no ground-truth path — its only parameters are `path_report`, `ads_performance`, and `config`.
- `load_simulation_ground_truth()` lives in `evaluation` and returns a `GroundTruth`, which no loader, dataset, or model accepts.
- Both model-facing loaders reject a table whose header contains `normalized_touchpoint`, `causal_increment`, `credit_share`, or `expected_conversion_probability`.
- `fit(dataset)` and `attribute(dataset)` take exactly one argument, so there is no parameter through which ground truth could arrive.

A model cannot read the answer because there is no expressible way to hand it over.

## Four-Segment to Five-Segment Adaptation <span class="status-label status-verified" aria-label="Verified"></span>

MTA-SIM normalizes a touchpoint into four segments; this repository adds `INTERACTION_TYPE` as a fifth. The two are not interchangeable, and `IMPRESSION` versus `CLICK` cannot be recovered from the four-segment data. Adaptation therefore happens only at the loading and output boundary, driven by an explicit simulator configuration.

| Representation | Key |
| --- | --- |
| MTA-SIM, four segments | `AD_PRODUCT:FORMAT:PLACEMENT:CREATIVE` |
| This repository, five segments | `AD_PRODUCT:FORMAT:PLACEMENT:CREATIVE:INTERACTION_TYPE` |

The configuration maps a billing cost type onto the missing segment:

| Simulator `cost_type` | Fifth segment |
| --- | --- |
| `CPC` | `CLICK` |
| `CPM` | `IMPRESSION` |

```python
config = SimulatorConfig.from_mapping({                              # 1
    "AMAZON_DSP:OTT:UNSPECIFIED:VIDEO": "CPM",                       # 2
    "SPONSORED_PRODUCTS:PRODUCT_AD:TOP_OF_SEARCH:UNSPECIFIED": "CPC",# 3
})
five = config.to_five_segment("AMAZON_DSP:OTT:UNSPECIFIED:VIDEO")    # 4
four = to_four_segment(five)                                         # 5
```

| Line | Detailed step | Reason |
| --- | --- | --- |
| 1 | Canonicalize every key and value up front | A configuration error must fail at construction, not midway through a report |
| 2-3 | State one cost type per four-segment touchpoint | The interaction type is never inferred from impression or click counts, which would silently invent a contract |
| 4 | Expand to the five-segment key the existing models require | The wrapped algorithms keep operating in their own grain |
| 5 | Reduce back to four segments for standard output | Everything outside the boundary sees MTA-SIM's grain |

Three configuration failures are rejected rather than guessed:

| Failure | Example | Behaviour |
| --- | --- | --- |
| Missing | A path contains a touchpoint absent from the configuration | `ValueError: missing simulator cost_type mapping for touchpoint …` |
| Ambiguous | A cost type other than exactly `CPC` or `CPM` | `ValueError: simulator cost_type for … must be one of CPC, CPM` |
| Colliding | Two spellings canonicalize to the same key | `ValueError: colliding simulator cost_type mapping; …` |

`SimulatorConfig.assert_reversible()` additionally proves, for the touchpoints a dataset actually contains, that four → five → four is the identity and that no two four-segment keys expand to the same five-segment key. A dataset that passes can round-trip without losing information.

## Loading a Dataset <span class="status-label status-verified" aria-label="Verified"></span>

For the maintained generation path, initialize the submodule and run:

```sh
git submodule update --init --recursive
uv run python -X utf8 -B script/generate_mta_sim_dataset.py
```

The generator adapter derives CPC/CPM from the resolved ZheyuanWu configuration rather than from observed delivery metrics. It preserves the original daily-window CSVs, aggregates path rows into the single reporting scope required by the local model interface, and keeps the normalized ground-truth view separate for evaluation. See [Generate MTA-SIM data](../../environment/mta-sim-generation.md).

Both loaders take explicit paths and apply no repository-relative default, so a dataset generated anywhere on the filesystem works unchanged:

```python
dataset = load_mta_sim_dataset(
    "/data/mta-sim/amc_path_report.csv",
    "/data/mta-sim/amazon_ads_daily_touchpoint_performance.csv",
    config=config,
)
```

| Table | Role in this layer |
| --- | --- |
| `amc_path_report` | Required. Adapted to five segments and validated against the existing aggregated-path contract |
| `amazon_ads_daily_touchpoint_performance` | Optional. Validated and annotated, then kept for diagnostics and reporting |
| `simulation_ground_truth` | Never loaded here. See [Evaluation](#evaluating-against-ground-truth) |

The performance table stays out of the model-facing rows because the standard output carries no spend or efficiency column. Its `unitsSold` field is preserved verbatim as an optional diagnostic rather than being forced into a mapping, and its stored `normalizedTouchpoint` is checked against the key derived from its own component columns.

## The Model Interface <span class="status-label status-verified" aria-label="Verified"></span>

Every model declares identity and capabilities as class attributes, so a caller can compare models without instantiating them.

```python
class MtaAttributionModel(ABC):
    model_id: ClassVar[str]
    model_version: ClassVar[str]
    capabilities: ClassVar[ModelCapabilities]

    def fit(self, dataset) -> "MtaAttributionModel": ...
    def attribute(self, dataset) -> list[StandardAttributionRow]: ...
    def save(self, path) -> Path: ...
    @classmethod
    def load(cls, path) -> "MtaAttributionModel": ...
```

`ModelCapabilities` reports `requires_fit`, `supports_persistence`, `deterministic`, `supported_outcomes`, and `grain`. A model that declares `supports_persistence=False` raises `NotImplementedError` from `save`/`load` rather than pretending to round-trip, and a model that declares `requires_fit=True` refuses to attribute before `fit`, or after being fitted on a different report scope.

| `model_id` | Version | Requires fit | Persists | Basis |
| --- | --- | --- | --- | --- |
| `markov_removal_effect` | 1.0.0 | No | Yes | Wraps `run_markov_attribution` |
| `path_level_shapley` | 1.0.0 | No | Yes | Wraps `run_shapley_attribution` |
| `uniform_credit` | 1.0.0 | Yes | No | Equal split; reference baseline |
| `dnn_credit` | 1.0.0 | Yes | Yes | Learned network; see [DNN credit model](./dnn.md) |

## Choosing a Model <span class="status-label status-verified" aria-label="Verified"></span>

Start with the question you need to answer, not with the algorithm:

::: tip Model selection guide
- **Which touchpoints contributed most to conversions?** → [Markov removal effect](./markov.md)
- **How sensitive is the result to the model choice?** → Run both [Markov](./markov.md) and [Shapley](./shapley.md), then compare
- **What share would a new campaign likely receive?** → [DNN credit model](./dnn.md) (the only model that predicts without path history)
- **Is any of the above meaningful at all?** → Compare against the [uniform credit baseline](./uniform.md)
:::

| Task | Recommended model | Fallback |
| --- | --- | --- |
| Official display and reporting | [Markov](./markov.md) | [Shapley](./shapley.md) interval |
| Sensitivity analysis | [Shapley](./shapley.md) | Compare with [Markov](./markov.md) |
| New campaign without path data | [DNN](./dnn.md) | [Uniform](./uniform.md) baseline |
| Baseline / null hypothesis | [Uniform](./uniform.md) | N/A — it is the floor |
| Understanding model internals | [Markov](./markov.md) (transition network) | [Shapley](./shapley.md) (coalition game) |

The two wrappers perform no arithmetic of their own. They forward the five-segment path rows to the existing estimators and relabel the results, so removal effects, convergence thresholds, and Shapley coalition values are bit-identical to a direct call. A regression test asserts exactly that, and pins the fixture's expected values so a change to the underlying mathematics fails loudly.

Instantiate by identifier:

```python
from modules.mta_standard.src.model_registry import MODEL_REGISTRY, build_model

for model_id in MODEL_REGISTRY:
    rows = build_model(model_id).fit(dataset).attribute(dataset)
```

## The Standard Output Row <span class="status-label status-verified" aria-label="Verified"></span>

Every model emits the same row, at MTA-SIM's four-segment grain:

| Field | Meaning |
| --- | --- |
| `model_id`, `model_version` | Which model and contract version produced the row |
| `report_start_date`, `report_end_date` | Report scope |
| `marketplace` | Advertising marketplace |
| `touchpoint` | Canonical four-segment key |
| `outcome` | `converted_users`, `purchase_count`, or `revenue` |
| `attribution_share` | Share of the outcome credited to the touchpoint |
| `attributed_value` | Absolute outcome credited to the touchpoint |
| `valid` | Whether the producing model considers the row usable |
| `warnings` | Ordered warning codes, pipe-separated |

`validate_standard_output()` enforces four invariants:

| Invariant | Rule | Tolerance |
| --- | --- | --- |
| Non-negativity | Shares and values are finite and `>= 0` | Exact |
| Uniqueness | One row per model, version, scope, marketplace, touchpoint, and outcome | Exact |
| Share conservation | Shares sum to 1 per model/scope/outcome | `1e-6` absolute |
| Outcome conservation | Attributed values sum to the observed outcome total | `1e-6` absolute, plus `1e-9` relative |

An outcome whose observed total is zero is a deliberate special case: its shares must sum to **zero**, not one, and every row must carry the `ZERO_OUTCOME_TOTAL` warning. Redistributing credit for an outcome that never occurred would manufacture attribution from nothing, so the validator rejects it.

## Evaluating Against Ground Truth <span class="status-label status-verified" aria-label="Verified"></span>

`evaluation` is the only module that opens `simulation_ground_truth`.

MTA-SIM publishes ground truth at the path × touchpoint grain and does not state whether `credit_share` is normalized per path or per report. The loader therefore applies one deterministic rule in both cases: sum `credit_share` per touchpoint, then divide by the total across touchpoints. When the table already holds one normalized row per touchpoint, that rule is the identity.

```python
ground_truth = load_simulation_ground_truth(path, scope=dataset.scope)
reports = compare_models(
    [build_model(model_id) for model_id in sorted(MODEL_REGISTRY)],
    dataset,
    ground_truth,
)
```

| Metric | Definition |
| --- | --- |
| `credit_share_mae` | Mean absolute error against ground-truth credit shares |
| `credit_share_rmse` | Root mean squared error of the same differences |
| `total_variation_distance` | Half the L1 distance between the two share vectors |
| `spearman_rho` | Rank correlation; `None` when undefined, such as a constant vector |
| `top_k_overlap` | Overlap rate of the leading `k` touchpoints, `k` capped by the touchpoint count |
| `conservation_error` | Deviation of the model's share sum from its required total |
| `runtime_seconds` | Wall-clock duration of the model's `attribute` call |

Model and ground-truth touchpoints are aligned on their **union**, with an absent touchpoint scored as a zero share. A model that omits a touchpoint is therefore penalized by the metrics rather than silently excused from it, and `missing_in_model` / `missing_in_ground_truth` report the discrepancy explicitly.

## Running the Tests <span class="status-label status-verified" aria-label="Verified"></span>

```bash
python -X utf8 -B -m unittest discover -s modules/mta_standard/tests -t . -p 'test_*.py'
```

The suite is deterministic and writes every fixture to a temporary directory outside the repository, which is how it proves the loaders do not depend on repository location.

## Boundaries <span class="status-label status-inference" aria-label="Inference"></span>

- The standardized layer changes no attribution mathematics; it changes how a model is loaded, called, validated, and scored.
- Ground-truth agreement measures whether a method recovers a known synthetic mechanism. It is not evidence about real-world advertising causality.
- The performance table is a diagnostic input here. Cost, ROAS, and reliability governance remain the responsibility of the existing [model comparison governance](../model-governance.md).

## References

- [Datasets and the MTA-SIM contract](../../datasets/index.md)
- [Markov removal effect](./markov.md)
- [Path-level Shapley](./shapley.md)
- [DNN credit model](./dnn.md)
