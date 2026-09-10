---
title: Campaign Budget Response Model and Optimizer
description: Fitted two-stage Campaign response curves and the constrained allocation solved from them
compact: "Reproduction specification for the Campaign budget optimizer: the two-stage saturating response model, its assumptions, the grid-refined least-squares fit, the shadow-price solver, the data model at every stage, and the `campaign_strategy.json` artifact."
lang: en-US
order: 30
---

# Campaign Budget Response Model and Optimizer <span class="status-label status-verified" aria-label="Verified"></span>

The [budget initializer](../module-overview/) answers a structural question: how many new Ad Groups does each Campaign need, and what starting budget does each new group receive when nothing is yet known about it. Its answer is a seed, labelled `INITIAL_SEED` with `is_optimized=false`, and it is derived from historical Multi-Touch Attribution (MTA) credit.

This specification answers a different question:

> Given Campaigns whose budgets have already been varied and observed, what budget should each Campaign receive so that total expected revenue is greatest, subject to the budget the business authorized and the floor and ceiling on each Campaign?

The two are not competing versions of one calculation. The initializer allocates where there is no response evidence; the optimizer allocates where there is. The generated artifact carries both so a reader can compare them side by side.

## What This Specification Covers

The specification is written so an agent holding only these pages and the repository's canonical data models can rebuild the implementation. It divides along the pipeline's own stages, because each stage has a distinct contract, a distinct failure mode, and a distinct thing it is allowed to know.

### [Model and Assumptions](./model-and-assumptions.md)

The functional forms of both stages, every assumption the model imposes rather than discovers, and the questions the fitted curve is not evidence for. Read this before any other part: the assumptions decide what the fit and the solver are permitted to be.

### [Data Collection and Data Model](./data-collection-and-data-model.md)

Where the training evidence comes from, how a budget experiment becomes one training row, the exact field list of that row, and the boundary that keeps attribution results and simulator ground truth out of the model. This is the "how the data is collected for prediction" contract.

### [Fitting Implementation](./fitting-implementation.md)

The deterministic grid-refined least-squares procedure, decomposed line by line: both search grids, the closed-form step, the non-negativity clamps, the evidence-support labels, and the diagnostics each fit reports.

### [Optimizer Implementation](./optimizer-implementation.md)

The constrained allocation problem, the shadow-price argument that justifies solving it by bisection, the two nested bisections, the remainder distribution, the independent post-validation, and every structured refusal.

### [Output Artifact and Verification](./output-artifact.md)

Where the intermediate and final products are written, the field-by-field contract of `campaign_strategy.json` with values from the committed artifact, the command that produces it, and the tests that verify it.

## Pipeline at a Glance

The chain runs from the Multi-Touch Attribution Simulator (MTA-SIM) research snapshot to the dashboard, and each stage narrows what the next may see:

```
simulation_research.json          input contract, from a file or materialized
                                  from a selected dashboard research scope
  -> mta_sim_research_adapter     read into canonical mta_common objects
  -> episode_bridge               join flat lists into CampaignEpisode records,
                                  observed records only
  -> response_dataset             aggregate into one row per Campaign x
                                  marketplace x period x intervention
  -> response_model               fit two stages per Campaign, label evidence
  -> budget_optimizer             equalize marginal revenue at one price
  -> outputs/campaign_strategy.json
  -> dashboard Optimization Log
```

## Attribution Is Not an Input

This is the boundary the [optimization plan](../optimization-plan.md) identifies under "MTA Attribution Is Not Budget Incrementality", and the implementation enforces it rather than merely recommending it.

Attribution divides credit for outcomes that already happened. A touchpoint may hold a large attributed share because its historical budget was large, because it sat close to conversion, or because it genuinely performed better; the share alone cannot separate these. Budget response is the different question of what changes when the budget changes, and only a record of budgets actually varying can answer it.

`response_dataset.py` enforces the boundary in code rather than in prose. The [data model page](./data-collection-and-data-model.md) specifies the forbidden-feature frozenset and the two exceptions it raises.

## The Optimization Variable Is the Campaign

The optimizer does not learn or claim Ad Group optimization. The candidate pool carries aggregate counts rather than features that distinguish one new Ad Group from another, so any split below a Campaign is a projection, not an optimization. Every plan states this in two fields it always carries: `ad_group_projection_basis` is `EQUAL_SPLIT_WITHIN_CAMPAIGN`, and `ad_group_optimization_claim` is `NOT_AD_GROUP_OPTIMIZED`. This is the same limit the [optimization plan](../optimization-plan.md) records under "Campaign-Level Contribution and Within-Campaign Differences", stated in output rather than left to the reader.

## What This Stage Does Not Establish

The optimizer maximizes expected revenue under a fitted model. That is not a claim of causal incrementality, and the [optimization plan](../optimization-plan.md) separates the two deliberately.

The fitted response is estimated from observed budget variation. Where that variation was assigned by a deterministic schedule rather than randomized, the estimate remains a response association rather than a causal effect, which is why each observation preserves its `assignment_type` and `randomized` flags. The `randomized` flag is recorded so a later evaluation can distinguish the two; the current model does not condition on it.

Comparison against the equal-split, MTA-seed, and historical-budget baselines, out-of-time validation, and the synthetic ground-truth evaluation belong to [strategy evaluation](/en/strategy-evaluation/) and are not performed here. Demonstrating a production gain requires a compliant experiment or holdout; neither an attribution share nor a fitted curve proves one.

## References

- [Concavity](/en/reference/definitions#concavity), [Marginal Revenue](/en/reference/definitions#marginal-revenue), and [Shadow Price of Budget](/en/reference/definitions#shadow-price-of-budget) in the domain glossary
- [Budget Constraints](/en/introduction/data-models/budget-delivery-and-outcome-observations/budget-constraints.md) and [Budget Observation](/en/introduction/data-models/budget-delivery-and-outcome-observations/budget-observation.md), the canonical input classes
- [Strategy Objective](/en/introduction/data-models/vocabularies/strategy-objective.md), the objective vocabulary the optimizer reads
