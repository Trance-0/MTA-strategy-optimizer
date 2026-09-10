---
title: Fitting Implementation
description: The deterministic grid-refined least-squares procedure, decomposed line by line
compact: "Line-by-line internals of `response_model.py`: the 5x10 spend grid, the 13-point kappa grid with closed-form ordinary least squares for baseline and alpha, non-negative clamps, TARGET_HISTORY/POOLED_TRANSFER/INSUFFICIENT_SUPPORT labelling, and reported diagnostics."
lang: en-US
order: 30
source_files: modules/mta_strategy_recommendation/src/response_model.py
test_files: modules/mta_strategy_recommendation/tests/test_response_model.py
---

# Fitting Implementation

## How It Is Implemented <span class="status-label status-verified" aria-label="Verified"></span>

Implementation: `modules/mta_strategy_recommendation/src/response_model.py`. The functional forms being fitted are specified on the [model and assumptions](./model-and-assumptions.md) page; this page specifies how their parameters are found.

Neither stage is fitted by gradient descent or by a general nonlinear least-squares routine. Each is fitted by exhaustive search over a fixed grid of the nonlinear parameter, scaled to the data's own magnitudes, with the linear parameters solved in closed form where they exist. This costs at most 65 candidate evaluations for the spend stage and 13 for the revenue stage, uses only the Python standard library, and is exactly reproducible.

The procedure has five parts: select the target-history route or the pooled route, fit the spend stage, fit the revenue stage, compute residual diagnostics, and label the evidence.

### Routing Each Campaign to a Fit

```python
grouped = dataset.by_campaign()                                     # 1
pooled_by_segment = _fit_pooled_models(grouped)                     # 2
models: dict[str, CampaignResponseModel] = {}
for campaign_id, observations in grouped.items():                   # 3
    target = _fit_single(campaign_id, observations,                 # 4
                         ResponseSupport.TARGET_HISTORY)
    if target is not None:                                          # 5
        models[campaign_id] = target
        continue
    pooled = pooled_by_segment.get(_segment_key(observations[0]))   # 6
    if pooled is not None:                                          # 7
        models[campaign_id] = replace(pooled, campaign_id=campaign_id)
        continue
    models[campaign_id] = _insufficient(campaign_id, observations)  # 8
return models
```

#### Line 1 — Group observations by Campaign

- Algorithm mapping: Establishes the per-Campaign evidence set each fit consumes
- Reason: One curve per Campaign is the model's grain; the Campaign is the optimization variable

#### Line 2 — Fit pooled models for every segment before any individual attempt

- Algorithm mapping: Precomputes the fallback so a Campaign that fails its own fit does not trigger a repeated pooled fit
- Reason: Pooling is a property of the segment, not of the Campaign that borrows it, so it is fitted once and shared

#### Lines 3-5 — Attempt the Campaign's own fit first, and use it when it succeeds

- Algorithm mapping: Assigns `TARGET_HISTORY` support
- Reason: A Campaign's own budget variation is the best available evidence for how that Campaign responds; a pooled curve is only a substitute

#### Lines 6-7 — Fall back to the segment's pooled model, restamped with this Campaign's identifier

- Algorithm mapping: Assigns `POOLED_TRANSFER` support while keeping the pooled diagnostics, including `pooled_campaign_ids`
- Reason: The borrowed parameters are real estimates, but they are not this Campaign's observed behavior, so both the label and the contributor list travel with them

#### Line 8 — Otherwise return a model that carries no curve

- Algorithm mapping: Assigns `INSUFFICIENT_SUPPORT` with both response stages `None`
- Reason: A Campaign with no usable evidence must be excluded from allocation, not given a falsely precise curve. Returning a model rather than omitting the Campaign keeps the diagnostics readable

### Evidence Thresholds and the Pooling Segment

```python
distinct_budgets = len({round(value, 6) for value in budgets})      # 1
if (len(observations) < MINIMUM_TARGET_OBSERVATIONS                 # 2
        or distinct_budgets < MINIMUM_DISTINCT_BUDGETS):            # 3
    return None
```

`MINIMUM_TARGET_OBSERVATIONS` is 4 and `MINIMUM_DISTINCT_BUDGETS` is 3.

#### Line 1 — Count distinct budgets at six decimal places

- Algorithm mapping: Defines what "a different budget" means
- Reason: Two arms differing in the tenth decimal are one budget level for fitting purposes, and rounding before the set comparison prevents floating-point noise from inflating the count

#### Lines 2-3 — Require both a minimum row count and a minimum number of distinct levels

- Algorithm mapping: Gates the `TARGET_HISTORY` route
- Reason: Twenty observations all at one budget contain no information about response. Both conditions must hold, because volume without variation and variation without volume each produce a curve the data cannot support

The same function is used for the pooled route, so a pooled fit faces the identical thresholds against its combined observation set.

Pooling is within a segment keyed by `(provider, ad_product, marketplace, currency)`, and requires at least two contributing Campaigns:

```python
for key, observations in segments.items():
    if len(contributors[key]) < 2:                                  # 1
        continue
    model = _fit_single(f"POOLED:{':'.join(key)}", observations,    # 2
                        ResponseSupport.POOLED_TRANSFER)
    if model is not None:
        pooled[key] = replace(model, diagnostics=replace(           # 3
            model.diagnostics,
            pooled_campaign_ids=tuple(sorted(contributors[key]))))
```

#### Line 1 — Require two or more distinct contributing Campaigns

- Algorithm mapping: Prevents a "pooled" model that is one Campaign's own history under another name
- Reason: A single-contributor pool would relabel one Campaign's curve as transferable evidence for a different Campaign without adding any

#### Line 2 — Fit the pool under a synthetic identifier

- Algorithm mapping: Names the model after its segment rather than any Campaign
- Reason: The pooled fit belongs to the segment; the borrowing Campaign's identifier is stamped on only at the point of transfer

#### Line 3 — Record every contributing Campaign, sorted

- Algorithm mapping: Populates `pooled_campaign_ids` in the diagnostics
- Reason: A reader must be able to see whose history a borrowed curve rests on. Sorting keeps the artifact deterministic

The segment uses ordinary decision-time Campaign attributes. It is unrelated to the dashboard's [presentation-only similarity](/en/introduction/data-models/presentation-only-similarity/) feature, which must never influence a fitted model.

### Fitting the Spend Stage

```python
highest_spend = max(spends)                                         # 1
if highest_spend <= 0:                                              # 2
    return None
capacity_grid = [highest_spend * factor                             # 3
                 for factor in (1.0, 1.15, 1.35, 1.6, 2.0)]
highest_budget = max(budgets) or highest_spend                      # 4
scale_grid = [highest_budget * factor for factor in                 # 5
              (0.1, 0.2, 0.35, 0.5, 0.75, 1.0, 1.5, 2.5, 4.0, 8.0)]
best = None; best_error = math.inf
for capacity in capacity_grid:                                      # 6
    for scale in scale_grid:
        if scale <= 0: continue                                     # 7
        candidate = SpendResponse(capacity=capacity, scale=scale)   # 8
        error = sum((candidate.expected_spend(budget) - spend) ** 2 # 9
                    for budget, spend in zip(budgets, spends))
        if error < best_error - 1e-12:                              # 10
            best_error = error; best = candidate
return best
```

#### Line 1 — Anchor the grid to the highest observed spend

- Algorithm mapping: Makes the search scale-free
- Reason: A Campaign spending in single dollars and one spending in thousands must both be searched at their own magnitude, without a hand-tuned absolute range

#### Line 2 — Refuse a Campaign that never spent

- Algorithm mapping: Returns `None`, routing the Campaign to pooling or insufficiency
- Reason: A capacity grid anchored at zero would be all zeros, and a Campaign with no spend has no delivery behavior to fit

#### Line 3 — Search capacities at or above the highest observed spend

- Algorithm mapping: Five multipliers from 1.0 to 2.0
- Reason: Capacity is a ceiling, so it cannot be below what was already spent. The upper multiplier of 2.0 admits a Campaign whose observed range never approached its ceiling, without letting capacity run away from the evidence

#### Line 4 — Anchor the scale grid to the highest budget, falling back to highest spend

- Algorithm mapping: Uses `or` so a zero or absent maximum budget degrades to the spend magnitude
- Reason: Scale is measured in budget units, and a dataset whose budgets are all zero would otherwise produce an all-zero grid rejected at line 7

#### Line 5 — Search ten scales spanning two orders of magnitude

- Algorithm mapping: Factors 0.1 through 8.0 of the highest budget
- Reason: The low end represents a Campaign that saturates almost immediately; the high end one whose spend is effectively linear across the observed range. Both are real delivery behaviors

#### Lines 6-7 — Exhaust the 50-point product, skipping non-positive scales

- Algorithm mapping: Full grid search rather than a descent
- Reason: Fifty evaluations are cheap, and exhaustive search cannot land in a local minimum

#### Line 8 — Construct each candidate through the dataclass

- Algorithm mapping: Routes every candidate through `__post_init__`
- Reason: The sign constraints are enforced at construction, so an invalid candidate cannot be scored and silently win

#### Line 9 — Score by sum of squared residuals against the capped expectation

- Algorithm mapping: Uses `expected_spend`, which applies the `min(B, ...)` budget cap
- Reason: The cap is part of the model, so the fit must be scored against the same function the optimizer will later call

#### Line 10 — Accept a new best only when it improves by more than `1e-12`

- Algorithm mapping: Strict improvement threshold
- Reason: Ties resolve to the earlier grid point, which makes the winner independent of floating-point ordering and keeps the fit byte-reproducible

### Fitting the Revenue Stage

The revenue stage has one nonlinear parameter and two linear ones, so only `kappa` is searched; `baseline` and `alpha` follow in closed form for each candidate.

```python
highest_spend = max(spends)
if highest_spend <= 0 or len(spends) < 2:                           # 1
    return None
for factor in (0.05, 0.1, 0.15, 0.25, 0.35, 0.5, 0.75,              # 2
               1.0, 1.5, 2.0, 3.0, 5.0, 8.0):
    kappa = highest_spend * factor
    if kappa <= 0: continue
    basis = [1.0 - math.exp(-spend / kappa) for spend in spends]    # 3
    solved = _least_squares_intercept_slope(basis, revenues)        # 4
    if solved is None: continue                                     # 5
    baseline, alpha = solved
    candidate = RevenueResponse(baseline=max(0.0, baseline),        # 6
                                alpha=max(0.0, alpha), kappa=kappa)
    error = sum((candidate.expected_revenue(spend) - revenue) ** 2  # 7
                for spend, revenue in zip(spends, revenues))
    if error < best_error - 1e-12:                                  # 8
        best_error = error; best = candidate
return best
```

#### Line 1 — Require positive spend and at least two observations

- Algorithm mapping: Returns `None`, routing the Campaign to pooling or insufficiency
- Reason: A line through fewer than two points is underdetermined, and zero spend gives a degenerate basis

#### Line 2 — Search thirteen `kappa` values from 0.05 to 8.0 times the highest observed spend

- Algorithm mapping: Denser at the low end than the high end
- Reason: Small `kappa` values differ sharply from one another in curvature across the observed range, while large ones all approach the same near-linear shape, so resolution is spent where it changes the fit

#### Line 3 — Transform spend into the saturating basis for this `kappa`

- Algorithm mapping: Converts the nonlinear problem into a linear one conditional on `kappa`
- Reason: With `kappa` fixed, revenue is exactly linear in `1 - exp(-S/kappa)`, so the remaining two parameters have an exact solution rather than needing a search

#### Line 4 — Solve intercept and slope in closed form by ordinary least squares

- Algorithm mapping: `baseline` is the intercept, `alpha` the slope
- Reason: An exact solution for the linear parameters removes two dimensions from the search, which is what keeps the whole fit to thirteen evaluations

#### Line 5 — Skip a `kappa` whose basis is degenerate

- Algorithm mapping: `_least_squares_intercept_slope` returns `None` when basis variance is at or below `1e-12`
- Reason: A `kappa` so small that every observation saturates to 1.0 gives a constant basis with no slope to estimate; dividing by its variance would be meaningless

#### Line 6 — Clamp both linear parameters non-negative

- Algorithm mapping: `max(0.0, ...)` before construction
- Reason: This is where concavity is imposed rather than discovered. A Campaign whose data implied negative advertising effect is fitted with `alpha` at zero — a flat curve — rather than a decreasing one the optimizer could not solve against

#### Line 7 — Score the clamped candidate, not the unclamped solution

- Algorithm mapping: Residuals computed from `expected_revenue` after clamping
- Reason: The clamp changes the curve, so scoring the pre-clamp solution would select a `kappa` on the strength of a curve that is not the one returned

#### Line 8 — Same strict-improvement tie-breaking as the spend stage

- Algorithm mapping: `1e-12` threshold
- Reason: Reproducibility, identically to the spend stage

### The Closed-Form Solution

```python
mean_basis = _mean(basis); mean_target = _mean(targets)
variance = sum((value - mean_basis) ** 2 for value in basis)        # 1
if variance <= 1e-12: return None                                   # 2
covariance = sum((value - mean_basis) * (target - mean_target)      # 3
                 for value, target in zip(basis, targets))
slope = covariance / variance                                       # 4
return mean_target - slope * mean_basis, slope                      # 5
```

Lines 1 through 5 are the textbook simple-regression estimator: slope is covariance over variance, and the intercept is whatever passes the fitted line through the means. Line 2 is the guard described above. No matrix library is involved, which is what allows the module to depend on the standard library alone.

## Evidence Support Labels <span class="status-label status-verified" aria-label="Verified"></span>

Every fit carries a `ResponseSupport` label, so a borrowed curve is never mistaken for observed behavior.

### `TARGET_HISTORY`

Fitted from that Campaign's own budget variation, having met both thresholds.

### `POOLED_TRANSFER`

Fitted from comparable Campaigns because the target Campaign lacks sufficient variation of its own. The borrowed model records `pooled_campaign_ids`. These estimates are legitimate but are not that Campaign's observed behavior, and both the artifact and the dashboard say so.

### `INSUFFICIENT_SUPPORT`

Neither route is possible. The Campaign is returned with `spend_response` and `revenue_response` both `None`, `is_usable` false, and both fit statuses `UNFITTED`. The optimizer excludes it. Calling `expected_spend()`, `expected_revenue_from_spend()`, `expected_revenue()`, or `marginal_expected_revenue()` raises `ResponseModelError` rather than returning a number that would look like an estimate.

## Reported Diagnostics <span class="status-label status-verified" aria-label="Verified"></span>

`ResponseDiagnostics` accompanies every model, fitted or not.

### `support`

The `ResponseSupport` label above.

### `observation_count`

Campaign-periods the fit consumed.

### `intervention_count`

How many of those carried a recorded intervention. Equal to `observation_count` when every period was an experimental arm.

### `distinct_budget_count`

Distinct configured budgets observed, at six-decimal rounding.

### `observed_budget_range`, `observed_spend_range`

Lowest and highest configured budget, and lowest and highest actual spend. The budget range is what later decides whether an optimized budget is an extrapolation.

### `spend_fit_status`, `revenue_fit_status`

`FITTED` when that stage produced usable parameters, `UNFITTED` when it did not. `DEGENERATE` exists in the enumeration but is not currently assigned by the fitting path.

### `spend_mean_absolute_error`

Mean absolute residual of the spend stage, in currency units. A value of zero means every observed spend equalled its predicted spend, which happens when a Campaign spent exactly its budget in every period.

### `revenue_mean_absolute_error`, `revenue_root_mean_square_error`

Mean absolute and root mean square residuals of the revenue stage. Both are reported because the second penalizes large misses more heavily, so a gap between them indicates a few badly fitted periods rather than uniform error.

### `model_version`

`CAMPAIGN_RESPONSE_V1`.

### `pooled_campaign_ids`

Contributing Campaigns for a `POOLED_TRANSFER` fit; empty otherwise.

All diagnostics are in-sample. See the [assumptions](./model-and-assumptions.md).

## Serialization <span class="status-label status-verified" aria-label="Verified"></span>

`CampaignResponseModel.to_dict()` emits `model_id` as `CAMPAIGN_RESPONSE_V1:<campaign_id>`, plus `model_version`, `campaign_id`, `currency`, both stages' parameters or `null`, and the diagnostics. `to_str()` serializes with sorted keys and compact separators. `from_dict` and `from_str` rebuild the exact curve, so a stored artifact reproduces the model that produced a past recommendation.

`response_models_to_dict(models)` wraps every model as `{"model_version": ..., "campaign_models": {...}}` with Campaigns sorted by identifier. `response_models_from_dict(payload)` reverses it.

## Source Files <span class="status-label status-verified" aria-label="Verified"></span>

### `response_model.py`

Source: `modules/mta_strategy_recommendation/src/response_model.py`

**Responsibility.** Fit the two-stage budget-to-spend-to-revenue response per Campaign, label the evidence behind each fit, and report fit quality. Contains no allocation logic.

**Public entry points.** `fit_campaign_response_models(dataset) -> Mapping[str, CampaignResponseModel]`, plus `response_models_to_dict()` and `response_models_from_dict()` for the serialized artifact. `CampaignResponseModel` exposes `is_usable`, `expected_spend()`, `expected_revenue_from_spend()`, `expected_revenue()`, `marginal_expected_revenue(configured_budget, step=1.0)`, `is_extrapolating()`, and the four serialization methods.

**Inputs.** A `CampaignResponseDataset` from `response_dataset.py`.

**Outputs.** One `CampaignResponseModel` per Campaign present in the dataset, including Campaigns that could not be fitted. Every Campaign in the input appears in the output.

**Dependencies.** Standard library only: `dataclasses`, `enum`, `json`, `math`, `typing`. Plus `response_dataset` for its two input types.

**Contract.** `MODEL_VERSION` is `CAMPAIGN_RESPONSE_V1`. `SpendResponse` requires non-negative capacity and positive scale; `RevenueResponse` requires non-negative baseline and alpha and positive kappa; both reject violations with `ValueError`, which is what keeps every fitted curve increasing and concave. Fitting is deterministic and byte-reproducible. A Campaign needs at least 4 observations across at least 3 distinct budgets for `TARGET_HISTORY`; pooling requires at least 2 contributing Campaigns in a `(provider, ad_product, marketplace, currency)` segment.

**Errors.** `ResponseModelError` when an unusable model is asked for an estimate, or when `marginal_expected_revenue` receives a non-positive step.

**Verification.** `modules/mta_strategy_recommendation/tests/test_response_model.py`.

## Verification

- **Scope:** The fitting procedure, evidence labelling, diagnostics, and serialization round-trip.
- **Cases:** Both grids selecting the best candidate; closed-form intercept and slope; non-negative clamping; threshold gating for target history; pooled segmentation and contributor recording; insufficient-support behavior and its raised errors; `to_dict`/`from_dict` and `to_str`/`from_str` round-trips.
- **Command:** `uv run python -X utf8 -B -m unittest modules.mta_strategy_recommendation.tests.test_response_model`.
- **Limitations:** In-sample only. The tests verify that the procedure finds the best candidate on its own grid, not that the grid contains the true parameters.
