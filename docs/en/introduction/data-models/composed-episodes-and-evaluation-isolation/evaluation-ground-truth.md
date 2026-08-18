---
title: Evaluation Ground Truth
description: Simulator-known true incremental effect for one campaign episode, isolated to evaluation-only code
compact: "EvaluationGroundTruth carries true_incremental_units, true_incremental_revenue, true_causal_effect, and simulator_ground_truth_id — the only place in the canonical model allowed to hold simulator-known causal truth. Never constructed by any current adapter; mirrors simulation_ground_truth's existing isolation in the market-simulation loaders."
order: 20
lang: en-US
---

# EvaluationGroundTruth

## Purpose <span class="status-label status-verified" aria-label="Verified"></span>

`EvaluationGroundTruth` is the only place in the canonical model allowed to define a field carrying simulator-known causal truth — the true incremental effect a simulation mechanism produced, as opposed to anything a real observational pipeline could ever measure. It exists to give a name and a validated shape to a category of information that this project's documentation already treats as categorically different from every other field: `docs/en/market-simulation/index.md` marks `simulation_ground_truth` "Evaluation only; prohibited as a training feature," and the existing `MtaSimDataset` loader enforces that by having no field for it at all. `EvaluationGroundTruth` is the canonical model's counterpart to that same rule.

No class described elsewhere in this documentation section may hold a field shaped like this one. [Campaign Episode](/en/introduction/data-models/composed-episodes-and-evaluation-isolation/campaign-episode.md) is checked for exactly that by `evaluation_only.assert_no_ground_truth_fields`.

## Ownership and Layer <span class="status-label status-verified" aria-label="Verified"></span>

Defined in `modules/mta_common/src/evaluation_only.py`, a module deliberately separated from `modules/mta_common/src/episode.py`. Nothing in `episode.py` imports from `evaluation_only.py`; the dependency runs the other way — `evaluation_only.py` imports `CampaignEpisode` from `episode.py`. This one-directional dependency is itself part of the isolation guarantee: `episode.py` can be read, reasoned about, and reused with no knowledge that `evaluation_only.py` exists.

## Fields <span class="status-label status-verified" aria-label="Verified"></span>

### true_incremental_units

#### Type

`float`

#### Requiredness

Required; no default.

#### Meaning

The simulator's true causal effect on units — the unit count that would not have occurred without advertising, known only because the simulator generated the underlying data and can report its own mechanism.

#### Missingness

Not nullable. An `EvaluationGroundTruth` record exists specifically to carry this value; there is no state in which it is legitimately absent from a constructed instance.

#### Validation

None beyond the dataclass's own type check. No sign or range constraint is enforced — a simulator mechanism could in principle report a negative incremental effect (advertising suppressing demand), so this field does not assume non-negativity the way `OutcomeObservation.total_units` does.

### true_incremental_revenue

#### Type

`float`

#### Requiredness

Required; no default.

#### Meaning

The simulator's true causal effect on revenue, on the same basis as `true_incremental_units`.

#### Missingness

Not nullable.

#### Validation

None beyond the dataclass's own type check, for the same reason as `true_incremental_units`.

### true_causal_effect

#### Type

`str`

#### Requiredness

Required; no default.

#### Meaning

Free-text description of the simulator mechanism that produced `true_incremental_units`/`true_incremental_revenue`, so an evaluation report can explain what generated the number it is comparing a model's prediction against.

#### Missingness

Not nullable; not validated as non-blank in `__post_init__` (there is no `__post_init__` on this class at all — see Validation).

#### Validation

`EvaluationGroundTruth` defines no `__post_init__`; none of its four fields is validated beyond the dataclass's built-in type check. This is a deliberate difference from every other class in this documentation section, most of which do validate required strings as non-blank.

### simulator_ground_truth_id

#### Type

`str`

#### Requiredness

Required; no default.

#### Meaning

Identifier tying this record back to the simulator's own ground-truth table, for traceability from an evaluation report back to the specific simulated scenario.

#### Missingness

Not nullable.

#### Validation

None; see `true_causal_effect`'s Validation note above — this applies to every field on the class.

## Invariants <span class="status-label status-verified" aria-label="Verified"></span>

- `EvaluationGroundTruth`'s four field names — `true_incremental_units`, `true_incremental_revenue`, `true_causal_effect`, `simulator_ground_truth_id` — are exactly the contents of `evaluation_only.FORBIDDEN_MODEL_FACING_FIELDS`, a `frozenset` maintained in the same module. `test_forbidden_fields_cover_every_ground_truth_field` in `modules/mta_common/tests/test_episode_and_evaluation_isolation.py` asserts this set equality directly, so the two cannot silently drift apart — adding a field to `EvaluationGroundTruth` without adding it to `FORBIDDEN_MODEL_FACING_FIELDS` would fail that test.
- No class outside `evaluation_only.py` may declare a field named for any of these four strings. `evaluation_only.assert_no_ground_truth_fields(model_facing_type)` is the automated, reusable check any future model-facing class can run against itself.
- `EvaluationGroundTruth` is never accepted as a field on any class described elsewhere in this documentation section. It is accepted only by [Evaluation Episode](/en/introduction/data-models/composed-episodes-and-evaluation-isolation/evaluation-episode.md), which exists specifically to pair it with a `CampaignEpisode` outside the model-facing type itself.

## Relationships <span class="status-label status-verified" aria-label="Verified"></span>

### Relationship to Evaluation Episode

[Evaluation Episode](/en/introduction/data-models/composed-episodes-and-evaluation-isolation/evaluation-episode.md) is the only class that holds an `EvaluationGroundTruth` field. It pairs one `EvaluationGroundTruth` with one `CampaignEpisode`, by composition.

### Relationship to Campaign Episode

[Campaign Episode](/en/introduction/data-models/composed-episodes-and-evaluation-isolation/campaign-episode.md) has no field of this type, and cannot be given one without changing its definition — this is what `assert_no_ground_truth_fields(CampaignEpisode)` verifies. See that page's Invariants section.

### Relationship to Market Simulation Ground Truth

`docs/en/market-simulation/index.md` documents that `simulation_ground_truth` is evaluation-only and that `MtaSimDataset` has no field for it and its loader accepts no ground-truth path — `EvaluationGroundTruth` is the canonical model's structural counterpart to that same rule, not a new policy. See [Market Simulation](/en/market-simulation/index.md).

## Legacy Mapping <span class="status-label status-verified" aria-label="Verified"></span>

### Current Source Fields

None populated by any current adapter. `simulation_ground_truth` is MTA-SIM's closest real-world analog, but no code path in this repository currently reads it into any structure — the existing loaders reject it outright rather than adapting it.

### Canonical Conversion

`modules/mta_common/src/legacy_adapters.py` has no function that constructs an `EvaluationGroundTruth`. Confirmed by inspection: the module contains no reference to `EvaluationGroundTruth`, `ground_truth`, or `simulation_ground_truth`. A future simulator-backed evaluation harness would be the only legitimate caller of this class's constructor.

### Information Loss

Not applicable — there is no conversion to describe yet.

## Examples <span class="status-label status-verified" aria-label="Verified"></span>

```python
from modules.mta_common.src.evaluation_only import EvaluationGroundTruth

ground_truth = EvaluationGroundTruth(
    true_incremental_units=3.0,
    true_incremental_revenue=75.0,
    true_causal_effect="SIMULATOR_HOLDOUT",
    simulator_ground_truth_id="GT-1",
)
```

Only a simulator-backed evaluation harness should ever construct this — see [Evaluation Episode](/en/introduction/data-models/composed-episodes-and-evaluation-isolation/evaluation-episode.md) for how it is combined with model-facing data without leaking into it.

## Downstream Usage <span class="status-label status-recommendation" aria-label="Recommendation"></span>

A future evaluation harness would construct `EvaluationGroundTruth` from a simulator's own ground-truth output and pair it, via `EvaluationEpisode`, with the `CampaignEpisode` a model or optimizer actually saw — comparing the two without ever passing ground truth into model-facing code. No such harness exists yet.

## Current Availability <span class="status-label status-verified" aria-label="Verified"></span>

Implemented in `modules/mta_common/src/evaluation_only.py` and tested in `modules/mta_common/tests/test_episode_and_evaluation_isolation.py`. `test_forbidden_fields_cover_every_ground_truth_field` asserts `FORBIDDEN_MODEL_FACING_FIELDS` exactly matches this class's field names. `test_assert_no_ground_truth_fields_catches_a_leaking_type` constructs a deliberately leaky ad-hoc dataclass carrying `true_incremental_units` and asserts `assert_no_ground_truth_fields` raises `ValueError` against it, proving the check actually detects a leak rather than trivially passing.

## Known Limitations <span class="status-label status-verified" aria-label="Verified"></span>

- No `__post_init__` validation exists on this class — none of its four fields is checked for blankness, sign, or range. This is intentional scope-narrowing (it exists to be isolated, not to validate a simulator's own output) but means a caller can construct a nonsensical instance (empty `simulator_ground_truth_id`, negative revenue with no error) without the class itself catching it.
- No simulator-backed evaluation harness exists yet to populate this class from real simulator output.
- The isolation guarantee (`FORBIDDEN_MODEL_FACING_FIELDS`) is enforced by field name only. A future model-facing class that reused one of these exact field names for an unrelated purpose would trip `assert_no_ground_truth_fields`, even if unrelated to ground truth — a narrow, deliberate trade-off against a name collision.
