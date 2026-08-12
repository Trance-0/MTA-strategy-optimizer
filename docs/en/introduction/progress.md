---
title: Progress and Todos
description: Implemented capabilities, known limitations, and next-stage priorities
lang: en-US
---

# Progress and Todos

## Implemented <span class="status-label status-verified" aria-label="Verified"></span>

- Deterministic processing and input validation for aggregated AMC-style paths.
- A five-segment touchpoint key: `AD_PRODUCT:FORMAT:PLACEMENT:CREATIVE:INTERACTION_TYPE`.
- Markov and path-level Shapley attribution for the three Outcomes `converted_users`, `purchase_count`, and `revenue`.
- Dual-model comparison, reliability flags, and recommended-attribution output.
- An entity Bridge from touchpoint attribution to Campaign.
- New Ad Group count calculation based on candidate capacity.
- An initial budget based on Campaign MTA scores and split equally within each Campaign.
- English VitePress navigation, GitHub Pages builds, and local PDF serving; Chinese source pages are preserved but currently excluded from publishing.

## Known Limitations <span class="status-label status-verified" aria-label="Verified"></span>

- The current strategy module is a deterministic budget initializer with `is_optimized=false`.
- New Ad Groups within one Campaign do not have distinguishable candidate-entity features, so the budget can only be split equally.
- MTA shares describe historical credit allocation; they are not marginal revenue from a budget increase.
- MTA-SIM's four-segment normalized touchpoints and this project's five-segment interaction-aware touchpoints are not directly interchangeable. `modules/mta_standard/` now bridges them through an explicit simulator configuration, but the fifth segment still cannot be recovered from four-segment data alone and must be supplied.
- `dnn_credit` is trained on path-level Shapley shares, so it is a learned surrogate of an observational method rather than an independent estimate, and its new-campaign prediction is a relative split rather than an outcome forecast.
- There is currently no rolling-window stability analysis, response curve, offline policy evaluation, or online experiment feedback loop.

## Next-Stage Todos <span class="status-label status-recommendation" aria-label="Recommendation"></span>

1. ~~**Build a data adapter layer**~~ — delivered in `modules/mta_standard/`: `SimulatorConfig` maps each four-segment key onto `CPC`/`CPM` and therefore onto `CLICK`/`IMPRESSION`, rejecting missing, ambiguous, and colliding mappings instead of guessing `INTERACTION_TYPE`. See [the standardized MTA interface](../attribution/standardized-interface/).
2. **Create an Ad Group feature table**: add candidate Keyword, SKU, Target, Audience, price, margin, inventory, historical Spend, and budget-limited status.
3. **Define one response model**: predict `expected_revenue(ad_group, budget)`. Start with one supervised model as an auditable baseline; do not introduce a multi-model agent workflow.
4. **Implement a constrained optimizer**: maximize expected revenue subject to total-budget, minimum-budget, capacity, and business-eligibility constraints.
5. **Validate offline**: use temporal splits, baseline comparisons, calibration, and sensitivity analysis; use synthetic Ground Truth only for final evaluation.
6. **Validate before launch**: evaluate incremental effects with a randomized controlled experiment or compliant Holdout, avoiding treatment of observational attribution as causal return.

## Definition of Done <span class="status-label status-recommendation" aria-label="Recommendation"></span>

The optimization module should be marked “optimized” only when all of the following are true: it can predict outcomes after budget changes, constraints are machine-validated, the plan outperforms an explicit baseline, results can be reproduced, and the output continues to state the boundary between observational and causal evidence.
