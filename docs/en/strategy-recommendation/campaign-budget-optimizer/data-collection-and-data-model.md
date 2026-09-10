---
title: Data Collection and Data Model
description: How budget-variation evidence is collected, aggregated into training rows, and kept free of attribution and ground truth
compact: "Specifies how prediction evidence is collected: snapshot to `episode_bridge` to `CampaignResponseObservation`, the aggregation rule that sums outcomes but takes budget once, the row's exact fields, and `FORBIDDEN_RESPONSE_FEATURES` enforcement."
lang: en-US
order: 20
source_files: modules/mta_strategy_recommendation/src/response_dataset.py, modules/mta_strategy_recommendation/src/episode_bridge.py
test_files: modules/mta_strategy_recommendation/tests/test_response_dataset.py
---

# Data Collection and Data Model

## How the Data Is Collected <span class="status-label status-verified" aria-label="Verified"></span>

The response model cannot be fitted from ordinary reporting. Reporting records what each Campaign spent and earned at whatever budget it happened to carry, and a Campaign held at one budget for its whole history contains no information about what a different budget would have produced. The model needs budgets that *moved*.

The evidence therefore comes from a budget-intervention experiment: a configuration under which the Multi-Touch Attribution Simulator (MTA-SIM) assigns each Campaign-period a budget arm, then records what that arm actually spent and earned. Each arm is an `intervention_id`, and the collection contract preserves arms rather than collapsing them.

### Source of record

`simulation_research.json`, either configured directly as a file or materialized by the dashboard from a selected database research scope. The two paths produce the same file contract, so the command below is unchanged in either case.

### What one arm records

A decision — configured budget, the baseline budget it moved from, the resulting delta, how the assignment was made, and whether it was randomized — followed by what was then observed: actual spend, impressions, clicks, and revenue.

### What makes an arm usable evidence

Distinct configured budgets. A Campaign qualifies for its own fitted curve at four or more observations across three or more distinct budgets; below that it has a history, not a response. The [fitting page](./fitting-implementation.md) specifies both thresholds and the pooled fallback.

### Why repeated budgets are not collapsed

A budget experiment may deliberately assign several arms to the same Campaign and day. Each distinct `intervention_id` remains a separate response observation, so the budget variation the model needs is neither merged away nor rejected as a duplicate.

## Collection Pipeline <span class="status-label status-verified" aria-label="Verified"></span>

### `mta_sim_research_adapter`

Reads the simulator's file contract into canonical `mta_common` objects, leaving them as flat parallel lists: campaigns, budget observations, delivery observations, outcome observations, and the context mappings that carry each observation's Campaign identifier.

### `episode_bridge`

Joins those flat lists into `CampaignEpisode` values on Campaign, marketplace, and period. One episode is emitted per budget observation whose Campaign is known; a budget observation naming an unknown Campaign is skipped rather than raising.

Two properties of this join are contractual rather than incidental:

#### Observed records only

The snapshot's `evaluation_outcome_observations` carry the organic and incremental splits the simulator knows because it generated them. They are evaluation-only truth and are never composed into a `CampaignEpisode`. A database materializer therefore omits rows whose `evaluation_only` flag is true.

#### Campaign restated in the observed scope

`CampaignEpisode` requires one currency across every scope it composes, but a Campaign's own scope describes where its identity was read, which may be a different marketplace from the period being observed. The bridge replaces the Campaign's `reporting_scope` with the budget observation's before composing.

### `response_dataset`

Aggregates episodes into the training rows the fit consumes. This is the only stage that decides what a Campaign "spent and earned in a period" means, so the trainer, the optimizer, and the dashboard all read one definition rather than each re-deriving totals.

## The Training Row <span class="status-label status-verified" aria-label="Verified"></span>

One `CampaignResponseObservation` represents one Campaign, marketplace, period, and assigned intervention, carrying what was decided and what was then observed.

### Identity

#### `campaign_id`

The observed Campaign.

#### `marketplace`

Marketplace the period was observed in.

#### `report_start_date`, `report_end_date`

Inclusive ISO start and end dates of the period.

#### `currency`

Currency every monetary field is denominated in. One row carries exactly one.

### Decision-time context

These are attributes known before the period ran, which is what makes them legitimate for segmenting a pooled fit.

#### `provider`

Decision-time advertising platform, as a `Provider` enumeration value.

#### `ad_product`

Decision-time provider ad product.

#### `campaign_status`

Decision-time Campaign status. Compared case-insensitively against `ACTIVE` when the optimizer decides eligibility.

### The assigned intervention

#### `configured_budget`

The budget assigned before the period ran. This is the model's independent variable.

#### `intervention_id`

Identifier of the assigned arm, or `None` when the period carried no recorded intervention. `is_intervention` is the derived property `intervention_id is not None`.

#### `baseline_budget`

The untreated budget the intervention moved from, or `None`.

#### `budget_delta`

`configured_budget - baseline_budget`, or `None`.

#### `assignment_type`

How the intervention was assigned, as an `AssignmentType` enumeration value, or `None`. Recorded but not conditioned on by the fit.

#### `randomized`

Whether assignment was randomized, or `None`. Recorded but not conditioned on by the fit.

### The observation

#### `actual_spend`

What the period actually spent. This is the intermediate variable joining the two fitted stages.

#### `impressions`, `clicks`

Observed delivery, summed across the period's touchpoints. Carried for diagnostics; neither is a fitted variable.

#### `total_revenue`

Observed revenue summed across touchpoints and Products, rounded to six decimal places. This is the response model's target.

### Derived key

#### `period_key`

The four-part tuple `(campaign_id, marketplace, report_start_date, intervention_id)` that identifies what a row aggregates.

### Validation on construction

`__post_init__` raises `ValueError` when `configured_budget`, `actual_spend`, `total_revenue`, `impressions`, or `clicks` is negative.

## Aggregation Rules <span class="status-label status-verified" aria-label="Verified"></span>

Several episodes covering the same Campaign, marketplace, period, and intervention are aggregated into one observation, which is how a Campaign advertising several Products still yields one response figure for that experimental arm.

The aggregation is not uniform across fields, and the asymmetry is the point:

```python
# Budget and spend describe the Campaign-period itself, so they are taken
# once rather than summed over episodes that repeat the same decision.
configured_budget = _consistent_value(                              # 1
    key, "configured_budget",
    (episode.budget_observation.configured_budget for episode in episodes))
actual_spend = _consistent_value(                                   # 2
    key, "actual_spend",
    (episode.budget_observation.actual_spend for episode in episodes))
for name in ("baseline_budget", "budget_delta",                     # 3
             "assignment_type", "randomized"):
    _consistent_value(                                              # 4
        key, name,
        (getattr(episode.budget_observation, name) for episode in episodes))

impressions = 0; clicks = 0; total_revenue = 0.0                    # 5
for episode in episodes:                                            # 6
    for delivery in episode.delivery_observations:                  # 7
        impressions += delivery.impressions or 0
        clicks += delivery.clicks or 0
    for outcome in episode.outcome_observations:                    # 8
        total_revenue += outcome.total_revenue or 0.0
```

### Lines 1-2 — Take budget and spend once, refusing contradictions

- Algorithm mapping: Reads one value for the Campaign-period rather than accumulating one per episode
- Reason: A budget describes the Campaign-period itself; episodes repeat the same decision rather than each contributing a share of it. Summing would multiply one budget by the number of Products the Campaign advertised, inventing budget variation that never happened

### Lines 3-4 — Validate the repeated decision metadata without storing a sum

- Algorithm mapping: Calls the same consistency check on four fields purely for its rejection behavior
- Reason: Two episodes claiming different baselines for one arm mean the input is malformed, and a fit built on it would be silently wrong

### Lines 5-8 — Sum the observed quantities

- Algorithm mapping: Accumulates impressions and clicks across delivery records, revenue across outcome records
- Reason: These are genuine per-touchpoint and per-Product quantities. A Campaign's revenue for a period is the sum of what its Products earned, and `None` is treated as zero rather than as missing

### `_consistent_value` rejection

A Campaign-period-intervention whose episodes disagree on any of the six fields raises `ResponseDatasetError` naming the field and the conflicting values. Distinct `intervention_id` values in the same period are *not* a conflict: they are separate valid experiment arms, and the grouping key separates them before this check runs.

### Ordering and determinism

Rows are ordered by Campaign, marketplace, period start date, and intervention identifier, because grouping keys are sorted before aggregation. Revenue is rounded to six decimal places. The same episodes always produce the same dataset.

## The Attribution and Ground-Truth Boundary <span class="status-label status-verified" aria-label="Verified"></span>

Attribution divides credit for outcomes that already happened; budget response asks what changes when the budget changes. The distinction is enforced in code rather than in review.

### `FORBIDDEN_RESPONSE_FEATURES`

A module-level frozenset naming every field that would constitute a leak, kept beside the builder that enforces it:

```
attribution_evidence      attributed_revenue        credit_share
markov_share              shapley_share             similarity_reference
similarity_score          true_incremental_units    true_incremental_revenue
true_causal_effect        simulator_ground_truth_id incremental_units
incremental_revenue       expected_organic_units    expected_organic_revenue
```

Three kinds of leak are covered: attribution results, the dashboard's [presentation-only similarity](/en/introduction/data-models/presentation-only-similarity/) values, and simulator ground truth including the organic and incremental splits.

### `assert_no_forbidden_response_features(feature_names)`

Intersects the offered names with the frozenset and raises `ResponseDatasetError` listing every leaked name, with the reason stated in the message rather than left to the caller to infer.

### `EvaluationEpisode` rejection

`build_campaign_response_dataset` checks the type of every episode before anything else. An `EvaluationEpisode` — the wrapper carrying the simulator's organic and incremental split — raises `ResponseDatasetError` outright, directing the caller to pass its `.episode` instead. A non-`CampaignEpisode` of any other type raises naming the type received.

## Where the Intermediate Product Is Saved <span class="status-label status-verified" aria-label="Verified"></span>

The dataset is an in-memory value, not a file. `CampaignResponseDataset` is constructed, fitted, and discarded within one command invocation; there is no cache, no intermediate CSV, and no database write between the bridge and the fit.

The evidence is not lost, however: every row is serialized into the final artifact's `response_observations` array, so the exact input behind a fitted curve is reconstructable from `campaign_strategy.json` alone. The [output artifact page](./output-artifact.md) specifies that array's flattened field shape, which differs slightly from the in-memory row (`report_start_date` is emitted as `report_date`, and the two enumeration fields as their string values).

## Worked Example <span class="status-label status-verified" aria-label="Verified"></span>

One row from the committed artifact's `response_observations`:

```json
{
  "campaign_id": "CAMPAIGN-DISPLAY",
  "marketplace": "TOY",
  "report_date": "2026-01-01",
  "currency": "USD",
  "provider": "AMAZON_ADS",
  "ad_product": "AMAZON_DSP",
  "configured_budget": 4.5,
  "actual_spend": 4.5,
  "impressions": 449,
  "clicks": 260,
  "total_revenue": 142.55,
  "intervention_id": "CAMPAIGN-DISPLAY:TOY:2026-01-01:0.75",
  "baseline_budget": 6.0,
  "budget_delta": -1.5,
  "assignment_type": "RULE_BASED",
  "randomized": false
}
```

The `intervention_id` encodes the arm as Campaign, marketplace, date, and multiplier: this period was assigned 0.75 times its baseline of 6.0, giving 4.5. `randomized` is false and `assignment_type` is `RULE_BASED`, which is precisely the case where the fitted curve is an association rather than a causal effect. Actual spend equals the configured budget, so this Campaign was not delivery-limited at this level.

The committed artifact holds 40 such rows across 2 Campaigns — 20 arms each, at 5 distinct budgets.

## Source Files <span class="status-label status-verified" aria-label="Verified"></span>

### `response_dataset.py`

Source: `modules/mta_strategy_recommendation/src/response_dataset.py`

**Responsibility.** Aggregate `CampaignEpisode` records into one Campaign-period row per assigned budget intervention, and enforce what a response feature may never be.

**Public entry points.** `build_campaign_response_dataset(episodes) -> CampaignResponseDataset` and `assert_no_forbidden_response_features(feature_names) -> None`. `CampaignResponseDataset` exposes `__len__`, `__iter__`, `campaign_ids`, `for_campaign(campaign_id)`, and `by_campaign()`; `CampaignResponseObservation` exposes `is_intervention` and `period_key`.

**Inputs.** An iterable of `CampaignEpisode`, each requiring a non-`None` `budget_observation`.

**Outputs.** A frozen `CampaignResponseDataset` whose `observations` tuple is ordered by Campaign, marketplace, period start date, and intervention identifier, with revenue rounded to six decimal places.

**Dependencies.** `modules.mta_common.src.enums` for `AssignmentType` and `Provider`, `modules.mta_common.src.episode` for `CampaignEpisode`, `modules.mta_common.src.evaluation_only` for the `EvaluationEpisode` it rejects.

**Errors.** `ResponseDatasetError` for an `EvaluationEpisode`, a non-`CampaignEpisode`, a missing budget observation, mixed currencies within one Campaign-period-intervention, conflicting decision metadata for one arm, or a forbidden feature name. Negative budget, spend, revenue, impressions, or clicks raise `ValueError`.

**Verification.** `modules/mta_strategy_recommendation/tests/test_response_dataset.py`.

### `episode_bridge.py`

Source: `modules/mta_strategy_recommendation/src/episode_bridge.py`

**Responsibility.** Join the research adapter's flat canonical lists into `CampaignEpisode` values on Campaign, marketplace, and period, which is the only type the response dataset accepts.

**Public entry point.** `campaign_episodes_from_research_snapshot(snapshot) -> tuple[CampaignEpisode, ...]`, one episode per Campaign, marketplace, and period holding a budget observation.

**Inputs.** An `MtaSimResearchSnapshot` from `modules.mta_standard.src.mta_sim_research_adapter`.

**Outputs.** A tuple of `CampaignEpisode`, each carrying a `BudgetConstraints` defaulted to `SPEND_UP_TO_BUDGET`, the budget observation, and the delivery and outcome observations grouped to its Campaign and period.

**Contract.** Reads the snapshot's observed records only; `evaluation_outcome_observations` are never composed into an episode. Attribution evidence is likewise not attached. A budget observation naming an unknown Campaign is skipped. Each Campaign is restated in its observed period's reporting scope. Delivery and outcome records are located through the adapter's parallel context mapping, because the canonical delivery and outcome classes are Touchpoint-scoped rather than Campaign-scoped; an observation whose context carries no `campaign_id` is skipped.

**Dependencies.** `modules.mta_common.src` budget, campaign, delivery, enums, episode, and outcome modules; `modules.mta_standard.src.mta_sim_research_adapter`.

**Verification.** `modules/mta_strategy_recommendation/tests/test_response_pipeline.py`.

## Verification

- **Scope:** Aggregation of episodes into response observations and the forbidden-feature boundary.
- **Cases:** Repeated-budget arms preserved as separate rows; outcomes summed while budget and spend are taken once; conflicting metadata and mixed currencies rejected; `EvaluationEpisode` and forbidden feature names rejected; ordering and rounding determinism.
- **Command:** `uv run python -X utf8 -B -m unittest modules.mta_strategy_recommendation.tests.test_response_dataset`.
- **Limitations:** Runs against constructed episodes and fixtures. The file contract between this repository and the pinned MTA-SIM generator is verified by `test_response_pipeline.py` instead.
