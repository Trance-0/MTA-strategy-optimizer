---
title: Strategy Optimization Model
description: Current budget initializer and future Ad Group revenue-optimization model
lang: en-US
---

# Strategy Optimization Model

## Current: Budget Initializer <span class="status-label status-verified" aria-label="Verified"></span>

The public `generate_budget_recommendation()` function in `modules/mta_strategy_recommender/src/budget_recommender.py` explicitly returns a deterministic, **unoptimized** Ad Group count and budget starting point.

```text
Recommended MTA shares + AMC entity Bridge → Campaign Outcome contribution
Campaign Outcome contribution × Outcome weight → Campaign MTA score
Candidate count ÷ capacity rule → new Ad Group count
Campaign budget ÷ new-group count → initial budget per group
```

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

| Responsibility | File |
| --- | --- |
| Core calculation | `src/budget_recommender.py` |
| Generation entry point | `scripts/generate_initial_budget.py` |
| Strategy input | `data/simulated/strategy_request.json` |
| Candidate pool | `data/simulated/candidate_pool.json` |
| Current output | `outputs/initial_budget_recommendation.json` |
| Output validation | `src/hierarchy_validator.py` |

## Next Stage: One Ad Group Response Model <span class="status-label status-recommendation" aria-label="Recommendation"></span>

The first optimization version should use one supervised, auditable response model rather than orchestrating multiple Agents or generative models. Model inputs must be available at decision time:

- historical MTA contribution and reliability;
- Campaign, Ad Product, and Ad Group attributes;
- candidate features such as Keyword, SKU, Target, and Audience;
- historical impressions, clicks, cost, purchases, and revenue;
- price, margin, inventory, budget-limited status, and pacing;
- candidate budget values and temporal features.

The model output should be expected revenue for each Ad Group under candidate budget (b):

$$
\widehat{\text{expected revenue}}(g,b)
$$

MTA results should be used as a historical prior or feature, not treated as budget response directly.

## Constrained Optimizer <span class="status-label status-recommendation" aria-label="Recommendation"></span>

After the model produces budget–revenue responses, a separate deterministic optimizer solves:

$$
\max_{b_g}
\sum_g \widehat{\text{expected revenue}}(g,b_g)
$$

subject to:

$$
\sum_g b_g \le \text{total campaign budget},
\qquad
\text{minimum budget}(g) \le b_g \le \text{maximum budget}(g)
$$

It should also include inventory, activation eligibility, budget increments, and business guardrails. If the true business objective is profit rather than revenue, change the objective to expected gross margin instead of mixing Revenue, Return on Ad Spend (ROAS), and unit sales.

## Validation Criteria <span class="status-label status-recommendation" aria-label="Recommendation"></span>

- Compare against three baselines: equal split, the current MTA Seed, and historical budgets.
- Use out-of-time validation to avoid future-data leakage from random splitting.
- Check predictive calibration, budget monotonicity, saturation, and extrapolation range.
- Use MTA-SIM Ground Truth only for synthetic evaluation after training ends.
- Demonstrate production gains through a compliant experiment or Holdout; MTA shares do not prove them directly.

For practical background on large-scale online experimentation systems, read [Online Controlled Experiments at Large Scale](/research/ab-testing/Online%20Controlled%20Experiments%20at%20Large%20Scale.pdf).

## References

- [Online Controlled Experiments at Large Scale (PDF)](/research/ab-testing/Online%20Controlled%20Experiments%20at%20Large%20Scale.pdf)
