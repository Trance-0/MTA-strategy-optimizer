---
title: Strategy Optimization Model
description: Current budget initializer and future Ad Group revenue-optimization model
compact: "Landing page for the strategy module: the IMPLEMENTED `generate_budget_recommendation()` seed in `src/budget_recommender.py`, the IMPLEMENTED Campaign response model and constrained optimizer in campaign-budget-optimizer.md, and still-PROPOSED Ad Group-level response and validation baselines. Read for orientation, not field detail."
lang: en-US
---

# Strategy Optimization Model

## Current: Budget Initializer <span class="status-label status-verified" aria-label="Verified"></span>

The public `generate_budget_recommendation()` function in `modules/mta_strategy_recommendation/src/budget_recommender.py` explicitly returns a deterministic, **unoptimized** Ad Group count and budget starting point.

The current strategy proceeds in four steps:

1. combine recommended MTA shares with the AMC entity bridge to derive Campaign Outcome contributions;
2. weight those contributions to obtain each Campaign MTA score;
3. apply capacity rules to candidate counts to determine the new Ad Group count; and
4. divide each Campaign budget by its new-group count to obtain the initial budget per group.

For Campaign (c):

$$
\text{campaign score}(c)
= \sum_o \text{outcome weight}(o)
\times \text{campaign contribution}(c,o)
$$

For a new Ad Group within the Campaign:

$$
\text{initial Ad Group budget}
= \text{total budget}
\times \frac{\text{campaign score}}
{\sum_c \text{campaign score}(c)}
\div \text{recommended Ad Group count}
$$

Related files:

### Core calculation

File: `src/budget_recommender.py`

### Generation entry point

File: `script/generate_initial_budget.py`

### Strategy input

File: `data/simulated/strategy_request.json`

### Candidate pool

File: `data/simulated/candidate_pool.json`

### Current output

File: `outputs/initial_budget_recommendation.json`

### Output validation

File: `src/hierarchy_validator.py`

## Current: Campaign Response Model and Optimizer <span class="status-label status-verified" aria-label="Verified"></span>

Where a Campaign's budget has already been varied and observed, the seed above is no longer the best available answer. A supervised, auditable response model is fitted per Campaign and a deterministic optimizer allocates against it, solving:

$$
\max_{b_c}
\sum_c \widehat{\text{expected revenue}}(c,b_c)
$$

subject to the authorized total budget and each Campaign's floor and ceiling. Because each fitted response is concave, the solution equalizes marginal expected revenue across every unconstrained Campaign at a single shadow price on budget.

The model is fitted in two stages — configured budget to actual spend, then actual spend to revenue — so a Campaign that cannot spend its budget is not confused with one that spends it poorly. Attribution is not an input to either stage: it divides credit for what already happened, which is a different question from how revenue responds to a budget change.

The optimization variable is the **Campaign**. Ad Group budgets are not optimized, because the candidate pool carries counts rather than features that would distinguish one new Ad Group from another; every plan discloses this as `NOT_AD_GROUP_OPTIMIZED`.

Read [Campaign Budget Response Model and Optimizer](campaign-budget-optimizer.md) for the fitted forms, the solver, the structured refusals, and the output contract.

Related files:

### Response dataset

File: `src/response_dataset.py`

### Fitted response model

File: `src/response_model.py`

### Constrained optimizer

File: `src/budget_optimizer.py`

### Generation entry point

File: `script/generate_campaign_strategy.py`

### Current output

File: `outputs/campaign_strategy.json`

## Next Stage: One Ad Group Response Model <span class="status-label status-recommendation" aria-label="Recommendation"></span>

Extending the response model below the Campaign requires inputs the current data does not carry. Model inputs must be available at decision time:

- historical MTA contribution and reliability;
- Campaign, Ad Product, and Ad Group attributes;
- candidate features such as Keyword, SKU, Target, and Audience;
- historical impressions, clicks, cost, purchases, and revenue;
- price, margin, inventory, budget-limited status, and pacing;
- candidate budget values and temporal features.

The model output would be expected revenue for each Ad Group under candidate budget (b):

$$
\widehat{\text{expected revenue}}(g,b)
$$

MTA results should be used as a historical prior or feature, not treated as budget response directly.

The optimizer would then extend to inventory, activation eligibility, budget increments, and business guardrails. If the true business objective is profit rather than revenue, change the objective to expected gross margin instead of mixing Revenue, Return on Ad Spend (ROAS), and unit sales; the current optimizer refuses a `MAXIMIZE_PROFIT` request rather than answering it with a revenue model.

## Validation Criteria <span class="status-label status-recommendation" aria-label="Recommendation"></span>

- Compare against three baselines: equal split, the current MTA Seed, and historical budgets.
- Use out-of-time validation to avoid future-data leakage from random splitting.
- Check predictive calibration, budget monotonicity, saturation, and extrapolation range.
- Use MTA-SIM Ground Truth only for synthetic evaluation after training ends.
- Demonstrate production gains through a compliant experiment or Holdout; MTA shares do not prove them directly.

For practical background on large-scale online experimentation systems, read [Online Controlled Experiments at Large Scale](/research/ab-testing/Online%20Controlled%20Experiments%20at%20Large%20Scale.pdf).


## References

- [Online Controlled Experiments at Large Scale (PDF)](/research/ab-testing/Online%20Controlled%20Experiments%20at%20Large%20Scale.pdf)
