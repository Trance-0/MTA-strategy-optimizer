---
title: Progress and Todos
description: Implemented capabilities, known limitations, and next-stage priorities
compact: "Authoritative status list: implemented capabilities through the Campaign response model, constrained optimizer, and strategy evaluation layer; known limitations such as equal within-Campaign splits; and the remaining todos toward Ad Group grain and causal validation."
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
- A Campaign budget response model and constrained optimizer, and a strategy evaluation layer that projects both strategy artifacts onto one contract, checks allocation conservation, and compares each against observed baselines.
- English VitePress navigation, GitHub Pages builds, and local PDF serving; Chinese source pages are preserved but currently excluded from publishing.

## Known Limitations <span class="status-label status-verified" aria-label="Verified"></span>

- The deterministic budget initializer still reports `is_optimized=false`; only the separate Campaign budget optimizer reports `is_optimized=true`, and only when observed budget variation supports a fitted response curve.
- New Ad Groups within one Campaign do not have distinguishable candidate-entity features, so the budget can only be split equally.
- MTA shares describe historical credit allocation; they are not marginal revenue from a budget increase.
- Current MTA-SIM and this project share native five-segment interaction-aware values. Historical four-segment fixtures remain supported only through an explicit `SimulatorConfig`; their missing interaction still cannot be inferred from delivery metrics.
- `dnn_credit` is trained on path-level Shapley shares, so it is a learned surrogate of an observational method rather than an independent estimate, and its new-campaign prediction is a relative split rather than an outcome forecast.
- There is currently no rolling-window stability analysis, response curve, offline policy evaluation, or online experiment feedback loop.

## Next-Stage Todos <span class="status-label status-recommendation" aria-label="Recommendation"></span>

1. ~~**Build a data adapter layer**~~ — delivered in `modules/mta_standard/`: native five-segment values pass through unchanged; `SimulatorConfig` remains only for historical four-segment input and rejects missing, ambiguous, and colliding mappings. See [the standardized MTA interface](../attribution/standardized-interface/).
2. **Create an Ad Group feature table**: add candidate Keyword, SKU, Target, Audience, price, margin, inventory, historical Spend, and budget-limited status.
3. ~~**Define one response model**~~ — delivered at Campaign rather than Ad Group grain in `modules/mta_strategy_recommendation/`: one auditable fitted response curve per Campaign, no multi-model agent workflow. Ad Group grain still waits on item 2. See [the Campaign budget optimizer](../strategy-recommendation/campaign-budget-optimizer.md).
4. ~~**Implement a constrained optimizer**~~ — delivered in the same module, maximizing expected revenue subject to total-budget, minimum-budget, and eligibility constraints, and refusing rather than guessing when budget variation has not been observed.
5. **Validate offline**: baseline comparison is delivered in `modules/mta_strategy_evaluation/`, which scores each strategy against equal-split and observed-budget baselines. Temporal splits, calibration, and sensitivity analysis remain; synthetic Ground Truth stays reserved for final evaluation, and no simulator publishes a true optimal allocation yet. See [evaluation layers](../strategy-evaluation/evaluation-layers.md).
6. **Validate before launch**: evaluate incremental effects with a randomized controlled experiment or compliant Holdout, avoiding treatment of observational attribution as causal return.

## Definition of Done <span class="status-label status-recommendation" aria-label="Recommendation"></span>

The optimization module should be marked “optimized” only when all of the following are true: it can predict outcomes after budget changes, constraints are machine-validated, the plan outperforms an explicit baseline, results can be reproduced, and the output continues to state the boundary between observational and causal evidence.
