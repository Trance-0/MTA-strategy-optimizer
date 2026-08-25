---
title: Strategy Output
description: The canonical data class a strategy returns, and the conservation contract every evaluator checks it against
compact: "StrategyOutput, CampaignBudgetDecision, AdGroupBudgetSlot, and the derived ConservationReport in modules/mta_strategy_evaluation/src/strategy_output.py, plus strategy_projection.py which projects initial_budget_recommendation.json and campaign_strategy.json into one comparable shape."
lang: en-US
source_files: modules/mta_strategy_evaluation/src/strategy_output.py, modules/mta_strategy_evaluation/src/strategy_projection.py
---

# Strategy Output

## Purpose <span class="status-label status-verified" aria-label="Verified"></span>

This project produces budget strategies from two different places and, until now, in two different shapes. The deterministic initializer writes `initial_budget_recommendation.json`, whose Campaigns carry a `budget_seed_share` and a list of Ad Group slots. The Campaign budget optimizer writes the `optimized_strategy` object inside `campaign_strategy.json`, whose Campaigns carry an `optimized_budget` and no Ad Group at all. The two answer the same question — how should this Campaign Group's money be divided — and nothing in the repository could compare them, because no type existed that both are instances of.

`StrategyOutput` is that type. It is the single data class a strategy returns and the single data class an evaluator accepts, so a comparison between the seed and the optimized plan is a comparison between two values of one type rather than two hand-written readers of two JavaScript Object Notation (JSON) documents. It follows the [Canonical Data Model](/en/introduction/data-models/index.md) scheme exactly: every class is a `@dataclass(frozen=True)`, every constraint that can be checked at construction is checked in `__post_init__`, and the module imports nothing outside the standard library and `modules/mta_common/`.

The class deliberately carries no model, no fitted curve, and no attribution share. It is the *decision* — what budget each Campaign was given — separated from the reasoning that produced it, because an evaluator that could see the reasoning would be scoring the argument rather than the outcome.

## Ownership and Layer <span class="status-label status-verified" aria-label="Verified"></span>

Defined in `modules/mta_strategy_evaluation/src/strategy_output.py`. It depends on `modules/mta_common/src/reporting_scope.py`, `enums.py`, and `lineage.py`, and nothing in `modules/mta_strategy_recommendation/` depends on it. That direction matters: the recommendation module keeps producing its native artifacts without knowing an evaluation layer exists, and the evaluation layer adapts to them. Reversing it would make every strategy change a change to the evaluator too.

`strategy_projection.py` sits beside it and holds the two readers that turn the committed artifacts into `StrategyOutput` values. Those readers are adapters in the same sense as `modules/mta_common/src/legacy_adapters.py`: they know the artifacts' field names so that nothing else has to.

## Fields <span class="status-label status-verified" aria-label="Verified"></span>

### strategy_id

#### Type

`str`

#### Requiredness

Required; no default.

#### Meaning

Which strategy produced this output, lowercase and underscore-separated — `deterministic_budget_seed` for the initializer, `campaign_response_optimizer` for the optimizer.

#### Missingness

Not nullable.

#### Validation

Must be non-empty after stripping whitespace.

### strategy_version

#### Type

`str`

#### Requiredness

Required; no default.

#### Meaning

The version of the contract the producing strategy was executed under, carried forward so a stored evaluation says which strategy contract it scored.

#### Missingness

Not nullable.

#### Validation

Must be non-empty after stripping whitespace.

### allocation_type

#### Type

`str`

#### Requiredness

Required; no default.

#### Meaning

Whether this is an unoptimized seed (`INITIAL_SEED`) or an optimized result (`OPTIMIZED`). The evaluator reports the two separately rather than averaging them, because a seed is not a failed optimization.

#### Missingness

Not nullable.

#### Validation

Must be one of `INITIAL_SEED` or `OPTIMIZED`.

### scope

#### Type

[Reporting Scope](/en/introduction/data-models/touchpoint-and-provider-contract/reporting-scope.md)

#### Requiredness

Required; no default.

#### Meaning

The marketplace, advertiser, currency, and date window this allocation was computed for. Reusing the canonical value object is what makes a strategy output comparable to the observations it will be scored against.

#### Missingness

Not nullable.

#### Validation

`ReportingScope.__post_init__` alone. Every monetary field on this output is denominated in `scope.currency`.

### campaigns

#### Type

`tuple[CampaignBudgetDecision, ...]`

#### Requiredness

Required; no default.

#### Meaning

One decision per Campaign this strategy allocated to.

#### Missingness

Not nullable, and not empty — a strategy that allocated to no Campaign made no decision to evaluate.

#### Validation

Must contain at least one entry, and Campaign identifiers must be unique. A duplicate identifier would make the conservation sums silently double-count.

### total_budget

#### Type

`float | None`

#### Requiredness

Optional; defaults to `None`.

#### Meaning

The authorized total the allocation had to fit inside. `None` means the strategy ran in relative-shares-only mode, which the deterministic initializer supports when no budget baseline is configured.

#### Missingness

`None` is meaningful and relaxes the monetary conservation constraints to the share constraints alone. It is not a stand-in for zero.

#### Validation

When present, must be finite and non-negative.

### uses_attribution

#### Type

`bool`

#### Requiredness

Optional; defaults to `False`.

#### Meaning

Whether Multi-Touch Attribution (MTA) evidence informed this allocation. Attribution may inform an Initial Strategy and must never reach a fitted response model or the optimizer, so recording it on the output is what lets an evaluation report state which side of that line the strategy stood on.

#### Missingness

Not nullable.

#### Validation

None beyond the type.

### lineage

#### Type

[Data Lineage](/en/introduction/data-models/historical-evidence-and-lineage/data-lineage.md) or `None`

#### Requiredness

Optional; defaults to `None`.

#### Meaning

Where this decision came from — which artifact, which schema version, which adapter version, and whether the underlying data was synthetic.

#### Missingness

`None` when the producer did not record provenance. The projection readers always populate it.

#### Validation

`DataLineage.__post_init__` alone. Its `classification` is `DECISION_TIME`, because a strategy output is by construction a decision made before its result was observed.

### warnings

#### Type

`tuple[str, ...]`

#### Requiredness

Optional; defaults to the empty tuple.

#### Meaning

Ordered warning codes the producing strategy raised, such as `NO_BUDGET_BASELINE_RELATIVE_SHARES_ONLY`. Carried through rather than dropped, so a plan that was already known to be weak does not read as a clean one after projection.

#### Missingness

Empty means no warning was raised, which is distinct from warnings not being recorded.

#### Validation

None beyond the type.

## Campaign Budget Decision <span class="status-label status-verified" aria-label="Verified"></span>

`CampaignBudgetDecision` is one Campaign's share of the plan.

#### `campaign_id`

The allocated Campaign. Required, non-empty.

#### `budget_share`

This Campaign's fraction of the group total, in `[0, 1]`. Required, because it is the one field both producers can always supply: the initializer stores it directly, and the optimizer's is derived from its budget over the allocated total.

#### `budget`

The absolute daily budget in `scope.currency`, or `None` in relative-shares-only mode. Must be non-negative when present.

#### `ad_product`

The Campaign's advertising product — `SPONSORED_PRODUCTS`, `SPONSORED_BRANDS`, `SPONSORED_DISPLAY`, or `AMAZON_DSP` (Demand-Side Platform). Optional, because the optimizer's artifact records it on the observations rather than on the allocation.

#### `provider`

The canonical [Provider](/en/introduction/data-models/vocabularies/provider.md), when known. Optional for the same reason.

#### `ad_groups`

Ordered `AdGroupBudgetSlot` entries, empty for a strategy that does not divide below the Campaign. Empty is the honest value for the optimizer, which explicitly claims `NOT_AD_GROUP_OPTIMIZED`.

#### `execution_status`

`EXECUTABLE`, `INSUFFICIENT_BUDGET_FOR_MINIMUMS`, or `UNEXECUTABLE`. Any other value is rejected at construction.

#### `decision_basis`

Free-text label naming how the number was arrived at, such as `CAMPAIGN_RESPONSE_MARGINAL_EQUALIZATION` or `CONFIGURED_BASELINE`. Optional.

`AdGroupBudgetSlot` carries `ad_group_slot_id`, `allocation_basis`, `budget_share`, and an optional `budget`, with the same non-negativity and range rules.

## Conservation Contract <span class="status-label status-verified" aria-label="Verified"></span>

The four constraints from [Recommended Strategy Structure](./strategy-structure.md) are checked here, over `StrategyOutput`'s own fields:

$$
\begin{aligned}
\sum_{g\in c} s_{c,g} &= s_c &&\text{(1) Within-Campaign share conservation},\\[4pt]
\sum_c s_c &= 1 &&\text{(2) Campaign shares sum to one},\\[4pt]
\sum_{g\in c} B_{c,g} &= B_c &&\text{(3) Within-Campaign budget conservation},\\[4pt]
\sum_c B_c &\le B_{\mathrm{total}} &&\text{(4) Group budget not exceeded}.
\end{aligned}
$$

Constraint (4) is an inequality: leaving budget unallocated is permitted, exceeding the total is not. Constraints (1) and (3) apply only to Campaigns that actually carry Ad Group slots; a Campaign with none conserves trivially. Constraints (3) and (4) are skipped entirely when `total_budget` is `None`, which is what relative-shares-only mode means.

Tolerances are the attribution layer's:

#### Share conservation

Absolute tolerance `1e-12`. No relative tolerance, because shares are already normalized and a relative bound would be a second, looser statement of the same thing.

#### Budget conservation

Absolute tolerance `1e-6`, relative tolerance `1e-9`. A residual passes if it is within either.

### Derived, not stored

`ConservationReport` is computed from `campaigns` by the `conservation()` method rather than stored as a field. The earlier proposal in [Recommended Strategy Structure](./strategy-structure.md) declared it a field; making it derived is a deliberate departure, because a stored report is free to disagree with the allocation beside it and nothing would say which was authoritative. A derived one cannot.

The report carries each constraint's worst residual (`within_campaign_share_error`, `campaign_share_error`, `within_campaign_budget_error`, `budget_overrun`), the tolerances it judged them against, an ordered tuple of human-readable `violations`, and `is_conserving`, which is true exactly when `violations` is empty.

A failing report does not raise. `__post_init__` rejects what is structurally impossible — a negative budget, an unknown execution status, a duplicate Campaign — while conservation is a property of an otherwise well-formed allocation, and the evaluation layer's job is to report it rather than to make it unrepresentable. A strategy whose report is not conserving is rejected before scoring, and the reason is printed.

## Invariants <span class="status-label status-verified" aria-label="Verified"></span>

- `StrategyOutput` carries no field named in `FORBIDDEN_MODEL_FACING_FIELDS`, verified by calling `assert_no_ground_truth_fields` on it and on both composed classes in `modules/mta_strategy_evaluation/tests/test_strategy_output.py`.
- `StrategyOutput` carries no attribution share, no fitted parameter, and no expected-revenue figure. `uses_attribution` records whether attribution informed the decision; it does not carry the attribution.
- Every monetary field is denominated in `scope.currency`. No field on this class mixes currencies, because there is exactly one scope per output.
- Campaign identifiers are unique within one output.
- `conservation()` is a pure function of the value: two equal `StrategyOutput` values return equal reports, and no call mutates anything.

## Relationships <span class="status-label status-verified" aria-label="Verified"></span>

### Relationship to the Campaign budget optimizer

`OptimizedBudgetPlan` in `modules/mta_strategy_recommendation/src/budget_optimizer.py` is the optimizer's own richer result: it carries expected revenue, marginal revenue, response support, and extrapolation flags per Campaign. `StrategyOutput` is the decision extracted from it. The optimizer is not changed to return `StrategyOutput`, and `strategy_projection.py` reads its artifact instead. See [Campaign Budget Response Model and Optimizer](/en/strategy-recommendation/campaign-budget-optimizer.md).

### Relationship to the deterministic initializer

`initial_budget_recommendation.json` is projected the same way, keeping its Ad Group slots, which are the only place in the repository where constraints (1) and (3) are non-trivial. See [Ad Group initial-budget output data contract](/en/strategy-recommendation/output-data-contract).

### Relationship to Campaign Episode

`StrategyOutput` is a decision; [Campaign Episode](/en/introduction/data-models/composed-episodes-and-evaluation-isolation/campaign-episode.md) is an observation. The evaluation layer holds both — the strategy that was chosen, and what was then observed — which is exactly the pairing [Evaluation Layers](./evaluation-layers.md) describes.

## Legacy Mapping <span class="status-label status-verified" aria-label="Verified"></span>

### Current Source Fields

From `initial_budget_recommendation.json`: `campaigns[].campaign_id`, `campaigns[].budget_seed_share`, `campaigns[].campaign_budget_seed`, `campaigns[].execution_status`, `campaigns[].recommended_ad_groups[]`, `budget_seed_total`, and `mta_source_snapshot`.

From `campaign_strategy.json`: `optimized_strategy.allocations[].campaign_id`, `.optimized_budget`, `.allocation_basis`, `optimized_strategy.allocated_budget`, `optimized_strategy.authorized_budget`, and `currency`, with marketplace and dates recovered from `response_observations`.

### Canonical Conversion

`strategy_projection.strategy_output_from_initial_budget` and `strategy_projection.strategy_output_from_campaign_strategy`. The optimizer's shares are derived as `optimized_budget / allocated_budget`, and are `0.0` for every Campaign when the plan allocated nothing.

### Information Loss

The projection drops the optimizer's per-Campaign expected revenue, marginal revenue, response support, and extrapolation flags, and drops the initializer's outcome contributions, count rationale, and bridge summary. Both are recoverable from the artifacts themselves; they are omitted here because they are the strategy's reasoning rather than its decision, and an evaluator must not score the argument.

A non-optimized plan — one whose `is_optimized` is `false` because the optimizer refused — projects to a `StrategyOutput` with no Campaign, which is rejected at construction. The reader raises `StrategyProjectionError` naming the refusal reasons instead, so a refusal is never silently scored as an allocation of nothing.

## Examples <span class="status-label status-verified" aria-label="Verified"></span>

```python
from modules.mta_common.src.reporting_scope import ReportingScope
from modules.mta_strategy_evaluation.src.strategy_output import (
    CampaignBudgetDecision,
    StrategyOutput,
)

output = StrategyOutput(
    strategy_id="campaign_response_optimizer",
    strategy_version="1.0.0",
    allocation_type="OPTIMIZED",
    scope=ReportingScope(
        marketplace="TOY",
        advertiser_id="adv_demo_001",
        currency="USD",
        report_start_date="2026-01-01",
        report_end_date="2026-01-20",
    ),
    campaigns=(
        CampaignBudgetDecision(
            campaign_id="CAMPAIGN-DISPLAY", budget_share=0.15638, budget=10.321458
        ),
        CampaignBudgetDecision(
            campaign_id="CAMPAIGN-SEARCH", budget_share=0.84362, budget=55.678542
        ),
    ),
    total_budget=66.0,
)

report = output.conservation()
assert report.is_conserving, report.violations
```

## Downstream Usage <span class="status-label status-verified" aria-label="Verified"></span>

`script/evaluate_strategies.py` projects both committed artifacts into `StrategyOutput`, checks each one's conservation, and passes the conserving ones to the contributed response model described in [Contributed Models](./contributed-models/index.md). The result is written to `modules/mta_strategy_evaluation/outputs/strategy_evaluation.json` and served to the dashboard under the `strategyEvaluation` snapshot key. See [Running an Evaluation](./running-an-evaluation.md).

## Current Availability <span class="status-label status-verified" aria-label="Verified"></span>

Implemented and tested. `modules/mta_strategy_evaluation/tests/test_strategy_output.py` covers construction, every `__post_init__` rejection, the four conservation constraints at and just outside tolerance, relative-shares-only mode, and the ground-truth field check. `modules/mta_strategy_evaluation/tests/test_strategy_projection.py` projects both committed artifacts and asserts each conserves.

## Known Limitations <span class="status-label status-verified" aria-label="Verified"></span>

- The optimizer's artifact records no marketplace or date window on the plan itself, so the projection recovers them from `response_observations` and raises if that list is empty. An optimized plan produced without observations cannot be projected.
- `budget_share` for an optimized plan is derived from the allocated total rather than the authorized total, so a plan that deliberately underspends still has shares summing to one. Constraint (4) is what records the underspend, not constraint (2).
- Nothing ties `scope` to the reporting window the strategy's evidence actually covered; the projection copies what the artifact recorded, and an artifact with a wrong window projects to an output with the same wrong window.
- `AdGroupBudgetSlot` has no Ad Group identifier, only a slot identifier, because the initializer allocates to anonymous slots rather than to existing Ad Groups. An evaluation cannot therefore attribute a slot's outcome to a real Ad Group.

## Source Files <span class="status-label status-verified" aria-label="Verified"></span>

### `strategy_output.py`

Source: `modules/mta_strategy_evaluation/src/strategy_output.py`

- Responsibility: Define `StrategyOutput`, `CampaignBudgetDecision`, `AdGroupBudgetSlot`, and `ConservationReport`, and the four conservation constraints with their tolerances.
- Inputs: Values built by `strategy_projection.py` or by a future strategy that returns this type directly.
- Outputs: The four classes above, the `ALLOCATION_TYPE_INITIAL_SEED` / `ALLOCATION_TYPE_OPTIMIZED` / `EXECUTION_STATUSES` constants, and the three tolerance constants.
- Public entry points: `StrategyOutput.conservation() -> ConservationReport` and `StrategyOutput.to_dict() -> dict`. `to_dict` returns JSON-compatible values only, with `provider` projected to its string value and `None` preserved rather than zero-filled.
- Determinism: `conservation()` and `to_dict()` are pure; Campaigns are serialized in the order supplied, never re-sorted.
- Dependencies: `modules/mta_common/src/enums.py`, `lineage.py`, `reporting_scope.py`; Python standard library `dataclasses` and `math`.
- Verification: `modules/mta_strategy_evaluation/tests/test_strategy_output.py`.

### `strategy_projection.py`

Source: `modules/mta_strategy_evaluation/src/strategy_projection.py`

- Responsibility: Read the two committed strategy artifacts and return `StrategyOutput` values, raising rather than fabricating when an artifact cannot honestly be projected.
- Inputs: Parsed `initial_budget_recommendation.json` and `campaign_strategy.json` documents, or paths to them.
- Outputs: `strategy_output_from_initial_budget(document)`, `strategy_output_from_campaign_strategy(document)`, `load_strategy_outputs(directory)`, and `StrategyProjectionError`.
- Error handling: raises `StrategyProjectionError` when a document is empty, when `optimized_strategy.is_optimized` is false (naming `infeasibility_reasons`), or when an optimized plan carries no `response_observations` from which to recover marketplace and dates.
- Determinism: Campaign order follows the artifact's own order in both readers, never alphabetical, matching how `backend/repository/strategy.py` reassembles the same documents.
- Dependencies: `strategy_output.py`; `modules/mta_common/src/enums.py`, `lineage.py`, `reporting_scope.py`; Python standard library `json` and `pathlib`.
- Verification: `modules/mta_strategy_evaluation/tests/test_strategy_projection.py`.

## References

- [Recommended strategy structure](./strategy-structure.md)
- [Evaluation layers](./evaluation-layers.md)
- [Contributed models](./contributed-models/index.md)
- [Canonical data model](/en/introduction/data-models/index.md)
- [Campaign budget response model and optimizer](/en/strategy-recommendation/campaign-budget-optimizer.md)
