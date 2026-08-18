---
title: Campaign Episode
description: One campaign's decision-time and observed-after-treatment fields, composed for a future response model or optimizer
compact: "CampaignEpisode composes Campaign, BudgetConstraints, BudgetObservation, DeliveryObservation, OutcomeObservation, and AttributionEvidence into one model-facing row, classified into decision-time versus observed-after-treatment groups, with campaign_id and currency cross-consistency validation and no field able to carry evaluation-only ground truth."
lang: en-US
---

# CampaignEpisode

## Purpose <span class="status-label status-verified" aria-label="Verified"></span>

`CampaignEpisode` is one campaign's model-facing record: everything a future response model or a future strategy optimizer's evaluation loop would need for one campaign, in one composed object. It is also referred to as an optimization observation. It exists because no current shape in this repository joins a campaign's forward-looking budget bounds with what was actually spent and what was actually delivered and attributed — `strategy_request.json`, the attribution outputs, and the budget recommender's outputs are three separate files with no single row-level join today.

`CampaignEpisode` composes rather than restates: it holds a [Campaign](./campaign.md), a [Budget Constraints](./budget-constraints.md), an optional [Budget Observation](./budget-observation.md), and tuples of [Delivery Observation](./delivery-observation.md), [Outcome Observation](./outcome-observation.md), and [Attribution Evidence](./attribution-evidence.md) — each already validated on its own terms by its own `__post_init__`. `CampaignEpisode` adds only the cross-object consistency checks that require seeing more than one piece at once.

## Ownership and Layer <span class="status-label status-verified" aria-label="Verified"></span>

Defined in `modules/mta_common/src/episode.py`, in the canonical model's composed-episode layer. It sits above every observation class it references and below the not-yet-implemented response model and strategy optimizer that would consume it. It has no dependency on `modules/mta_common/src/evaluation_only.py`; the dependency runs the other way — `EvaluationEpisode` depends on `CampaignEpisode`, never the reverse. See [Evaluation Episode](./evaluation-episode.md).

## Fields <span class="status-label status-verified" aria-label="Verified"></span>

### campaign

#### Type

[Campaign](./campaign.md)

#### Requiredness

Required; no default.

#### Meaning

The campaign this episode describes. Decision-time-available: everything on `Campaign`, including its `reporting_scope`, is known before treatment (budget commitment) happens.

#### Missingness

Not nullable. A `CampaignEpisode` with no campaign is not a meaningful episode.

#### Validation

None beyond `Campaign`'s own `__post_init__`. `campaign.campaign_id` is the identity every other field is cross-checked against.

### budget_constraints

#### Type

[Budget Constraints](./budget-constraints.md)

#### Requiredness

Required; no default.

#### Meaning

The forward-looking budget bounds and `BudgetUsagePolicy` in force for `campaign`. Decision-time-available: known before treatment.

#### Missingness

Not nullable.

#### Validation

`budget_constraints.campaign_id` must equal `campaign.campaign_id`, checked in `CampaignEpisode.__post_init__`.

### budget_observation

#### Type

[Budget Observation](./budget-observation.md) `| None`

#### Requiredness

Optional; defaults to `None`.

#### Meaning

What was actually configured and actually spent for `campaign`, once known. Observed-after-treatment: only knowable from normal reporting once the campaign has run.

#### Missingness

`None` means no budget observation has been recorded yet for this episode — for example, a campaign that has been decided but not yet run. This is a real state, not an error.

#### Validation

When present, `budget_observation.campaign_id` must equal `campaign.campaign_id`, and its `reporting_scope.currency` must equal `campaign.reporting_scope.currency`. Both are checked in `CampaignEpisode.__post_init__`.

### delivery_observations

#### Type

`tuple[`[Delivery Observation](./delivery-observation.md)`, ...]`

#### Requiredness

Optional; defaults to an empty tuple via `field(default_factory=tuple)`.

#### Meaning

Delivery metrics observed for this campaign's touchpoints, one entry per touchpoint. Observed-after-treatment.

#### Missingness

An empty tuple means no delivery has been observed yet, not that delivery is inapplicable — `DeliveryObservation` itself is the class that distinguishes those cases per touchpoint. See [Delivery Observation](./delivery-observation.md)'s own Missingness section.

#### Validation

Every entry's `reporting_scope.currency` must equal `campaign.reporting_scope.currency`, checked in `CampaignEpisode.__post_init__`.

### outcome_observations

#### Type

`tuple[`[Outcome Observation](./outcome-observation.md)`, ...]`

#### Requiredness

Optional; defaults to an empty tuple.

#### Meaning

Outcomes observed for this campaign's touchpoints, one entry per touchpoint. Observed-after-treatment.

#### Missingness

An empty tuple means no outcome has been observed yet.

#### Validation

Every entry's `reporting_scope.currency` must equal `campaign.reporting_scope.currency`, checked in `CampaignEpisode.__post_init__`.

### attribution_evidence

#### Type

`tuple[`[Attribution Evidence](./attribution-evidence.md)`, ...]`

#### Requiredness

Optional; defaults to an empty tuple.

#### Meaning

Historical attribution evidence for this campaign's touchpoints and outcomes, one entry per touchpoint and outcome. Observed-after-treatment.

#### Missingness

An empty tuple means no attribution evidence has been computed yet for this episode.

#### Validation

Every entry's `reporting_scope.currency` must equal `campaign.reporting_scope.currency`, checked in `CampaignEpisode.__post_init__`.

## Invariants <span class="status-label status-verified" aria-label="Verified"></span>

- `budget_constraints.campaign_id == campaign.campaign_id`, always.
- `budget_observation.campaign_id == campaign.campaign_id`, whenever `budget_observation` is present.
- Every `reporting_scope.currency` reachable from `budget_observation`, `delivery_observations`, `outcome_observations`, and `attribution_evidence` equals `campaign.reporting_scope.currency`. A `CampaignEpisode` cannot silently mix, say, a USD campaign with an EUR delivery observation.
- `CampaignEpisode` has no field that can carry evaluation-only simulator ground truth. This is structural, not just a naming convention: `evaluation_only.assert_no_ground_truth_fields(CampaignEpisode)` inspects `dataclasses.fields(CampaignEpisode)` against `FORBIDDEN_MODEL_FACING_FIELDS` and does not raise, because none of `CampaignEpisode`'s six field names appear in that set. See [Evaluation Ground Truth](./evaluation-ground-truth.md) for what that set contains and why.
- The decision-time versus observed-after-treatment split itself is **structural, not an explicit typed field**: it is expressed by which of the six fields a piece of data occupies (`campaign`/`budget_constraints` are required with no default; `budget_observation`/`delivery_observations`/`outcome_observations`/`attribution_evidence` all default to "not yet observed"), not by a `RecordClassification`-typed attribute on `CampaignEpisode` itself. `RecordClassification` as an enum is instead used as a typed field on [Data Lineage](./data-lineage.md)'s `classification` attribute, for tagging a record's provenance; `CampaignEpisode` does not reference `RecordClassification` at all. Do not read this page as implying `CampaignEpisode` carries a `classification` field — it does not.

## Relationships <span class="status-label status-verified" aria-label="Verified"></span>

### Relationship to Campaign and Budget Constraints

`campaign` and `budget_constraints` are the two required, decision-time-available fields; every other field is optional and observed-after-treatment. See [Campaign](./campaign.md) and [Budget Constraints](./budget-constraints.md).

### Relationship to Budget, Delivery, Outcome, and Attribution Evidence Observations

`budget_observation`, `delivery_observations`, `outcome_observations`, and `attribution_evidence` are the observed-after-treatment pieces, each independently defined and validated on its own page: [Budget Observation](./budget-observation.md), [Delivery Observation](./delivery-observation.md), [Outcome Observation](./outcome-observation.md), [Attribution Evidence](./attribution-evidence.md).

### Relationship to Evaluation Episode

[Evaluation Episode](./evaluation-episode.md) holds a `CampaignEpisode` as a field rather than extending it, specifically so that simulator ground truth can never reach a function typed to accept `CampaignEpisode`. `CampaignEpisode` itself has no awareness of `EvaluationEpisode` — the dependency is one-directional.

## Legacy Mapping <span class="status-label status-verified" aria-label="Verified"></span>

### Current Source Fields

None. No single legacy source produces a campaign-episode-shaped row today. The pieces it composes each have their own legacy source: `Campaign`/`AdGroup` from `strategy_request.json`, `BudgetConstraints`/`BudgetObservation` from `strategy_request.json` and `initial_budget_recommendation.json`, `DeliveryObservation` from `TouchpointSpend`, `AttributionEvidence` from `AttributionResult`/`StandardAttributionRow`. `OutcomeObservation` is likewise adaptable today (see [Outcome Observation](./outcome-observation.md)'s Legacy Mapping).

### Canonical Conversion

`modules/mta_common/src/legacy_adapters.py` contains **no** `campaign_episode_from_*` function. Confirmed by inspection: the module has no reference to `Episode` anywhere. Every piece `CampaignEpisode` composes is independently adaptable via an existing `legacy_adapters.py` function, but nothing today assembles those adapted pieces into one `CampaignEpisode`.

### Information Loss

Not applicable — there is no conversion to describe yet.

## Examples <span class="status-label status-verified" aria-label="Verified"></span>

```python
from modules.mta_common.src.budget import BudgetConstraints, BudgetObservation
from modules.mta_common.src.campaign import Campaign
from modules.mta_common.src.enums import BudgetUsagePolicy, Provider
from modules.mta_common.src.episode import CampaignEpisode
from modules.mta_common.src.reporting_scope import ReportingScope

scope = ReportingScope(
    marketplace="US",
    advertiser_id="ADV-1",
    currency="USD",
    report_start_date="2026-01-01",
    report_end_date="2026-01-31",
)
campaign = Campaign(
    campaign_id="CAMP-1",
    campaign_name="Campaign One",
    provider=Provider.AMAZON_ADS,
    ad_product="SPONSORED_PRODUCTS",
    status="enabled",
    reporting_scope=scope,
)
episode = CampaignEpisode(
    campaign=campaign,
    budget_constraints=BudgetConstraints(
        campaign_id="CAMP-1",
        budget_usage_policy=BudgetUsagePolicy.SPEND_UP_TO_BUDGET,
    ),
    budget_observation=BudgetObservation(
        campaign_id="CAMP-1", reporting_scope=scope, configured_budget=100.0
    ),
)
```

A mismatched `budget_constraints.campaign_id` or a `budget_observation` in a different currency both raise `ValueError` at construction rather than producing a silently inconsistent episode.

## Downstream Usage <span class="status-label status-recommendation" aria-label="Recommendation"></span>

A future response-prediction model would consume `CampaignEpisode` as its training and inference row shape. A future strategy optimizer would read `CampaignEpisode` to evaluate a candidate allocation against observed history. Neither consumer exists yet; no code outside `modules/mta_common/tests/` currently constructs a `CampaignEpisode`.

## Current Availability <span class="status-label status-verified" aria-label="Verified"></span>

Implemented in `modules/mta_common/src/episode.py` and tested in `modules/mta_common/tests/test_episode_and_evaluation_isolation.py`: `CampaignEpisodeConsistencyTests` covers the mismatched-`campaign_id` and mismatched-currency rejections and a fully consistent construction; `DecisionTimeVsObservedFieldClassificationTests` asserts exactly `{"campaign", "budget_constraints"}` are the required (no-default) fields and that every observed-after-treatment field defaults to its empty/`None` unobserved state; `EvaluationOnlyIsolationTests.test_campaign_episode_carries_no_ground_truth_field` asserts `assert_no_ground_truth_fields(CampaignEpisode)` does not raise.

## Known Limitations <span class="status-label status-verified" aria-label="Verified"></span>

- No adapter assembles a `CampaignEpisode` from legacy data yet; a caller must construct one from already-adapted pieces.
- The decision-time/observed-after-treatment split is documented and structural (which field a value occupies) rather than machine-checkable via a single typed marker on `CampaignEpisode` itself — a reader must consult this page or the module docstring to know which group a field belongs to.
- Cross-consistency validation checks `campaign_id` and `currency` only; it does not check that `reporting_scope`'s date window is consistent across pieces, or that `touchpoint`s referenced by `delivery_observations`/`outcome_observations`/`attribution_evidence` belong to `campaign` (no field ties a `Touchpoint` back to a `Campaign` today).
