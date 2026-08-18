---
title: Evaluation Episode
description: A CampaignEpisode paired with its simulator ground truth, by composition rather than inheritance
compact: "EvaluationEpisode composes a CampaignEpisode and an EvaluationGroundTruth as two sibling fields rather than subclassing CampaignEpisode, so a function typed to accept CampaignEpisode has no attribute path into ground truth even if an EvaluationEpisode is passed by mistake."
lang: en-US
---

# EvaluationEpisode

## Purpose <span class="status-label status-verified" aria-label="Verified"></span>

`EvaluationEpisode` lets an evaluation harness hold both a model-facing [Campaign Episode](./campaign-episode.md) and its [Evaluation Ground Truth](./evaluation-ground-truth.md) at once, so it can compare a model's decision against simulator truth — while making it structurally impossible for that ground truth to reach the model or optimizer being evaluated. It is the only class in the canonical model permitted to reference `EvaluationGroundTruth`.

The isolation mechanism is composition, not inheritance: `EvaluationEpisode` **holds** a `CampaignEpisode` as a field (`self.episode`) rather than subclassing it. `issubclass(EvaluationEpisode, CampaignEpisode)` is `False`. This matters because inheritance would have made an `EvaluationEpisode` instance also *be* a `CampaignEpisode` — passable anywhere a `CampaignEpisode` was expected, including into model-facing code, at which point that code would hold an object that, via ordinary attribute access, could reach ground-truth fields even if it never used them. Composition removes that path entirely: a function typed to accept `CampaignEpisode` cannot be handed an `EvaluationEpisode` at all (`isinstance(evaluation, CampaignEpisode)` is `False`), so ground truth cannot reach it by accident, only by a caller explicitly extracting `.episode` and passing that.

## Ownership and Layer <span class="status-label status-verified" aria-label="Verified"></span>

Defined in `modules/mta_common/src/evaluation_only.py`, alongside `EvaluationGroundTruth`. Depends on `episode.CampaignEpisode`; `episode.py` has no reciprocal dependency on this module. This one-directional dependency means `CampaignEpisode` can be understood, and can be handed to model-facing code, with no need to know `EvaluationEpisode` exists at all.

## Fields <span class="status-label status-verified" aria-label="Verified"></span>

### episode

#### Type

[Campaign Episode](./campaign-episode.md)

#### Requiredness

Required; no default.

#### Meaning

The model-facing campaign episode — exactly what a model or optimizer being evaluated would have seen, with no ground truth attached.

#### Missingness

Not nullable.

#### Validation

None beyond `CampaignEpisode`'s own `__post_init__`, which already ran when `episode` was constructed. `EvaluationEpisode` itself defines no `__post_init__` and adds no cross-field check between `episode` and `ground_truth`.

### ground_truth

#### Type

[Evaluation Ground Truth](./evaluation-ground-truth.md)

#### Requiredness

Required; no default.

#### Meaning

The simulator's ground truth for the same episode `episode` describes — the true incremental effect a model or optimizer's decision on `episode` should be evaluated against.

#### Missingness

Not nullable.

#### Validation

None. Nothing ties `ground_truth.simulator_ground_truth_id` back to `episode.campaign.campaign_id` at construction time — matching the two is the caller's responsibility.

## Invariants <span class="status-label status-verified" aria-label="Verified"></span>

- `EvaluationEpisode` is not a subclass of `CampaignEpisode`: `issubclass(EvaluationEpisode, CampaignEpisode)` is `False`, and an `EvaluationEpisode` instance is never `isinstance(..., CampaignEpisode)`. Verified directly by `test_evaluation_episode_composes_rather_than_extends` and `test_evaluation_episode_is_not_a_campaign_episode` in `modules/mta_common/tests/test_episode_and_evaluation_isolation.py`.
- `EvaluationEpisode`'s own field set is exactly `{"episode", "ground_truth"}` — it adds no field of its own beyond composing the two, and in particular defines no ground-truth-shaped field directly on itself (the ground truth lives one attribute level down, on `.ground_truth`).
- Code that legitimately needs both — an evaluation harness — reads `EvaluationEpisode` and extracts `.episode` when it needs to call model-facing code with just the `CampaignEpisode`. This is a documented convention (`episode.py`'s module docstring), not a mechanism enforced by the type system beyond what composition already provides.

## Relationships <span class="status-label status-verified" aria-label="Verified"></span>

### Relationship to Campaign Episode

`episode` is a `CampaignEpisode` in full — every invariant on [Campaign Episode](./campaign-episode.md) already held before it was wrapped here. `EvaluationEpisode` adds no additional constraint on it.

### Relationship to Evaluation Ground Truth

`ground_truth` is an [Evaluation Ground Truth](./evaluation-ground-truth.md) in full. `EvaluationEpisode` is the only class permitted to hold one.

### Relationship to Market Simulation Ground Truth Isolation

`docs/en/market-simulation/index.md` documents that `simulation_ground_truth` is isolated to the evaluation workflow and that neither existing loader accepts it as model input. `EvaluationEpisode`'s composition-not-inheritance design is the canonical model's structural version of that same separation: an evaluation-only container that a model-facing consumer cannot be handed by type. See [Market Simulation](/en/market-simulation/index.md).

## Legacy Mapping <span class="status-label status-verified" aria-label="Verified"></span>

### Current Source Fields

None. No legacy shape in this repository combines an episode with simulator ground truth in one row today.

### Canonical Conversion

`modules/mta_common/src/legacy_adapters.py` has no function that constructs an `EvaluationEpisode`. Confirmed by inspection: the module contains no reference to `Episode` anywhere. A future simulator-backed evaluation harness would construct one from an already-built `CampaignEpisode` and `EvaluationGroundTruth`.

### Information Loss

Not applicable — there is no conversion to describe yet.

## Examples <span class="status-label status-verified" aria-label="Verified"></span>

```python
from modules.mta_common.src.evaluation_only import EvaluationEpisode, EvaluationGroundTruth

evaluation = EvaluationEpisode(
    episode=episode,  # a CampaignEpisode, e.g. from ./campaign-episode.md's example
    ground_truth=EvaluationGroundTruth(
        true_incremental_units=3.0,
        true_incremental_revenue=75.0,
        true_causal_effect="SIMULATOR_HOLDOUT",
        simulator_ground_truth_id="GT-1",
    ),
)

# A function typed to accept CampaignEpisode cannot be handed `evaluation` directly:
assert not isinstance(evaluation, type(episode))
# The evaluation harness explicitly unwraps to call model-facing code:
model_facing_call(evaluation.episode)
```

## Downstream Usage <span class="status-label status-recommendation" aria-label="Recommendation"></span>

A future evaluation harness would construct one `EvaluationEpisode` per simulated campaign, pass `.episode` to the model or optimizer under evaluation, and compare its output against `.ground_truth` to compute an evaluation metric — mirroring the existing pattern the attribution module already uses to compare model output against `simulation_ground_truth`, documented in [Market Simulation](/en/market-simulation/index.md). No such harness exists yet for the canonical model.

## Current Availability <span class="status-label status-verified" aria-label="Verified"></span>

Implemented in `modules/mta_common/src/evaluation_only.py` and tested in `modules/mta_common/tests/test_episode_and_evaluation_isolation.py`. `test_evaluation_episode_composes_rather_than_extends` asserts the field set is exactly `{"episode", "ground_truth"}` and that `EvaluationEpisode` is not a `CampaignEpisode` subclass. `test_evaluation_episode_is_not_a_campaign_episode` constructs both a `CampaignEpisode` and an `EvaluationEpisode` wrapping it, and asserts `isinstance(evaluation, CampaignEpisode)` is `False` while `evaluation.episode is episode` holds.

## Known Limitations <span class="status-label status-verified" aria-label="Verified"></span>

- No cross-check ties `ground_truth` to `episode` at construction time — a caller could pair a `CampaignEpisode` for one campaign with `EvaluationGroundTruth` for another, and `EvaluationEpisode` would not catch it.
- No simulator-backed evaluation harness exists yet to construct this class from real data.
- The composition-not-inheritance guarantee prevents an `EvaluationEpisode` from being *used* as a `CampaignEpisode` by the type system, but it does not prevent a caller from manually reading `evaluation.episode.campaign` fields and, separately, `evaluation.ground_truth` fields, and combining them ad hoc outside the type system's protection — the guarantee is against accidental structural substitution, not against a caller choosing to defeat the separation deliberately.
