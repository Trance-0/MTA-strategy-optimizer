---
title: Terms and Abbreviations
description: Attribution, advertising hierarchy, data, and optimization terminology
lang: en-US
---

# Terms and Abbreviations

This page defines the specific meaning of terms in this project for readers who understand basic marketing or data analysis but may not be familiar with advertising-attribution systems.

## Core Business Terms <span class="status-label status-verified" aria-label="Verified"></span>

### AMC (Amazon Marketing Cloud)

Amazon Marketing Cloud is a privacy-safe analytics environment. AMC-style paths in this project are aggregated demonstration data and do not imply that user-level details can be exported.

### MTA (Multi-Touch Attribution)

A method for allocating Outcome credit among multiple historical marketing touchpoints. This project runs Markov and path-level Shapley.

### Touchpoint

One classifiable advertising interaction. This project uses a five-segment normalized key:

```text
AD_PRODUCT:FORMAT:PLACEMENT:CREATIVE:INTERACTION_TYPE
```

### Customer Path

An ordered sequence of touchpoints in the observation window, separated with ` > `.

### Outcome

A business result to which the model allocates credit. This project includes unique converted users, purchase count, and revenue.

### Campaign Group, Campaign, and Ad Group

The project uses the `Campaign Group → Campaign → Ad Group → Keyword/SKU/Target/Audience` hierarchy. `ad_product` is a Campaign attribute, not an independent level.

## Attribution Terms <span class="status-label status-verified" aria-label="Verified"></span>

### Attribution Share

The proportion of one Outcome that a touchpoint receives after allocation across all touchpoints. Shares for the same Outcome sum to 1.

### Markov Chain

A model describing paths with state-transition probabilities. This project calculates credit from the decrease in conversion probability when a touchpoint is removed.

### Removal Effect

The non-negative estimated decrease in conversion probability relative to baseline after a touchpoint is removed from the transition network.

### Shapley Value

A fair credit allocation from cooperative game theory. This project's path-unanimity implementation splits one path's Outcome equally among its unique touchpoints.

### Causal Incrementality

The additional Outcome actually caused by advertising relative to the “no advertising” counterfactual. An observational MTA attribution share does not automatically equal causal incrementality.

## Strategy and Optimization Terms <span class="status-label status-verified" aria-label="Verified"></span>

### Budget Seed

An explainable initial budget for later review or optimization. Current output is a Seed, not an optimum.

### Response Curve

A function relating budget or Spend to expected Outcome. Saturation means the marginal return from additional budget gradually declines.

### Marginal Revenue

Expected additional revenue from one added unit of budget. Budget optimization must estimate it; it is not the same as historically attributed revenue.

### Constraint

A rule that an optimized plan must satisfy, such as total budget, minimum budget, inventory, activation eligibility, or budget increment.

### ROAS (Return on Ad Spend)

Attributed revenue divided by advertising Spend. ROAS is a ratio and must not be confused with maximizing total revenue or profit as though they were the same objective.

## Data Governance Terms <span class="status-label status-verified" aria-label="Verified"></span>

### Ground Truth

A reference answer used to evaluate a model. MTA-SIM's `simulation_ground_truth` is valid only for the synthetic mechanism and is prohibited as a training feature.

### Data Leakage

Using information during training that is unavailable at decision time—for example, using Ground Truth as an input—which produces a misleading evaluation.

### Repository Fact / External / Inference / Recommendation

- <span class="status-label status-verified" aria-label="Verified"></span> **Verified**: confirmed directly by code or data in this repository.
- <span class="status-label status-external" aria-label="External"></span> **External**: from a cited external repository or source.
- <span class="status-label status-inference" aria-label="Inference"></span> **Inference**: an evidence-based interpretation rather than direct measurement.
- <span class="status-label status-recommendation" aria-label="Recommendation"></span> **Recommendation**: a design or next step pending review.
