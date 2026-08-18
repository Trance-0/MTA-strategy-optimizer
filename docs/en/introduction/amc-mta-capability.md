---
title: AMC MTA Capability Assessment
compact: "Maturity assessment by dimension, recorded sample results including TVD, Spearman, and reliability counts, ranked risks, and a four-phase implementation order. Read for scope and risk judgment, not for field contracts."
lang: en-US
---

# AMC MTA Capability Assessment

## Final Assessment

The current project is best described as:

> An engineering-complete, contract-strict, reproducible AMC MTA attribution and dual-model diagnostic demonstration.

It is more than an algorithm sketch: input, paths, cost, models, comparison, governed output, and tests form a closed loop. It is not a production attribution system, causal-incrementality system, or automatic-budget system. The principal gaps are now real AMC evidence, stability, methodological calibration, and production-operation boundaries rather than whether the code runs.

## Layered Maturity

### engineering reliability

Assessment: relatively high. Evidence: reproducible execution and strict validation; recorded 107-test coverage of lineage, privacy, conservation, reliability, and rollback.

### attribution method

Assessment: medium. Evidence: complementary models with explicit semantics, but hand-worked benchmarks and real-data calibration remain necessary.

### data evidence

Assessment: low. Evidence: deterministic synthetic sample only; no real AMC query or cross-window evidence.

### business decision support

Assessment: very low. Evidence: model diagnostics and reliability only; no automatic-execution authority.

### demonstration completeness

Assessment: relatively high. Evidence: suitable for demonstration, teaching, interface review, and preparing real-data integration.

### production readiness

Assessment: low. Evidence: missing production data, stability, continuous integration, monitoring, and causal validation.

These assessments are recommendations based on the code, tests, inputs, and outputs reviewed by the source document. They are not statistical ratings and do not automatically apply to future data versions.

## Existing MTA Capabilities

### 1. AMC Path Input Capability

- A strict five-segment key distinguishes ad product, format, placement, creative, and impression/click.
- Converted users, purchase count, and revenue remain distinct.
- Path construction supports contiguous 14-day gaps, report-start truncation, and multiple-purchase segmentation.
- Each run accepts one account, marketplace, currency, and window and requires complete Ads daily coverage.
- Aggregate impressions and clicks are never used to fabricate user journeys.

### 2. Dual-Model Attribution Capability

- Markov uses order, repeated touchpoints, and removal effects.
- Path-level Shapley provides an order-independent path-participation benchmark.
- Three Outcomes are allocated and conserved independently.
- Impression and click remain independent five-segment primary results.
- The two models are not averaged, avoiding a false appearance of consensus between different assumptions.

### 3. Cost and Efficiency Capability

- Amazon Ads cost joins on the complete five-segment key.
- CPC belongs only to click, CPM only to impression, and cost is not duplicated.
- Output includes ROAS, ROI, order CPA, and cost per converted user.
- Platform-reported purchases/sales remain separate from AMC-attributed Outcomes.

### 4. Model Diagnostics and Reliability Capability

- Markov and Shapley shares, absolute percentage-point gaps, and relative gaps are compared per touchpoint and Outcome.
- Summaries calculate total variation distance, Spearman correlation, and Top-5 overlap.
- Impressions and clicks remain independent five-segment comparison records.
- Unique paths, converted users, and purchases are recalculated from raw AMC aggregates as support evidence.
- Binary reliability depends only on calculation validity, sufficient data support, and model consistency.
- The compact output has no budget-execution fields; stability remains a separate future artifact.

The recommendation table is a governed Markov display with a Shapley benchmark and reliability result. It is not a budget recommendation or automation permission.

## Current Sample Results

The migrated source recorded a deterministic snapshot rebuilt on 2026-07-29 from the unified user-event source. It contained 11,147 events, 2,400 synthetic users, 3,547 journeys, 153 unique aggregate paths, 17 five-segment touchpoints, 920 converted users, 1,023 purchases, and 87,802.83 revenue. Both models conserved all three Outcomes. These are historical sample facts; any changed input requires regeneration.

### Overall Differences

#### converted users

Five-segment TVD: 1.945%. Spearman rho: 0.8890. Top 5 overlap: 3/5. Interpretation: close shares with some head-ranking differences.

#### purchase count

Five-segment TVD: 1.975%. Spearman rho: 0.9111. Top 5 overlap: 3/5. Interpretation: close shares and broadly consistent ranking.

#### revenue

Five-segment TVD: 2.059%. Spearman rho: 0.9314. Top 5 overlap: 4/5. Interpretation: close shares and broadly consistent ranking.

Approximately two percent of contribution mass would have to move for the two models to agree. The accurate conclusion is that total shares are close while some leading ranks remain sensitive to model assumptions; synthetic results do not establish real-business stability.

### Largest Touchpoint Gap

The largest recorded gap across all Outcomes was the revenue record for:

`AMAZON_DSP:DISPLAY:UNSPECIFIED:IMAGE:IMPRESSION`

Its recorded revenue share was 6.129% under Markov and 6.660% under Shapley: a 0.532 percentage-point gap and approximately 8.32% relative gap. Compact output retains `gap_pp`, `relative_gap`, and `models_consistent` but no longer emits a difference grade or key-disagreement label.

### Current Reliability Result

The snapshot's 51 touchpoint/Outcome records were:

#### `calculation_valid=true`

Count: 51.

#### `data_support_sufficient=true`

Count: 51.

#### `models_consistent=true`

Count: 51.

#### `reliability_status=RELIABLE`

Count: 51.

#### `reliability_status=UNRELIABLE`

Count: 0.

Each Outcome summary AND-aggregated its touchpoint-level Booleans. Total variation distance, Spearman, and Top-K overlap remained supporting diagnostics and did not change reliability.

The three comparison outputs had compact 14/13/15-column contracts expressing gaps, support, reliability, and the governed point/model interval. They support diagnostics, human discussion, and real-data acceptance—not automatic budgeting.

## Position of the Two Models in Fast-Moving Consumer Goods

The governance design uses Markov as the official display because frequent exposure, short paths, repeated purchase, touch order, repetition, and non-converter information may be valuable in fast-moving consumer goods. Shapley is a benchmark for dependence on order and removal assumptions. Real AMC data and incremental experiments have not validated this choice.

Two methodological limits remain:

1. Purchase and revenue Markov models use only positive-Outcome paths, so they are weighted path-contribution allocations rather than full occurrence-probability removal effects.
2. Current Shapley is the exact equal allocation of a path unanimity game, not a general response Shapley model over all observed coalitions.

Therefore “Markov official, Shapley benchmark” is a governance choice, not proof that Markov is ground truth.

## Principal Risks

### High Priority

1. **Missing real data:** no AMC query SQL, privacy thresholds, query versions, or real aggregates.
2. **Unverified stability:** no rolling windows, 3/7/14-day sensitivity, or suitable resampling.
3. **Scope isolation:** event construction groups only by `journey_id`; reused identifiers across accounts could connect unrelated paths.
4. **Insufficient model benchmarks:** removal semantics, negative-effect clipping, and equal fallback lack hand-calculated gold cases.

### Medium Priority

5. Naive timestamps are interpreted as UTC, which may hide an upstream timezone error.
6. AMC paths omit currency, preventing direct revenue/cost currency validation.
7. Integer parsing through `float` may lose precision above `2**53`, and monetary calculations do not use `Decimal`.
8. Concurrent publication has no inter-process lock; a concurrent reader could briefly observe mixed versions.
9. There is no package, dependency lock, or continuous integration; scripts rely on local path injection.

See `_bmad-output/implementation-artifacts/amc_mta/deferred/deferred-work.md` for the recorded engineering backlog.

## Recommended Implementation Order

### Phase One: Prove Real AMC Usability

1. Fix the AMC query template, privacy threshold, field mapping, query version, and `data_as_of`.
2. Replace synthetic paths with multiple periods of real anonymous aggregates.
3. Add marketplace, advertiser, and currency to the complete scope key.
4. Establish input-snapshot manifests and reproducible run records.

### Phase Two: Establish Stability

1. Test 3/7/14-day path-window sensitivity.
2. Build at least eight rolling windows spanning promotion, non-promotion, and seasonality.
3. Rebuild from underlying journeys/periods or use parametric resampling appropriate to aggregate counts.
4. Report interval width, Top-5 inclusion rate, gap-direction consistency, and gap-band stability.

### Phase Three: Harden Method and Engineering

1. Add hand-calculated Markov removal cases and alternative removal-semantics comparisons.
2. Decide whether to retain path-level Shapley alone or add another response model as a third benchmark.
3. Adopt `Decimal`, strict schema handling, packaging, and continuous integration.
4. Publish through version directories plus an atomic manifest for stronger consistency.

### Phase Four: Validate Business Use

1. Use output for human review before any automatic budget adjustment.
2. Run incremental or quasi-experiments on leading, well-supported touchpoints.
3. Recalibrate version-one gap/support thresholds using real stability and experiment results.
4. Consider automation only after full support and stability evidence.

## Whether to Continue

The source recommendation was to continue from the present code and integrate real AMC data rather than rewrite immediately. That recommendation depends on real aggregate paths satisfying the contract, data volume remaining practical for batch processing, and hand-worked benchmarks not disproving model semantics. If any condition fails, compare refactoring with alternative approaches. While the goal remains MTA attribution alone, one focused module is preferable to prematurely expanding into prediction and budget-platform scope.
