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

`AD_PRODUCT:FORMAT:PLACEMENT:CREATIVE:INTERACTION_TYPE`

### Customer Path

An ordered sequence of touchpoints in the observation window, separated with ` > `.

### Outcome

A business result to which the model allocates credit. This project includes unique converted users, purchase count, and revenue.

### Campaign Group, Campaign, and Ad Group

The project uses the `Campaign Group → Campaign → Ad Group → Keyword/SKU/Target/Audience` hierarchy. `ad_product` is a Campaign attribute, not an independent level.

## Advertising Platform Terms <span class="status-label status-verified" aria-label="Verified"></span>

### ASIN (Amazon Standard Identification Number)

A unique identifier for a product sold on Amazon. While a [SKU](#sku-stock-keeping-unit) is a seller-defined identifier, an ASIN is Amazon-assigned and consistent across all sellers of the same product.

### SKU (Stock Keeping Unit)

A seller-defined unique identifier for a sellable item within a platform and marketplace. One Product may map to multiple SKUs. See also [ASIN](#asin-amazon-standard-identification-number).

### CPC (Cost Per Click)

A billing model where the advertiser pays for each click on their ad. In this project, `CPC` cost is assigned only to `CLICK` interaction types.

### CPM (Cost Per Mille / Cost Per Thousand Impressions)

A billing model where the advertiser pays per thousand impressions. In this project, `CPM` cost is assigned only to `IMPRESSION` interaction types.

### DSP (Demand-Side Platform)

Amazon's programmatic advertising platform that allows advertisers to buy display, video, and audio ads programmatically. In this project, DSP is one of the four ad products alongside SP, SB, and SD.

### SP (Sponsored Products)

Cost-per-click ads for individual product listings on Amazon, appearing in search results and product detail pages.

### SB (Sponsored Brands)

Cost-per-click ads featuring a brand logo, custom headline, and multiple products, appearing in prominent search result positions.

### SD (Sponsored Display)

Display ads that target relevant audiences both on and off Amazon, using interest-based or product-based targeting.

### Impression

An ad display event counted when an ad is rendered on screen. Together with [CLICK](#click), it is one of the two `INTERACTION_TYPE` values used in this project's five-segment touchpoint key.

### Click

A user interaction event where a user clicks on an ad. Together with [IMPRESSION](#impression), it is one of the two `INTERACTION_TYPE` values used in this project's five-segment touchpoint key.

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

## Evaluation Metrics <span class="status-label status-verified" aria-label="Verified"></span>

### MAE (Mean Absolute Error)

The average of the absolute differences between predicted and actual values. It tells you how far off your estimates are on average, in the same units as the original numbers. A lower MAE means better accuracy. Unlike [RMSE](#rmse-root-mean-squared-error), MAE treats all errors equally regardless of size.

### RMSE (Root Mean Squared Error)

The square root of the average squared differences between predicted and actual values. It penalizes large errors more heavily than small ones, so a single bad prediction has a bigger impact on RMSE than on [MAE](#mae-mean-absolute-error). Like MAE, lower is better.

### TVD (Total Variation Distance)

Half the sum of absolute differences between two probability distributions, point by point. It ranges from 0 (identical distributions) to 1 (completely different). In this project, TVD compares the full attribution-share vector from a model against either another model or the ground truth. It answers "how different are these two allocations overall?" rather than "which touchpoint differs most?"

### Spearman's Rho (Spearman Rank Correlation, ρ)

A measure of how well two rankings agree, ranging from -1 (perfectly reversed) to +1 (perfectly identical). Unlike a direct share comparison, rho cares only about order: do Markov and Shapley rank the same touchpoints as most important? A rho of `None` means one set of values has no ranking (e.g., uniform equal shares), which is a deliberate signal rather than a measurement failure.

### Top-K Overlap

The fraction of the top K touchpoints (by attribution share) that two models agree on. For example, Top-5 overlap of 0.8 means 4 of the top 5 touchpoints appear in both models' top 5. It measures agreement among the most important touchpoints specifically, complementing [TVD](#tvd-total-variation-distance) which measures distribution-wide agreement.

### Conservation Error

The difference between a model's sum of allocated shares and the required total (1 for shares, the observed outcome total for values). A value of zero means the model perfectly conserved the input total. Non-zero values indicate a calculation defect.

### L1 Distance (Manhattan Distance)

The sum of absolute differences between two vectors across all dimensions. In this project, [TVD](#tvd-total-variation-distance) is defined as half the L1 distance between share vectors, normalizing the result to [0, 1].

## Technical Terms <span class="status-label status-verified" aria-label="Verified"></span>

### CSV (Comma-Separated Values)

A plain-text tabular data format where each line is a row and commas separate columns. All data inputs and outputs in this project use CSV with a header row. Leading and trailing whitespace is stripped before validation.

### ISO Date Format

An internationally standardized date representation (`YYYY-MM-DD`, e.g., `2026-01-01`). All dates in project data contracts must use this format. The standard is maintained by the [International Organization for Standardization](https://www.iso.org).

### UTC (Coordinated Universal Time)

The primary time standard by which the world regulates clocks. All timestamps in project data are stored and compared in UTC to avoid timezone-related ordering inconsistencies.

### SHA-256 (Secure Hash Algorithm 256-bit)

A cryptographic hash function that produces a 256-bit (32-byte) fingerprint of any data. The strategy module uses SHA-256 digests to verify that the AMC attribution and entity evidence files have not changed since the strategy request was created.

### DNN (Deep Neural Network)

A machine learning model with multiple layers of interconnected nodes. In this project, the [DNN credit model](/en/attribution/standardized-interface/dnn) learns to predict attribution shares from touchpoint segment structure, enabling predictions for campaigns with no historical path data.

### SHAP (SHapley Additive exPlanations)

A widely used library for explaining model predictions using Shapley values. This project's Shapley implementation is an exact closed-form solution for a specific path-unanimity game and does not use the SHAP package. The two should not be confused.

### JSON (JavaScript Object Notation)

A lightweight text-based data interchange format. Strategy requests and outputs in this project use JSON.

### API (Application Programming Interface)

A defined way for one program to request services from another. In this project, Amazon Ads API and Amazon Marketing Cloud API provide the upstream data that feeds into attribution and strategy calculations.

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

### ROI (Return on Investment)

Attributed revenue minus advertising cost, divided by advertising cost: `(revenue - cost) / cost`. Unlike [ROAS](#roas-return-on-ad-spend), ROI subtracts the cost and can be negative when costs exceed revenue. Both are calculated per touchpoint in this project's model outputs.

### CPA (Cost Per Acquisition / Cost Per Action)

Advertising cost divided by attributed purchase count: `cost / attributed purchases`. It answers "how much did I spend for each purchase attributed to this touchpoint?" A lower CPA is generally better, but it must be interpreted alongside revenue and ROAS — a very low CPA on very few purchases may not be meaningful.

### Cost Per Converted User

Advertising cost divided by attributed converted users. Similar to [CPA](#cpa-cost-per-acquisition--cost-per-action) but uses unique purchasing users rather than order count as the denominator. The two diverge when a single user purchases multiple times.

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
