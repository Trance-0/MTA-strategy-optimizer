---
title: Optimizer Implementation
description: The constrained allocation problem and the shadow-price bisection that solves it, decomposed line by line
compact: "Line-by-line internals of `budget_optimizer.py`: the constrained revenue maximization, the outer price bisection and inner per-Campaign demand bisection, `_search_ceiling`, remainder distribution, independent post-validation tolerances, and the five structured refusals."
lang: en-US
order: 40
source_files: modules/mta_strategy_recommendation/src/budget_optimizer.py
test_files: modules/mta_strategy_recommendation/tests/test_budget_optimizer.py
---

# Optimizer Implementation

## The Problem <span class="status-label status-verified" aria-label="Verified"></span>

The optimizer chooses Campaign budgets $b_1 \ldots b_n$ solving:

$$
\max_{b} \sum_c \hat{R}_c(b_c)
$$

subject to $\sum_c b_c = B_{\text{total}}$ under `SPEND_FULL_BUDGET`, or $\sum_c b_c \le B_{\text{total}}$ under `SPEND_UP_TO_BUDGET`, and $\text{minimum}_c \le b_c \le \text{maximum}_c$ for every Campaign.

$\hat{R}_c$ is the composed response from the [model page](./model-and-assumptions.md): budget determines spend, spend determines revenue. An absent minimum is treated as zero; an absent maximum as unbounded.

## Why a Shadow Price Rather Than a General Solver <span class="status-label status-verified" aria-label="Verified"></span>

Because each fitted $\hat{R}_c$ is separable, increasing, and concave, the optimum has a structure worth exploiting. There is exactly one price of budget $\lambda$ at which every interior Campaign's marginal expected revenue is equal:

$$
\frac{\partial \hat{R}_c}{\partial b_c} = \lambda \quad \text{for every Campaign not sitting at a bound}
$$

The reasoning is direct. If two unconstrained Campaigns had different marginal returns, moving one unit of budget from the lower to the higher would raise total revenue, so the allocation was not optimal. Campaigns whose floor or ceiling binds sit at that bound, which is precisely what the equal-marginal condition requires at a constrained optimum.

Each Campaign's demand for budget falls as $\lambda$ rises, because its marginal revenue is decreasing in its own budget. Total demand is therefore monotone in $\lambda$, and a bisection converges on the price that exhausts the authorized budget. The solver is deterministic, auditable, and needs no external dependency.

The marginal return is taken as a forward difference over the *composed* response, with a step of one currency unit, so the spend stage's own saturation is included. A derivative of the revenue stage alone would miss a Campaign that has stopped being able to spend what it is given.

## How It Is Implemented <span class="status-label status-verified" aria-label="Verified"></span>

Implementation: `modules/mta_strategy_recommendation/src/budget_optimizer.py`. `_PRICE_ITERATIONS` is 200 and `_ALLOCATION_TOLERANCE` is `1e-6`.

`optimize_campaign_budgets()` runs six gates in a fixed order, and each may return a structured refusal instead of continuing: objective check, request validation, eligibility filtering, feasibility check, solve, and post-validation.

### Eligibility Filtering

```python
active = [item for item in requests if item.is_active]              # 1
excluded = [item.campaign_id for item in requests if not item.is_active]
supported = []
for request in active:
    model = response_models.get(request.campaign_id)                # 2
    if model is None or not model.is_usable:                        # 3
        excluded.append(request.campaign_id)
        continue
    supported.append((request, model))
```

#### Line 1 — Separate inactive Campaigns before consulting any model

- Algorithm mapping: An inactive Campaign is excluded regardless of how well it fitted
- Reason: Eligibility is a business fact, not a modelling one, so it is decided first

#### Lines 2-3 — Exclude a Campaign with no model or an unusable one

- Algorithm mapping: `is_usable` is false for `INSUFFICIENT_SUPPORT` and for any model missing either stage
- Reason: A Campaign whose curve could not be estimated cannot be allocated against. Naming it in `excluded_campaign_ids` rather than dropping it silently keeps "received no budget" distinguishable from "was never considered"

### The Outer Price Bisection

```python
def demand(price):                                                  # 1
    return {request.campaign_id: _campaign_demand(request, model, price)
            for request, model in supported}
def total(price):
    return sum(demand(price).values())

if (budget_usage_policy == BudgetUsagePolicy.SPEND_UP_TO_BUDGET     # 2
        and total(0.0) <= total_budget + _ALLOCATION_TOLERANCE):
    return demand(0.0)                                              # 3

low_price = 0.0
high_price = max(_highest_marginal(request, model)                  # 4
                 for request, model in supported) + 1.0
for _ in range(_PRICE_ITERATIONS):                                  # 5
    mid_price = (low_price + high_price) / 2.0
    if total(mid_price) > total_budget:                             # 6
        low_price = mid_price
    else:
        high_price = mid_price
    if high_price - low_price < 1e-12: break                        # 7
budgets = demand(high_price)                                        # 8

allocated = sum(budgets.values())
remainder = total_budget - allocated
if (budget_usage_policy == BudgetUsagePolicy.SPEND_FULL_BUDGET      # 9
        and remainder > _ALLOCATION_TOLERANCE):
    budgets = _distribute_remainder(supported, budgets, remainder)
```

#### Line 1 — Express total demand as a function of one scalar price

- Algorithm mapping: Reduces an $n$-dimensional allocation to a one-dimensional root find
- Reason: This is the whole benefit of the shadow-price formulation; without it the problem would need a general constrained optimizer

#### Lines 2-3 — Short-circuit when the budget does not bind

- Algorithm mapping: At price zero every Campaign wants its maximum; if that fits under `SPEND_UP_TO_BUDGET`, return it
- Reason: When the authorized budget exceeds what every Campaign can use, there is no scarcity to price. Bisecting anyway would converge to zero and waste 200 iterations

#### Line 4 — Bracket the price above every Campaign's marginal revenue at its floor

- Algorithm mapping: Highest marginal at any minimum, plus one
- Reason: At a price above every Campaign's best marginal return, all demand collapses to the floors, which guarantees the upper bracket produces total demand at or below the target and the bisection is valid

#### Lines 5-6 — Bisect: raise the floor when demand overshoots, lower the ceiling otherwise

- Algorithm mapping: Standard bisection on a monotone decreasing function
- Reason: `total` is non-increasing in price because each Campaign's own demand is, so the sign of the comparison identifies which half contains the root

#### Line 7 — Stop early once the bracket closes to `1e-12`

- Algorithm mapping: Absolute width termination inside a fixed 200-iteration cap
- Reason: The cap bounds worst-case work and guarantees termination regardless of the function's behavior; the early exit avoids pointless iterations once the price is resolved

#### Line 8 — Take demand at the *upper* price, not the midpoint

- Algorithm mapping: `high_price` is the side of the bracket whose demand fits within the budget
- Reason: The invariant maintained by lines 5-6 is that `high_price` never overshoots. Reading demand there means the returned allocation cannot exceed the authorized total, which the post-validation then confirms independently

#### Line 9 — Distribute any shortfall only under `SPEND_FULL_BUDGET`

- Algorithm mapping: Calls `_distribute_remainder` when budget is left over
- Reason: Under `SPEND_UP_TO_BUDGET` a shortfall is a correct answer: it means no Campaign could use the rest. Under `SPEND_FULL_BUDGET` the policy requires spending it anyway

### The Inner Demand Bisection

Each Campaign's demand at a given price is itself found by bisection, because the composed response has no closed-form inverse for its marginal.

```python
minimum = _minimum(request); maximum = _maximum(request)
if maximum <= minimum: return minimum                               # 1
ceiling = maximum if math.isfinite(maximum) else _search_ceiling(model)  # 2
if model.marginal_expected_revenue(minimum) <= price:               # 3
    return minimum
if model.marginal_expected_revenue(ceiling) >= price:               # 4
    return ceiling
low, high = minimum, ceiling
for _ in range(_PRICE_ITERATIONS):                                  # 5
    mid = (low + high) / 2.0
    if model.marginal_expected_revenue(mid) > price:
        low = mid
    else:
        high = mid
    if high - low < _ALLOCATION_TOLERANCE: break                    # 6
return (low + high) / 2.0                                           # 7
```

#### Line 1 — Return the floor when the bounds leave no room

- Algorithm mapping: Handles a Campaign whose minimum equals its maximum
- Reason: A pinned Campaign has exactly one feasible budget; searching for it would divide a degenerate interval

#### Line 2 — Substitute a finite search ceiling for an unbounded Campaign

- Algorithm mapping: `_search_ceiling` returns `max(observed_budget_high, spend_scale, 1.0) * 8.0`
- Reason: Bisection needs a finite bracket. Beyond a few multiples of the observed range and the fitted spend scale the composed curve is flat, so this bounds the search without changing the optimum. The `1.0` floor protects against a Campaign whose observed budgets and fitted scale are both near zero

#### Line 3 — Clamp to the floor when even the floor's marginal return is below the price

- Algorithm mapping: Corner solution at the minimum
- Reason: Budget costs more than this Campaign can earn with it, so it takes only what its floor forces

#### Line 4 — Clamp to the ceiling when even the ceiling's marginal return is above the price

- Algorithm mapping: Corner solution at the maximum
- Reason: This Campaign would take more if allowed; its bound binds, which is the equal-marginal condition's permitted exception

#### Lines 5-6 — Bisect the interior case to `1e-6`

- Algorithm mapping: Same monotone bisection as the outer loop, on one Campaign's marginal revenue
- Reason: Marginal revenue is decreasing in budget because both stages saturate, so the root is unique and bisection is safe

#### Line 7 — Return the bracket midpoint

- Algorithm mapping: Averages the converged bounds
- Reason: The interior root is genuinely inside the bracket, unlike the outer loop where one side is the feasible one, so the midpoint is the best estimate

### Remainder Distribution

Reached when every Campaign's marginal revenue has fallen to zero before the authorized budget is exhausted, yet `SPEND_FULL_BUDGET` requires spending it all.

```python
receivers = [request for request, _ in supported                    # 1
             if _maximum(request) - result[request.campaign_id]
                > _ALLOCATION_TOLERANCE]
while remainder > _ALLOCATION_TOLERANCE and receivers:              # 2
    share = remainder / len(receivers)                              # 3
    moved = 0.0; still_open = []
    for request in receivers:
        room = _maximum(request) - result[request.campaign_id]      # 4
        take = min(share, room)                                     # 5
        result[request.campaign_id] += take
        moved += take
        if room - take > _ALLOCATION_TOLERANCE:                     # 6
            still_open.append(request)
    remainder -= moved
    receivers = still_open
    if moved <= _ALLOCATION_TOLERANCE: break                        # 7
```

#### Line 1 — Consider only Campaigns with headroom below their ceiling

- Algorithm mapping: Filters by remaining room
- Reason: A Campaign already at its maximum cannot absorb any part of the remainder

#### Lines 2-3 — Repeat in rounds, splitting the remaining amount equally among receivers

- Algorithm mapping: Equal split rather than proportional or marginal-ranked
- Reason: At this point every Campaign's marginal return is effectively zero, so no ranking among them is meaningful. Equal split is the neutral choice, and it is disclosed as a policy consequence rather than as an optimization

#### Lines 4-5 — Give each receiver the lesser of its share and its remaining room

- Algorithm mapping: Clamps the transfer at the ceiling
- Reason: Placing the remainder must not violate the bound the post-validation will check

#### Line 6 — Keep a Campaign for the next round only if room remains

- Algorithm mapping: Rebuilds the receiver list each round
- Reason: A Campaign that filled to its ceiling this round drops out, so the next round's equal split concentrates on those that can still take budget

#### Line 7 — Abandon when a full round moves nothing

- Algorithm mapping: Progress guard
- Reason: If every receiver is at its ceiling, the remainder is genuinely unplaceable. Breaking here leaves the shortfall visible to post-validation, which then refuses the plan, rather than looping forever

### Independent Post-Validation

Before any plan is reported, the allocation is re-checked against the constraints it was meant to satisfy, by code that does not share the solver's assumptions.

#### Total not exceeded

`allocated > total_budget + 1e-4` is a problem.

#### Full budget exactly met

Under `SPEND_FULL_BUDGET`, `abs(allocated - total_budget) > 1e-4` is a problem.

#### Every floor respected

`budget < minimum - 1e-6` is a problem, per Campaign.

#### Every ceiling respected

`budget > maximum + 1e-6` is a problem, per Campaign.

#### Every predicted revenue finite and non-negative

`model.expected_revenue(budget)` non-finite or negative is a problem, per Campaign.

Any problem produces `SOLVER_VALIDATION_FAILED`. A solver is a piece of numerical code, and this is what stops a convergence failure from being reported as an optimum. The tolerances differ deliberately: `1e-4` on totals absorbs accumulated summation error across Campaigns, while `1e-6` on individual bounds matches the inner bisection's own convergence tolerance.

## Structured Refusal Instead of a Fabricated Optimum <span class="status-label status-verified" aria-label="Verified"></span>

When no responsible optimization exists the optimizer returns a plan with `is_optimized=false`, a `recommendation_type` naming the failure, and `infeasibility_reasons` explaining it. It never returns an allocation it cannot justify, and it never labels its result `INITIAL_SEED`, which belongs to the separate initializer. Structural and infeasibility problems are *returned*, not raised, so a caller always receives an explanation it can display.

### `PROFIT_OBJECTIVE_NOT_MODELED`

`MAXIMIZE_PROFIT` was requested. The fitted response predicts revenue, not margin, so optimizing revenue and calling it profit would answer a different question than the one asked. Checked first, before any input validation, because the objective decides whether this optimizer is the right tool at all.

### `INFEASIBLE_REQUEST`

The request is structurally invalid. Every problem found is reported together rather than on first failure: no Campaign supplied, a non-finite or negative total budget, duplicate Campaign identifiers, Campaigns mixing currencies, or a Campaign whose minimum exceeds its maximum.

### `NO_SUPPORTED_CAMPAIGN_RESPONSE`

No Campaign survived eligibility filtering, so no optimized allocation can be justified. `excluded_campaign_ids` names every Campaign dropped.

### `INFEASIBLE_CONSTRAINTS`

The bounds cannot accommodate the authorized budget: the minimums total more than is authorized, or under `SPEND_FULL_BUDGET` the maximums total less than the amount that must be spent. Both are checked with `_ALLOCATION_TOLERANCE` slack.

### `SOLVER_VALIDATION_FAILED`

The solver returned an answer that the independent post-validation above rejected.

## Result Types <span class="status-label status-verified" aria-label="Verified"></span>

### `CampaignBudgetRequest`

One Campaign's optimization inputs: `campaign_id`, `constraints` (a canonical `BudgetConstraints`), `initial_budget`, `currency`, `is_active` defaulting true, and optional `current_budget`. `__post_init__` raises `ValueError` when `constraints.campaign_id` differs from `campaign_id`, or when `initial_budget` is negative.

### `CampaignAllocation`

One Campaign's result: identifiers and the three budgets (`current_budget`, `initial_budget`, `optimized_budget`), expected spend and expected revenue at both the initial and optimized budget, the revenue delta, the marginal expected revenue at the optimized point, the `response_support` label, both observed ranges, `is_extrapolated`, and `model_version`. Budgets and revenues are rounded to six decimal places; marginal revenue to nine, because it is a ratio whose informative digits sit further right.

### `OptimizedBudgetPlan`

The complete result, feasible or not. `is_optimized` is true only when every gate passed. Carries the objective and policy echoed back, `authorized_budget` and `allocated_budget`, the expected initial and optimized revenue with their difference, `allocation_basis` of `CAMPAIGN_RESPONSE_MARGINAL_EQUALIZATION`, the two Ad Group disclosure fields, `allocations`, `infeasibility_reasons`, and `excluded_campaign_ids`.

## Extrapolation <span class="status-label status-verified" aria-label="Verified"></span>

A budget outside the range the fit observed is still the solver's answer, but it rests on the curve's shape beyond the evidence. Each allocation therefore carries `is_extrapolated`, computed as `configured_budget < low or configured_budget > high` against `observed_budget_range`, and the dashboard names every extrapolated Campaign rather than letting the number stand unqualified.

This matters most for a Campaign whose budget genuinely bound: its observed range may be narrow precisely because it never had room to grow, which is the case where the optimizer most wants to increase it and has least evidence for how far. Both Campaigns in the committed artifact are extrapolated for exactly this reason.

## Source Files <span class="status-label status-verified" aria-label="Verified"></span>

### `budget_optimizer.py`

Source: `modules/mta_strategy_recommendation/src/budget_optimizer.py`

**Responsibility.** Allocate Campaign budgets against fitted response curves by equalizing marginal expected revenue at a single shadow price, subject to the authorized total and each Campaign's bounds. Attribution is not an input.

**Public entry points.** `optimize_campaign_budgets(requests, response_models, total_budget, objective=MAXIMIZE_REVENUE, budget_usage_policy=SPEND_UP_TO_BUDGET) -> OptimizedBudgetPlan`, with `CampaignBudgetRequest`, `CampaignAllocation`, and `OptimizedBudgetPlan` as the surrounding types. `ALLOCATION_BASIS`, `AD_GROUP_PROJECTION_BASIS`, and `AD_GROUP_OPTIMIZATION_CLAIM` are the exported constant labels.

**Inputs.** A sequence of `CampaignBudgetRequest`, a mapping of Campaign identifier to `CampaignResponseModel`, a total budget, and the two vocabulary values.

**Outputs.** One `OptimizedBudgetPlan`, always. `to_dict()` on the plan and on each allocation produces the JavaScript Object Notation (JSON) shapes the artifact embeds.

**Dependencies.** `math` and `dataclasses` from the standard library; `modules.mta_common.src.budget` for `BudgetConstraints`; `modules.mta_common.src.enums` for `BudgetUsagePolicy` and `StrategyObjective`; `response_model` for `CampaignResponseModel`, `ResponseSupport`, and `MODEL_VERSION`.

**Guarantees.** A returned plan with `is_optimized=true` has passed independent post-validation: within the authorized total, exact under `SPEND_FULL_BUDGET` to within `1e-4`, within every Campaign's floor and ceiling to within `1e-6`, and predicting a finite non-negative revenue for each Campaign. Otherwise `is_optimized` is false and `infeasibility_reasons` is non-empty. `recommendation_type` is `OPTIMIZED_CAMPAIGN_BUDGET` on success and never `INITIAL_SEED`.

**Errors.** `CampaignBudgetRequest` raises `ValueError` when its constraints name a different Campaign or its initial budget is negative. Structural and infeasibility problems are returned as a non-optimized plan rather than raised. `BudgetOptimizerError` is defined for optimizer misuse.

**Verification.** `modules/mta_strategy_recommendation/tests/test_budget_optimizer.py`.

## Verification

- **Scope:** The constrained solver, its bounds handling, and every structured refusal.
- **Cases:** Both budget usage policies; floors and ceilings binding and not binding; the equal-marginal condition across unconstrained Campaigns; the non-binding short-circuit; remainder distribution; and each of the five refusal types.
- **Command:** `uv run python -X utf8 -B -m unittest modules.mta_strategy_recommendation.tests.test_budget_optimizer`.
- **Limitations:** Verifies the solver against the fitted curves it is given. It cannot verify that maximizing those curves raises realized revenue, which requires a compliant experiment.
