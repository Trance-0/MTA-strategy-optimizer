---
title: Evaluation Layers
description: How the current evaluation episode works, and where a new layer attaches to it
compact: "Explains CampaignEpisode to EvaluationEpisode composition isolation and the evaluate_model flow in mta_standard, then specifies StrategyEvaluationEpisode and the three-layer runner in modules/mta_strategy_evaluation/src/evaluation_episode.py. Read before adding an evaluation layer."
lang: en-US
source_files: modules/mta_strategy_evaluation/src/evaluation_episode.py
---

# Evaluation Layers

## Purpose <span class="status-label status-verified" aria-label="Verified"></span>

This page is the one to read before adding an evaluation layer. It explains the mechanism the project already uses to keep ground truth away from the models it scores, then specifies where a new layer attaches to it. The mechanism is worth understanding before extending, because it is structural rather than procedural: the isolation is enforced by which class holds which field, not by a rule that a reviewer has to remember.

## How the Current Episode Works <span class="status-label status-verified" aria-label="Verified"></span>

### The model-facing half

[`CampaignEpisode`](/en/introduction/data-models/composed-episodes-and-evaluation-isolation/campaign-episode.md) in `modules/mta_common/src/episode.py` is one Campaign's record. Its fields split into two groups, and the split is expressed by the field list itself rather than by a flag:

#### Decision-time fields

`campaign` and `budget_constraints` are required and have no default. They were knowable before the budget was committed, so a model may read them when deciding.

#### Observed-after-treatment fields

`budget_observation` defaults to `None`, and `delivery_observations`, `outcome_observations`, and `attribution_evidence` each default to an empty tuple. They exist only after the period ran.

An episode is therefore self-describing: a field that is present was observed, and one that is absent was not. Nothing carries a `RecordClassification` label saying which half it belongs to — that vocabulary is used on [`DataLineage`](/en/introduction/data-models/historical-evidence-and-lineage/data-lineage.md) instead, where a record describes its own provenance. On the episode the split is structural, which is stronger, because a structural split cannot be mislabelled.

`__post_init__` enforces two things across the whole object: every nested record's `campaign_id` matches the episode's own Campaign, and every reachable `ReportingScope` agrees on one currency. Both are cross-object checks that no single nested class could make on its own, which is the reason the composition exists at this level.

### The evaluation-only half

[`EvaluationGroundTruth`](/en/introduction/data-models/composed-episodes-and-evaluation-isolation/evaluation-ground-truth.md) carries what only the simulator knows: `true_incremental_units`, `true_incremental_revenue`, `true_causal_effect`, and `simulator_ground_truth_id`. Those four names are also listed in `FORBIDDEN_MODEL_FACING_FIELDS`, and `assert_no_ground_truth_fields(some_type)` walks any dataclass's fields and raises if one of them appears. That turns the isolation rule into a check a test can run against a class that did not exist when the rule was written.

### The join, and why it is composition

[`EvaluationEpisode`](/en/introduction/data-models/composed-episodes-and-evaluation-isolation/evaluation-episode.md) holds both — but it **holds** a `CampaignEpisode` in a field named `episode` rather than subclassing it:

```python
@dataclass(frozen=True)
class EvaluationEpisode:
    episode: CampaignEpisode
    ground_truth: EvaluationGroundTruth
```

The consequence is the entire point. Had it inherited, an `EvaluationEpisode` would also *be* a `CampaignEpisode`, so it could be passed to any function expecting one, and that function would hold an object with a live attribute path to ground truth — reachable by accident, by a stray `getattr`, or by a serializer that walks every field. With composition, `isinstance(evaluation, CampaignEpisode)` is `False`. Ground truth reaches model-facing code only if a caller deliberately writes `.episode` and passes that, which is a visible act in a diff rather than an invisible one.

The same idea appears twice more in the repository, which is how you can tell it is the project's convention and not a local choice. `build_campaign_response_dataset` raises outright when handed an `EvaluationEpisode`. And `FORBIDDEN_RESPONSE_FEATURES` in `response_dataset.py` blocks a parallel list of names — attribution shares, similarity scores, incremental figures — from being used as response-model features.

### How a model is scored today

`modules/mta_standard/src/evaluation.py` is the attribution layer's scorer and the closest working precedent. Its shape is:

1. `evaluate_model(model, dataset, ground_truth, *, top_k)` receives the model, the data it may see, and the truth it may not.
2. The model is fitted and asked to attribute using `dataset` alone. `ground_truth` is not passed to `fit` or to `attribute` — the module's docstring states this as an invariant.
3. The model's output and `ground_truth` meet for the first time inside the scorer, which computes Mean Absolute Error (MAE), Root Mean Squared Error (RMSE), Total Variation Distance (TVD), Spearman's Rho, and Top-K overlap.
4. `compare_models` runs that for several models and returns one `EvaluationReport` per model.

Ground truth enters at step 3 and never earlier. A new layer should preserve that ordering.

## Where a New Layer Attaches <span class="status-label status-verified" aria-label="Verified"></span>

A strategy evaluation needs one thing the attribution evaluation does not: the *decision*. Attribution scores a model's explanation of what already happened, so the model plus the dataset is enough. A strategy proposes budgets that were never spent, so scoring it requires holding the proposal beside what was observed.

`StrategyEvaluationEpisode` in `modules/mta_strategy_evaluation/src/evaluation_episode.py` is that container, and it follows `EvaluationEpisode`'s design exactly — by composition:

```python
@dataclass(frozen=True)
class StrategyEvaluationEpisode:
    strategy_output: StrategyOutput
    episodes: tuple[CampaignEpisode, ...]
    ground_truth: EvaluationGroundTruth | None = None
```

#### `strategy_output`

The decision under evaluation, as specified in [Strategy Output](./strategy-output.md).

#### `episodes`

The model-facing observations for the same Campaigns and window — what actually happened. These are ordinary `CampaignEpisode` values, so everything already true of them stays true.

#### `ground_truth`

Optional, and `None` for every evaluation this repository can currently run, because the Multi-Touch Attribution Simulator (MTA-SIM) publishes attribution ground truth rather than strategy ground truth. There is no true optimal allocation to compare against. The field exists so the third layer has somewhere to put one when a simulator publishes it, and it is `None` rather than a fabricated value, in the same way [`OutcomeObservation`](/en/introduction/data-models/budget-delivery-and-outcome-observations/outcome-observation.md) leaves incremental figures unset rather than deriving them from totals.

`__post_init__` enforces that every Campaign named in `strategy_output` has at least one episode, and that `strategy_output.scope.currency` matches every episode's currency. Comparing a plan in one currency against observations in another is the failure this prevents.

The class is not a subclass of `EvaluationEpisode`, does not hold one, and carries no ground-truth-shaped field of its own — `assert_no_ground_truth_fields` is asserted against it and against `StrategyOutput` in the tests.

## The Three Layers <span class="status-label status-verified" aria-label="Verified"></span>

The three-layer scheme on the [framework index](./index.md) becomes three functions in `evaluation_episode.py`. Each returns a result rather than raising, so one failing layer does not hide the others.

### Layer one: unit and contract

`check_contract(strategy_output)` asks whether one strategy is internally correct, needing no observation and no ground truth. It runs the conservation report from [Strategy Output](./strategy-output.md) and reports every violation with its residual. This is the only layer that can fail a strategy outright: a plan that does not conserve is not scored further, because a comparison against a plan that has lost or invented money is not meaningful.

### Layer two: governance comparison

`compare_to_baselines(episode)` asks whether the strategy beats baselines under observed conditions, needing observations but no ground truth. It computes each Campaign's observed revenue per unit of spend from `episodes`, then reports what the strategy's allocation would have concentrated budget into relative to two baselines built from the same observations: an equal split across the allocated Campaigns, and the observed configured budget itself.

This layer reports a *ranking* agreement, not a revenue prediction. It answers "did the strategy move budget toward the Campaigns that were observed to return more per unit spent," which observed data can answer, rather than "how much revenue would this plan have produced," which it cannot — that requires a response model, which is layer three's business.

### Layer three: ground-truth evaluation

`score_against_ground_truth(episode)` asks whether the strategy recovers a known optimum. It returns `None` when `episode.ground_truth is None`, which is the honest result for every run this repository can currently perform, and the runner records it as not-run rather than as a zero score. A zero would read as a strategy that scored nothing; not-run reads as a question that was not asked.

## Adding a Fourth Layer <span class="status-label status-verified" aria-label="Verified"></span>

To add one, write a function in `evaluation_episode.py` taking a `StrategyEvaluationEpisode` and returning a frozen result dataclass, then add it to `run_evaluation_layers`. Four rules keep a new layer consistent with the existing three:

1. **Take the episode, not its parts.** A layer that takes `episodes` alone cannot see the decision; one that takes loose fields can be handed mismatched ones. The container has already validated that its parts agree.
2. **Read `ground_truth` only if the layer is a ground-truth layer,** and return a not-run result when it is `None`. Never substitute a default.
3. **Return a result; do not raise.** A layer that raises stops the others from reporting.
4. **Assert the isolation.** If the layer introduces a new dataclass that model-facing code will see, call `assert_no_ground_truth_fields` on it in a test, and if it feeds features to a response model, call `assert_no_forbidden_response_features` on their names.

A layer that needs a *fitted* model rather than observed aggregates belongs in an adapter under `modules/mta_strategy_evaluation/adapters/`, not here — see [Contributed Models](./contributed-models/index.md) for that boundary.

## Source Files <span class="status-label status-verified" aria-label="Verified"></span>

### `evaluation_episode.py`

Source: `modules/mta_strategy_evaluation/src/evaluation_episode.py`

- Responsibility: Define `StrategyEvaluationEpisode` and the three layer functions, keeping ground truth optional and structurally separate from the model-facing episodes beside it.
- Inputs: A `StrategyOutput` and the `CampaignEpisode` records for the same Campaigns and window.
- Outputs: `StrategyEvaluationEpisode`, `ContractCheckResult`, `BaselineComparisonResult`, `GroundTruthScore`, `StrategyEvaluationResult`, `check_contract`, `compare_to_baselines`, `score_against_ground_truth`, `run_evaluation_layers`.
- Public entry points: `run_evaluation_layers(episode) -> StrategyEvaluationResult` runs all three in order and returns every result, including a not-run marker for layer three; it does not short-circuit on a failing contract, but records `contract.is_conserving` so the caller can decide.
- Error handling: `__post_init__` raises `ValueError` for a Campaign with no episode or a currency mismatch. The layer functions themselves do not raise.
- Determinism: Campaign order follows `strategy_output.campaigns`; every reported number is rounded at the point of serialization only.
- Dependencies: `strategy_output.py`; `modules/mta_common/src/episode.py`, `evaluation_only.py`; Python standard library `dataclasses` and `math`.
- Verification: `modules/mta_strategy_evaluation/tests/test_evaluation_episode.py`.

## Current Availability <span class="status-label status-verified" aria-label="Verified"></span>

Implemented and tested. Layer three returns a not-run result in every configuration this repository supports, because no simulator here publishes a true optimal allocation.

## Known Limitations <span class="status-label status-verified" aria-label="Verified"></span>

- Layer two's baselines are built from the same observations it evaluates against, so it measures consistency with observed efficiency rather than out-of-sample performance. A strategy that concentrates budget into the historically best Campaign scores well by construction, which is a description of the metric, not evidence that the strategy is good.
- Layer three cannot run. Strategy ground truth is a future requirement on the simulator, not a gap in this code.
- `StrategyEvaluationEpisode` validates that every allocated Campaign has an episode, but not the reverse: an observed Campaign the strategy ignored is silently absent from the comparison.
- No layer accounts for the reporting window differing between the strategy's scope and the episodes' scopes beyond the currency check.

## References

- [Strategy output](./strategy-output.md)
- [Contributed models](./contributed-models/index.md)
- [Evaluation episode](/en/introduction/data-models/composed-episodes-and-evaluation-isolation/evaluation-episode.md)
- [Campaign episode](/en/introduction/data-models/composed-episodes-and-evaluation-isolation/campaign-episode.md)
- [Model testing and comparison](/en/attribution/model-testing.md)
